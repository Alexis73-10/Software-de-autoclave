# Handoff — Estado al 2026-06-03 (sesión 2)

**Rama activa:** `dev`  
**PR abierto:** [#16 — feat: UI responsive a orientación — layout portrait + font scaling](https://github.com/Alexis73-10/Software-de-autoclave/pull/16)  
**PR anterior (pendiente de merge):** [#15 — feat: suministro_electrico modo seguro](https://github.com/Alexis73-10/Software-de-autoclave/pull/15)

---

## Qué se hizo hoy (sesión 2, 2026-06-03) — Puertas + modos descomp + generador

### Commits del día (sesión 2)

| Commit | Descripción |
|--------|-------------|
| `401f25b` | feat: EquipmentCapabilities agrega cooling_mode_max por clase de equipo |
| `f5d5e61` | feat: storage.delete() + wizard borra perfil bloqueado antes de reinstalar |
| `d562118` | feat: puertas MOTORIZED/MOTORIZED_LOCKING bloquean apertura si sensor activo |
| `13ac3b5` | fix: test_advanced_door usa side_effect por clave + cobertura LOCKING y puerta 2 |
| `33afa67` | feat: AdvancedDoor mantiene desbloquear activo hasta vacio de empaque |
| `f700d94` | fix: test_desbloquear_baja verifica que desbloquear_on no se llama |
| `8396b60` | feat: generador — módulo db.py con historial de códigos generados |
| `3c9b941` | fix: db.py CHECK constraint en tipo + eliminar commit() redundante |
| `e79ca81` | feat: generador con historial de códigos y lógica de reinstalación |
| `aa576cf` | fix: generar_post registra antes de obtener historial + guards en reinstalar |

### Detalle

**`EquipmentCapabilities.cooling_mode_max` (`401f25b`):**
Campo nuevo en el dataclass: MESA_N=1, MESA_B/PISO=3, lab=5. Sin UI ni validación aún (modos no implementados).

**`storage.delete()` + wizard reinstalación (`f5d5e61`):**
`storage.delete()` borra el archivo de perfil sin lanzar si no existe. `wizard.instalar()` llama `delete()` antes de `save()`, resolviendo el caso de perfil corrupto/bloqueado que impedía reinstalar.

**Puertas MOTORIZED — bloqueo por sensor (`d562118`, `13ac3b5`):**
`factory._build_door_cfg()` agrega `di["bloqueo"] = "bloqueo_puerta_N"` para MOTORIZED y MOTORIZED_LOCKING. `AdvancedDoor.cmd_abrir()` deniega apertura si el sensor está activo. ADVANCED no recibe el sensor (usa presión de empaque). 9 tests en `tests/test_advanced_door.py`.

**AdvancedDoor desbloqueo biestable (`33afa67`, `f700d94`):**
`_from_abriendo()` ya no apaga `desbloquear` en el segundo ciclo. Ahora mantiene `desbloquear_on()` mientras `presion_empaque() > vacio_empaque` y llama `desbloquear_off()` solo cuando cae al umbral. `_from_cerrando()` sin cambios. `_pulso_desbloqueo_enviado` conservado (lo usa `_from_cerrando()`).

**Generador — módulo db.py (`8396b60`, `3c9b941`):**
Nuevo `tools/generador/db.py` con `init_db()`, `fue_instalado()`, `log_codigo()`, `get_history()`. SQLite en `tools/generador/generador.db`. CHECK constraint en columna `tipo`. 8 tests en `tests/test_generador_db.py`.

**Generador — historial y reinstalación (`e79ca81`, `aa576cf`):**
`app.py` reescrito: `_sessions` es `dict[str,str]` (token→usuario), `generar_post` decide si mostrar código de instalación o solo de fábrica según historial, nuevo endpoint `POST /reinstalar`, tabla de historial en el dashboard. Historial se obtiene después de loguear para incluir la entrada nueva.

### Estado de tests

```
173 passed, 2 warnings (deprecation en test_storage.py — datetime.utcnow())
```

---

## Qué sigue

- Cerrar la rama: invocar `superpowers:finishing-a-development-branch` para review final + PR
- Issue pendiente (pre-existente): `test_checkpoint_entra_en_sostenimiento` — checkpoints en código 0.80/0.97 vs spec 0.50/0.90

---

## Qué se hizo antes (sesión 1, 2026-06-03) — Fixes post-perfiles + HAL mejorado

### Commits

| Commit | Descripción |
|--------|-------------|
| `869ecb9` | fix: CalentamientoFase — crash tolerancia=None por clave JSON inconsistente |
| `19f68f6` | feat: HAL detecta sensores desconectados + calibración polinomial |
| `b576148` | fix: pytest ignora scripts no-test + test_steam pasa cap a BaseFase |

---

## Qué sigue

### Paso inmediato: cerrar la rama de perfiles de equipo

Invocar `superpowers:finishing-a-development-branch` para:
1. Revisión final de toda la implementación (perfiles + HAL + fixes)
2. Crear PR con todos los cambios desde `649a4c6`

### Issue pendiente aún: checkpoints de CalentamientoFase

El test `test_checkpoint_entra_en_sostenimiento` sigue fallando (pre-existente, no introducido esta semana):
- Spec y test esperan checkpoints en 0.50/0.90
- Código tiene 0.80/0.97
- Decisión pendiente: ajustar el código a la spec o actualizar la spec

---

## Qué se hizo ayer (2026-06-02) — Implementación de perfiles de equipo

### Resultado

Se implementaron completamente los 5 perfiles de equipo. Los 11 tasks del plan están completados con revisión de spec y calidad por cada uno. Lo que queda para mañana es el review final y el flujo de cierre de rama.

**Plan:** `docs/superpowers/plans/2026-06-02-equipment-profiles-impl.md`  
**Commits del día:** `649a4c6` → `0b367dd` (13 commits)

---

### Archivos nuevos creados hoy

| Archivo | Commit | Descripción |
|---------|--------|-------------|
| `src/autoclave/installation/equipment.py` | `649a4c6` | `EquipmentClass`, `EquipmentCapabilities`, `get_capabilities()` |
| `src/autoclave/devices/puertas/door_type.py` | `fb68459` | `DoorType` enum (5 valores) |
| `tests/test_equipment.py` | `649a4c6` | 7 tests de capacidades |
| `tests/test_prevacio_caps.py` | `2d7635e` | 3 tests de skip sin vacío |
| `tests/test_calentamiento_caps.py` | `1476750` | 4 tests de sensor dual |
| `tests/test_esterilizacion_caps.py` | `7b4252a` + `bdb8787` | 4 tests de sensor dual + None |

### Archivos modificados hoy

| Archivo | Commit | Cambio |
|---------|--------|--------|
| `src/autoclave/installation/profile.py` | `17198db` | +`equipment_class`, +`door_type: DoorType`, +`cooling_level`; -`equipment_type`, -`drying_type` |
| `src/autoclave/installation/storage.py` | `17198db` | load/save para los nuevos campos |
| `src/autoclave/installation/wizard.py` | `b9be989` + `0b367dd` | 5 pasos (antes 2); selección de perfil, puertas, enfriamiento |
| `src/autoclave/devices/puertas/advanced_door.py` | `292ec48` | Claves do/ai/di opcionales sin fallar |
| `src/autoclave/devices/puertas/door_factory.py` | `4a47e55` | Usa `DoorType` enum, crea `SimpleDoor` o `AdvancedDoor` |
| `src/autoclave/devices/factory/factory.py` | `4a47e55` | IO condicional por `DoorType` |
| `src/autoclave/state_machine/cycle_phases/base_fase.py` | `92ffe4d` | +`cap` como 6° param + `_temp_camara_2()` |
| `src/autoclave/backend/context.py` | `730c7b2` | Llama `get_capabilities()` y pasa `cap` a `ControlLoop` |
| `src/autoclave/services/domain/loop/control_loop.py` | `730c7b2` | Acepta y pasa `cap` a `StateMachine` |
| `src/autoclave/state_machine/state_machine.py` | `730c7b2` | Acepta y pasa `cap` a `CicloState` |
| `src/autoclave/state_machine/states/ciclo.py` | `730c7b2` | Pasa `cap` a cada fase |
| `src/autoclave/state_machine/cycle_phases/prevacio.py` | `2d7635e` | Skip si `cap.has_vacuum` es False |
| `src/autoclave/state_machine/cycle_phases/calentamiento.py` | `1476750` | Dual sensor si `cap.has_liquid_sensor` |
| `src/autoclave/state_machine/cycle_phases/esterilizacion.py` | `7b4252a` + `bdb8787` | Dual sensor; falla si sensor declarado sin lectura |
| `tests/test_profile_validation.py` | `17198db` | Actualizado para nuevos campos |
| `tests/test_door_from_profile.py` | `4a47e55` | Actualizado para `DoorType` enum |
| *(5 test files de fases)* | `92ffe4d` | `cap=MagicMock()` como 6° arg en todos los helpers |

---

### Estado de los tests

```
pytest tests/ --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```

- **~99 pasan**
- **1 falla pre-existente:** `test_checkpoint_entra_en_sostenimiento` en `test_calentamiento_fase.py`  
  (checkpoints en código: 0.80/0.97; spec y test esperan 0.50/0.90 — no fue introducido hoy)

---

## Historial de sesiones anteriores

### 2026-06-02 — Implementación de perfiles de equipo (13 commits: `649a4c6` → `0b367dd`)

5 perfiles de equipo completamente implementados: `EquipmentClass`, `EquipmentCapabilities`, `DoorType` enum, wizard de 5 pasos, `cap` inyectado hasta `BaseFase`, fases con comportamiento condicional por capacidades. ~99 tests pasan. Crash `tolerancia=None` en `CalentamientoFase` resuelto al día siguiente (`869ecb9`). Plan: `docs/superpowers/plans/2026-06-02-equipment-profiles-impl.md`.

### 2026-06-01 — Diseño de perfiles de equipo (solo spec, sin código)

Se definió el diseño completo: 5 perfiles, 5 tipos de puerta, tabla de capacidades, arquitectura Opción B (EquipmentCapabilities en memoria, EquipmentClass en disco). Doc: `docs/superpowers/specs/2026-06-01-equipment-profiles-design.md`.

### 2026-05-28 — UI responsive a orientación

La UI detecta flips landscape ↔ portrait en ambos monitores y reconstruye el layout sin perder estado del ciclo. Font scaling, layout portrait para `InterfazPrincipal` y `CycleWindow`, fix multi-monitor con `winfo_width/height`. 20 tests nuevos. Commits `d20e14b` → `3e62ed3`.

### 2026-05-27 — `suministro_electrico` modo seguro (PR #15)

Flag `FALLO_SUMINISTRO_ELECTRICO` bloquea inicio de ciclo y bomba. En ciclo activo aborta y descomprime sin bomba. Puertas avanzadas con apertura sin bomba. Indicador en footer UI.
