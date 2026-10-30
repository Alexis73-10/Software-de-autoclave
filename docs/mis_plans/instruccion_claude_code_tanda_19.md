# Instrucción maestra para Claude Code — Tanda 19: enlace Modbus TCP con los módulos M31-U (sin supervisión)

> Se lanza con `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_tanda.ps1 -Tanda 19` (`claude -p`; se relanza si se corta). Siempre REANUDA desde `docs/informes/tanda19/estado.md`.

## Alcance y fuentes
- Fuentes de verdad, que se leen COMPLETAS:
  - `docs/mis_plans/decisiones_tanda_19.md`;
  - `docs/mis_plans/planeacion_enlace_modbus.md` (MOD-01 a MOD-17).
- Referencia del hardware: `docs/referencia/m31/`. Lee los `.txt`; los `.pdf` solo si una tabla del texto se lee mal.
- Prioridad: velocidad, sin sacrificar seguridad (código Clase C). No hay hardware Modbus en esta máquina: todo se prueba con el simulador M31 (MOD-14).

## Modo de ejecución
- La sesión principal hace A0, F, I, K, L y Z.
- **Hasta 4 subagentes a la vez**, en V (solo lectura), P (worktree y rama propia) y R (solo lectura).
- Los subagentes no corren la suite completa: solo sus pruebas y las de los módulos que tocan.
- La sesión principal corre la suite completa con `pytest tests -n auto`. Lo que falle solo en paralelo se repite en serie y cuenta como verde si pasa en serie (anotado).

## 0. Reglas
1. Rama `tanda-19` desde `dev`.
   - Estado en `docs/informes/tanda19/estado.md` (tabla `| Etapa | Estado | Nota |`), al día después de cada commit, con el último commit.
   - Informe único: `docs/informes/tanda19/R19_informe.md`.
   - Índice: `docs/informes/informe_tanda_<fecha>_t19.md`.
2. Git:
   - Nunca `main`, `--force`, `git add -A`, `git push --delete`, `git branch -D` ni reescritura del historial. No toques los stash.
   - No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, `_suites_t11/`.
   - Prefijos: `feat(t19)`, `fix(t19)`, `test(t19)`, `docs(t19)`.
3. Pruebas:
   - Prohibido borrar, saltar (`skip`/`xfail`) o relajar una prueba existente.
   - Única excepción: actualizar la aserción de una prueba que fija un comportamiento que esta tanda cambia por decisión de Cristian (buzzer en DO 25; `_CANALES_APAGADO_BASE`; puertos según el enlace; `build_serial` → `build_enlace`). La decisión se cita en un comentario.
   - Cada prueba tocada va al informe.
   - Las pruebas del enlace serial existentes deben pasar sin cambios.
4. Prohibido:
   - hardware, puertos COM o red real: el simulador escucha solo en `127.0.0.1` y en un puerto libre;
   - firmware;
   - ejecutar `.ps1`, el Setup o la herramienta de táctiles;
   - escribir en el registro de Windows;
   - cambiar la configuración de red de esta máquina;
   - instalar software del sistema;
   - borrar archivos sin seguimiento de git;
   - leer o imprimir el archivo de secretos de activación.

   Autorizado:
   - `pip install` de `pymodbus` en el entorno virtual del proyecto (MOD-13);
   - `tools/entrega/compilar_entrega.py` en K.
5. Todo temporizador nuevo usa `time.monotonic()`. Presión siempre en kPa absolutos.
6. Textos visibles en español e inglés, con el mecanismo i18n existente.
7. Ante ambigüedad: lo más seguro y reversible, anotado como «DECISIÓN SIN CONFIRMAR». Todo en español.

## 1. Etapas

### A0. Precondición (sesión principal)
1. Base de la rama: si `git merge-base --is-ancestor tanda-18 dev` se cumple, `tanda-19` sale de `dev`. Si no (la tanda 18 aún no se unió), `tanda-19` sale de `tanda-18`, y en `estado.md` queda «base tanda-18». En ese caso, en K se une `tanda-19` a `dev` (que trae la tanda 18 completa) y la suite completa en verde sobre el resultado es obligatoria. Si en la tanda 18 había algo que la suite no pasa, K se bloquea y se anota.
2. Si `git status --porcelain --untracked-files=no` no está vacío:
   - si `git diff --ignore-cr-at-eol --quiet` confirma que solo hay diferencias de fin de línea, restaura esos archivos con `git checkout -- <archivo>` y lo anota;
   - si hay cambios reales: `| A0 | Esperando | cambios sin commit: <lista> |`, `CERRADO.txt` con `BLOQUEADO:` y TERMINA.
