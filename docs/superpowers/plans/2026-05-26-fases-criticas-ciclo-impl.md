# Fases Críticas del Ciclo — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el módulo de vapor saturado (Antoine) y las tres fases críticas del ciclo: calentamiento, estabilización y esterilización, incluyendo verificación transversal de sensores en CicloState.

**Architecture:** Un módulo nuevo `steam.py` provee `p_saturacion_kpa(T)` usando la ecuación de Antoine. `BaseFase` expone un helper `_verificar_vapor_saturado()`. `CicloState` agrega verificación de sensores críticos antes de cada tick de fase. Las tres fases implementan lógica propia sin repetir verificaciones de seguridad (ya manejadas por CicloState).

**Tech Stack:** Python 3.14, unittest.mock (tests), pytest, estructura BaseFase existente.

---

## Mapa de archivos

| Archivo | Acción |
|---------|--------|
| `src/autoclave/core/steam.py` | Crear — función `p_saturacion_kpa()` |
| `src/autoclave/state_machine/cycle_phases/base_fase.py` | Modificar — agregar import de steam + helper `_verificar_vapor_saturado()` |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — agregar constantes de sensores críticos + paso 4 en `run()` |
| `src/autoclave/state_machine/cycle_phases/calentamiento.py` | Reemplazar — implementación completa |
| `src/autoclave/state_machine/cycle_phases/estabilizacion.py` | Reemplazar — implementación completa |
| `src/autoclave/state_machine/cycle_phases/esterilizacion.py` | Reemplazar — implementación completa |
| `src/autoclave/cycles/factory/instrumental_134.json` | Modificar — agregar parámetros nuevos |
| `src/autoclave/cycles/factory/bowe_dick.json` | Modificar — agregar parámetros nuevos |
| `tests/test_steam.py` | Crear |
| `tests/test_calentamiento_fase.py` | Crear |
| `tests/test_estabilizacion_fase.py` | Crear |
| `tests/test_esterilizacion_fase.py` | Crear |
| `tests/test_ciclo_sensores.py` | Crear |

---

## Task 1: Módulo `steam.py` — ecuación de Antoine

**Files:**
- Create: `src/autoclave/core/steam.py`
- Test: `tests/test_steam.py`

- [ ] **Step 1: Crear test con valores conocidos de IAPWS**

```python
# tests/test_steam.py
from autoclave.core.steam import p_saturacion_kpa


def test_p_saturacion_100():
    result = p_saturacion_kpa(100)
    assert abs(result - 101.3) < 1.0, f"Esperado ~101.3 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_121():
    result = p_saturacion_kpa(121)
    assert abs(result - 205.0) < 1.0, f"Esperado ~205.0 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_134():
    result = p_saturacion_kpa(134)
    assert abs(result - 302.9) < 1.0, f"Esperado ~302.9 kPa, obtenido {result:.1f} kPa"


def test_p_saturacion_monotonica():
    """Presión de saturación debe crecer con la temperatura."""
    temps = [100, 110, 121, 130, 134, 140]
    presiones = [p_saturacion_kpa(t) for t in temps]
    for i in range(len(presiones) - 1):
        assert presiones[i] < presiones[i + 1]
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_steam.py -v
```

Esperado: `ModuleNotFoundError: No module named 'autoclave.core.steam'`

- [ ] **Step 3: Crear `steam.py`**

```python
# src/autoclave/core/steam.py
#
# Constantes NIST WebBook para agua líquida, rango válido 99–145 °C.
# log₁₀(P_kPa) = A - B / (C + T_celsius)

_A = 7.26509
_B = 1810.94
_C = 244.485


def p_saturacion_kpa(t_celsius: float) -> float:
    """Presión de saturación del vapor de agua en kPa absolutos. Rango válido: 99–145°C."""
    return 10 ** (_A - _B / (_C + t_celsius))
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```
pytest tests/test_steam.py -v
```

Esperado: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/core/steam.py tests/test_steam.py
git commit -m "feat: módulo steam con ecuación de Antoine para P_sat(T)"
```

---

