# Planeación: endurecimiento del backend para edición de parámetros del ciclo

> **Adenda 2026-10-14 (tanda, T10):** prevalece la instrucción de la tanda. D-1 queda como "estado distinto de CICLO + excepción del ingeniero" (guard ya vigente); identidad por token (spec de autenticación v7, sustituye RB-02); auditoría en `audit_log` (sustituye las columnas nuevas de `cycle_params_audit`, RB-03.2). Implementado en T10: catálogo `core/managers/catalogo_parametros.py` con los límites de §1.6 (tabla en `docs/informes/limites_catalogo.md`), tipos estrictos, programa dañado al cargar con recuperación desde `.bak`, `globals.tipo_carga` (solido|liquido) con la regla líquido → modo 4/5, auditoría atómica (sin registro se revierte, 503 `BASE_OCUPADA`), `.bak` al escribir, `valor_anterior_esperado` opcional (409 `VALOR_CAMBIO`), triggers de solo anexar en `audit_log` (v4) y PATCH /cycle/parameter para técnico+ingeniero. No implementado: `_param_lock` separado (el guard bajo `_sm_lock` ya impide aplicar un cambio después del inicio), directorio de datos persistente para `cycles/user` (RB-04.5) y timeout de 5 s en los clientes PySide (RB-09; esas vistas ya no envían token y se retiran en la Fase 5).

Estado: BORRADOR, revisión 3 (corregida con `INFORME_VERIFICACION_SPECS_PARAMETROS_SENSORES.md`). Pendiente de aprobación de Cristian. No hay código escrito ni se debe escribir hasta que este documento sea aprobado.
Ubicación prevista: `docs\mis_plans\planeacion_endurecimiento_backend_parametros.md`
Fuente de los hechos: los tres informes de Claude Code (2026-10-02, rama `dev`, HEAD `960647f`). Las referencias `archivo:línea` deben verificarse al implementar; varias líneas de `server.py` cambiaron por trabajo sin commit.
Norma de referencia: IEC 62304 Clase C, ISO 14971.

---

## 1. Propósito y alcance

Hoy cualquier cliente puede cambiar parámetros de un programa de ciclo en cualquier estado de la máquina, sin identidad verificable, con auditoría escrita por la UI y con escritura de archivo no atómica. Este documento especifica el endurecimiento del BACKEND (rutas de escritura de parámetros y su persistencia) para que sea seguro construir encima la interfaz de Opciones.

Es la primera de tres especificaciones: (1) esta; (2) `planeacion_sensores_ciclo.md`; (3) `planeacion_opciones_parametros_ciclo.md` (pantallas QML, pendiente).

Hallazgos que cubre: OPC-01, OPC-02 (parcial), OPC-03, OPC-04, OPC-05, OPC-12, OPC-17, OPC-18, OPC-19, OPC-22, OPC-23, OPC-26, OPC-27, OPC-28, OPC-30, OPC-34, OPC-35, OPC-37.
Fuera de alcance: interfaz gráfica, roles de sensor, valores por defecto y asterisco, cambios en la lógica de las fases, flujo de FALLA y reset (OPC-24), interlock de puertas con sensor `None` (OPC-25).

---

## 2. Decisiones adoptadas

