# Prompt para Claude Code — tanda 23: «módulo E/S» y numeración RTD / AI (sin supervisión)

Lo envía `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_prompt.ps1 -Nombre tanda23` y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español (código, comentarios, commits, informe). Código Clase C (NTC-IEC 62304): velocidad sin sacrificar seguridad.

## Reglas

1. Si existe `docs/informes/tanda23/estado.md` con pasos hechos, REANUDA desde el primero pendiente. Si no existe, créalo y empieza por A0.
2. La spec es `docs/mis_plans/decisiones_tanda_23.md` (MES-01..04, AIN-01..05, AIN-R1..R3). Léela completa antes de empezar. Ante ambigüedad, lo más seguro y reversible, marcado «DECISIÓN SIN CONFIRMAR» en el informe.
3. Rama `tanda-23` creada desde `dev`. Nunca `main`, `--force`, `git add -A`, `git push` ni `git branch -D`. No escribas en módulos reales, red, registro de Windows ni ejecutes `.ps1` o el Setup (sí puedes editar sus textos). No leas el archivo de secretos.
4. **Subagentes: 4 a la vez como máximo.** Ningún subagente corre la suite completa (solo sus pruebas); la sesión principal corre `pytest tests -n auto`.
5. Después de cada commit, actualiza `estado.md` (paso → Hecho/Pendiente, último commit).

## Etapas

**A0 (principal).**
1. Comprueba que la tanda 22 cerró: existe `docs/informes/tanda22/CERRADO.txt`, su primera línea no empieza por `BLOQUEADO:` y `dev` contiene el merge de `tanda-22`. Si no, escribe `docs/informes/tanda23/CERRADO.txt` con `BLOQUEADO: la tanda 22 no ha cerrado` y termina.
2. Crea `tanda-23` desde `dev`; commit de este prompt y de `decisiones_tanda_23.md` (rutas explícitas).
3. Inventario en `docs/informes/tanda23/inventario.md` (grep, sin cambiar nada): (a) nombres persistidos con «tarjeta» (MES-03.2) con archivo y tipo de almacén; (b) usos de «tarjeta» como recuadro de interfaz (MES-03.3); (c) lugares donde se muestra un código de alarma (MES-04); (d) cada uso de un número de puerto con tipo `"AI"` que suponga rangos sin solape (AIN-R1); (e) consumidores que suponen `ai` de 16 posiciones (AIN-03). Esta lista guía a los subagentes y a la prueba de regla.

**B AIN (1 subagente, worktree `tanda-23-ain`; en paralelo con C1, que no toca estos archivos).** AIN-01..05 completos:
- `protocols/modbus_link.py` (fc04 0x0000 ×16, `ai` de 24), `core/runtime/asignacion_io.py` (grupos, `FORMATO` 2, migración idempotente con `.bak` y fila de bitácora), `core/runtime/io_names.py` (ids «RTD 0n» / «AI nn»), `hal/measures`, calibración (AIN-04), restauración de respaldos, `config/instances/*.yaml`, controlador y pantalla de Reasignación, Entradas/Salidas, Calibración de sensor, simuladores y dobles.
- Cada punto del inventario (d) pasa a trabajar por grupo (AIN-R1).
- Pruebas nuevas (`tests/test_t23_ain_*.py`): lectura de 16 AI contra `m31_simulado`; migración FORMATO 1 → 2 (valores, `.bak`, bitácora, idempotencia, respaldo); **equivalencia AIN-R2** (para asignaciones FORMATO 1 de fábrica y de ejemplo, el canal crudo de cada función no cambia); RTD 01 y AI 01 asignados a la vez sin conflicto y sin cruce de lecturas; AI 16 con calibración nominal lee; rangos fuera (RTD 07, AI 17, AI 00) → `puerto_inexistente`; calibración de 8 entradas completada a 16 sin tocar 0–7.

