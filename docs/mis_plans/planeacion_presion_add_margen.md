# Planeación: presión añadida como margen de trabajo sobre saturación (PAM)

Fecha: 9-nov-2026. Base: rama `dev` (incluye tanda 33, cascada CAS, y tanda 34). Equipo de referencia: SN260001 (modo chaqueta).
Estado: criterio aprobado por Cristian el 9-nov (puntos 1 y 2 de la propuesta). Valores marcados `DECISIÓN SIN CONFIRMAR` quedan a confirmar en banco.

## 1. Problema

1.1. Evidencia (respaldo `respaldo_SN260001_20261109_102755.zip`, alpha.24):

- Ciclo 26 (Líquidos, 121 °C, CIC-04). La Principal (`temp_camara`, dentro del líquido) solo llegó a 121,0 °C con el empuje de líquidos (cámara ≈227 kPa). En ESTABLE_PREESTERILIZACION la presión se bajó a ≈207 kPa. Al entrar a ESTERILIZACION (121,1 °C, 208,6 kPa) la cámara subió a 217,5 kPa en 4 s (aislamiento, techo 216,0) y luego cayó linealmente (≈0,4 kPa/s) hasta 201,4 kPa sin recuperarse: CIC-04.
- Ciclo 27 (Instrumental 121, sólido, cancelado en CALENTAMIENTO a los ≈12 min). Cámara estable en 207–208 kPa (Psat ≈121,4 °C); Principal en 120,6–120,8 °C; `temp_2_camara` (no en uso) en 121,4–121,5 °C. La Principal nunca llegó a 121,0 °C y la fase nunca entró a ESTABLE_PREESTERILIZACION.
- En los dos ciclos, con vapor estable, la Principal lee entre 0,4 y 0,8 K por debajo de Tsat(P_cámara).

1.2. Causa en el código:

- CALENTAMIENTO apunta a `p_obj = Psat(t_obj)` y el aporte de vapor llega a cero en `p_obj + rango_calentamiento_pres` (2 kPa). El techo `Psat(t_obj) + presion_add_calentamiento` nunca se usa como margen de trabajo. Con la Principal leyendo bajo, la presión queda clavada en ≈207 kPa y la temperatura objetivo no se alcanza.
- Con carga líquida, después del empuje la fase obliga a bajar a `Psat(t_obj) + 2` antes de ESTABLE (`bajando_a_psat`, `p_max_entrada`). Esto descarta la presión que hizo falta para que la Principal llegara a t_obj.
- ESTERILIZACION fija `P_sp = Psat(T_est + brecha_segura_temperatura + 0,3)` sin relación con la presión de trabajo real. La cámara llega desde CALENTAMIENTO por debajo de la banda, y en modo chaqueta la cascada pasa a nivel «baja» (consigna 350 kPa) o, en la alpha.24, la exención M2-REC-01 da vapor sin límite de chaqueta. Resultado: pulso largo, aislamiento y luego una cámara sin reserva.

1.3. Criterio de Cristian (9-nov): la presión añadida es el margen por encima de Psat que tolera un desfase presión/temperatura por error de sensores o calibración antes de considerar gases no condensables. La presión puede trabajar hasta `Psat + presion_add`; no es una presión que deba alcanzarse.

## 2. Alcance

Incluido: CALENTAMIENTO (rampa, entrada y sostenimiento de ESTABLE_PREESTERILIZACION), la consigna de ESTERILIZACION (`P_sp`), la coherencia T–P de CALENTAMIENTO (C-02) y la detección de aire de ESTERILIZACION (C-03). Modo chaqueta y modo cámara.

Fuera de alcance: fallas de temperatura y de presión de ESTERILIZACION (incluida CIC-04, que no cambia), F0, C-13, VCH-AIS, D-CHQ, la cascada salvo su referencia, PREVACIO, DESCOMPRESION y SECADO. RECUPERACION en modo cámara (ver hallazgo PAM-H2).

## 3. Diseño

### PAM-01 Rampa de CALENTAMIENTO gobernada por temperatura

