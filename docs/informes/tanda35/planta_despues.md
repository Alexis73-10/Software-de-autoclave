# Tanda 35: planta antes y después de CRI

Fecha: 9-nov-2026. Rama `tanda35`, commit `536f0b56` (CRI-01..04). Referencia: alpha.26 (`base_planta.md`, commit `edc30ec3`).
Especificación: `docs/mis_plans/planeacion_cascada_integral.md` §1.4 y §6.3. Prueba: `tests/test_cri_planta.py` (45 pruebas, todas pasan, sin `xfail`).
Escenario y supuestos: los de `base_planta.md` (planta PROVISIONAL, desde ESTERILIZACION, T carga 121,6 °C, Principal −0,6 K, desfase heredado 7 kPa, programa con los valores del equipo). En este escenario la cascada arranca sin `dp` heredado: `dp` inicial = `margen_chaqueta_est` 20.

## 16 combinaciones, antes (alpha.26) y después (CRI)

P mín con CIC-04 = 203,0 kPa. «dp fin» es el `dp` de la cascada en el último tick de ESTERILIZACION (el script no lo da; se leyó de `estado.cascada_chaqueta`). En la alpha.26 no hay `dp`.

| # | Paso | Pérdida | Llenado | Resultado alpha.26 | Resultado CRI | P mín antes → después | Aisl. antes → después | Chq máx antes → después | dp fin (máx) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0,100 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 209,9 → 211,7 | 0 → 0 | 217,6 → 223,8 | 6,1 (20,0) |
| 2 | 0,100 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 209,5 → 211,7 | 0 → 0 | 216,4 → 219,8 | 6,3 (20,2) |
| 3 | 0,100 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 209,4 → 211,6 | 0 → 0 | 223,2 → 227,6 | 10,1 (20,2) |
| 4 | 0,100 | 0,8 | 1,5 | CIC-04 (T baja) 142 s | CIC-04 (T baja) 235 s | 205,8 → 206,0 | 0 → 0 | 215,7 → 217,8 | 138,0 |
| 5 | 0,030 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 209,3 → 211,2 | 0 → 0 | 237,9 → 234,4 | 18,6 (21,1) |
| 6 | 0,030 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 207,7 → 209,4 | 0 → 0 | 233,1 → 236,9 | 19,0 (29,9) |
| 7 | 0,030 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 207,3 → 208,0 | 0 → 0 | 256,8 → 250,5 | 32,0 (37,5) |
| 8 | 0,030 | 0,8 | 1,5 | CIC-04 (P baja) 23 s | CIC-04 (P baja) 28 s | 202,0 → 202,5 | 0 → 0 | 225,9 → 228,7 | 46,7 |
| 9 | 0,015 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 208,2 → **207,9** | 0 → 0 | 268,9 → 259,3 | 36,5 (46,1) |
| 10 | 0,015 | 0,4 | 1,5 | COMPLETADO | COMPLETADO | 204,7 → 206,2 | 0 → 0 | 256,7 → 260,9 | 37,0 (65,6) |
| 11 | 0,015 | 0,8 | 4,0 | COMPLETADO | COMPLETADO | 203,8 → 204,2 | 0 → 0 | 305,5 → 289,9 | 63,3 (72,3) |
| 12 | 0,015 | 0,8 | 1,5 | CIC-04 (P baja) 18 s | CIC-04 (P baja) 18 s | 200,5 → 200,7 | 0 → 0 | 228,2 → 231,6 | 36,9 |
| 13 | 0,008 | 0,4 | 4,0 | COMPLETADO | COMPLETADO | 206,2 → **205,4** | 0 → 0 | 322,6 → 298,3 | 67,8 (80,6) |
| 14 | 0,008 | 0,4 | 1,5 | CIC-04 (P baja) 29 s | CIC-04 (P baja) 34 s | 202,0 → 202,3 | 0 → 0 | 240,5 → 248,6 | 49,4 |
| 15 | 0,008 | 0,8 | 4,0 | CIC-04 (P baja) 18 s | CIC-04 (P baja) 18 s | 200,8 → 201,0 | 0 → 0 | 264,0 → 270,1 | 36,8 |
| 16 | 0,008 | 0,8 | 1,5 | CIC-04 (P baja) 16 s | CIC-04 (P baja) 17 s | 199,5 → 199,6 | 0 → 0 | 229,7 → 233,4 | 36,1 |