- D-1. La edición de parámetros solo se permite con el estado global PREPARACION o PREPARADO (lista blanca). Se bloquea en CICLO (incluida la espera de confirmación del operador y cualquier `FALLO_*` interno), FALLA y cualquier otro estado. Hoy ningún código lleva el estado global a EMERGENCIA ni a HIBERNACION (OPC-24); la lista blanca los cubriría si se agregan. Aplica a todos los programas, no solo al activo.
- D-2. Pueden editar `biomedico`, `tecnico` e `ingeniero`. No pueden `admin` ni `operador`. Matriz fina por rol pendiente en el plan de roles.
- D-3. La auditoría la escribe el backend. Se registra el login, el nombre, el rol y la fecha con segundos. No se pide motivo.
- D-4. Control de concurrencia optimista: el cliente envía el valor anterior que cree vigente; si no coincide, el backend rechaza (409).
- D-5 (ampliada). El valor 0 se prohíbe, con mínimo del catálogo mayor que 0 (o el mínimo físicamente válido que apruebe Cristian), en: (a) todo parámetro leído con `or <constante>` (Anexo A.1); (b) los parámetros leídos con `default=` en los que 0 produce bloqueo, FALLO o desactiva una protección (Anexo A.2). Los mínimos concretos se proponen en el Anexo B y los aprueba Cristian. Los valores vigentes de los cinco perfiles ya cumplen cualquier mínimo mayor que 0. No se modifica la lógica de las fases.
- D-6. Catálogo de parámetros en código con límites de seguridad no editables; el rango del JSON solo puede restringir el del catálogo.
- D-7. Un programa de usuario se edita sobre su archivo en el directorio de datos persistente (D-10). Los perfiles de fábrica son inmutables.
- D-8. En esta fase la identidad la declara el cliente y el backend la registra como no verificada. El token de sesión se especificará aparte, con prioridad alta.
- D-9. El backend escucha solo en `127.0.0.1` y se corrigen los comentarios que describen una topología de dos PC (`backend/main.py:29`, `main.py:232`), porque todos los clientes usan `127.0.0.1` fijo y el código no soporta esa topología (OPC-35). Si algún día la puerta 2 va en otro equipo, se reabre con una especificación de red.
- D-10. Los perfiles de usuario residen en un directorio de datos persistente: `app_root()/data/cycles/user/`, sembrado desde el paquete la primera vez (mismo patrón que `calibration.yaml`, `utils/paths.py:25-42`). El backend es el único lector y escritor; las demás UIs (PySide y QML) obtienen los programas por HTTP, nunca desde disco (OPC-34).
- D-11. Se permite editar el programa activo en PREPARACION y PREPARADO con efecto inmediato (OPC-19). Con D-5 aplicado a `globals.presion_chaqueta` y `globals.rango_presion_chaqueta` desaparece la doble semántica de 0 entre CICLO y PREPARACION/PREPARADO (OPC-28).
- D-12 (revisada). `PATCH /cycle/parameters` tiene un cliente activo, `SecadoView` (OPC-27). Se conserva como envoltorio fino del servicio único (RB-08), con todos los requisitos de este documento; `SecadoView` deja de editar sin auditoría y se retira junto con la vista cuando Secado migre a QML.
- D-13. La auditoría es estrictamente de solo anexar, sin procedimiento de depuración.
- D-14. `cycle_params_audit` conserva `usuario` con el significado actual (nombre completo, valores históricos mixtos) y agrega `usuario_login`. Las filas nuevas llenan ambas columnas; las consultas comparan por `usuario_login` cuando existe (OPC-37).
- D-15. Los clientes de escritura usan un timeout mayor (propuesta: 5 s) y tratan un timeout como resultado INCIERTO: recargan el valor del backend antes de informar éxito o fallo (OPC-26).

---

## 3. Estado actual relevante (verificado)

- `PATCH /cycle/parameter` (`server.py:673-696` con el trabajo sin commit actual): valida programa, ruta y rango del JSON; no verifica rol ni estado; no audita; edita cualquier programa cargado, incluido el activo; persiste solo si `source == "user"`.
- `PATCH /cycle/parameters` (`server.py:622-663`): solo sección `secado`; tabla de rangos propia que admite 0 en presiones; asigna parámetro por parámetro, de modo que un fallo a mitad deja cambios parciales (OPC-12). Cliente: `SecadoView` (`ui_pyside/views/secado.py:126-135`).
- El `Cycle` editado es el mismo objeto que usa la máquina de estados; `set_param` muta la hoja en sitio. Un cambio actúa en el tick siguiente.
- `_sm_lock` es un `threading.Lock` (no reentrante) y solo lo toman `ControlLoop._tick` (`control_loop.py:180-181`) y `set_active_cycle` (`:301-311`). Ninguna otra ruta HTTP lo toma. Dentro de la sección crítica el lazo hace E/S serial bloqueante y `all_off()` con espera de hasta 1 s por ACK, repetible en cada tick (OPC-22, OPC-23). El tick corre cada 0.5 s más su duración.
- Auditoría: `cycle_params_audit` la escribe el proceso PySide después del PATCH (`params_ciclo.py:343-357`), con nombre completo o "Desconocido", sello sin segundos; si el INSERT falla, el cambio queda sin registro.
- Persistencia: `_save_cycle_json` (`server.py:699-710`) abre en modo "w" y ejecuta `git add/commit` en el hilo de la petición. `BackendClient` tiene `timeout=0.8` s (`backend_client.py:48-56`): con git lento, PySide informa "no se guardó" aunque el backend ya aplicó el cambio (OPC-26). En el EXE de un solo archivo, `cycles/user/*.json` se reescribe en la carpeta temporal de extracción y se pierde al cerrar (OPC-34).
- `Cycle.set_param`: `bool("false")` devuelve `True`; NaN e infinito pasan los rangos; no distingue entero de flotante.
- Si `globals.F0` pasa de falso a verdadero durante ESTERILIZACION, `_timer_timeout_max` queda en `None` y la comparación lanza `TypeError` en cada tick: la fase no completa ni falla (OPC-30). Respalda el bloqueo por estado.
- Más de un proceso escribe en `data/autoclave.db` (backend, PySide, QML); WAL activo; sin transacciones explícitas ni manejo de `database is locked` (`timeout` por defecto de 5 s).
- Roles definidos en `ui_pyside/services/roles.py`: `admin`, `tecnico`, `biomedico`, `ingeniero`; `operador` es el valor por defecto de la tabla y no está en esa lista. `SessionManager` guarda `usuario`, `nombre` y `rol` por proceso.

