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
        # D9-7 (tanda 9): solo los programas de fábrica (ver Autoclave.spec)
        ('src/autoclave/cycles/factory', 'autoclave/cycles/factory'),
        ('src/autoclave/config', 'autoclave/config'),
    ],
    hiddenimports=[
        'autoclave.backend.server',
        # server.py la carga con importlib.import_module (R8): PyInstaller no la ve.
        'autoclave.backend.server_reasignacion',
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
# D9-7 (tanda 9): correo NEUTRO y nada de cycles/ que no sea factory/ (el build
# se detiene si se cuela algo). Igual que Autoclave.spec.
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