Fallan 6 de 16 antes y 6 de 16 después, los mismos casos. CRI no rescata ninguno; los fallos llegan algo más tarde y con P mín algo más alta.
En los casos 9 y 13 la P mín de cámara baja 0,3 y 0,8 kPa con CRI (siguen con 4,9 y 2,4 kPa sobre CIC-04 y completan). En los demás casos que completan, la P mín sube entre 0,4 y 2,2 kPa.

## Criterios de liberación (§6.3)

| Criterio | Resultado |
|---|---|
| Todo caso que completaba con la alpha.26 sigue completando | **Cumple** (los 10) |
| Ningún caso nuevo con aislamientos VCH-AIS | **Cumple** (0 en los 16, antes y después) |
| 134 °C sin CIC-16 | **Cumple**: ciclo completo 134 °C con caudal A14, abierto y restrictivo (k 1,00): ningún CIC-16, ≤ 1 aislamiento; los que llegan a ESTERILIZACION completan (`test_134_sin_cic16`; el restrictivo sigue con su timeout de CALENTAMIENTO, excluido desde CAS-04) |
| Sin `xfail` que oculte un caso | **Cumple**: cada caso tiene su resultado fijado en `ESPERADO_CRI` |

## Casos que siguen fallando: límite físico

Pérdida total de cámara ≈ pérdida fija + venteo del escape lento (0,001 × (P − P_atm) ≈ 0,13 kPa/s a 203 kPa con P_atm 75). Capacidad estacionaria: caudal máximo chaqueta → cámara que la chaqueta puede sostener con la cámara en 203 kPa (llenado con la rampa de la planta hacia 350 kPa = 1,5 × caudal + 0,15 de pérdida de chaqueta). Cota de lazo abierto: `vapor_chaqueta`, `vapor_camara` y escape lento abiertos desde el primer instante (lo máximo que puede dar cualquier control), 900 s (`test_casos_que_fallan_son_limite_fisico`).

| # | Paso | Pérdida total (kPa/s) | Capacidad estacionaria (kPa/s) | Lazo abierto: P mín (instante) / Principal mín | Tipo de límite |
|---|---|---|---|---|---|
| 4 | 0,100 | 0,93 | 0,90 | 200,1 kPa (900 s) / 120,06 °C | pérdida > capacidad |
| 8 | 0,030 | 0,93 | 0,90 | 197,1 kPa (900 s) / 119,54 °C | pérdida > capacidad |
| 12 | 0,015 | 0,93 | 0,90 | 192,6 kPa (86 s) / 118,78 °C | pérdida > capacidad |
| 14 | 0,008 | 0,53 | 0,90 | 201,2 kPa (52 s) / 120,77 °C | transitorio: la chaqueta debe subir a ≈269 kPa a ≤ 1,5 kPa/s y la cámara tiene ≈9 kPa de margen |
| 15 | 0,008 | 0,93 | 1,07 | 199,9 kPa (30 s) / 120,82 °C | transitorio: chaqueta a ≈319 kPa |
| 16 | 0,008 | 0,93 | 0,90 | 179,9 kPa (128 s) / 117,40 °C | pérdida > capacidad |

En los 6, ni con todo abierto desde el inicio la cámara se sostiene sobre CIC-04 (203,0) o la Principal sobre 120,9 °C: ningún control lo resuelve con esta planta (CRI-H1). La planta es provisional; el banco debe medir llenado de chaqueta y caída de cámara (CRI-H1).

## Ciclos completos

`python -m pytest tests/test_t33_cas04_planta.py tests/test_pam_planta.py`: **65 passed, 12 xfailed** (alpha.26: 64 passed, 13 xfailed). Sin XPASS ni fallos. El cambio es `test_pam_planta.py::test_desfase_de_sonda_0_6_k_llega_a_esterilizar[liquidos|restrictivo|chaqueta]`, que pasa a cumplir con CRI (el implementador lo sacó de `_NO_CUMPLE`). Los 11 xfail de CAS-04 y el de Instrumental 121 restrictivo chaqueta siguen igual (timeout de CALENTAMIENTO por A14-M2 o k = 1,07, fuera de alcance de CRI).

