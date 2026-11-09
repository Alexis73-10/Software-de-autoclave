# Tanda 33: control en cascada de la chaqueta (CAS) — informe

Estado: **liberada en la planta simulada con el ajuste del tope de la baja (8-nov)**. Sin merge a `dev` ni compilación todavía. Rama `tanda33`.

## Resumen para Cristian

- En modo chaqueta, la cascada decide `vapor_chaqueta` en ESTERILIZACION y en CALENTAMIENTO (en sostenimiento y después del enclave de líquidos). Según la presión de la cámara (baja, banda o alta) fija una consigna para la chaqueta, con histéresis de 3 kPa. En el modo chaqueta reemplaza al PWM, al corte A14-M2 y a la exención M2-REC-01. El modo cámara no cambia.
- `liquidos.json` (fábrica y usuario): `presion_add_esterilizacion` pasa de 11 a 15.
- **Ajuste del 8-nov (lo autorizaste tú):** en el nivel «baja» la consigna es `min(presion_max_chaqueta_control − 10, presion_suministro_vapor)`, que con los defectos del equipo da **350 kPa**. Antes era techo − 2, unos 218 kPa a 121 °C. Los niveles «banda» (`min(P_sp + margen_est, techo − 2)`) y «alta» (OFF) no cambian, como tampoco `HISTERESIS_KPA` 3 ni `MARGEN_TECHO_KPA` 2. VCH-AIS, D-CHQ y el corte duro de CICLO siguen prevaleciendo. El nuevo tope es `DECISIÓN SIN CONFIRMAR` hasta el banco.
- **Decisión tomada (regla 3):** el caudal abierto con k = 1,00 sigue cumpliendo 9/9 y el restrictivo con k = 1,00 cumple 4/8 (sin contar el 134 °C excluido). Por eso **se libera con el ajuste** y el restrictivo queda como caracterización. No hubo reversión.
- Con el caudal restrictivo, los 8 escenarios de Líquidos dejaron de terminar en CIC-04 y ahora completan. Los 4 que no cumplen tienen `presion_add_liquido_calentamiento` 20 y su presión mínima queda en 204,2–204,3 kPa, 0,2–0,3 kPa bajo el umbral de 204,5. Siguen sobre el umbral de falla (203,0) y tienen ≤ 1 aislamiento. La chaqueta real llega como máximo a 297,7 kPa.

## Veredicto CAS-04

Criterio: k = 1,00 con caudal abierto **y** restrictivo. Umbrales: COMPLETADO, presión mínima ≥ 204,5 kPa a 121 °C y ≥ 303,7 a 134 °C, aislamientos ≤ 1, chaqueta real < 375 y sobreimpulso a 134 °C ≤ 0,79 K.

**Exclusión:** el timeout de CALENTAMIENTO a 134 °C (caudal restrictivo con todos los k, y abierto con k = 1,07). La alpha.24 da el mismo resultado. Viene de la rampa con A14-M2, que CAS no toca.

Escenarios que cumplen. Cada celda dice alpha.24 / tanda 33 anterior / tanda 33 con el ajuste.

| Caudal | k = 1,00 | k = 1,07 (informativo) | k = 0,95 (informativo) |
|---|---|---|---|
| abierto (real) | 9/9 / 9/9 / **9/9** | 8/9 / 0/9 / 0/9 | 4/9 / 9/9 / 9/9 |
| restrictivo 0,015/s | 8/9 / 0/9 / **4/9** (4/8 sin el 134 °C) | 0/9 / 0/9 / 0/9 | 8/9 / 0/9 / 0/9 |

- **Abierto, k = 1,00.** Los resultados son los mismos que antes del ajuste:
  - presión mínima 206,5–207,4 kPa a 121 °C y 306,2 a 134 °C;
  - cero aislamientos y chaqueta máxima 247,8 kPa;
  - sobreimpulso a 134 °C de 0,49 K (alpha.24: 0,69);
  - con la planta de A14, 0,35 K y 15,7 conmutaciones por minuto (alpha.24: 0,59 K y 33,3).
- **k = 1,07 (informativo).**
  - Abierto: los Líquidos ahora completan (antes daban CIC-04 o temperatura baja), pero con presión mínima de 203,4–203,5 kPa, bajo 204,5.
  - Restrictivo: timeout de CALENTAMIENTO en las tres versiones.
  - Sigue la dependencia de calibración (HAZ-CAS-02).
- **k = 0,95 (informativo).**
  - Abierto: 9/9 (alpha.24: 4/9, con un CIC-16).
  - Restrictivo: los Líquidos ahora completan (antes daban CIC-04), con presión mínima de 204,0–204,2 kPa.

La tabla completa (55 escenarios, en tres columnas) está en `CAS04_tabla.md`.

## Qué decidir (Cristian)

1. ¿Basta con calibrar `pres_chaqueta` contra un patrón como precondición para k ≠ 1 (HAZ-CAS-02)?
2. Confirmar en el banco el tope de 350 kPa del nivel baja.
3. Falta: revisor de seguridad sobre el diff de CAS (incluido el ajuste), `CLAUDE.md`, HAZ-CAS-01/02 y HAZ-M2-REC-01 superado, REQ, bloque T33 de la hoja de banco, suite completa, merge y compilación (alpha.25).

## Qué mirar en el banco

- Calibrar primero `pres_chaqueta` con patrón.
- Correr un ciclo de Líquidos a 121 °C y un ciclo de sólidos a 134 °C.
- En `backend.log`, revisar:
  - las líneas «Cascada chaqueta», en particular cuánto tiempo pasa en nivel baja con la consigna en 350;
  - el número de «cámara AISLADA»;
  - la presión mínima de cámara;
  - la presión máxima de chaqueta.

