# K12 — Compilación H (tanda 12)

Fecha: 24-oct-2026. Lo hizo la sesión principal entre las 18:45 y las 19:00 (hora de Bogotá).

**Sí hay compilación H y se recomienda instalarla** en el equipo de pruebas antes de los ciclos del lunes 26-oct. Se instala con `Autoclave_Setup_1.0.0-h.exe` siguiendo la sección 8g del LEEME (G → H), con «Actualizar (conserva los datos)» marcada. Después se siguen los casos del bloque T12 de la hoja de banco.

## Origen
- `tanda-12` se unió a `dev` con `--no-ff` en el commit d660c06, «Merge tanda-12 en dev (A0, J12, P12, E12, L12, V12)». En ese momento `git diff tanda-12 dev` estaba vacío.
- La etiqueta `inst-2026-10-24-h` apunta a d660c06.
- La suite se corrió sobre 151599e: es el mismo código que d660c06, que después de 151599e solo agrega documentación. Con `pytest -n auto` dio **7522 passed, 9 failed, 10 skipped, 3 xfailed** en 6 min 40 s (`suites/integ_final.log`).
  - Los 9 rojos son de impresión y de las vistas de calibración/QML. En serie pasan los 9 (`suites/integ_final_serie.log`). Son interferencia del paralelo; los mismos archivos fallaban así en la línea base.
  - Total: **7531 passed**. La línea base era 7218.
- La compilación se hizo en un worktree limpio, desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_h`), con `git status` vacío.

## Entorno
Igual que en K11: el entorno virtual de L8 `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3) con PyInstaller 6.20.0. El `pip freeze` está en `entrega/2026-10-24_h/entorno_build.txt`. La tanda 12 no cambió requisitos ni archivos `.spec`.

## Comandos
- `python -m PyInstaller --noconfirm Autoclave.spec`: salida 0, unos 280 s.
  - En el `PYZ` del ejecutable están `autoclave.core.runtime.steam` (con `t_saturacion_c`), `cycle_phases.esterilizacion`, `core.managers.catalogo_parametros` y `backend.context`. Se comprobó con `CArchiveReader`.
  - Los 4 programas de fábrica empaquetados son los de la tanda 12 (`presion_add` con máximo de catálogo 30).
- `python -m PyInstaller --noconfirm GeneradorCodigos.spec`: salida 0.
- `ISCC.exe /Q /DEntrega=...\entrega\2026-10-24_h /DAppVer=1.0.0-h /DAppVerNum=1.0.0.8 tools\instalador\autoclave.iss`: salida 0. Se lanzó desde PowerShell, porque Git Bash reescribe los argumentos `/D…`. **El Setup no se ejecutó.**

Advertencias del build: las mismas de K8 a K11 (hidden imports opcionales `tzdata`, `importlib_resources.trees` y `scipy.special._cdflib`).

## Verificaciones
`python tools/verificar_entrega_neutra.py dist/Autoclave` salió con 0:
- la calibración es neutra (sha256 4f13c26f…8347162);
- el correo es neutro (d76b44a1…2a3f86);
- solo está `cycles/factory`, con 4 programas.

`Autoclave/` tiene 2300 archivos y pesa 311 MB. No hay `installation_profile.json*`, `*.db`, `data/` ni `.claude/`.

## Prueba de humo
Se hizo sobre una copia en `C:\Users\tecni\t12tmp\humo_h`, que se borró al terminar, con `Autoclave.exe --portable` y el guion `_suites_t12/humo.py` (no versionado: psutil más PrintWindow):
- a los 60 s estaban corriendo el lanzador, `--rol ui --door 1 --screen 0` y `--rol ui --door 2 --screen 1`;
- la puerta 1 mostraba **INSTALACIÓN DEL EQUIPO, Paso 1 de 8 · Activación** (`entrega/2026-10-24_h/prueba_humo_asistente.png`);
- la puerta 2 mostraba el reposo con **«Instalación en curso en la pantalla 1»** (`prueba_humo_pantalla2.png`);
- `lanzador.log`, `ui_puerta1.log`, `ui_puerta2.log` y `autoclave.log` no tienen `Traceback`, `ERROR`, `CRITICAL` ni `COM<n>`;
- al final se cerraron los procesos y no quedó ninguno vivo.

## Actualización G → H (ensayo sobre una copia)
Se usó el guion nuevo `tools/ensayo_actualizacion_g_h.py`, que reutiliza el de B → D. Corre en dos fases:
1. **G:** con el código de la etiqueta G (`git archive inst-2026-10-23-g src`) y el `_internal` de `entrega/2026-10-23_g`. Siembra el equipo y copia los programas de usuario de la G, con el Bowie & Dick en `presion_add_calentamiento` 99.
2. **H:** con el código de la etiqueta H y **el `_internal` real de la H**. Llama a las funciones reales de arranque `BackendContext._avisar_migraciones_correctivas` y `auditar_migraciones_correctivas`.