## Herencia de dp CALENTAMIENTO → ESTERILIZACION (observación del implementador)

- `planta_vapor.simular` resetea las fases solo al inicio, así que en los ciclos completos de `test_t33_cas04_planta.py` y `test_pam_planta.py` ESTERILIZACION **no** hereda el `dp` (parte de `margen_chaqueta_est`). En producción `CicloState` llama `siguiente.reset()` al avanzar de fase (`states/ciclo.py:1424`) y la herencia ocurre. `test_herencia_dp_en_ciclo_completo` lo reproduce con el reset en la transición.
- Sí pasa en la planta: con Líquidos abierto CALENTAMIENTO publica `dp` ≈ 4,0 kPa (cerca de `DP_MIN_KPA` 3, por la bajada a saturación); restrictivo 8,2–8,4; 134 abierto 7,5. Con la herencia los tres ciclos completan sin aislamientos (Líquidos abierto P mín 210,6 en lugar de 210,9).
- **Hallazgo (sensibilidad, fuera del escenario de §6.3):** en el escenario de §1.4 con `dp` heredado de 4 kPa en lugar de 20, dos casos que completaban con la alpha.26 fallan: caso 10 (0,015 / 0,4 / 1,5) CIC-04 por T baja y caso 11 (0,015 / 0,8 / 4,0) CIC-04 por P baja (P mín 201,9). Con `dp` heredado 3 falla el 11 y completa el 10 (203,8). Causa probable: la integral (`KI_CRI` 0,15) tarda en llevar la consigna de banda desde `P_sp` + 4 al `dp` que pide la pérdida (36–63 kPa en esos casos), mientras la cámara cae; la recarga llega tarde como en la alpha.26. En los ciclos completos simulados que llegan a ESTERILIZACION la herencia corresponde a la necesidad (p. ej. 17,0 kPa con 0,015 / 0,4 / 4,0) y todos completan; los de llenado 1,5 o paso 0,008 no llegan a ESTERILIZACION (timeout de CALENTAMIENTO, sin referencia alpha.26). Queda fijado en `test_sensibilidad_dp_heredado_4`. Decisión para Cristian/director: si conviene acotar por abajo el `dp` heredado (p. ej. `max(heredado, margen_chaqueta_est)`).

## Después de la corrección del revisor

Fecha: 9-nov-2026, rama `tanda35` sobre `275d3191`, sin commit. Correcciones de la revisión de seguridad:

- **ALTA-1 (antiembalamiento por integración condicional):** el nivel se decide antes de integrar; en «baja» (consigna saturada en `tope_baja`) no se integra error positivo; con VCH-AIS aislado o `inhibir_vapor_chaqueta` (`solo_bajar`) solo se integra error negativo (`dp` puede bajar, nunca subir); sin lectura de cámara/chaqueta, sin lectura del Principal en ESTERILIZACION (`congelar`) o con parámetros inválidos sigue congelada del todo. En «alta» sin cambio.
- **MEDIA-2 (herencia):** ESTERILIZACION parte de `max(dp heredado, margen_chaqueta_est)`, acotado a [`DP_MIN_KPA`, `tope_baja` − `P_sp`].

`python tests/banco/cri_barrido_planta.py` (el escenario parte sin herencia, `dp` inicial 20, así que MEDIA-2 no actúa aquí); «dp fin (máx)» leído de la cascada con un script de apoyo fuera del repositorio.

