# Spec: suministro_electrico — Modo Seguro por Corte Eléctrico

**Fecha:** 2026-05-27  
**Rama:** `dev`

---

## Objetivo

Detectar la pérdida de suministro eléctrico (DI `suministro_electrico` = 0) y ejecutar un protocolo de seguridad diferenciado según si el equipo está en ciclo o en espera.

---

## Contexto

- `suministro_electrico` ya existe en `EstadoAutoclave.map_di` (índice 13). El hardware ya envía el dato.
- El patrón `EmergencyStop` / flag `PARO_EMERGENCIA` es el modelo a seguir.
- `ProtocoloFallo.ejecutar()` ya descomprime sin bomba de vacío (usa `descompresion_lenta` o `aire_admosferico_camara`).
- La apertura de puertas en `ServicioPuertas` no involucra la bomba; el bloqueo es por presión/temperatura.

---

## Comportamiento esperado

### Fuera de ciclo (PREPARADO)

| Condición | Acción |
|-----------|--------|
| `suministro_electrico` → 0 | Setear flag `FALLO_SUMINISTRO_ELECTRICO` |
| Flag activo | Apagar bomba de vacío |
| Flag activo | Bloquear `LISTO_PARA_CICLO` → botón de inicio deshabilitado |
| Flag activo | Alarma `ALERTA` "SUMINISTRO_ELECTRICO" (recuperable, no bloqueante de hardware) |
| Puertas avanzadas | Permitir apertura/cierre en **modo seguro** (ver sección Puertas) |

### En ciclo (CICLO)

| Condición | Acción |
|-----------|--------|
| `suministro_electrico` → 0 | Detectar en `CicloState.run()` |
| — | Ejecutar `ProtocoloFallo` (apaga todo, abre válvula de descompresión sin bomba) |
| — | Registrar alarma `EMERGENCIA` "FALLO_SUMINISTRO_ELECTRICO" |
| — | Transición → `FALLO` → estado `FALLA` (requiere reconocimiento del operador) |

---

## Diseño por capas

### 1. Device — `devices/suministro_electrico/suministro_electrico.py` (archivo nuevo)

Clase `SuministroElectrico`, espejo exacto de `EmergencyStop`:
- `update(value: bool)` — setea/limpia `FALLO_SUMINISTRO_ELECTRICO` en `estado`
- En flanco bajante (1→0): llama `set_do.bomba_vacio_off()` directamente

### 2. Flag — `core/status.py`

Agregar a `_flags_map`:
```python
"FALLO_SUMINISTRO_ELECTRICO": 7,
```
(Renumerar si hay conflicto con índice existente.)

### 3. Control Loop — `services/domain/loop/control_loop.py`

Instanciar `SuministroElectrico` en `__init__`. En `run()`, después de `paro_emergencia.update(...)`:
```python
self.suministro_electrico.update(
    bool(self.estado.sensores_di.get("suministro_electrico", 1))
)
```
Default `1` para no disparar antes de la primera lectura del hardware.

### 4. VacuumPump — `devices/pump/pump.py`

En `puede_activar()`, agregar:
```python
if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
    logger.warning("Bomba bloqueada: fallo de suministro eléctrico.")
    return False
```

### 5. Estado PREPARADO — `state_machine/states/preparado.py`

- `verificar_suministros()`: agregar `"suministro_electrico"` a la lista de suministros verificados (genera alarma `ALERTA` si = 0).
- `esta_preparado()`: agregar `not self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")`.

### 6. Estado CICLO — `state_machine/states/ciclo.py`

En `CicloState.run()`, después del bloque de `PARO_EMERGENCIA` (paso 2):
```python
if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
    logger.error("CicloState: ABORTADO por fallo de suministro eléctrico")
    self.estado.fase_ciclo = "FALLO_SUMINISTRO"
    self.alarm_manager.report(Alarm(
        alarm_id="FALLO_SUMINISTRO_ELECTRICO",
        alarm_type=AlarmType.EMERGENCIA,
        source_state="CICLO",
        description="Pérdida de suministro eléctrico durante el ciclo.",
        recoverable=False,
    ))
    self._protocolo.ejecutar()
    self._resultado_pendiente = CicloResultado.FALLO
    return CicloResultado.ESPERANDO_CONFIRMACION
```

### 7. Puertas avanzadas — `devices/puertas/advanced_door.py`

**Nuevo parámetro:** `alarm_manager` en `__init__`.

**Modo seguro en `_from_abriendo()` y `_from_cerrando()`:**

| Paso | Normal | Modo seguro (flag activo) |
|------|--------|--------------------------|
| Vacío | `vacio_on()` (bomba + válvula) | Solo `desbloquear_on()` (válvula, sin bomba) |
| Umbral de presión | `presion_empaque() <= vacio_empaque` | `presion_empaque() <= presion_admosferica + rango_presion_atm` |
| Alarma | — | `ALERTA` no bloqueante `ABRIENDO_MODO_SEGURO` |

La alarma `ABRIENDO_MODO_SEGURO` se limpia al llegar a `DoorState.ABIERTO` o `DoorState.CERRADO`.

**Archivos afectados además de `advanced_door.py`:**
- `devices/puertas/door_factory.py`: pasar `alarm_manager` en dict `io`
- `backend/context.py`: incluir `alarm_manager` al crear puertas

### 8. UI — `ui/window/main_window.py`

Agregar indicador en el footer junto al indicador de conexión:

- `⚡ Suministro: OK` (texto verde `#7FFF7F`) cuando `suministro_electrico = 1`
- `⚡ Sin suministro` (texto rojo `#FF7F7F`) cuando `suministro_electrico = 0`

Lee `get_sensores_di()["suministro_electrico"]` desde `ui_service`.

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `devices/suministro_electrico/suministro_electrico.py` | **Nuevo** |
| `core/status.py` | Agregar flag |
| `services/domain/loop/control_loop.py` | Instanciar device + llamar update |
| `devices/pump/pump.py` | Bloquear si flag activo |
| `state_machine/states/preparado.py` | Verificar suministro + bloquear listo |
| `state_machine/states/ciclo.py` | Detectar flag → abortar ciclo |
| `devices/puertas/advanced_door.py` | Modo seguro + alarm_manager |
| `devices/puertas/door_factory.py` | Pasar alarm_manager |
| `backend/context.py` | Incluir alarm_manager en create_door |
| `ui/window/main_window.py` | Indicador de suministro en footer |

---

## Criterios de aceptación

1. Con `suministro_electrico = 0` y equipo en PREPARADO: botón de inicio deshabilitado, bomba no arranca, alarma visible en panel izquierdo.
2. Con `suministro_electrico = 0` durante ciclo activo: ciclo aborta, cámara descomprime sin bomba, equipo va a estado FALLA.
3. Puerta avanzada con flag activo: abre/cierra sin bomba, usando solo la válvula de empaque, con umbral atmosférico.
4. Alarma `ABRIENDO_MODO_SEGURO` visible durante la maniobra, se limpia al completar.
5. Al restaurar `suministro_electrico = 1`: flag se limpia, alarmas desaparecen, sistema vuelve a permitir ciclos.
