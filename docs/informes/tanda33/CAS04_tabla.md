# CAS-04: planta simulada, alpha.24 contra tanda 33 (7-nov-2026)

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

- Todos los escenarios terminan en COMPLETADO.
- Presión mínima de cámara en ESTERILIZACION ≥ Psat(T_est) − brecha_error_presion + 1,5:
  - 121 °C: 205,04 − 2 + 1,5 = **204,5 kPa**
  - 134 °C: 304,20 − 2 + 1,5 = **303,7 kPa**
- Aislamientos VCH-AIS ≤ 1 por ciclo (CALENTAMIENTO + ESTERILIZACION).
- Chaqueta real máxima < 375 kPa (`presion_max_chaqueta_control`).
- Sobreimpulso a 134 °C ≤ 0,59 + 0,2 = 0,79 K.
- «Conm./min» cuenta los cambios de `vapor_chaqueta` (ON→OFF y OFF→ON) por minuto de ESTERILIZACION. Es informativo.

## Veredicto (tanda 33, con HISTERESIS_KPA 3 y MARGEN_TECHO_KPA 2, valores sin cambio)

| Caudal | k = 1,00 | k = 1,07 (lee alto) | k = 0,95 (lee bajo) |
|---|---|---|---|
| **abierto (real)** | **9/9 cumple** | 0/9: Líquidos FALLO (temperatura baja con add_est 15, CIC-04 con 11), sin aislamientos; 134 °C timeout de CAL | 9/9 cumple |
| restrictivo | **0/9**: Líquidos CIC-04 (8/8), 134 °C timeout de CAL | 0/9 (timeout de CAL) | 0/9 (CIC-04; 134 °C timeout de CAL) |
| alpha.24, mismo cuadro | abierto 9/9 · restrictivo 8/9 | abierto 8/9 · restrictivo 0/9 | abierto **4/9** (2–6 aislamientos, un **CIC-16**; 134 °C 0,99 K y 1 aislamiento) · restrictivo 8/9 |

- **Caudal abierto (el real), k = 1,00: CUMPLE.** Todos los escenarios terminan en COMPLETADO. Presión mínima 206,5–207,4 kPa a 121 °C y 306,2 a 134 °C. 0 aislamientos. Chaqueta máxima 247,8 kPa. Sobreimpulso a 134 °C de 0,49 K (alpha.24: 0,69). Con la planta de A14, 0,35 K (alpha.24: 0,59) y 16,8 conmutaciones/min (alpha.24: 33,3).
- **Caudal abierto, k = 0,95: cumple.** Mejora a la alpha.24, que llegaba a CIC-16.
- **Caudal abierto, k = 1,07: NO cumple. Es una dependencia de calibración (HAZ-CAS-02).** En Líquidos, la cascada cree que la chaqueta está en el tope (218 kPa leídos ≈ 208,6 reales), que no basta para sostener la cámara sobre P_sp − 2. El ciclo falla por presión o temperatura baja, sin aislamientos y con la chaqueta lejos de D-CHQ (falla segura). La alpha.24 completaba esos 8 escenarios gracias a la exención M2-REC, con mínimos de 204,9 kPa, al borde del criterio.
- **Caudal restrictivo, k = 1,00: NO cumple, y ningún ajuste permitido lo corrige** (ver intentos). Es estructural: con 0,015/s, sostener la cámara contra la pérdida de 0,35 kPa/s exige la chaqueta unos 23 kPa sobre la cámara (≈ 230 kPa para 207), y el tope de la cascada es techo − 2 = 218 (MARGEN 1: 219). La cámara cae a CIC-04 sin aislamientos (falla segura). Es el hallazgo previo de CAS-02, ahora en ciclo completo. La alpha.24 completaba porque la exención dejaba subir la chaqueta hasta 287 kPa.
- **134 °C con caudal restrictivo (todos los k) y con caudal abierto k = 1,07: timeout de CALENTAMIENTO, igual en la alpha.24.** La causa es la rampa con su corte A14-M2, que CAS no cambia (la cámara se estanca en 296 kPa con el restrictivo, y con k = 1,07 en 304 kPa sin entrar a la banda). No es un efecto de la cascada.
- Aparte del criterio: a 121 °C, con `brecha_segura_temperatura` 0,3 y caudal abierto, el sobreimpulso es de 0,76–0,77 K en las dos versiones. No lo introduce CAS.

## Intentos de ajuste (k = 1,00; 9 escenarios por caudal)

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

## Tabla completa (alpha.24 / tanda 33)

