# K11 — Compilación G (tanda 11)

Fecha: 23-oct-2026, sesión principal, de 18:00 a 18:20 (hora de Bogotá). **Hay compilación G y se recomienda instalarla** en el equipo de pruebas antes de los ciclos del lunes 26-oct, con `Autoclave_Setup_1.0.0-g.exe` y la sección 8f del LEEME (F → G, dejando marcada «Actualizar (conserva los datos)»).

## Origen
- `tanda-11` unida a `dev` con `--no-ff`: 8051145, «Merge tanda-11 en dev (R11, E11, S11, U11, N11, O11)». `git diff tanda-11 dev` vacío en ese momento.
- Etiqueta `inst-2026-10-23-g` → 8051145.
- Suite en ese código (25bbe81, tras unir N11 y el guion del ensayo; después solo documentación), con `pytest -n auto`: **7216 passed, 2 failed, 10 skipped, 3 xfailed** en 6 min (`suites/integ_n11_final.log`). Los 2 rojos (`test_ciclos_print.py::test_print_selected_sin_seleccion_no_imprime` y `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`) pasan en serie (`suites/integ_n11_final_serie.log`, 2 passed). Son interferencia del paralelo y ya fallaban así en la línea base. Total: **7218 passed** (línea base 6993).
- Compilado en un worktree limpio desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_g`), con `git status` vacío.

## Entorno
- Entorno virtual de L8 `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3), PyInstaller 6.20.0. Requisitos, `pyproject.toml` y `.spec` sin cambios desde la F (`git diff inst-2026-10-23-f inst-2026-10-23-g -- requirements*.txt *.spec pyproject.toml`: vacío). Sí cambiaron `tools/instalador` y `tools/estacion` (N11). `pip freeze` en `entrega/2026-10-23_g/entorno_build.txt`.
- PowerShell sin las rutas de Git en el PATH. `_internal` solo trae `libssl-3.dll`/`libcrypto-3.dll` de Python 3.14, igual que en la D, la E y la F.

## Comandos
- `python -m PyInstaller --noconfirm Autoclave.spec`: salida 0, 245 s. En el `PYZ.pyz` del ejecutable están `autoclave.backend.server_reasignacion`, `autoclave.backend.reinicio` (R11), `autoclave.core.runtime.nombre_usuario` (U11) y `psutil`, que necesita la espera de una sola instancia de R11. Comprobado con `CArchiveReader`.
- `python -m PyInstaller --noconfirm GeneradorCodigos.spec`: salida 0.
- `ISCC.exe /Q /DEntrega=...\entrega\2026-10-23_g /DAppVer=1.0.0-g /DAppVerNum=1.0.0.7 tools\instalador\autoclave.iss` (desde el worktree de la etiqueta): salida 0. **El Setup no se ejecutó.**

Advertencias del build: las mismas de K8 a K10 (hidden imports opcionales `tzdata`, `importlib_resources.trees`, `scipy.special._cdflib`, y frameworks de macOS ignorados).

## Verificaciones
`python tools/verificar_entrega_neutra.py dist/Autoclave` (salida 0):
- calibración neutra (sha256 4f13c26f…8347162);
- correo neutro (d76b44a1…2a3f86);
- solo `cycles/factory` (4 programas).

`Autoclave/` tiene 2298 archivos (305 MB). No hay `installation_profile.json*`, `*.db`, `data/` ni `.claude/`.

## Prueba de humo
Copia en `C:\Users\tecni\t11tmp\humo_g` (borrada al terminar), `Autoclave.exe --portable`:
- a los 60 s corren el lanzador, `--rol ui --door 1 --screen 0` y `--rol ui --door 2 --screen 1`;
- puerta 1: **INSTALACIÓN DEL EQUIPO, Paso 1 de 8 · Activación** (`entrega/2026-10-23_g/prueba_humo_asistente.png`);
- puerta 2: **Reposo con «Instalación en curso en la pantalla 1»** (`prueba_humo_pantalla2.png`);
- `lanzador.log`, `ui_puerta1.log`, `ui_puerta2.log` y `autoclave.log` no tienen `Traceback`, `ERROR`, `CRITICAL` ni `COM<n>`;
- procesos cerrados.

La sesión de Windows estaba bloqueada, así que una captura del escritorio solo mostraba la pantalla de bloqueo. Las capturas se tomaron de cada ventana con `PrintWindow` (PW_RENDERFULLCONTENT).

