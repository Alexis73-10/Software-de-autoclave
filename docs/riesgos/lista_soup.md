# Lista SOUP (D1, tanda 6, 21-oct-2026; versiones actualizadas en L1, tanda 7; recortada al producto en L8, tanda 8, 22-oct-2026)

Origen de las versiones: desde L8 (tanda 8, D8-3.26), `requirements.lock.txt` tiene **solo las dependencias del producto**. Sale del `pip freeze` de un entorno virtual limpio (Python 3.14.3) en el que solo se instalaron las dependencias directas de `pyproject.toml`, con las versiones del entorno de compilación de la tanda 7 como restricciones. Las herramientas de prueba y compilación están en `requirements-dev.txt` (columna "Origen de la versión" = `dev`). Python sale del intérprete.

Cambios de versión respecto a la tabla de L1 (tanda 7): **ninguno**. Las 48 versiones del lock nuevo son las mismas que tenía el lock anterior.

Revisión de uso (L8): se recorrieron con `ast` todos los `import` de terceros de `src/autoclave` (incluidos los que están dentro de funciones). Solo se importan: PySide6, qfluentwidgets, fastapi, uvicorn, pydantic, serial (pyserial), escpos (python-escpos), PIL (pillow), requests, keyring, psutil, ruamel.yaml, yaml (PyYAML) y win32print (pywin32). Con el entorno limpio se importaron sin error los 241 módulos de `src/autoclave`.

Se comprobó además el contenido del ejecutable compilado con el entorno limpio (`Autoclave.spec`, PyInstaller 6.20.0): frente a la compilación B de la tanda 7, ya no entran `tzdata`, `cryptography` (con su `libssl/libcrypto-3-x64.dll` y `_cffi_backend`) ni `websockets`. Ninguno lo importa el programa.

La clase de riesgo es una propuesta según el uso. Las anomalías conocidas quedan por completar: no se revisaron las listas de errores de cada proyecto.

## SOUP del producto (van dentro del ejecutable)

| SOUP | Versión | Origen de la versión | Uso | Clase propuesta | Anomalías conocidas |
|---|---|---|---|---|---|
| Python (CPython) | 3.14.3 | entorno (intérprete) | Intérprete | C | Por completar |
| pyserial | 3.5 | lock | Comunicación con la ESP32 (control de actuadores) | C | Por completar |
| pydantic / pydantic_core | 2.12.5 / 2.41.5 | lock | Validación de perfiles y de la API | B | Por completar |
| FastAPI | 0.135.2 | lock | Backend HTTP (comandos de ciclo y puertas) | C | Por completar |
| starlette | 1.0.0 | lock | Base de FastAPI | C | Por completar |
| uvicorn (+ h11, click, anyio) | 0.42.0 (0.16.0, 8.3.1, 4.13.0) | lock | Servidor ASGI | B | Por completar |
| requests (+ urllib3, certifi, idna, charset-normalizer) | 2.33.1 (2.6.3, 2026.2.25, 3.11, 3.4.7) | lock | Cliente HTTP de la UI al backend (comandos de puertas, arranque) | B | Por completar |
| PySide6 (+Addons, Essentials) | 6.11.1 | lock | UI QML/Widgets (avisos NO ABRIR, alarmas) | B | Por completar |
| shiboken6 | 6.11.1 | lock | Enlace C++/Python de PySide6 | B | Por completar |
| PySide6-Fluent-Widgets (módulo `qfluentwidgets`), extra `full` | 1.11.2 | lock | Widgets de la UI (menú de ajustes) | A | Por completar |
| PySideSix-Frameless-Window / darkdetect / colorthief | 0.8.1 / 0.8.0 / 0.2.1 | lock | Dependencias de qfluentwidgets (no se importan en `src/`) | A | Por completar |
| scipy (+ numpy) | 1.17.1 (2.3.5) | lock | qfluentwidgets lo importa al cargar (`image_utils` -> `scipy.ndimage`); no se importa en `src/` (ver `Autoclave.spec`, B2 tanda 4) | A | Por completar |
| keyring (+ pywin32-ctypes, jaraco.*, more-itertools) | 25.7.0 | lock | Guardar la contraseña del correo de reportes | A | Por completar |
| psutil | 7.2.2 | lock | Estado de red y respaldo | A | Por completar |
| pywin32 | 311 | lock | Impresión en Windows (`win32print`) | B | Por completar |
| python-escpos | 3.1 | lock | Impresión del ticket (marca de carga no estéril) | B | Por completar |
| qrcode / python-barcode / appdirs / argcomplete / six / importlib_resources / setuptools | 8.2 / 0.16.1 / 1.4.4 / 3.7.0 / 1.17.0 / 7.1.0 / 82.0.1 | lock | Dependencias de python-escpos (no se importan en `src/`) | A | Por completar |
| pillow | 12.0.0 | lock | Imágenes (impresión en Windows) | A | Por completar |
| PyYAML | 6.0.3 | lock | Configuración | B | Por completar |
| ruamel.yaml | 0.19.1 | lock | Configuración (calibración, nombres de E/S) | B | Por completar |
| typing_extensions / typing-inspection / annotated-types / annotated-doc / colorama | 4.15.0 / 0.4.2 / 0.7.0 / 0.0.4 / 0.4.6 | lock | Dependencias de pydantic, FastAPI y click | A | Por completar |
| PyInstaller (bootloader) | 6.20.0 | dev | Su bootloader va dentro del `.exe` entregado y arranca todo el programa | B | Por completar |

