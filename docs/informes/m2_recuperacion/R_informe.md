# M2-REC: exención del corte A14-M2 en esterilización — informe (7-nov-2026)

Prompt: `docs/mis_plans/prompt_claude_code_m2_recuperacion.md`. Rama `m2_recuperacion` (sin unir a `dev`). La primera versión, con las condiciones (a) RECUPERACION y (b) bajo la banda, quedó bloqueada por el resultado de la planta (§3). **Cristian eligió la opción 1 (§5): la exención aplica solo con la condición (b).** Pendiente: revisión de seguridad (la lanza el director), merge a `dev`, compilación y `CERRADO.txt`. No se compiló: `python tools/entrega/compilar_entrega.py`.

## 1. Diagnóstico (confirmado)

- El código coincide con el diagnóstico. En `EsterilizacionFase._vapor_on()` el corte A14-M2 (`corte_chaqueta_consigna.debe_cortar`: `pres_chaqueta > P_sp + margen_chaqueta_est`, 208,9 + 8 = 216,9 kPa a 121 °C) deja `vapor_chaqueta` en OFF en RECUPERACION y en la rama «bajo la banda» del PWM. `vapor_camara` sigue abierta, pero con la chaqueta a 8–10 kPa sobre la cámara el paso no basta para reponer la pérdida de una carga líquida.
- El `backend.log` del equipo (`backend_equipo_7nov.log`, no versionado: `.gitignore` excluye `docs/informes/**/*.log`) muestra, para el ciclo 23, la secuencia del prompt: cortes M2 cada ~10 s desde el inicio de ESTERILIZACION (la fase arranca en RECUPERACION con T = 121,3 < 121,6), aislamiento a 216,1 kPa, fin del aislamiento a 211,9 kPa, corte M2 con la chaqueta a 227,3 kPa y FALLO CIC-04 a 201,5 kPa 16 s después. No hay inhibición D-CHQ, SUM-06 ni CIC-18.
- Origen de la chaqueta cargada: en CALENTAMIENTO, durante el empuje de líquidos y la bajada a saturación, el umbral M2 usa el techo ampliado: Psat(121) + 11 + 15 + 8 ≈ 239 kPa. En ESTERILIZACION baja a 216,9. La chaqueta entra a esterilización por encima del umbral nuevo.
- La planta simulada reproduce el fallo sin la exención (§3).

## 2. Cambio (commits 7409303e y abad2554)

**Versión vigente (abad2554, opción 1):** `motivo_exencion(pres_camara, consigna, banda_baja)` devuelve `"bajo_banda"` solo con `pres_camara < P_sp - 2` (lecturas numéricas) y None en otro caso; RECUPERACION ya no exime. La fase la evalúa en el paso 4 (modo chaqueta, sin aislamiento), en RECUPERACION y en PWM. Todo lo demás de esta sección sigue igual. La descripción que sigue es la de la primera versión (7409303e).


- `corte_chaqueta_consigna.py`: `motivo_exencion(en_recuperacion, pres_camara, consigna, banda_baja)` → `"recuperacion"`, `"bajo_banda"` o None (función pura, sin histéresis; `True` estricto; sin lectura numérica de cámara no hay «bajo_banda»), y el parámetro `debe_cortar(..., camara_necesita_vapor=False)`. Con la exención, el umbral no corta, pero sigue cortando sin lectura válida de `pres_chaqueta` o sin umbral calculable (falla cerrada).
- `esterilizacion.py`: en el paso 4, solo en modo chaqueta y sin aislamiento, la fase fija `self._exencion_m2` con `motivo_exencion(self._en_recuperacion, pres, self.p_sp, _BANDA_PWM_BAJA)` (ya con la transición RECUPERACION↔PWM de ese tick) y `_corte_consigna_chaqueta` lo pasa a `debe_cortar`. Con aislamiento, o sin lectura del Principal o de la cámara, la exención vale None. `_vapor_on()` sigue evaluando primero `inhibir_vapor_chaqueta` (D-CHQ), y el corte duro de CICLO tras `update()` no cambia. Modo cámara sin cambio.
- Log, sin bitácora: una línea al empezar cada tramo y otra al terminarlo, o al cambiar de motivo, con `pres_camara`, `pres_chaqueta`, el umbral M2 y el motivo (`_actualizar_exencion_m2`).
- `reset()` deja `_exencion_m2 = None`.

## 3. Planta simulada (valores PROVISIONALES)

`tests/helpers/planta_vapor.py` recibe parámetros opcionales: `PERDIDA_CAMARA` (por defecto 0, el modelo de A14 no cambia), estado inicial (`p_camara_inicial`, `t_sonda_inicial`), `ajustes` por instancia, `programa_liquidos()`, `simular(..., planta_kw=, desde_esterilizacion=)`, y en el resultado `p_min_ester`, `p_chaqueta_max_ester` y `exencion_s`.

