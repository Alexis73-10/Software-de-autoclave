# Tanda 33: control en cascada de la chaqueta (CAS) — informe (parcial, BLOQUEADA)

Estado: **sin merge a `dev` y sin compilación**. El criterio de liberación de CAS-04 no se cumple (ver abajo). Rama `tanda33`.

## Resumen para Cristian

- En modo chaqueta, ESTERILIZACION (y CALENTAMIENTO en sostenimiento y tras el enclave de líquidos) ahora decide `vapor_chaqueta` con una cascada: según la presión de la cámara (baja / banda / alta) fija una consigna para la chaqueta, con histéresis de 3 kPa y tope atado al techo de aislamiento (techo − 2). Reemplaza el PWM, el corte A14-M2 y la exención M2-REC-01 solo en modo chaqueta; el modo cámara no cambia.
- `liquidos.json` (fábrica y usuario): `presion_add_esterilizacion` 11 → 15.
- Con **válvula de asiento sin restricción** (lo que Cristian confirmó) y `pres_chaqueta` bien calibrada (k = 1,00), en la planta simulada los 9 escenarios completan, sin aislamientos, con menos sobreimpulso y menos conmutaciones que la alpha.24.
- **Pero** con el paso cámara–chaqueta restrictivo (0,015/s, el de la planta por defecto) la cascada termina en CIC-04 (falla segura) en los 8 escenarios de Líquidos, mientras que la alpha.24 completaba. Ningún ajuste de `HISTERESIS_KPA` (2–5) ni `MARGEN_TECHO_KPA` (1–4) lo corrige (8 intentos). Por la regla del prompt, no se hizo merge ni compilación.
- Con k = 1,07 (el transmisor de chaqueta lee 7 % alto) la cascada falla de forma segura en Líquidos: dependencia de calibración (HAZ-CAS-02). Con k = 0,95 completa 9/9 (la alpha.24 solo 4/9).

## Qué decidir (Cristian)

1. ¿Liberar con el criterio limitado al caudal abierto (el real), dejando el restrictivo como caracterización? Si el equipo tuviera restricción, la cámara no se repone y termina en CIC-04.
2. ¿Basta la calibración con patrón de `pres_chaqueta` como precondición para k ≠ 1 (HAZ-CAS-02)?
3. Si se libera: falta revisor de seguridad, documentación (CLAUDE.md, HAZ-CAS-01/02, REQ, bloque de banco T33), suite completa, merge y compilación (alpha.25).

## Qué mirar en el banco (si se libera)

Calibrar `pres_chaqueta` con patrón primero; ciclo Líquidos 121 °C; ciclo 134 °C sólidos; en `backend.log`: líneas «Cascada chaqueta», nº de «cámara AISLADA», presión mínima de cámara, chaqueta máxima.

## Planta simulada

Tabla completa (55 escenarios, alpha.24 contra tanda 33) y los 8 intentos de ajuste: `CAS04_tabla.md`. Resumen (escenarios que cumplen, alpha.24 entre paréntesis):

| Caudal | k = 1,00 | k = 1,07 | k = 0,95 |
|---|---|---|---|
| abierto (real) | 9/9 (9/9) | 0/9 (8/9) | 9/9 (4/9) |
| restrictivo 0,015/s | 0/9 (8/9) | 0/9 (0/9) | 0/9 (8/9) |

Abierto, k = 1,00: presión mínima de cámara 206,5–207,4 kPa a 121 °C (criterio 204,5) y 306,2 a 134 °C (303,7); chaqueta máxima 247,8 kPa; sobreimpulso a 134 °C 0,49 K (alpha.24 0,69; con la planta de A14, 0,35 frente a 0,59); conmutaciones de `vapor_chaqueta` 33,3 → 16,8 por minuto. 134 °C restrictivo y abierto con k = 1,07 dan timeout de CALENTAMIENTO también en la alpha.24 (rampa con A14-M2, que CAS no cambia).

## DECISIÓN SIN CONFIRMAR

- `HISTERESIS_KPA` 3, `MARGEN_TECHO_KPA` 2, umbrales −2/+1, OFF en nivel `alta` (hasta el banco).
- La cascada se evalúa también con aislamiento o sin lectura del Principal (log/publicación), pero la orden es ON solo sin aislamiento, con lectura y sin `inhibir_vapor_chaqueta`.
- Tras VCH-AIS, D-CHQ o pérdida de lectura la válvula de la cascada sigue la salida real: no reabre por histéresis hasta `pres_chaqueta <= consigna − 3`.
- `estado.cascada_chaqueta.valvula` = orden aplicada (unificado en las dos fases); None fuera de las fases; tras cancelar o paro queda el último valor hasta el siguiente ciclo.
- En CALENTAMIENTO la cascada empieza a decidir un tick después de entrar a ESTABLE_PREESTERILIZACION; con empuje, en el tick del enclave. A14-M2 deja de evaluarse mientras decide la cascada.
- La planta (ganancias k, variantes de caudal) es provisional.

## Pruebas cambiadas o retiradas

- `test_m2_rec_esterilizacion.py`: retiradas 8 de `debe_cortar` con exención, `test_motivo_exencion`, 11 de la fase con `_exencion_m2` y 2 de planta (la «antes» parcheaba `motivo_exencion`); quedan `test_exencion_retirada` y `test_modo_camara_sin_cambio`.
- `test_t28_a14_esterilizacion.py`: retiradas `test_m2_ester_corta_sobre_p_sp_mas_margen_y_reabre_debajo`, `test_m2_ester_usa_el_margen_del_programa`, las 7 `test_h1_*` del tramo ON en modo chaqueta, `test_h1_bajo_p_low_con_el_corte_activo`; `test_h1_integracion_cicloestate_*` reescrita como `test_integracion_cicloestate` en `test_t33_cas02_esterilizacion.py`.
- `test_t16_s1_esterilizacion.py`: `test_modo_chaqueta_pwm_conmuta_solo_chaqueta` y `test_aislamiento_sale_con_histeresis_y_3_s` adaptadas.
- `test_ajuste_7nov_liquidos.py`: tramo final de `test_chaqueta_m2_techo_ampliado_en_empuje_y_en_bajada_normal_despues` (ahora decide la cascada).
- `test_t28_a14_m3_brecha.py`: Líquidos espera `presion_add_esterilizacion` 15 (CAS-05).
- 36 escenarios de planta marcados `xfail(strict=True)` con su motivo (los que no cumplen).
- Pruebas nuevas: `test_t33_cascada_chaqueta.py` (72), `test_t33_cas02_esterilizacion.py` (36), `test_t33_cas03_calentamiento.py` (19), `test_t33_cas04_planta.py`.
- Pruebas T33 + `test_t28_a14_m3_brecha`: 176 pasan, 36 xfail. **No se corrió la suite completa** (la base, en el worktree `..\autoclave_base`, iba por ~17 % al cerrar; ver `suite_base.txt`).

## Hallazgo M3 (solo reportado)

`backend/context.py:306` solo reescribe el archivo de los programas con `source == "user"`: un programa de fábrica con `brecha_segura_temperatura` 1,0 se migra en memoria (`_migrar_brecha_t28`) en cada arranque y nunca queda marcado ni reescrito. Los JSON de fábrica del repo ya traen 0,3, así que no se pudo confirmar cuál programa lo dispara (probable `textiles` en la copia instalada del equipo).

## Pendiente por el bloqueo

Revisor de seguridad sobre el diff de CAS, `CLAUDE.md`, HAZ-CAS-01/02 y HAZ-M2-REC-01 superado, REQ, bloque T33 de la hoja de banco, suite completa, merge y compilación.
