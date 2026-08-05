# Fusión CALENTAMIENTO/ESTABILIZACION Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar la fase `ESTABILIZACION` del pipeline de ciclo y hacer que el tramo `ESTABLE_PREESTERILIZACION` de `CalentamientoFase` espere una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION, en vez del timer fijo actual que entrega con la presión todavía inflada por inercia térmica.

**Architecture:** Cambio contenido a un solo archivo de lógica de fase (`calentamiento.py`) más limpieza mecánica en 5 archivos que referencian la fase eliminada (orquestación, dos mapeos de UI, uno de logging). Sin cambios de esquema JSON — todos los parámetros ya viven en la sección `calentamiento` de los perfiles.

**Tech Stack:** Python, pytest, unittest.mock.

## Global Constraints

- Ningún parámetro cambia de sección JSON — todo sigue bajo `parameters.calentamiento` en los perfiles (`src/autoclave/cycles/{factory,user}/*.json`).
- No tocar la sección JSON huérfana `"estabilizacion"` de `bowe_dick.json` (factory y user) — gestionada por un proceso externo de auto-actualización, fuera de este alcance.
- No tocar docs fechados en `docs/superpowers/specs/` ni `docs/superpowers/plans/` salvo el spec/plan de este mismo trabajo — son registros históricos de trabajos pasados.
- Seguir la convención de fallas del repo: debounce/timeout dedicado con motivo específico en `self.estado.motivo_fallo`, apagar las tres salidas (`vapor_camara`, `descompresion_lenta`, `descompresion_rapida`) al entrar en `FALLO`.
- Referencia de diseño completa: `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`.

---

### Task 1: Rediseñar el tramo ESTABLE_PREESTERILIZACION de CalentamientoFase

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py`
- Test: `tests/test_calentamiento_fase.py`

**Interfaces:**
- Produce (nuevos atributos de instancia en `CalentamientoFase`, usados por los tests): `self._en_sostenimiento: bool`, `self._timer_sostenido_desde: float | None`, `self._timer_recuperacion_fin: float | None`. Reemplazan a `self._timer_estable_inicio` (se elimina).
- Consume: `self._fallo(mensaje: str) -> FaseResult` (ya existe en la clase, sin cambios de firma) y `self._apagar_salidas()` (ya existe, sin cambios).

- [ ] **Step 1: Actualizar el fixture y los tests de `tests/test_calentamiento_fase.py` para el nuevo comportamiento**

Reemplazar la firma y el diccionario `valores` de `_make_fase` (líneas 9-43) por:

```python
def _make_fase(t_obj=134.0, presion_add=11.0, timeout_min=60,
               factor=50.0, rango=2.0, tasa_calentamiento=0.0, tasa_presion=0.0,
               tiempo_estable=0, intervalo=2, t_inicial=20.0,
               escape_lento_on=1, escape_lento_off=0,
               escape_rapido_on=0, escape_rapido_off=10,
               rango_temp_estabilizacion=1.0, timeout_recuperacion_estabilizacion=5):
    """tasa_calentamiento/tasa_presion quedan en 0 (deshabilitadas, ver guard
    '> 0' en calentamiento.py) por defecto: los tests que no ejercitan el
    control por tasa cambian temperatura/presión entre ticks sin control de
    tiempo real, lo que produciría una tasa artificialmente alta y forzaría
    vapor_camara a OFF de forma espuria si el control estuviera activo."""
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    estado.motivo_fallo = ""
    set_do = MagicMock()
    cycle = MagicMock()

    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "presion_add_calentamiento": presion_add,
            "timeout_calentamiento": timeout_min,
            "factor_calentamiento": factor,
            "rango_calentamiento": rango,
            "tasa_calentamiento": tasa_calentamiento,
            "tasa_presion": tasa_presion,
            "tiempo_estable_preesterilizacion": tiempo_estable,
            "intervalo_segmentos_calor": intervalo,
            "escape_lento_on": escape_lento_on,
            "escape_lento_off": escape_lento_off,
            "escape_rapido_on": escape_rapido_on,
            "escape_rapido_off": escape_rapido_off,
            "rango_temp_estabilizacion": rango_temp_estabilizacion,
            "timeout_recuperacion_estabilizacion": timeout_recuperacion_estabilizacion,
        }
        return valores.get(param, default)

    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap = MagicMock()

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do
```

Reemplazar todo el bloque `# ── Condición de finalización ─────` (líneas 218-286, desde `def test_completa_sin_sostenimiento_cuando_tiempo_estable_es_cero` hasta el final de `test_sostenimiento_timer_no_se_reinicia_si_condicion_sale_de_rango`) por:

