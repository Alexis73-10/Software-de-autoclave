# Plan etapa 4 (T-8 + T-14) — Login QML contra el backend (Fase 1, solo plan)

**Estado:** cerrado (2026-10-08): implementado en `8e33d64`, `cae6365`, `22b72f5`, `30ed280`, `0958f78` (SAF-01) y el refactor de `SessionManager` (§9).
**Versión:** v5.1 — aprobada para implementar (2026-10-08): renombre en commit 1; simulador nace con `/usuarios` y `clave` en commit 2; contrato verifica nombres de campo del 422 en ambos; etiquetas fijas de `Login.qml` registradas en el plan de idiomas (`planeacion_opciones.md` §11); bloqueo de usuario legítimo como riesgo residual 4 de la spec y candidato NRM-01; prueba "Admin"/"admin" con contador y respuesta compartidos
**Spec:** `docs/mis_plans/planeacion_backend_autenticacion.md` v7 (en revisión: decisiones 33-35, §4.1 con `GET /auth/sesion` e `igual_actual`, §6 riesgo residual 3, T-14)
**Rama:** `dev` (HEAD `dd8f107`). Sin cambios de código, ramas ni commits en esta fase.
**Informe previo:** `docs/mis_plans/informe_estado_opciones.md` (A1, A4, A5, G3, OPC-27)

---

## 0. Decisiones tomadas

| # | Tema | Decisión |
|---|---|---|
| R1-1 | Nuevo usuario | En QML, con el token de la ventana |
| R1-2/R2-8 | Cambio de clave | Composición del Login, tres campos, teclados y reglas de Nuevo usuario |
| R1-3 | Abandonar el cambio | Permitido; el siguiente login vuelve a obligar |
| R1-4 | Suspensión | Standby de la UI y HIBERNACION |
| R1-6 | Hilo y timeout | Hilo aparte, una operación en vuelo, plazo total 5 s, reglas por operación (§3.2) |
| R1-8 | Logout al cerrar la app | Sí |
| R1-11 | Mensajes | `es.json`, claves por causa, texto idéntico al actual; sin `en.json` |
| R1-12 | `SessionManager` | En su sitio en T-8; refactor posterior (§9) |
| R2-1 | Login vencido | El backend cuenta el intento (aceptado) |
| R2-2 | Bloqueo | 429 con código, segundos y `Retry-After`; el 5.º fallo es 429; la clave correcta no cuenta |
| R2-3 | Al perder conexión | Principal según estado (preciclo / ciclo en curso) |
| R2-5 | Nuevo usuario en OPCIONES | Pantalla completa desde un botón en Usuarios; "<" vuelve a Usuarios |
| R2-6 | Menú PySide | Quitar solo la entrada, commit aparte; el puente se conserva |
| R2-7 | Commits | Contrato del backend primero, con pruebas |
| R2-9 | Mensajes | Todo por clave; 422 por campo y código; 403/409 por código; desconocido → `error_generico` + log |
| R2-10 | Simulador | Usuarios por rol, uno con clave pendiente y uno para bloqueo; token `sim-<usuario>-<n>` por sesión |
| R3-1 | Token huérfano | Aceptado sin expiración (decisión 2); riesgo residual 3 de la spec |
| R3-2 | `GET /auth/sesion` | Aprobado: 200 `{usuario, rol}` o 401 estándar; una vez al reconectar; endpoint de autenticación |
| R3-3 | Alcance de códigos | Commit 1: todo lo que pasa por `_rechazar`/`_Rechazo` y todos los endpoints de las pantallas de T-8, con sus 422. Resto después |
| R3-4 | Pérdida de conexión | Toda pantalla con token en uso: OPCIONES, Nuevo usuario, Cambio de clave. En el cambio obligatorio, el cierre vuelve al Login y descarta el token |
| R3-5 | Usuarios | Visible para admin e ingeniero (corregido en `planeacion_opciones.md` v4 §2 y §3.6) |
| R3-6 | Clave igual a la actual | Se mantiene, con código propio `igual_actual` en `clave_nueva` (backend y simulador) |
| R3-7 | Cuerpo de errores | Aprobado con cambios: `sesion_invalida`; 422 con lista `{campo, codigo}` |
| R3-8 | Textos | Aprobados los de §6.2 marcados "aprobado"; añadidos `clave_pudo_cambiar`, `confirmar_clave_nueva`, `usuario_bloqueado` |
| R4-1 | H-T8-01 | Aprobado, commit 1: fallos de `clave_actual` suman al contador del login; al 5.º, 429 con el mismo cuerpo e invalidación del token; un cambio exitoso reinicia el contador. Cambio de clave ante 429: cierra sesión, vuelve al Login y muestra el bloqueo con cuenta regresiva. Pruebas de contrato en backend y simulador |
| R4-2 | Cambio obligatorio sin conexión | Se descarta el token sin enviar nada; registro en el log local |
| R4-3 | Textos | Todos los propuestos aprobados o fijados (§6.2). El Login usa mayúsculas en título y botón: "LOGIN" (`Login.qml:117`) e "INICIAR SESIÓN" (`:339`) |
| R4-4 | Fichero de riesgos | No se crea. Token huérfano y H-T8-01 añadidos como candidatos en NRM-01 (`hallazgos_nrm.md`) |
| R4-5 | Renombre `password` → `clave` | En el mismo commit que actualiza el puente de Nuevo usuario, el simulador y las pruebas (§5) |

