# CAS-04: planta simulada, alpha.24 contra tanda 33 (7-nov-2026; ajuste del tope de la baja, 8-nov-2026)

Planta simulada con valores **PROVISIONALES** (`tests/helpers/planta_vapor.py`): no reproduce la dinámica real del equipo. Sirve para comparar los dos controles con la misma planta. Prueba: `tests/test_t33_cas04_planta.py`. Tabla: `python tests/banco/t33_planta_tabla.py` (alpha.24: el mismo script con `--raiz C:\Users\tecni\Documents\autoclave_base --modulo tests.helpers.planta_vapor_t33`, ejecutado con el directorio de trabajo en ese árbol; `planta_vapor_t33.py` es una copia sin cambios de la planta extendida y es el único archivo agregado a ese árbol).

## Planta y escenarios

- Ciclo completo CALENTAMIENTO → ESTERILIZACION en modo chaqueta, con las fases reales de cada versión.
- **Error de ganancia del transmisor de chaqueta**: lectura = p_atm + (real − p_atm) · k, con p_atm = 75 kPa (`presion_admosferica` del equipo). k = 1,00 (exacto), 1,07 (lee alto: es la firma de los ciclos 21 y 23 de SN260001) y 0,95 (lee bajo). El control y el D-CHQ ven la lectura. La columna «Chq máx» es la presión **real**.
- **Caudal chaqueta → cámara**:
  - «abierto», 0,1/s: la válvula de asiento sin otra restricción, cámara y chaqueta casi un solo volumen. **Es la configuración real que confirmó Cristian.**
  - «restrictivo», 0,015/s: el paso del escenario M2-REC.
  - «defecto_A14», 0,06/s: la planta de A14, solo para la regresión del sobreimpulso a 134 °C. Su resultado en la alpha.24 es 0,59 K, igual que en A14, lo que valida el arnés.
- **Líquidos 121 °C**: el programa de fábrica con `presion_add_esterilizacion` 15 y 11, `presion_add_liquido_calentamiento` 15 y 20, y `brecha_segura_temperatura` 0,3 y 0,0. La carga tiene inercia alta y la cámara una pérdida fija de 0,35 kPa/s (son los ajustes del escenario M2-REC). La chaqueta arranca en la consigna C-05 del programa, que es donde la deja PRECALENTAMIENTO.
- **134 °C sólidos**: el programa de fábrica con la planta de A14 (la chaqueta arranca en 328 kPa).

## Criterio

Umbrales (sin cambio):

- El escenario termina en COMPLETADO.
- Presión mínima de cámara en ESTERILIZACION ≥ Psat(T_est) − brecha_error_presion + 1,5:
  - 121 °C: 205,04 − 2 + 1,5 = **204,5 kPa**
  - 134 °C: 304,20 − 2 + 1,5 = **303,7 kPa**
- Aislamientos VCH-AIS ≤ 1 por ciclo (CALENTAMIENTO + ESTERILIZACION).
- Chaqueta real máxima < 375 kPa (`presion_max_chaqueta_control`).
- Sobreimpulso a 134 °C ≤ 0,59 + 0,2 = 0,79 K.
- «Conm./min» cuenta los cambios de `vapor_chaqueta` (ON→OFF y OFF→ON) por minuto de ESTERILIZACION. Es informativo.

Criterio de liberación (Cristian, 8-nov): **k = 1,00 con caudal abierto Y con caudal restrictivo**, con los umbrales de arriba.

- **Excluido:** el timeout de CALENTAMIENTO a 134 °C (caudal restrictivo con todos los k y abierto con k = 1,07). La alpha.24 también lo da. Viene de la rampa con su corte A14-M2, y CAS no toca la rampa.
- **Informativos:** k = 1,07 y k = 0,95. Se reportan comparados con la alpha.24 y con la versión anterior de la tanda 33.
- **Regla:** si el abierto con k = 1,00 deja de cumplir, se revierte el ajuste y se libera con el diseño anterior. Si solo falla el restrictivo, se libera con el ajuste y el restrictivo queda como caracterización. No se vuelve a bloquear.

## Ajuste del 8-nov (CAS-01)