## Herramientas (no se distribuyen; `requirements-dev.txt`)

| Herramienta | Versión | Origen de la versión | Uso |
|---|---|---|---|
| PyInstaller | 6.20.0 | dev | Empaquetado del ejecutable |
| pyinstaller-hooks-contrib | 2026.5 | dev | Hooks de empaquetado |
| altgraph / pefile / packaging | 0.17.5 / 2024.8.26 / 25.0 | dev | Dependencias de PyInstaller durante la compilación |
| pytest (+ pluggy, iniconfig, pygments) | 9.0.3 | dev | Pruebas |
| httpx (+ httpcore) | 0.28.1 (1.0.9) | dev | Lo necesita `fastapi.testclient` en las pruebas; el programa usa `requests` |
| python-multipart | 0.0.29 | dev | Formularios (`fastapi.Form`) del generador de códigos (`tools/generador`, `GeneradorCodigos.spec`). Va dentro de `GeneradorCodigos.exe`, que se queda en el PC de Especifika y NO se instala en el equipo del cliente |

## Retirados de la lista (L8, D8-3.26)

`python-multipart` estuvo en esta tabla en el commit 66993dd; se pasó a herramientas (arriba) porque el generador de códigos lo necesita (verificación de L8).

No los importa `src/autoclave` y ya no entran en el ejecutable compilado con el entorno limpio. Estaban en la tabla de L1 porque el lock anterior era el entorno completo de la máquina de compilación:

| Paquete | Versión anterior | Motivo |
|---|---|---|
| SQLAlchemy | 2.0.44 | El registro usa `sqlite3` de la biblioteca estándar. Quitado también de `pyproject.toml` |
| httpx | 0.28.1 | Pasa a herramienta de prueba (ver arriba) |
| cryptography | 48.0.0 | No se importa; con el entorno anterior entraba en el `.exe` |
| pandas | 2.3.3 | No se importa |
| matplotlib | 3.10.7 | No se importa (además está excluido en `Autoclave.spec`) |
| customtkinter / tk | 5.2.2 / 0.1.0 | UI antigua, no se importa. `tk` quitado de `pyproject.toml` |
| pyqtgraph | — | No se importa. Quitado de `pyproject.toml` |

Firmware ESP32 (`Hardware/Comunicacion_esclava_ESP32_V3`), su núcleo Arduino y sus librerías: versiones por completar.
