# Handoff — Estado al 2026-05-27

**Rama activa:** `dev`  
**PR abierto:** [#15 — feat: suministro_electrico modo seguro](https://github.com/Alexis73-10/Software-de-autoclave/pull/15)

---

## Qué se hizo hoy

### Feature completa: `suministro_electrico` — modo seguro ante corte eléctrico

La DI `suministro_electrico` (índice 13, ya existía en el hardware) ahora dispara un protocolo de seguridad diferenciado.

**Comportamiento implementado:**

- **Fuera de ciclo (PREPARADO):** flag `FALLO_SUMINISTRO_ELECTRICO` bloquea el botón de inicio y la bomba de vacío; genera alarma `ALERTA` recuperable `"SUMINISTRO_ELECTRICO"`.
- **En ciclo (CICLO):** ciclo abortado inmediatamente, `ProtocoloFallo` descomprime sin bomba, transición a FALLA requiere confirmación del operador.
- **Puertas avanzadas (modo seguro):** apertura/cierre sin bomba, solo válvula de empaque (`desbloquear_on`), umbral de presión atmosférica (`presion_admosferica + rango_presion_atm` ≈ 121 kPa), alarma no bloqueante `ABRIENDO/CERRANDO_MODO_SEGURO_{nombre}` única por puerta.
- **UI:** indicador `⚡ Suministro: OK` (verde) / `⚡ Sin suministro` (rojo) en el footer.

**Archivos creados/modificados:**

| Archivo | Cambio |
|---------|--------|
| `devices/suministro_electrico/suministro_electrico.py` | Nuevo device (patrón EmergencyStop) |
| `core/status.py` | Flag `FALLO_SUMINISTRO_ELECTRICO` en índice 7 |
| `services/domain/loop/control_loop.py` | Instancia y llama `update()` con default 1 |
| `devices/pump/pump.py` | `puede_activar()` retorna False si flag activo |
| `state_machine/states/preparado.py` | `verificar_suministros()` + `esta_preparado()` |
| `state_machine/states/ciclo.py` | Bloque 2b post-PARO_EMERGENCIA |
| `devices/puertas/advanced_door.py` | Modo seguro + `_alarm_report/clear()` guards |
| `devices/puertas/door_factory.py` | Pasa `alarm_manager` |
| `backend/context.py` | Incluye `alarm_manager` en `create_door` |
| `ui/window/main_window.py` | `_lbl_suministro` + `_upd_suministro()` en footer |

**Tests:** 24 nuevos, todos green. Sin regresiones en los 65 tests existentes.

**Commits relevantes (más reciente primero):**
```
6b17958  docs: spec y plan de implementación de suministro_electrico
0178c82  feat: indicador de suministro eléctrico en footer de la UI
7f7aa24  feat: context.py pasa alarm_manager a create_door
8788594  fix: AdvancedDoor — alarm guard, IDs distintos, tests _from_cerrando
debed05  feat: AdvancedDoor modo seguro — abre/cierra sin bomba
81e030f  feat: CicloState aborta y descomprime ante fallo de suministro
9d4e724  feat: preparado_state bloquea ciclo ante fallo de suministro
80b4584  feat: ControlLoop integra SuministroElectrico
3ca0803  feat: VacuumPump bloquea si FALLO_SUMINISTRO_ELECTRICO activo
e57b97c  feat: SuministroElectrico device y flag
```

---

## Issue pendiente: CalentamientoFase crash en producción

**Este issue existía antes de hoy y NO fue resuelto.**

### Crash observado

```
TypeError: '<=' not supported between instances of 'float' and 'NoneType'
  File "calentamiento.py", line 89 in update
    if self._verificar_vapor_saturado(temp, pres, tolerancia):
  File "base_fase.py", line 71 in _verificar_vapor_saturado
    return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
```

`tolerancia_kpa` llega como `None` → el ciclo Bowe & Dick no tiene el parámetro que el código busca.

### Estado actual de `calentamiento.py`

El archivo tiene cambios **sin commitear** en el working tree:

| Línea | Problema |
|-------|----------|
| 36 | `t_obj = get_param(...)` — sin fallback `or 134.0` |
| 37 | `tasa_seg = (get_param(...)) / 60` — sin fallback, crash si None |
| 38 | `timeout_seg = (get_param(...)) * 60` — sin fallback, crash si None |
| 39 | `tolerancia = get_param("calentamiento", "rango_presion_calentamiento")` — sin fallback `or 9.0` |
| 49 | `self._checkpoints = [0.80 * t_obj, 0.97 * t_obj]` — spec dice 0.50/0.90 |

### Problema de fondo — conflicto de nombres de parámetros

| Ciclo | Clave JSON | Sección |
|-------|-----------|---------|
| `instrumental_134` | `presion_add_calentamiento` | `calentamiento` |
| `bowe_dick` | `rango_presion_calentamiento` | `calentamiento` |

El código (línea 39) usa `rango_presion_calentamiento` (editado manualmente por el usuario), pero `instrumental_134.json` tiene `presion_add_calentamiento` → ese ciclo queda con `tolerancia = None`.

### Opciones para resolver

**A. Unificar en `rango_presion_calentamiento`** — renombrar la clave en todos los `instrumental_134.json`. Código usa ese nombre + `or 9.0` de fallback.

**B. Buscar con fallback entre las dos claves** — código prueba `rango_presion_calentamiento`, si None prueba `presion_add_calentamiento`. Más flexible, más complejo.

**C. Unificar en `presion_add_calentamiento`** — renombrar en `bowe_dick.json`. Mismo efecto que A, distinto nombre canónico.

### Qué falta por hacer

1. Elegir la estrategia (A, B o C).
2. Actualizar los JSONs afectados.
3. Restaurar defaults `or X` en líneas 36-39 de `calentamiento.py`.
4. Decidir si checkpoints van a 0.50/0.90 (spec) o 0.80/0.97 (cambio del fix subagent). El test `test_checkpoint_entra_en_sostenimiento` falla actualmente por este motivo.
5. Commitear `calentamiento.py`.
6. Correr `pytest tests/test_calentamiento_fase.py -v` para verificar.
