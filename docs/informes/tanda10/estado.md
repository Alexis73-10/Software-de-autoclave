# Tanda 10: estado

Rama `tanda-10`, creada desde `dev` (748337a, contiene `tanda-9` cerrada) en A0. Sesión principal arrancada por el lanzador el 23-oct a las 10:49 (hora de Bogotá).

Precondición A0: `tanda9/estado.md` tiene `| Z | Hecha |` y `dev` contiene la tanda 9 cerrada (fb32ad4, registro del push). Cumplida. La rama `tanda-9` tiene además 2 commits posteriores al cierre (Entrega E: 376eeb5 y cafb06e, sin push); se unieron a `tanda-10` (e391ffe) porque la compilación de esta tanda los necesita (DECISIÓN SIN CONFIRMAR A0-1).

**DECISIÓN SIN CONFIRMAR A0-2:** la letra **E** ya está usada (etiqueta `inst-2026-10-23-e`, `entrega/2026-10-23_e/`, Setup 1.0.0-e ya en la USB). Reusarla exigiría mover la etiqueta (`--force`, prohibido) y sobrescribir la entrega. La compilación de esta tanda (D10-5) se llama **F**: `inst-<fecha>-f`, `entrega/<fecha>_f/`, `Autoclave_Setup_1.0.0-f.exe`, y el LEEME describe «Actualizar E → F» (y D → F, por si el equipo aún tiene la D).

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| A0 | Hecha | f73acf6 | Línea base en `_suites_t10/base` (`tanda-10` e391ffe): **6633 passed, 10 skipped, 3 xfailed** (34 min, `suites/base.log`). |
| G10 | Hecha, unida a `tanda-10` (d6bb062). Suite tras unir: pendiente | `tanda-10-g10` (c6c3aed) | 125 passed en el worktree. |
| T10 | Hecha, unida a `tanda-10` (089dc0c). Suite tras unir: pendiente | `tanda-10-t10` (634dea1) | 1558 passed, 5 skipped en el worktree. Solo texto en `protocolo_fallo.py` (revisado: misma condición y prioridad). |
| W10 | Hecha, unida a `tanda-10` (cc11aa4). Suite tras unir: pendiente | `tanda-10-w10` (b4fb30c) | 225 passed en el worktree. |
| U10a | Hecha, unida a `tanda-10` (af5eaf5). Suite tras unir: pendiente | `tanda-10-u10a` (c1fbfbc) | 41 pasan en la prueba nueva; 90 en textos/i18n. Pregunta: «Chbr.»/«Gskt.» en inglés. |
| U10b | En curso (subagente nuevo desde las 11:38 que CONTINÚA el trabajo sin commit del anterior en el mismo worktree `agent-a26b3309f9ff1210b`) | | |
| K10 | Preparada (entorno `_venv_t8_producto` con PyInstaller 6.20.0, ISCC en `AppData/Local/Programs/Inno Setup 6`; requisitos, `.spec` e instalador sin cambios desde la E; ensayo E → tanda-10 `--desde-src` sin errores salvo «faltan respaldos», esperado porque `src/autoclave/config/` no cambió desde la E). Compila al unir U10b con la suite en verde | | |
| Z | Pendiente | | |

Instrucciones comunes de los subagentes: `tanda10/brief_subagentes.md`. Si la sesión se corta: los subagentes trabajan en `.claude/worktrees/agent-*` (ver `git worktree list`), cada uno en su rama `tanda-10-<id>`; NO relanzarlos desde cero, revisar su rama y su informe y CONTINUAR.

## Sesión 01 (10:49)
- A0: rama creada, Entrega E unida, línea base lanzada.
- 11:0x: lanzados G10, T10, W10 y U10a (4 subagentes). En cola: U10b (después de U10a). La sesión principal NO termina el turno con subagentes activos.
- G10, W10 y T10 terminadas y unidas a `tanda-10` (d6bb062, cc11aa4, 089dc0c). La suite de integración corre después de la línea base.
- U10a unida (af5eaf5); textos/i18n/G10/T10 en la carpeta principal: 124 passed. U10b lanzado.
- Línea base: 6633 passed, 10 skipped, 3 xfailed. Suite de integración de G10+W10+T10+U10a en `_suites_t10/integ` (af5eaf5), una sola corrida para las cuatro uniones (llegaron juntas; DECISIÓN SIN CONFIRMAR A0-3: si hay rojo se aísla la rama).

## Sesión 01 bis (11:34, relanzada para acelerar, §2 de la instrucción)
- `pytest-xdist` 3.8.0 instalado en el Python del proyecto (no se agrega a `requirements-dev.txt`).
- La suite de integración `_suites_t10/integ` de la sesión anterior siguió corriendo (huérfana) y escribe en `suites/integ_g10_w10_t10_u10a.log`; no se repite (§2.2): la cubre la suite tras unir U10b.
- U10b: el subagente anterior dejó cambios sin commit y capturas en `tmp_u10b/`; se lanzó un subagente que continúa desde ahí.
- K10 preparada (ver fila). Ensayo previo en `C:\Users\tecni\Documents\_t10_k10_tmp`.
- 12:0x: la suite de integración huérfana terminó (af5eaf5, 33 min, `suites/integ_g10_w10_t10_u10a.log`): **1 failed, 6727 passed, 10 skipped, 3 xfailed**. Rojo real de U10a: `test_i18n_linea_base.py::test_qml_i18n_igual_a_referencia_para_toda_clave` no conoce las claves `abrev.*` (3 niveles). Se pidió al subagente de U10b el arreglo en su rama (exentar `abrev.` como `ticket_ciclo.`); se comprueba en la suite tras unir U10b.
