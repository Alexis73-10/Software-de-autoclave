# Planeación — Autenticación y endurecimiento del backend

**Proyecto:** Software de Autoclave (Especifika S.A.S.)
**Estado:** v7 — cerrada (2026-10-08). La v7 añade el cambio de contrato de la etapa 4 (decisiones 33 a 36, §4.1, riesgos residuales 3 y 4, T-14); cuerpo final aprobado en `plan_t8_login_qml.md` §3.4. T-8 y T-14 implementados — precede a `planeacion_backend_parametros.md`
**Ubicación sugerida:** `docs\mis_plans\planeacion_backend_autenticacion.md`
**Origen:** informes de Code del 7-oct (inventario de endpoints, login, clientes) y hallazgos H-03, OPC-02, OPC-14, OPC-16 a OPC-19
**Documentos relacionados:** `planeacion_opciones.md`, `planeacion_backend_parametros.md`

---

## 1. Objetivo

Cerrar H-03 y los endpoints que accionan hardware sin comprobaciones, e introducir identidad verificada en el backend. Es condición previa para Opciones QML, la bitácora y la escritura de parámetros.

Se implementa en **una sola fase** (token y roles incluidos). El software no está montado en ningún equipo, así que perder temporalmente la calibración y la configuración desde PySide es aceptable.

## 2. Estado actual

| Hecho | Detalle |
|---|---|
| Sin autenticación | Ningún endpoint recibe ni verifica identidad o rol. Todo está en `backend/server.py`, sin routers ni WebSocket. |
| Host | `backend/main.py:27-31`: `0.0.0.0:8000`, sin configuración. Ningún cliente usa otra dirección que `127.0.0.1` / `localhost`. |
| Login | `login_controller.py:63-86` (QML) y `ui_pyside/views/login.py:218-259` leen SQLite directamente. SHA-256 sin sal (`session_manager.py:4-5`). |
| Sesión | `SessionManager`: atributo de clase en memoria, una por proceso (cada ventana QML y PySide tienen la suya). |
| Usuario semilla | `seed_admin_if_empty` (`db_manager.py:474`): `admin` / `admin1234`. |
| Operadores | La tabla `operadores` no existe. `ciclos.operador` existe pero nadie la llena (B-02). |
| Paro de emergencia | Es una entrada física, no un endpoint. No se ve afectado por esta spec. |
| Botones de puerta (T-9) | QML (`PantallaPreciclo.qml:577-585`) y Tk solo dependen de conexión y de que no haya un comando en curso; ningún filtro por estado. En CICLO no hay botón porque la pantalla de ciclo lo oculta. |
| Apertura automática (T-9) | La ejecuta el backend directamente sobre `ServicioPuertas` (`ciclo.py:254-336`), sin HTTP. Es más estricta que la manual: exige `temp_camara` y `pres_camara` presentes. |
| Estados inalcanzables (T-9) | Ningún código pone EMERGENCIA ni HIBERNACION. La emergencia en ciclo termina en FALLA. |
| Parámetros de ciclo (T-9) | El ciclo en curso usa el mismo objeto que edita `PATCH /cycle/parameter(s)`, sin copia. Unos valores se leen en vivo y otros se fijan al entrar en la fase, de forma accidental. |

**Endpoints con efecto físico y sin ninguna comprobación:** `PATCH /io/test/output/{name}`, `POST /outputs/reset`, `POST /io/test/reset_all`, `POST /io/test/exit`. Las puertas no comprueban estado de máquina y abren aunque falte un sensor (OPC-16).

## 3. Decisiones aprobadas

