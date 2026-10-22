# L1 — Lock de dependencias y lista SOUP (tanda 7, 22-oct-2026)

Rama: `tanda-7-l1`. No se tocó código del programa.

## Archivos modificados

- `requirements.lock.txt` — regenerado.
- `docs/riesgos/lista_soup.md` — versiones actualizadas y filas nuevas.
- `docs/informes/tanda7/L1_lock_soup.md` — este informe.

## requirements.lock.txt

**Cambio de codificación:** el archivo anterior estaba en **UTF-16 LE con CRLF** (Git lo trataba como binario, `-text`, así que los diffs no se podían leer). Ahora está en **UTF-8 sin BOM** (en la práctica, ASCII puro) con LF. Desde este commit Git lo trata como texto y los cambios se ven en los diffs. Las herramientas que lo lean como UTF-16 (no se encontró ninguna) dejarían de funcionar.

**Origen:** `C:\Users\tecni\t7tmp\entorno_build.txt`, la salida de `python -m pip freeze` del Python 3.14.3 del sistema, el mismo que ejecutó PyInstaller 6.20.0 en K1. Se comparó contra `importlib.metadata` del intérprete para PySide6, FastAPI, uvicorn, pydantic, pyserial, python-escpos, PySide6-Fluent-Widgets, scipy, PyInstaller, keyring, psutil, requests, pywin32, shiboken6 y starlette, y todas coinciden.

**Formato anterior:** no tenía cabecera. Era un `pip freeze` de 32 paquetes con un único comentario generado por pip (`# Editable install with no version control (autoclave==0.1.0)`). Se mantiene el formato de `pip freeze` (`paquete==versión`, una por línea, en orden alfabético) y se agregan **5 líneas de comentario** al inicio que dicen de dónde sale el archivo. pip ignora los comentarios.

**Qué se quitó:** solo la línea editable del propio proyecto, `-e git+https://github.com/Alexis73-10/Software-de-autoclave.git@0cfb4cc...#egg=autoclave`. Es el paquete `autoclave` instalado en modo desarrollo; no es una dependencia. No había entradas `file://`. Quedan 148 paquetes, todos con `==` (se validaron con `packaging.requirements`).

**Diferencias con el lock anterior:**
- Ya no está `serial==0.0.97`. Era un paquete de PyPI que no tiene nada que ver con pyserial y que usa el mismo nombre de módulo (`serial`), así que podía tapar a pyserial. En el entorno de compilación ya no está instalado. Esto es una mejora.
- Los 31 paquetes restantes del lock anterior siguen en la misma versión.
- Entran 117 paquetes que el lock anterior no tenía (PySide6, FastAPI, uvicorn, PyInstaller, scipy, etc.).

## lista_soup.md

- **Ninguna versión cambió** respecto a la tabla del 21-oct: todas coinciden con el entorno de compilación. Ahora la columna de origen dice `lock` (antes muchas decían `entorno`, porque el lock viejo no las tenía).
- **Filas nuevas**, marcadas **(nueva)**: requests 2.33.1, shiboken6 6.11.1, keyring 25.7.0, psutil 7.2.2, pywin32 311, PyInstaller 6.20.0 (su bootloader va dentro del `.exe`), pyinstaller-hooks-contrib 2026.5, altgraph/pefile (solo compilación).
- Versiones pedidas: PySide6 6.11.1, FastAPI 0.135.2, uvicorn 0.42.0, pydantic 2.12.5, pyserial 3.5, python-escpos 3.1, qfluentwidgets (PySide6-Fluent-Widgets) 1.11.2, scipy 1.17.1, PyInstaller 6.20.0, Python 3.14.3.
- **Revisión de uso:** se recorrieron los `import` de terceros en `src/` con `ast`. Solo se importan PySide6, qfluentwidgets, fastapi, uvicorn, pydantic, serial (pyserial), escpos, PIL, requests, keyring, psutil, ruamel, yaml y win32print. Por eso, en la columna "Uso" quedan marcados "(no se importa en `src/`)": SQLAlchemy (el registro usa `sqlite3`), httpx (el cliente usa `requests`), cryptography, qrcode, numpy, pandas, matplotlib, customtkinter/tk, python-multipart y PySideSix-Frameless-Window. A scipy se le corrigió el uso, que estaba "por completar": lo carga qfluentwidgets (según `Autoclave.spec`). No se borró ninguna fila.

## Pruebas

- Búsqueda en `tests/`, `src/` y `*.spec`: ninguna prueba ni script lee `requirements.lock.txt` ni `lista_soup.md`. No hay pruebas afectadas.
- Suite completa (`python -m pytest -q -p no:cacheprovider`): 5020 passed, 2 skipped, 3 xfailed (17 min 52 s; corrida por la sesión principal el 22-oct, 06:05). Línea base: 5020 passed / 2 skipped / 3 xfailed.

## DECISIONES SIN CONFIRMAR

1. **El lock trae el entorno completo de la máquina de compilación (148 paquetes).** Incluye muchos que el programa no usa (google-genai, playwright, PyAutoGUI, PyQt6, opencv-python, youtube-transcript-api, etc.). Motivo: la orden fue regenerarlo "desde el entorno con el que se compiló K1" y quitar solo lo evidentemente local, y es lo que reproduce exactamente ese entorno. Alternativa: recortarlo a las dependencias reales del programa (las de `pyproject.toml` más PyInstaller y sus dependencias transitivas). Commit: el de este informe y el anterior de la rama. Cómo revertir: `git checkout e8e42d7 -- requirements.lock.txt`.
2. **Cabecera de comentarios en el lock.** Motivo: que quede escrito de dónde sale. Alternativa: dejar el `pip freeze` sin comentarios. Para revertirla, borrar las 5 primeras líneas.
3. **Clase propuesta B para PyInstaller.** Su bootloader se distribuye dentro del `.exe` y arranca todo el programa. Alternativa: C, si se considera parte de la cadena de control.

## PREGUNTAS PARA CRISTIAN

1. ¿El lock debe ser el entorno completo de compilación (como quedó) o solo las dependencias del producto? Si es lo segundo, conviene compilar en un venv limpio para que el `.exe` no pueda arrastrar paquetes ajenos.
2. Los SOUP marcados "(no se importa en `src/`)", como SQLAlchemy, cryptography, qrcode, numpy, pandas, matplotlib y customtkinter, ¿se sacan de la lista SOUP y de `pyproject.toml`? Hay que confirmar antes si PyInstaller los mete en el `.exe` (revisar `build/Autoclave/xref-Autoclave.html` o el `warn-*.txt`).
3. `pyproject.toml` declara `pyqtgraph`, `tk` y `SQLAlchemy`, y `src/` no importa ninguno de los tres. Además le faltan `fastapi`, `uvicorn`, `requests`, `psutil` y `python-escpos`, que sí se importan. No se tocó porque está fuera del alcance de L1.

## Comprobaciones manuales para Cristian

- Abrir `requirements.lock.txt` en un editor y ver que se lea como texto normal (UTF-8).
- Revisar la tabla de `docs/riesgos/lista_soup.md` y las notas de uso.
