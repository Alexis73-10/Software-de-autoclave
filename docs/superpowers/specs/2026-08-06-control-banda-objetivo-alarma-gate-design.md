# Spec — Separar umbral de válvula, umbral de alarma y gate de listo/inicio (chaqueta y drenaje) + debounce de apagado

**Fecha:** 2026-08-06

## Alcance

Hoy, en `preparado.py` (estado PREPARADO) y `preparacion.py` (estado PREPARACION), el control de presión de chaqueta y temperatura de drenaje usa un único umbral (el borde de la banda `objetivo ± rango`, o un techo único en el caso de drenaje) para tres cosas a la vez: accionar la válvula, disparar la alarma bloqueante, y decidir si el equipo está "listo" (gate que permite avanzar de PREPARACION a PREPARADO, y de PREPARADO a iniciar el ciclo). Esto hace que la alarma bloqueante (`CHAQUETA_FRIA`, futura `TEMP_DRENAJE_ALTA` con banda) dispare casi cada vez que el equipo arranca frío, porque la válvula no reacciona hasta que ya se cruzó el borde tolerado.

Esta spec:

1. Separa esas tres responsabilidades usando el valor objetivo como umbral de la válvula (reacciona antes, sin tolerancia) y el borde de la banda (`objetivo ± rango`) como umbral de la alarma bloqueante y del gate de listo/inicio (sin cambiar esos umbrales).
2. Aplica esto a presión de chaqueta (`presion_chaqueta`/`rango_presion_chaqueta`, ya existente) y a temperatura de drenaje, agregando un parámetro nuevo `rango_temp_drenaje` para poder darle la misma banda.
3. Agrega un contador de 3 ticks para confirmar el apagado de `vapor_chaqueta`, `agua_intercambiador` y `aire_admosferico_camara`, evitando chattering de la válvula ahora que el umbral de encendido/apagado está más pegado al objetivo.

**Fuera de alcance:**
- `mantener_presion_camara()`/`igualar_presion_camara()` (presión de cámara vs. atmosférica) no cambia su lógica de banda — ya es simétrica por diseño (aire de un lado, descompresión rápida del otro). Solo se le agrega el debounce de apagado para `aire_admosferico_camara`.
- `descompresion_rapida`/`descompresion_lenta` no llevan debounce de apagado (no se pidió).
- No se agrega alarma de "drenaje muy frío": no existe acción física para ese caso (no hay calefactor de drenaje), así que el lado bajo de la banda de drenaje solo participa en el gate de listo, nunca en una alarma.
- No se toca `ciclo.py` (fase CICLO) ni su propio `_mantener_drenaje()` — ese ya tiene su propio debounce (ver spec `2026-08-05-drenaje-espera-confirmacion-debounce-design.md`), es una ruta de código distinta.

---

## Decisiones de diseño

1. **Helper compartido `control_banda.py`** en vez de repetir la lógica 4 veces (chaqueta/drenaje × preparado.py/preparacion.py). Expone una función pura `evaluar_banda()` y una clase pequeña con estado `ConfirmadorApagado`.

2. **Un solo umbral por rol, no una banda con histéresis para la válvula.** La válvula reacciona en cuanto `actual` cruza el objetivo exacto, en la dirección que corresponda (chaqueta: enciende si `presión < objetivo`; drenaje: enciende si `temp > objetivo`, que es el comportamiento actual sin cambios). La banda (`objetivo ± rango`) ya no interviene en cuándo enciende la válvula — solo en cuándo se considera "fuera de tolerancia" (alarma) o "no listo" (gate).

3. **El gate de listo/inicio exige la banda completa, en ambos sentidos, sin cambios de valor** respecto a hoy — solo se separa de la válvula. `dentro_de_banda = (objetivo - rango) <= actual <= (objetivo + rango)`.

4. **Confirmación de apagado con contador de ticks, no de tiempo.** A diferencia de `generar_alarma_temporizada` (que usa `time.time()` y ya existe para las alarmas), el debounce de válvula usa un contador de ticks consecutivos — mismo estilo que `_DEBOUNCE_LECTURAS` en `esterilizacion.py`. Solo se exige para la transición a **apagado**; el encendido sigue siendo inmediato (reaccionar rápido a una desviación real es más seguro que retrasarlo).

5. **`rango_temp_drenaje` va en `global_params.json`**, junto a `temp_segura_drenaje`, porque ese parámetro no es por-ciclo (a diferencia de `presion_chaqueta`/`rango_presion_chaqueta`, que sí viven en `parameters.globals` de cada perfil de ciclo). Valor por defecto: `5` (°C), banda 65–75°C sobre el `temp_segura_drenaje` actual de 70°C.

6. **Las alarmas de tiempo (`generar_alarma_temporizada`, `tiempo_estable_alarma`) no se tocan.** Siguen funcionando igual, solo cambia qué condición las dispara (borde de banda en vez de umbral único). La asimetría existente entre `preparado.py` (usa `generar_alarma_temporizada`) y `preparacion.py` (reporta la alarma de inmediato) se mantiene tal cual — no es parte de este cambio.