## Actualización F → G (ensayo sobre una copia)
Guion nuevo `tools/ensayo_actualizacion_f_g.py`, que reutiliza el de B → D. Corre primero con el código de la etiqueta F (`git archive inst-2026-10-23-f src`) y el `_internal` de `entrega/2026-10-23_f`, y después con el código de la etiqueta G y **el `_internal` real de la G**. Carpetas de prueba en `C:\Users\tecni\Documents\_t11_k11_tmp`; registro en `ensayo_f_g.log`.
```
F: version_bd 10; semillas [admin, ingeniero]
G: serial PRUEBA-001, version_bd 11, usuarios [Admin, Ingeniero, cristian], temp_max_apertura 75,
   marca_calibracion true, marca_correo true, programas de fábrica [4], fuentes [user]
   semillas: Admin/Ingeniero con nombre mostrado igual, mismo hash de contraseña, debe_cambiar_clave 1 (como en la F), marca cuenta_sistema 1
   usuario_renombrado: 2 filas ({"usuario": "Admin", ...}, {"usuario": "Ingeniero", ...})
   inicio de sesión: admin/ADMIN/Admin → Admin; ingeniero/INGENIERO → Ingeniero
   E/S: sin aire_comprimido_chaqueta; aire_comprimido_camara y Cámara 2 presentes
   respaldos: [<fecha>/autoclave/config/instances/ACV-2026-001.yaml]
OK: sin errores []
```
- **U11:** la migración de usuarios funciona sobre una base de la F.
- **E11:** el YAML de instancia se refresca solo y se respalda porque cambió de la F a la G. `global_params.json` no cambió, así que no se respalda.
- El registro trae un `UnicodeDecodeError` en el hilo que lee la salida de error de la fase F (texto del log en cp1252). No afecta al resultado, porque el JSON sale por la salida estándar.

## LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/`, `entrega/2026-10-23_g/` y `usb/`)
Se agregó:
- el aviso de cabecera de la G;
- la tabla **«Cambios respecto a la F»**;
- la sección **8f**: F → G con el Setup, con «Actualizar (conserva los datos)» marcada y **sin** Instalación limpia en el equipo de pruebas. La casilla de estación sigue DESMARCADA (K9-1), así que el paso 06 de los táctiles no corre allí. La sección dice qué comprobar de la tanda 11 y cómo volver a la F con el respaldo.

U11 ya había actualizado las credenciales de la §5.

## Entrega (`entrega/2026-10-23_g/`, no versionada)
`Autoclave/`, `Autoclave_2026-10-23_g.zip` (Python, `testzip` sin errores, 2298 archivos), `Autoclave_Setup_1.0.0-g.exe` (86 MB), `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256` (verificado), `entorno_build.txt`, `LEEME_INSTALACION.md`, `prueba_humo_asistente.png`, `prueba_humo_pantalla2.png` y `usb/`.
```
8faf292c94106ce035c642ef5325167755632356dcb9e505053905cea239f01c *Autoclave_Setup_1.0.0-g.exe
b40ea5cab3689d9601caa49d4935b6bc68e2ef46cbefc4a94261e055c6bb9ff1 *Autoclave_2026-10-23_g.zip
1fbfad2ea79e12418fdd02936d283c3854401eaaffa474c873f6451af789cc36 *GeneradorCodigos.exe
b6b6034f78f6b2f0563b5f6eed3ba6c4e0f3b644027f4a38eaff72e6efaf904f *Autoclave/Autoclave.exe
a0cadd14cc3e59be01917f58fe19ca003c92c0456c59f536a754b6c84248e422  MANIFIESTO_CARPETA_Autoclave.sha256 (2298 archivos)
```

### `usb/` (exactamente lo que va a la USB)
- `Autoclave_Setup_1.0.0-g.exe`;
- `SHA256SUMS.txt`, solo con la línea del Setup (`sha256sum -c` sobre el Setup copiado: OK);
- `LEEME_INSTALACION.md`;
- `drivers/`.

El generador queda en `entrega/2026-10-23_g/`, fuera de `usb/`. No se copió nada a ninguna USB.

**Pendiente:** `entrega/drivers/` sigue vacía, así que `usb/drivers/` también.

## Verificar en sitio
- La actualización real F → G con el Setup (8f): debe aparecer la página nueva con «Actualizar (conserva los datos)» marcada. Después, iniciar sesión con `Ingeniero` y la contraseña de la F.
- Cambiar la impresora en PREPARADO: el software debe cerrarse y volver a abrir solo en menos de 1 minuto (R11). En `lanzador.log`, buscar «El backend pidió reiniciar el software» y «Autoclave relanzado».
- Entradas/Salidas sin aire comprimido de chaqueta, con DO 13 libre (E11).
- SEN-03 solo con las sondas en uso (S11).
- Filas «Entrada 1/2/3» y Preciclo/Ciclo sin filas «—» (O11).
- Instalación limpia y asociación de táctiles: **solo en un PC de prueba**, con los casos A-N11-01 a 05 de la hoja de banco (N11).
