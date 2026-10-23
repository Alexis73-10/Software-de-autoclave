# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src\\autoclave\\ui_pyside\\app.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/autoclave/images', 'autoclave/images'),
        # D9-7 (tanda 9): solo los programas de fábrica (ver Autoclave.spec)
        ('src/autoclave/cycles/factory', 'autoclave/cycles/factory'),
        ('src/autoclave/config', 'autoclave/config'),
    ],
    hiddenimports=[],
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