---

## 1. Qué dice la spec

Citas de la v6 sin cambios (decisiones 2, 3, 5, 8, 10, 11, 15, 29, 31; §4.1; §5.1; §5.7; §7 T-8 y T-14; §8 criterios 9, 10, 12; texto completo en la v2 de este plan). La v7 (en revisión) añade las decisiones 33-35, `GET /auth/sesion` e `igual_actual` en §4.1, el riesgo residual 3 en §6 y el texto nuevo de T-14.

---

## 2. Estado actual del flujo y verificaciones

Tabla de la v2 sin cambios (LoginController, SessionManager, OpcionesController, puente de Nuevo usuario, Login.qml, Main.qml, Opciones.qml, conexión, acceso HTTP, simulador, backend). Verificaciones de esta ronda:

| Verificación | Resultado | Evidencia |
|---|---|---|
| Generación del token | `secrets.token_urlsafe(32)`: 32 bytes aleatorios = **256 bits** (≥ 128). Solo en memoria del backend. | `backend/autenticacion.py:10, 38` |
| Expiración | Ninguna: solo `emitir`, `obtener`, `invalidar`, `clave_cambiada`. | `autenticacion.py:29-58` |
| Usuario inexistente y bloqueo (R3-7b) | **Sí acumula, con la misma respuesta.** El intento se reserva con la clave `casefold` del nombre escrito antes de buscarlo en la BD; un usuario inexistente o inactivo (la búsqueda filtra `activo=1`) pasa por `simular_verificacion()`, que gasta el mismo tiempo que un PBKDF2 real; la respuesta es el mismo 401, y con el contrato v7 el 5.º fallo y los siguientes dan el mismo 429 con los mismos segundos. No revela existencia por código, cuerpo ni tiempo. | `server.py:232-250`; `autenticacion.py:80-82, 99-111`; `contrasenas.py:50-53`; `db_manager.py:601-607` |
| Observación (no hallazgo) | Cualquiera puede bloquear 5 min a un usuario real con 5 intentos (inherente a la decisión 10). La columna `usuario` es `UNIQUE` sin `COLLATE NOCASE` (`db_manager.py:104`): "Admin" no encuentra a "admin" pero comparte su contador; la respuesta es igual, sin fuga. | |
| `clave_actual_incorrecta` y bloqueo (R3-7c) | **No cuenta.** `change_password` verifica la clave actual sin tocar `intentos_login`: con un token válido se pueden probar claves actuales sin límite. **Hallazgo H-T8-01** (§8), propuesta en §3.4. | `server.py:288-294` |
| `:592` | `POST /cycle/select`: 409 con el `reason` de `control_loop.set_active_cycle` (rechazo en CICLO). Lo usa `UIServiceBackend.select_cycle` (`ui/service_ui/ui_service_backend.py:314`), es decir, el selector de programa de preciclo y Tk. **OPCIONES no lo usa.** | `server.py:582-596` |
| `:779` | `_encolar_en_impresora`, usado por `POST /cycle/history/print` y `POST /report/summary/print`: 409 durante un ciclo (y 503 con `detail.impresora`). Lo usan Historial y Reportes del Menú Principal (`ui_qml/bridge/acciones_ciclos.py:165, 174`). **OPCIONES no lo usa.** | `server.py:769-790, 833` |
| Fichero de gestión de riesgos | **No existe** (P-02 / NRM-01, `planeacion_auditoria_iec62304.md:256`, `hallazgos_nrm.md:9`). El riesgo residual del token huérfano se registró en la spec §6 (riesgo 3) y se marca como candidato al futuro fichero. | |

