# Tanda 28, flujo C — informe (A14, A12)

Rama `tanda28c`. Diagnóstico y comparación de A14 en `docs/informes/tanda28/A14_diagnostico.md`.

## A14 — resumen y medidas M1 y M2

Diagnóstico, planta simulada y gráficas antes/después en `docs/informes/tanda28/A14_diagnostico.md`. Causas (a), (b) y (c) del prompt confirmadas (con IF97 el margen de (b) es 3,26 kPa y no 3,6, AJ28C-01). Riesgo HAZ-EST-07, REQ-60..62 y fila de banco T28-A14-01 registrados.

### A14-M1 — banda PWM anclada a `P_sp` (commit `e538773c`)

- `EsterilizacionFase.consigna_pwm(t_est, brecha)` = `Psat(T_est + brecha_segura_temperatura + 0,3)` (el 0,3 es `_HIST_RECUP_TEMP_K`); se calcula una vez al entrar a la fase (`self.p_sp`, log «P_sp=… (banda …)») y la banda es `[P_sp - 2, P_sp + 1]`, en los dos modos. Fuera de IAPWS-IF97 cae a `Psat(T_est)`.
- Sin cambio: techo `P_control_max`, histéresis de 2 kPa del modo cámara, aislamiento VCH-AIS, RECUPERACION y sus transiciones, C-08, `factor_esterilizacion`, `intervalo_segmentos_ester`.
- Advertencia no bloqueante `aviso_banda_pwm_techo` (`catalogo_parametros._evaluar_banda_pwm`, texto es/en) si `P_sp + 1 > P_control_max - 5`: al guardar y en el log al cargar. Con la brecha 1,0 salta; con 0,3 (M3) no.
- Pruebas: `tests/test_t28_a14_esterilizacion.py` (nuevo); ajustadas a la banda nueva `test_esterilizacion_fase.py` y `test_t16_s1_esterilizacion.py`.

### A14-M2 — corte de `vapor_chaqueta` sobre la consigna (commit `6f07cf1c`)

- Componente puro `state_machine/cycle_phases/corte_chaqueta_consigna.py`; solo modo chaqueta, en CALENTAMIENTO (con ESTABLE_PREESTERILIZACION) y ESTERILIZACION: `vapor_chaqueta` OFF si `pres_chaqueta > consigna + margen_chaqueta_est`. Consigna: `P_sp` en ESTERILIZACION; `Psat(T_obj) + presion_add_calentamiento` en CALENTAMIENTO. Sin lectura de `pres_chaqueta` o sin consigna o margen utilizable: OFF (falla cerrada). Sin histéresis. Es un AND con la decisión de la fase y con D-CHQ; nunca enciende. El log anota el inicio y el fin del corte.
- Parámetro `esterilizacion.margen_chaqueta_est` (kPa, clase «diferencia», defecto 8, rango 2–30; `DECISIÓN SIN CONFIRMAR` hasta el banco): catálogo, migración que agrega el defecto si falta (`cycle_manager`), los 10 programas, i18n es/en; un valor fuera de rango en la fase se recorta.
- Las pruebas de modo chaqueta de la tanda 16 reciben ahora una lectura de `pres_chaqueta` bajo el umbral (antes no la tenían o era 330 kPa).

### Resultado simulado con M1 + M2 + M3 (134 °C, modo chaqueta)

De FALLO CIC-16 (6 aislamientos, 1,21 K, P máx 319,4 kPa, 42 % en banda) a COMPLETADO sin aislamientos, 0,59 K, P máx 311,6 kPa y 100 % en banda; modo cámara 0,87 K (antes 1,30 K). Planta provisional; se confirma en el banco (T28-A14-01).

Hallazgo AJ28C-01 (BAJA): el margen de la salida de RECUPERACION al techo con la brecha 1,0 es 3,26 kPa con IF97 (el prompt decía ≈3,6).

## A14-M3 — `brecha_segura_temperatura` = 0,3 °C (decisión de Cristian)