- Mientras la Principal no haya alcanzado `t_obj` (enclave existente `_t_obj_alcanzada`, 5 s sostenidos, ahora para toda carga), el objetivo de presión de la rampa con carga sólida es `p_obj_rampa = p_techo_rampa - MARGEN_EMPUJE_KPA`, con `p_techo_rampa = Psat(t_obj) + presion_add_calentamiento`.
- Con carga líquida el empuje no cambia: objetivo `Psat(t_obj) + presion_add_liquido_calentamiento` y techo `Psat(t_obj) + presion_add_calentamiento + presion_add_liquido_calentamiento`, como hoy (ajuste 7-nov). Aplicar el margen sobre el techo ampliado subiría el objetivo de líquidos (de 225 a 232 kPa con los valores de SN260001), un cambio de ajuste que no se pidió.
- `MARGEN_EMPUJE_KPA` = `histeresis_cierre_camara` del programa + 1 (4 kPa con los valores actuales), para que el empuje no llegue al aislamiento. `DECISIÓN SIN CONFIRMAR`.
- Los términos de tasa, proximidad, sobrepaso y calidad de vapor (C-09) no cambian; solo cambia la referencia de presión del término de proximidad y de sobrepaso. La temperatura sigue con `t_obj`.
- El empuje deja de ser exclusivo de líquidos: con carga sólida usa solo `presion_add_calentamiento`. `presion_add_liquido_calentamiento` se conserva con su significado (extra de líquidos sobre el techo durante el empuje).

### PAM-02 Presión de trabajo (P_trabajo)

- Al enclavar `t_obj`, se fija `P_trabajo = clamp(P_cámara, Psat(t_obj), p_techo - MARGEN_EMPUJE_KPA)` con el techo normal (sin el extra de líquidos).
- El desfase `d = P_trabajo - Psat(t_obj)` (≥ 0) es la medida, en kPa, de la diferencia entre la Principal y la saturación de la presión medida. Se registra en el log y en `estado` (solo publicación) al fijarse y en cada cambio.
- Adaptación: si dentro de ESTABLE_PREESTERILIZACION la ventana se reinicia porque la Principal quedó bajo `t_obj`, `P_trabajo` sube 1 kPa (`PASO_TRABAJO_KPA`) sin pasar de `p_techo - MARGEN_EMPUJE_KPA`. Una sola subida por reinicio. `DECISIÓN SIN CONFIRMAR`.
- `P_trabajo` vive en la instancia del ciclo (se pierde con un reinicio, como los demás temporizadores de fase).

### PAM-03 Entrada y sostenimiento de ESTABLE_PREESTERILIZACION

- Entrada: `T >= t_obj` y `Psat(t_obj) - 2 <= P <= P_trabajo + 1`. Se retira el requisito de líquidos de bajar a `Psat(t_obj) + 2` (`p_max_entrada` y `bajando_a_psat` pasan a referirse a `P_trabajo + 1`). Tras el empuje de líquidos sigue sin vapor mientras `P > P_trabajo + 1`.
- Banda de sostenimiento: sin cambio (`t_obj <= T <= t_obj + rango_temp_estabilizacion` y `Psat(t_obj) - 2 <= P <= p_techo`).
- Control de presión en sostenimiento: la referencia pasa de `Psat(t_obj)` a `P_trabajo`. En modo chaqueta es la cascada CAS-03 (`p_ref = P_trabajo`, mismo techo). En modo cámara, el objetivo de la rampa en sostenimiento es `P_trabajo`.
- VCH-AIS y el techo ampliado del empuje no cambian.

### PAM-04 Herencia en ESTERILIZACION

