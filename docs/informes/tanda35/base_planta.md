# Tanda 35, paso 1: línea base de planta (CRI)

Fecha: 9-nov-2026. Rama `tanda35`, commit `edc30ec3` (alpha.26, sin cambios en `src/`).
Especificación: `docs/mis_plans/planeacion_cascada_integral.md` §1.4 y §6.3.
Script: `python tests/banco/cri_barrido_planta.py` (misma interfaz para la comparación tras CRI; `--motivos`, `--json`, `--t-carga`, `--pasos`, `--perdidas`, `--llenados`).

## Escenario y supuestos (planta PROVISIONAL, `tests/helpers/planta_vapor.py`)

- Desde el inicio de ESTERILIZACION (`simular(..., desde_esterilizacion=True)`), modo chaqueta.
- Cámara 212,0 kPa (vapor 211,9 + aire 0,1), chaqueta 215,0 kPa.
- Principal (`temp_camara`) 0,6 K bajo la sonda real; las demás sondas sin desfase.
- Desfase heredado de CALENTAMIENTO 7 kPa: `estado.desfase_trabajo = 7` antes del primer tick (PAM-04).
- Programa: Líquidos 121 °C de fábrica con los valores del equipo: `presion_add_esterilizacion` 11, `brecha_segura_temperatura` 0, `margen_chaqueta_est` 20 (resto de fábrica: `brecha_segura_presion` 1,5, `brecha_error_presion` 2, 15 min).
- Planta de líquidos `AJUSTES_LIQUIDOS` (CONDENSACION 0,005, CALOR 0,003, PERDIDA_TERMICA 0) con `PASO_CAMARA` ∈ {0,1; 0,03; 0,015; 0,008}, `PERDIDA_CAMARA` ∈ {0,4; 0,8} kPa/s y `LLENADO_CHAQUETA` ∈ {4; 1,5} kPa/s.
- **Supuesto propio (la especificación no lo fija):** carga y sonda real arrancan en 121,6 °C (la Principal lee 121,0 = T_est, como al enclavar t_obj).
- Arnés de `planta_vapor.simular`: D-CHQ y OFF forzado como CicloState; sin CicloState (sin SENSOR_AUSENTE, sin protocolo de fallo).
- Una falla de ESTERILIZACION con `alarma_fallo` None es CIC-04.

## Resultado: 16 combinaciones (alpha.26)

| # | Paso (1/s) | Pérdida (kPa/s) | Llenado (kPa/s) | Resultado | P mín cámara (CIC-04) | Aisl. VCH-AIS | Chq máx | Duración (s) |
|---|---|---|---|---|---|---|---|---|
| 1 | 0,100 | 0,4 | 4,0 | COMPLETADO | 209,9 (203,0) | 0 | 217,6 | 900 |
| 2 | 0,100 | 0,4 | 1,5 | COMPLETADO | 209,5 (203,0) | 0 | 216,4 | 900 |
| 3 | 0,100 | 0,8 | 4,0 | COMPLETADO | 209,4 (203,0) | 0 | 223,2 | 900 |
| 4 | 0,100 | 0,8 | 1,5 | FALLO CIC-04 (T baja) | 205,8 (203,0) | 0 | 215,7 | 142 |
| 5 | 0,030 | 0,4 | 4,0 | COMPLETADO | 209,3 (203,0) | 0 | 237,9 | 900 |
| 6 | 0,030 | 0,4 | 1,5 | COMPLETADO | 207,7 (203,0) | 0 | 233,1 | 900 |
| 7 | 0,030 | 0,8 | 4,0 | COMPLETADO | 207,3 (203,0) | 0 | 256,8 | 900 |
| 8 | 0,030 | 0,8 | 1,5 | FALLO CIC-04 (P baja) | 202,0 (203,0) | 0 | 225,9 | 23 |
| 9 | 0,015 | 0,4 | 4,0 | COMPLETADO | 208,2 (203,0) | 0 | 268,9 | 900 |
| 10 | 0,015 | 0,4 | 1,5 | COMPLETADO | 204,7 (203,0) | 0 | 256,7 | 900 |
| 11 | 0,015 | 0,8 | 4,0 | COMPLETADO | 203,8 (203,0) | 0 | 305,5 | 900 |
| 12 | 0,015 | 0,8 | 1,5 | FALLO CIC-04 (P baja) | 200,5 (203,0) | 0 | 228,2 | 18 |
| 13 | 0,008 | 0,4 | 4,0 | COMPLETADO | 206,2 (203,0) | 0 | 322,6 | 900 |
| 14 | 0,008 | 0,4 | 1,5 | FALLO CIC-04 (P baja) | 202,0 (203,0) | 0 | 240,5 | 29 |
| 15 | 0,008 | 0,8 | 4,0 | FALLO CIC-04 (P baja) | 200,8 (203,0) | 0 | 264,0 | 18 |
| 16 | 0,008 | 0,8 | 1,5 | FALLO CIC-04 (P baja) | 199,5 (203,0) | 0 | 229,7 | 16 |