## DECISIÓN SIN CONFIRMAR

- El tope del nivel baja: `min(presion_max_chaqueta_control − 10, presion_suministro_vapor)` (ajuste del 8-nov).
- `HISTERESIS_KPA` 3, `MARGEN_TECHO_KPA` 2, umbrales −2/+1 y OFF en el nivel `alta` (hasta el banco).
- La cascada se evalúa también con aislamiento o sin lectura del Principal (para el log y la publicación). La orden ON solo sale sin aislamiento, con lectura y sin `inhibir_vapor_chaqueta`.
- Tras VCH-AIS, D-CHQ o una pérdida de lectura, la válvula de la cascada sigue a la salida real: no reabre por histéresis hasta `pres_chaqueta <= consigna − 3`.
- `estado.cascada_chaqueta.valvula` es la orden aplicada (igual en las dos fases). Vale None fuera de las fases. Tras cancelar o un paro queda el último valor hasta el ciclo siguiente.
- En CALENTAMIENTO la cascada empieza a decidir un tick después de entrar a ESTABLE_PREESTERILIZACION; con empuje, en el tick del enclave. A14-M2 deja de evaluarse mientras decide la cascada.
- La planta (ganancias k y variantes de caudal) es provisional.

## Pruebas cambiadas o retiradas

- `test_m2_rec_esterilizacion.py`: se retiraron 8 pruebas de `debe_cortar` con exención, `test_motivo_exencion`, 11 de la fase con `_exencion_m2` y 2 de planta (la «antes» parcheaba `motivo_exencion`). Quedan `test_exencion_retirada` y `test_modo_camara_sin_cambio`.
- `test_t28_a14_esterilizacion.py`:
  - se retiraron `test_m2_ester_corta_sobre_p_sp_mas_margen_y_reabre_debajo`, `test_m2_ester_usa_el_margen_del_programa`, las 7 `test_h1_*` del tramo ON en modo chaqueta y `test_h1_bajo_p_low_con_el_corte_activo`;
  - `test_h1_integracion_cicloestate_*` se reescribió como `test_integracion_cicloestate` en `test_t33_cas02_esterilizacion.py`.
- `test_t16_s1_esterilizacion.py`: se adaptaron `test_modo_chaqueta_pwm_conmuta_solo_chaqueta` y `test_aislamiento_sale_con_histeresis_y_3_s`.
- `test_ajuste_7nov_liquidos.py`: se cambió el tramo final de `test_chaqueta_m2_techo_ampliado_en_empuje_y_en_bajada_normal_despues` (ahora decide la cascada).
- `test_t28_a14_m3_brecha.py`: Líquidos espera `presion_add_esterilizacion` 15 (CAS-05).
- Ajuste del 8-nov:
  - `test_t33_cascada_chaqueta.py`: la baja usa 350. Pruebas nuevas: `test_tope_baja_*`, histéresis bajo 350, paso de baja a banda y parámetros inválidos.
  - `test_t33_cas02_esterilizacion.py`: `test_nivel_baja_lleva_la_chaqueta_al_tope` usa 350. `test_planta_paso_restrictivo_falla_segura` pasa a ser `test_planta_paso_restrictivo_completa`.
  - `test_t33_cas03_calentamiento.py`: la baja usa 350 en sostenimiento y después del enclave.
  - `test_t33_cas04_planta.py`: el criterio es k = 1,00 con caudal abierto y restrictivo. Quedan 32 escenarios en `xfail(strict=True)` con su motivo: 4 excluidos (134 °C con timeout de CAL), 4 de caracterización (restrictivo k = 1,00 con add_liq 20) y 24 informativos (k = 1,07 y 0,95). La prueba de falla segura pasa a ser `test_liquidos_que_no_cumplen_quedan_lejos_de_la_falla`.
- Las pruebas T33 más `test_t28_a14_m3_brecha`, `test_t16_s1_esterilizacion`, `test_ajuste_7nov_liquidos` y `test_m2_rec_esterilizacion` dan 260 pasan y 32 xfail. La selección `-k "a14 or t16 or t12 or calentamiento or esterilizacion or chaqueta or vch or liquido"` da 1445 pasan. **La suite completa no se corrió.**

## Hallazgo M3 (solo reportado)

`backend/context.py:306` solo reescribe el archivo de los programas con `source == "user"`. Un programa de fábrica con `brecha_segura_temperatura` 1,0 se migra en memoria (`_migrar_brecha_t28`) en cada arranque y nunca queda marcado ni reescrito. Los JSON de fábrica del repo ya traen 0,3, así que no se pudo confirmar qué programa lo dispara (probablemente `textiles` en la copia instalada del equipo).

## Decisión de Cristian (8-nov)

- **Ajuste autorizado:** el nivel «baja» de la cascada usa `min(presion_max_chaqueta_control − 10, presion_suministro_vapor)` (350 kPa con los defectos). `DECISIÓN SIN CONFIRMAR` hasta el banco.
- **Criterio de liberación:** k = 1,00 con caudal abierto Y restrictivo. Abierto 9/9; restrictivo 4/8 (los otros 4 quedan como caracterización). Excluido: el timeout de CALENTAMIENTO a 134 °C (viene de la rampa A14-M2, también en la alpha.24). Se libera con el ajuste.
- **Precondición HAZ-CAS-02 (obligatoria):** calibrar `pres_chaqueta` con patrón antes del banco y de la instalación (evidencia: chaqueta 216,9 kPa con cámara 211,9 ≈ k 1,07). Es el primer paso del bloque T33 de la hoja de banco.
