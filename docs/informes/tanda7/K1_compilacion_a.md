# K1 — Compilación A (base estable)

Fecha: 22-oct-2026, 00:14–00:34 (hora de Bogotá). Sesión principal.

## Origen
- Etiqueta `inst-2026-10-22-a` → `dev` 18eb429 ("Merge tanda-6 en dev (docs push)").
- Suite en ese código (rama `tanda-7` = 18eb429 + solo docs): **5020 passed, 2 skipped, 3 xfailed** (20 min 08 s).
- Compilado en un worktree limpio desprendido de 18eb429 (`C:\Users\tecni\Documents\_build_a`), sin archivos sin commit.

## Entorno
- Python 3.14.3 (instalación del sistema, `C:\Users\tecni\AppData\Local\Programs\Python\Python314`; el proyecto no usa entorno virtual).
- PyInstaller 6.20.0. Aviso de PyInstaller: "Running PyInstaller as admin is not necessary" (la consola corre como administrador); sin efecto en el resultado.
- `pip freeze` exacto: `entrega/2026-10-22_a/entorno_build.txt` (149 paquetes).

## Specs de producción
- `Autoclave.spec` (onedir; `exe_unico.py`: backend + pantallas QML + ajustes en un solo ejecutable con `--rol`). Es el que reemplazó a `AutoclaveBackend.spec`/`AutoclaveSettings.spec`/`AutoclaveUI` (tanda 2, R1; LEEME de la tanda 4). Esos specs viejos NO se compilaron.
- `GeneradorCodigos.spec` (herramienta para generar el código de activación del día; se entrega aparte para la instalación).

Comandos: `python -m PyInstaller --noconfirm Autoclave.spec` (salida 0, ~232 s) y `python -m PyInstaller --noconfirm GeneradorCodigos.spec` (salida 0, ~49 s).

## Advertencias del build
Autoclave.spec (7, ninguna bloqueante):
- hidden imports no encontrados: `pycparser.lextab`, `pycparser.yacctab`, `importlib_resources.trees`, `scipy.special._cdflib` (módulos opcionales de dependencias; ya aparecían antes);
- 3 avisos de bibliotecas de macOS ignoradas (`serial.tools.list_ports_osx`, `darkdetect._mac_detect`).

GeneradorCodigos.spec: 1 (`importlib_resources.trees`).

## Contenido verificado
- `Autoclave/`: 329 MB, 2942 archivos; primer nivel: `Autoclave.exe`, `_internal/`.
- Recursos presentes en `_internal/autoclave/`: `config/`, `cycles/factory` (4 programas) y `cycles/user`, `i18n/es.json` y `en.json`, `images/`, `ui_qml/qml` y `ui_qml/assets`.
- Ausentes (comprobado con `find`): `installation_profile.json*`, `data/`, `*.db`, `.claude/`, logs, fotos de capturas. `config/correo.json` lleva remitente y destinos, sin contraseña (la contraseña vive en el almacén de credenciales de Windows).
- `GeneradorCodigos.exe`: 18 MB (onefile).

## Prueba de humo (copia en `C:\Users\tecni\t7tmp\humo_a`, borrada al final)
1. `Autoclave.exe` sin argumentos fuera de Archivos de programa: muestra "¿Instalar Autoclave en este PC?" (Programa `C:\Program Files\Especifika\Autoclave`, Datos `C:\ProgramData\Especifika\Autoclave`). Se respondió **No** para no instalar nada en este PC: el proceso termina (comportamiento de diseño de `instalador_exe.ofrecer_instalacion`).
2. `Autoclave.exe --portable`: a los 60 s corren el lanzador y `--rol ui --door 1 --screen 0`; ventana "Autoclave" con **INSTALACIÓN DEL EQUIPO, Paso 1 de 7 · Activación** (número de serie y código de 12 caracteres). Captura: `entrega/2026-10-22_a/prueba_humo_asistente.png`.
3. Sin traceback ni ventana de error. Sin perfil no arranca el backend del control, así que no se abrió ningún puerto COM (la etapa `verificando_instalacion` corta antes del serial).
4. Procesos cerrados y copia borrada.

No probado aquí (requiere instalar en Archivos de programa o la tarjeta): la instalación elevada y el arranque con perfil. Verificar en sitio.

## Entrega (`entrega/2026-10-22_a/`, no versionada; `/entrega/` agregado a `.gitignore`)
| Archivo | SHA-256 |
|---|---|
| `Autoclave_2026-10-22_a.zip` (152 MB; contiene `Autoclave/` y `GeneradorCodigos.exe`) | `63ad9ff2feb149a909f2649a815fc8148d8f538600fccbb686c98963f13deed7` |
| `GeneradorCodigos.exe` | `b0c08a6b81ef3814023e63cf3066cb27c476a41bb9d5d8a5b20c4f6a27d06428` |
| `Autoclave/Autoclave.exe` | `c4c8b2e21d7bf8b81832f611e1e2230887e9f35728f47a5a97d9659fb89ad5e2` |
| carpeta `Autoclave/` (SHA-256 del manifiesto `MANIFIESTO_CARPETA_Autoclave.sha256`, 2942 archivos ordenados) | `aa5f0df4217c57042615376885e993e3a22ee0d56cc42efc93f62b84d421602b` |

Además: `SHA256SUMS.txt`, `entorno_build.txt`, `LEEME_INSTALACION.md` (borrador; P1 escribe el definitivo) y la captura de la prueba de humo.

## Resultado
K1 HECHA. La compilación A es instalable y queda como respaldo garantizado para las 14:00.
