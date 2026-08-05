# Selector de ciclo por click en la pantalla principal

## Contexto

La pantalla principal (`InterfazPrincipal` en `src/autoclave/ui/window/main_window.py`) muestra
el número de ciclo (`_lbl_n_ciclo`, hoy fijo en "01") junto al nombre del ciclo activo
(`_lbl_ciclo_nombre`). No existe ninguna forma de cambiar cuál es el ciclo activo desde esta
pantalla — el operador debe editar los parámetros vía `ParametrosCicloView` (PySide6), pero eso
no permite elegir *cuál* ciclo de usuario queda seleccionado para la próxima corrida.

Investigando el flujo actual se encontró que el ciclo activo se fija una única vez al arrancar
el backend:

```python
# backend/context.py
self.cycle_manager.set_default_cycle("bowe_dick")
```

Y ese objeto `Cycle` queda enterrado por referencia dentro de `ControlLoop.__init__` →
`StateMachine.__init__` → cada sub-estado (`preparacion_state`, `preparado_state`, `CicloState`)
→ cada fase del ciclo (`PrecalentamientoFase`, `CalentamientoFase`, etc.), todos construidos una
sola vez al levantar el backend. Cambiar solo `cycle_manager.selected_cycle` no tiene ningún
efecto sobre el loop en vivo: hay que reconstruir la `StateMachine` completa con el nuevo `Cycle`
para que el cambio se propague a todos esos componentes.

## Objetivo

Permitir que el operador cambie el ciclo de usuario activo haciendo click en el número de ciclo
de la pantalla principal, siempre que la máquina no esté en medio de un ciclo.

## Alcance

- Solo ciclos con `source == "user"` son seleccionables (son los editables/operativos; iguales a
  los que ya lista `ParametrosCicloView`).
- Solo permitido cuando el estado global de la máquina no es `CICLO`. En cualquier otro estado
  (PREPARACION, PREPARADO, FALLA, HIBERNACION) el click está habilitado.
- El cambio es solo en memoria — no se persiste en disco. Al reiniciar el backend, vuelve a
  arrancar con `"bowe_dick"` (comportamiento actual sin cambios).
- No requiere sesión de usuario iniciada.

## Backend

### `ControlLoop.set_active_cycle(cycle)` — `services/domain/loop/control_loop.py`

Guarda `cap` como atributo de instancia en `__init__` (hoy se pasa a `StateMachine` pero no se
conserva, y se necesita para reconstruirla). Nuevo método, mismo patrón de retorno
`(ok: bool, motivo: str)` que ya usa `enter_test_mode()`:

```python
def set_active_cycle(self, cycle) -> tuple[bool, str]:
    if self.estado.get_machine_state() == GlobalState.CICLO:
        return False, "No se puede cambiar de ciclo mientras hay uno en curso."
    self.cycle = cycle
    self.state_machine = StateMachine(
        io=self.link, estado=self.estado, set_do=self.set_do,
        cycle=cycle, config=self.config_manager, cap=self.cap,
    )
    return True, ""
```

Reconstruir `StateMachine` es seguro aquí porque solo ocurre fuera de `CICLO`: no hay fases en
curso cuyo estado interno se pierda.

### Endpoints — `backend/server.py`

`GET /cycles` — lista todos los ciclos cargados (para que la UI filtre por `source`):

```python
@app.get("/cycles")
def list_cycles():
    return [
        {"id": c.id, "name": c.name, "source": getattr(c, "source", "user")}
        for c in context.cycle_manager.cycles.values()
    ]
```

`POST /cycle/select` — cambia el ciclo activo:

```python
class _SelectCycleBody(BaseModel):
    cycle_id: str

@app.post("/cycle/select")
def select_cycle(body: _SelectCycleBody):
    cycle = context.cycle_manager.cycles.get(body.cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail=f"Ciclo '{body.cycle_id}' no encontrado")
    if getattr(cycle, "source", "user") != "user":
        raise HTTPException(status_code=422, detail="Solo se pueden seleccionar ciclos de usuario")

    ok, reason = context.control_loop.set_active_cycle(cycle)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)

    context.cycle_manager.set_default_cycle(body.cycle_id)
    return {"ok": True, "id": cycle.id, "name": cycle.name}
```

`set_default_cycle` ya existe en `CycleManager` y ya valida existencia — se reutiliza tal cual
para sincronizar `cycle_manager.selected_cycle` con el nuevo ciclo activo (usado por
`cycle_logger`, `GET /cycle`, etc.). Se llama solo después de que `set_active_cycle` confirma el
cambio, para no desincronizar el puntero si el control loop rechazó el cambio.

## UI service layer — `ui/service_ui/ui_service_backend.py`

