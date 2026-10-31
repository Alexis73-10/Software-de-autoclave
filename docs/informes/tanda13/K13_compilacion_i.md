# K13 — Compilación I (tanda 13)

Fecha: 24-oct-2026, noche. Lo hizo la sesión principal entre las 23:25 y las 23:45 (hora de Bogotá), sin subagentes.

**Sí hay compilación I y se recomienda instalarla el lunes 26-oct en lugar de la H.**
- Se instala con `Autoclave_Setup_1.0.0-i.exe` siguiendo la sección 8h del LEEME:
  - H → I, si el equipo ya tiene la H;
  - G → I, si sigue en la G.
- Deje marcada «Actualizar (conserva los datos)».
- Para los ciclos se sigue el bloque T12 de la hoja de banco, que ya tiene las cifras recalculadas con IAPWS-IF97.

La I es la H más dos cambios:
- **VAP-01**: saturación con IAPWS-IF97, ver `S13_saturacion_if97.md`;
- **Licencia L0**: estaba unida a `dev` después de la H, ver `docs/informes/licencia/L0_secretos_y_contrasenas.md`.

## Origen
- `tanda-13` se unió a `dev` con `--no-ff` en el commit 1abcf28, «Merge tanda-13 en dev (VAP-01: saturación con IAPWS-IF97)». La etiqueta `inst-2026-10-24-i` apunta a 1abcf28.
- La suite se corrió sobre b84e758; hasta 1abcf28 solo se agregó documentación. Con `pytest tests -n auto` dio **7808 passed, 11 failed, 10 skipped, 3 xfailed**:
  - en serie pasan 9 de los 11;
  - quedan las 2 rojas ajenas de `test_config_correo`, que dependen de `data/correo_equipo.json` del PC de desarrollo, igual que en L0;
  - total: **7817 passed**.
  - Detalle en S13 §6.
- La compilación se hizo en un worktree limpio, desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_i`), con `git status` vacío.

## Entorno
Igual que en K12: el entorno virtual `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3, PyInstaller 6.20.0). El `pip freeze` está en `entrega/2026-10-24_i/entorno_build.txt`. Desde la H solo cambiaron los `.spec` de L0, que agregan el recurso de secretos; los requisitos no cambiaron.

## Comandos
- `python -m PyInstaller --noconfirm Autoclave.spec`: salida 0, unos 283 s (`suites/build_autoclave.log`).
  - LIC-01 imprimió «secretos de activación de `…\especifika_secretos\activacion.json` (huella instalación **1742ee57**, fábrica **f44eb00d**)». El archivo de secretos no se abrió ni se imprimió; solo lo leyó el `.spec`.
  - El `PYZ` contiene:
    - `autoclave.core.runtime.steam`, con las funciones de IF97 (`_ps_mpa`);
    - `core.managers.catalogo_parametros`, con `_psat`;
    - `ui_qml.domain.consignas`.
  - Se comprobó con `ZlibArchiveReader`.
- `python -m PyInstaller --noconfirm GeneradorCodigos.spec`: salida 0 (`suites/build_generador.log`).
- `ISCC.exe /Q /DEntrega=…\entrega\2026-10-24_i /DAppVer=1.0.0-i /DAppVerNum=1.0.0.9 tools\instalador\autoclave.iss`: salida 0 (`suites/iscc.log`).
  - Se lanzó desde PowerShell, con el `.iss` de la etiqueta.
  - **El Setup no se ejecutó.**

Advertencias del build: las mismas de K8 a K12 (hidden imports opcionales `tzdata`, `importlib_resources.trees` y `scipy.special._cdflib`), más el aviso de siempre del plugin QML `assetdownloader`.

## Verificaciones
`python tools/verificar_entrega_neutra.py dist/Autoclave` salió con 0:
- la calibración es neutra (sha256 4f13c26f…8347162);
- el correo es neutro (d76b44a1…2a3f86);
- solo está `cycles/factory`, con 4 programas.

