# -*- mode: python ; coding: utf-8 -*-
#
# Autoclave en una carpeta (onedir): backend + las dos pantallas QML + menú de
# ajustes. Entrada: src/autoclave/exe_unico.py (se relanza a sí mismo con --rol).
#   pyinstaller --noconfirm Autoclave.spec   ->  dist/Autoclave/Autoclave.exe (+ _internal/)
#
# 19-oct: antes era onefile; el .exe de 250 MB tardaba ~10 s en descomprimirse
# en cada apertura antes de mostrar nada. En carpeta no hay descompresión. Se
# reparte la carpeta dist/Autoclave entera (p. ej. en una USB); al abrirla
# fuera de Archivos de programa ofrece instalarse (instalador_exe.py).
#
# uvicorn.run de un string y los imports diferidos por rol no los sigue
# PyInstaller: se fuerzan como hidden imports. Los .qml, fuentes e iconos se
# cargan desde disco (resource_path), por eso van en datas.

# Módulos de Qt que el programa no usa (QML: QtQuick, Controls, Effects,
# Layouts, Shapes; Python: QtCore/Gui/Widgets/Qml/Quick/QuickWidgets/Network/
# PrintSupport). El hook de PySide6 arrastra todos los plugins QML; QtWebEngine
# solo eran 83 MB. opengl32sw.dll se conserva: es el OpenGL por software si el
# PC industrial no tiene controlador de vídeo.
_QT_SOBRANTES = (
    'webengine', 'webview', 'webchannel', 'quick3d', 'qt63d', 'qt3d', '/qml/qt3d',
    'virtualkeyboard', 'qt6pdf', 'qtpdf', '/qml/qtquick/pdf', 'graphs', 'charts',
    'datavisualization', 'multimedia', 'spatialaudio', 'location', 'positioning',
    'sensors', 'texttospeech', 'scxml', 'remoteobjects', 'serialbus', 'bluetooth',
    'nfc', 'designer', 'qt6help', 'qthelp', 'quicktimeline', 'lottie',
)


from PyInstaller.utils.hooks import collect_data_files


def _sobra(destino):
    d = destino.replace('\\', '/').lower()
    return d.startswith('pyside6/') and any(p in d for p in _QT_SOBRANTES)


a = Analysis(
    ['src\\autoclave\\exe_unico.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/autoclave/images', 'autoclave/images'),
        # D9-7 (tanda 9): solo los programas de fábrica. cycles/user y
        # cycles/defecto son del banco; en la primera instalación los programas
        # editables se siembran como copia de fábrica (utils/resources.py).
        ('src/autoclave/cycles/factory', 'autoclave/cycles/factory'),
        ('src/autoclave/config', 'autoclave/config'),
        ('src/autoclave/i18n/*.json', 'autoclave/i18n'),
        ('src/autoclave/ui_qml/qml', 'autoclave/ui_qml/qml'),
        ('src/autoclave/ui_qml/assets', 'autoclave/ui_qml/assets'),
        # capabilities.json de python-escpos (sin él no imprime ningún ticket)
        *collect_data_files('escpos'),
    ],
    hiddenimports=[
        'autoclave.backend.main',
        'autoclave.backend.server',
        # server.py la carga con importlib.import_module (R8): PyInstaller no la ve.
        'autoclave.backend.server_reasignacion',
        'autoclave.ui_qml.app',
        'autoclave.ui_pyside.app',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'PySide6.QtQuick',
        'PySide6.QtQuickControls2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # B2 (tanda 4): 'scipy' ya NO se excluye. qfluentwidgets lo importa al cargar
    # (image_utils -> scipy.ndimage) y con él excluido el menú de ajustes
    # (engrane) no abre. Lo que se excluye NO debe ser importado transitivamente
    # por qfluentwidgets, PySide6, uvicorn/fastapi/pydantic, serial ni win32:
    # lo vigila tests/test_b2_spec_excludes.py.
    excludes=['autoclave.simulador', 'pytest', 'matplotlib', 'tkinter',
              'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtWebEngineQuick', 'PySide6.Qt3DCore', 'PySide6.QtQuick3D',
              'PySide6.QtPdf', 'PySide6.QtCharts', 'PySide6.QtGraphs',
              'PySide6.QtMultimedia', 'PySide6.QtDataVisualization'],
    noarchive=False,
    optimize=0,
)
a.binaries = [b for b in a.binaries if not _sobra(b[0])]
a.datas = [d for d in a.datas if not _sobra(d[0])]
# D8-3.18 (tanda 8): la entrega lleva la calibración NEUTRA, no la del banco
# (config/calibration.yaml del repositorio). Se reemplaza la empaquetada por la
# plantilla; K8 lo comprueba con tools/verificar_calibracion_neutra.py.
_CALIB = 'autoclave/config/calibration.yaml'
a.datas = [d for d in a.datas if d[0].replace('\\', '/') != _CALIB]
a.datas.append((_CALIB, 'src/autoclave/config/plantillas/calibration_neutra.yaml', 'DATA'))
# D9-7 (tanda 9): correo NEUTRO (sin remitente ni destinatarios) y, de cycles/,
# nada que no sea factory/. El build se detiene si se cuela algo; después,
# K9 lo comprueba en la carpeta compilada con tools/verificar_entrega_neutra.py.
_CORREO = 'autoclave/config/correo.json'
a.datas = [d for d in a.datas if d[0].replace('\\', '/') != _CORREO]
a.datas.append((_CORREO, 'src/autoclave/config/plantillas/correo_neutro.json', 'DATA'))
_ciclos_ajenos = [d[0] for d in a.datas
                  if d[0].replace('\\', '/').startswith('autoclave/cycles/')
                  and not d[0].replace('\\', '/').startswith('autoclave/cycles/factory/')]
if _ciclos_ajenos:
    raise SystemExit(f'D9-7: solo cycles/factory va en la entrega; sobran {_ciclos_ajenos}')
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Autoclave',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Autoclave',
)
