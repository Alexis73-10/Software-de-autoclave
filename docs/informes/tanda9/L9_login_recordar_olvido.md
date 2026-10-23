# L9 — D9-12 (H9): «Recordar usuario» y «¿Olvidó su contraseña?» en el inicio de sesión QML

Rama `tanda-9-l9` (desde `tanda-9` en e8a22d0). NO entra en la compilación D.

## Qué se pidió
`decisiones_tanda_9.md` D9-12 (diferido): H9 «Recordar usuario» y «¿Olvidó su contraseña?». Origen (hallazgos del 22-oct y documentos previos):
- `INFORME_OPCIONES_POST_LOGIN.md` §«Recordar usuario»: en QML la casilla era solo visual (`recordarUsuario.marcado` cambiaba con un toque; no se guardaba ni se leía). La interfaz PySide sí lo hacía (solo el nombre, en `QSettings`).
- `planeacion_ui_dual_pantalla.md` §12.2 n.º 12: «¿Olvidó su contraseña?» en un equipo sin canal de recuperación → «definir el flujo real (restablecimiento por administrador desde Usuarios) o retirar el enlace». En QML era un texto sin acción.

## Qué se hizo
1. **Recordar usuario (solo el nombre).**
   - Nuevo `src/autoclave/ui_qml/domain/recordar_usuario.py`: `cargar`, `guardar`, `olvidar`, `ruta_por_defecto()` = `app_root()/data/login_recordado.json` con `{"usuario": "..."}`. Escritura atómica (`.tmp` + `os.replace`). Archivo ausente, dañado o con nombre no válido (vacío, más de 30 caracteres, caracteres no imprimibles) = nada recordado; nunca hace fallar el login. Los avisos de registro no incluyen el nombre.
   - `LoginController`: propiedades `usuarioRecordado` (constante, leída al abrir) y `recordarUsuario` (casilla, `recordarUsuarioChanged`), ranura `fijarRecordarUsuario(bool)` y parámetro `ruta_recordado` (pruebas). El archivo se toca **solo con credenciales válidas** (también si se exige cambiar la contraseña): casilla marcada → guarda el nombre tecleado (sin espacios); desmarcada → lo borra. Un intento fallido no lo toca. Contraseña y token nunca pasan por este módulo.
   - `Login.qml`: el campo usuario se prellena con `usuarioRecordado`; la casilla (`casillaRecordarUsuario`) refleja el controlador y su toque llama a `fijarRecordarUsuario`.
   - `.gitignore`: `/data/login_recordado.json` (y su `.tmp`).
2. **¿Olvidó su contraseña?** Un toque en el enlace (`enlaceOlvidoClave`) muestra/oculta un texto (`ayudaOlvidoClave`, provisional sin diseño): «Pida a un administrador o a un ingeniero que restablezca su contraseña en OPCIONES › Usuarios. Recibirá una contraseña temporal que deberá cambiar al ingresar.» Apunta al restablecimiento existente (`POST /usuarios/{usuario}/restablecer_clave`, roles admin e ingeniero, clave temporal con cambio obligatorio). No se inventó ningún canal de recuperación.
3. **i18n:** clave nueva `sesion.ayuda_olvido_clave` en `es.json` y `en.json` (las etiquetas `formulario.recordar_usuario` y `formulario.olvido_contrasena` ya existían).

## Commits
- `4a168df` feat(tanda9-l9): login QML recuerda solo el nombre de usuario y explica el restablecimiento de contraseña (D9-12, H9)
- (este informe) docs(tanda9-l9)

## Pruebas
`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a326ce4d604c87b0b\src\autoclave\__init__.py` (PYTHONPATH del worktree).

Nuevas (TDD: ambas en rojo antes del cambio; la QML se comprobó en rojo con el `Login.qml` original: 6 errores):
- `tests/test_l9_recordar_usuario.py` (28): módulo de dominio (archivo ausente/dañado/inválido, solo la clave `usuario`, olvidar) y controlador contra el backend real (marcada + login válido guarda solo el nombre, sin contraseña ni token en el archivo; login fallido no guarda ni borra; desmarcada + login válido olvida; cambio de clave obligatorio también recuerda; la casilla no escribe hasta entrar).
- `tests/test_l9_login_qml_recordar_olvido.py` (6): `Login.qml` real a 1200x1920 en subproceso, archivo de preferencias redirigido a temporal: prellenado + casilla marcada, toque de casilla, entrar marcada/desmarcada, reabrir vacío, ayuda de «¿Olvidó…?» visible/oculta con el texto del catálogo, sin avisos del motor QML.

Corridas (las nuevas + las que cargan `Login.qml`/`LoginController` o el catálogo i18n): `test_l9_recordar_usuario`, `test_l9_login_qml_recordar_olvido`, `test_login_controller`, `test_login_qml_autenticacion`, `test_panel_teclado_login`, `test_sesion_backend`, `test_opciones_qml`, `test_n8_cerrar_sesion_qml`, `test_u2_navegacion_qml`, `test_s9_login_y_causa_qml`, `test_i18n`, `test_i18n_linea_base`, `test_i1_i18n_backend` → **377 passed in 151.01s**. Suite completa no corrida (regla 8).

## DECISIONES SIN CONFIRMAR
- **DSC-L9-1:** «Recordar usuario» guarda solo el nombre en `data/login_recordado.json` (preferencia local de la interfaz, compartida por todos en el equipo), no en `QSettings`/registro como la interfaz PySide; se escribe solo tras credenciales válidas. Por defecto la casilla queda desmarcada mientras no haya nada recordado. Revertir = quitar el archivo o la casilla.
- **DSC-L9-2:** el nombre recordado se muestra a cualquiera que abra el inicio de sesión (revela un nombre de usuario válido en un equipo compartido). Se juzgó aceptable porque la contraseña sigue siendo obligatoria y el bloqueo por intentos sigue activo; si no se acepta, retirar la casilla.
- **DSC-L9-3:** «¿Olvidó su contraseña?» muestra una ayuda en línea (sin ventana emergente, sin diseño) que remite al restablecimiento por un administrador o ingeniero en OPCIONES › Usuarios. No hay recuperación por correo, preguntas ni códigos.
- **DSC-L9-4:** recordar también al entrar con cambio de contraseña obligatorio (las credenciales fueron válidas).

## PREGUNTAS PARA CRISTIAN
1. ¿Se conserva «Recordar usuario» (DSC-L9-2) o se retira por ser un equipo compartido?
2. ¿La ayuda de «¿Olvidó su contraseña?» debe nombrar también al técnico? Hoy el backend solo deja restablecer a admin e ingeniero (`_GESTION_USUARIOS`); el técnico ve Usuarios en solo lectura.
3. ¿Hace falta diseño (ventana o tarjeta) para la ayuda, o basta el texto bajo el enlace?
4. Si un usuario recordado se desactiva, su nombre sigue apareciendo hasta que alguien entre con la casilla desmarcada. ¿Se quiere limpiar al desactivarlo?

## Pendientes
- Hoja de banco: verificar en el equipo que el archivo se crea en `%ProgramData%\Especifika\Autoclave\data\` (compilado) y que la casilla sobrevive a un reinicio.
- No es etapa ★: sin revisores ni planta simulada; no toca ciclo, puertas, sensores ni alarmas.