---

## Arquitectura

### Nuevo módulo: `src/autoclave/state_machine/states/control_banda.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoBanda:
    debe_activar: bool       # válvula debe estar ON, umbral = objetivo (sin tolerancia)
    fuera_por_debajo: bool   # actual < objetivo - rango  (alarma "frío/bajo")
    fuera_por_encima: bool   # actual > objetivo + rango  (alarma "caliente/alto")
    dentro_de_banda: bool    # objetivo-rango <= actual <= objetivo+rango (gate listo/inicio)


def evaluar_banda(actual: float, objetivo: float, rango: float, activar_si_bajo: bool) -> ResultadoBanda:
    """Evalúa un control de banda con objetivo como umbral de válvula.

    activar_si_bajo=True  → la válvula sube el valor (ej. vapor_chaqueta): enciende si actual < objetivo.
    activar_si_bajo=False → la válvula baja el valor (ej. agua_intercambiador): enciende si actual > objetivo.
    """
    limite_inf = objetivo - rango
    limite_sup = objetivo + rango
    debe_activar = actual < objetivo if activar_si_bajo else actual > objetivo
    return ResultadoBanda(
        debe_activar=debe_activar,
        fuera_por_debajo=actual < limite_inf,
        fuera_por_encima=actual > limite_sup,
        dentro_de_banda=limite_inf <= actual <= limite_sup,
    )


class ConfirmadorApagado:
    """Exige N ticks consecutivos de 'debe estar apagado' antes de confirmar
    el apagado real de una salida. El encendido no pasa por aquí — solo el
    apagado, para evitar chattering cuando el umbral de encendido está
    pegado al objetivo (sin histéresis)."""

    def __init__(self, ticks_requeridos: int = 3):
        self._ticks_requeridos = ticks_requeridos
        self._contador = 0

    def confirmar(self, debe_estar_apagado: bool) -> bool:
        if debe_estar_apagado:
            self._contador += 1
        else:
            self._contador = 0
        return self._contador >= self._ticks_requeridos

    def reset(self):
        self._contador = 0
```

### `preparado.py` — `__init__`

Agregar tres confirmadores, uno por válvula:

```python
self._confirmador_chaqueta = ConfirmadorApagado()
self._confirmador_drenaje = ConfirmadorApagado()
self._confirmador_aire_camara = ConfirmadorApagado()
```

### `preparado.py` — `mantener_chaqueta()`

```python
def mantener_chaqueta(self):
    press_chaqueta = self.estado.sensores_pres["pres_chaqueta"]
    press_obj = self.cycle.get_param("globals", "presion_chaqueta")
    rango = self.cycle.get_param("globals", "rango_presion_chaqueta")

    if not self.estado.sensores_di["vapor_suministro"]:
        self.set_do.vapor_chaqueta_off()
        self._confirmador_chaqueta.reset()
        self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
        self.alarm_manager.clear("CHAQUETA_FRIA")
        self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
        return True
    else:
        self.alarm_manager.clear("SUMINISTRO_VAPOR")

    r = evaluar_banda(press_chaqueta, press_obj, rango, activar_si_bajo=True)

    if r.debe_activar:
        self.set_do.vapor_chaqueta_on()
        self._confirmador_chaqueta.reset()
    elif self._confirmador_chaqueta.confirmar(True):
        self.set_do.vapor_chaqueta_off()

    if r.fuera_por_debajo:
        self.generar_alarma_temporizada("CHAQUETA_FRIA")
    else:
        self.alarm_manager.clear("CHAQUETA_FRIA")

    if r.fuera_por_encima:
        self.generar_alarma_temporizada("CHAQUETA_SOBRECALENTADA")
    else:
        self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")

    return r.dentro_de_banda
```

Nota: antes, `CHAQUETA_SOBRECALENTADA` limpiaba solo implícitamente (nunca se llamaba `clear` explícito en la rama "dentro de banda" para esa alarma en algunos casos). Con `evaluar_banda()` ambas alarmas se limpian explícitamente cuando no aplica su condición — comportamiento más consistente, sin cambiar cuándo disparan.

### `preparado.py` — `mantener_drenaje()`

```python
def mantener_drenaje(self):
    temp = self.estado.sensores_temp["temp_drenaje"]
    temp_obj = self.config.get("temp_segura_drenaje")
    rango = self.config.get("rango_temp_drenaje")

    r = evaluar_banda(temp, temp_obj, rango, activar_si_bajo=False)

    if r.debe_activar:
        self.set_do.agua_intercambiador_on()
        self._confirmador_drenaje.reset()
    elif self._confirmador_drenaje.confirmar(True):
        self.set_do.agua_intercambiador_off()

    if r.fuera_por_encima:
        self.generar_alarma_temporizada("TEMP_DRENAJE_ALTA")
    else:
        self.alarm_manager.clear("TEMP_DRENAJE_ALTA")

    return r.dentro_de_banda
