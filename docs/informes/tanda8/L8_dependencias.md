# L8 — Dependencias (D8-3.26), tanda 8

Rama `tanda-8-l8`. Commits:
- `66993dd` build(tanda8-l8): lock solo del producto desde venv limpio, requirements-dev y pyproject (D8-3.26).
- `7213557` build(tanda8-l8): python-multipart a requirements-dev para el generador de códigos.
- (este informe).

## 1. Qué se hizo (por punto de D8-3.26)

| Punto | Estado | Detalle |
|---|---|---|
| `requirements.lock.txt` solo del producto, desde venv limpio | Hecho (`66993dd`) | 48 paquetes. Mismas versiones que el lock anterior (el de la tanda 7, que era el entorno completo de la máquina). Comprobado: los 48 del lock están en el `pip freeze` del venv con la misma versión; lo demás del venv es exactamente lo de `requirements-dev.txt`. |
| `requirements-dev.txt` aparte | Hecho (`66993dd`, ampliado en `7213557`) | Incluye el lock (`-r`) + pytest 9.0.3, httpx 0.28.1, PyInstaller 6.20.0, pyinstaller-hooks-contrib 2026.5 y, desde `7213557`, python-multipart 0.0.29. |
| `pyproject.toml`: fuera pyqtgraph, tk, SQLAlchemy; dentro fastapi, uvicorn, requests, psutil, python-escpos | Hecho y verificado | `dependencies` ya no tiene pyqtgraph/tk/SQLAlchemy y sí tiene los 5 pedidos. Extra `dev` con pytest, httpx, pyinstaller, pyinstaller-hooks-contrib y python-multipart. |
| Lista SOUP | Hecho | `docs/riesgos/lista_soup.md` (la vigente desde D1/L1): tabla del producto, tabla de herramientas y tabla de retirados. En `7213557` python-multipart pasó de "retirados" a "herramientas". |

### Hallazgo corregido en la verificación
El commit `66993dd` retiraba `python-multipart` por completo ("la API no recibe formularios"). Es cierto para `src/autoclave`, pero el **generador de códigos** (`tools/generador/app.py`, `GeneradorCodigos.spec`, que K1 compila) usa `fastapi.Form`, que exige python-multipart. Con el venv limpio, `tests/test_g1_generador.py` daba 7 errores (`RuntimeError` de FastAPI) y el `GeneradorCodigos.exe` no habría arrancado. Se agregó a `requirements-dev.txt` y al extra `dev` (no es del producto). Tras instalarlo: `test_g1_generador.py` + `test_generador_db.py` → 30 passed.

## 2. Cómo crear el venv

```
C:\Users\tecni\AppData\Local\Programs\Python\Python314\python.exe -m venv C:\Users\tecni\Documents\_venv_t8_producto
C:\Users\tecni\Documents\_venv_t8_producto\Scripts\python.exe -m pip install -r requirements.lock.txt -r requirements-dev.txt
C:\Users\tecni\Documents\_venv_t8_producto\Scripts\python.exe -m pip install -e . --no-deps
```
(desde la raíz del repo). Solo el producto (sin herramientas): `pip install -r requirements.lock.txt`.

