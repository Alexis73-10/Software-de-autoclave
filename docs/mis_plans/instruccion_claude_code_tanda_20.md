# Instrucción maestra para Claude Code — Tanda 20: cierre de la migración a Modbus y Setup con Modbus (sin supervisión)

> Se lanza con `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_tanda.ps1 -Tanda 20` (`claude -p`; se relanza si se corta). Siempre REANUDA desde `docs/informes/tanda20/estado.md`.

## Alcance y fuentes
- Fuentes de verdad, que se leen COMPLETAS: `docs/mis_plans/decisiones_tanda_20.md` (T20-01 a T20-06), `docs/mis_plans/adenda_tanda_19_banco.md`, `docs/informes/banco_m31_2026-10-27.md` y `docs/mis_plans/planeacion_enlace_modbus.md`. Si chocan, prevalecen las decisiones, después la adenda.
- Referencia del hardware: `docs/referencia/m31/` (los `.txt`; los `.pdf` solo si una tabla se lee mal). Registros de usuario/contraseña web: 0x758B (5) y 0x7590 (3) del manual del principal.
- Prioridad: que la entrega instale y conecte con los módulos reales. Código Clase C: velocidad sin sacrificar seguridad. No hay módulos en esta máquina: todo con el simulador M31 en 127.0.0.1.

## Modo de ejecución
- La sesión principal hace A0, B, F, I, K, L y Z.
- **Hasta 4 subagentes a la vez**, en V (solo lectura), P (worktree y rama propia) y R (solo lectura). Revisores solo en R.
- Los subagentes no corren la suite completa. La principal corre `pytest tests -n auto`; lo que falle solo en paralelo se repite en serie y cuenta como verde si pasa (anotado).

