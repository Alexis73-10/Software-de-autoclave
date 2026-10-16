# Límites del catálogo de parámetros (T10, tanda 2026-10-14)

Fuente: `src/autoclave/core/managers/catalogo_parametros.py`. Reglas de §1.6 de la instrucción, que prevalecen sobre el Anexo B del borrador de endurecimiento:

- presión absoluta: de 1 a 400 kPa (límite del modelo);
- temperatura absoluta: de 1 a 200 °C (límites del modelo);
- tiempos y timeouts: mínimo 1 en su unidad, salvo los que admiten 0 como "no se ejecuta" o "sin espera" (Anexo A.3);
- los demás parámetros del Anexo A.1 y A.2 llevan un mínimo mayor que 0;
- **ningún valor actual** de los programas se rechaza. Lo verifica `tests/test_t10_endurecimiento.py` sobre todos los JSON de `cycles/factory` y `cycles/user`.

**Rango efectivo** = intersección del rango del catálogo y el `min`/`max` del JSON del programa (D-6). Además, los tipos son estrictos (RB-05.3):
- `bool`: solo `true`/`false`;
- `int`: no admite parte decimal;
- `float`: no admite NaN ni infinito;
- ningún tipo admite cadenas numéricas;
- `enum`: debe ser una de sus `options`.

**Regla de coherencia (1.2):** con `globals.tipo_carga = liquido`, `descompresion.modo` debe ser 4 o 5.

## Tabla aplicada

