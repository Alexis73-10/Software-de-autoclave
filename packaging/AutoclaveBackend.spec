# -*- mode: python ; coding: utf-8 -*-

# uvicorn.run("autoclave.backend.server:app", ...) es un import dinámico por
# string — PyInstaller no lo puede seguir estáticamente desde main.py. Basta
# con forzar 'autoclave.backend.server' como hidden import: PyInstaller sí
# sigue estáticamente sus imports normales (context, state_machine, hal,
# devices, services...) una vez que sabe que ese módulo entra al build.
# No se usa collect_submodules('autoclave') a propósito: arrastraría también
# ui/ui_pyside/ui_qml (Tk, PySide6, QML) que el backend nunca importa y que
# hace el build extremadamente lento.

# ORG-07 (tanda 15): el .spec vive en packaging/; las rutas del repositorio
# (script, pathex, datas, sys.path) son relativas a RAIZ. Se compila desde
# la raíz:  pyinstaller --noconfirm packaging\AutoclaveBackend.spec
import os
RAIZ = os.path.abspath(os.path.join(SPECPATH, '..'))


def _r(ruta):
    return os.path.join(RAIZ, ruta)


def _rel(datas):
    # (origen relativo a RAIZ, destino); un origen absoluto queda igual
    return [(_r(origen), destino) for origen, destino in datas]

a = Analysis(
    [_r('src\\autoclave\\backend\\main.py')],
    pathex=[_r('src')],
    binaries=[],
    datas=_rel([
        ('src/autoclave/images', 'autoclave/images'),
        # D9-7 (tanda 9): solo los programas de fábrica (ver Autoclave.spec)
        ('src/autoclave/cycles/factory', 'autoclave/cycles/factory'),
        ('src/autoclave/config', 'autoclave/config'),
    ]),
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
a.datas.append((_CORREO, _r('src/autoclave/config/plantillas/correo_neutro.json'), 'DATA'))
_ciclos_ajenos = [d[0] for d in a.datas
                  if d[0].replace('\\', '/').startswith('autoclave/cycles/')
                  and not d[0].replace('\\', '/').startswith('autoclave/cycles/factory/')]
if _ciclos_ajenos:
    raise SystemExit(f'D9-7: solo cycles/factory va en la entrega; sobran {_ciclos_ajenos}')
# LIC-01 (licencia L0): secretos de activación desde el archivo fuera del
# repositorio (installation/secretos.py), como config/activacion_secretos.json.
# Sin archivo válido la compilación se detiene.
import os
import sys as _sys
_sys.path.insert(0, _r('src'))
from autoclave.installation.secretos import entrada_compilacion
a.datas.append(entrada_compilacion())
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