## 0. Reglas
1. Rama `tanda-20` desde `dev`. Estado en `docs/informes/tanda20/estado.md` (`| Etapa | Estado | Nota |`, con el último commit) al día después de cada commit. Informe único `docs/informes/tanda20/R20_informe.md`. Índice `docs/informes/informe_tanda_<fecha>_t20.md`.
2. Git: nunca `main`, `--force`, `git add -A`, `git push`, `git push --delete`, `git branch -D` ni reescritura del historial; no toques los stash. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, `_suites_t11/`. Prefijos `feat(t20)`, `fix(t20)`, `test(t20)`, `docs(t20)`, `chore(t20)`. El retiro del serial va en commits propios `chore(t20): retiro ...`.
3. Pruebas: prohibido saltar (`skip`/`xfail`) o relajar una prueba. Borrar solo las pruebas autorizadas por T20-03 (único objeto: enlace serial, firmware o ADC del serial), cada una en el informe con archivo y motivo. Las demás se migran al doble Modbus con su aserción intacta; si una aserción cambia por una decisión de Cristian, se cita en un comentario y va al informe.
4. Prohibido: módulos reales, puertos COM o red real (simulador solo en 127.0.0.1 y puerto libre); firmware; ejecutar `.ps1`, el Setup o la herramienta de táctiles; escribir en el registro de Windows; cambiar la red de esta máquina; instalar software del sistema; borrar archivos sin seguimiento de git; leer o imprimir el archivo de secretos; escribir contraseñas reales en el repositorio, logs o pruebas (las pruebas usan valores ficticios).
   Autorizado: escribir en `G:\Respaldos_autoclave\` (solo B); `pip` en el entorno del proyecto si hace falta quitar `pyserial`; `tools/entrega/compilar_entrega.py` en K; ejecutar el `.exe` compilado con `--rol configurar-modulo --ip 127.0.0.1` contra el simulador en K.
5. Temporizadores nuevos con `time.monotonic()`. Presión en kPa absolutos.
6. Textos visibles en español e inglés con el i18n existente (también los del Setup, `es.`/`en.`).
7. Ante ambigüedad: lo más seguro y reversible, «DECISIÓN SIN CONFIRMAR». Todo en español.
8. Los `.ps1` nuevos y el `.iss` se validan sin ejecutarlos contra el sistema: análisis estático (PSScriptAnalyzer si está, si no `[System.Management.Automation.Language.Parser]::ParseFile` en un proceso `pwsh -NoProfile` que solo parsea) y compilación del `.iss` con ISCC si `compilar_entrega.py` lo hace. Funciones puras de los `.ps1` (validación de IP/subred, elección de adaptador, armado del respaldo) se separan para poder probarlas con datos ficticios.

## 1. Etapas

### A0. Precondición
1. Si `git status --porcelain --untracked-files=no` no está vacío: si solo son fines de línea (`git diff --ignore-cr-at-eol --quiet`), restaurarlos y anotar; si hay cambios reales, `| A0 | Esperando | <lista> |`, `CERRADO.txt` con `BLOQUEADO:` y TERMINA.
2. Rama `tanda-20` desde `dev`.
3. Commit `docs(t20)`: `decisiones_tanda_20.md`, esta instrucción, el prompt, `adenda_tanda_19_banco.md`, `docs/informes/banco_m31_2026-10-27.md`.
4. Línea base de la suite en `docs/informes/tanda20/base_suite.txt`.

### B. Copia de seguridad en G: (T20-01; nada se borra antes de que B esté Hecha)
1. Comprobar `G:\` (existe, se puede escribir, espacio > 3 × tamaño de `.git`). Si no: `BLOQUEADO: disco G no disponible para la copia previa al retiro del serial`, `CERRADO.txt` y TERMINA.
2. Crear la carpeta, el bundle `--all`, `git bundle verify`, el `git archive` de `dev` y `LEEME.txt`. Calcular SHA-256 de los dos archivos y anotarlos en `LEEME.txt` y en el informe.
3. Etiqueta local anotada `respaldo-serial-pre-t20` (sin push).
4. `| B | Hecha | ruta, SHA-256, commit |`.

### V. Verificaciones (hasta 4 subagentes de solo lectura; archivo:línea)
- **V-01 · Inventario del serial:** todo lo que importa o usa `serial_link`, `serial_link_config`, `build_serial`, `enlace_io`, `ADC_MAXIMO`, `calibration.yaml` serial, puertos del serial, handshake, `pyserial`, `Hardware/`. Clasificar cada uso: borrar, migrar a Modbus o conservar (API/historial).
- **V-02 · Pruebas:** qué pruebas dependen del doble serial o de `conftest` con enlace serial. Clasificar: borrar (T20-03), migrar a doble Modbus, sin cambio. Proponer el doble Modbus común (simulador o doble en memoria de `EnlaceES`) y su fixture por defecto.
- **V-03 · Adenda:** dónde están en `modbus_link.py` la composición, la comparación de firmware, la bandera 0x0C37 y la escritura de la configuración de seguridad; qué cambia para ADB-01..05; qué le falta al simulador (reinicio, contador 0x0C37, usuario/contraseña web); dónde se empareja `board_id` (ADB-03).
- **V-04 · Setup y estación:** cómo el `.iss` invoca `--rol asociar-tactiles` y gestiona `Paso06`/`Paso07` (páginas, respaldo, Reparar, desinstalación, silencioso); dónde ubicar las páginas de red, contraseña y resultado; cómo evitar que la contraseña llegue al log de Inno; qué instala hoy `enlace_io.json`.

Con V, la principal escribe en `estado.md` la tabla de propiedad de archivos de P (un dueño por archivo).

### F. Fundaciones (principal)
- F1: doble Modbus común y fixture por defecto en `tests/conftest.py` (sin borrar aún el serial), con pruebas que lo validen.
- F2: claves i18n (es/en) nuevas (resultado de configurar el módulo, textos del Setup en el `.iss`).

### P. Implementación en paralelo (3 subagentes, `isolation: worktree`, ramas `tanda-20-<s>` desde `tanda-20` tras F)
Cada uno toca solo sus archivos, pone sus pruebas en `tests/test_t20_<s>*.py` con `req`, hace commit y responde en español con archivos, pruebas nuevas/tocadas/borradas, DECISIONES SIN CONFIRMAR y pruebas de banco pendientes.

**s1 · Adenda y rol** (`protocols/modbus_link.py`, `modbus_link_config.py`, `config/modbus_link.json`, `tests/helpers/m31_simulado.py`, `exe_unico.py` en lo del rol, módulo nuevo del rol): T20-02 y T20-04, con sus pruebas obligatorias.

**s2 · Retiro del serial** (lo que V-01/V-02 asignen): T20-03 completo, incluida la migración de pruebas y la documentación del código (`CLAUDE.md` se toca en Z).

**s3 · Setup y estación** (`tools/instalador/autoclave.iss`, `tools/instalador/estacion_setup.ps1`, `tools/estacion/08_*.ps1`, `_comun.ps1`, `tools/estacion/LEEME.md`, `tools/instalador/LEEME.md`): T20-05. Pruebas: funciones puras de los `.ps1` con Pester si está disponible o con pruebas de Python que inspeccionen el `.iss` (páginas, `Paso08`, desinstalación, que la contraseña no aparezca en `Log(`/parámetros); parseo sin errores de los `.ps1`.

### I. Integración (principal)
1. Une s1, s2, s3 en `tanda-20` con `--no-ff`; conflictos conservando las dos intenciones, anotados.
2. Integración: backend completo contra el simulador con la composición real de 5 esclavos (arranque, ADB-04 con configuración distinta → reinicio → verificada, lecturas, una salida, pérdida y reconexión); el rol `configurar-modulo` contra el simulador (correcto, composición distinta, contraseña escrita y releída, sin bobinas escritas: el contador de escrituras de bobinas del simulador queda en 0).
3. `grep` final: ninguna referencia a `serial_link`, `SerialLink`, `build_serial`, `enlace_io.json`, `pyserial` fuera de historial, informes y `docs/versiones/`.
4. `tools/claves_sin_uso_i18n.py` sin huérfanas nuevas (las del serial que se conservan por historial, anotadas).
5. T20-06 (hoja de banco regenerada, M-5 ampliado, M-7, MED-04, AN-30/31/32).
6. Suite completa en verde. Recolectadas = base + nuevas − borradas (cuadrar en el informe).

### R. Revisión (3 subagentes de solo lectura, `git diff dev...tanda-20 -- <rutas del área>`)
Prompt común: «Código de seguridad Clase C de un autoclave. Busca: conexión verificada con composición, firmware u orden distintos; configuración de seguridad dada por buena sin releerla tras el reinicio; reinicio del módulo con salidas encendidas o en ciclo; 0x0C37 usado todavía como condición; el rol `configurar-modulo` escribiendo bobinas o configuración de seguridad, o actuando con un backend en marcha, o aceptando una IP distinta de 127.0.0.1 en `--ip`; la contraseña en logs, línea de comandos, resultado o repositorio; el paso 08 aplicando IP sin respaldo, sin reversión, en un adaptador Wi-Fi o virtual, o rompiendo la única red con salida sin advertencia; restos del serial alcanzables en tiempo de ejecución; pruebas borradas fuera de T20-03 o migradas con aserción relajada; reloj de pared en temporizadores. No ejecutes la suite completa. Responde en español con hallazgos `V20-<s>-xx` (archivo:línea, alta/media/baja, motivo) o "sin hallazgos".»
Corrige los válidos (commit) y repite la suite. Un hallazgo alto sin corregir bloquea K.

### K. Unión y entrega (suite en verde, sin altos)
1. `git checkout dev`, `git merge --no-ff tanda-20 -m "Merge tanda-20 en dev"`, suite completa.
2. Commit `docs(t20)` en `dev`: anomalías conocidas de la versión que se entrega (copia de la anterior): retirar AN-30/31/32 cerradas, agregar MED-04, DECISIONES SIN CONFIRMAR de esta tanda, bloque M con M-5 ampliado y M-7, «solo Modbus TCP; la tarjeta ESP32 ya no es compatible», uso previsto sin uso clínico.
3. `python tools/entrega/compilar_entrega.py --con-generador`.
4. Con la entrega hecha: arrancar el simulador M31 en 127.0.0.1 y ejecutar el `Autoclave.exe` compilado con `--rol configurar-modulo --ip 127.0.0.1 --puerto <libre> --resultado <tmp>`; debe dar `ok` (prueba de que pymodbus va dentro del `.exe`). Resultado al informe.
Si falla la unión o la suite: `git merge --abort` o revert, estado `Bloqueada` con el motivo, y pasa a L. Si falla la entrega, el script deshace su commit; anota y pasa a L. No hagas push: el comando que imprime el script va al informe.

### L. Limpieza
Quita los worktrees de `.claude/worktrees/` de esta tanda sin cambios sin commit y `git worktree prune`.

### Z. Cierre
- `CLAUDE.md`: la sección «Enlace de E/S» pasa a «Enlace de E/S Modbus (tandas 19–20)», sin la selección ni el serial; agrega el rol `configurar-modulo`, el paso 08 y ADB-01..05 resumidos. Quita del resto del archivo lo que describa el serial como vigente.
- Informe R20 completo (con la ruta y SHA-256 de la copia en G:).
- Índice con la primera línea: unida o no a `dev` y versión entregada.
- Fila `| Z | Hecha | ... |` y `CERRADO.txt` (fecha, commit del merge, suite, ruta de la copia en G:).