- Programas: 0,3 en los 10 JSON (`factory/` y `user/`); defecto del catálogo `BRECHA_SEGURA_TEMPERATURA_DEFECTO` = 0,3.
- Retirado el paso 1 de P2 de la tanda 16 (`_migrar_recuperacion`, 0,3 → 1,0 en cada carga; constantes `BRECHA_SEGURA_VIEJA/NUEVA` eliminadas). Se conservan el paso 2 (subir `presion_add_esterilizacion` al mínimo de `COHERENCIA_RECUPERACION`) y la salvaguarda del alivio (paso 3).
- Migración única nueva `cycle_manager._migrar_brecha_t28` (corre antes de P2 y solo en la carga desde archivo, como P2): 1,0 → 0,3 con origen «migración tanda 28 (M3)», que reutiliza la vía de C-04.4/P2 (fila `param_ciclo_cambio`, aviso SIS-06 no bloqueante y reescritura del JSON de usuario con `.bak`). La marca `migrado_t28_m3: true` en la hoja del parámetro la hace idempotente: un 1,0 fijado a mano después se conserva. Un valor distinto de 1,0 y 0,3 (p. ej. 0,7) no se toca (solo se marca). La copia y la instantánea de un ciclo interrumpido no migran.
- `presion_add_esterilizacion` sin cambio (15 a 134 °C, 11 a 121 °C). `COHERENCIA_RECUPERACION` con brecha 0,3: mínimo 8,09 kPa a 134 °C y 5,88 a 121 °C; se cumple. Histéresis C-08 (+0,3 K, +1,0 kPa) sin cambio.
- A 134 °C: `P_sp` = Psat(134,6) = 309,57 kPa; borde alto de la banda 310,57; techo 319,20; margen 8,6 kPa (sin la advertencia de A14-M1).
- Resultado simulado (planta provisional): modo chaqueta pasa de FALLO CIC-16 (6 aislamientos, 1,21 K) a COMPLETADO sin aislamientos y 0,59 K; modo cámara sin regresión (0,87 K, antes 1,30 K).
- Pruebas: `tests/test_t28_a14_m3_brecha.py` (nuevo). Adaptadas a la decisión, sin relajar lo que verifican: `test_t12_c07_c13_json.py` (valor de los JSON: 0,3) y `test_t16_s4_programas.py` (las pruebas de P1/P2 que necesitan brecha 1,0 la fijan explícitamente, con la marca de M3 si pasan por la carga; la del paso 1 retirado se reemplazó por `test_p2_ya_no_sube_la_brecha_03`).

Hallazgos:
- **AJ28C-02 (BAJA)**: la marca de idempotencia vive en la hoja del parámetro (`esterilizacion.brecha_segura_temperatura.migrado_t28_m3`), porque `escribir_parametros` y el guardado del backend solo reescriben `parameters`. La pantalla y la validación ignoran claves extra de la hoja. Un programa de usuario con 0,3 o 0,7 queda marcado en memoria y la marca llega al archivo con el siguiente guardado. `DECISIÓN SIN CONFIRMAR`.
- **AJ28C-03 (BAJA)**: los defectos del hospital (`cycles/defecto/`) se migran en memoria al cargar pero no se auditan ni se reescriben (igual que P2 de la tanda 16). `DECISIÓN SIN CONFIRMAR`.

## A12 — Prevacío atascado entre escape y vacío

Causa confirmada en `prevacio.py`: el paso DECOMPRESION de cada pulso solo pasaba a VACIO_BAJO con `pres <= atm + rango_presion_atm` (el rango de cámara segura del equipo, 5 kPa por defecto) y no tenía tiempo límite. Con la cámara cerca de la atmosférica el escape rápido casi no tiene diferencial y la presión puede quedar estancada sobre ese umbral: el pulso quedaba detenido sin vapor ni bomba, indefinidamente. Ejemplo: el programa de fábrica de 134 °C tiene `presion_alta_pulso_a` 80 kPa; en Bogotá (74,6 kPa) el umbral era 79,6 kPa.

Cambios (commit `A12`):
- Parámetro de programa `prevacio.presion_inicio_vacio` (kPa sobre la atmosférica, clase «diferencia», defecto 10, rango 0–30, `DECISIÓN SIN CONFIRMAR`). DECOMPRESION pasa a VACIO_BAJO con `pres <= atm + presion_inicio_vacio`; ya no usa `rango_presion_atm`.
- Parámetro `prevacio.timeout_descompresion` (min, int, defecto 5, rango 1–30, `DECISIÓN SIN CONFIRMAR`). Se arma en el primer tick del paso de cada pulso y corre también sin lectura de presión. Al vencer: escape rápido OFF, la bomba no se enciende, FALLO con código propio **CIC-20** «Descompresión del prevacío sin terminar» (ALARMA, bloquea el inicio, despeje manual, como CIC-15; textos es/en con título, plantilla y acción, que usa la ventana de detalle ALD) vía `alarma_fallo` (`_ALARMAS_PROPIAS_FASE` de CicloState) y protocolo de fallo normal.
- Fuera de rango en la fase (programa dañado o instantánea vieja): se recorta al rango y, sin valor numérico, rige el defecto.
- Los dos parámetros en los 10 programas (`factory/` y `user/`), en el catálogo (`_poner`, validación al guardar con `set_param` y al cargar con `errores_programa`) y con etiqueta y descripción es/en en Parámetros del ciclo › Prevacío (se actualizó también la descripción de «Número de pulsos A», que citaba el rango atmosférico).
- Migración al cargar (`migrar_parametros`, `_agregar_claves_a12`): defecto si falta, con origen «migración tanda 28 (A12)». Como cambian el comportamiento de un programa existente, cada agregado se audita (`param_ciclo_cambio`, valor anterior vacío, causa `migracion_parametro_nuevo`) y el JSON de usuario se reescribe con `.bak` (mismo mecanismo que la migración correctiva), sin aviso SIS-06.
- Sin cambios en la secuencia de pasos, en `_STAGGER_APAGADO_VACIO` (0,15 s) ni en `timeout_bajo`/`timeout_alto`.

