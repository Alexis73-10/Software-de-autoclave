# VER — Versionado automático 1.0.0-alpha.N

Fecha: 25-oct-2026. Instrucción: `docs/mis_plans/instruccion_claude_code_versionado.md`. Rama `versionado` desde `dev`, sin push y sin crear `v1.0.0-alpha.1`.

## Resumen para Cristian
- **Base:** `tanda-15` se unió a `dev` (b7560e6, «Merge tanda-15 en dev») como pedía el paso 0. Sin conflictos; la suite quedó como al cierre de la tanda 15 (7834 passed).
- **Hallazgo de trazabilidad (§1, 62304 §5.8.4): el `.exe` de las compilaciones actuales no sabe su versión.** Ver §1.
- **Fuente única:** `src/autoclave/_version.py`. Hoy dice `1.0.0-alpha.0` (= todavía sin entregas). La primera entrega que corra el script será la `1.0.0-alpha.1`.
- **Entrega en un comando:** `python tools\entrega\compilar_entrega.py` desde `dev` limpio. Ver §2 y la sección 10 del LEEME.
- **Antes de la primera entrega en el PC del banco**, mover fuera de `src/` tres archivos sin versionar que bloquean (y que hoy entran en cualquier compilación hecha desde ese árbol): `src/autoclave/config/calibration.yaml.bak`, `src/autoclave/i18n/es.json.bak` e `src/autoclave/images/icono autoclave.jpg`.
- **Pregunta urgente (P1):** los respaldos hechos con la I no se podrán restaurar en la alpha.1. Ver §4.
- Suite final: ver §6.

## 1. Verificación: la versión en el `.exe` de la I
Método: inspección de `entrega/2026-10-24_i/Autoclave/_internal/` y del entorno de compilación `_venv_t8_producto`, sin abrir el programa.
- `_internal/` solo trae 4 `*.dist-info` (`click`, `keyring`, `numpy`, `pydantic`) más la de `importlib_metadata` vendida dentro de `setuptools`. **No hay `autoclave-*.dist-info`.** Los `.spec` no usan `copy_metadata("autoclave")`.
- Además, `autoclave` **ni siquiera está instalado** en `_venv_t8_producto`: `importlib.metadata.version("autoclave")` da `PackageNotFoundError` ahí mismo.
- Por eso, en el `.exe` de la I (y en todas las anteriores) cada sitio caía a su valor de reserva:

| Dónde | Qué mostraba la I |
|---|---|
| Información del sistema (`GET /system/info`, `software.version`) | `None` → «—» |
| Panel «Información del equipo» (`ui_qml/bridge/info_equipo.py`) | `None` → «—» |
| Ticket de arranque | `Software        v?` |
| Registro de ciclo (columna `version_sw` de la base) y ticket de ciclo | `?` |
| Manifiesto de respaldo (`version_sw`) | `0` |

- Desde fuente sí salía `0.5.0`, porque el entorno de desarrollo tiene el paquete instalado en modo editable. Por eso no se veía en el banco.
- **Consecuencia:** ningún registro de ciclo hecho con un `.exe` (B a I) identifica la versión del software que lo controló.
- Corregido en esta etapa (VER-03/VER-05). Comprobado en una compilación real (§3).

## 2. Qué se hizo

### Fuente única (VER-01, VER-02, VER-03)
- `src/autoclave/_version.py`:
  - `VERSION_SEMVER = "1.0.0-alpha.0"` y `__version__ = "1.0.0a0"`;
  - las conversiones SemVer ↔ PEP 440;
  - `version_mostrada()` y `version_completa()`.
- Las dos asignaciones las reescribe solo el script de entrega.
- `pyproject.toml`: `dynamic = ["version"]` con `[tool.setuptools.dynamic] version = {attr = "autoclave._version.__version__"}`.
  - El backend de build es `setuptools.build_meta`; está instalado setuptools 82.0.1.
  - Se comprobó con `read_configuration`, que da `1.0.0a0`.
- Los 5 sitios (`backend/rutas/sistema.py`, `backend/rutas/respaldo.py`, `devices/printer/arranque_equipo.py`, `services/domain/logging/cycle_logger.py`, `ui_qml/bridge/info_equipo.py`) llaman a `version_completa()`.
- Pruebas estáticas:
  - ningún `.py` de `src/` llama `version("autoclave")`;
  - solo `_version.py` asigna `__version__`/`VERSION_SEMVER`.