| Parámetro | Unidad | Rango del JSON | Catálogo | Rango efectivo | Valores actuales | Motivo |
|---|---|---|---|---|---|---|
| `calentamiento.rango_temp_estabilizacion` | °C | 0 a 10 | 0.1 a — | 0.1 a 10 | 1.0 | Anexo A.1: 0 se sustituye |
| `calentamiento.temperatura_calentamiento` | °C | 100 a 140 | 1 a 200 | 100 a 140 | 121.0, 134.0 | temperatura del modelo |
| `calentamiento.timeout_calentamiento` | min | 1 a 999 | 1 a — | 1 a 999 | 60 | tiempo: mínimo 1 en su unidad |
| `calentamiento.timeout_recuperacion_estabilizacion` | min | 1 a 60 | 1 a — | 1 a 60 | 5 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo` |  | 0 a 5 | 0 a 5 | 0 a 5 | 1 | modo 0 conservado (enfriamiento natural) |
| `descompresion.modo_1.timeout` | min | 1 a 3600 | 1 a — | 1 a 3600 | 10 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_2.timeout` | min | 1 a 3600 | 1 a — | 1 a 3600 | 30 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_3.presion_cambio` | kPa | 0 a 500 | 1 a 400 | 1 a 400 | 150 | presión absoluta del modelo |
| `descompresion.modo_3.timeout` | min | 1 a 3600 | 1 a — | 1 a 3600 | 30 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_4.presion_camara_enfriamiento` | kPa | 0 a 500 | 1 a 400 | 1 a 400 | 200 | presión absoluta del modelo |
| `descompresion.modo_4.temperatura_enfriamiento` | °C | 0 a 150 | 1 a 200 | 1 a 150 | 80 | temperatura del modelo |
| `descompresion.modo_4.tiempo_apertura_chaqueta` | sec | 1 a 3600 | 1 a — | 1 a 3600 | 5 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_4.timeout` | min | 1 a 3600 | 1 a — | 1 a 3600 | 120 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_5.presion_camara_enfriamiento` | kPa | 0 a 500 | 1 a 400 | 1 a 400 | 200 | presión absoluta del modelo |
| `descompresion.modo_5.temperatura_enfriamiento` | °C | 0 a 150 | 1 a 200 | 1 a 150 | 80 | temperatura del modelo |
| `descompresion.modo_5.tiempo_apertura_chaqueta` | sec | 1 a 3600 | 1 a — | 1 a 3600 | 5 | tiempo: mínimo 1 en su unidad |
| `descompresion.modo_5.timeout` | min | 1 a 3600 | 1 a — | 1 a 3600 | 120 | tiempo: mínimo 1 en su unidad |
| `estabilizacion.temperatura_estabilizacion` | °C | 0 a 200 | 1 a 200 | 1 a 200 | 134.0 | temperatura del modelo |
| `estabilizacion.timeout_recuperacion` | seg | 0 a 3600 | 1 a — | 1 a 3600 | 10, 5 | tiempo: mínimo 1 en su unidad |
| `esterilizacion.temperatura_esterilizacion` | °C | 100 a 140 | 1 a 200 | 100 a 140 | 121.0, 134.0 | temperatura del modelo |
| `esterilizacion.tiempo_esterilizacion` | min | 0 a 9999 | 1 a — | 1 a 9999 | 15.0, 3.5, 7.0 | tiempo: mínimo 1 en su unidad |
| `finalizacion.temp_max_apertura` | °C | 0 a 150 | 1 a 200 | 1 a 150 | 100.0, 80.0 | temperatura del modelo |
| `finalizacion.timeout_temperatura` | min | 1 a 120 | 1 a — | 1 a 120 | 30 | tiempo: mínimo 1 en su unidad |
| `globals.presion_chaqueta` | kPa | 0 a 400 | 1 a 400 | 1 a 400 | 250, 300, 350 | presión absoluta del modelo |
| `globals.rango_presion_chaqueta` | kPa | 0 a 100 | 1 a — | 1 a 100 | 25, 50 | Anexo A.1: banda de ancho cero |
| `precalentamiento.presion_precalentamiento` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 200, 250, 350 | presión absoluta del modelo |
| `precalentamiento.timeout_precalentamiento` | min | 0 a 3600 | 1 a — | 1 a 3600 | 1, 10 | tiempo: mínimo 1 en su unidad |
| `prevacio.presion_alta_pulso_a` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 140, 160, 80 | presión absoluta del modelo |
| `prevacio.presion_alta_pulso_b` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 160 | presión absoluta del modelo |
| `prevacio.presion_alta_pulso_c` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 160 | presión absoluta del modelo |
| `prevacio.presion_alta_pulso_d` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 160 | presión absoluta del modelo |
| `prevacio.presion_baja_pulso_a` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 20, 30, 50 | presión absoluta del modelo |
| `prevacio.presion_baja_pulso_b` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 110, 30 | presión absoluta del modelo |
| `prevacio.presion_baja_pulso_c` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 110 | presión absoluta del modelo |
| `prevacio.presion_baja_pulso_d` | kPa | 0 a 1000 | 1 a 400 | 1 a 400 | 110 | presión absoluta del modelo |
| `prevacio.timeout_alto` | min | 0 a 3600 | 1 a — | 1 a 3600 | 10 | tiempo: mínimo 1 en su unidad |
| `prevacio.timeout_bajo` | min | 0 a 3600 | 1 a — | 1 a 3600 | 10 | tiempo: mínimo 1 en su unidad |
| `secado.modo` |  | 1 a 3 | 1 a 3 | 1 a 3 | 1, 3 | Anexo A.1: 0 se sustituye |
| `secado.presion_alta_secado` | kPa | 0 a 300 | 1 a 400 | 1 a 300 | 50, 80 | presión absoluta del modelo |
| `secado.presion_baja_secado` | kPa | 0 a 200 | 1 a 400 | 1 a 200 | 20 | presión absoluta del modelo |
| `secado.presion_chaqueta_secado` | kPa | 0 a 500 | 1 a 400 | 1 a 400 | 200, 300 | presión absoluta del modelo |
| `secado.rango_chaqueta_secado` | kPa | 0 a 100 | 1 a — | 1 a 100 | 30 | Anexo A.1: 0 se sustituye |
| `secado.timeout_pulso` | seg | 1 a 600 | 1 a — | 1 a 600 | 10, 120, 180 | tiempo: mínimo 1 en su unidad |

## Tiempos donde 0 sigue siendo válido (sin límite del catálogo)

- `precalentamiento.tiempo_precalentamiento`: 0 salta la fase.
- `secado.tiempo_secado`: 0 salta la fase.
- `descompresion.tiempo_pre_despresurizacion`: 0 significa sin espera previa.
- `finalizacion.tiempo_espera_apertura`: 0 significa sin espera.
- `calentamiento.tiempo_estable_preesterilizacion`.
- `estabilizacion.tiempo_estabilizacion`.
- `prevacio.tiempo_adicional_*`.

## Notas

- `descompresion.modo` admite 0 (enfriamiento natural, decisión 1.2).
- Los parámetros sin fila en la tabla conservan el rango de su JSON: escapes, factores, brechas y rangos de falla de esterilización, deltas de presión (`presion_add_*`), tasas e intervalos de PWM. Sus mínimos los propone la especificación 3 y los aprueba Cristian.
- Un programa con un valor fuera del rango efectivo al cargar queda **dañado**: no se puede seleccionar, iniciar ni editar (RB-04.4 / RB-05.5).