```python
def list_user_cycles(self) -> list[dict]:
    """Lista los ciclos de usuario disponibles para seleccionar."""
    try:
        cycles = self.backend.get(path="/cycles")
        return [c for c in cycles if c.get("source") == "user"]
    except Exception as e:
        logger.warning("list_user_cycles error: %s", e)
        return []

def select_cycle(self, cycle_id: str) -> tuple[bool, str]:
    """Cambia el ciclo activo. Retorna (ok, motivo — vacío si ok)."""
    try:
        self.backend.post(path="/cycle/select", body={"cycle_id": cycle_id})
        return True, ""
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return False, detail
    except requests.RequestException as e:
        return False, f"No se pudo contactar al backend: {e}"
```

## UI — `ui/window/main_window.py` (`InterfazPrincipal`)

### Habilitar/deshabilitar el click

Se agrega estado `self._cycle_selector_habilitado = False` en `__init__`, y una función
llamada junto a `_upd_listo()` dentro de `_update_ui()` (cada 1s), siguiendo el mismo patrón de
bind/unbind condicional que ya usa `_upd_listo()` para `_boton_iniciar`:

```python
def _upd_cycle_selector_habilitado(self):
    habilitado = self.ui_service.get_estado_global() != "CICLO"
    if habilitado == self._cycle_selector_habilitado:
        return
    self._cycle_selector_habilitado = habilitado
    if habilitado:
        self._lbl_n_ciclo.bind("<Button-1>", lambda e: self._abrir_selector_ciclo())
        self._lbl_n_ciclo.configure(cursor="hand2")
    else:
        self._lbl_n_ciclo.unbind("<Button-1>")
        self._lbl_n_ciclo.configure(cursor="")
```

`_lbl_n_ciclo` es el widget usado como click target en ambos layouts (landscape: panel
izquierdo; portrait: banda superior) — es el único elemento de "info de ciclo" presente e
idéntico en ambas variantes de layout. El binding debe reaplicarse tras cada
`_rebuild_layout()` (cambio de orientación), igual que el resto de los bindings dependientes de
estado — reseteando `self._cycle_selector_habilitado = False` antes de reconstruir para forzar
el rebind en el siguiente tick.

### Diálogo selector

Mismo estilo visual que `CycleWindow._confirmar_abort` (`tk.Toplevel` con `overrideredirect`,
centrado sobre la ventana, fondo `CLR_DARK`): una lista vertical de `ctk.CTkButton`, uno por
ciclo de usuario, resaltando el que coincide con el ciclo activo actual
(`self.ui_service.get_cycle_param("id")`), más un botón "Cancelar".

```python
def _abrir_selector_ciclo(self):
    cycles = self.ui_service.list_user_cycles()
    if not cycles:
        self._mostrar_toast("No hay ciclos de usuario disponibles.")
        return

    current_id = self.ui_service.get_cycle_param("id")

    dlg = tk.Toplevel(self)
    dlg.overrideredirect(True)
    dlg.configure(bg=CLR_DARK)
    dlg.resizable(False, False)
    dlg.grab_set()
    # título "Seleccionar ciclo"
    # un CTkButton por ciclo — el que coincide con current_id se muestra resaltado/deshabilitado
    # click en un ciclo distinto al activo → self._seleccionar_ciclo(dlg, cycle_id, name)
    # botón "Cancelar" → dlg.destroy()
    # centrado sobre self, igual que _confirmar_abort en cycle_window.py

def _seleccionar_ciclo(self, dlg, cycle_id, name):
    dlg.destroy()
    ok, motivo = self.ui_service.select_cycle(cycle_id)
    if not ok:
        self._mostrar_toast(motivo)
        return
    # actualización optimista inmediata — no esperar el refresco de /cycle (cada ~5s)
    self.cycle_name = name
    self._lbl_ciclo_nombre.configure(text=self.cycle_name.upper())
```

## Casos de error cubiertos

- **Ciclo en curso**: el click está deshabilitado (cursor normal, sin binding) mientras
  `estado_global == "CICLO"`. Si por una condición de carrera el backend igual recibe la
  petición (p. ej. la máquina entra a CICLO justo entre el click y el POST), `set_active_cycle`
  devuelve `409` y el operador ve un toast con el motivo — no se aplica el cambio.
- **Sin ciclos de usuario disponibles**: toast informativo, no se abre el diálogo.
- **Backend no responde / error de red**: toast con el mensaje de `select_cycle`.

## Fuera de alcance

- Persistencia del ciclo seleccionado entre reinicios del backend.
- Selección de ciclos de fábrica (`source == "factory"`).
- Cambiar el valor mostrado en `_lbl_n_ciclo` ("01") — permanece como está hoy; no representa el
  ciclo seleccionado, solo se usa como zona de click.