1. **Host fijo en `127.0.0.1`**, sin configuración. No hay planes de acceso remoto.
2. **Token por sesión** emitido por `POST /auth/login`. Vence por logout o al entrar en suspensión, sin parámetro propio. Un reinicio del backend invalida todos los tokens y la UI vuelve al login.
3. **Login en el backend.** QML deja de leer SQLite para autenticar. PySide no se adapta y se elimina al terminar la migración.
4. **Hash:** PBKDF2-HMAC-SHA256, sal aleatoria por usuario, 600 000 iteraciones, formato `pbkdf2$iteraciones$sal$hash`. Sin migración de hashes viejos: los usuarios de desarrollo se recrean.
5. **Usuarios semilla:** `admin` (rol admin) e `ingeniero` (rol ingeniero), ambos con bandera `debe_cambiar_clave`. El primer login obliga a cambiar la contraseña. Mientras la bandera esté activa, el token solo permite `/auth/change_password` y `/auth/logout`; cualquier otra escritura devuelve 403 "debe cambiar la contraseña".
6. **Lectura sin token** en V1. El bind local es la protección.
7. **Endpoints operativos sin token** (inicio, aborto, confirmación, selección de ciclo, puertas, impresión). Cuando exista la tabla `operadores`, aceptan un campo opcional `operador` y lo guardan en `ciclos.operador` como declarado, no verificado.
8. **Sesiones independientes** por ventana QML. Un logout invalida solo su token.
9. **`git_autocommit` se elimina** de calibración y parámetros. No es un respaldo. La trazabilidad la da `audit_log`, que guarda valor anterior y nuevo.
10. **Registro y bloqueo:** logins fallidos y rechazos 401/403/409 de acciones físicas y de configuración van a `audit_log`. Bloqueo tras 5 intentos fallidos durante 5 min por usuario.
11. **Simulador:** replica las respuestas 401/403/409 y acepta un token de prueba fijo.
12. **`tools/generador`** es una aplicación externa y queda fuera de alcance.
13. **Guard de configuración unificado:** toda escritura de configuración (parámetros del sistema, de ciclo, calibración, sensores y entradas mostradas) se permite en cualquier estado distinto de CICLO.
14. **Excepción del ingeniero:** puede cambiar parámetros de ciclo y calibración también en CICLO (sección 5.8).
15. **HIBERNACION es la suspensión.** Puertas y modo de prueba se bloquean en HIBERNACION, porque las salidas están apagadas por definición.
16. **`POST /fault/reset`** no requiere identificación.
17. **Modo quiosco:** el PC de estación solo ejecuta este software. Única excepción: AnyDesk con acceso desatendido. **AnyDesk queda fuera del alcance de esta spec** y se trata aparte (OPC-21).
18. **Cierre de puerta:** sin comprobación de vacío ni temperatura. Con estado propio DESCONOCIDO se rechaza el cierre: la posición segura es abierta.
19. **Resultado real de las puertas:** 409 con motivo si la entrada de bloqueo cancela la apertura; indicador "sin actuador" para `SimpleDoor`.
20. **EMERGENCIA:** puertas y modo de prueba bloqueados, igual que HIBERNACION, aunque hoy no se alcance.
21. **Puerta de la apertura automática:** se define en el perfil de equipo (`puerta_descarga`). Con dos puertas abre la 2; con una, esa.
22. **Fallas:** `/cycle/acknowledge` restablece todo resultado FALLO; botón "Reconocer falla" sin rol en preciclo, visible solo en FALLA; tras soltar el paro de emergencia se exige un nuevo reconocimiento.
23. **Programas no seleccionados:** el ingeniero los puede editar durante CICLO.
24. **`temp_chaqueta`** se elimina del mapa de ejecución: se retiró de todos los equipos.
25. **Roles válidos:** admin, tecnico, ingeniero. `biomedico` se elimina del código (`roles.py`, `permisos_opciones.py`). Calibración y parámetros de ciclo: solo ingeniero. Modo de prueba: técnico e ingeniero. Admin no configura ni prueba.
26. **Creación de usuarios:** `POST /usuarios` en el backend. Ingeniero crea admin, técnico e ingeniero; admin crea admin y técnico; técnico no crea. El puente de Nuevo usuario deja de escribir directo en la base de datos. Reemplaza la decisión anterior de Nuevo usuario (escritura directa con SHA-256).
27. **Hashes viejos:** un hash que no empiece por `pbkdf2$` nunca valida. La base de desarrollo se recrea.
28. **`audit_log` se adelanta** a la etapa 1 como migración v1 (`PRAGMA user_version`). Lo demás de la spec de parámetros es v2. Las tablas `cycle_params_audit` y `sensor_calibration_audit` quedan como históricas, sin escrituras nuevas.
29. **Respuestas del login:** 401 genérico (credenciales inválidas, usuario inexistente o inactivo, sin distinguir); 429 con el usuario bloqueado, aunque la contraseña sea correcta. Los intentos cuentan también para usuarios inexistentes.
30. **Token del modo prueba invalidado** (logout o suspensión): el backend sale del modo prueba y apaga las salidas.
31. **Suspensión y token:** en la etapa 1 el token vence por logout o reinicio del backend; en la etapa 4 el puente QML llama a `/auth/logout` al entrar en suspensión.
32. **`PATCH /cycle/parameters` se elimina:** `PATCH /cycle/parameter` cubre el secado.
33. **(v7) Bloqueo con segundos restantes:** el 429 de `POST /auth/login` lleva un código estable, los segundos restantes y la cabecera `Retry-After`. El 5.º intento fallido ya responde 429 (antes 401). Un intento con la contraseña correcta no cuenta como fallo. La UI traduce el código con `es.json` y hace la cuenta regresiva local. Un login que la UI dio por vencido cuenta igual en el backend (aceptado). Los fallos de la clave actual en `POST /auth/change_password` suman al mismo contador del usuario; al 5.º responde el mismo 429 y se invalida ese token; un cambio exitoso reinicia el contador (H-T8-01).
34. **(v7) Códigos estables en los rechazos:** las respuestas 401, 403, 409 y 422 que muestra la UI llevan un código estable; la UI traduce todo mensaje con `es.json`, el 422 por campo y tipo, nunca con el texto de FastAPI. Código desconocido: mensaje genérico y registro. Cuerpo final en revisión.
35. **(v7) Simulador:** usuarios sembrados por rol en memoria (uno con clave pendiente y uno dedicado al bloqueo) y token determinista por sesión `sim-<usuario>-<n>` con tabla en memoria, para respetar la decisión 8. Definido solo en `simulador/`, escuchando en 127.0.0.1, sin trato especial en el cliente ni en producción.
36. **(v7) Inactividad de la sesión (SAF-01):** la sesión de cada ventana QML se cierra con logout tras 5 min sin toques ni teclas en esa pantalla, en cualquier estado del equipo (el standby no actúa en CICLO, FALLA ni EMERGENCIA). La actividad de la otra puerta no la mantiene viva. Al vencer, la ventana vuelve a la pantalla principal y el siguiente login avisa la causa.