### Identificación de la compilación (VER-04)
- `tools/entrega/info_compilacion.py` genera `src/autoclave/_build_info.py` (en `.gitignore`) con:
  - `COMMIT` (corto, 7);
  - `ETIQUETA`;
  - `FECHA_UTC`;
  - `SUCIO`.
- Lo llaman al empezar `Autoclave.spec`, `AutoclaveBackend.spec` y `AutoclaveSettings.spec`, así que **toda** compilación lo lleva, también las hechas a mano. `GeneradorCodigos.spec` no se tocó.
- Lo que se muestra:

| Caso | Mostrada | Completa (VER-05) |
|---|---|---|
| Entrega (etiqueta `v<versión>` y árbol limpio) | `1.0.0-alpha.N` | `1.0.0-alpha.N (1a2b3c4)` |
| Verificación (sin etiqueta) | `1.0.0-alpha.(N+1).dev+g1a2b3c4` | igual |
| Verificación con cambios sin commit | `1.0.0-alpha.(N+1).dev+g1a2b3c4.sucio` | igual |
| Desde fuente | `1.0.0-alpha.N+fuente` | igual |

### Dónde se ve (VER-05)
La versión completa aparece en:
- Información del sistema y el panel de información del equipo;
- el ticket de arranque;
- el registro (`version_sw`) y el ticket de cada ciclo;
- el manifiesto de respaldo;
- `GET /system/info`;
- la primera línea de cada log:
  - `lanzador.log`, `ui_puerta*.log` y `ajustes.log`: «Autoclave <versión> (<log>)»;
  - `backend.log`: «Autoclave <versión>: backend iniciado desde ...».

En los tickets, la versión larga se parte antes de `+` o ` (` en vez de cortarse en la columna 24 (ticket de ciclo) o 48 (ticket de arranque).

El firmware sigue aparte, con su `FW_VERSION`, sin cambios.

### Script de entrega `tools/entrega/compilar_entrega.py` (§2)
- **§2.1 Verificaciones previas.** Salida 2 y nada tocado si falla alguna. Bloquean:
  - una rama distinta de `dev`;
  - archivos versionados modificados o en el índice;
  - archivos sin versionar en `src/`, `packaging/`, `tools/instalador/` o `Hardware/`;
  - que no estén el python de compilación o `ISCC.exe`;
  - la suite en rojo.

  Solo avisan:
  - los archivos sin versionar en otras carpetas;
  - que `dev` local no coincida con `origin/dev`.
- **§2.2 Secuencia:**
  1. Calcula N y escribe `_version.py`.
  2. Hace el commit `chore(ver): 1.0.0-alpha.N`, junto con la entrada de `HISTORIAL_VERSIONES.md`.
  3. Compila los 3 `.spec`, más `GeneradorCodigos.spec` con `--con-generador`. Usa `AUTOCLAVE_ETIQUETA_ENTREGA` para que `_build_info.py` sea de entrega y comprueba después que lo sea y que esté limpio.
  4. Corre `verificar_entrega_neutra.py`.
  5. Ejecuta `Autoclave.exe --escribir-version <json>`. Ver «Método del paso 5».
  6. Corre `ISCC /DAppVer=1.0.0-alpha.N /DAppVerNum=1.0.0.<1000+N>`.
  7. Arma la carpeta `entrega/v1.0.0-alpha.N_<AAAA-MM-DD>/` con:
     - `Autoclave/` y el zip, verificado con `testzip`;
     - el Setup;
     - el LEEME;
     - `SHA256SUMS.txt` y el manifiesto;
     - `entorno_build.txt`, con el `pip freeze` del python de compilación;
     - `iscc.log`;
     - `usb/`, con el Setup, su suma, el LEEME y `drivers/`.
  8. Crea la etiqueta **anotada**. El mensaje lleva versión, fecha, commit, `AppVerNum`, los SHA-256 y los commits desde la entrega anterior.
  9. Si falla un paso de 3 a 8: `git reset --keep` al commit base y se restaura `_build_info.py` como estaba. La carpeta incompleta se renombra a `…fallida-HHMMSS`, sin borrarla. No queda etiqueta y N no se consume. Sale con 1 e indica el paso.
  10. Imprime `git push origin dev v1.0.0-alpha.N` sin ejecutarlo.
- **Método del paso 5:** se agregó a `exe_unico.py` la opción `--escribir-version RUTA`.
  - Escribe un JSON con la versión mostrada, la completa, los datos de `_build_info` y si está congelado.
  - Sale con 0 antes de abrir el puerto serial, el backend, una ventana o la oferta de instalación.
  - El script exige que la mostrada sea `1.0.0-alpha.N`, `congelado = true`, la etiqueta correcta y el commit del paso 2.
