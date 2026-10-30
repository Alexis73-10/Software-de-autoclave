# Informe — Autenticación, etapa 1: núcleo de seguridad del backend

**Spec:** `docs/mis_plans/planeacion_backend_autenticacion.md` (v6)
**Fecha:** 2026-10-07
**Rama:** dev, sin commits
**Tareas:** T-21, T-4, T-5, T-6, T-7, T-10, T-11, T-12 y T-20

## Resultado

La suite completa queda en verde: 1964 tests pasan y ninguno se omite. La línea base antes de empezar era de 1881 tests en verde.

## Archivos

**Nuevos**
- `src/autoclave/backend/contrasenas.py`: PBKDF2-HMAC-SHA256 con `hash_password`, `verificar_password` y `simular_verificacion`.
- `src/autoclave/backend/autenticacion.py`: `Sesion`, `AlmacenTokens` y `ControlIntentos`.
- `tests/backend_doble.py`: carga el servidor con un contexto falso y emite tokens por rol para las pruebas.
- `tests/test_backend_autenticacion.py`: 57 tests.
- `tests/test_db_audit_log.py`: 6 tests.

**Modificados**
- `src/autoclave/backend/server.py`
- `src/autoclave/backend/main.py`
- `src/autoclave/services/domain/logging/db_manager.py`
- `src/autoclave/services/domain/loop/control_loop.py`: solo se añade `bloqueo_maquina()`.
- `src/autoclave/ui_pyside/services/roles.py`
- `src/autoclave/ui_pyside/services/validacion_usuario.py`
- `src/autoclave/ui_pyside/services/session_manager.py`: guarda `token` si viene.
- `src/autoclave/ui_pyside/views/nuevo_usuario/puente.py`
- `src/autoclave/ui_pyside/views/nuevo_usuario/vista.py`
- `src/autoclave/ui_qml/domain/permisos_opciones.py`
- `src/autoclave/ui_qml/controllers/login_controller.py`

**Eliminados**
- `src/autoclave/utils/git_autocommit.py`
- `tests/test_git_autocommit.py`

## Qué se hizo por tarea

### T-21 — Migración v1 y `audit_log`
- `DbManager` aplica migraciones numeradas con `PRAGMA user_version`. La base anterior cuenta como v0.
- Cada migración corre en una transacción y, si falla, se revierte entera sin subir la versión. Hay un test que lo comprueba.
- La v1 crea solo `audit_log`, con las columnas de la sección 7 de la spec de parámetros y un índice por `(evento, entidad)`. La v2 queda reservada para esa spec.
- Métodos nuevos: `registrar_auditoria`, `get_auditoria` y `get_version_esquema`.
- `ts` usa reloj de pared, porque es un sello de registro y no un temporizador.
- `sensor_calibration_audit` y `cycle_params_audit` se siguen creando igual, pero ya no reciben escrituras.

### T-4 — Contraseñas, login, logout, cambio de contraseña y semillas
- **Hash:** formato `pbkdf2$600000$sal$hash`, con sal aleatoria de 16 bytes por usuario y comparación con `hmac.compare_digest`. Un hash que no empiece por `pbkdf2$` nunca valida.
- **`POST /auth/login`:**
  - Responde 401 genérico ("Usuario o contraseña incorrectos") si la clave es mala, si el usuario no existe o si está inactivo.
  - Responde 429 con el usuario bloqueado, aunque la clave sea correcta.
  - Si el usuario no existe, gasta el mismo tiempo de hash, para no revelar por el tiempo de respuesta cuáles existen.
  - Devuelve token, usuario, nombre, rol y `debe_cambiar_clave`.
- **Bloqueo por intentos:**
  - 5 fallos consecutivos bloquean al usuario 5 minutos, medidos con `time.monotonic()`.
  - Cuentan también los usuarios inexistentes.
  - El usuario se compara sin distinguir mayúsculas, para que cambiar la capitalización no reinicie el contador.
  - Un login correcto reinicia el contador.
- **Tokens:** `secrets.token_urlsafe(32)` en memoria, uno por login. Un logout invalida solo su token y un reinicio del backend los invalida todos.
- **`POST /auth/change_password`:**
  - Exige la contraseña actual (403 si no coincide).
  - La nueva debe cumplir las reglas de longitud y confirmación de Nuevo usuario y ser distinta de la actual (422 si no).
  - Al aceptarla, baja la bandera `debe_cambiar_clave` en la base y en la sesión activa.