Venv usado: `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3, `include-system-site-packages = false`). Contiene además los archivos de trabajo `producto_directas.txt`, `constraints_sistema.txt`, `venv_freeze*.txt` e `importar_todo.py` (no van al repo).

**Ojo para K8:** la instalación editable de `autoclave` en ese venv apunta al **worktree de L8** (`.claude\worktrees\agent-adb06df2611c6d3e7\src`). Los `.spec` ponen `pathex=['src']` delante, así que la compilación usa el `src` del directorio desde el que se lanza, pero antes de K8 conviene repetir `pip install -e . --no-deps` desde el repo principal (o desinstalar `autoclave` del venv) para que no quede apuntando a un worktree que se va a borrar.

## 3. Verificación de la compilación C con el venv limpio

Todo con `C:\Users\tecni\Documents\_venv_t8_producto\Scripts\python.exe` y `PYTHONPATH=<worktree>/src` (`autoclave.__file__` = `...\agent-adb06df2611c6d3e7\src\autoclave\__init__.py`).

1. Importación de todos los módulos de `src/autoclave`: **241 módulos, 0 fallos**.
2. `hiddenimports` de `Autoclave.spec` y `GeneradorCodigos.spec` (backend.main/server, ui_qml.app, ui_pyside.app, uvicorn.*, PySide6.QtQuick/QtQuickControls2, escpos, qfluentwidgets, scipy.ndimage, multipart, installation.activation, backend.contrasenas): **todos importan**.
3. Imports de terceros de `tests/`, `tools/` y `src/` (recorrido con `ast`): ninguno falta en el venv.
4. Pruebas que vigilan los `.spec` y herramientas: `test_b2_spec_excludes.py` + `test_adenda_herramientas_perfil.py` → 16 passed.
5. **Compilación de prueba fuera del repo** (`--distpath/--workpath` en `%TEMP%\l8_build`, lanzada desde el worktree, nada de build/dist en el repo):
   - `python -m PyInstaller --noconfirm Autoclave.spec` → salida 0, 310 s, carpeta `Autoclave` de 317 MB.
   - `python -m PyInstaller --noconfirm GeneradorCodigos.spec` → salida 0, 53 s, `GeneradorCodigos.exe` de 17 MB (con `multipart` dentro).
   - Avisos de `Autoclave.spec` (ninguno bloqueante): hidden imports no encontrados `tzdata`, `importlib_resources.trees`, `scipy.special._cdflib` (opcionales de dependencias; `tzdata` es nuevo porque ya no está en el venv y el programa no lo importa); 3 avisos de `ctypes` de librerías de macOS (pyserial, darkdetect); y un "Logging error" interno de PyInstaller (`TypeError: not enough arguments for format string` en un mensaje del modulegraph), sin efecto en el resultado.
   - Los ejecutables NO se arrancaron (el backend abriría puertos; queda para K8). La carpeta de prueba se borró; quedan solo los logs en `%TEMP%\l8_build\autoclave.log` y `generador.log`.

**Conclusión: el venv sirve para compilar la C (K8).**

### Hallazgo: compilar desde Git Bash mete una OpenSSL ajena
En la compilación de prueba entró `libssl-3-x64.dll` / `libcrypto-3-x64.dll` tomadas de `C:\Program Files\Git\mingw64\bin\` (están en el PATH de Git Bash; las pide el plugin TLS de Qt). Esa OpenSSL de Git no está en la lista SOUP. `libssl-3.dll` / `libcrypto-3.dll` (sin `-x64`) son las de CPython (`_ssl`) y sí son normales. Por eso la frase de la lista SOUP "ya no entra libssl/libcrypto-3-x64.dll" solo vale si se compila desde una consola sin Git en el PATH (PowerShell/cmd, como K1). **K8 debe compilar desde PowerShell/cmd** y comprobar que `_internal` no tiene `libssl-3-x64.dll`.

## 4. Pruebas
No hay pruebas nuevas (L8 no cambia código). No se corrió la suite completa: L8 solo toca `requirements*.txt`, `pyproject.toml` y documentos; las pruebas relevantes se listan arriba. La suite completa la corre la sesión principal al unir.

## DECISIONES SIN CONFIRMAR
1. python-multipart va en `requirements-dev.txt` (herramienta), no en el lock del producto, aunque viaja dentro de `GeneradorCodigos.exe`. Criterio: el generador no se instala en el equipo del cliente.
2. El bootloader de PyInstaller figura en las dos tablas SOUP (producto, porque va dentro del `.exe`; herramientas, porque se instala con dev). Se mantuvo como lo dejó `66993dd`.
3. Las versiones se congelaron iguales a las de la tanda 7 (no se actualizó nada), para que la C difiera de la B solo en lo que el programa no usa.

## PREGUNTAS PARA CRISTIAN
1. ¿Se deja constancia en el procedimiento de compilación (LEEME o K8) de que se compila desde PowerShell/cmd y no desde Git Bash, por la OpenSSL de Git?
2. ¿El generador de códigos y sus dependencias (python-multipart, FastAPI dentro del generador) deben tener su propia lista SOUP o basta con la tabla de herramientas?
3. Las columnas "Anomalías conocidas" siguen "Por completar": ¿quién y cuándo revisa las listas de errores de cada proyecto?

## Puntos de choque
`pyproject.toml`, `requirements.lock.txt`, `requirements-dev.txt`, `docs/riesgos/lista_soup.md`. Sin i18n, sin BD, sin QML.