Escenario de líquidos a 121 °C en modo chaqueta (`ESCENARIO_LIQUIDOS` en `tests/test_m2_rec_esterilizacion.py`):
- entrada a ESTERILIZACION con la chaqueta a 240 kPa y la cámara a 213 kPa;
- pérdida de la cámara de 0,35 kPa/s sin vapor (escape lento enclavado y carga líquida);
- paso chaqueta → cámara 0,015/s (restrictivo);
- 1 s de `vapor_chaqueta` = +12 kPa en la chaqueta;
- sonda en la carga a 121,0 °C, que sube despacio;
- sin pérdida térmica propia de la carga.

Programa de fábrica `liquidos.json`.

| Variante | Resultado | t | Aislamientos | P cámara máx / mín (kPa) | P chaqueta máx (kPa) | T máx (°C) |
|---|---|---|---|---|---|---|
| Antes (sin exención) | FALLO CIC-04 (201,9 < 203,0) | 51 s | 0 | 213,1 / 201,9 | 240,0 | 121,15 |
| **M2-REC-01 tal como se decidió** | **FALLO CIC-16 (6 aislamientos en 15 min)** | 72 s | 6 | 216,4 / 211,2 | 342,0 | 121,29 |
| Antes, paso 0,025 | FALLO CIC-04 | 88 s | 0 | 213,5 / 202,9 | 240,0 | — |
| M2-REC-01, paso 0,025 | FALLO CIC-16 | 64 s | 6 | 216,9 / 211,3 | 336,3 | — |
| Antes, carga que se calienta más rápido (CALOR 0,01) | FALLO CIC-04 | 52 s | 0 | 213,1 / 201,9 | 240,0 | — |
| M2-REC-01, CALOR 0,01 | FALLO CIC-16 | 74 s | 6 | 216,6 / 211,3 | 342,0 | 121,64 |

Sin la exención, el resultado coincide con el equipo: CIC-04 a los 51–88 s (en el equipo, 56 y 83 s).

**Con la exención la cámara ya no cae, pero el ciclo falla antes y por CIC-16.** Mecanismo:
1. La sonda de la carga líquida no llega a la salida de RECUPERACION (T ≥ 121,6 °C) en esos segundos.
2. La exención (a) deja `vapor_chaqueta` abierta de forma continua.
3. La chaqueta sube hacia el suministro (342 kPa; nunca llega al corte D-CHQ de 375, porque el suministro es de 350).
4. La cámara llega al techo de 216,0 kPa, se aísla, baja a 213 kPa, se reabre y vuelve a subir en ~2 s, hasta 6 aislamientos.

En todas las variantes la cámara queda bajo el techo + 1 kPa, y la chaqueta bajo D-CHQ y el alivio (385).

**Escenario de 134 °C de A14** (`test_t28_a14_m3_brecha::test_simulado_134_chaqueta_m1_m2_m3_sin_aislamientos`, planta original sin cambios). Con la exención:
- 1 aislamiento (antes 0);
- sobreimpulso de 1,09 K (antes 0,59 K);
- cámara a 319,2 kPa, es decir, en el techo;
- chaqueta a 339 kPa (antes 320).

La causa es la exención en RECUPERACION al entrar a la fase (22 s de exención). **Esta prueba queda en rojo**: no la ajusté, porque fija el resultado de seguridad de A14 (HAZ-EST-07) y no un detalle del corte.

**Resultado con la opción 1 implementada (abad2554):**

| Escenario | Resultado | Aislamientos | P cámara máx / mín (kPa) | P chaqueta máx (kPa) | T mín / máx (°C) | Exención |
|---|---|---|---|---|---|---|
| Líquidos 121 °C, base | COMPLETADO (900 s) | 0 | 213,1 / 206,8 | 255,1 | 121,00 / 121,30 | 65 s |
| Líquidos 121 °C, paso 0,025 | COMPLETADO | 0 | 213,5 / 206,8 | 240,0 | 121,00 / 121,31 | 64 s |
| Líquidos 121 °C, CALOR 0,01 | COMPLETADO | 0 | 213,1 / 206,7 | 254,9 | 121,00 / 121,32 | 65 s |
| 134 °C de A14, modo chaqueta | COMPLETADO | 0 | 311,6 / — | 326,0 (antes 320,1) | sobreimpulso 0,59 K (igual) | 3 s |
| 134 °C de A14, modo cámara | COMPLETADO | 0 | 319,4 / — | — | sobreimpulso 0,87 K (igual) | 0 s |