El nivel «baja» usa una consigna propia: `tope_baja = min(presion_max_chaqueta_control − 10, presion_suministro_vapor)`. Con los defectos del equipo vale min(365, 350) = **350 kPa**. Antes era `min(techo − 2, …)`, unos 218 kPa a 121 °C. Es `DECISIÓN SIN CONFIRMAR` hasta el banco.

No cambian los niveles «banda» (`min(P_sp + margen_est, techo − 2)`) ni «alta» (OFF), ni `HISTERESIS_KPA` 3, ni `MARGEN_TECHO_KPA` 2. VCH-AIS, D-CHQ y el corte duro de CICLO siguen prevaleciendo.

## Veredicto (8-nov, con el ajuste)

Escenarios que cumplen. Cada celda dice alpha.24 / tanda 33 anterior / tanda 33 con el ajuste.

| Caudal | k = 1,00 | k = 1,07 (informativo) | k = 0,95 (informativo) |
|---|---|---|---|
| **abierto (real)** | 9/9 / 9/9 / **9/9** | 8/9 / 0/9 / 0/9 | 4/9 / 9/9 / 9/9 |
| **restrictivo 0,015/s** | 8/9 / 0/9 / **4/9** (4/8 sin el 134 °C excluido) | 0/9 / 0/9 / 0/9 | 8/9 / 0/9 / 0/9 |

- **Caudal abierto, k = 1,00: CUMPLE 9/9, igual que antes del ajuste.** Mismas presiones mínimas: 206,5–207,4 kPa a 121 °C y 306,2 a 134 °C. Cero aislamientos. Chaqueta máxima 247,8 kPa. Sobreimpulso a 134 °C de 0,49 K. Con la planta de A14: 0,35 K y 15,7 conmutaciones por minuto. **No se revierte.**
- **Caudal restrictivo, k = 1,00: los 8 escenarios de Líquidos ahora COMPLETAN, sin CIC-04.** Antes del ajuste los 8 daban CIC-04.
  - Cumplen los 4 con `presion_add_liquido_calentamiento` 15: mínimo 204,8–205,2 kPa.
  - Los 4 con add_liq 20 quedan en 204,2–204,3 kPa, 0,2–0,3 kPa bajo 204,5. Siguen sobre el umbral de falla (203,0) y uno tiene 1 aislamiento (≤ 1).
  - La chaqueta real llega a 297,7 kPa como máximo, frente a 287 kPa en la alpha.24, lejos de 375.
  - Por la regla 3 **se libera con el ajuste** y estos 4 quedan como **caracterización**. La alpha.24 tampoco tenía margen en esos escenarios: 204,8–205,1 kPa.
  - En los 4 escenarios de add_liq 15 la tanda 33 repite exactamente la alpha.24. Con la chaqueta sobre la consigna de banda, las dos versiones dejan `vapor_chaqueta` encendida solo con la cámara bajo P_sp − 2 (la alpha.24 por la exención M2-REC, la cascada por el nivel baja).
- **Excluido:** 134 °C con caudal restrictivo (con todos los k) y abierto con k = 1,07 terminan en timeout de CALENTAMIENTO, igual que en la alpha.24 (rampa con A14-M2).
- **k = 1,07 (informativo):**
  - Abierto: los 8 de Líquidos ahora COMPLETAN. Antes daban CIC-04 o temperatura baja. El mínimo, 203,4–203,5 kPa, queda bajo 204,5 pero sobre la falla. La alpha.24 completaba con 204,9–206,8.
  - Restrictivo: timeout de CALENTAMIENTO, igual que en las otras dos versiones.
  - Sigue la dependencia de calibración HAZ-CAS-02.
- **k = 0,95 (informativo):**
  - Abierto: 9/9, sin cambio. La alpha.24 daba 4/9, con un CIC-16.
  - Restrictivo: los 8 de Líquidos ahora COMPLETAN. Antes daban CIC-04. El mínimo, 204,0–204,2 kPa, queda bajo 204,5, con 0–1 aislamientos. La alpha.24 daba 8/9.

## Intentos de ajuste del 7-nov, antes del ajuste del tope (k = 1,00; 9 escenarios por caudal; histórico)

