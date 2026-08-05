# Control de drenaje en espera de confirmación + debounce — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que `CicloState._mantener_drenaje()` (control de `agua_intercambiador` según `temp_drenaje`) corra también mientras el ciclo espera confirmación del operador (COMPLETADO/FALLO/CANCELADO/emergencia), y agregarle debounce simétrico de 3 lecturas para evitar activaciones/desactivaciones por oscilaciones cerca del umbral.

**Architecture:** Todo el cambio vive en `src/autoclave/state_machine/states/ciclo.py`: dos contadores nuevos de instancia gatillan el cambio de estado de la válvula solo tras 3 lecturas consecutivas en la misma dirección, y una llamada nueva a `_mantener_drenaje()` se agrega al bloque de `run()` que hoy se ejecuta durante `ESPERANDO_CONFIRMACION`.

**Tech Stack:** Python 3.14, pytest, unittest.mock.MagicMock.

## Global Constraints

- Debounce: exactamente 3 lecturas consecutivas (constante `_DEBOUNCE_LECTURAS_DRENAJE = 3`), simétrico (aplica tanto para encender como para apagar la válvula).
- No se agrega parámetro configurable para el número de lecturas — es una constante de módulo, igual que `_DEBOUNCE_LECTURAS` en `esterilizacion.py`.
- Sensor ausente (`temp_drenaje is None`) no debe resetear los contadores en progreso — solo se salta el tick.
- `_mantener_drenaje()` debe correr en TODAS las esperas de confirmación (COMPLETADO, FALLO, CANCELADO, emergencia), no solo durante `ProtocoloFallo`.

---

### Task 1: Debounce simétrico en `_mantener_drenaje()`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py:32-33` (constantes de módulo), `:57-79` (`__init__`), `:85-102` (`reset`), `:168-190` (`_mantener_drenaje`)
- Test: `tests/test_ciclo_drenaje.py` (reescribir completo)

**Interfaces:**
- Consumes: `Alarm`, `AlarmType` (ya importados en `ciclo.py`), `self.estado.sensores_temp["temp_drenaje"]`, `self.config.get("temp_segura_drenaje")`, `self.set_do.agua_intercambiador_on()/_off()`, `self.alarm_manager.report(Alarm)/clear(alarm_id)`.
- Produces: `CicloState._contador_drenaje_alta` / `_contador_drenaje_baja` (int, inicializados en 0), usados también por la llamada de Task 2. `_mantener_drenaje()` no cambia su firma (sin argumentos, sin retorno).

- [ ] **Step 1: Escribir los tests (reemplazando el archivo completo)**

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState


def _make_ciclo(temp_drenaje=25.0, temp_segura=40.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    estado.sensores_pres = {}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = temp_segura
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    return ciclo, set_do, alarm_manager, estado


def test_temp_alta_no_activa_agua_antes_de_3_lecturas():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()
    alarm_manager.report.assert_not_called()


def test_temp_alta_activa_agua_al_llegar_a_3_lecturas():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "TEMP_DRENAJE_ALTA"
    assert alarma.blocks_operation is False


def test_temp_segura_apaga_agua_al_llegar_a_3_lecturas():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()

    estado.sensores_temp["temp_drenaje"] = 30.0
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
    alarm_manager.clear.assert_any_call("TEMP_DRENAJE_ALTA")


def test_oscilacion_resetea_contador_sin_falso_positivo():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    estado.sensores_temp["temp_drenaje"] = 30.0
    ciclo._mantener_drenaje()  # baja (1) -- resetea contador de alta
    estado.sensores_temp["temp_drenaje"] = 45.0
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    set_do.agua_intercambiador_on.assert_not_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_temp_drenaje_ausente_no_hace_nada():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_segura=40.0)
    estado.sensores_temp = {}
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()
    set_do.agua_intercambiador_off.assert_not_called()
    alarm_manager.report.assert_not_called()
    alarm_manager.clear.assert_not_called()


def test_sensor_ausente_no_reinicia_contador_en_progreso():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    estado.sensores_temp = {}
    ciclo._mantener_drenaje()  # sensor ausente, no toca contadores
    estado.sensores_temp = {"temp_drenaje": 45.0}
    ciclo._mantener_drenaje()  # alta (3) -- debe disparar, no reiniciarse a 1
    set_do.agua_intercambiador_on.assert_called_once()


