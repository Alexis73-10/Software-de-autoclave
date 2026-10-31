# X9: pendientes de la tanda 8 (D9-13.3 ★ y D9-13.4)

Rama `tanda-9-x9`, creada desde `tanda-9` (98c9897, contiene 1ff5afa). Worktree `.claude/worktrees/agent-a6e7c80cff1fb1f3d`.

Todas las pruebas se corrieron con `PYTHONPATH=<worktree>/src`. Ruta comprobada:
`autoclave.__file__ = C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a6e7c80cff1fb1f3d\src\autoclave\__init__.py`.

No se corrió la suite completa (regla 8 del brief).

## D9-13.3 ★ — Bitácora de PATCH /cycle/parameter (TMG-01, SAF-01, SAF-02 de V8a)

| Punto | Qué se hizo |
|---|---|
| TMG-01 | Bajo `_sm_lock` (dentro del guard) solo se **consulta** si la fase sigue pendiente. Para eso hay métodos nuevos: `ControlLoop.fase_pendiente_en_curso` y `CicloState.fase_pendiente`; `aplicar_si_fase_pendiente` reutiliza este último. La copia del ciclo en curso se toca **después** de registrar la bitácora. Hay dos casos en que no se aplica: la fase inició entre medias, o el ciclo vigente corre con otra copia (`copia_esperada`, porque terminó y arrancó otro). En ambos rige desde el siguiente ciclo y queda una fila nueva `param_ciclo_no_aplicado_en_curso`, que corrige el `aplica: en_curso` de la primera fila. Esa fila tiene texto es/en en la bitácora y un reintento. |
| TMG-01 (revisión, SAF-01 Medio) | El cambio se valida sobre una copia del programa (`propuesta`). El JSON se escribe desde la copia. El programa almacenado recibe los valores **solo** después de registrar la bitácora, bajo `_sm_lock`. Así, un ciclo que arranca mientras se escribe la bitácora copia el valor anterior, que sí está registrado. Como el programa en memoria nunca tiene un valor sin registrar, no hace falta revertir la memoria. Se retiró `_revertir_parametro`. |
| SAF-01 | Método nuevo `DbManager.registrar_auditoria_lote(filas)`: una transacción (`BEGIN IMMEDIATE` … `commit`), todas las filas o ninguna, con rollback ante cualquier error. El cambio y su arrastre (tipo de carga → modo de descompresión) van en un solo lote. Si hay una transacción ajena abierta, el lote no se une a ella. El rollback está protegido para no tapar el error original. **Sin migración de base de datos.** |
| SAF-02 | Doble falla (falla la bitácora y luego falla reescribir el JSON, que se reintenta una vez): se escribe la marca `<programa>.json.sin_bitacora` y queda `logger.critical`. La memoria conserva los valores registrados. Al cargar, `CycleManager._marca_sin_bitacora` deja el programa como **dañado**: no se inicia ni se edita. En la misma sesión, el siguiente guardado correcto quita la marca. Reescribir el JSON tras fallar la bitácora ya no genera un `.bak` con el valor sin registrar. Escribir la propuesta no quita la marca; se quita al quedar registrado. |

Commits: 6926bca, 21f1dee (revisión), 0af6438 (re-revisión).

### Revisores (★)

- **Primera vuelta** (`safety-reviewer` y `timing-auditor` en paralelo, sobre 6926bca): **0 Críticos, 0 Altos.**
  - Medios: safety SAF-01 a SAF-04 y timing TMG-01, TMG-02.
  - Corregidos en 21f1dee:
    - safety SAF-01 (programa almacenado con valor sin registrar mientras se escribe la bitácora);
    - SAF-03 = TMG-01 (aplicar a la copia de otro ciclo);
    - SAF-07 = TMG-04 (transacción ajena);
    - SAF-06 = TMG-03 (reintento de la fila de corrección).
- **Re-revisión** (`safety-reviewer` sobre 21f1dee, también con el criterio de concurrencia): **no quedan Altos ni Críticos abiertos.**
  - Bajos corregidos en 0af6438:
    - `.bak` con la propuesta;
    - marca quitada antes de la bitácora;
    - `_revertir_parametro` sin uso.
  - Bajos no corregidos:
    - SAF-04: con `copia_esperada=None`, `aplicar_a_ciclo_en_curso` sigue aplicando, por compatibilidad con las pruebas de T-17. El único llamador vivo siempre la pasa.
    - SAF-05: el mensaje de rechazo dice «Programa dañado (fuera del catálogo): cambio sin registro…». El bloqueo funciona, pero el rótulo «fuera del catálogo» engaña sobre la causa. No se tocó porque esa cadena está en 3 sitios de `server.py`, que otras ramas también modifican.