## Task 2: Helper `_verificar_vapor_saturado()` en `BaseFase`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/base_fase.py`

- [ ] **Step 1: Escribir test del helper**

```python
# tests/test_steam.py  — agregar al final del archivo existente
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.base_fase import BaseFase


def _make_base_fase():
    estado = MagicMock()
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    alarms = MagicMock()
    # BaseFase no puede instanciarse directamente (update() es abstracto),
    # usamos una subclase mínima.
    class FaseTest(BaseFase):
        name = "TEST"
        def reset(self): pass
        def update(self): pass
    return FaseTest(estado, set_do, cycle, config, alarms)


def test_verificar_vapor_saturado_dentro_tolerancia():
    fase = _make_base_fase()
    # P_sat(134°C) ≈ 302.2 kPa — dentro de ±10 kPa → True
    assert fase._verificar_vapor_saturado(134.0, 302.2, 10.0) is True


def test_verificar_vapor_saturado_fuera_tolerancia_alta():
    fase = _make_base_fase()
    # P_real = 320 kPa, P_sat ≈ 302.2 → delta = 17.8 > 10 → False
    assert fase._verificar_vapor_saturado(134.0, 320.0, 10.0) is False


def test_verificar_vapor_saturado_fuera_tolerancia_baja():
    fase = _make_base_fase()
    # P_real = 285 kPa, P_sat ≈ 302.2 → delta = 17.2 > 10 → False
    assert fase._verificar_vapor_saturado(134.0, 285.0, 10.0) is False
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_steam.py::test_verificar_vapor_saturado_dentro_tolerancia -v
```

Esperado: `AttributeError: 'FaseTest' object has no attribute '_verificar_vapor_saturado'`

- [ ] **Step 3: Agregar import y helper a `base_fase.py`**

Agregar al inicio del archivo, después de los imports existentes:

```python
from autoclave.core.steam import p_saturacion_kpa
```

Agregar al final de la clase `BaseFase`, después de `_rango_atm()`:

```python
    def _verificar_vapor_saturado(self, t_celsius: float, p_real_kpa: float, tolerancia_kpa: float) -> bool:
        """True si |P_real - P_sat(T)| <= tolerancia."""
        return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
```

- [ ] **Step 4: Ejecutar todos los tests de steam**

```
pytest tests/test_steam.py -v
```

Esperado: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/base_fase.py tests/test_steam.py
git commit -m "feat: helper _verificar_vapor_saturado() en BaseFase"
```

---

## Task 3: Actualizar JSON de ciclos con parámetros nuevos

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`

- [ ] **Step 1: Agregar parámetros a sección `calentamiento` en `instrumental_134.json`**

Dentro del objeto `"calentamiento"`, agregar después del parámetro `"tiempo_estable_preesterilizacion"`:

```json
"rango_temp_estabilizacion": { "value": 1.0, "type": "float", "unit": "°C", "min": 0, "max": 10 },
"timeout_recuperacion_estabilizacion": { "value": 5, "type": "int", "unit": "min", "min": 1, "max": 60 }
```

- [ ] **Step 2: Agregar parámetros a sección `esterilizacion` en `instrumental_134.json`**

Dentro del objeto `"esterilizacion"`, agregar después de `"tipo_secado"`:

```json
"temperatura_add_esterilizacion": { "value": 2.0, "type": "float", "unit": "°C", "min": 0, "max": 20 },
"temperatura_error_esterilizacion": { "value": 5.0, "type": "float", "unit": "°C", "min": 0, "max": 30 },
"rango_presion_esterilizacion": { "value": 20.0, "type": "float", "unit": "kPa", "min": 0, "max": 100 },
"presion_error_esterilizacion": { "value": 40.0, "type": "float", "unit": "kPa", "min": 0, "max": 200 }
```

- [ ] **Step 3: Verificar JSON válido**

```
python -c "import json; json.load(open('src/autoclave/cycles/factory/instrumental_134.json'))"
```

Esperado: sin output (sin error)

- [ ] **Step 4: Repetir Steps 1-3 para `bowe_dick.json` (factory)**

