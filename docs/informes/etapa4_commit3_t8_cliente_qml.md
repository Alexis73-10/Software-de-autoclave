# Etapa 4 — Commit 3: T-8, login QML contra el backend

**Fecha:** 2026-10-08 · **Rama:** `dev` (sobre `cae6365`) · **Plan:** `docs/mis_plans/plan_t8_login_qml.md` v5.1, §3, §4 y §5 (commit 3)
**Suite:** 2119 pruebas en verde (`python -m pytest -q tests`, 3 min 22 s). **Sin commit:** falta la verificación visual de Cristian contra el simulador.

## Qué se hizo

| Pieza | Cambio |
|---|---|
| `ui_qml/sesion_backend.py` (nuevo) | Sesión de la ventana (una por proceso). Capa pura: `llamar()` traduce cada respuesta a una causa estable (código del backend, `backend_no_responde` o `error_generico` con registro). `OperacionSesion`: login y cambio de contraseña en un hilo, una sola operación en vuelo, plazo total de 5 s medido en el hilo de la GUI, descarte de respuestas tardías (y logout del token de un login tardío). `SesionVentana`: abre y cierra la sesión en `SessionManager`, logout en segundo plano que siempre cierra lo local, logout síncrono al salir (1 s), escrituras con token (`enviar`), avisos para el login y vigilancia de conexión (§3.7). |
| `SessionManager` | El token sale del dict de `current_user()` (accesor `token()`); `id` opcional; bandera `debe_cambiar_clave` y `clave_cambiada()`. |
| `LoginController` / `Login.qml` | Sin SQLite. Mensajes por clave de `es.json`; "Validando…" y botón deshabilitado en vuelo; bloqueo con cuenta regresiva local m:ss; señal `cambioClaveRequerido`. |
| `CambioClaveController` / `CambioClave.qml` (nuevos) | Composición del Login, tres campos, reglas de Nuevo usuario e `igual_actual`; 429 / sin respuesta / 401 cierran la sesión y vuelven al Login con su aviso; Salir e Inicio abandonan con logout. |
| `OpcionesController` / `Opciones.qml` | Salir hace logout; `cambioClavePendiente`; sección Usuarios con botón "Nuevo usuario" (admin e ingeniero). |
| Nuevo usuario | El puente vive en el proceso QML, escribe por `SesionVentana.enviar` y devuelve errores por clave; `NuevoUsuario.qml` los traduce y ahora muestra el error general. Se abre a pantalla completa sobre OPCIONES; "<" y Cancelar vuelven a Usuarios. Retirada la envoltura de textos de `validacion_usuario.py` (`error_ui` en su lugar). |
| `Main.qml` | Login → cambio obligatorio → OPCIONES; `abrirConfiguracion` respeta la bandera; standby y HIBERNACION cierran con logout; vigilancia de conexión en pantallas con token (OPCIONES, Nuevo usuario, Cambio de clave) con aviso y cuenta regresiva de 15 s; 401 → Login. |
| `app.py` | Crea e instala la sesión de la ventana y el puente de Nuevo usuario; logout al salir. |
| `permisos_opciones.py` | Usuarios visible para admin e ingeniero. |
| `es.json` | Secciones `sesion`, `usuarios`, `validacion` y `opciones.nuevo_usuario` (textos aprobados). |

## Decisión tomada en la implementación (a confirmar)

**El bloqueo deshabilita el botón solo para el usuario bloqueado** (`usuarioBloqueado`, sin distinguir mayúsculas). El plan decía "al llegar a cero solo se habilita el botón"; aplicado a todos los usuarios, un usuario bloqueado dejaba esa pantalla sin acceso 5 minutos para cualquiera (el bloqueo del backend es por usuario). La cuenta regresiva y el mensaje se muestran igual.

## Pruebas

- **Nuevas:** `test_sesion_backend.py` (29: causas, token fuera de logs y `repr`, bloqueo con reloj inyectado, **los cuatro timeouts** con hilos reales y plazo reducido, transporte real contra un socket que nunca responde, escrituras con token, vigilancia de conexión), `test_cambio_clave_controller.py` (11), `test_navegacion_sesion_qml.py` (11: carga real de `Main.qml` con la sesión inyectada).
- **Reescritas:** `test_login_controller.py` (contra el backend real vía `TestClient`) y `test_login_qml_autenticacion.py` (**login QML contra el backend real**: textos desde `es.json`, "Validando…" con botón deshabilitado, auditoría `login_ok`/`login_fallido`, bloqueo con 5:00, semilla admin → cambio).
- **Ajustadas:** `test_nuevo_usuario_puente.py`, `test_nuevo_usuario_qml.py`, `test_opciones_qml.py`, `test_permisos_opciones.py`, `test_session_manager.py`.
- **Humo con HTTP real** contra el simulador en uvicorn: credenciales inválidas, cambio obligatorio, cambio de clave, `/usuarios`, logout que invalida el token (401 después) y bloqueo 5:00.

## Verificación visual (pendiente, Cristian)

```powershell
python -m autoclave.simulador
$env:AUTOCLAVE_BACKEND_URL = "http://127.0.0.1:8001"
python -m autoclave.ui_qml.app --door 1
```
Usuarios del simulador: `admin`/`admin1234` e `ingeniero`/`ingeniero1234` (cambio obligatorio), `adm1`, `tec1`, `ing1` (`clave1234`), `bloq1` (para el bloqueo). Recorrido sugerido: login con clave mala; 5 fallos con `bloq1` (cuenta regresiva; otro usuario sí puede intentar); `admin` → CAMBIAR CONTRASEÑA (errores, abandonar, cambiar) → OPCIONES › Usuarios → Nuevo usuario ("<" vuelve); detener el simulador con OPCIONES abierto (aviso y cuenta regresiva; volver a levantarlo antes y después de 15 s).

