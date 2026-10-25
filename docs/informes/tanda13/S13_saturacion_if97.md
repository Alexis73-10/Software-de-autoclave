# S13 — Saturación con IAPWS-IF97 (tanda 13, VAP-01)

Fecha: 24/25-oct-2026. Lo hizo la sesión principal, sin subagentes ni revisor. Fuente de verdad: `docs/mis_plans/decisiones_tanda_13.md`.

**Resultado:** `p_saturacion_kpa(T)` y `t_saturacion_c(p)` usan ahora las ecuaciones de la región 4 de IAPWS-IF97 (ecuación 30 para ps(T) y 31 para Ts(p), coeficientes n1..n10 de la tabla 34). Tienen los mismos nombres y firmas. A 134 °C dan **304.20 kPa**; la fórmula de Antoine anterior daba 302.26.

Commit: b84e758 (código y pruebas). Los documentos van en un commit aparte.

## 1. Comparación

| T (°C) | IAPWS-IF97 (kPa) | Fórmula vieja (kPa) | Diferencia (kPa) | Error de la vieja en T (K) |
|---|---|---|---|---|
| 100 | 101.42 | 101.89 | −0.47 | +0.131 |
| 110 | 143.38 | 143.36 | +0.01 | −0.003 |
| 121 | 205.04 | 204.27 | +0.77 | −0.120 |
| 128 | 254.48 | 253.11 | +1.37 | −0.178 |
| 134 | 304.20 | 302.26 | +1.94 | −0.218 |
| 135 | 313.20 | 311.17 | +2.04 | −0.224 |
| 140 | 361.50 | 358.96 | +2.54 | −0.249 |

Diferencia = IF97 − vieja. La última columna es Tsat_IF97(P_vieja) − T, es decir, cuánto se equivocaba la vieja expresada en temperatura. A 100 °C la vieja daba de más; de 121 °C hacia arriba daba de menos, que es lo que señaló VAP-01.

Valores de referencia que cambian:
- techo de esterilización a 134 °C con `presion_add` 9: **313.2 kPa** (antes 311.3), con Tsat ≈ 135.0 °C;
- consigna de chaqueta a 134 °C con 9: **328.2 kPa** (antes 326.3);
- consigna de chaqueta a 121 °C con 11: **231.04 kPa** (antes 230.3);
- Bowie & Dick a 134.5 °C con 99: 407.7 kPa (antes 405.7);
- falla de presión baja de ESTERILIZACION a 134 °C: **302.2 kPa** (antes 300.3).

## 2. Implementación (`src/autoclave/core/runtime/steam.py`)
- Las conversiones van dentro: °C ↔ K (273.15) y kPa ↔ MPa.
- Validez (decisión 3): 0.01–373.946 °C. Para la presión se usa el rango equivalente, de Psat(0.01 °C) ≈ 0.611657 kPa a Psat(373.946 °C) ≈ 22064 kPa. El extremo se calcula con la propia ecuación 30, para que `t_saturacion_c(p_saturacion_kpa(373.946))` no lance.
- Se lanza `ValueError` fuera de rango, con entrada no finita o con `p_kpa <= 0`. No se recorta al rango de trabajo de 99–145 °C.
- El comentario de cabecera indica la fuente: IAPWS-IF97, región 4.

## 3. Pruebas de la decisión 4 (`tests/test_t13_s13_saturacion_if97.py`, 226 pruebas)
Se escribieron antes que el código: con la fórmula vieja fallaban 24 de 212. Ahora pasan todas.
- Tabla 35 (rel 1e-8): 300 K → 0.353658941e-2 MPa; 500 K → 0.263889776e1; 600 K → 0.123443146e2.
- Tabla 36 (1e-6 K): 0.1 MPa → 372.755919 K; 1 MPa → 453.035632; 10 MPa → 584.149488.
- Puntos de trabajo (±0.02 kPa): 121 °C → 205.04; 134 °C → 304.20; 134.5 °C → 308.67.
- Ida y vuelta T → p → T en 100–145 °C, cada 0.25 °C (1e-6 K).
- Monotonía; extremos del rango; `ValueError` fuera de rango, con no finitos y con `p <= 0`.
- Valores derivados: techo 313.2, chaqueta 134/9 → 328.2 y chaqueta 121/11 → 231.04.
- Programa con temperatura fuera de la tabla: devuelve la lista de errores sin lanzar, y `consigna_chaqueta` da `None` (ver 4.1).