3. Rama `tanda-19`.
4. Commit `docs(t19)` con:
   - `decisiones_tanda_19.md`, `planeacion_enlace_modbus.md`, esta instrucción y el prompt;
   - `docs/referencia/m31/`.
5. Línea base (recolectadas y resultado) en `docs/informes/tanda19/base_suite.txt`.

### V. Verificaciones (hasta 4 subagentes de solo lectura, sin commits; archivo:línea en el informe)
- **V-01 · Interfaz del enlace:** todos los usos de `SerialLink`, `context.serial`, `build_serial` y `build_hardware`, y de cada método o atributo del enlace fuera de `protocols/serial_link.py`. Incluye `src/`, `tools/`, el simulador y las pruebas. Resultado: la lista exacta para el `Protocol` `EnlaceES` (MOD-02).
- **V-02 · Medidas y calibración:** cómo se tratan hoy los valores crudos en `converters.py` y `units.py` (filtros, NAMUR, `senal_presion_presente`, `presion_en_falla`), `calibration_path`, el escritor de calibración y el esquema. Qué hay que cambiar para aceptar `None` por canal (MOD-03) y para tener una calibración por enlace (MOD-04).
- **V-03 · Asignación de E/S:** todos los usos de `PUERTOS_*` y `_OFFSET_PRES`; qué pasa hoy con una asignación guardada inválida al arrancar; `map_do`/`buzer_alarma` (código, YAML, pruebas, UI de Entradas/Salidas); `_CANALES_APAGADO_BASE`.
- **V-04 · Alarmas y estado:** dónde se traducen los `EventoTarjeta` y los `TARJETA_*` a alarmas (`ControlLoop`, `abortar_por_falla_io`, catálogo, i18n); qué consume `get_diagnostico()` en `/status` y en la UI; dónde agregar `enlace_io` en `/status` y en Información del equipo. Además, en el manual del principal: si el filtro de AI (0x0DA2) es un registro o uno por canal, y cualquier diferencia entre los dos manuales en las direcciones de MOD-07.

Con V, la sesión principal escribe en `estado.md` la **tabla de propiedad de archivos** de P: un dueño por archivo. Lo compartido lo hace la sesión principal en F o I.

### F. Fundaciones (sesión principal, un commit por punto)
- **F1 · Dependencia:** `pymodbus` fijado en `pyproject.toml` y `requirements.lock.txt`, con la línea de `docs/riesgos/lista_soup.md` (MOD-13). Comprobar que importa en Python 3.14.
- **F2 · Interfaz y selección:**
  - `protocols/enlace.py` con `EnlaceES` (`Protocol`) y `EventoTarjeta`, que se traslada o reexporta desde `serial_link` sin romper los imports actuales;
  - `config/enlace_io.json` y su lector;
  - `build_enlace` en `devices/factory`, usado por `context` y `build_hardware`;
  - `enlace_io` en `/status` (MOD-01, MOD-02).
  - Mientras `ModbusLink` no exista, `build_enlace` con `"modbus"` levanta un error claro. P-s1 lo completa.
- **F3 · Textos:** claves i18n (es/en) de las alarmas nuevas y del enlace en Información del equipo. Filas del catálogo de alarmas (MOD-12).

### P. Implementación en paralelo (3 subagentes, `isolation: worktree`)
Cada subagente:
- trabaja en la rama `tanda-19-<s>`, creada desde `tanda-19` después de F;
- toca solo sus archivos de la tabla;
- pone sus pruebas en `tests/test_t19_<s>*.py`, con el marcador `req`;
- hace commit en su rama;
- responde en español con: archivos tocados, pruebas nuevas y tocadas, DECISIONES SIN CONFIRMAR y pruebas de banco pendientes.

**s1 · ModbusLink y simulador** (`protocols/modbus_link.py`, `protocols/modbus_link_config.py`, `config/modbus_link.json`, `tests/helpers/m31_simulado.py`):
- MOD-02, MOD-03 (lado del enlace), MOD-06 a MOD-11 y el simulador de MOD-14.
- Pruebas de MOD-14 del enlace. Entre ellas, obligatoria: sin tick del lazo y con una salida en ON no sale ninguna petición, y el simulador apaga las salidas al vencer su tiempo.

**s2 · Medidas, calibración y asignación** (`hal/measures/converters.py`, `units.py`, `config/schema.py`, `config/calibration_modbus.yaml`, `utils/paths.py`, escritor de calibración, `core/runtime/asignacion_io.py`, `server_reasignacion.py` en lo de los puertos, `core/runtime/status.py` en `map_do`, `config/instances/ACV-2026-001.yaml`, `devices/io/set_io.py`):
- MOD-03 (`None` por canal), MOD-04 y MOD-05.
- Pruebas: `None` en un canal no afecta a los demás y reinicia su filtro; fábrica Modbus (décimas → °C; 4000/20000 µA → 0/400 kPa); falla de lazo con 0 µA; piso de señal de 3850; puertos según el enlace; buzzer en DO 25; apagado individual 1–32. Las del serial, sin cambios.