def test_se_llama_en_run_sin_importar_la_fase_activa():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    # temp_camara es sensor crítico (CicloState._SENSORES_TEMP_CRITICOS) y
    # debe estar presente o run() aborta el ciclo en el paso 4, antes de
    # llegar al paso 5 (_mantener_drenaje).
    estado.sensores_temp["temp_camara"] = 100.0
    estado.sensores_pres = {"pres_camara": 101.3, "pres_chaqueta": 300.0,
                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                           "vapor_suministro": 1}
    # cap.has_vacuum=False para que PrevacioFase.update() (paso 7, corre
    # DESPUÉS de _mantener_drenaje) se salte sin tocar más sensores/salidas.
    ciclo.cap = MagicMock()
    ciclo.cap.has_vacuum = False
    for fase in ciclo._fases:
        fase.cap = ciclo.cap
    # PrevacioFase está en índice 2 del pipeline (PRECALENTAMIENTO, PURGA, PRE_VACIO, ...)
    ciclo.reset()
    ciclo._fase_idx = 2
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called()
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_ciclo_drenaje.py -v`
Expected: FAIL en `test_temp_alta_no_activa_agua_antes_de_3_lecturas` (el código actual activa la válvula en la 1ra llamada, no en la 3ra) y en varios más — el código actual no tiene debounce.

- [ ] **Step 3: Agregar la constante de módulo**

En `ciclo.py`, junto a `_SENSORES_TEMP_CRITICOS`/`_SENSORES_PRES_CRITICOS` (línea 32-33):

```python
_SENSORES_TEMP_CRITICOS = ["temp_camara"]
_SENSORES_PRES_CRITICOS = ["pres_camara"]
_DEBOUNCE_LECTURAS_DRENAJE = 3
```

- [ ] **Step 4: Inicializar los contadores en `__init__` y `reset()`**

En `__init__` (después de la línea `self._resultado_pendiente: str | None = None`):

```python
        self._protocolo          = ProtocoloFallo(estado, set_do, cycle, config)
        self._fase_idx           = 0
        self._resultado_pendiente: str | None = None   # resultado almacenado hasta confirmación
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
```

En `reset()` (junto a los demás campos que se reinician):

```python
    def reset(self):
        """
        Llamar UNA vez al entrar al estado CICLO.
        Reinicia todas las fases y el protocolo de fallo.
        """
        self._fase_idx            = 0
        self._resultado_pendiente = None
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
        self.estado.motivo_fallo  = ""
        self._protocolo.reset()
```

- [ ] **Step 5: Reescribir `_mantener_drenaje()`**

Reemplazar el método completo (líneas 168-190):

```python
    def _mantener_drenaje(self):
        """Mantiene la temperatura de drenaje durante todo el ciclo, incluyendo
        las esperas de confirmación (COMPLETADO/FALLO/CANCELADO/emergencia).
        Debounce simétrico de _DEBOUNCE_LECTURAS_DRENAJE lecturas consecutivas
        antes de cambiar el estado de la válvula, para evitar activarla por
        oscilaciones de temp_drenaje cerca del umbral. Sensor ausente no
        resetea los contadores en progreso, solo salta el tick."""
        temp = self.estado.sensores_temp.get("temp_drenaje")
        if temp is None:
            return
        temp_segura = self.config.get("temp_segura_drenaje")
        if temp_segura is None:
            return

        if temp > temp_segura:
            self._contador_drenaje_alta += 1
            self._contador_drenaje_baja = 0
        else:
            self._contador_drenaje_baja += 1
            self._contador_drenaje_alta = 0

        if self._contador_drenaje_alta >= _DEBOUNCE_LECTURAS_DRENAJE:
            self.set_do.agua_intercambiador_on()
            self.alarm_manager.report(Alarm(
                alarm_id="TEMP_DRENAJE_ALTA",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Temperatura de drenaje alta: enfriando.",
                recoverable=True,
                blocks_operation=False,
            ))
        elif self._contador_drenaje_baja >= _DEBOUNCE_LECTURAS_DRENAJE:
            self.set_do.agua_intercambiador_off()
            self.alarm_manager.clear("TEMP_DRENAJE_ALTA")