---

## 4. Requisitos

### RB-01. Bloqueo por estado y exclusión con el inicio de ciclo (OPC-01, OPC-18, OPC-22, OPC-23, OPC-30)

1. Toda ruta que modifique parámetros comprueba el estado global y permite el cambio solo en PREPARACION o PREPARADO (lista blanca, D-1). Rutas: `PATCH /cycle/parameter`, `PATCH /cycle/parameters` y las de roles de sensor (especificación 2).
2. El hilo HTTP NO toma `_sm_lock` para editar. Motivos: su sección crítica incluye E/S serial bloqueante (hasta 1 s por tick) y es un `Lock` no reentrante, así que además `set_active_cycle` no podría llamarse con él retenido.
3. Diseño propuesto, que Claude Code debe verificar y refinar en su plan: un bloqueo propio (`_param_lock`) que cubre la sección crítica completa de la edición (comprobar estado, insertar auditoría, reemplazar archivo, aplicar en memoria, confirmar). La transición PREPARADO → CICLO, decidida por el hilo de control, adquiere ese bloqueo con intento no bloqueante y, si está ocupado, difiere el inicio un tick (0.5 s). Orden de bloqueos: `_param_lock` antes que `_sm_lock` en el hilo HTTP; el hilo de control nunca espera `_param_lock` mientras sostiene `_sm_lock`. `POST /cycle/select` también respeta ese orden. Resultado exigido: es imposible que un cambio se aplique después de iniciado el ciclo, y el lazo de control no espera nunca por una petición HTTP.
4. Claude Code debe ubicar dónde se decide hoy la transición a CICLO, medir los tiempos reales y proponer el punto exacto de enganche. Exigencia de tiempo: el lazo no se retrasa más de un tick.
5. Rechazo: HTTP 409, código `EDICION_BLOQUEADA_ESTADO`, con el estado actual en el cuerpo. La lista blanca cubre CICLO en espera de confirmación y los `FALLO_*` internos, porque el estado global sigue siendo CICLO.

### RB-02. Identidad y rol en cada escritura (OPC-02, parcial)

1. Toda petición de escritura incluye `usuario` (login), `nombre` y `rol`. Si faltan, el backend rechaza con `IDENTIDAD_FALTANTE`; se elimina "Desconocido".
2. El backend verifica que el rol esté en {`biomedico`, `tecnico`, `ingeniero`} (D-2). Rechazo: 403 `ROL_NO_PERMITIDO`. La lista de roles vive en un módulo compartido, no en `ui_pyside`.
3. LIMITACIÓN EXPLÍCITA (D-8): sin sesión propia en el backend, la identidad es declarada por el cliente. Es defensa en profundidad, no control de seguridad. Cada fila de auditoría lleva `identidad_verificada = 0`. Cierre completo: especificación aparte del token de sesión.
4. El backend escucha solo en `127.0.0.1` (D-9). Ninguna ruta lee hoy cabeceras ni IP; no existe identificación de clientes (B.3 del informe).
5. Las UIs adjuntan la identidad desde `SessionManager.current_user()` (PySide) o desde propiedades nuevas del `LoginController` (QML, hoy solo expone `nombreSesion`; especificación 3).