**Fallan 6 de 16 (la especificación §1.4 dice 7).** Ningún aislamiento VCH-AIS en ningún caso.

- El caso 4 cae por temperatura baja (Principal 120,9 < 120,9 °C, a los 142 s), con la presión aún en 205,8: el desfase de 0,6 K deja la Principal a 0,1 K de la falla de partida.
- Los otros 5 caen por presión baja en 16–29 s: paso restringido con pérdida alta o llenado lento, como describe §1.4.
- El caso 11 completa con 0,8 kPa de margen sobre CIC-04 y el 10 con 1,7: son los candidatos más cercanos a un 7.º fallo.
- Con la pérdida a 0,2 kPa/s (`--perdidas 0.2`) completan las 8 combinaciones, como dice §1.4.

### Por qué puede diferir de 7

Sensibilidad a la temperatura inicial de la carga (no fijada en §1.4), mismo resto del escenario:

| T carga inicial (°C) | Fallos | Observación |
|---|---|---|
| 121,0 / 121,1 | 16 | todos por T baja (la Principal arranca bajo T_est − 0,1) |
| 121,5 | 9 | se suman 10, 11 y 13 |
| 121,6 (base) | 6 | |
| 121,7 | 6 | mismos casos |
| 122,06 (Tsat de 212 kPa) | 6 | mismos casos |

Ninguna variante probada da 7. Cámara inicial 212,1 kPa en lugar de 212,0 tampoco cambia el conteo. Causa probable: la especificación usó otra condición inicial de la carga o de la sonda (no fijada en §1.4), o un arnés distinto. Para fijar el número hace falta el escenario exacto de quien obtuvo el 7.

## Ciclos completos (alpha.26)

`python -m pytest tests/test_t33_cas04_planta.py tests/test_pam_planta.py`: **64 passed, 13 xfailed** (sin fallos ni XPASS).

xfail de `test_t33_cas04_planta.py` (11):
- `test_criterio_cas04[134 sólidos|restrictivo|k=1.00]`
- `test_criterio_cas04[LIQ … |restrictivo|k=1.07]` (las 8 combinaciones add_est × add_liq × brecha)
- `test_criterio_cas04[134 sólidos|restrictivo|k=1.07]`
- `test_criterio_cas04[134 sólidos|abierto|k=1.07]`

xfail de `test_pam_planta.py` (2):
- `test_desfase_de_sonda_0_6_k_llega_a_esterilizar[liquidos|restrictivo|chaqueta]`
- `test_desfase_de_sonda_0_6_k_llega_a_esterilizar[instrumental_121|restrictivo|chaqueta]`

El resto pasa: en `test_t33_cas04_planta.py`, los Líquidos restrictivo k 1,00 y 0,95, todo el abierto k 1,00 y 0,95, 134 sólidos abierto k 1,00 y 0,95, restrictivo k 0,95, la planta A14 y las pruebas de ganancia y de distancia a la falla; en `test_pam_planta.py`, los otros 6 casos de desfase 0,6 K y los 8 de Principal calibrada.
