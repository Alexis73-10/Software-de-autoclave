# K10 — Compilación F (tanda 10)

Fecha: 23-oct-2026, sesión principal, de 12:13 a 12:25 (hora de Bogotá). **Hay compilación F y se recomienda instalarla** en el equipo de pruebas antes de los ciclos del lunes 26-oct, con `Autoclave_Setup_1.0.0-f.exe` y la sección 8e del LEEME (E → F, o D → F). Se llama **F** y no E porque la letra E ya la usó la compilación de esta mañana (DECISIÓN SIN CONFIRMAR A0-2).

## Origen
- `tanda-10` unida a `dev` con `--no-ff`: 4923349, «Merge tanda-10 en dev (G10, T10, W10, U10a, U10b; Entrega E)». `git diff tanda-10 dev` vacío en ese momento.
- Etiqueta `inst-2026-10-23-f` → 4923349.
- Suite en ese código (0635da5, unión de U10b; lo que sigue hasta 4923349 es solo documentación), con `pytest -n auto` (pytest-xdist 3.8.0, §2 de la instrucción): **6990 passed, 3 failed, 10 skipped, 3 xfailed** en 6 min (`suites/integ_u10b.log`). Los 3 rojos (`test_ciclos_print.py::test_print_selected_sin_seleccion_no_imprime`, `test_ciclos_print.py::test_print_selected_imprime_directo_sin_dialogo`, `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`) pasan en serie (3 passed, `suites/integ_u10b_serie.log`): interferencia del paralelo, no rojo. Total: **6993 passed**.
- Compilado en un worktree limpio desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_f`), con `git status` vacío.

## Entorno
- Entorno virtual de L8 `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3), PyInstaller 6.20.0. Requisitos, `.spec`, `tools/instalador` y `tools/estacion` sin cambios desde la E (`git diff inst-2026-10-23-e tanda-10 -- requirements*.txt *.spec tools/instalador tools/estacion`: vacío). `pip freeze`: `entrega/2026-10-23_f/entorno_build.txt`.
- PowerShell con las rutas de Git quitadas del PATH. `_internal` solo trae `libssl-3.dll`/`libcrypto-3.dll` de Python 3.14 (como la D y la E).

## Comandos
- `python -m PyInstaller --noconfirm Autoclave.spec`: salida 0, 259 s. `autoclave.backend.server_reasignacion` está en el `PYZ.pyz` del ejecutable (corrección de la E, comprobada con `CArchiveReader`).
- `python -m PyInstaller --noconfirm GeneradorCodigos.spec`: salida 0 (fuente monoespaciada de D10-2.2: `Consolas, "Cascadia Mono", monospace` en `tools/generador/app.py` de la etiqueta).
- `ISCC.exe /Q /DEntrega=...\entrega\2026-10-23_f /DAppVer=1.0.0-f /DAppVerNum=1.0.0.6 tools\instalador\autoclave.iss`: salida 0. **El Setup no se ejecutó.** La versión se pasa por línea de órdenes, igual que en la E (los valores por defecto del `.iss` siguen en la D).

Advertencias del build: las mismas de K8/K9 (hidden imports opcionales `tzdata`, `importlib_resources.trees`, `scipy.special._cdflib`; «Logging error» interno de PyInstaller).

## Verificaciones
`python tools/verificar_entrega_neutra.py dist/Autoclave` (salida 0): calibración neutra (sha256 4f13c26f…8347162), correo neutro (d76b44a1…2a3f86) y solo `cycles/factory` (4 programas). `Autoclave/` con 2298 archivos (305 MB); sin `installation_profile.json*`, `*.db`, `data/` ni `.claude/`.

## Prueba de humo
Copia en `C:\Users\tecni\t10tmp\humo_f` (borrada al terminar), `Autoclave.exe --portable`:
- a los 60 s corren el lanzador, `--rol ui --door 1 --screen 0` y `--rol ui --door 2 --screen 1`;
- puerta 1: **INSTALACIÓN DEL EQUIPO, Paso 1 de 8 · Activación** (`entrega/2026-10-23_f/prueba_humo_asistente.png`);
- puerta 2: **Reposo con «Instalación en curso en la pantalla 1»** (D10-4, `prueba_humo_pantalla2.png`);
- sin `Traceback`, `ERROR`, `CRITICAL` ni `COM<n>` en `lanzador.log`, `ui_puerta1.log`, `ui_puerta2.log` ni `autoclave.log`. Procesos cerrados.

