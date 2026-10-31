# C1 — Calibración y Entradas/Salidas desde el ejecutable (PySide)

## Hallazgo principal (defecto real)
El menú de ajustes PySide NO podía usarse desde la etapa de autenticación del backend:
1. `LoginView` comparaba un SHA-256 contra `hash_pw`, pero las contraseñas se guardan con PBKDF2 → ningún usuario entraba.
2. Aunque entrara, el login PySide no obtenía token y `BackendClient` no enviaba `Authorization`: `PATCH /calibration`, `/io/test/*`, `PATCH /cycle/parameter` responden 401 (requieren técnico/ingeniero).
Es decir: en el equipo de pruebas no se habría podido calibrar ni hacer diagnóstico de E/S.

## Corrección
- `ui_pyside/services/auth_backend.py`: login con `POST /auth/login` (mismo 401 genérico, bloqueo por intentos 429, 503 sin BD) y logout con `POST /auth/logout`; el token queda en `SessionManager`. Un usuario con cambio de contraseña pendiente no deja sesión (debe cambiarla desde OPCIONES de la UI principal).
- `BackendClient` acepta `token_provider`; `ui_pyside/services/backend_client.py` lo instancia con el token de la sesión y TODAS las vistas PySide usan ese cliente (6 archivos). El cliente base sin proveedor no cambia.
- Salir del menú (✕) y "cerrar sesión" invalidan el token en el backend.
- Calibración: 401/403 se muestran como "Sesión vencida o sin permiso", no como fallo de conexión. Los 422/409 de plausibilidad (S3a) ya se manejaban (rechazo con motivo; confirmación explícita que reenvía `confirmar_fuera_de_rango`): S3a está en `dev`, verificado.
- Ninguna ventana escribe salidas en ciclo o sin sesión: lo impone el backend (`requiere_rol` + `guard_estado` que rechaza CICLO; técnico nunca en ciclo para calibración); prueba nueva: sin token PATCH calibración, `/io/test/enter` y `/io/test/output` → 401 y `set_output` no se llama.

## Ejecutable congelado (solo lectura de `exe_unico.py` / `Autoclave.spec`)
- El engrane llama `comando_ajustes()`: con `AUTOCLAVE_EXE_UNICO=1` y frozen → `[exe, "--rol", "ajustes"]`; el lanzador exporta esa variable a las pantallas, y `exe_unico.main` atiende `--rol ajustes` → `ui_pyside.app.main()`. Correcto.
- `autoclave.ui_pyside.app` está en hiddenimports. NO verificado (no se compila): que PyInstaller recoja `qfluentwidgets` (recursos/fuentes) y `qdarkstyle`/iconos si los usa; la importación de las vistas es diferida dentro de `MainWindowFluent`, que PyInstaller no sigue por análisis estático si no están en el árbol de imports (están importados dentro de `__init__`; PyInstaller sí los detecta, pero conviene probar el exe). **Comprobación manual obligatoria con el exe**: engrane → login → Entradas/Salidas → Calibración.
- Recomendación (no aplicada, el spec lo edita otra sesión): agregar `qfluentwidgets` a `collect_data_files`/hiddenimports si el exe muestra widgets sin estilos o falla al abrir.

## DECISIONES SIN CONFIRMAR
1. Login PySide vía backend (token real) en vez de pasar el token de la ventana QML al subproceso por entorno (un token en el entorno es visible a otros procesos). Alternativa: reutilizar la sesión QML.
2. Cambio de contraseña pendiente: se rechaza el acceso al menú PySide con mensaje, no se implementa el cambio ahí.

## Pendientes
- PySide sigue siendo UI provisional (Fase 5 fuera de alcance). Parámetros del sistema/Opciones avanzadas/Conectividad siguen allí; en QML dicen "Próximamente".

## Revisión (safety-reviewer) y correcciones
- SAF-01 (Alta, sesión/modo prueba huérfanos): cerrar la ventana por cualquier vía (`closeEvent`) invalida el token (y con él sale de un modo prueba propio); el login cierra antes cualquier sesión previa (SAF-02); logout reintenta una vez (SAF-05). NO se cambió la regla vigente (decisión 30: solo la sesión dueña sale del modo prueba, ni siquiera un ingeniero; hay una prueba que lo exige). Alternativa que se deja a Cristian: permitir a un ingeniero forzar la salida de un modo prueba huérfano (apaga todo, auditado). Limitación: `LanzadorAjustes.cerrar()` usa `terminate()` (kill duro) al salir la UI principal; el token queda vivo hasta que alguien fuerce la salida (el ingeniero) o se reinicie el backend. Pendiente: caducidad de tokens por inactividad en el backend (no existe; es una etapa de autenticación aparte).
- SAF-03 (Media): `io_do.py` ya no marca la salida como encendida si el backend rechazó (se muestra el motivo, 401 como sesión vencida) y no da por salido el modo prueba si `/io/test/exit` falla.
- SAF-04 (Baja, PENDIENTE): `secado.py` hace `PATCH /cycle/parameters` (ruta inexistente → 404); la vista de secado no puede guardar. Se deja documentado; no hay falso éxito.

## Defecto adicional detectado en el ejecutable (NO corregido: `Autoclave.spec` es de la otra sesión)
`Autoclave.spec` excluye `scipy`, pero `qfluentwidgets.common.image_utils` hace `from scipy.ndimage.filters import gaussian_filter` al importarse. En el exe el menú de ajustes PySide fallaría al abrir (ImportError). Hay que quitar `scipy` de `excludes` (o `scipy.ndimage` en hiddenimports) y compilar para comprobar. **Acción manual antes del lunes.**