Abrir `src/autoclave/cycles/factory/bowe_dick.json`, agregar los mismos parámetros en las mismas secciones. Verificar con:

```
python -c "import json; json.load(open('src/autoclave/cycles/factory/bowe_dick.json'))"
```

- [ ] **Step 5: Repetir Steps 1-4 para los archivos `cycles/user/`**

El `CycleManager` carga primero factory y luego user, con el mismo `cycle_id`, por lo que user tiene prioridad. Ambos deben tener los nuevos parámetros.

```
python -c "import json; json.load(open('src/autoclave/cycles/user/instrumental_134.json'))"
python -c "import json; json.load(open('src/autoclave/cycles/user/bowe_dick.json'))"
```

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/cycles/factory/instrumental_134.json src/autoclave/cycles/factory/bowe_dick.json src/autoclave/cycles/user/instrumental_134.json src/autoclave/cycles/user/bowe_dick.json
git commit -m "feat: parámetros estabilización y esterilización en JSONs de ciclos"
```

---

## Task 4: Verificación de sensores críticos en `CicloState`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py`
- Test: `tests/test_ciclo_sensores.py`

- [ ] **Step 1: Escribir test de sensor ausente**

```python
# tests/test_ciclo_sensores.py
from unittest.mock import MagicMock, patch
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": 1}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_fallo_si_temp_camara_ausente():
    ciclo, estado = _make_ciclo()
    estado.sensores_temp["temp_camara"] = None

    result = ciclo.run()

    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo.alarm_manager.report.assert_called_once()


def test_fallo_si_pres_camara_ausente():
    ciclo, estado = _make_ciclo()
    estado.sensores_pres["pres_camara"] = None

    result = ciclo.run()

    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"


def test_no_fallo_si_sensores_presentes():
    ciclo, estado = _make_ciclo()
    # Sensores OK, puertas OK → debe llegar a ejecutar la primera fase
    # La primera fase (PrecalentamientoFase mock) devolverá EN_CURSO o similar
    result = ciclo.run()
    # No debe ser SENSOR_AUSENTE
    assert estado.fase_ciclo != "SENSOR_AUSENTE"
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_ciclo_sensores.py -v
```

Esperado: `FAILED — AssertionError` (sensor ausente no causa FALLO todavía)

- [ ] **Step 3: Agregar constantes de sensores al inicio de `ciclo.py`**

Después de los imports existentes y antes de la clase `CicloResultado`, agregar:

```python
_SENSORES_TEMP_CRITICOS = ["temp_camara"]
_SENSORES_PRES_CRITICOS = ["pres_camara"]
```

- [ ] **Step 4: Agregar paso 4 en `CicloState.run()`**

En el método `run()`, después del bloque `# ── 3. Verificar puertas` (línea ~217) y antes de `# ── 4. Mantener presión de chaqueta`, agregar:

```python
        # ── 4. Verificar sensores críticos ────────────────────────────
        ausentes = [
            s for s in _SENSORES_TEMP_CRITICOS
            if self.estado.sensores_temp.get(s) is None
        ] + [
            s for s in _SENSORES_PRES_CRITICOS
            if self.estado.sensores_pres.get(s) is None
        ]
        if ausentes:
            logger.error("CicloState: SENSOR_AUSENTE — %s", ausentes)
            self.estado.fase_ciclo = "SENSOR_AUSENTE"
            self.alarm_manager.report(Alarm(
                alarm_id="SENSOR_AUSENTE",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="CICLO",
                description=f"Sensor crítico ausente: {', '.join(ausentes)}",
                recoverable=False,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION
```

Renumerar el comentario siguiente a `# ── 5. Mantener presión de chaqueta` y el resto en consecuencia.

- [ ] **Step 5: Ejecutar tests**

```
pytest tests/test_ciclo_sensores.py -v
```

Esperado: 3 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_sensores.py
git commit -m "feat: verificación transversal de sensores críticos en CicloState"
```

---

## Task 5: Implementar `CalentamientoFase`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py`
- Test: `tests/test_calentamiento_fase.py`