## 4. Reglas por endpoint

**Token:** — = sin token. **Guard:** estados de máquina permitidos o condición.

### 4.1 Nuevos

| Endpoint | Token | Guard | Notas |
|---|---|---|---|
| `POST /auth/login` | — | bloqueo por intentos | devuelve token, rol y `debe_cambiar_clave`; (v7) 429 con código estable, segundos restantes y `Retry-After`, también en el 5.º fallo (decisión 33) |
| `POST /auth/logout` | sí | — | invalida el token |
| `POST /auth/change_password` | sí | — | obligatorio si `debe_cambiar_clave`; (v7) rechaza la clave nueva igual a la actual con 422 `igual_actual` en `clave_nueva`; los fallos de la clave actual cuentan para el bloqueo del login (429 al 5.º e invalidación del token, decisión 33) |
| `GET /auth/sesion` | sí | — | (v7) endpoint de autenticación: valida el token. 200 `{usuario, rol}` o 401 estándar. La UI lo llama una vez al reconectar con el backend, nunca de forma periódica |
| `POST /usuarios` | sí (admin o ingeniero) | — | reglas de creación de la decisión 26; 403 si el rol no puede crear el rol pedido, 409 si el usuario ya existe (sin distinguir mayúsculas), 422 si falla la validación. Validaciones de `validacion_usuario.py` excepto el campo Código/ID, eliminado de la pantalla |