| # | Paso | Pérdida | Llenado | Resultado | Cambio vs CRI | P mín CRI → corregido | Aisl. | Chq máx CRI → corregido | dp fin (máx) CRI → corregido |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0,100 | 0,4 | 4,0 | COMPLETADO | igual | 211,7 → 211,7 | 0 | 223,8 → 223,8 | 6,1 (20,0) → 6,1 (20,0) |
| 2 | 0,100 | 0,4 | 1,5 | COMPLETADO | igual | 211,7 → 211,7 | 0 | 219,8 → 219,8 | 6,3 (20,2) → 6,3 (20,2) |
| 3 | 0,100 | 0,8 | 4,0 | COMPLETADO | igual | 211,6 → 211,6 | 0 | 227,6 → 227,6 | 10,1 (20,2) → 10,1 (20,2) |
| 4 | 0,100 | 0,8 | 1,5 | CIC-04 (T baja) 235 s | igual | 206,0 → 206,0 | 0 | 217,8 → 217,8 | 138,0 → 133,5 (133,5) |
| 5 | 0,030 | 0,4 | 4,0 | COMPLETADO | igual | 211,2 → 211,2 | 0 | 234,4 → 234,4 | 18,6 (21,1) → 18,6 (21,1) |
| 6 | 0,030 | 0,4 | 1,5 | COMPLETADO | igual | 209,4 → 209,4 | 0 | 236,9 → 236,9 | 19,0 (29,9) → 19,0 (29,9) |
| 7 | 0,030 | 0,8 | 4,0 | COMPLETADO | igual | 208,0 → 208,0 | 0 | 250,5 → 250,5 | 32,0 (37,5) → 32,0 (37,5) |
| 8 | 0,030 | 0,8 | 1,5 | CIC-04 (P baja) 28 s | igual | 202,5 → 202,5 | 0 | 228,7 → 228,7 | 46,7 → 24,0 (24,0) |
| 9 | 0,015 | 0,4 | 4,0 | COMPLETADO | igual | 207,9 → 207,9 | 0 | 259,3 → 259,3 | 36,5 (46,1) → 36,5 (46,1) |
| 10 | 0,015 | 0,4 | 1,5 | COMPLETADO | igual | 206,2 → 206,2 | 0 | 260,9 → 260,9 | 37,0 (65,6) → 37,0 (55,6) |
| 11 | 0,015 | 0,8 | 4,0 | COMPLETADO | igual | 204,2 → 204,2 | 0 | 289,9 → 289,9 | 63,3 (72,3) → 63,3 (75,6) |
| 12 | 0,015 | 0,8 | 1,5 | CIC-04 (P baja) 18 s | igual | 200,7 → 200,7 | 0 | 231,6 → 231,6 | 36,9 → 22,8 (22,8) |
| 13 | 0,008 | 0,4 | 4,0 | COMPLETADO | igual | 205,4 → 205,4 | 0 | 298,3 → 298,4 | 67,8 (80,6) → 67,9 (85,2) |
| 14 | 0,008 | 0,4 | 1,5 | CIC-04 (P baja) 34 s | igual | 202,3 → 202,3 | 0 | 248,6 → 248,6 | 49,4 → 26,0 (26,0) |
| 15 | 0,008 | 0,8 | 4,0 | CIC-04 (P baja) 18 s | igual | 201,0 → 201,0 | 0 | 270,1 → 270,1 | 36,8 → 22,9 (22,9) |
| 16 | 0,008 | 0,8 | 1,5 | CIC-04 (P baja) 17 s | igual | 199,6 → 199,6 | 0 | 233,4 → 233,4 | 36,1 → 22,6 (22,6) |

- Ningún caso cambia de resultado; `ESPERADO_CRI` no se modifica. 0 aislamientos en los 16. Fallan los mismos 6 (límite físico).
- El `dp` ya no se infla en «baja»: en los fallos tempranos (8, 12, 14–16) queda en 22,6–26,0 (antes 36–49). Los máximos de 10, 11 y 13 cambian unos kPa porque se acumulan en «banda» (integración permitida) y el recorrido previo es otro.
- **Caso 4: el `dp` sigue llegando a 133,5 kPa.** La cámara queda en «banda» (sobre `p_baja`, bajo `P_sp`) mientras la chaqueta no alcanza la consigna (límite de la planta) y la Principal cae a CIC-04 por T baja: la integración condicional de ALTA-1 no cubre un embalamiento en «banda» con la chaqueta saturada físicamente. No cambia el resultado (falla igual, sin aislamientos) y queda para el informe.
- **Sensibilidad con `dp` heredado 4 (MEDIA-2):** con `max(4, 20)` = 20 los casos 10 y 11 vuelven a completar; `ESPERADO_DP_HEREDADO_4` = `ESPERADO_CRI` (`test_sensibilidad_dp_heredado_4`, 16 pasan).
- **134 °C sin CIC-16:** `test_134_sin_cic16` (caudal A14, abierto y restrictivo) pasa: ningún CIC-16, ≤ 1 aislamiento.
- Pruebas dedicadas (CRI, T33, PAM, esterilización y calentamiento): 723 passed, 12 xfailed (los mismos 12 de antes, sin XPASS).