## 4. Llamadores y la excepción fuera de rango
`grep -rn "p_saturacion_kpa\|t_saturacion_c" src tools` encuentra estos llamadores. No hay otra fórmula de vapor.

| Llamador | Entrada | ¿Puede salirse de 0.01–373.946 °C? | ¿Rompe un ciclo? |
|---|---|---|---|
| `catalogo_parametros.consigna_chaqueta`, `_evaluar_limites`, contrapresión de líquidos en `errores_coherencia` | temperaturas del programa | Sí, con un programa corrupto (fuera del catálogo 1–200 °C) | **Sí rompía la carga** → corregido (4.1) |
| `esterilizacion.py` `p_sat_est = Psat(t_est)` | `temperatura_esterilizacion` (catálogo 100–140) | No: un programa fuera del catálogo queda DAÑADO y no se ejecuta | No |
| `esterilizacion.py` `_control_vapor_pwm` → `Psat(temp)` | lectura del Principal, solo en PWM_ACTIVO (T ≥ t_est + brecha) | Solo con una lectura > 373.9 °C (sensor roto; el canal es 0–200 °C) | No rompe la seguridad (4.2) |
| `esterilizacion.py` C-03 → `Tsat(pres)` | lectura de presión | Sí (p < 0.61 kPa) | No: ya estaba en `try/except ValueError` (dT = 0; la presión baja falla aparte) |
| `calentamiento.py` `_duty_por_calidad_vapor` → `Psat(temp)` | lectura, solo con T ≥ T_obj − 3 | Solo con > 373.9 °C | No rompe la seguridad (4.2) |
| `calentamiento.py` `_diferencia_coherencia_tp` → `Tsat(pres)` | lectura de presión | Sí | No: `try/except ValueError` → None = incoherente (reinicia la ventana, lo más seguro) |
| `calentamiento.py` `p_obj = Psat(t_obj)` | parámetro del programa (catálogo) | No | No |
| `protocolo_fallo.py` `Psat(t_est)` | parámetro, con valor por defecto 121 si no es número | No (catálogo) | No |
| `base_fase._verificar_vapor_saturado` | solo lo usa `estabilizacion.py`, fuera de la secuencia | — | No |
| `ciclo.py` log de la consigna → `Tsat(consigna)` | consigna de 200 a 385 kPa, o `None` (no se llama) | No | No |
| `ui_qml/domain/consignas.py` | temperatura guardada, ya filtrada a 99–145 | No | No |

### 4.1 Corrección en `catalogo_parametros.py` (DECISIÓN SIN CONFIRMAR)
La suite lo detectó con `test_c2_programas_persistentes.py::test_usuario_con_valores_fuera_de_catalogo_no_es_ejecutable`: un programa de usuario con `temperatura_esterilizacion` 999.
- **Antes:** la fórmula vieja no lanzaba. El programa cargaba como **DAÑADO**, se veía en la lista y no se podía ejecutar.
- **Con la función nueva:** `errores_coherencia` lanzaba `ValueError` y el archivo terminaba en `errores_carga`. Su lugar en la lista lo ocupaba **en silencio el programa de fábrica del mismo nombre**.

La instrucción dice que solo cambia `steam.py`. Aun así se eligió lo más seguro y reversible: un ayudante `_psat(t)` que devuelve `None` fuera de la tabla. Las reglas derivadas de Psat (techo de cámara, consigna de chaqueta y contrapresión) no se evalúan para esa temperatura, porque el catálogo ya la rechaza. `consigna_chaqueta` devuelve `None`, igual que con un valor no numérico. `steam.py` conserva el `ValueError` de la decisión 3. Son 34 líneas en un solo archivo; para revertir basta con quitar `_psat`.