- **§2.3 `AppVerNum`:** `etapa × 1000 + N` (alpha 1, beta 2, rc 3, final 9000).
  - Rechaza N > 999.
  - alpha.1 = `1.0.0.1001`, mayor que el `1.0.0.9` de la I, así que el Setup actualiza.
  - `AppId` sin cambios. El `.iss` no se tocó: ya recibía `AppVer`/`AppVerNum` por `/D`.
- **§2.4 Historial:** `docs/versiones/HISTORIAL_VERSIONES.md` tiene el encabezado y la nota de que alpha.1 sucede a la I (`inst-2026-10-24-i`), sin entradas.
  - Las entradas se agregan debajo de una línea marcadora, la más nueva primero.
  - Los commits listados van desde la alpha anterior (para alpha.1, desde `inst-2026-10-24-i`), con `--no-merges`.

## 3. Comprobaciones con compilación real
- **Compilación de verificación** (commit dae4d0f, `_venv_t8_producto`, `Autoclave.spec`): salida 0.
  - `dist/Autoclave/Autoclave.exe --escribir-version` dio `1.0.0-alpha.1.dev+gdae4d0f.sucio`, con `congelado: true`. El JSON está en `suites/version_exe_verificacion.json`.
  - Salió `.sucio` por los 3 archivos sin versionar de `src/` del resumen.
  - El proceso terminó solo, sin ventanas ni puerto serial.
- **Ensayo de punta a punta del script:** ver §5.

## 4. DECISIONES SIN CONFIRMAR y preguntas
- **P1 (urgente) Respaldos de la I:** `validar_para_equipo` exige la misma versión mayor (`version_mayor`: lo anterior al primer punto).
  - Los respaldos hechos con la I llevan `version_sw = "0"` (§1); los de alpha.N, `"1"`.
  - **Un respaldo de la I no se podrá restaurar en la alpha.1** (motivo `version`). No se tocó la regla, porque rechazar es lo seguro.
  - Si se quiere aceptar los respaldos `"0"`/`"0.5.0"` del mismo formato, hay que decidirlo.
- **D1 `alpha.0` como valor inicial** de `_version.py`: «sin entregas». Así, una compilación de verificación antes de la primera entrega se ve `1.0.0-alpha.1.dev+g…` y no dice ser la alpha.1.
- **D2 Formato de la versión completa:**
  - la entrega agrega ` (<commit>)`;
  - la de verificación ya lleva `+g<commit>`;
  - con árbol sucio se agrega `.sucio`;
  - una compilación con la etiqueta pero con árbol sucio se trata como verificación.
- **D3 «Desde fuente»** se decide por `sys.frozen`, no por la existencia de `_build_info.py`. Un `_build_info.py` que quede de una compilación anterior no hace que el código fuente diga ser una compilación.
- **D4 `_build_info.py` lo generan los `.spec`**, no solo el script, para que toda compilación hecha a mano quede identificada.
  - La etiqueta de entrega llega por la variable `AUTOCLAVE_ETIQUETA_ENTREGA`, porque la etiqueta se crea después de compilar.
  - Si alguien la define a mano, una compilación de verificación diría ser entrega. Queda documentado.
- **D5 «Sucio»** = versionados con cambios o sin versionar en las carpetas del producto. Es la misma regla de bloqueo de §2.1.
- **D6 Criterio de suite en verde del script:** `pytest tests -n auto`. Si hay rojas, se repiten en serie (`--lf`) y cuenta como verde solo si en serie pasan todas. Es el criterio de las tandas; las rojas de Qt en paralelo son intermitentes. Se desactiva con `--sin-suite-serie`.
- **D7 `test_config_correo` aislado** (solo la prueba): las 2 «rojas ajenas» de cada tanda dependían de `data/correo_equipo.json` del PC y habrían bloqueado toda entrega en el banco.
- **D8 Python de compilación:**
  - `--python-compilacion`, o `AUTOCLAVE_PYTHON_COMPILACION`, o `..\_venv_t8_producto` si existe;
  - si no hay ninguno, la entrega se bloquea; nunca compila con el python de desarrollo sin pedirlo.
  - ISCC: `--iscc`, o `AUTOCLAVE_ISCC`, o `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`.
- **D9 Contenido de la carpeta de entrega:**
  - se compilan los 3 `.spec`, pero la carpeta lleva solo `Autoclave/`, como la I;
  - `AutoclaveBackend.exe` y `AutoclaveSettings.exe` quedan en `dist/`;
  - el zip se llama `Autoclave_v1.0.0-alpha.N.zip`.
  - **No** hace la prueba de humo con capturas que hacía K13: sigue siendo manual.
