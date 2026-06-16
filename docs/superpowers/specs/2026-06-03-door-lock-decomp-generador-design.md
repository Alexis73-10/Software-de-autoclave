# Spec — Puertas, modos descompresión, generador de códigos y perfil corrupto
**Fecha:** 2026-06-03

## Alcance

Cinco mejoras independientes identificadas en pruebas:

1. `AdvancedDoor` — desbloqueo sostenido hasta vacío de empaque
2. `EquipmentCapabilities` — límite de modos de descompresión por clase
3. Puerta motorizada — bloquear apertura si sensor de bloqueo activo
4. Generador de códigos — historial + lógica de reinstalación
5. Wizard de instalación — eliminar perfil bloqueado antes de reinstalar

---

## 1. AdvancedDoor — desbloqueo sostenido (biestable)

### Problema

En `_from_abriendo()`, `desbloquear_on()` se llama al inicio y se apaga en el segundo ciclo mediante el flag `_pulso_desbloqueo_enviado`. Para una válvula biestable, ese segundo pulso la devuelve al estado cerrado antes de que el empaque haya liberado presión.

### Comportamiento esperado

`desbloquear` permanece activo hasta que `presion_empaque() <= vacio_empaque`. Solo entonces se apaga. Esto garantiza que el empaque esté completamente desinflado antes de que el actuador de apertura empiece a mover la puerta.

### Cambios

**`advanced_door.py` — `_from_abriendo()`:**

- Eliminar la lógica que usa `_pulso_desbloqueo_enviado` para apagar `desbloquear`.
- Reemplazar por: mantener `desbloquear_on()` cada ciclo mientras `presion_empaque() > vacio_empaque`; llamar `desbloquear_off()` cuando `presion_empaque() <= vacio_empaque`.
- El flag `_pulso_desbloqueo_enviado` queda sin uso en `_from_abriendo()` pero se conserva — `_from_cerrando()` lo usa para asegurar que `desbloquear_on()` se envíe al menos una vez.

**`_from_cerrando()` — sin cambios.** Ya mantiene `desbloquear_on()` hasta que la puerta cierra físicamente.

### Invariante

`desbloquear` nunca debe apagarse mientras `presion_empaque() > vacio_empaque` durante apertura.

---

## 2. EquipmentCapabilities — modos de descompresión

### Contexto

Los modos de descompresión (0–5) no están implementados aún. Este cambio solo agrega la capacidad al dataclass para que esté disponible cuando se implementen.

### Cambio

Agregar campo `cooling_mode_max: int` a `EquipmentCapabilities` en `equipment.py`:

| EquipmentClass | cooling_mode_max |
|----------------|-----------------|
| MESA_N         | 1               |
| MESA_B         | 3               |
| MESA_B_LAB     | 5               |
| PISO           | 3               |
| PISO_LAB       | 5               |

- Sin campo nuevo en `InstallationProfile`.
- Sin UI nueva.
- Sin validación en `profile.py` (aún no hay selección de modo).

---

## 3. Puerta motorizada — bloquear apertura por sensor

### Contexto

`DoorType.MOTORIZED` y `DoorType.MOTORIZED_LOCKING` tienen motor pero su lógica de bloqueo no verifica el sensor `bloqueo_puerta_X`. `DoorType.ADVANCED` usa `presion_empaque` y no necesita este cambio.

### Cambios

**`factory.py` — `_build_door_cfg()`:**

Agregar clave `"bloqueo"` al `di` para `MOTORIZED` y `MOTORIZED_LOCKING`:

```python
has_mech_lock_sensor = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING)
if has_mech_lock_sensor:
    cfg["di"]["bloqueo"] = f"bloqueo_puerta_{n}"
```

**`advanced_door.py` — `cmd_abrir()`:**

```python
def cmd_abrir(self):
    if "bloqueo" in self.di:
        if self.estado.sensores_di.get(self.di["bloqueo"]):
            logger.warning("Puerta %s: bloqueada mecánicamente, apertura denegada", self.name)
            return
    self.set_state(DoorState.ABRIENDO)
```

`ADVANCED` nunca tiene `di["bloqueo"]` → el check queda implícitamente ignorado.

---

## 4. Generador de códigos — historial y reinstalación

### Base de datos

Archivo: `tools/generador/generador.db` (SQLite, creado automáticamente al iniciar la app).

```sql
CREATE TABLE IF NOT EXISTS codigos_generados (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    serial   TEXT NOT NULL,
    tipo     TEXT NOT NULL,   -- 'instalacion' | 'fabrica' | 'reinstalacion'
    fecha    TEXT NOT NULL,   -- ISO date YYYY-MM-DD
    usuario  TEXT NOT NULL
);
```

### Lógica de generación (`/generar` POST)

1. Buscar si el serial tiene algún registro `tipo IN ('instalacion', 'reinstalacion')`.
2. **Primera instalación** (sin registro previo):
   - Mostrar código de instalación + clave de fábrica.
   - Registrar `tipo='instalacion'`.
3. **Ya instalado** (existe registro):
   - Mostrar solo clave de fábrica.
   - Registrar `tipo='fabrica'`.
   - Mostrar botón "Solicitar reinstalación".
4. **Botón reinstalación** → POST a `/reinstalar`:
   - Mostrar código de instalación.
   - Registrar `tipo='reinstalacion'`.

### Historial visible

En la página `/generar`, bajo los códigos generados, mostrar tabla con los últimos registros del serial consultado (tipo, fecha, usuario) ordenados por fecha descendente.

### Inicialización

Al arrancar `app.py`, llamar a `init_db()` que crea el archivo y la tabla si no existen.

---

## 5. Wizard — eliminar perfil bloqueado antes de reinstalar

### Problema

`storage.save()` rechaza guardar si `profile.locked=True` y el archivo existe. Cuando el perfil está corrupto, el archivo existe pero es inválido → `bootstrap.py` devuelve `None` → se lanza el wizard → `save()` falla con RuntimeError.

### Cambios

**`storage.py` — nueva función:**

```python
def delete():
    INSTALLATION_FILE.unlink(missing_ok=True)
```

**`wizard.py` — función `instalar()`:**

Antes de `save(profile)`:

```python
storage.delete()
save(profile)
```

Safe en instalación nueva (el archivo no existe → `unlink(missing_ok=True)` no hace nada) y resuelve el caso de perfil corrupto o bloqueado sin lógica extra.

---

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/devices/puertas/advanced_door.py` | Items 1 y 3 |
| `src/autoclave/devices/factory/factory.py` | Item 3 |
| `src/autoclave/installation/equipment.py` | Item 2 |
| `src/autoclave/installation/storage.py` | Item 5 |
| `src/autoclave/installation/wizard.py` | Item 5 |
| `tools/generador/app.py` | Item 4 |

## Tests a escribir

| Item | Tests |
|------|-------|
| 1 | `test_desbloqueo_sostenido_hasta_vacio`: simular ciclos con presión alta → desbloquear activo; presión baja → desbloquear se apaga |
| 3 | `test_motorizada_bloqueada_no_abre`: `cmd_abrir()` con sensor activo → estado no cambia |
| 3 | `test_motorizada_desbloqueada_abre`: sensor inactivo → transiciona a ABRIENDO |
| 4 | Tests de lógica de DB: primera vez da código instalación, segunda vez solo fábrica, reinstalación da código instalación y registra como reinstalacion |
| 5 | `test_reinstall_overwrites_locked_profile`: save falla si no se llama delete antes; pasa si se llama delete |