---

## 3. Diseño

### 3.1 Token
En `SessionManager`, fuera del dict de `current_user()`, accesor `token()`, `id` opcional, bandera `debe_cambiar_clave`. Nunca en disco ni logs; prueba de `repr` y `caplog`.

### 3.2 Cliente de sesión, hilo y timeout
Sin cambios respecto a la v2 (capa pura y capa Qt `OperacionSesion`; `ocupado`; plazo total 5 s con `QTimer`; descarte de respuestas tardías; logout del token tardío; logout que borra lo local siempre y registra en el log local; cambio de clave sin reintento → `clave_pudo_cambiar`). Tabla de pruebas de timeout de la v2 vigente. Token huérfano: aceptado (R3-1).

### 3.3 Cambio de contraseña obligatorio
- `POST /auth/change_password` con `{clave_actual, clave_nueva, confirmacion}`. Pantalla `CambioClave.qml`: composición de `Login.qml`, campos actual / nueva / confirmación (`confirmar_clave_nueva`), teclado alfanumérico, longitudes `PASSWORD_MIN`/`PASSWORD_MAX`.
- Abandonar: logout y principal; la bandera persiste en la BD (`db_manager.py:609-616`).
- Clave nueva igual a la actual: 422 `igual_actual` en `clave_nueva` (R3-6), en backend y simulador.
- 429 en el cambio de clave (R4-1): el backend ya invalidó el token; la UI borra la sesión local sin enviar logout, vuelve al Login y muestra `sesion.usuario_bloqueado` con la cuenta regresiva desde `segundos_restantes`.

### 3.4 Contrato de errores — cuerpo final (aprobado con cambios R3-7)

**Forma común** (`detail` sigue siendo texto para `door_command_service.py:43-49` y Tk):
```json
{ "detail": "<texto en español actual>", "codigo": "<código estable>" }
```

**429:**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 287

{ "detail": "Usuario bloqueado por intentos fallidos; espere 5 minutos",
  "codigo": "usuario_bloqueado",
  "segundos_restantes": 287 }
```
Entero, redondeo hacia arriba, mínimo 1, igual a `Retry-After`. El 5.º fallo responde 429 con 300. La clave correcta no cuenta (ya es así: `autenticacion.py:104-106, 113-117`; prueba explícita nueva).

**401:** `credenciales_invalidas` (login, `server.py:250`); `sesion_invalida` (token ausente o inválido, `:143`, `:1162`; renombrado desde `sesion_vencida`).

**403:** `clave_pendiente` (`:146`), `rol_sin_permiso` (`:148`), `clave_actual_incorrecta` (`:294`), `rol_no_creable` (`:333`).

**409 por `_rechazar`/`_Rechazo`:** `estado_no_permitido` + `"estado"` (`:172`), `configuracion_invalida` (`:183`, `:1159`), `usuario_existe` (`:335`, `:344`), `programa_en_curso` (`:1094`), `modo_prueba_otra_sesion` (`:1166`), `modo_prueba_inactivo` (`:1183`, `:1258`), `modo_prueba_no_dueno` (`:1185`, `:1265`), `paro_emergencia` (`:1260`), `modo_prueba_rechazado` (`:1169`, `:1268`, motivo variable en `detail`).

**422 de `change_password` y `POST /usuarios`** (completo):
```json
{ "detail": "Datos inválidos",
  "codigo": "validacion",
  "errores": [
    { "campo": "clave_nueva",  "codigo": "corta" },
    { "campo": "confirmacion", "codigo": "no_coinciden" }
  ] }