- **D10 Reversión:**
  - usa `git reset --keep`, que se niega si hubiera cambios locales, en vez de `--hard`;
  - `dist/` y `build/` quedan con la compilación fallida (no versionados);
  - si falla la creación de la etiqueta (paso 8), también se deshace.
- **D11 Fecha de la carpeta:** fecha local del PC; `FECHA_UTC` en `_build_info`.
- **D12 Versión final sin prerelease:** la verificación posterior se vería `X.Y.(Z+1)-dev`. Está fuera de alcance (solo alpha por ahora).
- **D13 Primera línea del log:** se escribe al configurar cada log del ejecutable único (`_log_a_archivo`) y en `backend/main.py`. El `autoclave.log` de `utils/logging.py` no se tocó.
- **D14 `tools/tandas/lanzar_prompt.ps1`** sigue sin versionar. `CLAUDE.md` ya lo documenta, pero el archivo no se agregó al repositorio: es de Cristian.

## 5. Ensayo de punta a punta
Se hizo en un **clon desechable** fuera del repositorio (`Documents\_ver_ensayo`, ya borrado), en una rama `dev` del clon. Antes se creó en el clon una etiqueta ficticia `v1.0.0-alpha.900`, para que el ensayo produjera `alpha.901` y nunca se confundiera con la alpha.1 real. En el repositorio no se creó ninguna etiqueta. La salida completa está en `suites/ensayo_entrega.txt`.

- Verificaciones previas: sin errores. Hubo un aviso de `dev` ≠ `origin/dev`, esperado en el clon. La suite no se repitió dentro del ensayo: se corrió aparte (§6).
- Pasos 1 a 8 en orden y salida 0:
  - N = 901 y `AppVerNum` 1.0.0.1901;
  - commit `chore(ver): 1.0.0-alpha.901`;
  - 3 `.spec` compilados;
  - entrega neutra;
  - **el `.exe` reportó `1.0.0-alpha.901 (57631aa)`**;
  - Setup `Autoclave_Setup_1.0.0-alpha.901.exe` de 87 MB, con `FileVersion` 1.0.0.1901 y `ProductVersion` 1.0.0-alpha.901;
  - etiqueta anotada con los SHA-256.
- La carpeta tenía:
  - `Autoclave/`, con 2301 archivos, los mismos que la I;
  - el zip, con 2301 entradas;
  - el Setup, el LEEME y `entorno_build.txt`;
  - `SHA256SUMS.txt` y el manifiesto;
  - `iscc.log`;
  - `usb/`, con el Setup, su suma, el LEEME y `drivers/`.

  La entrada de `HISTORIAL_VERSIONES.md` quedó debajo de la marca.
- **Defecto encontrado y corregido (b3be082):** `SHA256SUMS.txt` y el manifiesto salían con CRLF y `sha256sum -c` no los leía (las de la I son LF). Convertidas a LF, las tres sumas, el manifiesto completo y la suma de `usb/` verificaron OK.
- **Reversión real:** se corrió otra entrega en el clon con un python de compilación inexistente. El paso 3 falló, salió con 1 y quedó todo como antes:
  - HEAD volvió a 57631aa;
  - no se creó `v1.0.0-alpha.902`;
  - `_build_info.py` volvió a su contenido previo;
  - el árbol quedó limpio.

## 6. Suite
Todas las corridas con `python -m pytest tests -n auto`; las rojas se repitieron en serie.

| Momento | En paralelo | Rojas en serie | Total |
|---|---|---|---|
| `dev` tras unir `tanda-15` (b7560e6) | 7830 passed, 6 failed | pasan 4; quedan las 2 de `test_config_correo` (datos del PC) | 7834 passed |
| `versionado` final (b3be082 + informe) | 7901 passed, 8 failed | **pasan las 8** (Qt intermitente en paralelo) | **7909 passed, 0 rojas** |

Son 75 pruebas más que la base:
- 73 de `tests/test_ver_version.py` y `tests/test_ver_entrega.py`;
- las 2 de `test_config_correo`, que ahora pasan siempre (D7).

Registros en `suites/suite_final.log` y `suites/suite_final_serie.log` (no versionados, `*.log`).

`versionado` se une a `dev` con `--no-ff` («Merge versionado en dev»). `dev` no se movió desde la base, así que el árbol unido es el mismo que se probó. Sin push.
