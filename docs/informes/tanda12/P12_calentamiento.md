# P12 — CALENTAMIENTO (tanda 12)

Rama `tanda-12-p12` desde `tanda-12` (c462114). Archivo de código tocado: solo
`src/autoclave/state_machine/cycle_phases/calentamiento.py` (encabezado del módulo actualizado).

## Qué se hizo, por punto

**C-01 (`presion_add_calentamiento` es solo techo)**
- `p_obj = Psat(T_obj)` sin sumar `presion_add`; lo usan `duty_proximidad`, `sobrepaso` y el log de inicio.
- Entrada a ESTABLE_PREESTERILIZACION: `T >= T_obj` y `P >= p_obj - 2`.
- Banda de sostenimiento: `T_obj <= T <= T_obj + rango_temp_estabilizacion` y `Psat(T_obj) - 2 <= P <= Psat(T_obj) + presion_add`.
- Techo independiente: `P >= Psat(T_obj) + presion_add` pone el duty en 0 (antes era 2 × presion_add).
- `_duty_por_calidad_vapor(temp, pres, t_obj)` exige `P >= Psat(T) - 2` (se quitó el parámetro `p_add`).
- Constante de módulo `_TOLERANCIA_PSAT_KPA = 2.0`.

**C-02 (coherencia T–P)**: en la banda, `|Tsat(P) - T_principal| <= _COHERENCIA_TP_K (1.0)` usando `t_saturacion_c`. Si no hay coherencia, el tick cuenta como fuera de banda: la ventana se reinicia y se arma el timeout de recuperación que ya existía. El log (WARNING) muestra Tsat(P), T y la diferencia. Se escribe solo cuando se pierde la coherencia, no en cada tick. Si `t_saturacion_c` lanza `ValueError`, el tick se trata como incoherente. No se exige con `tipo_carga == "liquido"`.

**C-09**: `_FACTOR_TOPE_TEMPERATURA = 0.97` se reemplazó por `T >= T_obj - _MARGEN_CALIDAD_VAPOR_K (3.0)`.

**C-13.7b (ventana)**: `refs_en_consigna` ignora las Referencias en `None` o ausentes. Las que sí leen tienen que estar en `>= T_obj`.

## Commits
- `c038db0` test(tanda12-p12): pruebas nuevas (en rojo)
- `52298d6` feat(tanda12-p12): implementación y actualización de las pruebas existentes
- `9cebf0a` fix(tanda12-p12): la coherencia se exige salvo con `liquido` (falla segura)
- el commit de este informe

## Pruebas nuevas
- `tests/test_t12_c01_calentamiento_techo.py`: entra con -1.9 y no entra con -2.1; completa en Psat; techo en 1× y no en 2×; con aire (Psat+30) el duty queda en 0, la ventana no arranca y aparece "techo" en el log; el log usa p_obj sin el add; calidad de vapor con Psat(T)-2.
- `tests/test_t12_c02_coherencia_tp.py`: 1.2 K reinicia la ventana y arma la recuperación; si se sostiene, termina en FALLO; con 0.8 K completa; con líquido no se exige; con sólido explícito sí; con `tipo_carga` vacío se trata como sólido.
- `tests/test_t12_c09_tope_calidad_vapor.py`: con 121 el corte empieza en 118.0 (a 117.5 y 117.99 no corta); con 134, en 131.0.
- `tests/test_t12_c13_7b_ventana_referencia_sin_lectura.py`: una Referencia en None o ausente no bloquea y completa; con dos Referencias, una None y otra en consigna, completa; con una None y otra fría, bloquea; una Referencia fría bloquea.

Resultado exacto, con `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-ab992c69a691fd932\src\autoclave\__init__.py`:
- Las 4 pruebas nuevas, las de calentamiento y las de los módulos que importan la fase o corren el ciclo completo (85 archivos de `tests/` que mencionan `states.ciclo`/`CicloState`/simulador/calentamiento, sin los de QML): **1793 passed, 10 skipped** (`pytest -n auto`).
- Tras el último fix, el subconjunto de calentamiento y simulador: **279 passed, 3 skipped**.

## Pruebas existentes modificadas (y por qué)
- `tests/test_calentamiento_fase.py`:
  - `p_obj = Psat(134) + 11` pasa a `Psat(134)` en todas las pruebas (C-01.1). Con el valor viejo la presión quedaba justo en el techo nuevo y fuera de coherencia.
  - `test_no_completa_si_falta_presion_aunque_temp_llegue`: ahora usa `Psat - 2.1`, porque `Psat` sin el add ya es el objetivo.
  - `test_duty_calidad_vapor_no_restringe_dentro_de_sostenimiento`: `p_min_para_temp` pasa a `Psat(134.5) - 2`.
  - Las 3 pruebas puras de `_duty_por_calidad_vapor` pierden `p_add`, usan el tope de 131 en vez de 129.98 y `Psat(T) - 2` (C-01.5 y C-09). Una se renombró a `test_duty_por_calidad_vapor_sin_restriccion_bajo_el_tope`.
  - Se actualizaron comentarios que hablaban del 97 %.
