# Tanda 6 — índice (21-oct-2026)

Rama `tanda-6` (desde `dev` 7d825b5). Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_6.md`. Línea base de la suite: 4379/1/3.

**Bloque 2: SÍ se ejecutó.** `docs/mockups/tanda6/APROBADO.md` existía al empezarlo.

Estado detallado: `docs/informes/tanda6/estado.md`. Decisiones: `docs/informes/tanda6/DECISIONES_PARA_REVISAR.md`.

## Cierre (Z)
- Suite final: 5020 passed, 2 skipped, 3 xfailed (19 min, 22-oct)
- Merge `--no-ff tanda-6` en `dev`: `git merge --no-ff tanda-6` en `dev` (ver commit de merge)
- `git merge-base --is-ancestor tanda-6 dev`: `git merge-base --is-ancestor tanda-6 dev` = OK (exit 0)
- `git push origin dev tanda-6`: `git push origin dev tanda-6` OK (dev ea91725..7a872ce, tanda-6 rama nueva). `git push origin tanda-4 tanda-5` DENEGADO por el clasificador; su contenido ya está en dev. Opcional: Cristian lo empuja a mano
- Nada a `main`.

## Etapas

| Bloque | Etapa | Commit | Informe (`docs/informes/tanda6/`) |
|---|---|---|---|
| 1 | E0 | ea22565, a7f6db8, 02323a0, merge 7d825b5 | `estado.md` |
| 1 | T2 ★ | 5de3a1e … 563c133; docs 7e1f4bd | `T2_respuestas_T1.md`, `T2_matriz_actualizada.md`, `T2_ensayo_tabla.md` |
| 1 | C1 | d8bfde6, b816bd1, cbbf8d0, ce2878c | `C1_correcciones_t5.md` |
| 1 | X1 | 15ffbbd, merge 8181b66 | `X1_solapamiento_es.md` |
| 1 | I4 backend ★ | ed4c650, 5ff5139, af24210, merge 33c8baf | `I4_ingles_backend.md` |
| 1 | R1 | 81ebd3e, 2c741e3 | `R1_hallazgos_pendientes.md` |
| 1 | W1 | 74af54f | `W1_estacion_windows.md` |
| 1 | D1 | 910e4e3 | `D1_documentacion_62304.md` |
| 2 | B1 | d8a27b4, merge 700e3e9 | `B1_barra_flotante.md` |
| 2 | O3 | 33fd8de, merge 739e849 | `O3_entradas_mostradas.md` |
| 2 | O2a | a1cd455, 8926043, 9e7f7a0 | `O2a_parametros_equipo.md` |
| 2 | O2b | 9192b36, 39ec70c | `O2b_usuarios.md` |
| 2 | O2c | 01936bb, 9050d08 | `O2c_fecha_hora.md` |
| 2 | O2d | d4dcbda, d3fb631 | `O2d_info_sistema.md` |
| 2 | O2e | cc49976, 477a88d | `O2e_bitacora.md` |
| 2 | O2f | 5ab13ac, merge 4de45d7, db1d4b9 | `O2f_calibracion_atm.md` |
| 2 | O2g | 2a8ab46, merge 4de45d7, db1d4b9 | `O2g_conectividad.md` |
| 2 | O2h | e56dabb, merge 4de45d7, db1d4b9 | `O2h_respaldo.md` |
| 2 | I4 QML | 8b9fa78 | `I4_ingles_qml.md` |
| 2 | H1 | 980a9f5 | `H1_hoja_banco.md` |
| — | Z | commit de cierre | este índice, `estado.md`, `DECISIONES_PARA_REVISAR.md` |

## PREGUNTAS PARA CRISTIAN

### T2
- ¿Los segundos de tolerancia por DI vencida (hasta 4 s, vapor cortado) cuentan como exposición en ESTERILIZACION, o se pausa el timer / se marca el ticket?
- ¿DESPEJAR de COM-02/03 debe exigir el enlace "ok" o una sesión?
- ¿La marca "CARGA NO ESTÉRIL" también para FALLO, CANCELADO y EMERGENCIA?
- P-10: verificar en banco (C-05) qué botón ofrece la UI al arrancar con la cámara no segura.

### C1
- ¿Se reescriben con `clase` los programas duplicados antes de C1c, o basta la migración con advertencia?
- ¿El transductor de empaque mide en absoluto?

### X1
- Confirmar en el equipo, con las dos pantallas, que el solapamiento no reaparece.

### I4 backend
- ¿Se aprueba el inglés de los nombres de fábrica ("Bowie & Dick", "Instruments 121°C/134°C", "Liquids")?
- ¿Se marca la clase de los parámetros en las 49 plantillas de alarma para convertir sus unidades (I4-4)?
- ¿Se unifican las familias de códigos D-22 (`EMERGENCIA` ↔ `PARO_EMERGENCIA`) en una tanda con banco?

### R1
- R1-P1: ¿auditar el ACK del ALL_OFF al salir del modo prueba? Rec.: sí.
- R1-P2: `mantener_presion_camara` corre 2 veces por tick en PREPARADO. Rec.: una sola llamada, con banco.
- R1-P3: ¿separar `rango_calentamiento` en temperatura y presión? Rec.: sí.
- R1-P4: Principal perdido después de un protocolo ya iniciado, ¿pasa a `solo_lenta`? Rec.: sí.
- R1-P5: abort durante la tolerancia DI. Rec.: aceptar la cancelación o, como mínimo, cambiar el texto.

### W1
- ¿Qué edición de Windows tiene el PC industrial (Shell Launcher o tarea programada)?
- ¿Cómo entra el técnico? (decide los bloqueos de la cuenta del operador)
- ¿Contraseña de autologon en texto plano o Sysinternals Autologon?

### O3
- ¿Se amplía el registro de lecturas para guardar las entradas elegidas de cada ciclo?

### O2a
- `timeout_chaqueta`: ¿conectarlo en PREPARACION/PREPARADO con alarma que bloquee el inicio?
- SAF-02: ¿limitar `temp_max_apertura` por debajo de T_sat(P_atm) o reservar >80 °C al ingeniero?
- SAF-04: ¿un cambio de parámetro en PREPARADO reinicia la ventana de estabilidad?
- ¿El transductor de empaque y el rango 100–400 kPa son absolutos?
- Idioma de la segunda ventana QML (resuelto en I4 QML: lee `GET /language`; confirmar en banco).

### O2b
- ¿Selector de operador en Preciclo, validado en el backend (H-06)?
- H-02: ¿revalidar en cada petición que el usuario siga activo?

### O2e
- ¿Unificar en el visor `cycle_params_audit` y `sensor_calibration_audit`, o basta `audit_log`?
- ¿Mostrar la entidad con nombre traducido en vez de la clave?

### O2f
- SAF-01: ¿referencia fija por sitio (presión esperada o altitud), rechazando o exigiendo ingeniero si se aleja más de ±5 kPa?
- SAF-02: ¿`ABIERTO` viene de sensor de posición en todos los tipos de puerta, incluida `SimpleDoor`?
- ¿Descartar la medición en `por_confirmar` en cuanto arranca un ciclo?

### O2g
- ¿Remitente y servidor SMTP editables desde la pantalla (ingeniero)?

### O2h
- ¿Firmar el respaldo (HMAC con clave del equipo)?
- ¿Restaurar programas reutilizando el validador de `PATCH /cycle/parameter`?
- ¿Recrear usuarios con contraseña temporal y cambio obligatorio?
- ¿Restaurar también la presión atmosférica de referencia del mismo equipo?

### I4 QML
- ¿Exponer un código para el motivo de bloqueo del estado seguro (S4) para traducirlo?
- ¿Basta la revisión de truncado sobre estados vacíos, dejando diálogos con datos al recorrido en inglés de H1?

### H1
- ¿Se confirma la tolerancia de ±0,5 kPa contra el barómetro (D-30)?

## Pasos manuales previos al lunes 26-oct
1. **Push** de `dev`, `tanda-4`, `tanda-5` y `tanda-6` a `origin`: el clasificador de permisos de Claude Code lo bloqueó en E0 (no llegó a git). Resultado de Z: `git push origin dev tanda-6` OK (dev ea91725..7a872ce, tanda-6 rama nueva). `git push origin tanda-4 tanda-5` DENEGADO por el clasificador; su contenido ya está en dev. Opcional: Cristian lo empuja a mano.
2. Revisar `data/unidades.json` (°C/kPa) y `data/idioma.json` (es) en el equipo (no versionados).
3. Ejecutar W1 en el PC industrial según `tools/estacion/LEEME.md`: primero cada script con `-WhatIf`, luego en orden 01→05; verificar el log en `%ProgramData%\Especifika\Autoclave\estacion\estacion.log`. Ningún script se ejecutó en la tanda.
4. Verificar en banco la hoja H1 (`docs/mis_plans/hoja_pruebas_banco/`, 26 pruebas nuevas: E-07, F-05…F-07, B-09, B-10, C-06, A-06, D-20…D-36, G-03), en especial T2 (P-1, P-2, P-3, P-12), la calibración atmosférica (D-30/D-31) y el recorrido en inglés (D-34…D-36).
5. Regenerar `requirements.lock.txt` (le faltan PySide6, FastAPI…), necesario para la lista SOUP de D1.
6. Limpiar los worktrees de `.claude/worktrees/` (5 `agent-*`) y borrar las ramas ya unidas `tanda-6-x1`, `tanda-6-i4`, `tanda-6-b1`, `tanda-6-o3`, `tanda-6-o2fgh` (comprobar antes con `git branch --merged tanda-6`).
7. Revisar los archivos sin versionar que no son de la tanda: `installation_profile.json.invalido-20261020-145927`, `src/autoclave/i18n/es.json.bak`, `docs/catalogo_alarmas.2026-09-18.bak.md`, `src/autoclave/images/icono autoclave.jpg`.
8. Revisar las traducciones nuevas marcadas "sin revisar" (nombres de fábrica, `ciclo.principal_sin_lectura`, `notificaciones.despejar`, frases de bitácora de la unión O2f–O2h).
9. Responder las PREGUNTAS PARA CRISTIAN de arriba que afecten a la instalación (W1, O2f SAF-01, O2a SAF-02, tolerancia DI).

## Sin hacer / pendiente
- Z: suite final, merge, verificación y push (ver marcadores arriba).
- 25 hallazgos de revisores abiertos (R1), entre ellos los de PySide (P3 SAF-03/04/05, C1 SAF-05) y los Bajos de O1 (SAF-06/07).
- O2f: TMG-04 (hilo daemon) y TMG-05 (GET síncrono en hilo GUI) abiertos; SAF-01/02 como preguntas.
- O2a: `timeout_chaqueta` sin conectar; TMG-02 (GET síncrono) abierto.
- O2h: restauración de programas, perfil y usuarios; firma del respaldo.
- O2g: Wi-Fi/IP solo lectura; SMTP no editable desde la UI.
- O3: la gráfica no traza entradas fuera de `temp_camara`, `temp_ref`, `pres_camara`; `temp_drenaje_camara` sin fuente.
- I4: unificar familias de códigos (D-22), etiquetas del teclado (D-18), unidades en descripciones de alarma del PDF (I4-4), código del motivo de bloqueo del estado seguro (I4Q-2), `detail` del rechazo de cambio de programa en español (I4Q-4).
- D1: probabilidad/severidad de riesgos, ids de banco en la matriz, anomalías SOUP, V-01, firmware y otros "por completar".
- W1: comportamiento sin probar (solo análisis sintáctico); bloqueos de la cuenta del operador y AnyDesk sin script.
- X1: caso con dos pantallas no reproducido.

## Recordatorios (§1.11, no tocados en esta tanda)
- (a) El correo solo llega a los destinatarios guardados: a un correo escrito a mano no llega nada, aunque el software diga que se envió.
- (b) El asistente de instalación debe pedir información y calcular el modelo del equipo.
