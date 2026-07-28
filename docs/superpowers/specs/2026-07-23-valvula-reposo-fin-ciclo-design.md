# Spec — Válvula de reposo al finalizar el ciclo (descompresión abierta salvo vacío)

**Fecha:** 2026-07-23

## Alcance

Al finalizar el ciclo, sin importar la razón (completado normal, cancelado, fallo, emergencia, puertas, sensor ausente, pérdida de conexión), la cámara debe quedar en un estado de reposo seguro:

- Si la cámara **no está en vacío** (`pres_camara >= presion_admosferica - rango_presion_atm`): debe quedar **abierta la válvula de descompresión** correspondiente al modo configurado del ciclo (`descompresion.modo`), no cerrada.
- Si la cámara **está en vacío real** (`pres_camara < presion_admosferica - rango_presion_atm`): debe abrirse la **válvula de aire atmosférico** en su lugar.

Esta regla reemplaza el comportamiento actual, que en distintos puntos:
- cierra incondicionalmente todas las salidas al completar `DescompresionFase` (`_apagar_todo()`), sin dejar nada abierto ni siquiera en vacío;
- en `ProtocoloFallo`, trata "rango normal" y "vacío" como un mismo caso y siempre fuerza aire atmosférico, incluso cuando la cámara está en rango normal (no en vacío) — comportamiento que la spec previa (`2026-07-22-protocolo-fallo-modo-descompresion-design.md`) dejó explícitamente sin cambios ("Sin cambios: el caso Normal/Vacío ... sigue exactamente igual").

**Continúa fuera de alcance:** el estado `FALLA` (posterior a la confirmación de un fallo) no recibe vigilancia continua — la válvula queda fija en el último valor que dejó `ProtocoloFallo` antes de la confirmación. Se acepta este límite porque `FALLA` normalmente dura poco y no hay fases generando presión activamente. Tampoco se modifica la lógica de puertas, sensores críticos, ni el resto del pipeline de fases.

---

## Decisiones de diseño

1. **Mapeo modo → válvula, centralizado en un módulo nuevo** (`valvula_reposo.py`), reutilizado por `DescompresionFase` y por `CicloState`. Mismo criterio que ya usa `ProtocoloFallo._aplicar_paso_modo` (modo 0 se trata como modo 2):

   | Modo configurado | Válvula que queda abierta |
   |---|---|
   | 0 | Lenta (forzado, igual que en `ProtocoloFallo`) |
   | 1 | Rápida |
   | 2 | Lenta |
   | 3 | Rápida |
   | 4 / 5 | Chaqueta + rápida |

   Nota: para el modo 3, este mapeo estático asume que ya se cruzó `presion_cambio` (siempre cierto en los tres puntos donde se usa, porque la cámara ya está en o por debajo de rango atmosférico). `ProtocoloFallo._aplicar_paso_modo` conserva su propio seguimiento dinámico de sub-etapa para cuando la despresurización todavía está en curso — no se toca.

2. **`ProtocoloFallo` reutiliza `_aplicar_paso_modo` como estado de reposo**, en vez de una lógica nueva, porque ya sabe mantener la sub-etapa correcta del modo 3 en vivo. Se separa el caso "rango normal" del caso "vacío real" tanto en `ejecutar()` (disparo) como en `update()` (mantenimiento continuo).

3. **`DescompresionFase` deja de apagar todo al completar.** Para los modos 1–5, la válvula correcta ya está activa en el momento en que se cumple la condición de fin (`_en_presion_atm()`) — el único cambio es no apagarla. Para el modo 0 (que hoy no activa ninguna salida), se fuerza la válvula lenta como reposo por defecto, igual que ya hace `ProtocoloFallo` para ese modo.

4. **Vigilancia continua durante `ESPERANDO_CONFIRMACION` para el caso `COMPLETADO` limpio.** Hoy, cuando el ciclo termina sin pasar por `ProtocoloFallo` (completado normal, sin fallo ni cancelación), nada vuelve a evaluar la presión mientras se espera que el operador confirme — si la cámara se sigue enfriando y cae en vacío en ese lapso, no se corrige. Se agrega un método en `CicloState` que aplica la misma regla en cada tick, sólo quando `_resultado_pendiente == COMPLETADO` (los demás casos ya están cubiertos porque `ProtocoloFallo.update()` corre continuamente en esa misma ventana).