### 4.2 Lectura (sin token, sin cambios)

`GET /calibration/{tipo}/{sensor}`, `/status`, `/global_params`, `/cycle`, `/cycles`, `/cycle/current/readings`, `/cycle/current/progress`, `/cycle/current/graph`, `/cycle/summary`, `/cycle/list`, `/report/summary`, `/cycle/history/{id}/graph`, `/cycle/history`, `/cycle/history/{id}/readings`, `/cycle/history/{id}/ticket`.

### 4.3 Operativos (sin token)

| Endpoint | Guard | Cambio |
|---|---|---|
| `POST /ui/activity` | — | ninguno |
| `POST /cycle/select` | ya rechaza en CICLO | ninguno |
| `POST /cycle/history/print`, `POST /report/summary/print` | ya rechazan en CICLO (409) e impresora no lista (503) | ninguno |
| `POST /cycle/start` | bandera `LISTO_PARA_CICLO` | acepta `operador` opcional cuando exista la tabla |
| `POST /cycle/abort` | solo en CICLO | ninguno; es acción de seguridad y nunca exige token |
| `POST /cycle/acknowledge` | solo en CICLO | ninguno |
| `POST /fault/reset` | solo en FALLA | ninguno; sin identificación. Se evalúa si es redundante con `/cycle/acknowledge` (T-9) |
| `POST /outputs/reset` | **409 en CICLO** (nuevo) | para detener un ciclo existe `/cycle/abort` |
| `POST /doors/{door}/open`, `/close` | **distinto de CICLO y de HIBERNACION** (nuevo) | ver 5.3; `source_door` sin usar, fuera de alcance |

### 4.4 Configuración (token obligatorio)

| Endpoint | Rol | Guard | Cambio |
|---|---|---|---|
| `PATCH /calibration/{tipo}/{sensor}` | ingeniero | distinto de CICLO; en CICLO solo ingeniero (5.8) | usuario del token; se ignora `usuario` del cuerpo; sin `git_autocommit`; auditoría en backend |
| `PATCH /cycle/parameter` | ingeniero | distinto de CICLO; en CICLO según 5.8 | sin `git_autocommit`; auditoría en backend |

Los endpoints de parámetros del sistema y de sensores y entradas mostradas se definen en `planeacion_backend_parametros.md` con estas mismas reglas.

### 4.5 Modo de prueba (token obligatorio, rol técnico o ingeniero)

| Endpoint | Guard | Cambio |
|---|---|---|
| `POST /io/test/enter` | ya rechaza en CICLO y con paro de emergencia; **también en HIBERNACION y EMERGENCIA** | nuevo rechazo en HIBERNACION y EMERGENCIA |
| `POST /io/test/exit` | **409 si no se estaba en modo prueba**; solo la sesión que entró | nuevo |
| `PATCH /io/test/output/{name}` | **modo prueba activo, distinto de CICLO, HIBERNACION y EMERGENCIA, sin paro de emergencia; para encender, condiciones de R-02 (5.4)** | nuevo |

### 4.6 Se eliminan

| Endpoint | Motivo |
|---|---|
| `POST /io/test/reset_all` | solo lo usan tests; apagar todo en cualquier estado puede cortar el vapor a mitad de ciclo |
| `PATCH /cycle/parameters` | duplica `PATCH /cycle/parameter`; solo lo usa PySide (`secado.py`) |
| `GET /cycle/history/{id}/ticket.txt` | solo lo usan tests; un GET no debe escribir archivos |

## 5. Diseño

### 5.1 Token
- Almacén en memoria del backend: token aleatorio (`secrets.token_urlsafe(32)`), usuario, rol, emisión.
- Cabecera `Authorization: Bearer <token>`.
- Invalidación: logout, entrada en suspensión, reinicio del backend.
- El vencimiento nunca afecta a un ciclo en curso: solo a escrituras de configuración y modo de prueba.