- [ ] **Step 1: Escribir tests**

```python
# tests/test_calentamiento_fase.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(t_obj=134.0, tasa=5.0, timeout_min=60, tolerancia=9.0, t_inicial=20.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "tasa_calentamiento": tasa,
            "timeout_calentamiento": timeout_min,
            "presion_add_calentamiento": tolerancia,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_calentamiento_normal_valvula_on():
    """Temperatura lejos del objetivo → válvula abierta."""
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0)
    estado.sensores_temp["temp_camara"] = 20.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


def test_completado_cuando_alcanza_temperatura():
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_por_timeout():
    fase, estado, set_do = _make_fase(t_obj=134.0, timeout_min=1)
    fase.update()  # inicializar
    fase._timer_timeout_fin -= 200  # simular tiempo transcurrido
    estado.sensores_temp["temp_camara"] = 50.0
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_rampa_frena_valvula_cuando_supera_limite():
    """Si temperatura real supera T_permitida, válvula se cierra."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tasa=1.0, t_inicial=20.0)
    fase.update()  # inicializar con t_inicio=20
    # Con tasa=1°C/min y t_inicio=20, a t=0s T_permitida≈20°C
    # Forzamos temp = 50°C (muy por encima de la rampa) y elapsed≈0
    fase._t_inicio_fase += 0  # no avanzar tiempo
    estado.sensores_temp["temp_camara"] = 50.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_entra_en_sostenimiento():
    """Al alcanzar el 50% del objetivo, la fase entra en verificación."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 67.0  # 50% de 134
    # P_sat(67°C) ≈ 27.6 kPa — poner presión muy alta (aire)
    estado.sensores_pres["pres_camara"] = 200.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert estado.fase_en_sostenimiento is True


def test_checkpoint_se_libera_con_presion_correcta():
    """Cuando presión ≈ P_sat(T), el checkpoint se libera."""
    from autoclave.core.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=15.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 67.0
    # Presión correcta para el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(67.0)
    fase.update()  # entrar en checkpoint
    result = fase.update()  # liberar checkpoint
    assert fase._en_checkpoint is False
    assert estado.fase_en_sostenimiento is False


def test_salidas_apagadas_al_completar():
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_calentamiento_fase.py -v
```

Esperado: múltiples FAILED (fase no implementada)

- [ ] **Step 3: Implementar `calentamiento.py`**

