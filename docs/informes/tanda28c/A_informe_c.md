# Tanda 28, flujo C — informe (A14, A12)

Rama `tanda28c`. Diagnóstico y comparación de A14 en `docs/informes/tanda28/A14_diagnostico.md`.

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
