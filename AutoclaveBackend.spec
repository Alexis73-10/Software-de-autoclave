# -*- mode: python ; coding: utf-8 -*-

# uvicorn.run("autoclave.backend.server:app", ...) es un import dinámico por
# string — PyInstaller no lo puede seguir estáticamente desde main.py. Basta
# con forzar 'autoclave.backend.server' como hidden import: PyInstaller sí
# sigue estáticamente sus imports normales (context, state_machine, hal,
# devices, services...) una vez que sabe que ese módulo entra al build.
# No se usa collect_submodules('autoclave') a propósito: arrastraría también
# ui/ui_pyside/ui_qml (Tk, PySide6, QML) que el backend nunca importa y que
# hace el build extremadamente lento.

a = Analysis(
    ['src\\autoclave\\backend\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/autoclave/images', 'autoclave/images'),
        ('src/autoclave/cycles', 'autoclave/cycles'),
        ('src/autoclave/config', 'autoclave/config'),
    ],
    hiddenimports=[
        'autoclave.backend.server',
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AutoclaveBackend',
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