```python
# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva T de la cámara hasta temperatura_calentamiento siguiendo una rampa
# de tasa_calentamiento °C/min. Pausa en checkpoints al 50% y 90% de T_obj
# para verificar vapor saturado (|P_real - P_sat(T)| <= presion_add_calentamiento).

import time
import logging
from autoclave.core.steam import p_saturacion_kpa
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class CalentamientoFase(BaseFase):

    name = "CALENTAMIENTO"

    def reset(self):
        self._inicializado = False
        self._t_inicio = None
        self._t_inicio_fase = None
        self._timer_timeout_fin = None
        self._checkpoints = None
        self._en_checkpoint = False
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def update(self) -> FaseResult:
        t_obj       = self.cycle.get_param("calentamiento", "temperatura_calentamiento") or 134.0
        tasa_seg    = (self.cycle.get_param("calentamiento", "tasa_calentamiento") or 5.0) / 60
        timeout_seg = (self.cycle.get_param("calentamiento", "timeout_calentamiento") or 60) * 60
        tolerancia  = self.cycle.get_param("calentamiento", "presion_add_calentamiento") or 9.0

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            temp = self._temp_camara()
            if temp is None:
                return FaseResult.EN_CURSO
            self._t_inicio          = temp
            self._t_inicio_fase     = time.time()
            self._timer_timeout_fin = time.time() + timeout_seg
            self._checkpoints       = [0.50 * t_obj, 0.90 * t_obj]
            self.set_do.descompresion_lenta_on()
            self._inicializado = True
            logger.info(
                "Calentamiento: iniciando desde %.1f°C → %.1f°C | tasa %.1f°C/min | timeout %.0fs",
                self._t_inicio, t_obj, tasa_seg * 60, timeout_seg,
            )

        # ── 2. Timeout global ────────────────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            logger.error("Calentamiento: TIMEOUT")
            self._apagar_salidas()
            return FaseResult.FALLO

        temp = self._temp_camara()
        pres = self._pres_camara()

        # ── 3. Entrada a checkpoint ──────────────────────────────────────
        if (not self._en_checkpoint and self._checkpoints
                and temp is not None and temp >= self._checkpoints[0]):
            self._en_checkpoint = True
            self.estado.fase_en_sostenimiento = True
            logger.info(
                "Calentamiento: checkpoint %.1f°C — verificando vapor saturado",
                self._checkpoints[0],
            )

        # ── 4. Lógica de checkpoint ──────────────────────────────────────
        if self._en_checkpoint:
            if pres is None:
                return FaseResult.EN_CURSO
            if self._verificar_vapor_saturado(temp, pres, tolerancia):
                logger.info("Calentamiento: checkpoint %.1f°C liberado", self._checkpoints[0])
                self._checkpoints.pop(0)
                self._en_checkpoint = False
                self.estado.fase_en_sostenimiento = False
            else:
                p_sat = p_saturacion_kpa(temp)
                if pres > p_sat + tolerancia:
                    self.set_do.vapor_camara_off()
                else:
                    self.set_do.vapor_camara_on()
            return FaseResult.EN_CURSO

        # ── 5. Control de rampa ──────────────────────────────────────────
        if temp is None:
            return FaseResult.EN_CURSO

        if temp >= t_obj:
            logger.info("Calentamiento: COMPLETADO — %.1f°C alcanzados", temp)
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        elapsed    = time.time() - self._t_inicio_fase
        t_permitida = min(self._t_inicio + tasa_seg * elapsed, t_obj)

        if temp >= t_permitida:
            self.set_do.vapor_camara_off()
        else:
            self.set_do.vapor_camara_on()

        return FaseResult.EN_CURSO
```

- [ ] **Step 4: Ejecutar tests**

```
pytest tests/test_calentamiento_fase.py -v
```

Esperado: 8 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: implementar CalentamientoFase con rampa y checkpoints de vapor"
```

---

## Task 6: Implementar `EstabilizacionFase`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/estabilizacion.py`
- Test: `tests/test_estabilizacion_fase.py`

- [ ] **Step 1: Escribir tests**

```python
# tests/test_estabilizacion_fase.py
from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.estabilizacion import EstabilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5, t_obj=134.0, rango_temp=1.0, rango_pres=9.0, timeout_rec_min=2):
    estado = MagicMock()
    p_sat = p_saturacion_kpa(t_obj)
    estado.sensores_temp = {"temp_camara": t_obj}
    estado.sensores_pres = {"pres_camara": p_sat}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "tiempo_estable_preesterilizacion": tiempo_min,
            "temperatura_calentamiento": t_obj,
            "rango_temp_estabilizacion": rango_temp,
            "presion_add_calentamiento": rango_pres,
            "timeout_recuperacion_estabilizacion": timeout_rec_min,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = EstabilizacionFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_skip_cuando_tiempo_es_cero():
    fase, estado, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_not_called()


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_completado_cuando_expira_timer():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()  # inicializar
    fase._timer_principal_fin -= 100  # simular tiempo transcurrido
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_si_no_recupera_temperatura():
    fase, estado, set_do = _make_fase(tiempo_min=5, timeout_rec_min=1)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 120.0  # fuera de rango
    fase.update()  # arrancar timer recuperación
    fase._timer_recuperacion -= 200  # simular timeout
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.descompresion_lenta_off.assert_called()


def test_timer_recuperacion_se_resetea_al_recuperar():
    from autoclave.core.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(tiempo_min=5, timeout_rec_min=2)
    fase.update()  # inicializar
    # Simular que la condición sale del rango
    estado.sensores_temp["temp_camara"] = 120.0
    fase.update()
    assert fase._timer_recuperacion is not None
    # Restaurar condición
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)
    fase.update()
    assert fase._timer_recuperacion is None


def test_bang_bang_valvula_on_cuando_temp_baja():
    fase, estado, set_do = _make_fase()
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 133.0  # bajo T_obj
    set_do.reset_mock()
    fase.update()
    set_do.vapor_camara_on.assert_called()


def test_salidas_apagadas_al_completar():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()
    fase._timer_principal_fin -= 100
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_estabilizacion_fase.py -v
```