- **Medios abiertos** (preexistentes o fuera del alcance, ver PREGUNTAS):
  - SAF-02/TMG-05: un corte de energía entre escribir el JSON y registrar la bitácora deja el archivo con el valor sin registrar y sin marca.
  - SAF-04 (primera vuelta): la marca puede no escribirse si el disco falla, y no hay alarma.
  - SAF-05/TMG-02: tras un reinicio, la aplicación no ofrece forma de quitar la marca.

### Planta simulada, banco y riesgos

- **Planta simulada:** no se repitieron celdas de transición nuevas. D9-13.3 no cambia transiciones del ciclo ni de las puertas: cambia el orden bitácora/aplicación de un parámetro editado. Sí se corrieron las pruebas con la planta simulada que ejercitan `ciclo.py` y las fases tocadas (`test_r8_planta_simulada.py`, `test_s1_ensayo_simulador.py`) dentro de la tanda de regresión (ver Pruebas).
- **Banco:** D-X9-01 (cambio con el ciclo en curso: bitácora antes de aplicar) y D-X9-02 (ticket y motivos en inglés), en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (Bloque E9).
- **Riesgos:** HAZ-X9-01 y HAZ-X9-02 en `docs/riesgos/registro_riesgos.md`.

## D9-13.4 — Ticket, reimpresión y motivos de fallo en el idioma vigente

**Motivos de fallo de las fases** (calentamiento, esterilización, descompresión y secado)

- Módulo nuevo `core/runtime/motivos_fase.py`, con el mismo patrón que `motivos.Motivo` de puertas.
  - `MotivoFase` es un `str` con el texto en español de siempre, más un `codigo` y sus `valores`. El log, `estado.motivo_fallo` y la base reciben el mismo texto que antes. La forma cambia un poco: los valores pasan por el módulo de unidades, por ejemplo «140.0 °C».
  - `CicloState._registrar_fallo_de_fase` pasa el código y los valores a la alarma CIC-0x como `motivo_codigo` y `motivo_v_*`. Con la alarma se guardan en `ciclos.valores_fallo`.
  - `alarmas_i18n` arma `{motivo}` en el idioma vigente y en las unidades vigentes, también en español. Las unidades salen del proveedor del ticket.
  - De ahí lo usan la alarma en pantalla, el Historial, el PDF y el correo.
- Catálogo nuevo `motivos_fase.*` (15 códigos y `etapa.*`), en es y en.

**Ticket**

- Los rótulos pasan de la tabla interna al catálogo `ticket_ciclo.*`. En español el ticket queda igual que antes.
- En inglés:
  - El resultado `FALLO_<FASE>` sale como «FAILED (STERILIZATION)». También se traducen `FALLO_PUERTA_n_*`, `FALLO_IO`, `FALLO_CONEXION`, `FALLO_SUMINISTRO` y `SENSOR_AUSENTE`.
  - El aviso de uniformidad se guarda con clave y parámetros, y la temperatura sale en la unidad del ticket.
  - «SoftW.» y «F0 total» vienen del catálogo.
  - El nombre de un programa de fábrica sin cambiar sale del catálogo (D-14), mediante el resolutor que fija `context.py`.
- La reimpresión (`format_ticket`) usa la presentación vigente, así que también sale en inglés.

Commit: 16e1657. Banco y riesgos: b8a7707.

## Pruebas

Pruebas nuevas:
- `tests/test_x9_d9_13_3_bitacora_param_ciclo.py` (23): lote, TMG-01, SAF-01, SAF-02, revisión y re-revisión.
- `tests/test_x9_d9_13_4_ticket_motivos_idioma.py` (32): catálogo es/en y cp437, cada motivo en inglés sin español, integración CicloState → alarma → Historial, ticket es/en, °F, resultados y nombre.

Pruebas ajustadas:
- `test_v8a_tipo_carga_modos.py`: lote y `copia_esperada`; se retiró la prueba de `_revertir_parametro`.
- `test_t10_endurecimiento.py` y `test_backend_autenticacion.py`: lote, `fase_pendiente_en_curso` y fila de corrección.
- `test_v8b_textos.py`: `ticket_ciclo.*` exento de la regla de abreviaturas (DECISIÓN SIN CONFIRMAR de D9-13.4).
- `test_i18n_linea_base.py`: `motivos_fase.*` y `ticket_ciclo.*` como catálogo nuevo.