```python
# ── Condición de finalización / tramo ESTABLE_PREESTERILIZACION ──────────

def test_completa_sin_sostenimiento_cuando_tiempo_estable_es_cero():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()


def test_no_completa_si_falta_presion_aunque_temp_llegue():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0)  # sin el add
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_sostenimiento_arma_timer_y_no_completa_de_inmediato():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_sostenimiento is True
    assert fase._timer_sostenido_desde is not None
    assert estado.fase_en_sostenimiento is True


def test_sostenimiento_completa_tras_transcurrir_el_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer

    fase._timer_sostenido_desde -= 6  # simula que ya pasaron 6s (>= 5) dentro de banda
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_sostenimiento_se_reinicia_si_presion_excede_la_banda_superior():
    """Caso central del rediseño: si la presión se pasa de banda por inercia
    térmica durante el sostenimiento, el conteo se reinicia — la fase espera
    a que la presión regrese cerca de p_obj antes de volver a contar, en vez
    de completar con la presión todavía inflada (motivo original del cambio:
    CALENTAMIENTO entregaba a ESTERILIZACION con presión alta)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer
    assert fase._timer_sostenido_desde is not None

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # overshoot, muy fuera de banda (+-11)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_sostenido_desde is None  # se reinició
    assert estado.fase_en_sostenimiento is False

    # Vuelve a banda: arranca un timer nuevo, no retoma el anterior
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    assert fase._timer_sostenido_desde is not None

    fase._timer_sostenido_desde -= 6
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_sostenimiento_timer_recuperacion_se_cancela_al_recuperar():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5,
                                       timeout_recuperacion_estabilizacion=2)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # arma el timer de sostenimiento

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # sale de banda
    fase.update()
    assert fase._timer_recuperacion_fin is not None

    estado.sensores_pres["pres_camara"] = p_obj  # recupera
    fase.update()
    assert fase._timer_recuperacion_fin is None


def test_sostenimiento_fallo_si_nunca_converge_dentro_del_timeout_recuperacion():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5,
                                       timeout_recuperacion_estabilizacion=1)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # entra al tramo y arma timer de sostenimiento

    estado.sensores_pres["pres_camara"] = p_obj + 50.0  # sale de banda, arma recuperación
    fase.update()
    assert fase._timer_recuperacion_fin is not None

    fase._timer_recuperacion_fin -= 100  # simula que expiró el timeout de recuperación
    result = fase.update()
    assert result == FaseResult.FALLO
    assert estado.motivo_fallo != ""
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: FAIL en `test_sostenimiento_arma_timer_y_no_completa_de_inmediato`, `test_sostenimiento_completa_tras_transcurrir_el_tiempo`, `test_sostenimiento_se_reinicia_si_presion_excede_la_banda_superior`, `test_sostenimiento_timer_recuperacion_se_cancela_al_recuperar` y `test_sostenimiento_fallo_si_nunca_converge_dentro_del_timeout_recuperacion` con `AttributeError` (`_en_sostenimiento` / `_timer_sostenido_desde` / `_timer_recuperacion_fin` no existen todavía en `CalentamientoFase`). El resto de los tests del archivo (APROXIMACION, PWM, escapes, timeout global, control por tasa) deben seguir en PASS — no se tocó esa lógica.

- [ ] **Step 3: Implementar el rediseño en `calentamiento.py`**

Los números de línea de abajo son los del archivo **actual, sin editar** — cada reemplazo corre las líneas siguientes, así que conviene ubicar cada bloque por su contenido (nombre de función / comentario) en vez de recontar líneas a mano.

Reemplazar el comentario de módulo (líneas 1-24) por:

```python
# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint de esterilización (temperatura_calentamiento +
# presion_add_calentamiento) y sostiene esa condición durante una ventana
# continua de tiempo_estable_preesterilizacion segundos antes de entregar
# control a ESTERILIZACION. Tres tramos internos, sin retroceso entre ellos:
#   APROXIMACION              vapor_camara en bang-bang por tick: ON salvo
#                              que la pendiente ya supere tasa_calentamiento/
#                              tasa_presion (0 = sin límite; solo limita subida)
#   PWM_ACTIVO                entra al alcanzar |P - P_sat(T)| <= rango_calentamiento;
#                              vapor_camara en PWM (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION entra al cruzar temp>=t_obj y pres>=p_obj; exige
#                              una ventana CONTINUA de tiempo_estable_preesterilizacion
#                              segundos dentro de banda (|T-t_obj|<=rango_temp_estabilizacion
#                              Y |P-p_obj|<=presion_add_calentamiento) — el conteo
#                              se reinicia si sale de banda, así se espera a que
#                              la inercia térmica se disipe antes de completar.
#                              Timeout de recuperación dedicado
#                              (timeout_recuperacion_estabilizacion) si nunca
#                              converge. Ver docs/superpowers/specs/
#                              2026-08-04-fusion-calentamiento-estabilizacion-design.md
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion son puramente de
# control (bang-bang en APROXIMACION) — no producen FALLO; si vapor_camara
# no responde al comando OFF, no hay aborto automático por esta vía (riesgo
# aceptado, ver docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md).
```

Reemplazar `reset()` (líneas 38-58) por:

```python
    def reset(self):
        self._inicializado = False
        self._timer_timeout_fin = None
        self._en_pwm = False

        # Tramo ESTABLE_PREESTERILIZACION: ventana continua dentro de banda
        self._en_sostenimiento = False
        self._timer_sostenido_desde = None
        self._timer_recuperacion_fin = None

        # Pendiente instantánea (tasa_calentamiento / tasa_presion) —
        # alimenta el control de vapor_camara en APROXIMACION, paso 5
        self._temp_anterior = None
        self._pres_anterior = None
        self._t_tick_anterior = None

        # Temporizadores de dos estados (vapor PWM, escape lento, escape rápido)
        self._t_pulso_pwm = None
        self._pwm_abierto = False
        self._t_pulso_lento = None
        self._lento_abierto = False
        self._t_pulso_rapido = None
        self._rapido_abierto = False

        self.estado.fase_en_sostenimiento = False
