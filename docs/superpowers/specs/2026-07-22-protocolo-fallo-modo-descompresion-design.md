# Spec — Protocolo de fallo usa el modo de descompresión del ciclo
**Fecha:** 2026-07-22

## Alcance

Hoy `ProtocoloFallo` (`src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`), al detectar la cámara presurizada en el momento de un fallo/aborto, siempre abre `descompresion_lenta`. Se cambia ese comportamiento para que la despresurización de emergencia siga la misma estrategia de válvulas que el **modo de descompresión configurado en el ciclo** (`descompresion.modo`, 0–5), en vez de estar fijo a "lenta".

**Sin cambios:** el caso Normal/Vacío (`pres <= atm + rango` en el momento del disparo) sigue exactamente igual — `aire_admosferico_camara_on()`, sin lógica de modos.

**Fuera de alcance:** `DescompresionFase` (fin de ciclo normal) no se modifica. No se toca la lógica de puertas, sensores críticos, ni el resto de `CicloState`.

---

## Decisiones de diseño

1. **Modos 4 y 5 en fallo omiten la etapa de enfriamiento.** En un ciclo normal esperan a que `temp_camara` baje antes de descomprimir (pulsos de chaqueta, aire comprimido). En fallo van directo a la descompresión final: `descompresion_chaqueta_on()` + `descompresion_rapida_on()`. Motivo: en una emergencia interesa evacuar presión cuanto antes, no mantener la cámara presurizada/caliente esperando enfriamiento.
2. **Modo 0 (pasivo) se fuerza a modo 2 (lenta) como salvaguarda.** Un fallo con la cámara presurizada y ninguna válvula activa no es aceptable aunque el ciclo tenga configurado "sin acción". Se registra en el log que fue forzado.
3. **Timeout por modo con escalamiento.** Cada modo tiene su propio `timeout` (ya definido en el JSON del ciclo). Si se agota sin llegar a presión atmosférica, se escala automáticamente a `descompresion_chaqueta_on()` + `descompresion_rapida_on()` (la vía más agresiva) como último recurso, y se loguea una única vez. El modo 0 forzado usa el timeout de `modo_2` (no existe `modo_0.timeout` en el JSON).

---

## Arquitectura

### Firma del constructor

```python
class ProtocoloFallo:
    def __init__(self, estado, set_do, cycle, config):
```

Se agrega `cycle` como tercer parámetro posicional (mismo orden que usa `BaseFase`: `estado, set_do, cycle, config, ...`).

**Llamador a actualizar:** `CicloState.__init__` (`src/autoclave/state_machine/states/ciclo.py:78`):
```python
self._protocolo = ProtocoloFallo(estado, set_do, self.cycle, config)
```

### Estado interno nuevo

| Variable | Tipo | Propósito |
|----------|------|-----------|
| `_presurizado_al_disparo` | `bool` | `True` si al ejecutar() la cámara estaba presurizada. Determina qué rama sigue `update()`. |
| `_modo` | `int \| None` | Modo leído de `cycle.get_param("descompresion", "modo", default=0)` en el momento del disparo. `None` si no aplica (rama Normal/Vacío). |
| `_sub_etapa` | `str \| None` | Solo para modo 3: `"lenta"` / `"rapida"`. |
| `_t_timeout_descompresion` | `float \| None` | Timestamp límite calculado con el `timeout` del modo (o de `modo_2` si el modo era 0). |
| `_escalado` | `bool` | `True` una vez que se forzó chaqueta+rápida por timeout agotado. |

Todas se reinician en `reset()`.

### `ejecutar()` — cambios

Reemplaza el bloque actual:
```python
elif pres > atm + rango:
    self.set_do.descompresion_lenta_on()
```
por:
```python
elif pres > atm + rango:
    self._presurizado_al_disparo = True
    self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
    self._sub_etapa = "lenta" if self._modo == 3 else None
    self._t_timeout_descompresion = self._calcular_timeout(time.time())
    self._aplicar_paso_modo(pres)
```
La rama `else` (Normal/Vacío) **no cambia**: sigue llamando `aire_admosferico_camara_on()`.

### `_calcular_timeout(now)`

```python
timeout_key = "modo_2" if self._modo == 0 else f"modo_{self._modo}"
timeout_min = self.cycle.get_param("descompresion", timeout_key, "timeout", default=60)
return now + (timeout_min or 60) * 60
```

### `_aplicar_paso_modo(pres)` — un paso de la estrategia según el modo

```python
def _aplicar_paso_modo(self, pres):
    if self._escalado:
        self.set_do.descompresion_chaqueta_on()
        self.set_do.descompresion_rapida_on()
        return

    modo_efectivo = 2 if self._modo == 0 else self._modo

    if modo_efectivo == 1:
        self.set_do.descompresion_rapida_on()
    elif modo_efectivo == 2:
        self.set_do.descompresion_lenta_on()
    elif modo_efectivo == 3:
        if self._sub_etapa == "lenta":
            presion_cambio = self.cycle.get_param(
                "descompresion", "modo_3", "presion_cambio", default=150
            )
            self.set_do.descompresion_lenta_on()
            if pres <= presion_cambio:
                self.set_do.descompresion_lenta_off()
                self._sub_etapa = "rapida"
        else:
            self.set_do.descompresion_rapida_on()
    elif modo_efectivo in (4, 5):
        self.set_do.descompresion_chaqueta_on()
        self.set_do.descompresion_rapida_on()
```

