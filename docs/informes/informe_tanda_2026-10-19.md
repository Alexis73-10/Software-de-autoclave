# Informe de la tanda 2 (19 y 20 de octubre de 2026)

Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_2.md` (más `instruccion_claude_code_u4_tarjeta_desconectada.md`, insertada el 19-oct antes de S3). Estado y tabla de etapas: `docs/informes/tanda2/estado.md`. Cada etapa tiene su informe en `docs/informes/tanda2/` con archivos tocados, revisores, decisiones sin confirmar, pendientes y comprobaciones manuales.

- **Rama `tanda-2`**, creada desde `dev` (`dev-noche` ya era ancestro de `dev`). **Sin `git push`; nada se unió a `dev`.** No se tocó hardware, no se compiló firmware ni ejecutables.
- **Pruebas:** línea base de 3358 en `dev` limpio; al cierre de las etapas de código, 3585 pasan. **2 fallos, ajenos a esta tanda** (ver §3).
- **U4** la hizo otra sesión de Claude en el mismo árbol (`f6d55e6`); se integró sin conflictos con S3a y R1.

## 1. Índice de lo hecho

| Etapa | Commit | Pruebas al cerrar | Revisores | Informe |
|---|---|---|---|---|
| (previo) cambios sin commit encontrados al empezar: barra de tareas y simulador con historial | `49c7efa` | — | — | `U1_*` §Antecedentes |
| U1 Alarmas fuera de la barra superior | `9fba067` | 3375 | Sí | `U1_avisos_en_campana.md` |
| U2 Navegación inferior uniforme | `1c778c7` | 3386 | Sí | `U2_navegacion_inferior.md` |
| U3 Botón de tiempo de secado | `b9453de` (solo informe) | — | — | `U3_boton_secado.md` |
| S1 DO1/DO2 | `5aa6f92` | 3394 | Sí | `S1_do1_do2.md` |
| S2 `/cycle/select` | `7b8d44a` | 3413 | Sí | `S2_cycle_select.md` |
| P1 Hoja de pruebas de banco | `382e672` | — (documentos) | — | `P1_hoja_pruebas_banco.md` |
| G1 Generador de códigos | `2ce4e98` | 30 de G1 | No (fuera de la lista de la regla 7) | `G1_generador_codigos.md` |
| U4 Tarjeta desconectada vs. paro | `f6d55e6` (otra sesión) | 3498 | Sí | `U4_tarjeta_desconectada.md` |
| R1 Retiro de tkinter | `ece51e9`, `7669c1b` | 3518 | — | `R1_retiro_tkinter.md` |
| S3a Plausibilidad de calibración | `32e0b3a` | 3560 | Sí | `S3a_calibracion_plausibilidad.md` |
| S3c/S3d Base en falla y respaldo fuera del tick | `5cc27ff` | 3585 | Sí (safety + timing) | `S3_pendientes_c_d_e_f.md` |
| S3e `door_id` / `source_door` | `7955db6` | 3585 | Sí (con S3c/d) | `S3_pendientes_c_d_e_f.md` |
| S3b CIC-10 | — (propuesta) | — | — | `S3b_cic10_propuesta.md` |
| S3f SECADO | — (derivado a banco, prueba E-03) | — | — | `S3_pendientes_c_d_e_f.md` |
| W1 Estación Windows | (este commit; solo documento) | — | — | `docs/mis_plans/planeacion_estacion_windows.md` |

**Revisores:** en todas las etapas de seguridad se corrigieron los hallazgos Altos antes del commit (hubo Altos en U1, U2, S2, S3a y S3c/d; todos corregidos). Los Medios y Bajos corregidos o aceptados están en cada informe.

## 2. Bloqueadas

Ninguna.

## 3. Cosas que requieren tu atención (no son de esta tanda)

1. **2 pruebas en rojo** en `tests/test_t9_instalacion.py::test_app_abre_el_asistente_solo_en_la_puerta_1_sin_perfil` (casos `[2-True-False]` y `[1-False-False]`). Las causa un **cambio sin commit de otra sesión** en `src/autoclave/ui_qml/app.py` (la intro de arranque ahora sigue el progreso real del backend, `ProgresoArranqueBackend`): el test parchea `SimuladorProgresoArranque` para cortar el flujo y ya no se corta. Arreglo sugerido en el test: fijar `AUTOCLAVE_INTRO_SIMULACION` o parchear `app_mod.ProgresoArranqueBackend`. Con el árbol de esa sesión limpio, la suite está verde.
2. **Cambios sin commit de otra sesión** (el `.exe` único y la intro de arranque) que **no se tocaron ni entraron en ningún commit**:
   - `src/autoclave/exe_unico.py`, `Autoclave.spec`, `instalador_exe.py` (nuevos);
   - `utils/resources.py`, `utils/logging.py`, `utils/paths.py`, `cycle_manager.py`, `installation/backend_guard.py`;
   - `ui_qml/bridge/lanzador_ajustes.py`, `progreso_arranque.py`, `standby.py`, `qml/Main.qml`, `qml/Pantallas/IntroArranque.qml`, `ui_qml/app.py`, `tests/test_standby.py`;
   - `docs/mis_plans/instruccion_claude_code_tanda_2.md` (se agregaron U4 y G1).

   Decide quién los revisa y commitea. R1 declara `exe_unico.py` + `Autoclave.spec` como el punto de entrada de producción.
3. **Comentarios con "tkinter"** que quedan en `lanzador_ajustes.py` (archivo con cambios ajenos): se limpian al commitear ese archivo.

## 4. Decisiones sin confirmar (resumen; detalle y alternativa en cada informe)

**Prioridad (seguridad o instalación):**
- **U1 D-U1-1/-4 (reemplazadas por U4):** el panel de la campana ya no se bloquea ni se abre solo; U4 lo sustituyó (insignia roja parpadeante y tarjeta de alarmas, §2.E de su informe).
- **U2 D-U2-3:** abandonar el cambio de contraseña obligatorio descarta la sesión incompleta; **D-U2-5:** fuera de las pantallas con sesión, los toques no la prolongan (vence a los 5 min).
- **S1 D-S1-1/-2:** "generador interno" = sin DO1 ni DO2 para todo equipo con `vapor_source = generator`; un perfil sin el campo se sigue tratando como mixto. **Hay que reinstalar el perfil del equipo de pruebas con el asistente QML** (el `installation_profile.json` de la raíz del repo no tiene `vapor_source`).
- **S2 D-S2-1:** el origen del cambio de programa es declarado, no autenticado: riesgo aceptado de trazabilidad para el expediente.
- **S3a D-S3a-1:** valores de plausibilidad de calibración (conservadores), y la lectura "mostrada" no se contrasta con la viva (S3a-02 aceptado).
- **S3c D-S3c-1:** el paso a "sin base de datos" por una falla en caliente es **permanente hasta reiniciar**.
- **S3b:** CIC-10, ver §5.

**Otras:** U1 D-U1-0, D-U1-2/3/5; U2 D-U2-1/2/4; D-S3d-1; D-S3e-1; D-P1-1 (el imprimible es HTML, no `.xlsx`); D-R1-1/2/3; D-G1-1 a D-G1-4.

## 5. Pendientes

**Decisión de producto:**
- **CIC-10** (S3b): opciones A, B y C; se recomienda A + B y no implementar C sin análisis de riesgos.
- **Tarjeta "Tiempo adicional de secado"** del Menú Principal (U3): retirarla, mostrar `secado.tiempo_secado` o dejarla.

**Seguridad o proceso:**
- **Hoja de banco** (`docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.html`): ejecutarla en el equipo de pruebas; incluye SECADO con bomba y válvulas cerradas (E-03), el fsync del respaldo con antivirus y Líquidos con vidrio real.
- Los **permisos por rol de puertas** siguen sin aplicarse en la ruta HTTP (S3e).
- Dos llamadas síncronas del tick que quedan, una vez por ciclo (`contador.siguiente`, `marcar_en_curso`).
- **Entradas del generador** DI9 (`agua_generador`) y DI12 (`vapor_suministro`): si el generador interno no las entrega al software, hay que desmarcarlas en el asistente (S1).
- **`cycle_manager` y rutas del `.exe` único:** quedan con la otra sesión.

**De producto:** diseño final de los avisos, del modo sin base de datos, del asistente y de Opciones; revisión de las traducciones nuevas (`docs/mis_plans/revision_traducciones.md`); Fase 5 de Opciones (retiro de PySide; las vistas PySide se conservaron); `planeacion_generador_codigos.md` (firmas Ed25519, servidor central, licencias).

## 6. Comprobaciones manuales de Cristian

Todas están ordenadas y con criterio de aprobado en **la hoja de pruebas de banco** (`hoja_pruebas_banco_equipo_pruebas.html`, 28 pruebas), y detalladas en cada informe (U1: paro y panel; U2: navegación; S1: perfil y entradas; S2: cambio de programa; S3: calibración, base en falla, puertas; R1: compilar y probar `Autoclave.exe`; G1: compilar y probar el generador y su inicio automático).

Siguiente paso para integrar: revisar `tanda-2` (14 commits sobre `dev`) y unirla a `dev` cuando se apruebe, **después de resolver los puntos de §3**. Hacer `git push` solo por decisión de Cristian.