---

## Arquitectura

### Módulo nuevo: `src/autoclave/state_machine/cycle_phases/valvula_reposo.py`

```python
def abrir_valvula_modo(set_do, modo: int) -> None:
    modo_efectivo = 2 if modo == 0 else modo
    if modo_efectivo == 1:
        set_do.descompresion_rapida_on()
    elif modo_efectivo == 2:
        set_do.descompresion_lenta_on()
    elif modo_efectivo == 3:
        set_do.descompresion_rapida_on()
    elif modo_efectivo in (4, 5):
        set_do.descompresion_chaqueta_on()
        set_do.descompresion_rapida_on()


def cerrar_valvulas_descompresion(set_do) -> None:
    set_do.descompresion_rapida_off()
    set_do.descompresion_lenta_off()
    set_do.descompresion_chaqueta_off()
```

### `DescompresionFase` (`descompresion.py`)

Nuevo método `_finalizar()`:

```python
def _finalizar(self) -> FaseResult:
    p = self._pres_camara()
    if p is not None and p < self._pres_atm() - self._rango_atm():
        self._apagar_todo()
        self.set_do.aire_admosferico_camara_on()
    else:
        self.set_do.aire_admosferico_camara_off()
        abrir_valvula_modo(self.set_do, self._modo)
    return FaseResult.COMPLETADO
```

Reemplaza los `return FaseResult.COMPLETADO` (y el `self._apagar_todo()` que los precede cuando existe) en:
- `_tick_modo_0` — hoy no llama `_apagar_todo()`; pasa a llamar `self._finalizar()`.
- `_tick_modo_1`, `_tick_modo_2` — hoy llaman `self._apagar_todo()` antes; pasan a `return self._finalizar()`.
- `_tick_modo_3` (rama `else`/rápida) — igual.
- `_tick_sub_descompresion` (usada por modos 4 y 5) — igual.

`_apagar_todo()` se mantiene sin cambios (se sigue usando al inicio de la fase y en el timeout de `FALLO`).

### `ProtocoloFallo` (`protocolo_fallo.py`)

**`ejecutar()`** — se calcula `_modo`/`_sub_etapa` una sola vez al principio (antes ramificado sólo dentro del caso presurizado), y se separan tres casos en vez de dos:

```python
if pres is None:
    logger.warning(...)
else:
    self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
    self._sub_etapa = "lenta" if self._modo == 3 else None

    if pres > atm + rango:
        self._presurizado_al_disparo = True
        self._t_timeout_descompresion = self._calcular_timeout()
        self._aplicar_paso_modo(pres)
    elif pres < atm - rango:
        # Vacío real → aire atmosférico
        self.set_do.aire_admosferico_camara_on()
    else:
        # Rango normal, sin presión que evacuar → deja la válvula del modo
        self._aplicar_paso_modo(pres)
```

**`update()`** — mismo criterio de tres ramas en la sección de "Gestión dinámica de presión":

```python
if pres > atm + rango:
    ... # sin cambios (ambas sub-ramas existentes)
elif pres < atm - rango:
    # Vacío real
    self.set_do.descompresion_rapida_off()
    self.set_do.descompresion_lenta_off()
    self.set_do.descompresion_chaqueta_off()
    self.set_do.aire_admosferico_camara_on()
else:
    # Rango normal → mantener la válvula del modo, aire atmosférico cerrado
    self.set_do.aire_admosferico_camara_off()
    self._aplicar_paso_modo(pres)
```

La lógica del buzzer no cambia.

### `CicloState` (`ciclo.py`)

En `run()`, dentro del bloque de espera de confirmación:

```python
if self._resultado_pendiente is not None:
    if self.estado.get_flag("CICLO_CONFIRMADO"):
        ...
    if self._resultado_pendiente == CicloResultado.COMPLETADO:
        self._mantener_valvula_reposo()
    else:
        self._protocolo.update()
    return CicloResultado.ESPERANDO_CONFIRMACION
```