```

En `update()`, agregar dos lecturas de parámetro nuevas junto al resto (después de la línea `rapido_off = ...`, dentro del bloque que empieza en la línea 105):

```python
        rango_temp_estab =  self.cycle.get_param("calentamiento", "rango_temp_estabilizacion")           or 1.0
        timeout_rec_seg  = (self.cycle.get_param("calentamiento", "timeout_recuperacion_estabilizacion")  or 5) * 60
```

Reemplazar el bloque `# ── 7. Condición de finalización ────` completo (líneas 199-221, hasta el final del método) por:

```python
        # ── 7. Entrada y control de ESTABLE_PREESTERILIZACION ───────────────
        # Exige una ventana CONTINUA de tiempo_est segundos dentro de banda
        # respecto a los objetivos fijos (t_obj, p_obj) — el conteo se
        # reinicia si sale de banda, así se espera a que la inercia térmica
        # se disipe antes de entregar control a ESTERILIZACION.
        if not self._en_sostenimiento:
            if temp >= t_obj and pres >= p_obj:
                self._en_sostenimiento = True
                logger.info("Calentamiento: condición alcanzada — entra a ESTABLE_PREESTERILIZACION")
            else:
                return FaseResult.EN_CURSO

        dentro_rango = abs(temp - t_obj) <= rango_temp_estab and abs(pres - p_obj) <= p_add

        if dentro_rango:
            self._timer_recuperacion_fin = None
            if self._timer_sostenido_desde is None:
                self._timer_sostenido_desde = now
            self.estado.fase_en_sostenimiento = True
            if now - self._timer_sostenido_desde >= tiempo_est:
                logger.info(
                    "Calentamiento: COMPLETADO tras sostenimiento continuo de %.0fs — %.1f°C / %.1f kPa",
                    tiempo_est, temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
        else:
            self._timer_sostenido_desde = None
            self.estado.fase_en_sostenimiento = False
            if self._timer_recuperacion_fin is None:
                self._timer_recuperacion_fin = now + timeout_rec_seg
                logger.warning("Calentamiento: condición fuera de rango en sostenimiento — recuperando")
            if now > self._timer_recuperacion_fin:
                return self._fallo(
                    f"No se logró sostener condición estable en {timeout_rec_seg / 60:.0f} min"
                )

        return FaseResult.EN_CURSO
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — los 34 tests del archivo (los ya existentes sin tocar más los 6 nuevos/reescritos).

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: esperar ventana continua de estabilidad antes de completar CALENTAMIENTO

Reemplaza el timer fijo del tramo ESTABLE_PREESTERILIZACION (que
entregaba control con presion inflada por inercia termica) por una
ventana continua dentro de banda que se reinicia ante overshoot, con
timeout de recuperacion dedicado."
```