### 4.2 Lectura de temperatura > 373.9 °C en CALENTAMIENTO/ESTERILIZACION (PREGUNTA, sin cambio)
El canal de temperatura es de 0 a 200 °C (`CALIBRACION_PLAUSIBLE`). Una lectura así solo sale de un sensor o una tarjeta fuera de escala.
- **Antes:** la fórmula vieja devolvía un número enorme y el control seguía.
- **Ahora:** `fase.update()` lanza en cada tick. El `ControlLoop` lo trata como tick fallido: a los 3 seguidos apaga todas las salidas (`_EXCEPCIONES_PARA_APAGAR`), deja de renovar el latido y el watchdog del firmware apaga a los 5 s.
- **Cómo termina:**
  - En ESTERILIZACION, la falla de temperatura alta se evalúa antes del PWM, así que a los 5 s se registra el FALLO normal.
  - En CALENTAMIENTO, el timeout de la fase se evalúa antes del cálculo del duty, así que el ciclo termina en FALLO por tiempo límite.

En los dos casos el estado es seguro (salidas apagadas), pero el motivo inmediato queda solo en el log como excepción. Se propone, para la tanda 14, un filtro de plausibilidad de las lecturas vivas: rechazar fuera de 0–200 °C como «sin lectura», con SEN-02. Es otra lógica de ciclo y queda fuera del alcance de esta tanda.

## 5. Tests actualizados (decisión 5: recalculados, sin tocar tolerancias)

| Test | Valor viejo → nuevo |
|---|---|
| `test_steam.py::test_p_saturacion_134` | 302.9 → **304.2** (±1.0, igual) |
| `test_steam.py::test_verificar_vapor_saturado_dentro_tolerancia` | P = 302.2 → **304.2**; comentarios de los otros dos: deltas 17.8 → 15.8 y 17.2 → 19.2 |
| `test_t12_c04_presion_add.py::test_bd_original_sin_migracion_queda_rechazado` | 405.7 → **407.7** (±0.1) |
| `test_t12_c05_chaqueta.py::test_consigna_134_con_9` | 326.3 → **328.2** (±0.2) |
| `test_t12_c05_chaqueta.py::test_consigna_121_con_11` | 230.3 → **231.0** (±0.2) |
| `test_t12_c05_chaqueta.py::test_on_bajo_consigna_menos_10` | 326.3 − 10.5 → **328.2 − 10.5** (ya pasaba; consistencia) |
| `test_t12_c05_chaqueta.py::test_off_sobre_consigna_mas_10` | 326.3 + 10.5 → **328.2 + 10.5** |
| `test_t12_c05_chaqueta.py::test_sin_cambio_dentro_de_la_banda` | [316.8, 326.3, 335.8] → **[318.7, 328.2, 337.7]** |
| `test_t12_c05_chaqueta.py::test_la_consigna_se_registra_en_el_log_al_iniciar` | «consigna de chaqueta 326.3 kPa» → **328.2** |
| `test_t12_c05_chaqueta.py::test_consigna_justo_bajo_el_alivio_se_guarda_con_advertencia` | T_est 139 (consigna + 10 = 384.95) → **138.7** (384.40 < 385). Con IF97, 139 da 387.39 y se rechaza, que es justo lo que la prueba vecina comprueba con 140 |
| Comentarios en `test_t12_c05_chaqueta.py` | 326.3 → 328.2 (×2); margen 30: 313.3 + 30 = 343.3 → 315.2 + 30 = 345.2 |

`grep` de cifras de la fórmula vieja en `tests/`: no queda ninguna fuera de las anotadas «antes …». La única coincidencia es `test_x9_d9_13_4_ticket_motivos_idioma.py` con `pres_limite=302.0`, que es un valor arbitrario para formatear un mensaje.

## 6. Suite
`pytest tests -n auto` sobre b84e758 (`suites/s13_2.log`): **7808 passed, 11 failed, 10 skipped, 3 xfailed** en 6 min 41 s.
- En serie (`suites/s13_2_serie.log`), 9 de los 11 pasan: son las de interferencia del paralelo de siempre (calibración, `home_view`, `impresion_menu`, `ciclos_print`, `main_window`).
- Quedan 2 rojas ajenas: `test_config_correo.py::test_carga_el_archivo_del_repo` y `::test_descarta_destinos_invalidos`. Dependen de `data/correo_equipo.json` del PC de desarrollo, que no está versionado. Ya fallaban igual en L0 y no se tocó `data/`.
- **Total: 7817 passed** + 2 ajenas.
- Comparación con la línea base: la tanda 12 dio 7531; L0, ya en `dev`, dio 7591 + las mismas 2 ajenas. Las 226 nuevas son de S13.