- **Bandera `debe_cambiar_clave`:** mientras esté activa, ese token solo puede usar `change_password` y `logout`; cualquier otra escritura devuelve 403 "Debe cambiar la contraseña".
- **Semillas:** con la tabla `usuarios` vacía se crean `admin` (rol admin) e `ingeniero` (rol ingeniero), ambos con la bandera activa. La columna `debe_cambiar_clave` se añade con el mismo patrón de `ALTER TABLE` que ya usaba la tabla.
- **Roles:** `biomedico` se eliminó de `roles.py` y de `permisos_opciones.py`. Se añadieron `ROL_TECNICO`, `ROL_INGENIERO` y la tabla `ROLES_CREABLES`, que usan el backend y el puente.

### T-5 — `requiere_rol` y guard de estado
- **`requiere_rol(*roles)`:** dependencia de FastAPI.
  - 401 sin token o con token inválido, con la cabecera `WWW-Authenticate: Bearer`.
  - 403 si la sesión debe cambiar la contraseña o si su rol no está entre los permitidos.
  - El rol se toma siempre del token.
- **`guard_estado`:** gestor de contexto con dos variantes, `DISTINTO_DE_CICLO` y `DISTINTO_DE_CICLO_E_HIBERNACION`; esta última también bloquea EMERGENCIA.
  - Toma `_sm_lock` mediante `ControlLoop.bloqueo_maquina()`, comprueba el estado y mantiene el lock durante la escritura.
  - La excepción del ingeniero en CICLO se resuelve dentro del mismo guard.
  - Responde 409 con un motivo legible.
- **Registro de rechazos:** todo 401, 403 o 409 de estas rutas queda en `audit_log` como `rechazo_<código>`, con la ruta y el motivo.

### T-6 — Token, rol y guard en los endpoints
- **`PATCH /calibration/{tipo}/{sensor}`:** solo ingeniero, con guard y excepción del ingeniero. En CICLO aplica de inmediato. El campo `usuario` del cuerpo se ignora y se usa el usuario del token.
- **`PATCH /cycle/parameter`:**
  - Solo ingeniero, con guard y excepción del ingeniero.
  - La respuesta incluye `aplica` y la bitácora guarda `detalle` con programa, fase y `aplica`. Si el cambio se hace en CICLO, añade también ciclo, fase en curso y programa en curso.
  - En CICLO, editar el programa que se está ejecutando devuelve 409 (provisional, ver desviación 1).
- **Modo de prueba (`/io/test/enter`, `/io/test/exit`, `/io/test/output/{name}`):** técnico o ingeniero.
  - `/io/test/enter` se rechaza en CICLO, HIBERNACION y EMERGENCIA, y recuerda qué token entró.
  - Si otra sesión pide entrar con el modo prueba ya activo, recibe 409. Sin esto, le quitaría la propiedad a la sesión que entró.
  - En `/io/test/output`, apagar siempre se permite dentro del modo prueba.
  - Encender exige R-02: `pres_camara` dentro de `presion_admosferica ± rango_presion_atm`, leídos en vivo de la configuración, y todas las puertas en CERRADO. Si falta la lectura de presión, la configuración atmosférica o el estado de las puertas, se rechaza.
  - Se registran `modo_prueba_entra`, `modo_prueba_sale` y `salida_prueba`.
- **Logout:** si la sesión que cierra es la que entró al modo prueba, el backend sale del modo prueba y apaga las salidas (decisión 30).

### T-7 — Host fijo
- `backend/main.py` escucha en `HOST = "127.0.0.1"`, sin configuración.
- El simulador ya usaba `127.0.0.1`.

### T-10 — `git_autocommit` y auditoría
- Se quitó `git_autocommit` de calibración y de parámetros de ciclo, y se borraron el módulo y su test.
- Calibración y parámetros de ciclo se registran en `audit_log` (`calibracion_cambio` y `param_ciclo_cambio`) con el valor anterior y el nuevo.
- `GET /calibration` toma el último cambio de `audit_log` y, si no hay ninguno, de la tabla histórica. Devuelve el mismo formato de fecha que antes.

### T-11 — Endpoints eliminados
- `POST /io/test/reset_all`
- `GET /cycle/history/{id}/ticket.txt`, junto con `_TICKETS_DIR`
- `PATCH /cycle/parameters`

### T-12 — `/outputs/reset` y `/io/test/exit`
- `/outputs/reset` responde 409 en CICLO.
  - El estado se comprueba con `_sm_lock` tomado, pero `stop()` y el apagado de salidas corren fuera del lock. Motivo: `stop()` espera al hilo del loop, que puede estar esperando ese mismo lock.
  - Si un ciclo arrancara justo en ese intervalo, `stop()` lo deja todo apagado, que es el estado seguro.
