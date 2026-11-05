# A14 — Diagnóstico: sobreimpulso en ESTERILIZACION y fallo por aislamiento CIC-16

Tanda 28, flujo C (rama `tanda28c`). Fecha: 5-nov. Informe del punto: `docs/informes/tanda28c/A_informe_c.md` (sección A14).

## Cómo se reprodujo

- Planta simulada `tests/helpers/planta_vapor.py`. Cámara con vapor y aire, la carga sigue a Tsat(P_v) y la sonda tiene retraso de 15 s. Pierde calor hacia el ambiente y el escape lento queda enclavado, como en el programa de fábrica.
  - Modo cámara: `vapor_camara` inyecta desde el suministro (350 kPa).
  - Modo chaqueta: `vapor_chaqueta` llena la chaqueta desde el suministro, y `vapor_camara`, abierta, pasa vapor de la chaqueta a la cámara en proporción a la diferencia de presión.
  - Los valores de la planta son PROVISIONALES. Sirven para comparar el control antes y después con la misma planta, no para predecir el equipo.
- El arnés corre las fases reales `CalentamientoFase` → `EsterilizacionFase` con `SetOutput` real y reloj monotónico virtual (0,5 s por tick). Reproduce el corte D-CHQ de CicloState y no usa backend ni puerto.
- Script: `python tests/banco/a14_diagnostico_esterilizacion.py --etiqueta antes|despues`, con `PYTHONPATH=<worktree>\src`. Las gráficas quedan en `docs/informes/tanda28/a14/`. En cada gráfica:
  - panel superior: T de la sonda;
  - panel medio: P de cámara, P de chaqueta, `P_control_max` y Psat(T_est);
  - panel inferior: duty del actuador (media móvil de 30 s) y aislamiento.
- Programa: fábrica `instrumental_134.json` (134 °C, `presion_add_esterilizacion` 15, `factor_esterilizacion` 70, `intervalo_segmentos_ester` 3 s).
  - «vigente» es el programa del repositorio antes de A14, con `brecha_segura_temperatura` 1,0 y 3,5 min de exposición.
  - Las variantes de 15 min muestran el régimen.
- Métrica «en banda»: fracción del tiempo de ESTERILIZACION con T en [T_est, T_est + 1 K].

Valores de referencia (IAPWS-IF97, `core/runtime/steam.py`):
- Psat(134) = 304,20 kPa.
- `P_control_max` = Psat(134) + 15 = 319,20 kPa.
- Con brecha 1,0, la salida de RECUPERACION exige T ≥ 135,3 °C, es decir P ≥ Psat(135,3) = 315,94 kPa: solo 3,26 kPa bajo el techo.
- Con brecha 0,3, la salida de RECUPERACION es 134,6 °C: `P_sp` = Psat(134,6) = 309,57 kPa y la banda queda en [307,6, 310,6] kPa, con 8,6 kPa de margen al techo.

## Resultados antes de A14 (código y programa vigentes)

| corrida | resultado | aislamientos | T máx (°C) | sobreimpulso (K) | T mín exp. (°C) | P máx (kPa) | en banda [T_est, T_est+1] |
|---|---|---|---|---|---|---|---|
| chaqueta_vigente | FALLO CIC-16 | 6 | 135.21 | 1.21 | 134.00 | 319.4 | 42% |
| camara_vigente | COMPLETADO | 0 | 135.30 | 1.30 | 134.01 | 319.8 | 17% |
| chaqueta_vigente_15min | FALLO CIC-16 | 6 | 135.21 | 1.21 | 134.00 | 319.4 | 42% |
| camara_vigente_15min | COMPLETADO | 0 | 135.31 | 1.31 | 134.01 | 319.8 | 6% |
| chaqueta_brecha_1_0_15min | FALLO CIC-16 | 6 | 135.21 | 1.21 | 134.00 | 319.4 | 42% |
| camara_brecha_1_0_15min | COMPLETADO | 0 | 135.31 | 1.31 | 134.01 | 319.8 | 6% |
| chaqueta_brecha_0_3_15min | COMPLETADO | 5 | 135.11 | 1.11 | 134.00 | 319.4 | 81% |
| camara_brecha_0_3_15min | COMPLETADO | 0 | 134.92 | 0.92 | 134.01 | 319.6 | 100% |

Gráficas: `a14/antes_<corrida>.png`.

La simulación del modo chaqueta reproduce el fallo del equipo de pruebas (alpha.16, 5-nov):
- entra a ESTERILIZACION con 134,0 °C / 306,3 kPa, en el equipo 134,2 °C / 305,8 kPa;
- en RECUPERACION, `vapor_chaqueta` queda ON continuo y la chaqueta sube a ≈339 kPa;
- la cámara llega al techo de 319,2 kPa y se aísla;
- reabre al bajar a 316,2 kPa sostenido 3 s y vuelve al techo en ≈5 s;
- a los 6 aislamientos, CIC-16.

En la simulación los 6 aislamientos llegan en ≈100 s. En el equipo tomaron más tiempo, porque la chaqueta real tiene otra dinámica (valores provisionales).

## Confirmación de las causas

- **(a) La banda PWM sigue a la temperatura medida: confirmada (modo cámara).** Ver `antes_camara_brecha_0_3_15min.png`.
  - Con la brecha ya en 0,3 y sin M1, la banda `[Psat(T_actual) − 2, Psat(T_actual) + 1]` arrastra la presión con la temperatura en los dos sentidos. Mientras T sube, la banda sube con ella y sostiene P cerca del techo: P máx 319,6 kPa y T máx 134,92 °C.
  - Cuando T baja, la banda baja, P cae, T sigue bajando y vuelve a entrar a RECUPERACION, que lleva otra vez la presión hasta el techo. Resultado: un diente de sierra de ≈3,5 min entre 134,3 y 134,9 °C.
  - Con la brecha en 1,0 (`antes_camara_vigente_15min.png`), la temperatura queda en ≈135,3 °C: el 94 % del tiempo fuera de [T_est, T_est + 1].
- **(b) Con brecha 1,0 la salida de RECUPERACION queda a 3,3 kPa del techo: confirmada.**
  - En modo chaqueta (`antes_chaqueta_vigente.png`), T nunca llega a 135,3 °C (máx 135,21 °C), porque el aislamiento corta antes. El control nunca sale de RECUPERACION, de modo que `vapor_chaqueta` queda ON continuo y el ciclo termina en CIC-16.
  - El prompt habla de unos 3,6 kPa; con IF97 el margen es 3,26 kPa (hallazgo AJ28C-01).
- **(c) En modo chaqueta, la chaqueta da sobreimpulsos mayores que la banda: confirmada.** Ver `antes_chaqueta_brecha_0_3_15min.png`.
  - Aun con la brecha en 0,3, la presión de chaqueta acumulada (≈339 kPa, 20 kPa sobre el techo de cámara) empuja la cámara al techo cada vez que el control abre la chaqueta. Hubo 5 aislamientos en 15 min, uno menos que el disparo de CIC-16.
  - La cámara hereda la presión de la chaqueta. Ni el duty de `factor_esterilizacion`, pensado para `vapor_camara`, ni la banda la limitan (VCH-01).

Conclusión: ninguna de las tres medidas basta sola en modo chaqueta. M3 (brecha 0,3) deja el control salir de RECUPERACION. M1 (banda anclada a `P_sp`) evita que la presión siga a la temperatura. M2 (chaqueta acotada a `P_sp + margen_chaqueta_est`) impide que la chaqueta empuje la cámara al techo.

## Resultados con M1 + M2 + M3

(Se completa en el commit A14-M3; ver abajo.)
