# Tanda 6: estado

Rama `tanda-6`, creada desde `dev` (7d825b5) tras E0. Línea base de la suite: 4379/1/3. Bloque 2 **ejecutado** (`docs/mockups/tanda6/APROBADO.md` existe). Commits verificados con `git log --oneline tanda-6`.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| E0 | Hecha | ea22565, a7f6db8, 02323a0, merge 7d825b5; docs 74cf391 | `merge-base --is-ancestor tanda-5 dev` = OK. Push `origin dev tanda-4 tanda-5`: DENEGADO por el clasificador de permisos de Claude Code (no llegó a git); lo hace Cristian. `data/unidades.json`=°C/kPa, `data/idioma.json`=es (sin commit). |
| T2 ★ | Hecha | 5de3a1e, a15daa0, 5d7c93b, 5be87a2, 25727f6, 34552db, 5b1afa9, cd7f8d1, 38f37ac (P-7), 76d49b9 (P-6), 563c133 (P-8); docs 7e1f4bd | P-1…P-9 y P-12 aplicados (P-10/P-11 sin cambio). Suite 4451/2/3. Revisores: Altos corregidos, segunda pasada sin Críticos/Altos. Ver `T2_respuestas_T1.md`, `T2_matriz_actualizada.md`, `T2_ensayo_tabla.md`. |
| C1 | Hecha | d8bfde6 (C1c), b816bd1 (C1d), cbbf8d0 (C1a), ce2878c (C1b + informe) | a, b, c y d con pruebas; safety-reviewer en a y c sin Críticos ni Altos. Ver `C1_correcciones_t5.md`. |
| X1 | Hecha (rama tanda-6-x1, unida) | 15ffbbd, merge 8181b66 | Una sola OPCIONES por ventana y una página por segmento en E/S. Ver `X1_solapamiento_es.md`. |
| I4 backend ★ | Hecha (rama tanda-6-i4, unida) | ed4c650, 5ff5139, af24210, merge 33c8baf | Motivos de puerta con código, `valores_fallo` (v7), PDF/tickets es/en, cp437. Revisores sin Críticos/Altos/Medios. Ver `I4_ingles_backend.md`. |
| R1 | Hecha | 81ebd3e, 2c741e3 | 31 hallazgos: 4 corregidos, 2 ya cerrados, 25 abiertos (preguntas R1-P1…P5). Ver `R1_hallazgos_pendientes.md`. |
| W1 | Hecha (scripts sin ejecutar) | 74af54f | 11 `.ps1` + LEEME en `tools/estacion/`; solo análisis sintáctico (0 errores). Ver `W1_estacion_windows.md`. |
| D1 | Hecha | 910e4e3 | Registro de riesgos, matriz de trazabilidad, lista SOUP (24). Campos "por completar". Ver `D1_documentacion_62304.md`. |
| B1 | Hecha (rama tanda-6-b1, unida) | d8a27b4, merge 700e3e9 | Barra flotante en Preciclo y Ciclo en curso (decisión 1.7). Suite 4631/2/3. Ver `B1_barra_flotante.md`. |
| O3 | Hecha (rama tanda-6-o3, unida) | 33fd8de, merge 739e849 | Entradas mostradas en Preciclo, Ciclo y gráfica. Ver `O3_entradas_mostradas.md`. |
| O2a | Hecha | a1cd455, 8926043; docs 9e7f7a0 | `system_params` (v8), API 403/409 con auditoría, 7 submenús QML. Altos corregidos (TMG-01, SAF-01). Ver `O2a_parametros_equipo.md`. |
| O2b | Hecha | 9192b36; docs 39ec70c | Usuarios y operadores (v9), matriz 1.9. Suite 4801/2/3. Ver `O2b_usuarios.md`. |
| O2c | Hecha | 01936bb; docs 9050d08 | Fecha y hora solo lectura, aviso M1-01. Suite 4820/2/3. Ver `O2c_fecha_hora.md`. |
| O2d | Hecha | d4dcbda; docs d3fb631 | `GET /system/info`. Suite 4836/2/3. Ver `O2d_info_sistema.md`. |
| O2e | Hecha | cc49976; docs 477a88d | Bitácora `GET /audit_log` paginada con filtros. Ver `O2e_bitacora.md`. |
| O2f | Hecha (rama tanda-6-o2fgh, unida) | 5ab13ac, merge 4de45d7; docs db1d4b9 | Calibración atmosférica, página de prueba, impresión de ganancias. TMG-04/05 y SAF-01/02 abiertos. Ver `O2f_calibracion_atm.md`. |
| O2g | Hecha (rama tanda-6-o2fgh, unida) | 2a8ab46, merge 4de45d7; docs db1d4b9 | Red solo lectura, destinatarios de correo editables. Ver `O2g_conectividad.md`. |
| O2h | Hecha (rama tanda-6-o2fgh, unida) | e56dabb, merge 4de45d7; docs db1d4b9 | Respaldo/restauración por USB. Altos corregidos. Ver `O2h_respaldo.md`. |
| H1 | Hecha | 980a9f5 | 26 pruebas nuevas (49 → 75), `.md`/`.html` regenerados. Ver `H1_hoja_banco.md`. |
| I4 QML | Hecha | 8b9fa78 | Idioma desde `GET /language` en cada ventana, literales, truncado a 1024 px (44 capturas). Suite 5019/2/3. Ver `I4_ingles_qml.md`. |
| Z | En curso | (commit de cierre pendiente) | Suite final: 5020 passed, 2 skipped, 3 xfailed (19 min, 22-oct). Merge a `dev`: `git merge --no-ff tanda-6` en `dev` (ver commit de merge). `merge-base --is-ancestor tanda-6 dev`: `git merge-base --is-ancestor tanda-6 dev` = OK (exit 0). Push: `git push origin dev tanda-6` OK (dev ea91725..7a872ce, tanda-6 rama nueva). `git push origin tanda-4 tanda-5` DENEGADO por el clasificador; su contenido ya está en dev. Opcional: Cristian lo empuja a mano. Índice: `docs/informes/informe_tanda_2026-10-21_t6.md`. |