## Actualización E → F (ensayo sobre una copia)
`tools/ensayo_actualizacion_b_d.py` con el código de la etiqueta E (`git archive inst-2026-10-23-e src`) y el `_internal` de `entrega/2026-10-23_e`, luego el código de la etiqueta F y **el `_internal` real de la F**. Carpetas de prueba en `C:\Users\tecni\Documents\_t10_k10_tmp`.
```
E: version_bd 10; perfil y calibración en <tmp>\PD\Especifika\Autoclave
F: serial PRUEBA-001, version_bd 10, usuarios [admin, cristian, ingeniero], temp_max_apertura 75,
   pausa_max_esterilizacion_s 30, espera_sellado_sin_sonda_min 30, marca_calibracion true, marca_correo true,
   AI/DI/DO completos (Cámara 2 y descompresion_lenta), programas de fábrica [4], fuentes [user], respaldos []
ERRORES: ["faltan respaldos: [global_params.json, instances/ACV-2026-001.yaml]"]
```
El único «error» es una expectativa del guion, escrito para B → D: espera que se respalden los dos archivos de configuración de fábrica porque cambiaban de la B a la D. **De la E a la F `src/autoclave/config/` no cambió** (`git diff inst-2026-10-23-e tanda-10 -- src/autoclave/config/`: vacío), así que no hay nada que refrescar ni respaldar: es lo correcto. Se conservan perfil, usuarios, calibración, correo, `temp_max_apertura` = 75 y la BD (versión 10, sin migración). D → F no se ensayó aparte: la F tiene el mismo código de datos que la E, y D → E ya lo cubría el Setup E (sección 8d).

## LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/`, `entrega/2026-10-23_f/` y `usb/`)
Parte de la versión de la E (que no estaba versionada en `docs/instalacion/`; ahora sí). Agrega el aviso de cabecera de la F, la tabla **«Cambios respecto a la E»** y la sección **8e** (E → F y D → F con el Setup, sin copias a mano, casilla de estación DESMARCADA en el equipo de pruebas — K9-1 se mantiene — y qué comprobar de la tanda 10).

## Entrega (`entrega/2026-10-23_f/`, no versionada)
`Autoclave/`, `Autoclave_2026-10-23_f.zip` (Python, `testzip` sin errores, 2298 archivos), `Autoclave_Setup_1.0.0-f.exe` (82 MB), `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256` (verificado), `entorno_build.txt`, `LEEME_INSTALACION.md`, `prueba_humo_asistente.png`, `prueba_humo_pantalla2.png` y `usb/`.
```
c8cc13043ee7d45c3dd2b4c2c497868869c4be497ba162c32f9455287c454d9b *Autoclave_Setup_1.0.0-f.exe
ec9ccf8e133dc8356dad42268756920a48ff6eeec05a6db815e58bde19b71b60 *Autoclave_2026-10-23_f.zip
58c517aeb50a26cf1007d9d1a5c1b29240287dc4fbd6e855da5582ddf72a317c *GeneradorCodigos.exe
946f5b9f9334788a04ad745f0b026b6a51fa0faed0abcb0f2118fcfa21f483d4 *Autoclave/Autoclave.exe
547c2dcb85a3148a94cce911295057aa75145f25b9a327854ed0c14d14848c41  MANIFIESTO_CARPETA_Autoclave.sha256 (2298 archivos)
```

### `usb/` (exactamente lo que va a la USB)
`Autoclave_Setup_1.0.0-f.exe`, `SHA256SUMS.txt` (solo la línea del Setup; `sha256sum -c` sobre el Setup copiado: OK), `LEEME_INSTALACION.md` y `drivers/`. El generador queda en `entrega/2026-10-23_f/`, fuera de `usb/`. No se copió a ninguna USB.

**Pendiente:** `entrega/drivers/` sigue vacía, así que `usb/drivers/` también.

## Verificar en sitio
- La actualización real E → F con el Setup (8e) y la página de versión (debe actualizar, no ofrecer Reparar).
- Dos monitores: la pantalla 2 en Reposo con el aviso durante el asistente y su paso al flujo normal al terminar (W10).
- Ciclo/Preciclo y campana en es y en con la resolución real del equipo (U10a/U10b); CIC-10 sin sensor de presión (T10).
- El código de activación del generador nuevo, tecleando 0 en vez de O (G10).