### 5.2 Roles
- Dependencia de FastAPI `requiere_rol(*roles)`: 401 sin token o token inválido, 403 rol insuficiente.
- El rol se toma siempre del token.

### 5.3 Puertas

**Capas:**
- **Condiciones físicas** en `ServicioPuertas`: se aplican siempre, a la orden manual y a la automática.
- **Guard de estado** solo en el endpoint: 409 en CICLO, HIBERNACION y EMERGENCIA. Permitido en PREPARACION, PREPARADO y FALLA (la banda de presión protege durante la igualación de la cámara).
- La apertura automática no pasa por el endpoint (T-9), así que el guard no la afecta.

**Apertura (`_can_open_physical`, `ser_puertas.py:132`):**
- Se rechaza si falta o es inválida la lectura de `pres_camara` o `temp_camara`, o si falta `presion_atmosferica`, `rango_presion_atm` o `temp_max_apertura`. Hoy se omite la comprobación y se permite (OPC-16).
- Se mantiene: rechazo fuera de la banda atmosférica, sobre `temp_max_apertura` y si otra puerta no está CERRADO (DESCONOCIDO cuenta como no cerrada).
- Los valores se leen en vivo de la configuración, no de copias de `__init__` (OPC-11).

**Cierre (`_can_close_physical`):**
- Intervienen el estado de la puerta, `pres_camara` y, solo si la puerta usa empaque (`AdvancedDoor`), `pres_empaque_N`. Si falta una presión que interviene o la configuración atmosférica, se rechaza.
- No se añade comprobación de vacío ni de temperatura.
- Estado propio DESCONOCIDO: se rechaza el cierre. La posición segura es abierta; una orden de apertura sigue sujeta a las condiciones físicas de apertura.

**Resultado real:** `request_open` y `request_close` devuelven el resultado verdadero. Hoy devuelven OK aunque `AdvancedDoor` cancele por la entrada de bloqueo o `SimpleDoor` no tenga actuador. Se devuelve 409 con motivo en el primer caso y el indicador "sin actuador" en el segundo.

**Puerta de la apertura automática:** hoy "Puerta 2 si existe, si no Puerta 1" fijo en código. Pasa al perfil de equipo (`puerta_descarga`) con el mismo comportamiento; mientras esa spec no exista, se mantiene la regla actual.

### 5.4 Modo de prueba
- `PATCH /io/test/output/{name}` comprueba en backend: `test_mode_active`, estado distinto de CICLO, HIBERNACION y EMERGENCIA, y sin paro de emergencia.
- **Apagar** una salida (`value=false`) se permite siempre dentro del modo prueba.
- **Encender** exige además (R-02): `pres_camara` dentro de `presion_atmosferica ± rango_presion_atm` y todas las puertas en CERRADO. Aplica a todas las salidas, incluidas las de puerta: con una puerta abierta, el técnico la cierra primero (decisión de Cristian: quien prueba tiene el conocimiento para hacerlo).
- Si falta la lectura de presión de cámara o del estado de puertas, se rechaza.
- `/io/test/exit` guarda qué token entró y solo acepta salir a esa sesión. Si ese token se invalida, el backend sale del modo prueba y apaga las salidas.

### 5.5 Guard de estado
- Función única que comprueba el estado dentro de `_sm_lock`, siguiendo el precedente de `ControlLoop` (`control_loop.py:~298-313`), con dos variantes: `distinto_de_ciclo` (configuración) y `distinto_de_ciclo_e_hibernacion` (puertas y modo de prueba).
- La excepción del ingeniero (5.8) se resuelve dentro del mismo guard: con estado CICLO, rol ingeniero y endpoint de parámetros de ciclo o calibración, la escritura pasa a la lógica de 5.8.
- Devuelve 409 con motivo legible para la UI.

### 5.6 Contraseñas
- `hash_password` y `verificar_password` en un módulo del backend, no en `ui_pyside`.
- Comparación en tiempo constante (`hmac.compare_digest`).
- Contador de intentos fallidos en memoria por usuario; bloqueo de 5 min tras 5 fallos.