## Para el commit

Archivos de T-8 (no incluir `server.py` ni `serial_link.py` ni los archivos sin versionar del enlace serial): los 14 de `src/` modificados de la lista de `git status`, `src/autoclave/ui_qml/sesion_backend.py`, `src/autoclave/ui_qml/controllers/cambio_clave_controller.py`, `src/autoclave/ui_qml/qml/Pantallas/CambioClave.qml`, las 7 pruebas modificadas, `tests/test_sesion_backend.py`, `tests/test_cambio_clave_controller.py`, `tests/test_navegacion_sesion_qml.py` y este informe.

## Revisión de seguridad y temporización

Se relanzaron `timing-auditor` y `safety-reviewer` (solo lectura). Suite tras las correcciones: **2127 en verde** (39 pruebas en `test_sesion_backend.py`, 10 nuevas, una por corrección).

**Corregido:**

| Id | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| TMG-01 | Alta | Un login en vuelo seguía al salir del Login (casa), en standby o en HIBERNACION y abría una sesión sin pantalla; el siguiente toque entraba a OPCIONES sin credenciales | `OperacionSesion.cancelar()`; `cerrar_local` cancela la operación en vuelo y el Login destruido cancela su login; si responde después, su token se invalida. HIBERNACION cierra siempre (también con el login en vuelo) |
| TMG-02 / SAF-05 | Media / Baja | `enviar()` bloqueaba la GUI sin plazo total; el 401 navegaba dentro del slot de QML | Plazo total real (petición en hilo + espera acotada); `sesionInvalida` en diferido |
| TMG-03 | Media | Logout al salir sin plazo total | En hilos, espera total acotada a 1 s; los no confirmados quedan en el log |
| TMG-04 | Media | Logouts perdidos (Salir sin conexión, pendientes al salir) | Cola de tokens por invalidar: se reintenta al reconectar, tras un login correcto y al salir |
| TMG-06 | Baja | Respuestas sobre controladores ya destruidos | La pantalla destruida cancela su operación |
| TMG-07 | Baja | La validación al reconectar competía con el login | Operación propia |
| TMG-09 | Baja | `transporte_http` importaba `ui_qml.app` en el hilo de trabajo | URL resuelta al crear la sesión, en el hilo de la GUI |
| TMG-10 | Baja | Un login rechazado por "ocupado" cerraba la sesión previa | Se comprueba antes de cerrar |
| TMG-11 | Baja | Cambio de clave tardío sin rastro | Queda en el log (sin reintento) |
| SAF-02 | Baja | Sin validar el token al reconectar fuera de pantallas con token | Toda reconexión con sesión valida una vez con `GET /auth/sesion` |
| SAF-03 | Baja | El Login cortaba la contraseña en 30 caracteres y las claves admiten 64 | Tope de 64 en el campo contraseña |
| SAF-04 | Baja | El `repr` de `Resultado` mostraba el token | `datos` fuera del `repr` |
| SAF-06 | Baja | Un rechazo registraba el usuario tecleado (podía ser la contraseña) | Solo se registra en el bloqueo |

**Aceptado y documentado:** TMG-05 (la conexión automática de la señal ya es encolada entre hilos; emisión protegida al cerrar), TMG-08 (tras vencer o cancelar, la UI se libera aunque el hilo siga; el backend cuenta los intentos que le lleguen).

**Bloqueo por usuario en la UI:** el revisor de seguridad lo considera correcto (bloquearlo para todos permitiría negar el acceso a todos bloqueando un usuario). Un intento durante el bloqueo no lo alarga: `reservar_intento` devuelve falso sin contar (`backend/autenticacion.py:104-106`).

**Pendiente de decisión (SAF-01, Media):** la sesión solo se cierra por desatención con el standby, que no actúa en CICLO, FALLA ni EMERGENCIA y toma la menor inactividad de las dos pantallas. Una sesión abierta en ciclo y dejada con Inicio (U-5) sigue viva todo el ciclo: cualquiera entra a OPCIONES con ese rol. Hoy permite crear usuarios; con la Fase 3 (edición del ingeniero en CICLO, §5.8) permitiría cambiar fases pendientes. Propuesta del revisor: límite de inactividad propio de la sesión en todos los estados, o no conservar la sesión al salir con Inicio en esos estados.

**Notas del revisor de seguridad:** `AutoclaveSettings.exe` (menú PySide) sigue con login local sin token ni bloqueo; desde QML ya no se lanza. Con HIBERNACION ya activa se puede iniciar sesión (estado hoy inalcanzable, OPC-25).

## Commit 4 (preparado, sin commit)

`ui_pyside/views/admin_menu.py`: se quita la entrada "Nuevo usuario" y el filtro de admin que solo la afectaba; la vista `views/nuevo_usuario` y su puente se conservan. `tests/test_admin_menu_nuevo_usuario.py` ajustado (la opción ya no existe para ningún rol; las pruebas de `MainWindowFluent` se mantienen). Va después del commit 3, con solo esos dos archivos. Suite con todo: 2127 en verde.
