# Control en cascada de la chaqueta (CAS) — 7-nov-2026

Especificación para la tanda 33. Aplica solo al modo chaqueta (`estado.modo_vapor == "chaqueta"`, equipos de piso). El modo cámara (equipos de mesa) no cambia.

## 1. Diagnóstico (ciclos 21 y 23 de SN260001, alpha.21 y alpha.23, Líquidos 121 °C)

- Calentamiento con el empuje de líquidos (`presion_add_liquido_calentamiento` = 20): la cámara se sostiene en ≈227 kPa ~20 min; la chaqueta entra a ESTERILIZACION en 220–231 kPa.
- ESTERILIZACION: P_sp = 208,9 kPa (banda 206,9–209,9), techo `P_control_max` = 216,0, umbral A14-M2 = P_sp + 8 = 216,9. M2 corta desde el primer tick. Sin histéresis, M2 suelta ~1 s cada vez que la chaqueta toca 216,9: `vapor_chaqueta` abre, la chaqueta sube 5–10 kPa por segundo (suministro 350 kPa) y vuelve a cortar (5 veces en 40 s). Una de esas aperturas lleva la cámara al techo en ~2 s → aislamiento VCH-AIS (el «pulso alto» que ve Cristian en la gráfica).
- Tras el aislamiento la chaqueta sigue sobre el umbral, M2 la mantiene cerrada y la cámara cae ≈0,35 kPa/s (escape lento enclavado + condensación sobre la carga) hasta 201,5 kPa → CIC-04 a los ~83 s.
- Lectura incoherente: con la válvula de asiento abierta entre cámara y chaqueta (sin otra restricción, dato de Cristian), la chaqueta marca 12–13 kPa más que la cámara a ~208 kPa y coincide cerca de la atmosférica (74 / 77,8 kPa). Es la firma de un error de ganancia del transmisor de chaqueta, que no está calibrado con patrón (solo el de cámara). Con ese error, M2 corta cuando la chaqueta real está a la presión de la cámara: no queda diferencia de presión que empuje vapor y la cámara no se repone.
- `brecha_segura_temperatura` 0,3 → 0,0 no cambia el mecanismo (M2 manda sobre RECUPERACION y PWM) y deja el borde bajo de la banda a 2 kPa del fallo.
- La alpha.24 (M2-REC-01) exime a M2 bajo la banda: corrige el bloqueo pero deja un control todo-nada en el borde bajo y conserva el castañeteo de M2.

## 2. Decisiones de Cristian (7-nov, «todo como recomiendas»)

1. Fases: ESTERILIZACION y ESTABLE_PREESTERILIZACION (incluida la bajada a saturación tras el empuje de líquidos). La rampa de CALENTAMIENTO no cambia.
2. En modo chaqueta el nivel lo decide solo la presión de cámara, no la temperatura de la sonda. La RECUPERACION por temperatura sigue rigiendo el modo cámara. El aire en sólidos lo sigue vigilando C-03.
3. En modo chaqueta, en esas fases, la cascada reemplaza el PWM, el corte A14-M2 y la exención M2-REC-01. Sin cambio: VCH-AIS, D-CHQ, alivios, fallos, debounce, F0, C-03, C-13, exposición.
4. Tres niveles de consigna de chaqueta, histéresis de válvula de 3 kPa (ver §3, con el ajuste de diseño de §4).
5. Modo cámara sin cambio.
6. Planta simulada (121 °C líquidos y 134 °C sólidos), revisión de seguridad, riesgo nuevo, bloque de banco, migraciones con auditoría y `.bak` si hicieran falta.
7. Esta vez la tanda compila la entrega al final, solo con la suite completa en verde y la revisión de seguridad sin bloqueantes.

## 3. Diseño

Arquitectura física sin cambio: el vapor entra solo a la chaqueta por `vapor_chaqueta`; `vapor_camara` queda abierta y la cámara se llena por igualación a través de la válvula de asiento. Cambia solo la regla que decide `vapor_chaqueta`.

### CAS-01 Componente puro `state_machine/cycle_phases/cascada_chaqueta.py`

Entradas por tick: `pres_camara`, `pres_chaqueta`, `p_ref`, `p_techo`, `margen_est` (= `esterilizacion.margen_chaqueta_est` vía `corte_chaqueta_consigna.margen_kpa`), límites del equipo (`presion_max_chaqueta_control`, `presion_suministro_vapor`, de `limites_equipo`) y el estado previo de la válvula.

Nivel de cámara (umbrales iguales a la banda PWM de A14-M1):
- `baja`: `pres_camara < p_ref − 2,0`
- `alta`: `pres_camara > p_ref + 1,0`
- `banda`: el resto.

Consigna de chaqueta:
- `tope = min(p_techo − MARGEN_TECHO_KPA, presion_max_chaqueta_control − 10, presion_suministro_vapor)`, con `MARGEN_TECHO_KPA` = 2,0.
- `baja` → `tope`.
- `banda` → `min(p_ref + margen_est, tope)`.
- `alta` → sin consigna: `vapor_chaqueta` OFF forzado.
- Si `tope < p_ref + 1`, se usa `tope` igual (nunca se supera el techo) y se registra una advertencia una sola vez por fase.