- `/io/test/exit` responde 409 si el modo prueba no está activo o si lo pide otra sesión.

### T-20 — `POST /usuarios` y puente de Nuevo usuario
- **Endpoint `POST /usuarios`:** requiere token de admin o ingeniero.
  - Reglas de creación según `ROLES_CREABLES`.
  - 422 con `{"errores": {campo: mensaje}}` si falla la validación.
  - 403 si el rol no puede crear el rol pedido.
  - 409 si el usuario ya existe, sin distinguir mayúsculas. También cubre la carrera con el `INSERT`.
  - Guarda el hash PBKDF2 y `creado_por` desde el token, y registra `usuario_creado`.
- **Validación:** `validacion_usuario.py` ya no exige ni valida el Código/ID.
- **Puente (`puente.py`):** ya no toca SQLite.
  - Envía `POST /usuarios` con el token de la sesión, con un timeout de 5 s porque el hash tarda.
  - Traduce 401, 403, 409 y 422 a mensajes por campo.
  - `puedeCrear` acepta admin e ingeniero.
  - `roles` ofrece solo los roles que la sesión puede crear.
  - El parámetro `codigo` se sigue recibiendo, porque la pantalla aún lo envía, pero se ignora.

## Tests añadidos y criterios de aceptación que cubren

| Criterio | Tests |
|---|---|
| 1 (401 sin token, 403 con rol insuficiente) | `test_configuracion_sin_token_401`, `test_cabecera_invalida_401_y_queda_registrada`, `test_sin_token_401`, `test_admin_403`, `test_enter_sin_token_401_y_admin_403` |
| 2 (403 para admin y técnico; ingeniero en CICLO) | `test_configuracion_403_para_admin_y_tecnico_en_cualquier_estado`, `test_ingeniero_calibra_en_ciclo_y_aplica_de_inmediato`, `test_ingeniero_en_ciclo_edita_otro_programa`, `test_ingeniero_en_ciclo_programa_en_curso_409_provisional` |
| 2b (modo prueba en HIBERNACION) | `test_enter_bloqueado_en_ciclo_hibernacion_y_emergencia`, `test_estados_bloqueados_409_incluso_para_apagar`. Las puertas son de la etapa 2. |
| 3 (rechazos de `/io/test/output`) | `tests/test_io_endpoints.py` completo: fuera de modo prueba, estados bloqueados, paro, presión, vacío, sin lectura, sin configuración, puerta no cerrada, sin puertas y apagado siempre permitido |
| 4 (`/io/test/exit`) | `test_exit_fuera_de_modo_prueba_409`, `test_exit_desde_otra_sesion_409`, `test_enter_desde_otra_sesion_con_modo_prueba_activo_409` |
| 5 (`/outputs/reset`) | `test_outputs_reset_409_en_ciclo`, `test_outputs_reset_fuera_de_ciclo` |
| 7 (host) | `test_backend_escucha_solo_en_localhost` |
| 8 (token y ciclo en curso) | `test_token_invalidado_no_afecta_al_ciclo_en_curso`, `test_reinicio_del_backend_invalida_los_tokens` |
| 9 (bloqueo y registro) | `test_cinco_fallos_bloquean_aunque_la_clave_sea_correcta`, `test_usuario_inexistente_tambien_se_bloquea`, `test_bloqueo_dura_cinco_minutos`, `test_cuatro_fallos_no_bloquean_y_el_exito_reinicia`, `test_rechazo_409_queda_en_audit_log` |
| 10 (cambio de contraseña obligatorio) | `test_primer_login_de_semillas_obliga_a_cambiar_clave`, `test_cambio_de_clave_valida`, `test_usuarios_semilla_y_su_contrasena` |
| 10b (`POST /usuarios`) | `test_reglas_de_creacion_por_rol` (7 casos), `test_usuario_repetido_sin_distinguir_mayusculas_409`, `test_usuario_invalido_422_con_errores_por_campo`, `test_usuario_creado_inicia_sesion_y_queda_auditado` |
| 11 (`/cycle/abort` sin token) | `test_abort_funciona_sin_token` |
| §5.5 (lock) | `test_escritura_de_calibracion_dentro_del_lock_de_la_maquina` |
| §5.10 y T-21 | `tests/test_db_audit_log.py` (6 tests), `test_get_calibration_ultimo_cambio_de_audit_log_y_luego_historico` |

## Tests existentes ajustados