### RB-03. Auditoría escrita por el backend (OPC-03, OPC-37)

1. El backend escribe la fila de auditoría en la misma operación lógica que el cambio. Ningún cliente audita por su cuenta: `params_ciclo.py` deja de insertar y `SecadoView` pasa a quedar auditado por el backend.
2. Esquema (migración aditiva sobre `cycle_params_audit`): se conservan las columnas actuales y se agregan `programa_numero INTEGER`, `usuario_login TEXT`, `rol TEXT`, `accion TEXT` (`EDICION`, `RESTABLECER`, `ROLES_SENSOR`), `identidad_verificada INTEGER`.
3. Sello con segundos (`YYYY-MM-DD HH:MM:SS`, hora local), desempate por `id`.
4. `valor_anterior` lo lee el backend de su propio estado, nunca el cliente.
5. Atomicidad: si la auditoría no puede registrarse, el cambio no se aplica. Dentro del `_param_lock` de RB-01: abrir transacción con `BEGIN IMMEDIATE` (con tiempo de espera acotado, propuesta 1 s) e insertar la fila; escribir el archivo de forma atómica (RB-04); aplicar en memoria; confirmar. Si falla el archivo: ROLLBACK y 500 `PERSISTENCIA_FALLIDA`. Si falla la confirmación después de reemplazar el archivo: restaurar el contenido previo, revertir la memoria y responder 500.
6. Base ocupada: un `database is locked` o espera agotada se maneja explícitamente y responde 503 `BASE_OCUPADA`, sin aplicar el cambio. No debe ejecutarse nunca en el hilo de control.
7. Solo anexar: triggers de SQLite que bloquean `UPDATE` y `DELETE` sobre la tabla (D-13). Al arrancar se verifica que el SQLite en uso permite crear el trigger; si no, se registra un error visible. SQLite 3.50.4 los admite; el EXE publicado no se inspeccionó.
8. Consulta de última modificación: ruta de solo lectura que devuelve, por (programa, sección, parámetro), el último registro con login, nombre, rol, fecha, valor anterior y nuevo; índice por (`programa_numero`, `fase`, `param`, `id`). Se compara por `usuario_login` cuando existe (D-14).
9. Migración con el patrón actual de `_migrate()` (`ALTER TABLE ... ADD COLUMN` tolerante). No existe versionado de esquema (`PRAGMA user_version`); se recomienda agregarlo como mejora aparte.

### RB-04. Persistencia atómica (OPC-04, OPC-34)

1. Escritura de los JSON de usuario con archivo temporal en el mismo directorio, `flush` + `fsync`, relectura y validación del temporal y `os.replace`. Nunca abrir el definitivo en modo "w".
2. Conservar la versión anterior como `<nombre>.json.bak`.
3. El `git add/commit` sale del camino de la petición: hilo aparte, mejor esfuerzo; su fallo no afecta la respuesta. No es auditoría.
4. Un archivo ilegible o que viole el catálogo no se descarta en silencio ni se sustituye por el perfil de fábrica homónimo: se registra un error visible, se intenta `.bak`, y si no se puede el programa queda marcado como dañado y no ejecutable (`GET /cycles` expone el estado). Se reemplaza el `print` por logging.
5. Directorio de datos persistente (D-10): `app_root()/data/cycles/user/`, sembrado desde el paquete la primera vez. El backend es el único lector y escritor. Claude Code propone la migración de los tres archivos actuales de `cycles/user/` y qué hacer cuando existan copias divergentes. La vista PySide de parámetros y cualquier UI dejan de leer programas de disco.
6. `resource_path` y `utils/logging.py` dependen del directorio de trabajo o de `__file__` (OPC-34); se anota para la limpieza, sin cambiarlo aquí salvo lo que D-10 exija.

### RB-05. Validación de valores (OPC-05, OPC-17, OPC-28)