**C renombre «tarjeta» → «módulo E/S» (MES-01..04).**
- C1 (subagente, worktree `tanda-23-ui`, en paralelo con B): QML, `ui_qml` (Python), `ui_pyside`, `i18n/es.json` y `en.json` (valores y claves; actualiza los usos de las claves renombradas), y `tools/claves_sin_uso_i18n.py` verde.
- Une B a `tanda-23`. Luego, en paralelo:
  - C2 (subagente, worktree `tanda-23-nucleo`): `backend`, `cliente`, `core`, `services` (ticket, PDF, correo, historial; MES-04 con `codigo_visible()`), `protocols`, `devices`, `hal`, `state_machine`, `estacion`, `installation`, `utils`, `simulador`, `exe_unico.py`, `instalador_exe.py`. Si cambian campos de `/status` o el OpenAPI, actualiza la base de `tests/test_t15_rutas_equivalentes.py` (`docs/informes/tanda15/base/`) y anótalo; las rutas no cambian.
  - C3 (subagente, worktree `tanda-23-tools`): `tools/` (incluido `git mv tools/emparejar_tarjeta.py tools/emparejar_modulo_es.py` y sus referencias; `instalador/autoclave.iss` y `LEEME.md`, página «Red del módulo E/S»; `registro_pruebas`), `packaging/` y `tests/` (nombres y textos; no cambies lo que una prueba verifica).
  - C4 (subagente, worktree `tanda-23-docs`): documentación vigente: `CLAUDE.md`, `docs/README.md`, catálogo de alarmas, `docs/riesgos/registro_riesgos.md` (agrega AIN-R1..R3), manuales y `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (+ `.html` si se genera de él), `docs/mis_plans/planeacion_enlace_modbus.md`. No toques `docs/informes/` ni decisiones, planes o prompts de tandas cerradas.
- Une C1..C4 a `tanda-23` (resuelve conflictos conservando ambos cambios).

**D prueba de regla (principal).** `tests/test_t23_sin_tarjeta.py`: falla si aparece `/tarjeta|targeta/i` en valores de `i18n/*.json`, literales de `.qml`, plantillas de ticket/PDF/correo, `autoclave.iss`, textos `configurar_modulo.*` o mensajes de log; falla si un valor de `en.json` contiene `\bboard\b`; y falla si aparece en identificadores de `src/` fuera de una lista blanca explícita y comentada (códigos `TARJETA_*`, nombres persistidos del inventario (a), recuadros de interfaz del inventario (b)). Prueba de `codigo_visible()`.

**R revisión (1 subagente, solo lectura) — solo de B y AIN-R1/R2** sobre el diff de `tanda-23` contra `dev`: que ningún sensor cambie de canal físico, que la migración sea idempotente y no pierda funciones, que ninguna comprobación de duplicados o búsqueda por puerto mezcle RTD y AI, que la vigilancia del lazo, `all_off`, la configuración de seguridad y la composición (ADB-01..05, MOD-08) no se hayan tocado más allá de `N_PRES`, y que ningún código `TARJETA_*` ni nombre persistido haya cambiado. Corrige lo que encuentre y anótalo.

**Suite.** `pytest tests -n auto` verde.

**K (sin compilar).** Une `tanda-23` a `dev` (merge sin fast-forward). No compiles la entrega.

**Z cierre.**
1. `docs/informes/tanda23/R23_informe.md`: qué cambió por MES y AIN, archivos y pruebas; lista de lo que NO se renombró (MES-03) con el porqué; decisiones sin confirmar; migración (desde cuándo rige la numeración nueva en la bitácora); verificación en el equipo (sección final de `decisiones_tanda_23.md`); y, explícito, «la entrega no se compiló» con el comando exacto para compilarla desde `dev` (el mismo de la última entrega en `docs/versiones/HISTORIAL_VERSIONES.md`).
2. Agrega la fila `| Z | Hecha | ... |` en `estado.md`.
3. Como último acto, `docs/informes/tanda23/CERRADO.txt` con la fecha, el commit del merge y el resultado de la suite (o `BLOQUEADO:` y el motivo en la primera línea).

Empieza por A0 (o reanuda).
