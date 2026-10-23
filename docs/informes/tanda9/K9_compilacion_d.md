# K9 — Compilación D (tanda 9)

Fecha: 23-oct-2026, sesión principal, de 06:15 a 06:50 (hora de Bogotá). **Hay compilación D y se recomienda instalarla** en el equipo de pruebas antes de los ciclos del lunes 26-oct, con el Setup y siguiendo la sección 8c del LEEME (B → D, sin copias a mano). La C no se instala.

## Origen
- `tanda-9` unida a `dev` con `--no-ff`: 4357217, «Merge tanda-9 en dev (S9, B9, E9, A9, P9, C9, X9)». `git merge-base --is-ancestor tanda-9 dev`: sí. `git diff tanda-9 dev` vacío.
- Etiqueta `inst-2026-10-23-d` → 4357217.
- Suite en ese código (unión de B9, 82da39d; lo que sigue es solo documentación): **6606 passed, 10 skipped, 3 xfailed** (23 min), `suites/integ_b9.log`.
- Compilado en un worktree limpio desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_d`), con `git status` vacío.

## Entorno
- Entorno virtual limpio de L8: `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3), sin el paquete editable `autoclave` (`pip show autoclave`: no encontrado). Las dependencias no cambiaron desde la C (`git diff inst-2026-10-23-c inst-2026-10-23-d -- requirements*.txt`: vacío; solo cambiaron los `.spec`, por D9-7).
- PyInstaller 6.20.0. `pip freeze`: `entrega/2026-10-23_d/entorno_build.txt`.
- Compilado desde PowerShell, con las rutas de Git quitadas del PATH (hallazgo de L8). `_internal` no tiene `libssl-3-x64.dll` ni `libcrypto-3-x64.dll` (las de Git). Sí tiene `libssl-3.dll` y `libcrypto-3.dll`: son las de Python 3.14 (idénticas byte a byte a las de `Python314\DLLs`) y la C también las tenía.

## Comandos
- `python -m PyInstaller --noconfirm Autoclave.spec`: salida 0, 185 s.
- `python -m PyInstaller --noconfirm GeneradorCodigos.spec`: salida 0.
- `ISCC.exe /Q /DEntrega=...\entrega\2026-10-23_d tools\instalador\autoclave.iss` (desde el worktree de la etiqueta): salida 0. **El Setup no se ejecutó.**

Advertencias del build (ninguna bloqueante, las mismas de K8): hidden imports opcionales no encontrados (`tzdata`, `importlib_resources.trees`, `scipy.special._cdflib`), 3 bibliotecas de macOS ignoradas, el «Logging error» interno de PyInstaller y el aviso de Pydantic V1.

## Verificaciones D8-3.18 y D9-7
`python tools/verificar_entrega_neutra.py dist/Autoclave` (salida 0):
```
OK: calibración neutra empaquetada (sha256 4f13c26f…8347162)
OK: correo neutro (sha256 d76b44a1…2a3f86) y solo cycles/factory (4 programas: bowe_dick.json, instrumental_121.json, instrumental_134.json, liquidos.json)
```
Contenido: `Autoclave/` con 2296 archivos (305 MB); `_internal/autoclave/cycles/` solo tiene `factory/`; `config/instances/ACV-2026-001.yaml`; `i18n` es y en. No hay `installation_profile.json*`, `*.db`, `data/` ni `.claude/`.

## Prueba de humo
Copia en `C:\Users\tecni\t9tmp\humo_d` (borrada al terminar), `Autoclave.exe --portable`:
- a los 60 s corren el lanzador y `--rol ui --door 1 --screen 0`;
- ventana «Autoclave» con **INSTALACIÓN DEL EQUIPO, Paso 1 de 8 · Activación**: `entrega/2026-10-23_d/prueba_humo_asistente.png` (solo la ventana del programa);
- sin `Traceback`, `ERROR` ni `CRITICAL` en `lanzador.log`, `ui_puerta1.log` ni `autoclave.log`;
- sin perfil no arranca el control: no se abrió ningún puerto COM. Procesos cerrados.

## Actualización B → D (ensayo sobre una copia, D9-13.1)
`tools/ensayo_actualizacion_b_d.py` (de E9) con el código de la etiqueta B (`git archive inst-2026-10-22-b src`), el `_internal` de `entrega/2026-10-22_b`, el código de la etiqueta D y **el `_internal` real de la D** (`entrega/2026-10-23_d/Autoclave/_internal`). Carpetas de prueba en `C:\Users\tecni\Documents\_t9_k9_tmp`; nada fuera de ellas.