```

- [ ] **Step 6: Correr los tests para verificar que pasan**

Run: `pytest tests/test_ciclo_drenaje.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Correr toda la suite para verificar que no se rompió nada más**

Run: `pytest tests/ -v`
Expected: PASS — en particular ningún otro test llama `_mantener_drenaje` fuera de `test_ciclo_drenaje.py`.

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_drenaje.py
git commit -m "$(cat <<'EOF'
feat: debounce de 3 lecturas para la valvula de drenaje

Evita activar/desactivar agua_intercambiador por oscilaciones de
temp_drenaje cerca del umbral: ahora se exigen 3 lecturas consecutivas
en la misma direccion antes de cambiar el estado de la valvula.
EOF
)"
```

---

### Task 2: `_mantener_drenaje()` corre durante todas las esperas de confirmación

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py:228-246` (`run()`, bloque de `_resultado_pendiente`)
- Test: Create `tests/test_ciclo_drenaje_espera_confirmacion.py`

**Interfaces:**
- Consumes: `CicloState._mantener_drenaje()` (de Task 1), `CicloState._contador_drenaje_alta`/`_contador_drenaje_baja` (de Task 1), `CicloResultado.COMPLETADO`/`FALLO`/`CANCELADO` (ya existentes en `ciclo.py`).
- Produces: nada nuevo consumido por nadie más — es el último cambio del plan.

- [ ] **Step 1: Escribir el test nuevo**

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo_en_espera(resultado_pendiente, temp_drenaje=45.0, temp_segura=40.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    estado.sensores_pres = {}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = temp_segura
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    ciclo._resultado_pendiente = resultado_pendiente
    return ciclo, set_do, alarm_manager


def test_drenaje_corre_durante_espera_completado():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.COMPLETADO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()


def test_drenaje_corre_durante_espera_fallo():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.FALLO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()


def test_drenaje_corre_durante_espera_cancelado():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.CANCELADO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `pytest tests/test_ciclo_drenaje_espera_confirmacion.py -v`
Expected: FAIL en los tres tests — `run()` hoy no llama `_mantener_drenaje()` mientras `_resultado_pendiente is not None`.

- [ ] **Step 3: Agregar la llamada en `run()`**

En el bloque `if self._resultado_pendiente is not None:` (líneas 229-246), agregar `self._mantener_drenaje()` antes de la rama existente:

```python
        # ── 0. ¿Pendiente de confirmación y ya confirmado? ────────────
        if self._resultado_pendiente is not None:
            if self.estado.get_flag("CICLO_CONFIRMADO"):
                logger.info(
                    "CicloState: confirmación recibida → %s", self._resultado_pendiente
                )
                self.estado.set_flag("CICLO_CONFIRMADO", False)
                resultado_final = self._resultado_pendiente
                self._resultado_pendiente = None
                return resultado_final
            # Mantener la válvula de reposo activa mientras se espera
            # confirmación: COMPLETADO limpio usa su propio monitor de
            # presión; el resto (FALLO/CANCELADO/emergencia) ya lo cubre
            # el protocolo de fallo, que corre continuamente. El drenaje
            # se mantiene sin importar la causa de fin de ciclo.
            self._mantener_drenaje()
            if self._resultado_pendiente == CicloResultado.COMPLETADO:
                self._mantener_valvula_reposo()
            else:
                self._protocolo.update()
            return CicloResultado.ESPERANDO_CONFIRMACION
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `pytest tests/test_ciclo_drenaje_espera_confirmacion.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Correr toda la suite**

Run: `pytest tests/ -v`
Expected: PASS — sin regresiones en `test_valvula_reposo.py`, `test_protocolo_fallo_modo_descompresion.py`, ni el resto.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_drenaje_espera_confirmacion.py
git commit -m "$(cat <<'EOF'
feat: control de drenaje activo durante toda espera de confirmacion

Antes _mantener_drenaje() se saltaba por completo mientras el ciclo
esperaba confirmacion del operador (COMPLETADO/FALLO/CANCELADO/
emergencia). Ahora corre en todos los casos, sin importar la causa
de fin de ciclo.
EOF
)"
```