| Escenario | Caudal | k | Resultado a24 / t33 | P mín ester a24 / t33 (req) | Aisl. a24 / t33 | Chq máx a24 / t33 | Sobreimp. K a24 / t33 | Conm./min a24 / t33 | Cumple a24 / t33 |
|---|---|---|---|---|---|---|---|---|---|
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 205,2 / 201,8 (204,5) | 0 / 0 | 287,3 / 244,5 | 0,31 / 0,04 | 8,9 / 0,0 | sí / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 204,8 / 201,8 (204,5) | 0 / 0 | 250,3 / 244,5 | 0,05 / 0,04 | 12,5 / 0,0 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 205,1 / 201,8 (204,5) | 0 / 0 | 287,0 / 249,5 | 0,34 / 0,12 | 12,2 / 10,9 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 204,8 / 201,8 (204,5) | 0 / 0 | 250,3 / 249,5 | 0,12 / 0,12 | 9,2 / 10,9 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 205,1 / 201,7 (204,5) | 0 / 0 | 287,1 / 244,5 | 0,31 / 0,04 | 8,9 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 204,9 / 201,7 (204,5) | 0 / 0 | 250,4 / 244,5 | 0,05 / 0,04 | 10,4 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 205,1 / 201,6 (204,5) | 0 / 0 | 287,1 / 249,5 | 0,32 / 0,12 | 8,9 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 1,00 | COMPLETADO / FALLO CIC-04 | 204,8 / 201,6 (204,5) | 0 / 0 | 250,1 / 249,5 | 0,13 / 0,12 | 9,1 / 0,0 | sí / NO |
| 134 sólidos | restrictivo | 1,00 | FALLO timeout CAL / FALLO timeout CAL | — / — (303,7) | 0 / 0 | 328,0 / 328,0 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 235,0 / 235,0 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 235,0 / 235,0 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 238,5 / 238,5 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 238,5 / 238,5 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 233,8 / 233,8 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 233,8 / 233,8 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 238,5 / 238,5 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (204,5) | 0 / 0 | 238,5 / 238,5 | — / — | — / — | NO / NO |
| 134 sólidos | restrictivo | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (303,7) | 0 / 0 | 328,0 / 328,0 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 206,3 / 202,5 (204,5) | 0 / 0 | 269,5 / 253,1 | 0,32 / 0,18 | 9,7 / 12,4 | sí / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 204,9 / 202,5 (204,5) | 0 / 0 | 253,1 / 253,1 | 0,19 / 0,18 | 9,1 / 12,4 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 206,1 / 202,4 (204,5) | 0 / 0 | 273,3 / 258,4 | 0,36 / 0,27 | 8,6 / 12,0 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 204,9 / 202,4 (204,5) | 0 / 0 | 258,4 / 258,4 | 0,27 / 0,27 | 9,5 / 12,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 206,3 / 202,1 (204,5) | 0 / 0 | 269,4 / 253,1 | 0,31 / 0,17 | 11,1 / 15,7 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 204,9 / 202,1 (204,5) | 0 / 0 | 253,1 / 253,1 | 0,17 / 0,17 | 9,1 / 15,7 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 206,0 / 202,2 (204,5) | 0 / 0 | 273,2 / 258,4 | 0,36 / 0,28 | 9,1 / 10,4 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | restrictivo | 0,95 | COMPLETADO / FALLO CIC-04 | 204,9 / 202,2 (204,5) | 0 / 0 | 258,4 / 258,4 | 0,28 / 0,28 | 9,2 / 10,4 | sí / NO |
| 134 sólidos | restrictivo | 0,95 | FALLO timeout CAL / FALLO timeout CAL | — / — (303,7) | 0 / 0 | 337,2 / 337,2 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO | 208,3 / 207,4 (204,5) | 0 / 0 | 242,4 / 242,4 | 0,78 / 0,76 | 17,7 / 17,7 | sí / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO | 207,9 / 207,4 (204,5) | 0 / 0 | 242,4 / 242,4 | 0,48 / 0,48 | 17,4 / 17,5 | sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO | 208,5 / 206,7 (204,5) | 0 / 0 | 247,4 / 247,4 | 0,78 / 0,77 | 17,7 / 17,7 | sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO | 207,9 / 206,7 (204,5) | 0 / 0 | 247,4 / 247,4 | 0,49 / 0,49 | 17,5 / 17,5 | sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO | 208,5 / 206,7 (204,5) | 0 / 0 | 241,0 / 241,0 | 0,78 / 0,55 | 17,8 / 17,7 | sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO | 207,9 / 206,7 (204,5) | 0 / 0 | 241,0 / 241,0 | 0,48 / 0,48 | 17,4 / 17,6 | sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 1,00 | COMPLETADO / COMPLETADO | 208,6 / 206,5 (204,5) | 0 / 0 | 247,8 / 247,8 | 0,78 / 0,56 | 17,5 / 17,6 | sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 1,00 | COMPLETADO / COMPLETADO | 207,9 / 206,5 (204,5) | 0 / 0 | 247,8 / 247,8 | 0,49 / 0,49 | 17,5 / 17,6 | sí / sí |
| 134 sólidos | abierto | 1,00 | COMPLETADO / COMPLETADO | 306,2 / 306,2 (303,7) | 0 / 0 | 328,0 / 328,0 | 0,69 / 0,49 | 32,2 / 31,6 | sí / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO temp. baja | 206,8 / 203,2 (204,5) | 0 / 0 | 235,0 / 235,0 | 0,33 / 0,31 | 17,3 / 17,1 | sí / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO temp. baja | 204,9 / 203,2 (204,5) | 0 / 0 | 235,0 / 235,0 | 0,33 / 0,31 | 17,1 / 17,1 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO temp. baja | 206,8 / 203,2 (204,5) | 0 / 0 | 237,9 / 237,9 | 0,46 / 0,44 | 17,3 / 17,0 | sí / NO |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO temp. baja | 204,9 / 203,2 (204,5) | 0 / 0 | 237,9 / 237,9 | 0,45 / 0,44 | 17,1 / 17,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 | 206,8 / 201,3 (204,5) | 0 / 0 | 233,3 / 233,3 | 0,33 / 0,29 | 17,3 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 | 204,9 / 201,3 (204,5) | 0 / 0 | 233,3 / 233,3 | 0,31 / 0,29 | 17,1 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 | 206,8 / 201,3 (204,5) | 0 / 0 | 237,9 / 237,9 | 0,42 / 0,41 | 17,3 / 0,0 | sí / NO |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 1,07 | COMPLETADO / FALLO CIC-04 | 204,9 / 201,3 (204,5) | 0 / 0 | 237,9 / 237,9 | 0,42 / 0,41 | 17,1 / 0,0 | sí / NO |
| 134 sólidos | abierto | 1,07 | FALLO timeout CAL / FALLO timeout CAL | — / — (303,7) | 0 / 0 | 328,0 / 328,0 | — / — | — / — | NO / NO |
| Líquidos 121 add_est 15 add_liq 15 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO | 208,3 / 207,4 (204,5) | 3 / 0 | 242,4 / 242,4 | 0,79 / 0,76 | 17,7 / 17,5 | NO / sí |
| Líquidos 121 add_est 15 add_liq 15 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO | 207,9 / 207,4 (204,5) | 0 / 0 | 242,4 / 242,4 | 0,49 / 0,48 | 17,1 / 17,4 | sí / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO | 208,5 / 206,7 (204,5) | 2 / 0 | 250,5 / 250,5 | 0,79 / 0,77 | 17,5 / 17,4 | NO / sí |
| Líquidos 121 add_est 15 add_liq 20 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO | 207,9 / 206,7 (204,5) | 0 / 0 | 250,5 / 250,5 | 0,49 / 0,49 | 17,5 / 17,1 | sí / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0,3 | abierto | 0,95 | FALLO CIC-16 / COMPLETADO | 208,5 / 206,7 (204,5) | 6 / 0 | 244,7 / 244,7 | 0,51 / 0,76 | 21,9 / 17,7 | NO / sí |
| Líquidos 121 add_est 11 add_liq 15 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO | 207,9 / 206,7 (204,5) | 0 / 0 | 244,7 / 244,7 | 0,48 / 0,48 | 17,4 / 17,4 | sí / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0,3 | abierto | 0,95 | COMPLETADO / COMPLETADO | 208,6 / 206,5 (204,5) | 5 / 0 | 247,8 / 247,8 | 0,78 / 0,77 | 17,5 / 17,7 | NO / sí |
| Líquidos 121 add_est 11 add_liq 20 brecha 0 | abierto | 0,95 | COMPLETADO / COMPLETADO | 207,9 / 206,5 (204,5) | 0 / 0 | 247,8 / 247,8 | 0,49 / 0,49 | 17,5 / 17,4 | sí / sí |
| 134 sólidos | abierto | 0,95 | COMPLETADO / COMPLETADO | 306,2 / 306,2 (303,7) | 1 / 0 | 331,1 / 328,0 | 0,99 / 0,49 | 28,2 / 29,4 | NO / sí |
| 134 sólidos (planta A14, paso 0,06) | defecto_A14 | 1,00 | COMPLETADO / COMPLETADO | 306,3 / 306,1 (303,7) | 0 / 0 | 328,0 / 328,0 | 0,59 / 0,35 | 33,3 / 16,8 | sí / sí |