---

### Task 2: Eliminar EstabilizacionFase del pipeline

**Files:**
- Delete: `src/autoclave/state_machine/cycle_phases/estabilizacion.py`
- Delete: `tests/test_estabilizacion_fase.py`
- Modify: `src/autoclave/state_machine/states/ciclo.py`

**Interfaces:**
- Consume: nada nuevo — este task solo remueve referencias.
- Produce: `CicloState._fases` ya no contiene una instancia de `EstabilizacionFase`; cualquier código posterior que itere `_fases` o lea `self.estado.fase_ciclo` nunca verá el valor `"ESTABILIZACION"` de aquí en adelante (relevante para el Task 3).

- [ ] **Step 1: Borrar el archivo de la fase y su test**

```bash
git rm src/autoclave/state_machine/cycle_phases/estabilizacion.py tests/test_estabilizacion_fase.py
```

- [ ] **Step 2: Actualizar `ciclo.py`**

Reemplazar las líneas 7-8 (comentario de cabecera con el diagrama de secuencia) por:

```python
#   PRECALENTAMIENTO → PURGA → PRE_VACIO →
#   CALENTAMIENTO → ESTERILIZACION
```

Eliminar la línea 25 (`from autoclave.state_machine.cycle_phases.estabilizacion import EstabilizacionFase`).

En el bloque `self._fases = [...]` (líneas 68-77), eliminar la línea `EstabilizacionFase(*_args),` (línea 73), quedando:

```python
        self._fases = [
            PrecalentamientoFase(*_args),
            PurgaFase(*_args),
            PrevacioFase(*_args),
            CalentamientoFase(*_args),
            EsterilizacionFase(*_args),
            SecadoFase(*_args),
            DescompresionFase(*_args),
        ]
```

- [ ] **Step 3: Correr la suite completa y verificar que pasa**

Run: `pytest tests/ -v`
Expected: PASS — ningún test restante importa `EstabilizacionFase` ni depende de `"ESTABILIZACION"` como fase (confirmado por búsqueda previa en `tests/test_control_loop_desconexion_ciclo.py`, que no la referencia).

- [ ] **Step 4: Commit**

```bash
git add -A src/autoclave/state_machine/cycle_phases/estabilizacion.py tests/test_estabilizacion_fase.py src/autoclave/state_machine/states/ciclo.py
git commit -m "refactor: eliminar fase ESTABILIZACION del pipeline

Su funcion de sostenimiento queda fusionada en el tramo
ESTABLE_PREESTERILIZACION de CALENTAMIENTO (ver task anterior). El
pipeline pasa a CALENTAMIENTO -> ESTERILIZACION directo."
```

---

### Task 3: Limpiar mapeos muertos de ESTABILIZACION en UI y logging

**Files:**
- Modify: `src/autoclave/ui/cycle/cycle_window.py`
- Modify: `src/autoclave/ui/cycle/data/cycle_buffer.py`
- Modify: `src/autoclave/services/domain/logging/cycle_logger.py`

**Interfaces:** Ninguna — estos diccionarios son consumidos solo dentro de sus propios archivos vía `.get(fase)`; quitar una clave que nunca se va a consultar (la fase ya no existe) no cambia ninguna firma pública.

- [ ] **Step 1: `cycle_window.py` — quitar la entrada de `_FASE_TEMP_TARGET`**

En el diccionario de la línea 44-49, eliminar la línea:

