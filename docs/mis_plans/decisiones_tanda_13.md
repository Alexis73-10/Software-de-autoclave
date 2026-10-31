# Decisiones — Tanda 13 (mini-tanda: VAP-01, saturación con IAPWS-IF97, 24-oct)

Fuente de verdad de la tanda 13. Pedido de Cristian del 24-oct (20:39): corregir antes de instalar el lunes 26-oct.

## VAP-01. Presión de saturación con error de hasta −2.5 kPa
**Hallazgo:** `core/runtime/steam.py` usa una ecuación de Antoine (A=7.26509, B=1810.94, C=244.485) que da 302.26 kPa a 134 °C; las tablas de vapor (IAPWS-IF97), las tablas de calibración y los ingenieros usan 304.2 kPa. Error en la zona de trabajo: −0.77 kPa a 121 °C, −1.94 a 134 °C, −2.54 a 140 °C (≈ −0.12 a −0.25 K). Pesa sobre todo en la falla de presión baja de ESTERILIZACION (Psat − 2 dispara en realidad a ≈ Psat_real − 3.9 kPa a 134 °C), la entrada de C-01, las bandas PWM, C-02/C-03, el techo, la consigna de chaqueta, las validaciones 350/385 kPa, la contrapresión de líquidos, `base_fase.py`, `protocolo_fallo.py` y la consigna mostrada en la UI (`consignas.py`). F0 no se afecta.

Todo el código pasa por `steam.py` (verificado: no hay otra fórmula ni tabla de vapor duplicada en `src/`, `tools/` ni `Hardware/`).

## Decisiones
1. `p_saturacion_kpa(T)` y `t_saturacion_c(p)` pasan a las ecuaciones de la **región 4 de IAPWS-IF97** (ecuación 30 para ps(T) y ecuación 31 para Ts(p), forma cerrada, coeficientes n1..n10 de la tabla 34). Mismos nombres y firmas: ningún otro archivo de código cambia.
2. Unidades: entrada en °C / kPa absolutos, salida en kPa absolutos / °C (la norma trabaja en K y MPa: convertir dentro de la función).
3. Validez: 0.01–373.946 °C (273.16–647.096 K). Fuera de ese rango, o con entrada no finita, `ValueError`; `p_kpa <= 0` → `ValueError` (se conserva). DECISIÓN SIN CONFIRMAR: no se recorta al rango de trabajo 99–145 °C para no cambiar el comportamiento de los llamadores fuera de él; si algún llamador puede pasar un valor fuera de 0.01–373.946 °C (p. ej. `None` ya filtrado, 0 de sensor), se verifica que la excepción no rompa el ciclo y se anota en el informe.
4. Pruebas obligatorias:
   - valores de verificación de la norma, tabla 35: T = 300 K → 0.353658941e-2 MPa; 500 K → 0.263889776e1 MPa; 600 K → 0.123443146e2 MPa (tolerancia relativa 1e-8);
   - tabla 36: p = 0.1 MPa → 372.755919 K; 1 MPa → 453.035632 K; 10 MPa → 584.149488 K (tolerancia 1e-6 K);
   - puntos de trabajo: 121 °C → 205.04 kPa, 134 °C → 304.20 kPa, 134.5 °C → 308.67 kPa (±0.02);
   - ida y vuelta T → p → T en 100–145 °C (1e-6 K).
5. Se actualizan los tests existentes que tienen escritos valores derivados de la fórmula vieja (302.3, 204.3, 311.3, 326.3, 230.3, etc.), recalculándolos con la función nueva — nunca relajando tolerancias. Lista completa en el informe. Valores nuevos de referencia: techo 134 °C/9 kPa = 313.2; consigna de chaqueta 134/9 = 328.2; 121/11 = 231.04.
6. Se actualiza el comentario de cabecera de `steam.py` (fuente: IAPWS-IF97, región 4), la mención en `CLAUDE.md` y las cifras derivadas en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` y en el LEEME de la entrega (sección de cambios).
7. Los programas JSON no cambian (sus parámetros son temperaturas y diferencias, no Psat absolutas). Verificar que ningún programa de fábrica ni de usuario del repo queda rechazado por las validaciones 350/385 con la función nueva.
8. Efecto conocido y aceptado: con la tabla correcta, el techo a 134 °C con `presion_add_esterilizacion` 9 (313.2 kPa) equivale a ≈ 135.0 °C; el problema de salida de RECUPERACION de la tanda 12 (DECISIONES_PARA_REVISAR, urgente 1) **no cambia** y sigue pendiente para la tanda 14.