- `tests/test_q1_r1p3_rango_calentamiento.py`: `P_OBJ = Psat(134)` (C-01.1).
- `tests/test_t3_sensores_ciclo.py` (solo la sección de CALENTAMIENTO): la presión de `_calentamiento_con_referencia` y la de `test_principal_temp_2_camara...` pasa a `Psat(134)` (C-01). **Ojo al unir con E12**, que puede tocar otras secciones de este archivo.
- `tests/test_t8_s2a_ensayo_simulador.py` (`_evento_d8210`, solo con `con_referencia`): la planta simulada publica `temp_ref = T - 0.2`. Con la semántica nueva el Principal se estabiliza justo sobre T_obj, así que esa Referencia nunca llegaba a la consigna y el ciclo terminaba en FALLO_CALENTAMIENTO (cal_no_sostuvo) antes de DESCOMPRESION, que es lo que ensaya el evento. Para este evento la Referencia se publica 0.2 K **por encima** del Principal, coherente con el contexto físico confirmado (el Principal está en la zona más fría). Ver la pregunta 1.
- `tests/test_s2b_revision_correcciones.py` **no** se tocó: la lectura de `tipo_carga` se movió al tramo de sostenimiento para no romper su mock (`get_param` sin `default`).

## DECISIONES SIN CONFIRMAR
1. **"Con aire no entra a sostener" (C-01).** Se siguió literalmente C-01.2: con T = T_obj y P = Psat + 30 la fase sí pasa internamente a ESTABLE_PREESTERILIZACION, porque P >= p_obj - 2. Pero queda fuera de banda (techo y coherencia): la ventana no arranca, `fase_en_sostenimiento` sigue en False, el duty queda en 0 y se arma el timeout de recuperación. Si no se corrige en `timeout_recuperacion_estabilizacion`, termina en FALLO `cal_no_sostuvo`. La prueba comprueba "no sostiene" en ese sentido. No se agregó `P < techo` a la condición de entrada porque las decisiones no lo piden.
2. **`tipo_carga` distinto de `solido`/`liquido` (ausente, nulo o vacío)**: se trata como sólido y se exige la coherencia. Es la opción segura, porque solo puede alargar el calentamiento o terminar en FALLO. Para los valores válidos es idéntico a "solo con `solido`".
3. Si no se puede calcular Tsat(P) (P <= 0), el tick se trata como incoherente (fuera de banda).

## PREGUNTAS PARA CRISTIAN
1. **Referencia más fría que el Principal.** Con C-01, el objetivo de presión es Psat(T_obj) y el término de sobrepaso corta el vapor a `rango_calentamiento_pres` (2 kPa, unos 0.2 K) sobre él. El Principal queda entonces unas décimas por encima de T_obj (en el simulador, 134.0–134.1 °C). Antes, p_obj incluía `presion_add` y lo empujaba más o menos 1 K arriba. La ventana exige que cada Referencia que lee esté en `>= T_obj`. Si en el equipo una Referencia lee de forma sostenida aunque sea 0.1–0.2 K menos que el Principal, el ciclo nunca completa CALENTAMIENTO y termina en FALLO `cal_no_sostuvo`. Así salió en el simulador, con la Referencia a T - 0.2. Si el Principal de verdad está en la zona más fría, no debería pasar. ¿Se acepta, o se quiere una tolerancia para las Referencias en la ventana? Vale la pena observarlo el lunes si hay Referencia asignada.
2. Relacionado: con p_obj = Psat(T_obj) y `rango_calentamiento_pres = 2`, el control de proximidad deja de inyectar a +2 kPa sobre Psat. Si la cámara pierde algo de presión por el escape lento enclavado, la ventana puede oscilar en el borde inferior (Psat - 2). Conviene ver en el banco si la ventana completa sin reinicios.

## NECESITA DE OTRA ETAPA
- Ninguna dependencia de código. `t_saturacion_c` ya estaba en A0.
- Para la sesión principal (Z): actualizar en `CLAUDE.md` la descripción de CALENTAMIENTO (p_obj sin presion_add, techo 1×, tope de calidad de vapor en T_obj - 3 K, coherencia T–P, Referencia sin lectura).

## Pendientes
- Nada abierto dentro del alcance de P12.