```python
    "ESTABILIZACION":   ("estabilizacion",   "temperatura_estabilizacion"),
```

quedando:

```python
_FASE_TEMP_TARGET = {
    "PRECALENTAMIENTO": ("precalentamiento", "temperatura_precalentamiento"),
    "CALENTAMIENTO":    ("calentamiento",    "temperatura_calentamiento"),
    "ESTERILIZACION":   ("esterilizacion",   "temperatura_esterilizacion"),
}
```

- [ ] **Step 2: `cycle_buffer.py` — quitar la entrada de `FASE_DURACION_PARAM`**

En el diccionario de la línea 16-23, eliminar la línea:

```python
    "ESTABILIZACION":   "tiempo_estabilizacion",
```

quedando:

```python
FASE_DURACION_PARAM: dict[str, str] = {
    "PRECALENTAMIENTO": "tiempo_precalentamiento",
    "PURGA":            "tiempo_purga",
    "PRE_VACIO":        "tiempo_prevacio",
    "CALENTAMIENTO":    "tiempo_calentamiento",
    "ESTERILIZACION":   "tiempo_esterilizacion",
}
```

- [ ] **Step 3: `cycle_logger.py` — quitar ESTABILIZACION de los dos mapeos y corregir el comentario**

Reemplazar el comentario de cabecera (líneas 14-18) por:

```python
# Mapping de fases a códigos del ticket:
#   W (Warming)        → PRECALENTAMIENTO, PURGA, PRE_VACIO
#   H (Heating)        → CALENTAMIENTO
#   S (Sterilization)  → ESTERILIZACION
#   E (Exhaust/End)    → COMPLETADO, CANCELADO, FALLO, EMERGENCIA
```

En `_FASE_A_CODIGO` (líneas 44-55), eliminar la línea `"ESTABILIZACION":   "E",`, quedando:

```python
_FASE_A_CODIGO: dict[str, str] = {
    "PRECALENTAMIENTO": "PH",
    "PURGA":            "PG",
    "PRE_VACIO":        "PV",
    "CALENTAMIENTO":    "H",
    "ESTERILIZACION":   "S",
    "COMPLETADO":       "E",
    "CANCELADO":        "F",
    "FALLO":            "F",
    "EMERGENCIA":       "F",
}
```

En `_FASES_EN_CURSO` (líneas 62-66), eliminar `"ESTABILIZACION",`, quedando:

```python
_FASES_EN_CURSO: set[str] = {
    "PRECALENTAMIENTO", "PURGA", "PRE_VACIO",
    "CALENTAMIENTO", "ESTERILIZACION",
    "SECADO", "DESCOMPRESION",
}
```

- [ ] **Step 4: Correr la suite completa y verificar que pasa**

Run: `pytest tests/ -v`
Expected: PASS, incluyendo `tests/test_cycle_logger_printer.py` (no referencia ESTABILIZACION, confirmado antes de escribir este plan).

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/ui/cycle/cycle_window.py src/autoclave/ui/cycle/data/cycle_buffer.py src/autoclave/services/domain/logging/cycle_logger.py
git commit -m "chore: quitar mapeos de ESTABILIZACION en UI y logging de ticket

Referenciaban una seccion estabilizacion.* que nunca existio en los
perfiles activos (dead code ya antes de este cambio). De paso corrige
un bug latente: ESTABILIZACION estaba mal codificada como 'E'
(Exhaust/End) en vez de 'H' (Heating) en el ticket impreso."
```

---

### Task 4: Actualizar documentación

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/mis_plans/planeacion_fase_calentamiento.md`
- Modify: `docs/mis_plans/planeacion_fase_esterilizacion.md`

**Interfaces:** Ninguna — solo texto.

- [ ] **Step 1: `CLAUDE.md`**

Reemplazar el diagrama de secuencia (líneas 19-21):

```
PRECALENTAMIENTO → PURGA → PREVACIO → CALENTAMIENTO → ESTERILIZACION → (descompresión / secado / fin)
```

Reemplazar la lista de fases (líneas 23-30) por:

```markdown
Fases y su estado de diseño:
- `precalentamiento.py` — sostiene presión de chaqueta.
- `purga.py` — flujo de vapor para desplazar aire seco.
- `prevacio.py` — pulsos de vacío/vapor (hasta 4 tipos configurables).
- `calentamiento.py` — **rediseñado** (ver `docs/mis_plans/planeacion_fase_calentamiento.md`): tramos APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION, sin retroceso entre ellos. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`).
- `esterilizacion.py` — **rediseñado**, ver detalle abajo.
- `descompresion.py`, `secado.py`, `valvula_reposo.py`, `protocolo_fallo.py` — sin cambios recientes.
```

En la sección "ESTERILIZACION — diseño", corregir la línea 39 (menciona que viene de ESTABILIZACION, que ya no existe):

```markdown
Sostener la cámara en vapor saturado a `temperatura_esterilizacion` durante `tiempo_esterilizacion` minutos — la fase que efectivamente esteriliza. No hay tramo de aproximación: viene de CALENTAMIENTO ya en condición de vapor saturado.
```

- [ ] **Step 2: `docs/mis_plans/planeacion_fase_calentamiento.md`**

En la sección 1 ("Objetivo"), línea 12, reemplazar:

```markdown
Elevar la cámara desde la condición de salida de PRE_VACIO hasta el punto de vapor saturado correspondiente al setpoint de esterilización (`temperatura_calentamiento` + `presion_add_calentamiento`), y sostener esa condición (presión y temperatura) mediante una ventana continua de `tiempo_estable_preesterilizacion` segundos dentro de banda — reiniciada si sale de rango — antes de entregar el control directamente a ESTERILIZACION. Es la fase que prepara las condiciones de entrada para el ciclo de esterilización propiamente dicho; no realiza ninguna función de esterilización por sí misma. Absorbe la función que antes cumplía la fase separada `EstabilizacionFase` (eliminada del pipeline, ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`).
```

En "Posición en el pipeline" (línea 23), reemplazar el diagrama:

```
PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTERILIZACION
```

Reemplazar la sección 3 completa (máquina de estados interna, líneas 82-119) por:

```markdown
## 3. Máquina de estados interna de la fase

Tres tramos secuenciales, sin retroceso entre ellos (excepto por FALLO, que corta cualquier tramo):

```
[Entrada desde PRE_VACIO]
        │
        ▼
┌──────────────────────┐   |P_camara - P_sat(T_camara)| <= rango_calentamiento
│    APROXIMACION       │ ─────────────────────────────────────►┐
│  vapor_camara = ON    │                                        │
│  continuo             │                                        ▼
└──────────────────────┘                          ┌──────────────────────────┐
        │ timeout_calentamiento                    │       PWM_ACTIVO          │
        │ excedido                                 │  vapor_camara en PWM      │
        ▼                                          │  (factor_calentamiento /  │
     FALLO                                         │   intervalo_segmentos)    │
                                                     └──────────────────────────┘
                                                              │ T >= temperatura_calentamiento
                                                              │ Y P >= P_obj
                                                              ▼
                                               ┌────────────────────────────────┐
                                               │  ESTABLE_PREESTERILIZACION      │
                                               │  vapor_camara sigue en PWM      │
                                               │  dentro_rango = |T-t_obj|<=rango_temp_estabilizacion
                                               │    Y |P-P_obj|<=presion_add_calentamiento │
                                               └────────────────────────────────┘
                                                              │
                                        ┌─────────────────────┴─────────────────────┐
                                        │ dentro_rango: cuenta ventana continua       │ fuera de rango: reinicia
                                        │ tiempo_estable_preesterilizacion segundos   │ el conteo; arma timeout
                                        ▼                                            │ de recuperación
                                   COMPLETADO                                        ▼
                                                                            FALLO si no converge
                                                                            en timeout_recuperacion_estabilizacion
```

Los lazos de `descompresion_lenta` y `descompresion_rapida` corren **en paralelo a los tres tramos**, desde el inicio de la fase hasta `COMPLETADO`/`FALLO` — no están sincronizados con las transiciones de estado anteriores.

`tasa_calentamiento` / `tasa_presion` no producen `FALLO` — son exclusivamente parámetros de control, consumidos por el bang-bang de `APROXIMACION`.

Dentro del tramo `APROXIMACION`, `vapor_camara` es un bang-bang directo por tick: ON salvo que la pendiente medida (`tasa_t`/`tasa_p`) ya supere `tasa_calentamiento`/`tasa_presion`. Solo limita la dirección de subida (la válvula no puede enfriar).
```

Reemplazar la sección 5 completa (condición de finalización, líneas 149-163) por:

```markdown
## 5. Condición de finalización

```
P_obj = p_saturacion_kpa(temperatura_calentamiento) + presion_add_calentamiento

condición_entrada_al_tramo =
    temp_camara >= temperatura_calentamiento
    Y
    pres_camara >= P_obj

dentro_rango (evaluado cada tick DENTRO del tramo) =
    |temp_camara - temperatura_calentamiento| <= rango_temp_estabilizacion
    Y
    |pres_camara - P_obj| <= presion_add_calentamiento
```

- Al cumplirse `condición_entrada_al_tramo` por primera vez, se entra a `ESTABLE_PREESTERILIZACION`.
- Cada tick dentro del tramo se evalúa `dentro_rango` contra los objetivos fijos:
  - Si `True`: se cancela cualquier timeout de recuperación pendiente; si no hay una ventana en curso, arranca una (`_timer_sostenido_desde = now`). `COMPLETADO` cuando `time.time() - _timer_sostenido_desde >= tiempo_estable_preesterilizacion`.
  - Si `False`: la ventana en curso se reinicia (`_timer_sostenido_desde = None`) — el conteo debe volver a empezar desde cero la próxima vez que entre en banda. Si no había un timeout de recuperación armado, se arma uno (`now + timeout_recuperacion_estabilizacion*60`); si se excede sin haber vuelto a `dentro_rango`, `FALLO`.
- Con `tiempo_estable_preesterilizacion == 0`, la fórmula de arriba completa en el mismo tick en que se entra al tramo (la ventana requerida es de 0 segundos) — no hace falta un caso especial en el código.
```

Reemplazar la fila de la tabla FMEA (sección 8) que describe el riesgo aceptado del timer sin reinicio (antigua fila "ESTABLE_PREESTERILIZACION | Condición sale de rango pero timer no se reinicia...") por:

```markdown
| ESTABLE_PREESTERILIZACION | Oscilación prolongada dentro/fuera de banda nunca completa una ventana continua | Fase nunca completa por esta vía | Control de vapor_camara (PWM_ACTIVO) mal calibrado para el volumen de cámara, o inercia térmica mayor a la esperada | `timeout_recuperacion_estabilizacion` (timeout dedicado, arma cuando sale de banda, se cancela al recuperar) | Timeout dedicado + `timeout_calentamiento` global como red de seguridad final |
```

y eliminar la "Nota de riesgo (fila 6 de la matriz)" que documentaba el timer sin reinicio como riesgo aceptado (ya no aplica — el rediseño resuelve exactamente ese riesgo).

- [ ] **Step 3: `docs/mis_plans/planeacion_fase_esterilizacion.md`**

Reemplazar el diagrama de pipeline (línea 25):

```
... → CALENTAMIENTO → ESTERILIZACION → (fin de ciclo)
```

Reemplazar la línea 30 ("Estado de cámara al salir de ESTABILIZACION..."):

```markdown
- Estado de cámara al salir de CALENTAMIENTO (ya validada en condición de vapor saturado tras la ventana continua de estabilidad de su tramo ESTABLE_PREESTERILIZACION, pero esta fase no asume que se mantenga — contempla tramo de recuperación desde el primer tick).
```

- [ ] **Step 4: Verificación final — grep de referencias sueltas**

Run: `grep -rn "ESTABILIZACION" CLAUDE.md docs/mis_plans/`
Expected: sin resultados (todas las referencias activas quedaron actualizadas).

Run: `pytest tests/ -v`
Expected: PASS — confirma que los cambios de este plan (Tasks 1-3) no quedaron con ningún cabo suelto.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/mis_plans/planeacion_fase_calentamiento.md docs/mis_plans/planeacion_fase_esterilizacion.md
git commit -m "docs: actualizar documentacion tras fusionar ESTABILIZACION en CALENTAMIENTO

Diagrama de pipeline, lista de fases y especificacion detallada del
tramo ESTABLE_PREESTERILIZACION reflejan el nuevo diseno de ventana
continua con reinicio."
```