`test_simulado_134_chaqueta_m1_m2_m3_sin_aislamientos` vuelve a verde sin tocarlo. Riesgo de la exención (pedido por el prompt): con la opción 1 la chaqueta no pasa de 255 kPa y la cámara no vuelve al techo (máx. 213,5 kPa frente a 216,0): no hay aislamientos nuevos ni riesgo de CIC-16 en la planta. El tope de chaqueta propio no hace falta con estos valores, pero queda como `DECISIÓN PENDIENTE` de Cristian si el banco muestra otra cosa.

**Exploración previa a la decisión (no implementada):**

| Variante | Líquidos 121 °C (las 3 plantas) | 134 °C de A14 |
|---|---|---|
| Exención solo «bajo_banda», sin (a) | COMPLETADO, 0 aislamientos, cámara mín. 206,7–206,8 kPa, chaqueta máx. 240–255 kPa | COMPLETADO, 0 aislamientos, 0,59 K (igual que hoy) |
| (a)+(b) con tope de chaqueta 235 kPa | COMPLETADO, 0 aislamientos | no medido |
| (a)+(b) con tope de chaqueta 250 kPa | COMPLETADO, 2 aislamientos | no medido |
| (a)+(b) con tope de chaqueta 275 kPa | CIC-16 | no medido |
| (a)+(b) con tope de chaqueta 225 kPa | CIC-04 | no medido |

## 4. Hallazgo en CALENTAMIENTO (DECISIÓN PENDIENTE de Cristian)

No cambié nada en CALENTAMIENTO.
- En `bajando_a_psat` el duty es 0 por diseño, así que M2 no bloquea nada que la fase pida.
- En ESTABLE_PREESTERILIZACION el PWM puede pedir vapor (duty > 0 con P < Psat(T_obj) + 1). Ahí rige M2 con umbral Psat(T_obj) + `presion_add_calentamiento` + 8 ≈ 224 kPa a 121 °C, con el techo normal tras el empuje. El mismo bloqueo puede darse si la chaqueta queda sobre ~224 kPa tras el empuje (umbral ampliado ≈ 239 kPa), con un margen 7 kPa mayor que en esterilización. Ahí terminaría en el timeout de recuperación de la estabilización (`timeout_recuperacion_estabilizacion`, 5 min) y no en CIC-04.
- Hallazgo relacionado: el escalón del umbral M2 entre CALENTAMIENTO con empuje (≈239 kPa) y ESTERILIZACION (216,9 kPa) es lo que hace que esterilización empiece con la chaqueta «cargada».

## 5. Bloqueo de la primera versión y decisión de Cristian

**Decisión tomada (7-nov): opción 1, exención solo con la condición (b).** Implementada en abad2554. Se conservan las salvaguardas: lectura válida de `pres_chaqueta`, VCH-AIS, D-CHQ y el corte duro de CICLO prevalecen. El texto que sigue es el análisis que llevó a la decisión.

El prompt pide detenerse si la planta contradice el diagnóstico. La planta confirma que M2 bloquea la reposición cuando la cámara está **bajo la banda**. Contradice en cambio la premisa de la condición (a): que estar en RECUPERACION signifique que la cámara necesita vapor.

En líquidos, la fase sigue en RECUPERACION por la temperatura lenta de la sonda de la carga (121,0 < 121,6 °C) aunque la presión de la cámara esté sobre la banda. Eximir el corte ahí:
- convierte CIC-04 en CIC-16, y antes;
- en el escenario de 134 °C de A14, reintroduce un aislamiento y el sobreimpulso que A14 eliminó. Una prueba de seguridad de A14 queda en rojo.

Ante esto, y siguiendo «ante ambigüedad, lo seguro», no uní la rama a `dev`. El código de la rama implementa M2-REC-01 tal como se decidió, con sus pruebas.

**DECISIÓN PENDIENTE de Cristian** (una de):
1. **Solo la condición (b)** (`pres_camara < P_sp - 2`), sin (a). Recomendada por la planta: COMPLETADO en las 3 variantes de líquidos y sin cambio en 134 °C. Es un cambio de una línea en `motivo_exencion` más los ajustes de prueba.
2. (a)+(b) con un tope de chaqueta propio para la exención. La planta indica que es sensible al valor: 225 → CIC-04, 235 → COMPLETADO, 250 → 2 aislamientos, 275 → CIC-16. Habría que fijarlo en banco.
3. Mantener (a)+(b) tal como se decidió y aceptar el riesgo de CIC-16 y el aislamiento a 134 °C. Habría que ajustar `test_simulado_134_chaqueta_m1_m2_m3_sin_aislamientos` y actualizar HAZ-EST-07.

## 6. DECISIÓN SIN CONFIRMAR / PENDIENTE

