# Revisión de `planeacion_modo_fabrica.md` (v2) contra el código

Fecha: 22-nov-2026. Base: rama `dev` (f4a9aa9f), solo lectura. No se cambió código.
Rutas relativas a `src/autoclave/` salvo que se indique otra cosa.

Resumen: la spec es viable, pero la sección 3 tiene varias afirmaciones inexactas y hay seis puntos que obligan a cambiar el diseño antes de la Etapa 1:

1. El asistente se vuelve a ejecutar en equipos ya entregados (R-01).
2. No hay forma de cambiar la base en caliente (R-02).
3. Los cinco programas heredados reaparecen al borrarlos (R-03).
4. `mantenimiento_base.json` no se puede conservar (R-04).
5. La calibración «de fábrica» es otra cosa (R-05).
6. El respaldo USB no puede rechazar el paquete de liberación (R-06).

---

## 1. Correcciones a la sección 3 («Lo que hay hoy»)

| Afirmación de la spec | Real | Evidencia |
|---|---|---|
| `db_manager.py` crea las 14 tablas | Crea 12. `cycle_params_audit` y `sensor_calibration_audit` las crea cada una su clase, con conexión propia. La primera solo se instancia desde la UI PySide antigua y la segunda ya no recibe escrituras. | `services/domain/logging/cycle_params_audit.py:9,25`, `sensor_calibration_audit.py:9,30`, `backend/context.py:674`, `backend/rutas/io.py:195` |
| Triggers de solo anexar en 5 tablas | Correcto. Lista: `audit_log_sin_update/_sin_delete`, `mantenimientos_sin_update/_sin_delete`, `operadores_sin_delete`, `usuarios_sin_delete`, `catalogo_carga_sin_delete`, y 5 triggers de cuentas del sistema y borrado lógico (`usuarios_cuenta_sistema_protegida`, `_marca_sistema_inmutable`, `_marca_sistema_solo_semilla`, `_eliminado_irreversible`, `_sistema_no_se_elimina`). Con `recursive_triggers = ON`, un REPLACE dispara los DELETE. No hay ningún `DROP TRIGGER` en `src/`. | `db_manager.py:238-470, 668` |
| Esquema | `ESQUEMA_VERSION` = 15. La tabla nueva sería la migración v16. | `db_manager.py:549-567` |
| Semillas | Se crean al arrancar, no en una migración. El orden es tablas base → `_migrate` → v1..v15 → `seed_admin_if_empty`. Solo se crean si `usuarios` está vacía, con `debe_cambiar_clave=1` y `cuenta_sistema=1`. | `db_manager.py:670-672, 2094-2110` |
| El asistente escribe `equipo_instalado` (la spec propone escribir `estado_fabrica` «en la misma transacción») | No la escribe una ruta del backend: la escribe el proceso QML del asistente, sin backend. Cada paso abre su propio `DbManager` y hace su propio commit: `fijar_contrasenas`, luego el perfil, luego `registrar_equipo_instalado`. Si esta última falla, solo queda en el log y la instalación sigue. | `ui_qml/bridge/puente_instalacion.py:328-350, 463-488`, `exe_unico.py:414-437` |
| `cycles/defecto/` con `CycleManager.defecto(n)` | La carpeta no existe en el repo y se crea solo al duplicar. Los defectos se indexan **por el `cycle_number` del contenido**, no por el nombre del archivo. Solo se usan para la columna «defecto» y la marca «modificado» de la pantalla, y para arrastrar el tipo de carga. | `core/managers/cycle_manager.py:994-1012, 1055-1058`, `core/managers/gestion_programas.py:141-149`, `backend/rutas/programas.py:203-222` |
| (Implícito en D-08 y P-03) «Restaurar valores de fábrica» de un programa | **No existe** ninguna ruta ni botón para eso. Es funcionalidad nueva y la spec no la lista como tal. | — |
| Número del programa | La clave en el JSON es `cycle_number`; `numero` es solo el nombre en la API. | `backend/rutas/programas.py:66` |
| Calibración: `"defecto"` = neutro 1,0 / 0,0 | Es neutro solo en la sección `user` del YAML. La sección `factory` (curva cruda → unidad, 4–20 mA → 0–400 kPa) nunca se toca, es común a todos los equipos y ningún endpoint la escribe. | `backend/rutas/io.py:352-391`, `config/calibration_modbus.yaml` |
| `mantenimiento.json` («se reinicia, contadores en cero») | Es **configuración** (`intervalo_dias`, `intervalo_ciclos`). Los mantenimientos hechos están en la tabla `mantenimientos`. | `core/runtime/servicio_mantenimiento.py:86-93` |
| `mantenimiento_base.json` («se conserva si es configuración») | No es configuración ni registro: guarda `{"ciclos_instalacion": N}`, el contador de ciclos al instalar, que se fija una sola vez. | `servicio_mantenimiento.py:156-177` |
| `ciclo_contador.json` | Al arrancar toma `max(contador, MAX(numero_ciclo))`. Con la base nueva vacía y el archivo en 0, queda en 0. | `core/runtime/contador_ciclos.py:84-92`, `backend/context.py:1119` |
| Tickets, PDFs y cola de correo en `datos\` | Los tickets van a la cola de la impresora y no se guardan. Los PDF se generan en un directorio temporal y solo se envían. **No existe cola de correo.** Nada de eso queda en disco. | `backend/rutas/_comun.py:166`, `ui_qml/bridge/acciones_ciclos.py:355,426,537` |
| Logs | Están en dos carpetas: `datos\data\` (`lanzador.log`, `ui_puerta{N}.log`, `backend.log`, `ajustes.log`, `asociar_tactiles.log`, `configurar_modulo.log`) y `datos\logs\autoclave.log`. Además, `installation_profile_cambios.log` (junto al perfil) y `datos\estacion\estacion.log`. El «log de desarrollo» no es un archivo aparte: termina en `backend.log` y `autoclave.log`. | `exe_unico.py:86,369,383,549-575`, `backend/main.py:25`, `utils/logging.py:9,15` |
| `autoclave.db.bak*` | No existen. Lo que sí existe es `autoclave.db.corrupta-<fecha>` (con `-wal`/`-shm`) y la marca `BD_BLOQUEADA`. | `db_manager.py:587-606` |
| Perfil en `data/` | `installation_profile.json` está en la raíz de datos. No hay archivo de licencia: los códigos se verifican y no se guardan. | `installation/storage.py:13`, `installation/activacion_v2.py:7` |
| Respaldo USB: «ya resuelve escritura y espacio» | Detecta la USB con `psutil` (`removable`), pero no prueba la escritura antes (un fallo da 503 `usb_no_escribible`) y **no valida** el espacio, solo lo informa. | `core/runtime/respaldo.py:187-202`, `backend/rutas/respaldo.py:204-210` |
| Archivos de `data/` que la spec no menciona | `login_recordado.json` (guarda usuarios de las pruebas), `backend.pid`, `correo_equipo.json`, `impresora.json`, `idioma.json`, `unidades.json`, `tema.json`; además `programa\autoclave\config\correo.json`. | Informe del explorador 3 |

---

## 2. Hallazgos nuevos que cambian el diseño

**R-01 (crítico, afecta a FAB-03 y D-14). El asistente vuelve a correr en equipos entregados.**
- El asistente se ejecuta siempre que falte el perfil o sea inválido (ARR-06). Ejemplos: un sello de automatización que no verifica, o un perfil borrado. Pasa también en equipos ENTREGADO, y ahí se usa un código `REI`/`REIA`.
- Si «terminar el asistente» escribe FÁBRICA, un equipo en campo vuelve a FÁBRICA, que es justo lo que FAB-03 quiere impedir.
- Propuesta: escribir FÁBRICA solo con un código de primera instalación (`INS`/`INSA`, o v1 de instalación) y solo si la base no tiene ya `estado_fabrica = ENTREGADO`. Con un código `REI`/`REIA`, el estado queda en ENTREGADO aunque la base sea nueva.
- Añadir una prueba P-xx: perfil borrado, reinstalación con REI → ENTREGADO.

**R-02 (alto, afecta a 6.2 pasos 5–7). No se puede reemplazar la base en caliente.**
- `DbManager` mantiene una sola conexión compartida (WAL, `synchronous=FULL`). La usan además los hilos `EscritorBD` (CycleLogger) y `HistorialAlarmas`, y `SensorCalibrationAuditDB` tiene su propia conexión.
- No existe ningún mecanismo para cerrarlas todas. En Windows no se puede renombrar un archivo abierto (`db_manager.py:674-675`, `cycle_logger.py:158-190`).
- Además, `etapa_cierre` vive *dentro* de la base que se va a reemplazar.
- Propuesta: el cierre deja la base nueva como `autoclave.db.nueva` y una marca **fuera** de la base, por ejemplo `datos\data\cierre_fabrica.json` con la etapa y los hashes, y reinicia. Al arrancar, antes de abrir ningún `DbManager`, se lee la marca y se hacen los pasos 6–9 sin conexiones abiertas. Así desaparece el problema de los handles y la reanudación de 6.3 queda en un solo lugar.
- Como precondición, el cierre se rechaza en modo sin base o con `BD_BLOQUEADA`.

**R-03 (alto, afecta a D-06 y D-07). Los cinco programas heredados reaparecen al borrarlos.**
- `_soltar_fabrica_sin_copia_de_usuario` exime a los 5 programas de fábrica anteriores a Prion. Si se borra B&D de `cycles/user/`, su copia de `factory/` se sigue cargando con el número 1 (`cycle_manager.py:1060-1074`).
- `fabrica_vistos.lst` no sirve para esto: ya contiene los 6 ids desde la siembra, así que no distingue un programa borrado de uno visto.
- Hace falta una lista propia de borrados en FÁBRICA, por ejemplo `cycles/user/fabrica_borrados.lst`, que el cargador respete también para los heredados.
- Además, el borrado actual rechaza los programas de fábrica (422 `programa_de_fabrica`), siempre registra el número en `numeros_usados.json` y solo borra el defecto si el archivo se llama `programa_N.json` (`gestion_programas.py:167-196`). Hay que escribir una ruta nueva, no adaptar esta.

**R-04 (medio, afecta a D-10). `mantenimiento_base.json` debe volver a 0, no conservarse.**
Si el contador de ciclos vuelve a 0 y `ciclos_instalacion` queda en N, el cálculo de ciclos desde el último servicio da negativo o se desfasa. En el `data/` de desarrollo ya se ve el caso: `ciclo_contador` en 0 y `ciclos_instalacion` en 79. En cambio, `mantenimiento.json` (los intervalos) sí se conserva, al revés de lo que dice 6.4.

**R-05 (medio, afecta a FAB-08). Qué es la «calibración de fábrica del equipo».**
- Lo propio de cada equipo es la sección `user` del YAML (ganancia, offset, `poly` y los puntos `shown`/`real`). La sección `factory` es común y no cambia.
- `calibracion_fabrica_equipo.yaml` debe guardar la sección `user` vigente, y «defecto» debe restaurar esa sección.
- Ojo con la reasignación de E/S: «ultimo» ya descarta registros de otro puerto (`io.py:385`). La copia del equipo tiene que ir por función de sensor y no por puerto, o invalidarse cuando se reasigna.

**R-06 (medio, afecta a la sección 7). El manifiesto USB no tiene campo «tipo».**
- Hoy la validación solo rechaza `formato != 1`, otra serie u otra versión mayor (`core/runtime/respaldo.py:130-139`). Un paquete de liberación con el mismo formato pasaría.
- Hay que agregar `tipo` al manifiesto. Un manifiesto sin `tipo` se trata como «respaldo», para no romper los respaldos que ya existen. La restauración rechaza `tipo != "respaldo"`, y `/backup/restore` ignora además la carpeta `Especifika_liberaciones`.

---

## 3. Otros puntos (menores)

- **Semillas y P-06.** Construir la base nueva con `DbManager(ruta_nueva)` ya deja `Admin`/`Ingeniero` con la contraseña semilla y `debe_cambiar_clave=1`: es la opción a) sin código extra. Para la opción b) basta con `fijar_claves_instalacion` sobre la base nueva, que no escribe en la bitácora. No hay que copiar filas de usuarios: los triggers `_marca_sistema_solo_semilla` y `_cuenta_sistema_protegida` lo impedirían.
- **Base nueva incompleta.** `DbManager` no crea `cycle_params_audit` ni `sensor_calibration_audit`. Hay que crearlas al construir la base, o aceptar que nazcan cuando se instancien sus clases.
- **Atomicidad del paso 4.** `registrar_auditoria_lote` solo agrupa filas de `audit_log`, y cada método de `DbManager` hace su propio commit. Para que `system_params`, `estado_fabrica` y la fila de bitácora queden en una sola transacción hace falta una transacción propia. Con el enfoque de R-02 importa menos: si falla, se descarta el archivo `.nueva`.
- **Evento nuevo.** `equipo_liberado_fabrica` tiene que estar en `core/runtime/bitacora.py`, con su categoría. Si no, se registra con el aviso de «evento desconocido».
- **Numeración (FAB-09 / P-07).**
  - `numero_nuevo()` hoy asigna mayor + 1 sobre programas, fábrica, defectos y `numeros_usados.json`, sin reservar ningún rango ni poner tope. Con el máximo actual en 6, un duplicado en campo recibe el 7, dentro del rango de fábrica.
  - La siembra de PRI-05 también consulta `numeros_usados.json`. Si el cierre vacía ese archivo (paso 9), la siembra futura podría reutilizar un número de usuario retirado. Conviene vaciar solo los números del 1 al 10.
  - Hoy no existe ningún tope de 10 programas.
- **Marca `fabrica_equipo`.** Nadie la lee. Hay que tocar `_load_from_folder` y las reglas de editable (`source == "user"`) y borrable (`personalizado`).
- **Defecto por número.** `cycles/defecto/<id>.json` sirve si el contenido lleva `cycle_number`. Pero un defecto con número 1–6 tapa al genérico de ese número, y la migración T29-05 (`_modo_solido_fabrica`, `cycle_manager.py:1014`) sigue leyendo el `factory/` original. Hay que decidir cuál manda.
- **Restaurar parámetros.** Hoy es de a una clave (`POST /global_params/{clave}/reset`). Al cargar `parametros_fabrica_equipo.json`, hay que validar la coherencia de límites (suministro < alivio ≤ fondo) igual que `ConfigManager`.
- **`historial.db` del paquete.** Verificar que la exportación actual (`_conn.backup`, `rutas/respaldo.py:134-145`) anule `hash_pw` dentro de la copia; `usuarios.json` ya va sin hashes. `codigo_creacion` también debería ir en NULL.
- **Borrado en 6.4.** Faltan `login_recordado.json`, `backend.pid`, `*.corrupta-*`, `datos\logs\` e `installation_profile_cambios.log` (decidir si se borra: registra los cambios de perfil durante las pruebas). Sobran los tickets, los PDF, la cola de correo y `autoclave.db.bak*`, que no existen.
- **«Cámara sin presión» (6.1).** Conviene definirla como `camara_segura.motivos()` vacío con datos vigentes, el mismo criterio de NO ABRIR, en lugar de un umbral nuevo.
- **Regla «nunca se borra un respaldo».** Está en `core/runtime/respaldo_ciclos.py:23` (comentario), no en CLAUDE.md. La excepción de FAB-10 se documenta ahí.

---

## 4. Problemas de redacción de la spec

- Las preguntas de la sección 11 y las pruebas de la sección 10 usan el mismo prefijo `P-`. En la sección 9, «Verificación: P-05, P-06» se puede leer como prueba o como pregunta (P-06 es ambas). Propuesta: renombrar las preguntas a `PA-xx`.
- Las preguntas saltan de P-04 a P-06 (no hay P-05).
- FAB-04 se menciona como «reemplazada» en FAB-07, pero ya no aparece en la lista.

---

## 5. Lo que la Etapa 0 ya no necesita averiguar

| Pregunta de la Etapa 0 | Respuesta |
|---|---|
| Cola de correo, tickets y PDFs | No quedan en disco. |
| Logs | Ubicados (tabla de la sección 1). |
| `mantenimiento_base.json` | Contador de ciclos al instalar: se reinicia (R-04). |
| Orden de triggers y semillas | Tablas → migraciones (tablas y triggers) → semillas, todo en el constructor de `DbManager`. |
| Handles de SQLite | No hay mecanismo de cierre: propuesta en R-02. |

Contradicciones con la spec: secciones 1 a 3 de este informe.