Válvula (todo-nada con histéresis bajo la consigna, `HISTERESIS_KPA` = 3,0):
- ON si `pres_chaqueta <= consigna − 3`; OFF si `pres_chaqueta >= consigna`; entre medio, conserva el estado anterior.
- OFF sin lectura válida de `pres_chaqueta` o de `pres_camara` (None, no finita o ≤ 0): falla cerrada.
- Al cambiar de nivel se reevalúa con la nueva consigna en el mismo tick.

Salida: decisión ON/OFF, nivel, consigna y motivo (para log y publicación). Log sin bitácora: una línea en cada cambio de nivel o de consigna, con `pres_camara`, `pres_chaqueta`, nivel y consigna; nunca por tick. Publicación de solo lectura: `estado.cascada_chaqueta = {nivel, consigna, valvula}` (None fuera de las fases).

### CAS-02 ESTERILIZACION (modo chaqueta)

- `p_ref = self.p_sp` (A14-M1, fija en la fase); `p_techo = P_control_max`.
- La cascada decide `vapor_chaqueta` en lugar de `_vapor_on()` / `_control_vapor_pwm()` / `_corte_consigna_chaqueta()` / exención M2-REC-01.
- Prevalecen como hoy: aislamiento VCH-AIS (las dos válvulas OFF), `estado.inhibir_vapor_chaqueta` (D-CHQ, sin suministro, sin lectura) y el corte duro de CICLO después de `fase.update()`. `vapor_camara` abierta salvo aislamiento.
- `_en_recuperacion` se sigue calculando para log y publicación, pero no decide la válvula en modo chaqueta.
- `factor_esterilizacion` e `intervalo_segmentos_ester` dejan de usarse en modo chaqueta (documentarlo; siguen en modo cámara).

### CAS-03 CALENTAMIENTO (modo chaqueta)

- La cascada decide `vapor_chaqueta` cuando `self._en_sostenimiento` (ESTABLE_PREESTERILIZACION) o, con carga líquida y empuje (`add_liq > 0`), desde que `_t_obj_alcanzada` queda enclavada (incluye `bajando_a_psat`).
- `p_ref = p_obj = Psat(t_obj)`; `p_techo` = techo normal `Psat(t_obj) + presion_add_calentamiento` (no el ampliado del empuje). Durante `bajando_a_psat` la cámara está sobre `p_ref + 1` → nivel `alta` → OFF, como hoy.
- La rampa previa (y su A14-M2 con el techo ampliado del empuje) no cambia. VCH-AIS sigue con el techo que usa hoy (ampliado durante empuje y bajada, MEDIA-1).
- La banda de sostenimiento, la coherencia T-P, las Referencias y el timeout de recuperación no cambian.

## 4. Ajuste de diseño respecto a lo aprobado (propuesta de Claude, Cristian puede vetarlo antes de lanzar)

Cristian confirmó que entre cámara y chaqueta solo hay la válvula de asiento, sin restricción: con esa válvula abierta las dos son un solo volumen, y la presión que alcanza la chaqueta termina siendo la de la cámara. Por eso:
- La consigna máxima se ata al techo de aislamiento (`P_control_max − 2`) en lugar de `P_sp + 20`: una chaqueta por encima del techo terminaría aislando la cámara. A 121 °C con `presion_add_esterilizacion` 11 el tope es 214 kPa; con 15, 218 kPa. No se crea el parámetro `margen_chaqueta_recuperacion`.
- El nivel `alta` apaga la válvula en lugar de llevar la chaqueta a P_sp: con un sensor de chaqueta que lea bajo, «llevar a P_sp» podría abrir vapor con la cámara ya alta.
Todos estos valores (`HISTERESIS_KPA` 3, `MARGEN_TECHO_KPA` 2, umbrales −2/+1, OFF en `alta`) son `DECISIÓN SIN CONFIRMAR` hasta el banco.

## 5. Programas

- `cycles/factory/liquidos.json` y `cycles/user/liquidos.json`: `esterilizacion.presion_add_esterilizacion` 11 → 15 (techo 220 kPa a 121 °C; cumple COHERENCIA_RECUPERACION ≥ 10,6, máximo 30, alivio 385; mismo valor que 134 °C). No se migran programas instalados.
- Sin parámetros nuevos ni retirados (no hace falta migración).

## 6. Precondición de banco

Calibrar `pres_chaqueta` con patrón antes del primer ciclo (pantalla de calibración por canal AI que ya existe). Alternativa provisional: transferencia contra el sensor de cámara (calibrado con patrón) en modo prueba con `vapor_camara` abierta y presión estable, en atmosférica, ~150, ~210 y ~310 kPa; luego confirmar con patrón.

## 7. Riesgos

- HAZ-CAS-01: cambio del lazo de vapor en modo chaqueta (sobreimpulso, aislamientos, CIC-16, o falta de reposición, CIC-04). Controles: VCH-AIS, D-CHQ, alivios, fallos de presión/temperatura, planta simulada y banco.
- HAZ-CAS-02: dependencia de la calibración de `pres_chaqueta`. Lectura alta → menos reposición → CIC-04 (falla segura). Lectura baja → chaqueta real más alta → la cámara sube hasta el techo → aislamiento (seguro). Control: calibración con patrón como precondición de banco e instalación.
- HAZ-M2-REC-01 queda superado en modo chaqueta (ESTERILIZACION) y se anota así en el registro.