Revisión de las demás comparaciones del prevacío (punto 4):
- VACIO_BAJO (`pres <= presion_baja_pulso_X`) y VAPOR_ALTO (`pres >= presion_alta_pulso_X`) comparan contra presiones absolutas del programa y ya tienen tiempo límite (`timeout_bajo` / `timeout_alto` → FALLO CIC-02): no pueden quedar detenidos indefinidamente.
- Una `presion_alta_pulso_X` subatmosférica se alcanza subiendo desde el vacío, así que VAPOR_ALTO → HOLD_ALTO no se atasca; y el DECOMPRESION siguiente pasa enseguida (la cámara ya está bajo atm + margen). No se cambió.
- No hay otra comparación del prevacío contra `rango_presion_atm` ni contra la atmosférica.

Pruebas: `tests/test_t28_a12_prevacio.py` (nuevo): presión estancada en atm + 6 kPa con rango 5 pasa a vacío con `presion_inicio_vacio` 10 (con 5 sigue escapando y no depende del rango del equipo); `timeout_descompresion` da FALLO CIC-20 sin bomba, también sin lectura, y se reinicia en cada pulso; registro de CIC-20 en CicloState; textos; parámetros en los 10 programas; rangos del catálogo y validación al cargar y al guardar; migración con defectos, auditoría sin SIS-06, `.bak` e idempotencia. `tests/test_alarmas_catalogo.py` extendido con CIC-20 (valores y nivel). Las pruebas existentes de prevacío siguen en verde sin cambios.

Hallazgos:
- **AJ28C-04 (ALTA, corregido)**: DECOMPRESION del prevacío sin margen propio ni tiempo límite: el pulso podía quedar detenido indefinidamente (ver arriba).
- **AJ28C-05 (MEDIA, sin cambio)**: durante VAPOR_ALTO/HOLD_ALTO el escape lento abre en espejo del vapor; con una `presion_alta_pulso_X` subatmosférica (80 kPa de fábrica es subatmosférica a nivel del mar) la cámara puede estar bajo la atmosférica con el escape abierto, con posible entrada de aire. No atasca el pulso; no se tocó por la restricción de no cambiar la secuencia. Para decisión de Cristian.
- **AJ28C-06 (BAJA)**: arrancar la bomba con la cámara hasta 10 kPa sobre la atmosférica (antes como mucho el rango del equipo, 1–10 kPa) es la elección del prompt; valor y efecto sobre la bomba por confirmar en el banco. `DECISIÓN SIN CONFIRMAR`.
- **AJ28C-07 (BAJA)**: auditar los parámetros agregados (y reescribir el JSON de usuario con `.bak`) sin SIS-06: el prompt pide «auditoría como las migraciones anteriores», pero las claves nuevas anteriores (T12, T16, A14-M2) no se auditaban; se auditan estas porque cambian el comportamiento. `DECISIÓN SIN CONFIRMAR`.
- **AJ28C-08 (BAJA, entorno)**: `tests/test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite` falla en esta máquina sin `PYTHONUTF8=1` (salida del subproceso QML en cp1252); con UTF-8 pasa. No lo toca este cambio.

Documentación de A14 hecha (riesgo HAZ-EST-07, REQ-60..62, `CLAUDE.md`, fila de banco T28-A14-01). Pendiente (fuera de A14): revisor de seguridad sobre A14-M3 y A12, riesgo HAZ-PRV-01, trazabilidad y fila de banco de A12 (repetir el ciclo con los pulsos que se atascaban).