- `P_sp = min(max(Psat(T_est + brecha_segura_temperatura + 0,3), Psat(T_est) + d), P_control_max - 3)`, calculada una sola vez al entrar a la fase (como hoy, A14-M1). Con `d` sin dato (no hubo enclave, por ejemplo un reinicio), `d = 0`: comportamiento actual.
- El `- 3` deja la banda alta (`P_sp + 1`) al menos 2 kPa bajo el techo de aislamiento. `DECISIÓN SIN CONFIRMAR`.
- Rige para la banda PWM (modo cámara) y para la referencia de la cascada CAS-02 (modo chaqueta). Con esto la cámara entra a ESTERILIZACION dentro de la banda y la cascada no arranca en nivel «baja».
- Las fallas siguen contra `T_est` fija: CIC-04 en `Psat(T_est) - brecha_error_presion`, temperatura baja en `T_est - brecha_error_temperatura`, etc.

### PAM-05 Margen de no condensables ligado a la presión añadida

- C-03 (ESTERILIZACION, solo sólidos), lado de aire: falla CIC-12 cuando `P - Psat(T_principal) > tolerancia_aire` (debounce acumulado actual), con `tolerancia_aire = min(presion_add_esterilizacion, Psat(T_principal + 2) - Psat(T_principal))`. Nunca es más permisiva que el umbral actual de 2 K (≈11,3 kPa a 121 °C, ≈15,6 kPa a 134 °C).
- C-02 (CALENTAMIENTO, solo sólidos), lado de aire: coherente si `P - Psat(T_principal) <= min(presion_add_calentamiento, Psat(T_principal + 2) - Psat(T_principal))`. Hoy es `|Tsat(P) - T| <= 1 K`; el lado de aire se amplía hasta el margen de presión añadida, sin pasar de 2 K.
- El lado de vapor sobrecalentado no cambia: C-03 `dT < -2 K` → CIC-13, y C-02 `Tsat(P) - T >= -1 K`.
- Los mensajes de CIC-12 y del log de C-02 muestran el valor y el límite en kPa.

### PAM-06 Regla de coherencia brecha segura / brecha de error

- `brecha_segura_presion < brecha_error_presion` pasa a regla de coherencia al guardar y al cargar (código nuevo en `catalogo_parametros`, texto es/en). Sin ella, RECUPERACION por presión dispara después de la falla.
- El programa Líquidos de SN260001 tiene hoy 3,0 y 2,0 (cambio intencional de Cristian). Recomendación: rechazar al guardar y, al cargar, avisar SIS-06 sin migrar (el operador corrige). Pendiente de confirmación de Cristian (PAM-P1).

### 3.7 Ejemplo: Líquidos en SN260001 (121 °C, presion_add 11, extra de líquidos 20, histéresis 3)

- Empuje sin cambio: objetivo 225,0 kPa, techo ampliado 236,0. En el ciclo 26 la Principal (en el líquido) llegó a 121,0 °C con ≈227 kPa.
- `P_trabajo = clamp(227, 205,0, 216,0 - 4) = 212,0`; `d = 7,0`.
- Sin vapor hasta `P <= 213,0` (antes había que bajar a 207,0). Entrada a ESTABLE con `T >= 121,0` y `203,0 <= P <= 213,0`; sostenimiento en 212,0 (Tsat ≈121,8 °C), no en 205,0.
- ESTERILIZACION: `P_sp = min(max(206,9, 212,0), 216,0 - 3) = 212,0`; banda 210,0–213,0; entra dentro de la banda (sin nivel «baja» de la cascada, sin pulso ni aislamiento). Margen hasta CIC-04 (203,0): 7–10 kPa, contra ≈4 kPa hoy.

## 4. Hallazgos

- PAM-H1 (ALTA): la Principal lee 0,4–0,8 K bajo Tsat(P) en los ciclos 26 y 27, y `temp_2_camara` lee ≈Tsat(P). Antes del banco hay que comparar las dos sondas y el transmisor de cámara contra patrón a 121 °C. Si la Principal está descalibrada, se corrige con calibración y PAM solo absorbe el residual; si está bien y el punto es realmente más frío (condensado o aire en el drenaje), es un hallazgo de proceso que PAM no debe ocultar.
- PAM-H2 (MEDIA): en modo cámara, RECUPERACION de ESTERILIZACION sale solo con `T >= T_est + brecha + 0,3`; con la Principal leyendo bajo queda en vapor continuo hasta el techo con la histéresis C-08.3. Fuera de alcance; se revisa cuando haya datos de un equipo de mesa.
- PAM-H3 (MEDIA): sin presión de chaqueta ni estado de válvulas en la base del historial, la caída del ciclo 26 tras el aislamiento no se puede atribuir con certeza (descarga de chaqueta, corte M2 con el sensor de chaqueta leyendo alto). Falta el log de la estación del 9-nov 9:17–9:57.