### 5.7 Clientes
- `ciclo_controller.py:23` usa la misma constante de URL que `ui_qml/app.py` (`AUTOCLAVE_BACKEND_URL`).
- El puente QML guarda el token de su ventana, lo envía en cada escritura y maneja 401 (volver al login), 403 y 409 (mostrar motivo).

### 5.8 Cambios del ingeniero con ciclo en curso

**Parámetros de ciclo:**
1. El cambio siempre se guarda en el programa almacenado.
2. Si la fase del parámetro **aún no ha iniciado** en el ciclo en curso, el cambio también aplica al ciclo en curso.
3. Si la fase **ya inició** (en curso o terminada), el ciclo en curso conserva el valor anterior y el cambio aplica desde el siguiente ciclo.
4. La decisión se toma dentro de `_sm_lock`, comparando con la fase actual. Si la fase inicia en el mismo instante, se considera iniciada.
5. El ciclo en curso trabaja con una **copia profunda** de los parámetros tomada al iniciar. Una edición en CICLO actualiza el programa almacenado y, solo para fases pendientes, la copia. Hoy no existe copia (T-9): el ciclo usa el mismo objeto y la distinción entre valores en vivo y fijos es accidental (OPC-26). Con la copia, dentro de una fase iniciada ningún valor cambia.
5b. Programas no seleccionados: el ingeniero los puede editar en CICLO sin restricción, porque no afectan al ciclo en curso .
6. La respuesta del endpoint indica si el cambio aplicó al ciclo en curso o solo al siguiente, y la UI lo muestra.

**Calibración:** aplica de inmediato, porque no se puede asignar a una fase.

**Fase "Global":** sus parámetros rigen todo el ciclo, así que se consideran fase ya iniciada. Un cambio en CICLO aplica desde el siguiente ciclo.

**Secciones del JSON que no son fases propias:** `estabilizacion` se trata como CALENTAMIENTO; `despresurizacion` como DESCOMPRESION; `globals` y `finalizacion` como "Global". Consecuencia: un cambio en `finalizacion` durante el ciclo no afecta a la apertura automática de ese ciclo.

**Registro:** todo cambio va a `audit_log` con ciclo, fase, programa y `aplica` (`actual` o `siguiente`) en `detalle`. El ciclo no se marca en el ticket, el PDF ni el historial (decisión de Cristian). La trazabilidad queda solo en `audit_log`.

### 5.9 Fallas y restablecimiento

- `POST /cycle/acknowledge` activa `RESET_FALLA` para **todo** resultado FALLO, no solo para fases que empiezan por `FALLO_`. Hoy `SENSOR_AUSENTE` deja la máquina en FALLA sin salida desde QML (OPC-22).
- `POST /fault/reset` se mantiene, sin identificación, y lo usa un botón "Reconocer falla" en QML visible solo en FALLA .
- Con el paro de emergencia activo, `/cycle/acknowledge` y `/fault/reset` responden 409 y no guardan `RESET_FALLA`; la máquina descarta además cualquier `RESET_FALLA` que llegue con el paro activo. Tras soltar el paro se exige un nuevo reconocimiento. Hoy la máquina pasa sola a PREPARACION al soltar el paro (OPC-23).

### 5.10 Auditoría

- Tabla `audit_log` según `planeacion_backend_parametros.md` sección 7, creada por la migración v1.
- Datos de contexto (ciclo, fase, programa, `aplica`, motivo de rechazo) en `detalle` (JSON).
- Códigos de evento: `login_ok`, `login_fallido`, `login_bloqueado`, `logout`, `cambio_clave`, `rechazo_401`, `rechazo_403`, `rechazo_409`, `calibracion_cambio`, `param_ciclo_cambio`, `usuario_creado`, `modo_prueba_entra`, `modo_prueba_sale`, `salida_prueba`, `falla_reconocida`.
- `GET /calibration` toma el último cambio de `audit_log` y, si no hay, de `sensor_calibration_audit`. La pantalla PySide de parámetros sigue leyendo `cycle_params_audit` y no se adapta.

