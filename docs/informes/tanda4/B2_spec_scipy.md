# B2 — `Autoclave.spec` ya no excluye `scipy`

**Problema:** `qfluentwidgets` importa `scipy.ndimage` al cargar (`common/image_utils.py`). Con `scipy` en `excludes`, el menú PySide (engrane: calibración, Entradas/Salidas) probablemente no abría en el .exe.

**Medición** (importando `backend.server`, `backend.main`, `ui_pyside.main_window/app`, `ui_qml.app`, `exe_unico` en un intérprete limpio): se cargan transitivamente `scipy`, `numpy`, `PIL`, `colorthief`, `darkdetect`, `qframelesswindow`, `win32api/con/gui/print`, `defusedxml`, `unittest`, `PySide6.QtSvg/QtSvgWidgets/QtXml/QtQml/QtNetwork`, `serial`, `uvicorn`, `fastapi`, `pydantic`, `yaml`, `ruamel`. De los `excludes` restantes (`autoclave.simulador`, `pytest`, `matplotlib`, `tkinter`, QtWebEngine*, Qt3DCore, QtQuick3D, QtPdf, QtCharts, QtGraphs, QtMultimedia, QtDataVisualization) ninguno se importa (`QtMultimedia` de qfluentwidgets solo carga bajo demanda, no al abrir el menú). `qfluentwidgets`/`qframelesswindow` no traen archivos de datos (solo `.py`), no hace falta `collect_data_files`.

**Cambio:** se quita `'scipy'` de `excludes` y se deja comentario. El resto no se tocó. Efecto esperado: la carpeta `dist/Autoclave` crece (scipy+numpy).

**Pruebas** (`tests/test_b2_spec_excludes.py`): el spec no excluye ningún módulo de la lista de imprescindibles ni submódulos de paquetes de terceros imprescindibles; `scipy` no está excluido; en un intérprete limpio, nada de lo excluido (salvo `autoclave.simulador`, que solo corre con `python -m`) queda cargado al importar las 5 entradas; `autoclave.ui_pyside.main_window` se importa en `QT_QPA_PLATFORM=offscreen`.

**Comando de compilación (NO ejecutado):** desde la raíz del repo, con el entorno del proyecto:
`pyinstaller --noconfirm Autoclave.spec` → `dist\Autoclave\Autoclave.exe` (+ `_internal\`).

**Cinco comprobaciones a mano con el .exe**
1. El engrane abre el menú de ajustes (ventana PySide visible, sin cierre inmediato).
2. Login técnico/ingeniero en el menú y apertura de Calibración (lee valores, guarda con 200).
3. Entradas/Salidas: se ven las tarjetas de DI/DO/temperatura/presión con valores.
4. Un login incorrecto muestra el mensaje y no deja sesión; el correcto deja el token (opciones sensibles responden sin 401).
5. Cierre limpio: cerrar el menú y luego el programa no deja procesos `Autoclave.exe` colgados (Administrador de tareas) ni el puerto 8000 ocupado.

**Decisiones sin confirmar:** ninguna.