**s3 · Alarmas, estado e interfaz** (lo que V-04 identifique: traducción de eventos a alarmas, `/status`, Información del equipo):
- MOD-10 (exposición), MOD-12 y `enlace_io` en la UI.
- Pruebas de que `TARJETA_CONFIG_SEGURIDAD` y `TARJETA_MODULOS_ORDEN` bloquean el arranque y, en ciclo, llevan a COM-03 igual que `TARJETA_ALL_OFF_SIN_CONFIRMAR`.

### I. Integración (sesión principal)
1. Une las ramas en `tanda-19` con `--no-ff`, en el orden s2, s1, s3. Los conflictos se resuelven conservando las dos intenciones y se anotan.
2. Prueba de integración: backend completo con `enlace: modbus` contra el simulador M31 (arranque, conexión verificada, lectura de temperatura y presión, una orden de salida, pérdida y reconexión).
3. `tools/claves_sin_uso_i18n.py` sin claves huérfanas nuevas.
4. Comprobar que `packaging/Autoclave.spec` incluye pymodbus. Si `compilar_entrega.py` compila, se verifica ahí; si no, `pyinstaller --noconfirm packaging\Autoclave.spec` y prueba de importación en el `.exe` con un rol que no abra hardware, si existe. Si no existe, se anota.
5. Hoja de banco: bloque M (MOD-15) y paso previo de red (MOD-17) en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (y su `.html` si se genera desde el `.md`).
6. Riesgos: MED-01 a MED-03 en `docs/riesgos/registro_riesgos.md` (MOD-16).
7. Suite completa en verde. Recolectadas = base + nuevas.

### R. Revisión (3 subagentes de solo lectura)
Cada uno revisa `git diff dev...tanda-19 -- <rutas del área>`.

Prompt común: «Es código de seguridad Clase C de un autoclave. Busca:
- tráfico Modbus que mantenga vivo el módulo con el lazo de control congelado y una salida encendida;
- configuración de seguridad que se dé por buena sin leerla de vuelta;
- conexión verificada con modelos, firmware u orden distintos de los esperados;
- salidas que puedan quedar encendidas tras una pérdida de comunicación;
- acceso al cliente pymodbus desde dos hilos sin lock;
- un código de diagnóstico de PT100 o un 0 de AI publicado como lectura real;
- un `None` que rompa los filtros o se convierta en 0;
- puertos fuera de rango aceptados;
- el enlace serial cambiado en su comportamiento;
- reloj de pared en temporizadores;
- pruebas que pasan sin probar lo que dicen.

No ejecutes la suite completa. Responde en español con hallazgos `V19-<s>-xx` (archivo:línea, severidad alta/media/baja, motivo) o "sin hallazgos".»

Corrige los hallazgos válidos (commit) y repite la suite. Un hallazgo alto sin corregir bloquea K.

### K. Unión y entrega (suite en verde, sin hallazgos altos)
1. Ejecuta `git checkout dev` y `git merge --no-ff tanda-19 -m "Merge tanda-19 en dev"`, y luego la suite completa.
2. Commit `docs(t19)` en `dev`: crea o actualiza el archivo de anomalías conocidas de la versión que se entrega, copiando el de la anterior.
   - Agrega MED-01 a MED-03 y las DECISIONES SIN CONFIRMAR.
   - Agrega la lista de pruebas de banco del bloque M.
   - Agrega la nota «el enlace por defecto es Modbus; la tarjeta ESP32 requiere `enlace: serial`».
   - Uso previsto: sin uso clínico.
3. `python tools/entrega/compilar_entrega.py --con-generador`.

Si falla la unión o la suite: `git merge --abort` o revert del merge, estado `Bloqueada` con el motivo, y pasa a L.

Si falla la entrega: el script deshace su commit. Anota el paso y pasa a L.

No hagas push de `dev` ni de etiquetas: el comando de push que imprime el script va al informe.

### L. Limpieza (sin agentes activos)
- Quita los worktrees de `.claude/worktrees/` sin cambios sin commit y ejecuta `git worktree prune`.

### Z. Cierre
- `CLAUDE.md`: sección corta «Enlace de E/S (tanda 19)» con MOD-01 a MOD-12 resumidos, en el estilo de las demás.
- Informe R19 completo.
- Índice con la primera línea: unida o no a `dev` y versión entregada.
- Fila `| Z | Hecha | ... |` y `CERRADO.txt` (fecha, commit del merge, resultado de la suite).
