# Tanda 6: estado

Rama `tanda-6`, creada desde `dev` (7d825b5) tras E0. Línea base de la suite: 4379/1/3.

| Etapa | Estado | Commit | Nota |
|---|---|---|---|
| E0 | Hecha | ea22565, a7f6db8, 02323a0, merge 7d825b5 | `merge-base --is-ancestor tanda-5 dev` = OK. Push `origin dev tanda-4 tanda-5`: DENEGADO por el clasificador de permisos de Claude Code (no llegó a git); lo hace Cristian. `data/unidades.json`=°C/kPa, `data/idioma.json`=es (sin commit). |
| T2 | Hecha | 5de3a1e, a15daa0, 5d7c93b, 5be87a2, 25727f6, 34552db, 5b1afa9, cd7f8d1, P-7, P-6, 563c133 + docs | P-1…P-9 y P-12 aplicados (P-10/P-11 sin cambio). Suite final 4451 passed / 2 skipped / 3 xfailed. Revisores: Altos corregidos, segunda pasada sin Críticos/Altos. Ver `T2_respuestas_T1.md`, `T2_matriz_actualizada.md`, `T2_ensayo_tabla.md`. |
| C1 | Hecha | ver git log (C1c, C1d, C1a, C1b) | a, b, c y d con pruebas; safety-reviewer en a y c sin Críticos ni Altos; Medios corregidos. Ver `C1_correcciones_t5.md`. |
| R1 | Hecha | ver git log `fix(r1)` / `docs(r1)` | 31 hallazgos listados: 4 corregidos en R1 (O1 SAF-05; I4 SAF-02/TMG-02, TMG-03, TMG-04), 2 ya cerrados antes, 25 abiertos (5 preguntas nuevas R1-P1…P5). safety-reviewer sin Críticos ni Altos; su Bajo está corregido. Ver `R1_hallazgos_pendientes.md`. |
| O2a | Hecha | ver git log `o2a` | Parámetros del equipo: tabla `system_params` (v8), API con 403/409 y auditoría, 7 submenús en QML, idioma y unidades según la decisión 1.9. Revisores: Altos corregidos (TMG-01, SAF-01). Ver `O2a_parametros_equipo.md`. |
| O2b | Hecha | 9192b36 + docs | Usuarios y operadores (v9), matriz 1.9, pantalla con pestañas. safety-reviewer sin Altos; H-01/03/04/05 corregidos. Suite 4801/2/3. Ver `O2b_usuarios.md`. |
| O2c | Hecha | ver git log `o2c` | Fecha y hora solo lectura, `GET /system/time`, aviso M1-01, para todos. Suite 4820/2/3. Ver `O2c_fecha_hora.md`. |
| O2d | Hecha | ver git log `o2d` | Información del sistema, `GET /system/info`, sin "No disponible" en el Menú principal. Suite 4836/2/3. Ver `O2d_info_sistema.md`. |
| O2e | Hecha | ver git log `o2e` | Bitácora `GET /audit_log` paginada con filtros, valores en unidad vigente, eventos de suspensión. Ver `O2e_bitacora.md`. |
| O2f | Hecha (rama tanda-6-o2fgh, unida) | ver git log `o2f` + merge | Calibración atmosférica (ventana 120 s, confirmación, auditoría `calibracion_atm_*`), página de prueba e impresión de ganancias. timing-auditor y safety-reviewer sin Críticos/Altos; TMG-04/05 y SAF-01/02 abiertos. Ver `O2f_calibracion_atm.md`. |
| O2g | Hecha (rama tanda-6-o2fgh, unida) | ver git log `o2g` + merge | Conectividad: red en solo lectura (`netsh`), destinatarios de correo editables por admin/ingeniero (técnico 403, 1.9), 409 en ciclo. Ver `O2g_conectividad.md`. |
| O2h | Hecha (rama tanda-6-o2fgh, unida) | ver git log `o2h` + merge | Respaldo/restauración por USB (serie, hashes, plausibilidad de calibración; programas no se restauran), técnico e ingeniero. safety-reviewer: Altos corregidos. Ver `O2h_respaldo.md`. |