### `update()` — cambios

Reemplaza el bloque de "Gestión dinámica de presión" actual:

```python
if pres > atm + rango:
    if self._presurizado_al_disparo:
        if not self._escalado and time.time() > self._t_timeout_descompresion:
            logger.error(
                "Protocolo fallo: timeout del modo %d agotado, escalando a chaqueta+rápida",
                self._modo,
            )
            self._escalado = True
        self._aplicar_paso_modo(pres)
    else:
        # Nunca estuvo presurizada al disparo pero subió después:
        # comportamiento heredado, sin cambios.
        self.set_do.descompresion_lenta_on()
        self.set_do.aire_admosferico_camara_off()
else:
    # Rango normal o vacío: apagar válvulas de descompresión y mantener
    # aire atmosférico — converge con el comportamiento actual, sin cambios.
    self.set_do.descompresion_rapida_off()
    self.set_do.descompresion_lenta_off()
    self.set_do.descompresion_chaqueta_off()
    self.set_do.aire_admosferico_camara_on()
```

Requiere `import time` (no está importado actualmente en `protocolo_fallo.py`).

La lógica del buzzer ("condiciones seguras") **no cambia**.

### Resumen de comportamiento por modo (cámara presurizada al disparo)

| Modo seleccionado | Paso inicial y continuo | Timeout usado | Tras timeout agotado |
|---|---|---|---|
| 0 | Lenta (forzado) | `modo_2.timeout` | Chaqueta + rápida |
| 1 | Rápida | `modo_1.timeout` | Chaqueta + rápida |
| 2 | Lenta | `modo_2.timeout` | Chaqueta + rápida |
| 3 | Lenta hasta `presion_cambio`, luego rápida | `modo_3.timeout` | Chaqueta + rápida |
| 4 | Chaqueta + rápida (sin enfriamiento) | `modo_4.timeout` | Chaqueta + rápida (ya es la vía final) |
| 5 | Chaqueta + rápida (sin enfriamiento) | `modo_5.timeout` | Chaqueta + rápida (ya es la vía final) |

Al llegar a rango atmosférico/vacío, todos los modos convergen igual que hoy: válvulas de descompresión off + aire atmosférico on + buzzer cuando corresponde.

---

## Tests

**Archivo:** `tests/test_protocolo_fallo_modo_descompresion.py`

**Helper:** extender el patrón de `tests/test_protocolo_fallo_reintento.py`, agregando un `cycle = MagicMock()` con `get_param` configurado vía `side_effect` según claves.

**Actualización necesaria:** `tests/test_protocolo_fallo_reintento.py` — el constructor de `ProtocoloFallo` pasa a requerir `cycle`; actualizar `_make_protocolo()` para incluir un `cycle` mock (modo irrelevante para esos tests, ya que la presión ahí es atmosférica).

| Test | Qué verifica |
|------|-------------|
| `test_normal_vacio_sin_cambios` | Con `pres` en rango normal al disparo → `aire_admosferico_camara_on`, sin leer `cycle.get_param("descompresion", "modo", ...)` en la rama de decisión de válvula |
| `test_modo_0_se_fuerza_a_lenta` | Modo configurado `0`, presurizada → `descompresion_lenta_on` |
| `test_modo_0_usa_timeout_de_modo_2` | Verifica que el timeout calculado usa `modo_2.timeout`, no falla por `modo_0.timeout` inexistente |
| `test_modo_1_activa_rapida` | Modo `1`, presurizada → `descompresion_rapida_on` |
| `test_modo_2_activa_lenta` | Modo `2`, presurizada → `descompresion_lenta_on` |
| `test_modo_3_lenta_hasta_presion_cambio` | Modo `3`, `pres > presion_cambio` → `lenta_on`, no `rapida` |
| `test_modo_3_transicion_a_rapida` | Modo `3`, `pres <= presion_cambio` → `lenta_off` + `rapida_on` |
| `test_modo_4_va_directo_a_final_sin_enfriamiento` | Modo `4`, presurizada → `chaqueta_on` + `rapida_on` en el primer tick, sin tocar `agua_chaqueta`/`aire_comprimido_camara` |
| `test_modo_5_va_directo_a_final_sin_enfriamiento` | Igual que modo 4 |
| `test_timeout_agotado_escala_a_rapida` | Modo `2`, timeout vencido y aún presurizada → `chaqueta_on` + `rapida_on`, log de error una vez |
| `test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm` | Presión baja a rango normal en un tick posterior → apaga rapida/lenta/chaqueta, activa aire atmosférico (para cualquier modo) |
| `test_buzzer_sin_cambios` | Condiciones seguras tras descompresión por modo → buzzer emitido una sola vez (regresión) |

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py` | Modificar — agregar `cycle`, estrategia por modo, timeout/escalamiento |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — pasar `self.cycle` a `ProtocoloFallo(...)` |
| `tests/test_protocolo_fallo_reintento.py` | Modificar — adaptar `_make_protocolo()` al nuevo constructor |
| `tests/test_protocolo_fallo_modo_descompresion.py` | Crear |