| HISTERESIS_KPA | MARGEN_TECHO_KPA | restrictivo cumple | abierto cumple | Notas |
|---|---|---|---|---|
| 3 | 2 (actual) | 0/9 | 9/9 | mínimo restrictivo 201,6–201,8 kPa (CIC-04) |
| 2 | 2 | 0/9 | 9/9 | restrictivo 201,6–202,0 |
| 5 | 2 | 0/9 | 9/9 | 134 °C abierto 0,53 K |
| 3 | 1 | 0/9 | 9/9 | restrictivo 201,6–202,0 |
| 3 | 4 | 0/9 | 9/9 | 134 °C abierto 0,44 K |
| 2 | 1 | 0/9 | 9/9 | restrictivo 201,6–202,0 |
| 5 | 1 | 0/9 | 9/9 | 134 °C abierto 0,51 K |
| 5 | 4 | 0/9 | **5/9** | Líquidos add_est 11 abierto: mínimo 204,4 < 204,5 |

Ningún ajuste hace cumplir el caudal restrictivo con k = 1,00. Se dejan los valores actuales (3 / 2): son el mejor ajuste con el caudal real y no cambian nada con el restrictivo. Los intentos se corrieron cambiando las constantes del módulo en memoria; `cascada_chaqueta.py` queda sin cambios.

## Tabla completa (alpha.24 / tanda 33 anterior / tanda 33 con el ajuste)

La columna «tanda 33 anterior» se tomó de la versión del 7-nov de este archivo. Las columnas alpha.24 y tanda 33 se regeneraron el 8-nov.