Nuevo método:

```python
def _mantener_valvula_reposo(self):
    """Mientras se espera confirmación tras un COMPLETADO limpio (sin
    ProtocoloFallo): si la cámara cae en vacío por enfriamiento, abre aire
    atmosférico; si no, mantiene la válvula de descompresión del modo
    configurado."""
    pres = self.estado.sensores_pres.get("pres_camara")
    if pres is None:
        return
    atm   = self.config.get("presion_admosferica") or 101.3
    rango = self.config.get("rango_presion_atm")   or 20.0

    if pres < atm - rango:
        cerrar_valvulas_descompresion(self.set_do)
        self.set_do.aire_admosferico_camara_on()
    else:
        self.set_do.aire_admosferico_camara_off()
        modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
        abrir_valvula_modo(self.set_do, modo)
```

---

## Tests

**Archivo nuevo:** `tests/test_valvula_reposo.py` — pruebas directas del módulo `valvula_reposo.py` para cada modo (0–5) y el cierre.

**`tests/test_descompresion_fase.py`** — actualizar los tests existentes que hoy asumen apagado total al completar:
- `test_modo_1_completa_y_apaga_salidas` → renombrar/ajustar a `test_modo_1_completa_y_deja_rapida_abierta`: `descompresion_rapida_on` sigue activo, `descompresion_rapida_off` **no** se llama tras completar (con presión en rango normal).
- `test_modo_2_completa_y_apaga_salidas` → análogo con lenta.
- Nuevos: cada modo (0–5) completando con presión en **vacío real** (`pres < 81.3` con la config de test) → `aire_admosferico_camara_on` llamado, válvulas de descompresión apagadas.
- Nuevo: modo `0` completando en rango normal → `descompresion_lenta_on` llamado (forzado).
- `test_apagar_todo_al_fallo_timeout` no cambia (timeout sigue usando `_apagar_todo()` sin pasar por `_finalizar()`).

**`tests/test_protocolo_fallo_modo_descompresion.py`** — actualizar/agregar:
- `test_normal_vacio_sin_cambios` ya no aplica tal cual (el nombre asumía que normal y vacío se comportan igual); se reemplaza por dos tests: uno con `pres` en rango normal (→ `_aplicar_paso_modo` abre la válvula del modo, sin aire atmosférico) y otro con `pres` en vacío real (→ `aire_admosferico_camara_on`, comportamiento heredado).
- Nuevo: `update()` con transición de presurizado → rango normal → válvula del modo permanece abierta, aire atmosférico **no** se activa (reemplaza la expectativa actual de `test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm`, que pasa a dividirse en un caso "rango normal" y un caso "vacío real").

**Archivo nuevo:** `tests/test_ciclo_valvula_reposo.py` — para `CicloState._mantener_valvula_reposo()`:
- `COMPLETADO` pendiente, presión en rango normal → abre la válvula del modo configurado, no aire atmosférico.
- `COMPLETADO` pendiente, presión cae en vacío en un tick posterior (simulando enfriamiento durante la espera) → cierra descompresión, abre aire atmosférico.
- `FALLO`/`CANCELADO` pendientes → sigue llamando `self._protocolo.update()`, no `_mantener_valvula_reposo()`.

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/valvula_reposo.py` | Crear |
| `src/autoclave/state_machine/cycle_phases/descompresion.py` | Modificar — `_finalizar()`, actualizar los `return` de fin de modo |
| `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py` | Modificar — separar vacío real de rango normal en `ejecutar()` y `update()` |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — `_mantener_valvula_reposo()`, llamada condicional en `run()` |
| `tests/test_descompresion_fase.py` | Modificar — actualizar tests de finalización, agregar casos de vacío |
| `tests/test_protocolo_fallo_modo_descompresion.py` | Modificar — dividir normal/vacío |
| `tests/test_valvula_reposo.py` | Crear |
| `tests/test_ciclo_valvula_reposo.py` | Crear |