Esperado: múltiples FAILED

- [ ] **Step 3: Implementar `estabilizacion.py`**

```python
# state_machine/cycle_phases/estabilizacion.py
#
# FASE 5 — ESTABILIZACIÓN
#
# Mantiene temperatura_calentamiento durante tiempo_estable_preesterilizacion.
# Si tiempo == 0, la fase se salta. Timer principal corre sin parar;
# si las condiciones salen del rango, un timer de recuperación separado
# dispara FALLO si no se restauran a tiempo.

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EstabilizacionFase(BaseFase):

    name = "ESTABILIZACION"

    def reset(self):
        self._inicializado        = False
        self._timer_principal_fin = None
        self._timer_recuperacion  = None
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def update(self) -> FaseResult:
        tiempo_seg      = (self.cycle.get_param("calentamiento", "tiempo_estable_preesterilizacion") or 0) * 60
        t_obj           =  self.cycle.get_param("calentamiento", "temperatura_calentamiento")         or 134.0
        rango_temp      =  self.cycle.get_param("calentamiento", "rango_temp_estabilizacion")         or 1.0
        rango_pres      =  self.cycle.get_param("calentamiento", "presion_add_calentamiento")         or 9.0
        timeout_rec_seg = (self.cycle.get_param("calentamiento", "timeout_recuperacion_estabilizacion") or 5) * 60

        # ── 1. Skip ──────────────────────────────────────────────────────
        if tiempo_seg == 0:
            return FaseResult.COMPLETADO

        # ── 2. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            self._timer_principal_fin = time.time() + tiempo_seg
            self.set_do.descompresion_lenta_on()
            self._inicializado = True
            logger.info("Estabilización: iniciando %.0fs | T_obj=%.1f°C", tiempo_seg, t_obj)

        temp = self._temp_camara()
        pres = self._pres_camara()

        # ── 3. Verificar condiciones ─────────────────────────────────────
        dentro_rango = (
            abs(temp - t_obj) <= rango_temp
            and self._verificar_vapor_saturado(temp, pres, rango_pres)
        )

        # ── 4. Recuperación ──────────────────────────────────────────────
        if not dentro_rango:
            if self._timer_recuperacion is None:
                self._timer_recuperacion = time.time() + timeout_rec_seg
                logger.warning("Estabilización: condiciones fuera de rango — recuperando")
            if time.time() > self._timer_recuperacion:
                logger.error("Estabilización: FALLO — no se recuperaron las condiciones")
                self._apagar_salidas()
                return FaseResult.FALLO
        else:
            if self._timer_recuperacion is not None:
                logger.info("Estabilización: condiciones recuperadas")
            self._timer_recuperacion = None

        # ── 5. Control bang-bang ─────────────────────────────────────────
        if temp < t_obj:
            self.set_do.vapor_camara_on()
        else:
            self.set_do.vapor_camara_off()

        # ── 6. Condición de finalización ─────────────────────────────────
        if time.time() >= self._timer_principal_fin:
            logger.info("Estabilización: COMPLETADO")
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
```

- [ ] **Step 4: Ejecutar tests**

```
pytest tests/test_estabilizacion_fase.py -v
```

Esperado: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/estabilizacion.py tests/test_estabilizacion_fase.py
git commit -m "feat: implementar EstabilizacionFase con recuperación y timer independiente"
```

---

## Task 7: Implementar `EsterilizacionFase`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/esterilizacion.py`
- Test: `tests/test_esterilizacion_fase.py`

- [ ] **Step 1: Escribir tests**