```

(sin alarma de lado bajo — ver "fuera de alcance")

### `preparado.py` — `mantener_presion_camara()`

Sin cambios de umbral. Solo se agrega el confirmador al apagar `aire_admosferico_camara`:

```python
if min_p <= presion_camara <= max_p:
    if self._confirmador_aire_camara.confirmar(True):
        self.set_do.aire_admosferico_camara_off()
    self.set_do.descompresion_rapida_off()
    ...
    return True

if presion_camara < min_p:
    self.set_do.aire_admosferico_camara_on()
    self._confirmador_aire_camara.reset()
    ...
```

### `preparacion.py`

Mismos cambios en espejo: `suministrar_vapor_chaqueta()`, `verificar_temperatura_drenaje()`, `igualar_presion_camara()` — mismos confirmadores nuevos en `__init__`, misma llamada a `evaluar_banda()`. La diferencia con `preparado.py` es que aquí las alarmas se reportan de inmediato (sin `generar_alarma_temporizada`, que no existe en este archivo) — se mantiene así.

### `global_params.json`

```json
"rango_temp_drenaje": {"value": 5, "type": "int", "unit": "°C"},
```

(junto a `temp_segura_drenaje`)

---

## Tests

**Nuevo: `tests/test_control_banda.py`**
- `evaluar_banda`, `activar_si_bajo=True`: `debe_activar` solo si `actual < objetivo`; `fuera_por_debajo`/`fuera_por_encima` solo al cruzar `objetivo±rango`; casos en el borde exacto (`actual == objetivo`, `actual == objetivo-rango`).
- `evaluar_banda`, `activar_si_bajo=False`: misma cobertura, dirección invertida.
- `ConfirmadorApagado`: no confirma en tick 1 ni 2; confirma en tick 3; se resetea si en el tick 2 llega `False`; `reset()` explícito vuelve a 0.

**`tests/test_preparado_chaqueta.py`** — actualizar/agregar:
- La válvula enciende con `presión == objetivo - 1` (antes solo encendía bajo `limite_inf`) — confirma que ahora reacciona en el objetivo, no en el borde.
- La alarma `CHAQUETA_FRIA` NO dispara con `presión` entre `objetivo` y `limite_inf` (zona antes bloqueante, ahora tolerada).
- La alarma sigue dispando bajo `limite_inf` (sin cambios de umbral de alarma).
- El apagado de `vapor_chaqueta` requiere 3 llamadas consecutivas con `presión >= objetivo` antes de invocar `vapor_chaqueta_off`; una lectura baja intermedia resetea el conteo.

**Nuevo: `tests/test_preparado_drenaje.py`** (no existía cobertura directa de `mantener_drenaje`):
- Válvula enciende con `temp > temp_segura` (sin cambios).
- Alarma `TEMP_DRENAJE_ALTA` NO dispara entre `temp_segura` y `temp_segura + rango_temp_drenaje`; sí dispara por encima.
- Gate (`mantener_drenaje()` retorna `False`) si `temp < temp_segura - rango_temp_drenaje` (banda baja, aunque sin alarma).
- Apagado de `agua_intercambiador` requiere 3 lecturas consecutivas `<= objetivo`.

**`tests/test_preparacion_chaqueta.py`** — mismas actualizaciones que `test_preparado_chaqueta.py`, adaptadas a `suministrar_vapor_chaqueta()`.

**Nuevo: `tests/test_preparacion_temperatura_drenaje.py`** — mismas pruebas que `test_preparado_drenaje.py`, adaptadas a `verificar_temperatura_drenaje()`.

**`tests/test_preparacion_presion_camara.py`** — agregar caso de debounce de apagado para `aire_admosferico_camara` (3 lecturas dentro de rango antes de `aire_admosferico_camara_off`).

**Nuevo: `tests/test_preparado_presion_camara.py`** (no existía cobertura directa de `mantener_presion_camara` en `preparado.py`, solo mockeada desde otros tests) — mismo caso de debounce de apagado.

---

## Archivos afectados

| Archivo | Acción |
|---|---|
| `src/autoclave/state_machine/states/control_banda.py` | Crear — `ResultadoBanda`, `evaluar_banda()`, `ConfirmadorApagado` |
| `src/autoclave/state_machine/states/preparado.py` | Modificar — `mantener_chaqueta()`, `mantener_drenaje()`, `mantener_presion_camara()`, `__init__` (confirmadores) |
| `src/autoclave/state_machine/states/preparacion.py` | Modificar — `suministrar_vapor_chaqueta()`, `verificar_temperatura_drenaje()`, `igualar_presion_camara()`, `__init__` (confirmadores) |
| `src/autoclave/config/global_params.json` | Modificar — agregar `rango_temp_drenaje` |
| `tests/test_control_banda.py` | Crear |
| `tests/test_preparado_drenaje.py` | Crear |
| `tests/test_preparacion_temperatura_drenaje.py` | Crear |
| `tests/test_preparado_chaqueta.py` | Modificar |
| `tests/test_preparacion_chaqueta.py` | Modificar |
| `tests/test_preparacion_presion_camara.py` | Modificar |
| `tests/test_preparado_presion_camara.py` | Crear |