| Escenario | Caudal | k | Resultado a24 / t33 ant. / t33 | P mín ester a24 / ant. / t33 (req) | Aisl. a24 / ant. / t33 | Chq máx a24 / ant. / t33 | Sobreimp. K a24 / ant. / t33 | Conm./min a24 / ant. / t33 | Cumple a24 / ant. / t33 |
|---|---|---|---|---|---|---|---|---|---|
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 205,2 / 201,8 / 205,2 (204,5) | 0 / 0 / 0 | 287,3 / 244,5 / 287,3 | 0,31 / 0,04 / 0,31 | 8,9 / 0,0 / 8,9 | sí / NO / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,8 / 201,8 / 204,8 (204,5) | 0 / 0 / 0 | 250,3 / 244,5 / 250,3 | 0,05 / 0,04 / 0,05 | 12,5 / 0,0 / 12,5 | sí / NO / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 205,1 / 201,8 / 204,2 (204,5) | 0 / 0 / 0 | 287,0 / 249,5 / 297,5 | 0,34 / 0,12 / 0,38 | 12,2 / 10,9 / 8,3 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,8 / 201,8 / 204,2 (204,5) | 0 / 0 / 0 | 250,3 / 249,5 / 267,4 | 0,12 / 0,12 / 0,16 | 9,2 / 10,9 / 9,3 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 205,1 / 201,7 / 205,1 (204,5) | 0 / 0 / 0 | 287,1 / 244,5 / 287,1 | 0,31 / 0,04 / 0,31 | 8,9 / 0,0 / 8,9 | sí / NO / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 201,7 / 204,9 (204,5) | 0 / 0 / 0 | 250,4 / 244,5 / 250,4 | 0,05 / 0,04 / 0,05 | 10,4 / 0,0 / 10,4 | sí / NO / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 205,1 / 201,6 / 204,3 (204,5) | 0 / 0 / 1 | 287,1 / 249,5 / 297,7 | 0,32 / 0,12 / 0,35 | 8,9 / 0,0 / 7,9 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,8 / 201,6 / 204,3 (204,5) | 0 / 0 / 0 | 250,1 / 249,5 / 267,5 | 0,13 / 0,12 / 0,16 | 9,1 / 0,0 / 9,9 | sí / NO / NO |
| 134 sólidos | restrictivo | 1,00 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (303,7) | 0 / 0 / 0 | 328,0 / 328,0 / 328,0 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 235,0 / 235,0 / 235,0 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 235,0 / 235,0 / 235,0 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 238,5 / 238,5 / 238,5 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 238,5 / 238,5 / 238,5 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 233,8 / 233,8 / 233,8 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 233,8 / 233,8 / 233,8 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 238,5 / 238,5 / 238,5 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (204,5) | 0 / 0 / 0 | 238,5 / 238,5 / 238,5 | — / — / — | — / — / — | NO / NO / NO |
| 134 sólidos | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (303,7) | 0 / 0 / 0 | 328,0 / 328,0 / 328,0 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,3 / 202,5 / 204,1 (204,5) | 0 / 0 / 0 | 269,5 / 253,1 / 296,3 | 0,32 / 0,18 / 0,42 | 9,7 / 12,4 / 8,9 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 202,5 / 204,1 (204,5) | 0 / 0 / 0 | 253,1 / 253,1 / 271,3 | 0,19 / 0,18 / 0,23 | 9,1 / 12,4 / 8,7 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,1 / 202,4 / 204,2 (204,5) | 0 / 0 / 0 | 273,3 / 258,4 / 295,1 | 0,36 / 0,27 / 0,47 | 8,6 / 12,0 / 7,9 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 202,4 / 204,2 (204,5) | 0 / 0 / 0 | 258,4 / 258,4 / 264,8 | 0,27 / 0,27 / 0,28 | 9,5 / 12,0 / 9,1 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,3 / 202,1 / 204,0 (204,5) | 0 / 0 / 1 | 269,4 / 253,1 / 296,3 | 0,31 / 0,17 / 0,36 | 11,1 / 15,7 / 9,1 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 202,1 / 204,0 (204,5) | 0 / 0 / 0 | 253,1 / 253,1 / 271,2 | 0,17 / 0,17 / 0,22 | 9,1 / 15,7 / 8,9 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,0 / 202,2 / 204,2 (204,5) | 0 / 0 / 1 | 273,2 / 258,4 / 294,9 | 0,36 / 0,28 / 0,43 | 9,1 / 10,4 / 8,5 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 202,2 / 204,2 (204,5) | 0 / 0 / 0 | 258,4 / 258,4 / 269,7 | 0,28 / 0,28 / 0,31 | 9,2 / 10,4 / 8,7 | sí / NO / NO |
| 134 sólidos | restrictivo | 0,95 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (303,7) | 0 / 0 / 0 | 337,2 / 337,2 / 337,2 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 208,3 / 207,4 / 207,4 (204,5) | 0 / 0 / 0 | 242,4 / 242,4 / 242,4 | 0,78 / 0,76 / 0,76 | 17,7 / 17,7 / 17,7 | sí / sí / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 207,4 / 207,4 (204,5) | 0 / 0 / 0 | 242,4 / 242,4 / 242,4 | 0,48 / 0,48 / 0,48 | 17,4 / 17,5 / 17,5 | sí / sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 208,5 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 247,4 / 247,4 / 247,4 | 0,78 / 0,77 / 0,77 | 17,7 / 17,7 / 17,7 | sí / sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 247,4 / 247,4 / 247,4 | 0,49 / 0,49 / 0,49 | 17,5 / 17,5 / 17,5 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 208,5 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 241,0 / 241,0 / 241,0 | 0,78 / 0,55 / 0,55 | 17,8 / 17,7 / 17,7 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 241,0 / 241,0 / 241,0 | 0,48 / 0,48 / 0,48 | 17,4 / 17,6 / 17,6 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 208,6 / 206,5 / 206,5 (204,5) | 0 / 0 / 0 | 247,8 / 247,8 / 247,8 | 0,78 / 0,56 / 0,56 | 17,5 / 17,6 / 17,4 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,5 / 206,5 (204,5) | 0 / 0 / 0 | 247,8 / 247,8 / 247,8 | 0,49 / 0,49 / 0,49 | 17,5 / 17,6 / 17,6 | sí / sí / sí |
| 134 sólidos | abierto | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 306,2 / 306,2 / 306,2 (303,7) | 0 / 0 / 0 | 328,0 / 328,0 / 328,0 | 0,69 / 0,49 / 0,49 | 32,2 / 31,6 / 29,9 | sí / sí / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO temp. baja / COMPLETADO | 206,8 / 203,2 / 203,5 (204,5) | 0 / 0 / 0 | 235,0 / 235,0 / 235,0 | 0,33 / 0,31 / 0,35 | 17,3 / 17,1 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO temp. baja / COMPLETADO | 204,9 / 203,2 / 203,5 (204,5) | 0 / 0 / 0 | 235,0 / 235,0 / 235,0 | 0,33 / 0,31 / 0,32 | 17,1 / 17,1 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO temp. baja / COMPLETADO | 206,8 / 203,2 / 203,4 (204,5) | 0 / 0 / 0 | 237,9 / 237,9 / 237,9 | 0,46 / 0,44 / 0,47 | 17,3 / 17,0 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO temp. baja / COMPLETADO | 204,9 / 203,2 / 203,4 (204,5) | 0 / 0 / 0 | 237,9 / 237,9 / 237,9 | 0,45 / 0,44 / 0,44 | 17,1 / 17,0 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,8 / 201,3 / 203,5 (204,5) | 0 / 0 / 0 | 233,3 / 233,3 / 233,3 | 0,33 / 0,29 / 0,34 | 17,3 / 0,0 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 201,3 / 203,5 (204,5) | 0 / 0 / 0 | 233,3 / 233,3 / 233,3 | 0,31 / 0,29 / 0,30 | 17,1 / 0,0 / 16,9 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 206,8 / 201,3 / 203,5 (204,5) | 0 / 0 / 0 | 237,9 / 237,9 / 237,9 | 0,42 / 0,41 / 0,44 | 17,3 / 0,0 / 17,0 | sí / NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 / COMPLETADO | 204,9 / 201,3 / 203,5 (204,5) | 0 / 0 / 0 | 237,9 / 237,9 / 237,9 | 0,42 / 0,41 / 0,41 | 17,1 / 0,0 / 17,0 | sí / NO / NO |
| 134 sólidos | abierto | 1,07 | FALLO timeout CAL / FALLO timeout CAL / FALLO timeout CAL | — / — / — (303,7) | 0 / 0 / 0 | 328,0 / 328,0 / 328,0 | — / — / — | — / — / — | NO / NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 208,3 / 207,4 / 207,4 (204,5) | 3 / 0 / 0 | 242,4 / 242,4 / 242,4 | 0,79 / 0,76 / 0,76 | 17,7 / 17,5 / 17,5 | NO / sí / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 207,4 / 207,4 (204,5) | 0 / 0 / 0 | 242,4 / 242,4 / 242,4 | 0,49 / 0,48 / 0,48 | 17,1 / 17,4 / 17,4 | sí / sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 208,5 / 206,7 / 206,7 (204,5) | 2 / 0 / 0 | 250,5 / 250,5 / 250,5 | 0,79 / 0,77 / 0,77 | 17,5 / 17,4 / 17,4 | NO / sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 250,5 / 250,5 / 250,5 | 0,49 / 0,49 / 0,49 | 17,5 / 17,1 / 17,1 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 0,95 | FALLO CIC-16 / COMPLETADO / COMPLETADO | 208,5 / 206,7 / 206,7 (204,5) | 6 / 0 / 0 | 244,7 / 244,7 / 244,7 | 0,51 / 0,76 / 0,76 | 21,9 / 17,7 / 17,7 | NO / sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,7 / 206,7 (204,5) | 0 / 0 / 0 | 244,7 / 244,7 / 244,7 | 0,48 / 0,48 / 0,48 | 17,4 / 17,4 / 17,4 | sí / sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 208,6 / 206,5 / 206,5 (204,5) | 5 / 0 / 0 | 247,8 / 247,8 / 247,8 | 0,78 / 0,77 / 0,77 | 17,5 / 17,7 / 17,7 | NO / sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 207,9 / 206,5 / 206,5 (204,5) | 0 / 0 / 0 | 247,8 / 247,8 / 247,8 | 0,49 / 0,49 / 0,49 | 17,5 / 17,4 / 17,4 | sí / sí / sí |
| 134 sólidos | abierto | 0,95 | COMPLETADO / COMPLETADO / COMPLETADO | 306,2 / 306,2 / 306,2 (303,7) | 1 / 0 / 0 | 331,1 / 328,0 / 328,0 | 0,99 / 0,49 / 0,49 | 28,2 / 29,4 / 29,4 | NO / sí / sí |
| 134 sólidos (planta A14, paso 0,06) | defecto_A14 | 1,00 | COMPLETADO / COMPLETADO / COMPLETADO | 306,3 / 306,1 / 306,1 (303,7) | 0 / 0 / 0 | 328,0 / 328,0 / 328,0 | 0,59 / 0,35 / 0,35 | 33,3 / 16,8 / 15,7 | sí / sí / sí |