| Archivo | Cambio |
|---|---|
| `test_io_endpoints.py` | Se eliminaron los tests de `/io/test/reset_all`, porque la spec elimina el endpoint. El archivo se reescribió con token, modo prueba activo y R-02. |
| `test_io_test_mode_endpoints.py` | Se reescribió con token y sesión dueña. |
| `test_backend_cycle_summary.py` | `test_ticket_txt_con_lecturas` pasa a comprobar que `ticket.txt` devuelve 404, porque la spec lo elimina. |
| `test_backend_calibration_endpoints.py`, `test_backend_cycle_parameter_endpoint.py` | Envían token de ingeniero. Los tests de `git_autocommit` ahora comprueban que ya no existe. La auditoría se comprueba en `audit_log` y no en la tabla histórica. La respuesta incluye `aplica`. |
| `test_git_autocommit.py` | Borrado (decisión del punto 10 de tus respuestas). |
| `test_usuarios_db.py` | La semilla ahora son 2 usuarios. |
| `test_permisos_opciones.py` | `biomedico` pasa a ser un rol que no ve ninguna sección. |
| `test_login_controller.py`, `test_login_qml_autenticacion.py`, `test_opciones_qml.py` | Crean los usuarios con el hash PBKDF2 del backend. |
| `test_nuevo_usuario_puente.py` | Se reescribió contra un backend falso. Los tests de unicidad y escritura en la base pasan a ser responsabilidad del endpoint. |
| `test_nuevo_usuario_qml.py` | Usa un backend falso en lugar de la base. Ya no espera error en el campo Código. |
| `test_flujo_nuevo_usuario.py` | **Borrado**, por indicación tuya: el flujo es 100 % PySide y ya no puede funcionar. |

## Desviaciones y decisiones tomadas sin consultarte

1. **Programa en curso durante CICLO: 409 provisional.** La regla de fases pendientes (§5.8) es T-17, de la etapa 3. Hasta entonces, si el ingeniero edita en CICLO el programa que se está ejecutando, recibe 409. Sin la copia profunda, el cambio mutaría el objeto que usan las fases (OPC-26). Sí puede editar los demás programas, como dice 5b, y calibrar.
2. **Contraseña de la semilla `ingeniero`:** la spec no la define y usé `ingeniero1234`. El hash de las dos semillas va precalculado con una sal fija derivada del nombre de usuario. Es aceptable porque la contraseña semilla es pública y se cambia en el primer login, y evita 600 000 iteraciones cada vez que se crea una base. Cámbiala si prefieres otra.
3. **Login QML (`login_controller.py`):** sigue leyendo SQLite, pero ahora verifica con PBKDF2. Sin esto, tras recrear la base, el login QML habría quedado inutilizable hasta T-8 y no podrías hacer la verificación visual. Pasarlo a `/auth/login` sigue siendo trabajo de la etapa 4.
4. **Crear usuarios desde la pantalla no funcionará de punta a punta hasta la etapa 4.** El puente ya llama a `POST /usuarios` con el token de la sesión, pero ningún login obtiene token todavía: el de PySide no se adapta y el de QML se migra en T-8. Mientras tanto la pantalla muestra "Sesión no válida o vencida; inicie sesión de nuevo".
5. **Campo Código eliminado** de `NuevoUsuario.qml`, del puente (los slots `validar` y `guardar` ya no lo reciben) y de sus tests. Estado y los botones ocupan su lugar, según `images/nuevo_usuario_sin_codigo.png`. "Nivel de acceso", que aparece en ese mockup, no se añadió (D-01).
6. **Cambio de contraseña con la clave actual errónea:** devuelve 403 y queda registrado, pero no cuenta para el bloqueo de 5 intentos, que la spec solo define para el login.
7. **`/outputs/reset` al cerrar Tk durante un ciclo:** ahora recibe 409. **Corrección tras la revisión de seguridad:** Tk captura el error pero después termina el proceso del backend, así que el ciclo se corta igual, ahora sin apagar las salidas. Ver hallazgo B en `autenticacion_etapa1_revision_seguridad.md`.
8. **PySide sin adaptar,** como estaba previsto. Pierde calibración, parámetros de ciclo, secado (`/cycle/parameters`), modo prueba y creación de usuarios. Además, `admin_menu.py` solo muestra "Nuevo usuario" al admin, aunque ahora el ingeniero también puede crear.

## Verificación sugerida antes de commitear

- Recrear la base de desarrollo. Al arrancar se crean `admin`/`admin1234` e `ingeniero`/`ingeniero1234`.
- Login QML con ambos usuarios.
- Comprobar que el backend ya no responde desde otra máquina de la red.
- Se ejecutaron `safety-reviewer` y `timing-auditor`: ver `autenticacion_etapa1_revision_seguridad.md`. **No commitear hasta corregir los hallazgos A a D.**