```
- `campo` = nombre del campo del cuerpo de la petición:
  - `POST /auth/change_password`: `clave_actual`, `clave_nueva`, `confirmacion`.
  - `POST /usuarios`: `nombre`, `usuario`, `clave`, `confirmacion`, `rol`. (Hoy el backend usa `password` para la clave, `server.py:296-300`; pasa a `clave`, que es el campo del cuerpo `_NuevoUsuarioBody`.)
- `codigo` por campo: `obligatorio`, `formato` (solo `usuario`), `corta`, `larga`, `no_coinciden` (solo `confirmacion`), `rol_invalido` (solo `rol`), `igual_actual` (solo `clave_nueva`).
- Un error por campo, en el orden de los campos del cuerpo. Los límites (`{min}`, `{max}`) no viajan: la UI los toma de `validacion_usuario.py` (`NOMBRE_MAX`, `USUARIO_MIN/MAX`, `PASSWORD_MIN/MAX`), la misma fuente que el backend.
- 422 de FastAPI por cuerpo mal formado (lista en `detail`, sin `codigo`) → `error_generico` + log.

**Endpoints de las pantallas de T-8 cubiertos en el commit 1:** `POST /auth/login` (401, 429; 422 de FastAPI sin código), `POST /auth/logout` (401), `POST /auth/change_password` (401, 403, 422), `POST /usuarios` (401, 403, 409, 422), `GET /auth/sesion` (401). Fuera: `:592`, `:779` y los 422 de texto (`:434, 588, 1084, 1100, 1102`), que la UI trata como desconocidos.

**H-T8-01 (aprobado, commit 1):** `change_password` usa el mismo `ControlIntentos` con la clave del usuario de la sesión:
- reservar el intento antes de verificar la clave actual (como el login);
- usuario ya bloqueado → 429 `usuario_bloqueado` sin verificar;
- clave actual incorrecta → 403 `clave_actual_incorrecta`, o 429 si con ese fallo llega al 5.º;
- clave actual correcta (con o sin error de validación después) → `registrar_exito`: un cambio exitoso reinicia el contador;
- al bloquearse, se invalida el token de esa sesión (logout forzado, evento `login_bloqueado` con `{"origen": "cambio_clave"}`).
El contador es compartido con el login: 5 fallos en total entre ambos bloquean 5 min.

**Cliente:** `codigo` → clave `es.json`; 422 → `validacion.<codigo>` en el campo; desconocido → `error_generico` + `logger.error` con estado HTTP, ruta y código (sin cuerpo ni datos del formulario).

### 3.5 Bloqueo en la UI
`sesion.usuario_bloqueado` con `{tiempo}` en `m:ss`; cuenta regresiva local con `time.monotonic()` desde `segundos_restantes`; sin consultas; a 0 solo se habilita el botón. Un timeout nunca produce esta causa.

### 3.6 Logout
Un único `cerrar_sesion()`: Salir, cambio de clave, Nuevo usuario, login nuevo, standby, HIBERNACION (`puente.machineState`), cierre de la app (`_al_salir`, plazo corto).

### 3.7 Pérdida de conexión (R2-4, R3-2, R3-4)
**Ámbito:** toda pantalla con token en uso: OPCIONES, Nuevo usuario y Cambio de clave. Fuera de ellas no aplica (la sesión puede seguir abierta en memoria mientras se está en preciclo; se valida al volver, ver abajo).

**Secuencia:**
1. Primer `puente.connected == false`: el cliente rechaza las escrituras sin salir a la red (causa `backend_no_responde`), botones de guardar deshabilitados y aviso `sesion.sin_conexion_escrituras`.
2. **Variante con cuenta regresiva:** junto al aviso, `sesion.sin_conexion_cierre` con `{tiempo}` en `m:ss`, desde `0:15` hasta `0:00`, calculado localmente con `time.monotonic()` desde el primer sondeo fallido (sin consultas adicionales). Constante única `SIN_CONEXION_CIERRE_S = 15` en `ui_qml/sesion_backend.py`.
3. **Reconexión antes de 15 s:** una sola llamada a `GET /auth/sesion`. 200 → se quitan aviso y bloqueo; 401 → cierre de sesión y principal (en Cambio de clave obligatorio: Login).
4. **15 s continuos sin conexión:** cierre de sesión local. OPCIONES y Nuevo usuario → principal según estado (`Main.qml volverAPrincipal`, `:226-229`). Cambio de clave obligatorio → Login; el token se descarta sin enviar nada y se registra en el log local (`logger.warning("Token descartado sin conexión durante el cambio obligatorio de contraseña")`, sin el token) (R4-2).
5. Tras el cierre por 15 s desde OPCIONES o Nuevo usuario, al reconectar: `POST /auth/logout` con el token guardado aparte.

`GET /auth/sesion`: 200 `{"usuario": "...", "rol": "..."}`; 401 con el cuerpo común (`sesion_invalida`) y `WWW-Authenticate: Bearer`. Permitido con clave pendiente (como logout y change_password), porque Cambio de clave también valida al reconectar. El 200 no se audita; el 401 queda como `rechazo_401` (lo hace `requiere_rol`). Se llama una vez por reconexión, nunca en sondeo.

---

## 4. Nuevo usuario en OPCIONES › Usuarios
- Usuarios visible para admin e ingeniero: `permisos_opciones.py:22, 41` (`_SOLO_ADMIN` → `{admin, ingeniero}`), commit 3. Corrección ya hecha en `planeacion_opciones.md` v4 §2 (columna I = E) y §3.6.
- Botón `opciones.nuevo_usuario` → `push` de `NuevoUsuario.qml` a pantalla completa. Navegación del puente: `admin_menu` ("<", Cancelar) → `pop` a OPCIONES en Usuarios; `home` (Inicio) → principal conservando la sesión; `salir()` → `cerrar_sesion()` y principal.
- `NuevoUsuarioBridge` creado en `app.py`, con el cliente de sesión; errores por clave.

---

## 5. Orden de la etapa y commits

| # | Commit | Contenido | Cierra de R-2 |
|---|---|---|---|
| 1 | Contrato del backend | `RechazoApi` + manejador; códigos de §3.4; 429 con segundos y `Retry-After` (5.º fallo incluido); 422 en lista `{campo, codigo}` con nombres de campo del cuerpo; `igual_actual`; `GET /auth/sesion`; H-T8-01; `validacion_usuario.py` por códigos con envoltura de texto para PySide; renombre del campo de error `password` → `clave` en `/usuarios` junto con la adaptación mínima de `NuevoUsuarioBridge._errores_de` (lista `{campo, codigo}`, `clave` → campo de contraseña de la pantalla) y sus pruebas (R4-5, pregunta 1); `tests/contrato_autenticacion.py` contra el backend; ajustes de `test_backend_autenticacion.py` | congela el contrato |
| 2 | T-14 | Simulador con el contrato completo (incluidos `GET /auth/sesion`, `igual_actual`, bloqueo con segundos); usuarios por rol en memoria (uno con clave pendiente, uno para bloqueo); `ControlIntentos` reutilizado; token `sim-<usuario>-<n>`; batería de contrato también contra el simulador, con dos sesiones simultáneas y cierre en una | parte servidor |
| 3 | T-8 | Cliente, `SessionManager`, controladores, `Login.qml`, `CambioClave.qml`, `Main.qml`, `Opciones.qml`, `NuevoUsuario.qml`, `permisos_opciones.py`, `app.py`, `es.json`; retiro de la envoltura de texto | parte cliente |
| 4 | Menú PySide | Quitar la entrada "Nuevo usuario" (`admin_menu.py:20, 26, 31`); ajustar `test_admin_menu_nuevo_usuario.py` | — |
| — | Verificación visual | T-8 contra el simulador | cierra R-2 |
| 5 | Refactor posterior | Reubicación de `SessionManager` (§9) | — |

`server.py` tiene hunks sin commit del enlace serial A1/A2: el commit 1 incluye solo los de este contrato.

---

## 6. Archivos, claves i18n y pruebas

### 6.1 Archivos
| Archivo | Commit |
|---|---|
| `backend/server.py`, `backend/autenticacion.py`, `ui_pyside/services/validacion_usuario.py` | 1 |
| `simulador/servidor.py`, `simulador/autenticacion_simulada.py` (nuevo) | 2 |
| `ui_qml/sesion_backend.py` (nuevo), `ui_pyside/services/session_manager.py`, `ui_qml/controllers/{login,opciones}_controller.py`, `ui_pyside/views/nuevo_usuario/puente.py`, `ui_qml/qml/Pantallas/{Login,CambioClave,Opciones,NuevoUsuario}.qml`, `ui_qml/qml/Main.qml`, `ui_qml/domain/permisos_opciones.py`, `ui_qml/app.py`, `ui_qml/assets/textos/es.json`, `ui_pyside/services/validacion_usuario.py` | 3 |
| `ui_pyside/views/admin_menu.py` | 4 |

### 6.2 Claves en `es.json` (tabla completa)

**Sección `sesion`**
| Clave | Texto | Estado |
|---|---|---|
| `campos_vacios` | Ingrese usuario y contraseña | idéntico al actual (`login_controller.py:24`) |
| `credenciales_invalidas` | Usuario o contraseña incorrectos | idéntico al actual (`login_controller.py:25`); único para usuario inexistente y clave incorrecta |
| `usuario_bloqueado` | Usuario bloqueado por intentos fallidos. Intente de nuevo en {tiempo} | aprobado (R3-8); `{tiempo}` en `m:ss` |
| `backend_no_responde` | El equipo no responde; intente de nuevo | aprobado |
| `clave_pendiente` | Debe cambiar la contraseña | idéntico al backend (`server.py:146`) |
| `sesion_invalida` | Sesión no válida o vencida; inicie sesión de nuevo | idéntico al actual (`puente.py:27`, `server.py:143`) |
| `clave_actual_incorrecta` | La contraseña actual no es correcta | aprobado |
| `clave_pudo_cambiar` | No se pudo confirmar el cambio de contraseña. Inicie sesión con la contraseña nueva; si no funciona, use la anterior. | aprobado (R3-8) |
| `sin_conexion_escrituras` | Sin conexión con el equipo: no se pueden guardar cambios | aprobado |
| `sin_conexion_cierre` | La sesión se cerrará en {tiempo} si no vuelve la conexión | aprobado (R4-3; variante de cuenta regresiva, §3.7) |
| `validando` | Validando… | aprobado (R4-3) |
| `error_generico` | No se pudo completar la operación | aprobado |
| `rol_sin_permiso` | Su rol no tiene permiso para esta acción | idéntico al backend (`server.py:148`) |
| `titulo_cambio_clave` | CAMBIAR CONTRASEÑA | fijado (R4-3) |
| `aviso_cambio_obligatorio` | Debe cambiar su contraseña antes de continuar | fijado (R4-3) |
| `clave_actual` | Contraseña actual | aprobado (R4-3) |
| `clave_nueva` | Contraseña nueva | aprobado (R4-3) |
| `confirmar_clave_nueva` | Confirmar contraseña nueva | aprobado (R3-8) |
| `boton_cambiar_clave` | CAMBIAR CONTRASEÑA | aprobado (R4-3): el Login usa mayúsculas en título y botón (`Login.qml:117, 339`) |

**Sección `usuarios`** (Nuevo usuario)
| Clave | Texto | Estado |
|---|---|---|
| `sin_permiso` | Su rol no puede crear usuarios | idéntico al actual (`puente.py:26`) |
| `guardado_error` | No se pudo guardar el usuario | idéntico al actual (`puente.py:28`) |
| `rol_no_creable` | Su rol no puede crear usuarios con ese rol | idéntico al backend (`server.py:333`) |
| `usuario_existe` | El usuario ya existe | idéntico al actual (`validacion_usuario.py:18`) |

**Sección `validacion`** (por código del 422 y validación local)
| Clave | Texto | Estado |
|---|---|---|
| `obligatorio` | Campo obligatorio | idéntico (`validacion_usuario.py:16`) |
| `formato` | Sin espacios, de {min} a {max} caracteres | idéntico (`:17`) con marcadores |
| `corta` | Mínimo {min} caracteres | idéntico (`:19`) con marcador |
| `larga` | Máximo {max} caracteres | idéntico (`:20`, `:23`) con marcador |
| `no_coinciden` | Las contraseñas no coinciden | aprobado; idéntico (`:21`) |
| `rol_invalido` | Seleccione un rol | idéntico (`:22`) |
| `igual_actual` | La nueva contraseña debe ser distinta de la actual | aprobado; idéntico al backend (`server.py:302`) |

**Sección `opciones`**
| Clave | Texto | Estado |
|---|---|---|
| `nuevo_usuario` | Nuevo usuario | fijado (R4-3) |

Los códigos 409 que no usan las pantallas de T-8 (`estado_no_permitido`, `configuracion_invalida`, `programa_en_curso`, `modo_prueba_*`, `paro_emergencia`) se codifican en el backend en el commit 1, pero sus claves de `es.json` se añaden con las pantallas que los usen; hasta entonces caen en `error_generico`. Sin `en.json`.

### 6.3 Pruebas
| Prueba | Commit |
|---|---|
| `tests/contrato_autenticacion.py` (backend y simulador): H-T8-01 (fallos de `clave_actual` suman al contador del login, 429 al 5.º con el mismo cuerpo, token invalidado tras el 429, cambio exitoso reinicia el contador, login y cambio de clave suman entre sí); login 200; 401 `credenciales_invalidas`; usuario inexistente con las mismas respuestas 401 y 429 que uno existente; 5.º fallo 429 con 300 y `Retry-After`; clave correcta no cuenta; 401 `sesion_invalida`; 403 `clave_pendiente`; cambio de clave 403 / 422 lista / `igual_actual` / 200; `/usuarios` 403 / 409 / 422 lista; `GET /auth/sesion` 200 `{usuario, rol}` (también con clave pendiente) y 401; dos sesiones simultáneas y logout en una | 1 y 2 |
| `test_backend_autenticacion.py`: `:111-120` (429 en el 5.º), `:463` (422 lista), códigos | 1 |
| Envoltura de `validacion_usuario` (textos idénticos a los de hoy) | 1 |
| `test_sesion_backend.py` (timeouts de la v2; `SIN_CONEXION_CIERRE_S` con reloj inyectable), `test_login_controller.py`, `test_login_qml_backend.py`, `test_cambio_clave_qml.py`, navegación de `Main.qml` (standby, HIBERNACION, desconexión: 1.er sondeo, cuenta regresiva, reconexión con 200 y 401, cierre a 15 s en OPCIONES / Nuevo usuario / Cambio de clave), Nuevo usuario desde OPCIONES, `test_permisos_opciones.py` (Usuarios para ingeniero) | 3 |
| `test_admin_menu_nuevo_usuario.py` | 4 |

---

## 7. Impacto en pruebas existentes
v2 §7 y v3 §7, más `test_permisos_opciones.py` y `test_opciones_qml.py` (el ingeniero ve Usuarios).

---

## 8. Riesgos y hallazgos
- **H-T8-01 (Alto, nuevo).** `POST /auth/change_password` no cuenta los fallos de la clave actual (`server.py:288-294`): quien tenga una sesión abierta ajena puede probar contraseñas sin límite y averiguar la clave del usuario. Propuesta en §3.4. Candidato al fichero de riesgos (NRM-01).
- **R-5 (aceptado, R3-1).** Token huérfano sin expiración; registrado como riesgo residual 3 en la spec.
- **R-10.** `server.py` con hunks ajenos sin commit.
- **R-13 (resuelto por R4-5):** el puente se adapta al 422 nuevo en el mismo commit 1, así que no hay estado intermedio roto.
- **R-14.** Token del simulador predecible: solo herramienta de desarrollo en 127.0.0.1; prueba de que el backend no importa `simulador/`.
- **R-16. Renombre `password` → `clave`:** el **cuerpo** de `POST /usuarios` ya usa `clave` (`server.py:312-318`, `puente.py:119-120`); lo que cambia es solo la clave del campo en los errores del 422 (`server.py:296-300, 328-331`). Afecta a `puente.py:142-143` y a `NuevoUsuario.qml` (que muestra el error de la contraseña).
- **Bloqueo de usuarios legítimos** con 5 intentos (decisión 10); con H-T8-01 aprobado, también desde el cambio de clave.
- R-7, R-11, R-12 de la v2 siguen vigentes.

---

## 9. `SessionManager`
Sin cambios (v2 §8). Propuesta `autoclave/ui/service_ui/session_manager.py`, en commit de refactor posterior a T-8.

---

## 10. Preguntas bloqueantes
1. **Commit del renombre (R4-5):** el cuerpo de `POST /usuarios` ya usa `clave`; solo cambia la clave del campo en los errores del 422. El simulador hoy no tiene `/usuarios`, así que en el commit 1 no hay nada que actualizar en él: nace con `clave` en el commit 2. Propuesta: renombre en el commit 1 junto con la adaptación del puente y sus pruebas, y el simulador lo replica en el commit 2 (la batería de contrato lo verifica). ¿Se acepta, o se adelanta `/usuarios` del simulador al commit 1?

**Observación, no bloqueante:** `Login.qml` tiene textos fijos en el QML fuera de `es.json` ("LOGIN" `:117`, "Inicie sesión para continuar" `:142`, "Recordar Usuario" `:299`, "INICIAR SESIÓN" `:339`, "¿Olvidó su contraseña?" `:365`; ya existen `acciones.iniciar_sesion`, `formulario.recordar_usuario` y `formulario.olvido_contrasena`). R1-11 pidió pasar a `es.json` los mensajes, no las etiquetas; se dejan como están salvo indicación.