Resultados:
- Tras D9-13.3: 113 archivos que importan `db_manager`, `cycle_manager`, `ciclo`, la bitácora o `aplicar_a_ciclo` → **2570 passed, 7 skipped, 0 failed**.
- Tras la revisión y la re-revisión: los 9 archivos del PATCH y la bitácora → **237 passed**. Los dos archivos nuevos → **23 + 32 passed**.
- Tras D9-13.4: 203 archivos que citan ticket, cycle_logger, alarmas_i18n, motivo_fallo, las fases, i18n, CicloState o context (incluidos `test_r8_planta_simulada.py` y `test_s1_ensayo_simulador.py`) → **3694 passed, 7 skipped, 6 failed**. Las 6 eran pruebas que verificaban el comportamiento anterior: abreviaturas en `ticket_ciclo` (4), la línea base de i18n (1) y el aviso de uniformidad, que antes era texto (`test_t3_sensores_ciclo.py`, 1). Se ajustaron y, corridas de nuevo con las dos pruebas nuevas, dieron **158 passed, 0 failed**.

## DECISIONES SIN CONFIRMAR

1. **D9-13.4:** abreviaturas permitidas solo en `ticket_ciclo.*` («Temp. Ester.», «Ciclo No.», «Steril. temp.»). La prueba de D8-5.4 exenta esa sección.
2. **D9-13.4:** en inglés, el resultado sale como «FAILED (STERILIZATION)», con la fase entre paréntesis. En español se mantiene el código tal cual («FALLO_ESTERILIZACION»).
3. **D9-13.4:** los motivos de los ciclos anteriores a esta rama (texto libre en español) se muestran como están. No se migran.
4. **D9-13.4:** el motivo de tiempo límite de F0 en español conserva el prefijo «ESTERILIZACION_TIMEOUT_F0:», como antes (CLAUDE.md). En inglés dice «F0 time limit:».
5. **D9-13.3:** un programa marcado «sin bitácora» se carga como dañado (falla segura). No se intenta adivinar el valor registrado.
6. **D9-13.3:** si la fase inicia entre la bitácora y la aplicación, el ciclo sigue con el valor anterior y queda la fila `param_ciclo_no_aplicado_en_curso`. No se rechaza el cambio.

## PREGUNTAS PARA CRISTIAN

1. **Ancho del ticket:** D9-13.4 habla de 32 columnas, pero el código usa `ANCHO_TICKET = 24`. ¿Cuál es el de la impresora? No se cambió.
2. **Marca `.sin_bitacora` tras un reinicio:** hoy solo la quita un técnico a mano, después de revisar el archivo. ¿Se quiere una acción en la aplicación, registrada en la bitácora, que restaure el programa al perfil por defecto y quite la marca? Puede encajar con Manejo de ciclos, D9-10.
3. **Corte de energía entre escribir el JSON y la bitácora (SAF-02/TMG-05, Medio):** ¿se agrega una marca de intención antes de escribir y una comparación con `audit_log` al cargar? Es preexistente.
4. **Doble falla:** ¿debe además activar una alarma para el técnico, aunque el disco falle (SAF-04, Medio)? Requiere un código de alarma nuevo; no se creó.

## Puntos de choque para la unión

- `src/autoclave/backend/server.py`: `_update_cycle_parameter`, `_reescribir_json_programa`, `_marcar_sin_bitacora`, `_quitar_marca_sin_bitacora`, `_save_cycle_json`, `_escribir_json_programa(con_respaldo)`. Se retiró `_revertir_parametro`.
- `src/autoclave/services/domain/logging/db_manager.py`: `registrar_auditoria_lote` y `_fila_auditoria`. **Sin migración.**
- `src/autoclave/services/domain/loop/control_loop.py`: `fase_pendiente_en_curso`, y `aplicar_a_ciclo_en_curso(copia_esperada=)`.
- `src/autoclave/state_machine/states/ciclo.py`: `fase_pendiente`, y los valores del motivo de fase en `_registrar_fallo_de_fase`.
- `src/autoclave/backend/context.py`: resolutor del nombre en el ticket.
- i18n `es.json`/`en.json`:
  - `bitacora.ev.param_ciclo_no_aplicado_en_curso`, `bitacora.tipo.param_ciclo_no_aplicado_en_curso`;
  - secciones nuevas `motivos_fase` y `ticket_ciclo`, insertadas después de `estado_seguro_motivos`.
- `core/runtime/bitacora.py` (EVENTOS).
- `core/runtime/alarmas_i18n.py`.
- Fases: `calentamiento.py`, `esterilizacion.py`, `descompresion.py` y `secado.py` (solo los textos de los motivos).
- `cycle_manager.py`, `ticket_formatter.py` y `cycle_logger.py`.
- No se tocaron: `set_io.py`, el catálogo de alarmas ni QML. **No hay códigos de alarma nuevos.**

## Pendientes

- Suite completa (la corre la sesión principal).
- Preguntas 1 a 4.
- Capturas del ticket en inglés: D9-13.5, de prioridad baja.
