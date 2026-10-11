# Planeación — Backend de parámetros del sistema

**Proyecto:** Software de Autoclave (Especifika S.A.S.)
**Estado:** borrador v1 — depende de `planeacion_backend_autenticacion.md` (tareas T-4 a T-7 antes de la fase 2)
**Ubicación sugerida:** `docs\mis_plans\planeacion_backend_parametros.md`
**Documentos relacionados:** `planeacion_opciones.md` (secciones 3.2, 3.9, 5 y 10), `planeacion_backend_autenticacion.md`

---

## 1. Objetivo

Pasar los parámetros del sistema de un JSON de solo lectura a un almacén editable, validado, auditado y aplicable sin reiniciar, y construir sobre eso la bitácora general, la calibración atmosférica y las entradas mostradas por programa.

## 2. Estado actual (según el informe de Code)

| Hecho | Detalle |
|---|---|
| Almacén | `src/autoclave/config/global_params.json`, forma `{"value","type","unit","min"?,"max"?}`. |
| Carga | `ConfigManager.load_config()/get()` (`core/managers/config_manager.py:10-25`), una sola vez al arrancar (`context.py:32-34`). Sin guardado, sin lock. |
| API | Solo `GET /global_params` (`server.py:203`). |
| Validación | Mín/máx informativos, sin aplicar. |
| Respaldos en código | `or 101.3`, `or 20.0` y otros convierten 0 en el valor por defecto (OPC-13). |
| Copias al arrancar | `ServicioPuertas.__init__` (`ser_puertas.py:42-44`) y `preparado_state.__init__` (`preparado.py:18`). Se crean una vez; hoy exigen reiniciar. |
| Lectura en vivo | `base_fase`, `protocolo_fallo`, `ciclo.py`, `preparacion.py`, el resto de `preparado.py`, `advanced_door.py` y `cycle_logger.py`. |
| Caché UI | `/global_params` cada 25 × 200 ms = 5 s (`ui_service_backend.py:20`). |
| Auditoría existente | `cycle_params_audit` y `sensor_calibration_audit`, cada una con su clase y su conexión. No existe `audit_log`. |
| Migraciones | `_migrate()` aditiva con `try/except`, sin versión. |

## 3. Decisiones aprobadas

1. Los parámetros pasan a una tabla en la base de datos. El cambio y su registro de auditoría van en una sola transacción. El JSON actual queda como archivo de valores de fábrica.
2. Se aplican en memoria al guardar, sin reiniciar. Guard de estado unificado: cualquier estado distinto de CICLO. El ingeniero puede cambiar parámetros de ciclo y calibración en CICLO según la sección 5.8 de la spec de autenticación. La escritura modifica el mismo objeto de configuración, nunca lo reemplaza.
3. Un temporizador ya armado conserva su valor. El nuevo valor aplica al siguiente.
4. La UI invalida la caché de `/global_params` al guardar.
5. Tabla general `audit_log`. Las tablas viejas quedan como históricas, sin migrar. La auditoría de parámetros de ciclo pasa al backend.
6. `PRAGMA user_version` con migraciones numeradas.
7. Sin migración de datos de `lecturas_grafica`, sin compatibilidad con claves antiguas y sin adaptador, porque el software no está instalado en ningún equipo.
8. Nombres canónicos de entradas: los del mapa de ejecución (`temp_ref`). Las claves cortas de `/status` quedan como presentación de la API. Un único módulo de traducción cubre YAML, `/status` e índices.
9. Los documentos históricos se dejan como registro. Se actualizan solo los vigentes.
10. Se elimina `git_autocommit`: no es un respaldo. La trazabilidad la da `audit_log`.

## 4. Almacén de parámetros

### 4.1 Tabla `system_params`

| Columna | Tipo | Notas |
|---|---|---|
| `clave` | TEXT, PK | clave en código (ver `planeacion_opciones.md` 3.2) |
| `valor` | TEXT | serializado según `tipo` |
| `tipo` | TEXT | `int` o `float` |
| `unidad` | TEXT | |
| `minimo`, `maximo` | REAL, nulos permitidos | sin rango en parámetros no editables |
| `defecto` | TEXT | copia del valor de fábrica |
| `editable` | INTEGER | 0 para `presion_atmosferica` |
| `actualizado_por` | TEXT | usuario del token |
| `actualizado_en` | TEXT | marca de tiempo del reloj de pared para el registro |

### 4.2 Arranque
1. Si la tabla no existe, se crea y se siembra desde el JSON de fábrica.
2. En cada arranque se valida que todas las claves esperadas existan. Si falta una, el arranque falla con alarma. No hay valor de respaldo.
3. Se carga todo al `ConfigManager`.

### 4.3 `ConfigManager`
- `threading.RLock` para lectura y escritura (OPC-12).
- `get(clave)` sin `or` ni valor de respaldo (OPC-13). Un 0 es un valor válido.
- `set(clave, valor, usuario, rol)`: valida tipo y rango, abre transacción, escribe `system_params`, escribe `audit_log` y, si ambas tienen éxito, modifica `self.config` en el mismo objeto.
- Un fallo en cualquier punto revierte todo y deja el valor anterior en memoria.

