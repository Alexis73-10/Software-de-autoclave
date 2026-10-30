# -*- mode: python ; coding: utf-8 -*-

# ORG-07 (tanda 15): el .spec vive en packaging/; las rutas del repositorio
# (script, pathex, datas, sys.path) son relativas a RAIZ. Se compila desde
# la raíz:  pyinstaller --noconfirm packaging\AutoclaveSettings.spec
import os
RAIZ = os.path.abspath(os.path.join(SPECPATH, '..'))


# VER-04 (etapa VER): toda compilación lleva src/autoclave/_build_info.py
# (commit, etiqueta de entrega, fecha UTC, árbol sucio); lo lee autoclave._version.
import sys as _sys_ver
_sys_ver.path.insert(0, os.path.join(RAIZ, 'tools', 'entrega'))
from info_compilacion import generar_build_info
generar_build_info(RAIZ)


def _r(ruta):
    return os.path.join(RAIZ, ruta)


def _rel(datas):
    # (origen relativo a RAIZ, destino); un origen absoluto queda igual
    return [(_r(origen), destino) for origen, destino in datas]

a = Analysis(
    [_r('src\\autoclave\\ui_pyside\\app.py')],
    pathex=[_r('src')],
    binaries=[],
    datas=_rel([
        ('src/autoclave/images', 'autoclave/images'),
        # D9-7 (tanda 9): solo los programas de fábrica (ver Autoclave.spec)
        ('src/autoclave/cycles/factory', 'autoclave/cycles/factory'),
        ('src/autoclave/config', 'autoclave/config'),
    ]),
    hiddenimports=['autoclave._build_info'],   # VER-04
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoclaveSettings',
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