La primera corrida, antes de 4.1 y de recalcular (`suites/s13_1.log`), dio 15 rojas: las 8 de valores viejos, la de 4.1, 4 del paralelo y las 2 ajenas.

## 7. Programas (decisión 7)
Los 8 programas del repo (`cycles/factory` y `cycles/user`) pasan `errores_programa` con la función nueva, sin errores:

| Programa | Consigna de chaqueta (kPa) | Advertencias |
|---|---|---|
| factory/bowe_dick | 330.2 | — |
| factory/instrumental_121 | 231.0 | — |
| factory/instrumental_134 | 330.2 | — |
| factory/liquidos | 231.0 | — |
| user/bowe_dick | 332.7 | `presion_chaqueta` + rango = 375 > 350 (ya existía; no depende de Psat) |
| user/instrumental_121 | 229.0 | — |
| user/instrumental_134 | 328.2 | Ídem, 375 > 350 |
| user/liquidos | 231.0 | — |

También pasan los programas de usuario del equipo, es decir, los de la G más la migración de la H. Se ensayó con `tools/ensayo_actualizacion_i.py` desde el código fuente: ninguno queda dañado ni rechazado (ver K13).

## 8. Documentos (decisión 6)
- Comentario de cabecera de `steam.py`.
- `CLAUDE.md`:
  - convenciones: IF97, validez y valores;
  - ejemplo de la consigna de chaqueta: 328.2;
  - nota de C-08: sigue igual con techo 313.2.
- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`, bloque T12 y fila E-T12-01 del índice: todas las cifras derivadas recalculadas, en 26 líneas.
  - Psat 304,2 / 308,7 / 205,0.
  - Techos 313,2 / 317,7 / 214,0, y techo de calentamiento con 11: 315,2.
  - Consignas 328,2 / 332,7 / 229,0, con banda 318,2–338,2.
  - Entrada a sostener P ≥ 302,2.
  - RECUPERACION: entrada bajo P < 302,7 y salida desde P ≥ 303,7; reapertura del techo bajo 311,2.
  - B&D: 306,7 y 407,7.
- LEEME de la entrega: sección «Cambios respecto a la H» (en K13).

## 9. Efecto conocido (decisión 8)
Con IF97, el techo a 134 °C con `presion_add_esterilizacion` 9 es 313.2 kPa, que equivale a Tsat ≈ 135.0 °C. Sigue por debajo del umbral de salida de RECUPERACION con brecha 1.0, que es 135.3 °C. **No cambia** el problema urgente 1 de `tanda12/DECISIONES_PARA_REVISAR.md`, que sigue pendiente para la tanda 14.

## 10. DECISIONES SIN CONFIRMAR y preguntas
1. **Rango en presión de `t_saturacion_c`:** es el equivalente exacto del rango en temperatura de la decisión 3, de Psat(0.01 °C) ≈ 0.6117 kPa a Psat(373.946 °C) ≈ 22064 kPa. La norma admite Ts(p) desde 611.213 Pa; entre 0.6112 y 0.6117 kPa ahora se lanza. No tiene efecto práctico.
2. **`catalogo_parametros._psat`** (4.1): única excepción a «solo `steam.py`». Sin ella, un programa de usuario corrupto quedaba reemplazado en silencio por el de fábrica.
3. **PREGUNTA (4.2):** lecturas fuera de 0–200 °C en vivo. Propuesta para la tanda 14: tratarlas como «sin lectura».
4. Comentario sin tocar en `ui_qml/domain/consignas.py`: dice «rango válido de `p_saturacion_kpa` 99–145». Sigue siendo el filtro de dibujo correcto, pero ya no es el rango de validez de la función. Es un comentario de código fuera de `steam.py` y se deja para no tocar otros archivos.