```python
# tests/test_esterilizacion_fase.py
from unittest.mock import MagicMock
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(t_est=134.0, tiempo_min=3.5, temp_add=2.0, temp_err=5.0,
               pres_rango=20.0, pres_err=40.0):
    p_sat = p_saturacion_kpa(t_est)
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_est + 1.0}   # dentro de la banda
    estado.sensores_pres = {"pres_camara": p_sat + 5.0}   # dentro de la banda
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_esterilizacion":       t_est,
            "tiempo_esterilizacion":             tiempo_min,
            "temperatura_add_esterilizacion":    temp_add,
            "temperatura_error_esterilizacion":  temp_err,
            "rango_presion_esterilizacion":      pres_rango,
            "presion_error_esterilizacion":      pres_err,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = EsterilizacionFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_primer_tick_activa_descompresion_lenta():
    fase, estado, set_do = _make_fase()
    fase.update()
    set_do.descompresion_lenta_on.assert_called_once()


def test_en_curso_con_condiciones_normales():
    fase, estado, set_do = _make_fase()
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_completado_cuando_expira_timer():
    fase, estado, set_do = _make_fase(tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_fallo_temp_baja():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 133.9
    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.descompresion_lenta_off.assert_called()
    fase.alarm_manager.report.assert_called()
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "TEMP_BAJA" in alarm.id


def test_fallo_temp_alta():
    fase, estado, set_do = _make_fase(t_est=134.0, temp_add=2.0, temp_err=5.0)
    fase.update()
    # T_lim_alta = 134 + 2 + 5 = 141
    estado.sensores_temp["temp_camara"] = 141.1
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "TEMP_ALTA" in alarm.id


def test_fallo_presion_baja():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    p_sat = p_saturacion_kpa(134.0)
    estado.sensores_pres["pres_camara"] = p_sat - 0.1  # justo debajo de P_sat
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "PRES_BAJA" in alarm.id


def test_fallo_presion_alta():
    fase, estado, set_do = _make_fase(t_est=134.0, pres_rango=20.0, pres_err=40.0)
    fase.update()
    p_sat = p_saturacion_kpa(134.0)
    # P_lim_alta = P_sat + 20 + 40 = P_sat + 60
    estado.sensores_pres["pres_camara"] = p_sat + 61.0
    result = fase.update()
    assert result == FaseResult.FALLO
    alarm = fase.alarm_manager.report.call_args[0][0]
    assert "PRES_ALTA" in alarm.id


def test_valvula_on_en_limite_inferior():
    """Cuando temp == T_est (límite), la válvula pulsa para evitar caída."""
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()


def test_valvula_off_cuando_temp_en_banda():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 135.0  # sobre T_est
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_salidas_apagadas_en_fallo():
    fase, estado, set_do = _make_fase(t_est=134.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 120.0  # temp baja → fallo
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```
pytest tests/test_esterilizacion_fase.py -v
```

Esperado: múltiples FAILED

- [ ] **Step 3: Implementar `esterilizacion.py`**

```python
# state_machine/cycle_phases/esterilizacion.py
#
# FASE 6 — ESTERILIZACIÓN
#
# Mantiene vapor saturado durante tiempo_esterilizacion.
# Zonas:
#   Temp normal:  [T_est, T_est + add]
#   Temp error:   T > T_est + add + err_T  → FALLO TEMP_ALTA
#                 T < T_est (sin tolerancia) → FALLO TEMP_BAJA
#   Pres normal:  [P_sat(T), P_sat(T) + rango]
#   Pres error:   P > P_sat(T) + rango + err_P → FALLO PRES_ALTA
#                 P < P_sat(T) (sin tolerancia) → FALLO PRES_BAJA