1. Catálogo en código (nombre propuesto `catalogo_parametros`): ruta, tipo, unidad, mínimo y máximo de seguridad. Etiqueta, paso y decimales los agrega la especificación 3. Contenido inicial: rangos vigentes más las correcciones del Anexo B una vez aprobadas.
2. Rango efectivo = intersección de catálogo y JSON del programa (D-6); si el JSON es más amplio, prevalece el catálogo y se registra advertencia.
3. Tipos estrictos: booleano solo `true`/`false` JSON; entero rechaza flotante con parte decimal; flotante rechaza NaN e infinito; se rechaza toda cadena numérica. Rechazo: 422 `VALOR_INVALIDO`.
4. D-5: parámetros del Anexo A con mínimo del catálogo mayor que 0 (valores propuestos en el Anexo B).
5. Validación al cargar: un programa cuyo JSON contenga valores fuera del catálogo se marca como dañado (RB-04.4), de modo que un 0 introducido por edición manual no llegue a la lógica.
6. Unificación de rutas: una sola función de aplicación de cambios para ambas rutas (D-12). Con varios parámetros: todo o nada, auditoría de cada uno en la misma transacción. Se elimina la tabla duplicada de rangos de `server.py`.

### RB-06. Concurrencia entre clientes (D-4)

Toda petición incluye `valor_anterior_esperado`. Si difiere del actual: 409 `VALOR_CAMBIO` con el valor actual. Dos peticiones simultáneas sobre el mismo parámetro se serializan por el `_param_lock`.

### RB-07. Respuestas de error normalizadas

Cuerpo común con `codigo` y `mensaje`. Códigos: `EDICION_BLOQUEADA_ESTADO` (409), `VALOR_CAMBIO` (409), `ROL_NO_PERMITIDO` (403), `IDENTIDAD_FALTANTE` (422), `VALOR_INVALIDO` (422), `PROGRAMA_NO_ENCONTRADO` (404), `PROGRAMA_NO_EDITABLE` (409; solo lectura o dañado), `BASE_OCUPADA` (503), `PERSISTENCIA_FALLIDA` (500). La UI traduce cada código en `es.json` (especificación 3).

### RB-08. Punto único de escritura reutilizable

La lógica de RB-01 a RB-06 vive en un servicio único (nombre propuesto `ServicioConfiguracionCiclo`). Es el punto de extensión de la especificación 2 (roles de sensor).

### RB-09. Clientes de escritura (OPC-26, D-15)

Timeout de escritura de 5 s (propuesta) en los clientes; un timeout o un error de red se trata como resultado incierto: recargar el valor desde el backend antes de informar. Se adapta `params_ciclo.py` (PySide) y `SecadoView`; la UI QML nueva nace con este comportamiento.

---

## 5. Migración de base de datos

- Migración idempotente al iniciar el backend, con el patrón de `_migrate()`: `ALTER TABLE cycle_params_audit ADD COLUMN ...` solo si la columna falta.
- Filas históricas: `accion = 'EDICION'`, `rol = NULL`, `programa_numero = NULL`, `usuario_login = NULL`, `identidad_verificada = 0`. Los sellos y nombres existentes no se reescriben.
- Triggers de solo anexar e índice nuevo, creados después de las columnas.
- Copia de seguridad de `data/autoclave.db` antes de migrar; ejecutable dos veces sin efecto.
- Migración de `cycles/user/` al directorio de datos persistente (RB-04.5).

---

## 6. Impacto en el código

- `backend/server.py` (rutas, `_save_cycle_json`, guardias), `backend/main.py` (host y comentario).
- `core/managers/cycle_manager.py` (`set_param`, carga, archivos dañados), `config_manager.py`, `utils/paths.py`.
- `services/domain/loop/control_loop.py` y `state_machine/states/preparado.py` (enganche del intento de bloqueo en la transición a CICLO; `set_active_cycle`).
- `services/domain/logging/cycle_params_audit.py`, `db_manager.py` (migración).
- `utils/git_autocommit.py`.
- `ui_pyside/views/params_ciclo/params_ciclo.py` y `views/secado.py` (identidad, timeout, códigos, sin auditoría propia, sin lectura de disco), `ui/service_ui/backend_client.py` (timeout de escritura).
- Módulo nuevo del catálogo, módulo compartido de roles y servicio de configuración.
- `AutoclaveBackend.spec`, `AutoclaveUI.spec`, `AutoclaveSettings.spec` (semilla de `cycles/`).

---

## 7. Pruebas requeridas