Las carpetas de prueba quedaron en `C:\Users\tecni\Documents\_t12_k12_tmp` y el registro en `suites/ensayo_g_h.log`.

```
H: serial PRUEBA-001, version_bd 11, usuarios [Admin, Ingeniero, cristian], temp_max_apertura 75,
   marca_calibracion true, marca_correo true, programas de fábrica [4], fuentes [user]
H migraciones: bowe_dick / calentamiento / presion_add_calentamiento 99.0 -> 9.0, origen "migración tanda 12"
H auditoría: param_ciclo_cambio bowe_dick/calentamiento/presion_add_calentamiento 99.0 -> 9.0 (automatico, causa migracion_correctiva)
H avisos: SIS-06|bowe_dick/calentamiento.presion_add_calentamiento | .bak: bowe_dick.json.bak | dañados: {}
H 134_instrumental / bowe_dick: presion_chaqueta 350, rango 25 (se conservan); delta 1.5, margen 15, timeout_excursion 5
H instrumental_121 (250/25) y liquidos (300/50): claves nuevas presentes
OK: sin errores []
```

Lo que confirma el ensayo:
- **Los programas de usuario de la G cargan en la H** y ninguno queda dañado.
- **`bowe_dick` migra de 99 a 9** y deja su fila de auditoría, el aviso SIS-06 y el archivo anterior en `.bak`.
- **La chaqueta 350/25 se conserva** sin migrar.
- **Hallazgo:** `brecha_segura_temperatura` sigue en **0,3** en los programas de usuario del equipo. Es una DECISIÓN SIN CONFIRMAR: no se migra. Está explicada en la sección 8g del LEEME, en la hoja de banco T12 y en DECISIONES_PARA_REVISAR, punto 2.

El primer intento dio un falso error porque el guion leía las migraciones después de auditar, y desde V12 (SAF-07) la lista se vacía al auditar. Se corrigió el guion en 0731155, después de la etiqueta. Solo cambia el guion, no el producto.

## LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/`, `entrega/2026-10-24_h/` y `usb/`)
Se agregaron:
- el aviso de cabecera de la H;
- la tabla **«Cambios respecto a la G»**, organizada por C-xx;
- la sección **8g**, G → H con el Setup: «Actualizar» marcada, qué comprobar (SIS-06, la auditoría, B&D en 9, la chaqueta 350/25 y anotar la brecha) y cómo volver a la G con el respaldo.

## Entrega (`entrega/2026-10-24_h/`, no versionada)
Contiene `Autoclave/`, `Autoclave_2026-10-24_h.zip` (generado con Python; `testzip` sin errores, 2300 archivos), `Autoclave_Setup_1.0.0-h.exe` (87 MB), `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256` (verificado), `entorno_build.txt`, `LEEME_INSTALACION.md`, las dos capturas de la prueba de humo y `usb/`.
```
ad71f1729cd5b1435b4e3e70424d902c20bc65add18e1ea590ffcefef869ed30 *Autoclave_Setup_1.0.0-h.exe
bfb61b33d08c0d4a61bfc87550c5ce4a83fa9e54794d93c6698176dc09e7a8c8 *Autoclave_2026-10-24_h.zip
7040ca5f2dee1ffd0312cfe6eb8e479d51323d79359deb9c57dba680163d2499 *GeneradorCodigos.exe
3a871f4409df500de8c8839d79fcc15d59138c795308fe89c2fc844ceadc2068 *Autoclave/Autoclave.exe
05a553edadcdf5154c70896e7aed5825d156eab82e9713c76fe9c6b12cd1e6e5  MANIFIESTO_CARPETA_Autoclave.sha256 (2300 archivos)
```

### `usb/` (exactamente lo que va a la USB)
- `Autoclave_Setup_1.0.0-h.exe`;
- `SHA256SUMS.txt`, solo con la línea del Setup (`sha256sum -c` sobre el Setup copiado: OK);
- `LEEME_INSTALACION.md`;
- `drivers/`.

El generador queda en `entrega/2026-10-24_h/`, fuera de `usb/`. No se copió nada a ninguna USB.

**Pendiente:** `entrega/drivers/` sigue vacía, así que `usb/drivers/` también.

## Verificar en sitio
- Hacer la actualización real G → H con el Setup (sección 8g) y luego el caso A-T12-01 de la hoja de banco: aviso SIS-06 en Preciclo y en la campana, B&D en 9 y la fila de auditoría.
- Antes del primer ciclo, anotar `brecha_segura_temperatura` de los programas de usuario.
- El lunes, correr los casos E-T12-01 a 04 y F-T12-01/02 de la hoja de banco: consigna de chaqueta, entrada a sostener con la presión de saturación, esterilización sin conmutación rápida, Bowie & Dick con 9, excursión de Referencia y ticket NO CONFORME.