```
B: version_bd 9; perfil y calibración en <tmp>\PD\Especifika\Autoclave
D: serial PRUEBA-001, version_bd 10, usuarios [admin, cristian, ingeniero], temp_max_apertura 75,
   pausa_max_esterilizacion_s 30, espera_sellado_sin_sonda_min 30, marca_calibracion true, marca_correo true,
   AI [temp_camara, temp_2_camara, temp_referencia, temp_drenaje, pres_camara, pres_chaqueta],
   DO [vapor_chaqueta, vapor_camara, descompresion_rapida, descompresion_lenta, descompresion_chaqueta, vacio_camara,
       aire_comprimido_chaqueta, aire_comprimido_camara, aire_atmosferico_camara, agua_chaqueta, agua_intercambiador,
       agua_bomba, bomba_vacio, buzer_alarma],
   programas de fábrica [4], fuentes [user],
   respaldos [2026-10-23_063047/autoclave/config/global_params.json, 2026-10-23_063047/autoclave/config/instances/ACV-2026-001.yaml]
OK: sin errores []
```
**Cámara 2 y `descompresion_lenta` aparecen sin pasos manuales**; se conservan la calibración del equipo, el correo del sitio, el perfil, los usuarios y `temp_max_apertura` = 75; solo se respaldan los dos archivos esperados. La salida tiene además un `UnicodeDecodeError` en el hilo del guion que lee la salida del subproceso (una «ó» en cp1252): es del guion de ensayo, no del programa, y no afecta el resultado.

## LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/`, `entrega/2026-10-23_d/` y `usb/`)
- Aviso de cabecera: la C no se instala; B → D con el Setup.
- Tabla **B frente a D**.
- Sección **8c**: orden con el software cerrado, respaldo, Setup, casillas (**la de estación DESMARCADA en el equipo de pruebas** hasta validarla en un PC de prueba, D9-11 — DECISIÓN SIN CONFIRMAR K9-1), comprobaciones, programas de usuario de la B (E9-P1), qué no tocar y vuelta atrás. **Sin pasos de copia a mano.**
- La 8b (B → C) queda marcada como referencia.

## Entrega (`entrega/2026-10-23_d/`, no versionada)
`Autoclave/`, `Autoclave_2026-10-23_d.zip` (hecho con Python, `testzip` sin errores, 2296 archivos), `Autoclave_Setup_1.0.0-d.exe` (82 MB), `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256` (verificado), `entorno_build.txt`, `LEEME_INSTALACION.md`, `prueba_humo_asistente.png` y `usb/`.

```
29829cafb6e2f98786c745a5187edf31d1d5e9957497192a13324d4913a2df49 *Autoclave_Setup_1.0.0-d.exe
a8c87264a79a97796bc3579f1c1652531e8d388d59c36168eb6e1fec4d03fb21 *Autoclave_2026-10-23_d.zip
cdfe4c7fa9262245af43bf93404193d9cb69f83c513327a7c6c4a975e133d646 *GeneradorCodigos.exe
dafb0e2e429d842bf730ac9012752d82cd86ae9f613905398f141d3fb98bed93 *Autoclave/Autoclave.exe
7218a24ae3ab9b1a5ce73cd70816a1b80e49d35649c87bb7710dd3a2551a61ea  MANIFIESTO_CARPETA_Autoclave.sha256 (2296 archivos)
```

### `usb/` (exactamente lo que va a la USB)
`Autoclave_Setup_1.0.0-d.exe`, `SHA256SUMS.txt` (solo el Setup; verificado con `sha256sum -c` sobre el Setup ya copiado en `usb/` y coincide con la línea de la entrega), `LEEME_INSTALACION.md` y `drivers/`. Sin `GeneradorCodigos.exe`, sin el `.zip` y sin la carpeta `Autoclave/` suelta. No se copió a ninguna USB.

**Pendiente:** `entrega/drivers/` está vacía desde el 22-oct (no tiene ningún archivo), así que `usb/drivers/` también. Si el PC del equipo necesita el controlador del puerto serie de la tarjeta, Cristian debe agregarlo.

## DECISIONES SIN CONFIRMAR
- **K9-1:** en el equipo de pruebas, el LEEME pide desmarcar «Configurar este PC como estación del autoclave» en el Setup hasta validar la casilla en un PC de prueba (D9-11 lo pide así). Viene marcada por defecto en el Setup (D9-11), lo cual no se cambió.

## Verificar en sitio
- La actualización real B → D con el Setup (sección 8c) y los casos de banco C-05 a C-05h (S9), B-13 (B9, con la pregunta del tipo de puerta), A-E9-01/02 y D-E9-01 a 03 (E9), D-X9-01/02 (X9).
- Que con la D la tarjeta conecta y que sin sensores de presión aparecen SEN-06 y CIC-10 sin confirmación.
- El Setup y su casilla de estación en un PC de prueba, con la lista de `tools/instalador/LEEME.md`, antes de marcarla en el equipo.