- RB-01: intento de cambio en PREPARACION y PREPARADO (permitidos) y en CICLO, CICLO en espera de confirmación, `FALLO_*`, FALLA (rechazados con 409). Edición concurrente con `START_CICLO`: nunca se aplica un cambio posterior al inicio; el inicio se difiere un tick si la edición está en curso; el hilo de control nunca espera el `_param_lock`. Conmutar `globals.F0` durante ESTERILIZACION rechazado (OPC-30). Medición del tiempo retenido de `_sm_lock` antes y después.
- RB-02: sin identidad, con `admin`, con `operador`, con rol permitido.
- RB-03: auditoría con login, nombre, rol, segundos y valor anterior real; INSERT fallido impide el cambio; fallo entre temporal y reemplazo deja el original intacto; `UPDATE` y `DELETE` fallan; `database is locked` devuelve 503 sin aplicar.
- RB-04: corte simulado durante la escritura; archivo corrupto o fuera de catálogo al arrancar (recuperación desde `.bak` y marca de dañado); git ausente no afecta la respuesta; el EXE conserva los programas tras reiniciar.
- RB-05: booleano con "false", NaN, infinito, flotante en entero, cadena numérica, 0 en cada parámetro del Anexo A, JSON más amplio que el catálogo.
- RB-06: valor anterior desfasado devuelve 409; dos peticiones simultáneas.
- RB-09: timeout del cliente seguido de recarga correcta.
- Regresión: `PATCH /cycle/parameters` todo o nada y auditado; `SecadoView` y la vista de parámetros siguen editando programas de usuario.

---

## 8. Riesgos residuales y hallazgos

- R-1 (alta). Identidad no verificada en el backend (OPC-02 parcial); cierre con la especificación del token de sesión.
- R-2 (media). Enganche en la transición a CICLO (RB-01.3): toca la máquina de estados; requiere diseño y pruebas con especial cuidado y medición real (OPC-23: duración de la sección crítica NO DETERMINADA).
- R-3 (baja). Los sellos históricos sin segundos y los nombres mezclados en `usuario` no se pueden corregir.
- R-4 (media). `PREPARACION` y `PREPARADO` leen `globals.presion_chaqueta` sin respaldo; con D-5 el 0 deja de ser posible, pero un valor `None` sigue lanzando excepción (OPC-29, especificación 2 RS-09).
- Hallazgos fuera de esta especificación pero que Cristian debe priorizar: OPC-24 (flujo de FALLA borra alarmas no recuperables) y OPC-25 (interlock de puertas permite abrir con `temp_camara` o `pres_camara` en `None`).

---

## 9. Criterios de aceptación

1. Ninguna ruta de escritura acepta cambios fuera de PREPARACION o PREPARADO, y ningún cambio puede cruzarse con el inicio de un ciclo.
2. El lazo de control no espera nunca por una petición HTTP; la medición lo demuestra.
3. Todo cambio aplicado genera exactamente una fila de auditoría con login, nombre, rol, segundos y valor anterior real; ningún cambio se aplica sin su fila.
4. Un corte de energía simulado en cualquier punto no deja un JSON truncado, ni un cambio sin auditoría, ni la pérdida de programas en el EXE.
5. Valores de tipo incorrecto, NaN, infinito y 0 en los parámetros del Anexo A son rechazados con 422; un programa fuera de catálogo no se ejecuta.
6. Un cambio con valor anterior desfasado se rechaza con 409.
7. `SecadoView` y la vista de parámetros siguen funcionando, auditadas por el backend.
8. El backend escucha solo en `127.0.0.1`.

---

## 10. Preguntas abiertas

- E-1. `descompresion.modo = 0` (permitido hoy, mínimo JSON 0): la fase no abre válvulas y no tiene timeout (puede quedar en EN_CURSO indefinido), mientras `valvula_reposo.py` y `protocolo_fallo.py` lo tratan como modo 2 (OPC-36). Recomendación: prohibirlo (mínimo 1). ¿Es el modo 0 una función soportada?
- E-2. Mínimos concretos del Anexo B: se aprueban parámetro por parámetro en la especificación 3.

Todas las demás preguntas de las revisiones anteriores están cerradas por D-8 a D-15.

---

## Anexo A. Parámetros con sustitución o comportamiento especial del 0 (verificado por Claude Code)

### A.1 Lectura con `or <constante distinta de 0>` (0 se sustituye en silencio): mínimo del catálogo mayor que 0