### 4.4 Reglas de validación
- Tipo exacto: un parámetro `int` rechaza decimales.
- Mínimo y máximo inclusivos. Los rangos son los de `planeacion_opciones.md` 3.2.
- Reglas entre parámetros: ninguna en V1.
- Parámetro no editable (`presion_atmosferica`): rechazo con 403, sin importar el rol. Solo lo escribe la calibración atmosférica por una función interna.

## 5. Endpoints

| Endpoint | Rol | Guard | Descripción |
|---|---|---|---|
| `GET /global_params` | sin token | — | Lista de parámetros con valor, unidad, mín, máx, defecto, usuario y fecha de la última modificación. |
| `PATCH /global_params/{clave}` | técnico, ingeniero | distinto de CICLO | Cambia un valor. Devuelve el valor guardado. |
| `POST /global_params/{clave}/reset` | técnico, ingeniero | distinto de CICLO | Restaura el valor de fábrica. |
| `GET /audit_log` | todos los roles con token | — | Consulta con filtros (fecha, usuario, evento, entidad) y paginación. |

Códigos: 401 sin token, 403 rol insuficiente o parámetro no editable, 409 estado no permitido o calibración en curso, 422 valor inválido con motivo.

## 6. Lectura en vivo (OPC-11)

1. `ServicioPuertas` deja de copiar `temp_max_apertura`, `presion_atmosferica` y `rango_presion_atm` en `__init__` y los lee con `config.get` en cada uso.
2. `preparado_state` deja de copiar `tiempo_estable_alarma`.
3. `advanced_door`: `timeout_puerta` se lee al armar el temporizador, y el temporizador conserva el valor.
4. Es condición para que la calibración atmosférica tenga efecto real en la lógica de apertura de puerta.

## 7. Bitácora `audit_log`

| Columna | Notas |
|---|---|
| `id` | PK |
| `ts` | reloj de pared (registro), no `monotonic` |
| `usuario`, `rol` | del token |
| `evento` | código estable. Los de autenticación están en la spec de autenticación (5.10); esta spec añade `param_sistema_cambio`, `calibracion_atm_ok`, `calibracion_atm_abortada`, `suspension_entra` y `suspension_sale` |
| `entidad` | clave afectada |
| `valor_anterior`, `valor_nuevo` | texto |
| `detalle` | JSON opcional: ciclo, fase, programa, `aplica` (`actual`/`siguiente`), muestras, dispersión, motivo de aborto o rechazo |

- Eventos mínimos: los de `planeacion_opciones.md` 3.9.
- Las tablas viejas se mantienen. El visor del endpoint las une con una consulta, sin tocar sus filas.
- La auditoría de parámetros de ciclo la escribe el backend, que recibe el usuario del token. El cliente PySide deja de escribirla.

## 8. Calibración atmosférica en el backend

Funcional completo en `planeacion_opciones.md` sección 5. Requisitos del backend:
- Tarea del backend con flag `calibracion_en_curso`, expuesto en `/status`, que bloquea las escrituras de configuración.
- Endpoints: `POST /maintenance/atm-calibration/start` y `POST /maintenance/atm-calibration/cancel`. Rol técnico e ingeniero.
- Ventana de 120 s con `time.monotonic()`, muestreo cada 5 s.
- Aborta ante pérdida de precondición, lectura inválida o cancelación, y conserva el valor anterior.
- Al terminar con éxito escribe `presion_atmosferica` mediante la función interna y registra en `audit_log`.

## 9. Entradas mostradas y gráfica

### 9.1 Almacenamiento
- Tabla `ciclo_entradas_mostradas` (programa, posición 1 a 3, entrada): la selección de cada programa. Se eligen entre las 10 entradas del mapa de ejecución hasta que se conecte `io_enabled` (OPC-15).
- Al iniciar un ciclo se guarda en `ciclo_entradas_seleccion` la selección vigente (ciclo, posición, entrada), para que el historial muestre lo que se ejecutó.
- `lecturas_grafica` pasa a `(ciclo_id, t, entrada, valor)`. Se guardan todas las entradas habilitadas y se filtra al mostrar.
- La tabla vieja se elimina sin migrar datos.

### 9.2 Impacto (según el informe de Code, punto 8)
- Backend: `db_manager` (esquema, `insertar_lectura_grafica`, `get_lecturas_grafica`), `cycle_logger.py:316-320`, `/cycle/current/graph` y `/cycle/history/{id}/graph` (hoy arman 3 claves a mano).
- QML: `progreso_ciclo.py`, `ciclo_en_curso.py` (`_SERIES`), `GraficaCiclo.qml` (claves, textos y colores fijos), `ciclos_historial.py`, `DetalleCiclo.qml`, `MenuPrincipal.qml`, `resumen_sistema.py`.
- PDF y correo: `acciones_ciclos.py:367-372`, `pdf_ciclo.py:30-32,280`.
- Simulador: `servidor.py`, `repeticion.py`. Pruebas QML y los tests listados en el informe.
- No dependen: ticket (`lecturas`), `pdf_resumen`, `pdf_consolidado` y la gráfica de PySide.