## 6. Riesgo residual

1. **Procesos locales:** cualquier proceso del PC puede llamar a los endpoints operativos y de lectura en `127.0.0.1` sin token. Se acepta porque el PC queda en modo quiosco (decisión 17). La implementación del quiosco se define aparte.
2. **AnyDesk desatendido (OPC-21):** fuera de alcance. Se trata en una spec aparte.
3. **(v7) Token huérfano sin expiración:** si un login llega al backend y su respuesta nunca llega a la UI (timeout), o la UI se cierra sin logout (corte de energía, cierre forzado), el token queda válido hasta su logout o el reinicio del backend. Se acepta y se mantiene la decisión 2 (sin expiración propia). Tokens de `secrets.token_urlsafe(32)` (256 bits), solo en memoria del backend y escuchando en 127.0.0.1. Candidato al futuro fichero de gestión de riesgos (NRM-01).
4. **(v7) Bloqueo de un usuario legítimo:** cualquiera con acceso a la pantalla puede bloquear 5 min a un usuario real con 5 intentos fallidos (decisión 10; el bloqueo es por usuario y no revela si existe). Afecta al acceso a Opciones, no a los ciclos: los endpoints operativos no exigen token (decisión 7). Se acepta. Candidato a NRM-01.

## 7. Tareas para Code

| Id | Tarea | Tipo | Estado |
|---|---|---|---|
| T-1 a T-3 | Inventario de endpoints, login y clientes | lectura | hecho |
| **T-9** | Puertas, `/fault/reset` y lectura de parámetros de ciclo | lectura | hecho |
| **T-21** | Migración v1 con `PRAGMA user_version`: tabla `audit_log` (5.10) | código | |
| **T-4** | Módulo de contraseñas (PBKDF2), `POST /auth/login`, `/logout`, `/change_password`, almacén de tokens, bloqueo por intentos, `debe_cambiar_clave`, semillas `admin` e `ingeniero`, roles válidos sin `biomedico` | código | |
| **T-5** | `requiere_rol` y guard de estado (`distinto_de_ciclo`, `distinto_de_ciclo_e_hibernacion` con EMERGENCIA) | código | |
| **T-6** | Aplicar token, rol y guard a los endpoints de 4.4 y 4.5; quitar `usuario` del cuerpo en calibración | código | |
| **T-7** | Host fijo `127.0.0.1` | código | |
| **T-8** | Puente QML: login contra el backend, token por ventana, manejo de 401/403/409, cambio de contraseña obligatorio | código | hecho (`22b72f5`, `30ed280`, `0958f78`) |
| **T-10** | Eliminar `git_autocommit` de calibración y parámetros de ciclo; auditoría de ambos en `audit_log`; borrar `utils/git_autocommit.py` y `tests/test_git_autocommit.py` | código | |
| **T-11** | Eliminar `/io/test/reset_all`, `ticket.txt` y `PATCH /cycle/parameters`, ajustar tests | código | |
| **T-12** | `/outputs/reset` con 409 en CICLO; `/io/test/exit` con 409 fuera de modo prueba | código | |
| **T-13** | Puertas: guard distinto de CICLO y rechazo por sensor faltante (5.3) | código | tras T-9 |
| **T-14** | Simulador: mismo contrato que el backend (decisiones 33 a 35): sesión, cambio de clave, bloqueo con segundos restantes, `/usuarios`, 401/403/409 con código estable; usuarios sembrados por rol y token determinista por sesión `sim-<usuario>-<n>`; pruebas de contrato compartidas contra backend y simulador, con dos sesiones simultáneas y cierre en una | código | hecho (`8e33d64` contrato, `cae6365` simulador) |
| **T-15** | `ciclo_controller.py` con la constante de URL común | código | |
| **T-16** | Fallas: `acknowledge` para todo FALLO, botón QML "Reconocer falla", descarte de `RESET_FALLA` con paro activo (5.9) | código | |
| **T-17** | Copia profunda de parámetros al iniciar el ciclo y regla de fases pendientes (5.8) | código | |
| **T-18** | `request_open` y `request_close` con resultado real (5.3) | código | |
| **T-19** | Eliminar `temp_chaqueta` del mapa de ejecución (`status.py`) y de sus referencias | código | |
| **T-20** | `POST /usuarios` y puente de Nuevo usuario contra el endpoint | código | |