1. `precalentamiento.timeout_precalentamiento` (`precalentamiento.py:40`, constante 10 min; la fase solo corre si `tiempo_precalentamiento` es distinto de 0).
2. `prevacio.timeout_bajo` (`prevacio.py:128`, 10 min).
3. `prevacio.timeout_alto` (`prevacio.py:176`, 10 min).
4. `prevacio.presion_baja_pulso_a/b/c/d` (`prevacio.py:147`, 15 kPa).
5. `prevacio.presion_alta_pulso_a/b/c/d` (`prevacio.py:196`, 180 kPa).
6. `calentamiento.temperatura_calentamiento` (`calentamiento.py:203`, 134.0 °C; el JSON ya exige mínimo 100).
7. `calentamiento.timeout_calentamiento` (`calentamiento.py:205`, 60 min; JSON mínimo 1).
8. `calentamiento.rango_temp_estabilizacion` (`calentamiento.py:216`, 1.0 °C).
9. `calentamiento.timeout_recuperacion_estabilizacion` (`calentamiento.py:217`, 5 min; JSON mínimo 1).
10. `esterilizacion.temperatura_esterilizacion` (`esterilizacion.py:155`, 134.0 °C; JSON mínimo 100).
11. `esterilizacion.tiempo_esterilizacion` (`esterilizacion.py:156`, 3.5 min). Con 0 el registro y la pantalla muestran 0 mientras se ejecutan 3.5 min (`cycle_logger.py:210-211`, `pantalla_ciclo.py:70-72`).
12. `secado.modo` (`secado.py:32`, 1; JSON mínimo 1).
13. `secado.timeout_pulso` (`secado.py:37, 119, 135`, 10 s; JSON mínimo 1).
14. `secado.presion_chaqueta_secado` (`secado.py:60`, 200 kPa).
15. `secado.rango_chaqueta_secado` (`secado.py:61`, 30 kPa).
16. `secado.presion_baja_secado` (`secado.py:107`, 20 kPa).
17. `secado.presion_alta_secado` (`secado.py:125`, 80 kPa).
18. `globals.presion_chaqueta` (en CICLO 0 aplica 320 kPa, `ciclo.py:175-176`; en PREPARACION y PREPARADO se usa 0 literal, `preparacion.py:173`, `preparado.py:95`).
19. `globals.rango_presion_chaqueta` (en CICLO 0 aplica 50 kPa; en PREPARACION y PREPARADO banda de ancho cero).
20. `descompresion.modo_N.timeout`, N de 1 a 5 (`descompresion.py:47-48`, `protocolo_fallo.py:112-113`, 60 min; JSON mínimo 1).

### A.2 Lectura con `default=` donde el 0 produce bloqueo, FALLO o desactiva una protección: candidatos a mínimo mayor que 0

21. `descompresion.modo` (OPC-36, pregunta E-1).
22. `descompresion.modo_3.presion_cambio` (0 mantiene la fase lenta hasta el timeout y termina en FALLO).
23. `descompresion.modo_{4,5}.presion_camara_enfriamiento` (0 nunca abre aire comprimido).
24. `descompresion.modo_{4,5}.temperatura_enfriamiento` (0 impide terminar el enfriamiento; FALLO por timeout).
25. `finalizacion.temp_max_apertura` (0 impide la apertura automática y dispara `TIMEOUT_APERTURA_AUTOMATICA`).
26. `descompresion.modo_{4,5}.tiempo_apertura_chaqueta` (JSON ya exige mínimo 1).

### A.3 Valores 0 válidos y documentados (sin cambio)

`precalentamiento.tiempo_precalentamiento` (0 salta la fase), `prevacio.conteo_pulso_*` (0 salta el tipo), `secado.tiempo_secado` (0 salta la fase), `descompresion.tiempo_pre_despresurizacion` (sin espera previa), `finalizacion.tiempo_espera_apertura` (sin espera), `escape_*` con el patrón estándar, `globals.F0_objetivo`, entre otros. Se detallan en el informe de verificación (A.3).

## Anexo B. Límites de seguridad del catálogo (pendiente de aprobación)

Los rangos vigentes del JSON son amplios (por ejemplo `tiempo_esterilizacion` de 0 a 9999 min; presiones de 0 a 1000 kPa con equipo de 400 kPa; los límites del modelo, presión de 1 a 400 kPa y temperatura de 0 a 200 °C, no se consultan hoy). Claude propondrá en la especificación 3 un mínimo y un máximo por parámetro para los de los Anexos A.1 y A.2, contrastados con los límites del modelo, para aprobación de Cristian. Hasta entonces el catálogo conserva los rangos vigentes.