### 9.3 Nombres
Módulo único `io_names` con la tabla de equivalencias entre YAML, mapa de ejecución, claves de `/status` e índices. Los nombres de la nueva gráfica son los del mapa de ejecución.

## 10. Migraciones

1. `PRAGMA user_version` y la migración v1 (solo `audit_log`) los introduce la spec de autenticación (T-21). Esta spec añade la migración v1 → v2, que hace:
   - crear `system_params`;
   - crear `ciclo_entradas_mostradas` y `ciclo_entradas_seleccion`;
   - recrear `lecturas_grafica` con el esquema nuevo (sin copiar datos).
2. Cada migración es una función numerada, atómica (una transacción) y registra su versión al terminar.
3. `cycle_params_audit` y `sensor_calibration_audit` conservan su creación actual, sin cambios.

## 11. Renombres y limpieza

| Cambio | Detalle |
|---|---|
| `presion_admosferica` → `presion_atmosferica` | Código: `advanced_door.py`, `ser_puertas.py`, `base_fase.py`, `protocolo_fallo.py`, `ciclo.py`, `preparacion.py`, `preparado.py`, `cycle_window.py` y los tests listados en el informe. |
| `intervalo_imprecion_esterilizacion` → `intervalo_impresion_esterilizacion` | `global_params.json:13`, `cycle_logger.py:73`. Sin tests. |
| Eliminar `temp_max` y `tipo_puerta` | Solo del JSON. **No** se tocan `ui_qml/assets/textos/es.json:211` ni `info_equipo.py:84` (etiqueta y `profile.door_type`). |
| Respaldos en código | Se eliminan todos (`or 101.3`, `or 20.0`, defectos de `cycle_logger`, `MINUTOS_DEFECTO` de `standby.py`). |

El renombre es directo, sin compatibilidad con claves viejas, y va en **un solo commit mecánico** de buscar y reemplazar, separado de la lógica nueva. Documentos vigentes que se actualizan: `catalogo_alarmas.md` y `planeacion_opciones.md`. Los INFORME_* y los planes antiguos de `docs/superpowers` se dejan como registro, con una nota de consistencia.

## 12. `time.monotonic()` (OPC-08)

Alcance aprobado:
- `advanced_door.py:350,353,554,557` (espera de 0,3 s) y `:372,416,461,514` (`timeout_puerta`).
- `devices/buzer/buzer.py:23,37`.
- `cycle_logger.py:362` (intervalo de impresión) y `:229,375` (`timestamp_rel` del ticket).

Fuera de alcance: `cycle_window.py` y `cycle_buffer.py` (PySide, solo visual) y el arranque (`main.py`). Las marcas de tiempo de registros (`audit_log`, columnas `actualizado_en`) siguen usando el reloj de pared.

## 13. Orden de implementación

| Fase | Contenido | Verificación |
|---|---|---|
| 0 | Spec de autenticación (T-1 a T-8) | criterios de aceptación de esa spec |
| 1 | Migración v2 (`system_params`, entradas mostradas, `lecturas_grafica`), `ConfigManager` con lock y `set()` | pruebas de transacción, rollback y rangos |
| 2 | Endpoints de parámetros, lectura en vivo de `ServicioPuertas` y `preparado_state`, corrección de `time.monotonic()` | pruebas por estado, rol y rango |
| 3 | Renombres y limpieza (un solo commit mecánico) | tests existentes en verde |
| 4 | Calibración atmosférica | pruebas con simulador, aborto en cada precondición |
| 5 | Entradas mostradas y gráfica | verificación visual en QML, PDF y correo |

Cada fase termina con verificación visual de Cristian antes de commitear.

## 14. Criterios de aceptación

1. Cambiar un parámetro fuera de CICLO lo aplica sin reiniciar y registra en `audit_log` usuario, rol, valor anterior y nuevo, en una sola transacción.
2. Un fallo al escribir `audit_log` revierte el cambio de parámetro.
3. Un valor fuera de rango o de tipo incorrecto devuelve 422 y no cambia nada.
4. Con ciclo en curso o calibración en curso, la escritura devuelve 409.
5. Un valor 0 válido (por ejemplo, suspensión desactivada) no se convierte en el valor por defecto.
6. Si falta una clave al arrancar, el arranque falla con alarma.
7. Un cambio de `rango_presion_atm` o de `presion_atmosferica` afecta a la lógica de apertura de puerta sin reiniciar.
8. `presion_atmosferica` rechaza cualquier edición manual, con cualquier rol.
9. Cada ciclo guarda su selección de entradas y el historial lo muestra con esa selección.

## 15. Pendientes

| Id | Pendiente |
|---|---|
| **P-9** | Spec de perfil de equipo (`io_enabled`). |

Decidido: el renombre de claves (fase 3) va después de unir la rama `alarmas-parte-a`, que está por terminar. `temp_chaqueta` se elimina del mapa de ejecución (`status.py`), porque se retiró de todos los equipos (pendiente R-9 de la spec de autenticación).