## 8. Criterios de aceptación

1. Escritura de configuración o modo de prueba sin token: 401. Con rol insuficiente: 403.
2. `PATCH /cycle/parameter` y `PATCH /calibration`: 403 para admin y técnico en cualquier estado (solo ingeniero). Para ingeniero en CICLO se aplican según 5.8: un cambio a una fase no iniciada afecta al ciclo en curso; a una fase ya iniciada, solo al siguiente.
2b. Puertas y modo de prueba en HIBERNACION: 409.
3. `PATCH /io/test/output/{name}` fuera de modo prueba, en CICLO, HIBERNACION o EMERGENCIA, o con paro de emergencia: 409. Encender con presión en cámara, con una puerta no CERRADO o sin lectura de presión o de puertas: 409. Apagar dentro del modo prueba: siempre permitido.
4. `/io/test/exit` fuera de modo prueba o desde otra sesión: 409.
5. `/outputs/reset` en CICLO: 409.
6. Puertas en CICLO: 409. Con un sensor que interviene en la operación ausente: rechazo. La apertura automática al final del ciclo sigue funcionando.
7. El backend rechaza conexiones desde otra máquina.
8. Un token invalidado o un reinicio del backend no afecta a un ciclo en curso.
9. Cinco logins fallidos bloquean al usuario 5 min. Cada intento y cada rechazo queda registrado.
10. El primer login de `admin` y de `ingeniero` obliga a cambiar la contraseña; antes de cambiarla, cualquier otra escritura devuelve 403.
10b. `POST /usuarios`: admin no puede crear ingeniero (403); técnico no puede crear usuarios (403); usuario repetido sin distinguir mayúsculas: 409.
11. `/cycle/abort` funciona sin token.
11b. Una falla por `SENSOR_AUSENTE` se puede reconocer desde QML. Un reconocimiento con el paro activo no hace avanzar la máquina al soltar el paro.
11c. Una edición en CICLO a una fase ya iniciada no cambia ningún valor de esa fase en el ciclo en curso.
12. Pruebas automáticas por cada punto y verificación visual de Cristian antes de commitear.

## 9. Decisiones pendientes

Ninguna que bloquee la implementación. Las recomendaciones R-1 a R-9 de la v4 quedaron aprobadas como decisiones 18 a 24; AnyDesk (R-8) pasa a una spec aparte.

## 10. Hallazgos de T-9

| Id | Severidad | Hallazgo |
|---|---|---|
| **OPC-21** | Alta (fuera de alcance) | AnyDesk desatendido permite operar el equipo (ciclos, puertas) sin presencia física. Se trata aparte. |
| **OPC-22** | Alta | Una falla por `SENSOR_AUSENTE` deja la máquina en FALLA sin forma de salir desde QML. |
| **OPC-23** | Alta | `RESET_FALLA` pedido con el paro activo queda guardado y la máquina pasa sola a PREPARACION al soltar el paro, sin acción del operador. |
| **OPC-24** | Media | `request_open` devuelve OK aunque la apertura se cancele por bloqueo o no haya actuador. |
| **OPC-25** | Media | HIBERNACION y EMERGENCIA nunca se alcanzan. La suspensión vive solo en el puente QML; el apagado de salidas debe pasar al backend. Qué hace el paro de emergencia fuera de ciclo se revisa en la spec de alarmas. |
| **OPC-26** | Alta | Los parámetros de ciclo editados con ciclo en curso se aplican al mismo objeto en ejecución; qué valores cambian en vivo es accidental. |

Cerradas: D-2, D-5, D-6, D-7 (modo quiosco con AnyDesk), D-8, D-9.
