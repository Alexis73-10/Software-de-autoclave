# -*- mode: python ; coding: utf-8 -*-
#
# Generador de códigos (G1, tanda 2): un solo .exe de doble clic, SIN consola.
# Arranca el servidor y abre el navegador en http://localhost:<puerto>; si ya
# hay una instancia en el puerto, solo abre el navegador.
#
# Los datos (generador.db, config.json, Respaldos\, generador.log, la clave
# inicial del admin) NO van dentro del ejecutable: viven en
# C:\ProgramData\Especifika\Generador\ (o GENERADOR_DATOS). Por eso aquí no hay
# `datas`: no se empaqueta tools/generador/generador.db.
#
# Compilar (desde la raíz del repo, en el PC de Cristian):
#     pyinstaller packaging\GeneradorCodigos.spec
# Resultado: dist\GeneradorCodigos.exe. LIC-01 (licencia L0): el ejecutable NO
# lleva los secretos de activación; los lee en el PC donde corre del archivo
# %USERPROFILE%\Documents\especifika_secretosctivacion.json (o
# ESPECIFIKA_SECRETOS). Sin ese archivo el generador no arranca. Aun así, no
# copiarlo a ningún PC de cliente.

# ORG-07 (tanda 15): el .spec vive en packaging/; las rutas del repositorio
# (script, pathex) son relativas a RAIZ. Se compila desde
# la raíz:  pyinstaller --noconfirm packaging\GeneradorCodigos.spec
import os
RAIZ = os.path.abspath(os.path.join(SPECPATH, '..'))


def _r(ruta):
    return os.path.join(RAIZ, ruta)


a = Analysis(
    [_r('tools\\generador\\lanzador.py')],
    pathex=[_r('tools\\generador'), _r('src')],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app',
        'autoclave.installation.activation',
        'autoclave.backend.contrasenas',
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
        'multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # nada del software del autoclave más allá de activation y contrasenas
    excludes=['PySide6', 'tkinter', 'autoclave.backend.server', 'autoclave.ui',
              'autoclave.ui_qml', 'autoclave.ui_pyside'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GeneradorCodigos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