- **Sin confirmar:** el tramo de exención que va al log es «cámara bajo la banda» en un tick de control sin aislamiento, aunque `pres_chaqueta` esté bajo el umbral y la exención no cambie nada en ese tick. Motivo único: `bajo_banda`.
- **Sin confirmar:** sin histéresis (lo pidió el prompt). Con la presión de cámara ruidosa en el borde `P_sp - 2`, `vapor_chaqueta` puede conmutar tick a tick con la chaqueta sobre el umbral (una orden fc05 por cambio). Se mide en el banco (M2-REC-01).
- **Pendiente de Cristian:** el hallazgo de CALENTAMIENTO (§4) y el tope de chaqueta para la exención, si el banco lo pide.
- Con lectura del Principal pero sin lectura de la cámara (o al revés), la exención vale None: el paso 1c ya deja `vapor_chaqueta` en OFF.
- Valores de la planta (todos provisionales): pérdida de 0,35 kPa/s, paso 0,015/s, llenado de 12 kPa/s, sonda en la carga, sin pérdida térmica de la carga.

## 7. Pruebas

- `tests/test_m2_rec_esterilizacion.py` (39 casos, opción 1):
  - componente: `debe_cortar` con la exención, sin lectura, sin umbral y con `True` estricto; `motivo_exencion`;
  - RECUPERACION dentro de la banda → corte como antes; RECUPERACION y PWM bajo la banda con la chaqueta sobre el umbral → ON;
  - dentro o sobre la banda → corte u OFF como antes;
  - sin lectura de `pres_chaqueta` → OFF; aislamiento → OFF; D-CHQ → OFF; sin lectura de la cámara → sin exención;
  - modo cámara sin cambio; log sin repetición; `reset`;
  - planta de líquidos en 3 variantes: antes CIC-04, después COMPLETADO sin aislamientos.
- `tests/test_t28_a14_esterilizacion.py`: tres pruebas fijaban el corte con la cámara bajo la banda (`Psat(134)` = 304,2 kPa < `P_sp - 2` = 307,6 kPa, o la rama `P < p_low`).
  - `test_m2_ester_corta_sobre_p_sp_mas_margen_y_reabre_debajo` y `test_m2_ester_usa_el_margen_del_programa` pasan a PWM dentro de la banda, en el tramo ON (`_ester_chaqueta_pwm_on`).
  - `test_h1_bajo_p_low_con_el_corte_activo` ahora espera ON bajo la banda y el corte al volver a la banda.
- `test_t28_a14_m3_brecha::test_simulado_134_chaqueta_m1_m2_m3_sin_aislamientos`: en verde, sin tocarlo.
- Pruebas desactualizadas por las decisiones de Cristian del 7-nov, corregidas en commits aparte:
  - c243153e: `test_t10_endurecimiento::test_liquidos_reglas_de_coherencia` ya no espera el rechazo del prevacío con líquidos (permitido desde 1f23a230); el doble de `get_param` de `test_s2b_revision_correcciones` acepta el kwarg `default`.
  - a761ff1b: `test_q1_r1p3_rango_calentamiento::test_migracion_copia_el_valor_a_los_dos_y_conserva_el_orden` espera `presion_add_liquido_calentamiento` al final de la sección (migración del ajuste de líquidos).

## 8. Suite

Por orden de Cristian no se corrió la suite completa: se detuvo al 41 %. Hasta ahí, los únicos fallos eran los 3 desactualizados ya corregidos en c243153e. Pruebas focalizadas sobre abad2554:

- 518 en verde (antes de a761ff1b, 1 fallo: la lista de migración ya corregida). Archivos: `test_m2_rec_esterilizacion`, `test_t28_a14_esterilizacion`, `test_t28_a14_m3_brecha`, `test_ajuste_7nov_liquidos`, `test_esterilizacion_fase`, `test_calentamiento_fase`, `test_t12_c01/c03/c05/c07/v12`, `test_t16_s1/s2/s2_plausibilidad/s3/s3_protocolo_vapor`, `test_q1_r1p3_rango_calentamiento`, `test_ciclo_chaqueta`, `test_c1d_chaqueta_absoluta`, `test_sin_temp_chaqueta`, `test_precalentamiento_fase`, `test_t10_endurecimiento`, `test_s2b_revision_correcciones`.
- 266 en verde: `test_q1_r1p3_rango_calentamiento`, `test_protocolo_fallo_modo_descompresion`, `test_protocolo_fallo_reintento`, `test_t28_a12_prevacio`, `test_t32_*` (4) y `test_vaciado_chaqueta`.

## 9. Documentación

- `CLAUDE.md`: viñeta «Exención de M2 bajo la banda (M2-REC-01)» en «Control de vapor por chaqueta», junto a A14.
- `docs/riesgos/registro_riesgos.md`: HAZ-M2-REC-01.
- `docs/riesgos/matriz_trazabilidad.md`: REQ-86.
- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`: bloque M2-REC (M2-REC-01).