`Autoclave/` tiene **2301 archivos** y pesa 311 MB.
- La H tenía 2300. El archivo de más es `_internal/config/activacion_secretos.json`, de L0 (riesgo conocido, que se cierra en L1).
- No hay `installation_profile.json*`, `*.db`, `data/` ni `.claude/`.

## Prueba de humo (`suites/humo_i.log`)
Se hizo sobre una copia en `C:\Users\tecni\t13tmp\humo_i`, que se borró al terminar, con `Autoclave.exe --portable` y `_suites_t13/humo.py` (copia del de K12, no versionado):
- a los 60 s corrían el lanzador, `--rol ui --door 1 --screen 0` y `--rol ui --door 2 --screen 1`;
- la puerta 1 mostraba **INSTALACIÓN DEL EQUIPO, Paso 1 de 9 · Activación** (`prueba_humo_asistente.png`). Son 9 pasos porque L0 agregó «Contraseñas»; la H tenía 8;
- la puerta 2 mostraba el reposo con **«Instalación en curso en la pantalla 1»** (`prueba_humo_pantalla2.png`);
- `lanzador.log`, `ui_puerta1.log`, `ui_puerta2.log` y `autoclave.log` no tienen `Traceback`, `ERROR`, `CRITICAL` ni `COM<n>`;
- al final se cerraron los procesos y no quedó ninguno vivo.

## Actualizaciones H → I y G → I (ensayo sobre copias, `suites/ensayo_i.log`)
Se usó el guion nuevo `tools/ensayo_actualizacion_i.py`, que reutiliza los de K12 y E9. Cada fase usa el código de su etiqueta y su `_internal` real:
- G: `_t12_k12_tmp/repo_g` y `entrega/2026-10-23_g`;
- H: `repo_h` y `entrega/2026-10-24_h`;
- I: el worktree de la etiqueta I y `dist/Autoclave/_internal`.

Las fases llaman a las funciones reales de arranque (`_avisar_migraciones_correctivas` y `auditar_migraciones_correctivas`).

```
== H -> I (G -> H -> I) ==
H migraciones: bowe_dick / presion_add_calentamiento 99.0 -> 9.0 (migración tanda 12) | avisos SIS-06 | .bak
I migraciones: []   I avisos: []   dañados: {}
I consigna mostrada a 134 °C: 304.2 | chaqueta: 134_instrumental 328.2, bowe_dick 332.67, instrumental_121 229.04, liquidos 231.04
OK: sin errores []
== G -> I ==
I migraciones: bowe_dick / presion_add_calentamiento 99.0 -> 9.0 (migración tanda 12)
I avisos: SIS-06|bowe_dick/...  .bak: bowe_dick.json.bak  dañados: {}
I consigna mostrada a 134 °C: 304.2 | chaqueta: 134_instrumental 328.2, ...
OK: sin errores []
```

Lo que confirma el ensayo:
- **Los programas de usuario cargan en la I** por los dos caminos y ninguno queda dañado ni rechazado por las validaciones 350/385 con la tabla nueva.
- **Desde la H**, la migración no se repite y no aparece un SIS-06 nuevo.
- **Desde la G**, la I hace lo mismo que hacía la H: 99 → 9, fila de auditoría, SIS-06 y `.bak`.
- La chaqueta 350/25 se conserva. `brecha_segura_temperatura` sigue en 0,3, como en la H.
- **La consigna mostrada a 134 °C es 304.2 kPa**: es `consigna_esterilizacion`, la de la gráfica del PDF. La consigna de chaqueta del Instrumental 134 de usuario es **328.2 kPa**; la H daba 302.3 y 326.3.
- Se conservan el perfil, el usuario propio, el parámetro del equipo, la calibración y el correo del sitio. La BD queda en la versión 11 en los dos caminos.

## LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/`, `entrega/2026-10-24_i/` y `usb/`)
Se agregaron:
- el título de la compilación I;
- el aviso de cabecera de la tanda 13 («instale la I en lugar de la H»);
- el aviso de L0, que ahora dice «incluida desde la compilación I»;
- la tabla **«Cambios respecto a la H»**: suite, Psat vieja y nueva, umbrales que se mueven unos 2 kPa, programas sin cambios, L0 y versión del Setup;
- la sección **8h**: H → I y G → I con el Setup, qué comprobar (sin SIS-06 nuevo desde la H, SIS-07 de L0, «consigna de chaqueta 328.2 kPa» en el log) y cómo volver a la H.

## Entrega (`entrega/2026-10-24_i/`, no versionada)
Contiene:
- `Autoclave/`;
- `Autoclave_2026-10-24_i.zip` (`testzip` sin errores, 2301 archivos);
- `Autoclave_Setup_1.0.0-i.exe` (87 MB);
- `GeneradorCodigos.exe`;
- `SHA256SUMS.txt` y `MANIFIESTO_CARPETA_Autoclave.sha256`, los dos verificados con `sha256sum -c`;
- `entorno_build.txt`;
- `LEEME_INSTALACION.md`;
- las dos capturas de la prueba de humo;
- `usb/`.

```
971d75385c61d8ec896b919e1d67d8e05904928b426060e6b874e121da431961 *Autoclave_Setup_1.0.0-i.exe
7ed2c81ad95aa40682ab48c69f77e434cf1bf99b3079b81101c20eb2b6ec8c29 *Autoclave_2026-10-24_i.zip
9e47eb1bbbafec9fdea163208dc56dd3bf79b4842f34f0ba45f72537ae8e0b33 *GeneradorCodigos.exe
d34eae177b13348f76a93f08480c3140ce877d7ab8aa2b66d6d960646d5f1149 *Autoclave/Autoclave.exe
65d1749f790eaae133a9a422a439b71a46cc4c31311c102fe29a6863fad59f6d  MANIFIESTO_CARPETA_Autoclave.sha256 (2301 archivos)
```

### `usb/` (exactamente lo que va a la USB)
- `Autoclave_Setup_1.0.0-i.exe`;
- `SHA256SUMS.txt`, solo con la línea del Setup (`sha256sum -c` sobre el Setup copiado: OK);
- `LEEME_INSTALACION.md`;
- `drivers/`.

El generador queda en `entrega/2026-10-24_i/`, fuera de `usb/`. No se copió nada a ninguna USB.

**Pendiente:** `entrega/drivers/` sigue vacía, así que `usb/drivers/` también.

## Importante sobre L0 (para Cristian)
- **El `GeneradorCodigos.exe` de la I** se compiló con el mismo archivo de secretos (huella de instalación 1742ee57).
- **Los códigos de activación del generador anterior no sirven para una instalación limpia con la I.** Sí sirven para la actualización H → I o G → I, que no pasa por el asistente.
- Antes de una instalación nueva, compruebe que la huella de la página **Usuarios** del generador sea **1742ee57**.

## Verificar en sitio
- Hacer la actualización real (sección 8h). Comprobar:
  - que no aparece un SIS-06 nuevo desde la H;
  - que, en el primer ciclo, el log dice «consigna de chaqueta 328.2 kPa» para el Instrumental 134 de usuario.
- El lunes, correr el bloque T12 de la hoja de banco con las cifras de la I. Hay que estar atentos a la falla por presión baja, que ahora está en 302,2 kPa a 134 °C (antes, en la práctica, se disparaba a ≈ 300,3 kPa reales, porque la H calculaba Psat 2 kPa por debajo).
- Sigue pendiente el problema urgente 1 de la tanda 12: el techo a 134 °C/9 (313,2 kPa ≈ 135,0 °C) queda por debajo de la salida de RECUPERACION con brecha 1,0. Con la brecha de 0,3 de los programas de usuario no aplica.