import time
import logging
from autoclave.core.steam import p_saturacion_kpa
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class EsterilizacionFase(BaseFase):

    name = "ESTERILIZACION"

    def reset(self):
        self._inicializado = False
        self._timer_fin    = None
        self.estado.fase_en_sostenimiento = False

    def _apagar_salidas(self):
        self.set_do.vapor_camara_off()
        self.set_do.descompresion_lenta_off()
        self.estado.fase_en_sostenimiento = False

    def _fallo(self, alarm_id: str, descripcion: str) -> FaseResult:
        logger.error("Esterilización: FALLO — %s", alarm_id)
        self._apagar_salidas()
        self.alarm_manager.report(Alarm(
            alarm_id=alarm_id,
            alarm_type=AlarmType.FALLA,
            source_state="ESTERILIZACION",
            description=descripcion,
            recoverable=False,
        ))
        return FaseResult.FALLO

    def update(self) -> FaseResult:
        t_est      =  self.cycle.get_param("esterilizacion", "temperatura_esterilizacion")      or 134.0
        tiempo_seg = (self.cycle.get_param("esterilizacion", "tiempo_esterilizacion")            or 3.5) * 60
        temp_add   =  self.cycle.get_param("esterilizacion", "temperatura_add_esterilizacion")  or 2.0
        temp_err   =  self.cycle.get_param("esterilizacion", "temperatura_error_esterilizacion") or 5.0
        pres_rango =  self.cycle.get_param("esterilizacion", "rango_presion_esterilizacion")    or 20.0
        pres_err   =  self.cycle.get_param("esterilizacion", "presion_error_esterilizacion")    or 40.0

        # ── 1. Inicialización ────────────────────────────────────────────
        if not self._inicializado:
            self._timer_fin = time.time() + tiempo_seg
            self.set_do.descompresion_lenta_on()
            self.estado.fase_en_sostenimiento = True
            self._inicializado = True
            logger.info(
                "Esterilización: iniciando %.0fs | T=%.1f°C add=%.1f err_T=%.1f rango_P=%.1f err_P=%.1f",
                tiempo_seg, t_est, temp_add, temp_err, pres_rango, pres_err,
            )

        temp = self._temp_camara()
        pres = self._pres_camara()

        # ── 2. Verificar temperatura ─────────────────────────────────────
        if temp < t_est:
            return self._fallo(
                "ESTERILIZACION_TEMP_BAJA",
                f"Temperatura baja: {temp:.1f}°C < {t_est:.1f}°C"
            )
        if temp > t_est + temp_add + temp_err:
            return self._fallo(
                "ESTERILIZACION_TEMP_ALTA",
                f"Temperatura alta: {temp:.1f}°C > {t_est + temp_add + temp_err:.1f}°C"
            )

        # ── 3. Verificar presión ─────────────────────────────────────────
        p_sat = p_saturacion_kpa(temp)
        if pres < p_sat:
            return self._fallo(
                "ESTERILIZACION_PRES_BAJA",
                f"Presión baja: {pres:.1f} kPa < P_sat({temp:.1f}°C)={p_sat:.1f} kPa"
            )
        if pres > p_sat + pres_rango + pres_err:
            return self._fallo(
                "ESTERILIZACION_PRES_ALTA",
                f"Presión alta: {pres:.1f} kPa > {p_sat + pres_rango + pres_err:.1f} kPa"
            )

        # ── 4. Control bang-bang (pulsos cortos) ─────────────────────────
        if temp <= t_est:
            self.set_do.vapor_camara_on()
        else:
            self.set_do.vapor_camara_off()

        # ── 5. Condición de finalización ─────────────────────────────────
        if time.time() >= self._timer_fin:
            logger.info("Esterilización: COMPLETADO — %.0f seg completados", tiempo_seg)
            self._apagar_salidas()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
```

- [ ] **Step 4: Ejecutar tests**

```
pytest tests/test_esterilizacion_fase.py -v
```

Esperado: 9 tests PASSED

- [ ] **Step 5: Ejecutar suite completa**

```
pytest tests/test_steam.py tests/test_calentamiento_fase.py tests/test_estabilizacion_fase.py tests/test_esterilizacion_fase.py tests/test_ciclo_sensores.py -v
```

Esperado: todos PASSED

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/esterilizacion.py tests/test_esterilizacion_fase.py
git commit -m "feat: implementar EsterilizacionFase con 4 zonas de control y 4 FALLOs"
```