- PAM-H4 (MEDIA, solo parámetros): en Líquidos, `escape_lento_on_ester` 1 / `escape_lento_off_ester` 0 deja el escape lento enclavado abierto toda la exposición. En el ciclo 26 la cámara perdió ≈0,4 kPa/s sin vapor (≈0,2 kPa/s en CALENTAMIENTO con la carga más fría). Es una salida fija que la chaqueta debe reponer. Propuesta de banco: comparar con escape lento pulsado (p. ej. 1 s / 10 s). No se cambia el valor de fábrica sin el dato.
- PAM-H5 (ALTA, precondición): en ESTERILIZACION la cascada repone desde la chaqueta con `pres_chaqueta`; HAZ-CAS-02 sigue vigente (calibrar el sensor de chaqueta con patrón antes del banco).

## 5. Riesgos (para `docs/riesgos/registro_riesgos.md`)

- HAZ-PAM-01: la presión de trabajo puede quedar hasta `presion_add_calentamiento` sobre Psat(t_obj); la carga puede quedar hasta ≈2 K sobre el setpoint. Control: tope `p_techo - MARGEN_EMPUJE_KPA`, falla de temperatura alta de ESTERILIZACION sin cambio.
- HAZ-PAM-02: una Principal que pierde contacto y lee bajo empuja `P_trabajo` al tope. Control: tope fijo, falla de temperatura baja sin cambio, registro de `d` en el log y en el ticket (ver 6.4).
- HAZ-PAM-03: C-03/C-02 con tolerancia en kPa. Control: nunca más permisiva que 2 K.

## 6. Requisitos para la implementación

6.1. Constantes nuevas en `calentamiento.py`: `PASO_TRABAJO_KPA = 1.0`; `MARGEN_EMPUJE_KPA` calculado de `histeresis_cierre_camara + 1`. Sin parámetros de programa nuevos.

6.2. `estado.presion_trabajo` (kPa) y `estado.desfase_trabajo` (`d`), solo publicación; None fuera de ciclo y antes del enclave. ESTERILIZACION lee `d` de ahí.

6.3. Log: una línea al fijar `P_trabajo`, una por cada subida y una al entrar a ESTERILIZACION con `P_sp`, `d` y el origen («heredada» o «calculada»).

6.4. Ticket: línea informativa «Presión de trabajo: Psat + d kPa» al entrar a ESTERILIZACION (es/en). `DECISIÓN SIN CONFIRMAR`.

6.5. Pruebas: rampa con la Principal 0,6 K bajo Tsat(P) (sólido y líquido) llega a ESTABLE y a ESTERILIZACION; entrada a ESTERILIZACION sin nivel «baja» de la cascada; `P_trabajo` nunca supera el tope; `d = 0` sin enclave da el comportamiento actual; C-03 y C-02 con la tolerancia nueva y nunca por encima de 2 K; regla PAM-06; planta simulada (`tests/helpers/planta_vapor.py`) con un desfase de sonda de 0,6 K para Líquidos e Instrumental 121, en caudal abierto y restrictivo.

6.6. Trazabilidad: REQ nuevos uno por PAM-01..06; banco: bloque PAM en la hoja de pruebas.

## 7. Pendiente de Cristian

- PAM-P1: tratamiento de un programa que incumple PAM-06 al cargar (recomendado: aviso SIS-06 sin migrar).
- PAM-P2: verificación contra patrón de la Principal, `temp_2_camara` y el transmisor de cámara (PAM-H1).
- PAM-P3: log de la estación del 9-nov (PAM-H3).
