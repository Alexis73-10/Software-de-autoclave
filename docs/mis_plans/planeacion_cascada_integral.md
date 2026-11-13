# Planeación: cascada de chaqueta con reposición integral y recuperación sobre Psat (CRI)

Fecha: 9-nov-2026. Base: `dev` = alpha.26 (CAS tanda 33 + PAM-01..06). Equipo: SN260001, modo chaqueta.
Estado: aprobado por Cristian el 9-nov. Valores marcados `DECISIÓN SIN CONFIRMAR` quedan a confirmar en banco.

## 1. Problema

1.1. Síntoma (alpha.26, Líquidos 121 °C, CIC-04, 9-nov, descrito por Cristian): en esterilización dejó de ingresar vapor; cuando intentó recuperar ya era tarde y la presión cayó hasta la falla.

1.2. Causa en el código (`cascada_chaqueta.py`, `CascadaChaqueta.evaluar`):

- Nivel «banda» (`P_sp - 2 <= P_cam <= P_sp + 1`): consigna de chaqueta `min(P_sp + margen_chaqueta_est, techo - 2)`, con `techo = P_control_max`. Con el programa Líquidos del equipo (`presion_add_esterilizacion` 11 → techo 216,0) la chaqueta queda limitada a 214 kPa. Con PAM-04 `P_sp` sube a 210–213 kPa: la chaqueta solo puede estar 1–4 kPa sobre la cámara y por la válvula de asiento casi no pasa vapor.
- Solo el nivel «baja» (`P_cam < P_sp - 2`) pide 350 kPa. Para entonces faltan ≈5–7 kPa hasta CIC-04 (`Psat(T_est) - brecha_error_presion` = 203,0) y la recarga de la chaqueta más el paso por la válvula llegan tarde.
- El escape lento queda abierto toda la exposición por diseño: da el flujo de vapor que la Referencia necesita para leer (Cristian, 9-nov). Es una pérdida fija que la chaqueta debe reponer de forma continua, con una diferencia de presión chaqueta–cámara sostenida que el tope `techo - 2` no permite.
- Evidencia de capacidad: en el ciclo 26 (alpha.24) la cámara se sostuvo en ≈227 kPa durante el empuje de líquidos con el mismo escape lento abierto. El equipo puede reponer la pérdida cuando la chaqueta está suficientemente sobre la cámara.

1.3. `brecha_segura_presion` mide hoy por debajo de Psat (RECUPERACION con `P < Psat(T_est) - brecha_segura_presion`), lo que obliga a que sea menor que `brecha_error_presion` (regla PAM-06) y deja la recuperación a ≈0,5 kPa de la falla. Criterio de Cristian: el margen de recuperación está por encima de Psat. Además, en modo chaqueta RECUPERACION no decide la válvula (la decide la cascada), así que hoy el parámetro no actúa en SN260001.

1.4. Planta simulada (`tests/helpers/planta_vapor.py`, valores provisionales), esterilización de líquidos desde el inicio de la fase (cámara 212 kPa, chaqueta 215, Principal 0,6 K baja, desfase heredado 7 kPa, programa del equipo): con la alpha.26 fallan 7 de 16 combinaciones de paso chaqueta–cámara (0,1 / 0,03 / 0,015 / 0,008), pérdida fija (0,4 / 0,8 kPa/s) y llenado de chaqueta (4 / 1,5 kPa/s). Las que fallan combinan paso restringido con pérdida alta o llenado lento. Con la pérdida a 0,2 kPa/s las 8 combinaciones completan. Conclusión: el control debe sostener la diferencia de presión que pide la pérdida real; si la capacidad física no alcanza, ningún control lo sostiene (ver CRI-H1).

## 2. Alcance

Incluido: `cascada_chaqueta.py` (CAS-01), su uso en ESTERILIZACION (CAS-02) y en ESTABLE_PREESTERILIZACION (CAS-03), RECUPERACION de ESTERILIZACION (los dos modos), la regla PAM-06 y la presentación de `brecha_segura_presion`.

Fuera de alcance: VCH-AIS, D-CHQ, el corte duro de CICLO, fallas de ESTERILIZACION (CIC-04 y demás sin cambio), F0, C-03/C-13, PAM-01..05, la rampa de CALENTAMIENTO, PREVACIO, DESCOMPRESION, SECADO, el escape lento (no se cambia). PAM-07 (no condensables en líquidos por la Referencia) sigue pendiente aparte.

## 3. Diseño

### CRI-01 Consigna de chaqueta con acción integral

- `CascadaChaqueta` agrega `dp` (kPa): diferencia de presión chaqueta–cámara que la cascada aprende. `evaluar(...)` recibe el instante (`ahora`, monotonic) y, para la integral, si debe congelarla (ver abajo); el componente sigue puro.
- Integración por tick: `dp += KI_CRI * (p_ref - P_cam) * dt`, acotada a `[DP_MIN_KPA, tope_baja - p_ref]`. `KI_CRI` = 0,15 kPa/(kPa·s), `DP_MIN_KPA` = 3. `DECISIÓN SIN CONFIRMAR`. `dt` del reloj monotonic, recortado a 0–2 s (un salto o una pausa no integra de golpe).
- Valor inicial: `margen_chaqueta_est` del programa (el parámetro conserva su rango; pasa a ser el ΔP inicial). En ESTERILIZACION, si CALENTAMIENTO publicó un `dp` en `estado.cascada_chaqueta`, se parte de ese valor (lo aprendido con la misma carga), acotado igual.
- Consignas:
  - «banda»: `min(p_ref + dp, tope_baja)`. Se retira el límite `techo - MARGEN_TECHO_KPA` de este nivel.
  - «baja»: `tope_baja` (sin cambio).
  - «alta» (`P_cam > p_ref + 1`): OFF forzado (sin cambio). La integral sigue corriendo: con error negativo `dp` baja.
- Antiembalamiento: la integral se congela (no cambia `dp`) mientras VCH-AIS esté aislado, con `inhibir_vapor_chaqueta`, sin lectura de cámara o de chaqueta, y mientras la orden aplicada sea OFF por una prevalencia y no por la cascada.
- La válvula sigue con la histéresis actual bajo la consigna (`HISTERESIS_KPA` 3).
- Protección de cámara sin cambio: VCH-AIS cierra `vapor_camara` en el techo y la válvula de alivio queda como respaldo mecánico. La chaqueta nunca supera `min(D-CHQ - 10, suministro)`.
- Publicación: `estado.cascada_chaqueta` agrega `dp` (solo lectura). Log: una línea por cambio de nivel o de consigna (como hoy) y una cuando `dp` cambie más de 2 kPa desde la última línea.
- Rige en ESTERILIZACION y en ESTABLE_PREESTERILIZACION (una sola implementación).

### CRI-02 Recuperación medida sobre Psat

- `brecha_segura_presion` pasa a medirse por encima de `Psat(T_est)`:
  - RECUPERACION entra con `T < T_est + brecha_segura_temperatura` (sin cambio) o `P < Psat(T_est) + brecha_segura_presion`.
  - Sale con `T >= T_est + brecha_segura_temperatura + 0,3` (sin cambio) y `P >= Psat(T_est) + brecha_segura_presion + 1,0`.
- Modo chaqueta, ESTERILIZACION: el umbral del nivel «baja» de la cascada pasa a `p_baja = min(Psat(T_est) + brecha_segura_presion, p_ref - 1)` en lugar de `p_ref - 2`. El `min` evita que la cascada quede siempre en «baja» si la brecha supera la consigna (se registra en el log una vez por fase si recorta). `DECISIÓN SIN CONFIRMAR`.
- Modo chaqueta, ESTABLE_PREESTERILIZACION: el umbral sigue en `p_ref - 2` (`brecha_segura_presion` es de esterilización).
- Modo cámara: RECUPERACION con el umbral nuevo; el resto (C-08.3, histéresis del techo) sin cambio.

### CRI-03 Regla de coherencia

- Se retira PAM-06 (`errores_brecha_presion`, `COHERENCIA_BRECHA_PRESION`, `opciones.err_coherencia_brecha_presion`) con sus usos en `cycle_manager.py`, `parametros_ciclo_controller.py` y `sesion_backend.py`.
- Regla nueva `COHERENCIA_BRECHA_RECUPERACION`: `brecha_segura_presion < presion_add_esterilizacion - 3` (si no, la recuperación queda pegada al techo de aislamiento). Rechazo al guardar; al cargar, aviso SIS-06 y log, sin migrar (mismo tratamiento que tenía PAM-06). Textos es/en.

### CRI-04 Cambio de significado

- Los valores guardados no cambian; cambia su lectura (de «bajo Psat» a «sobre Psat»). Con 1,5 a 121 °C la recuperación pasa de 203,5 a 206,5 kPa.
- Al cargar cada programa por primera vez con esta versión: una fila de auditoría `param_ciclo_cambio` (origen «migración CRI: brecha_segura_presion medida sobre Psat»), una sola vez por programa con marca `migrado_cri` en la hoja del parámetro (patrón de `_migrar_brecha_t28`), sin SIS-06.
- Rótulo y ayuda del parámetro en Parámetros del ciclo, es/en: «Margen de recuperación sobre Psat».

## 4. Hallazgos

- CRI-H1 (ALTA): si la capacidad física (llenado de chaqueta desde el suministro y paso por la válvula de asiento) es menor que la pérdida de la cámara con carga líquida y escape lento abierto, ningún control sostiene la presión (planta, §1.4). El banco debe medir: subida de chaqueta con `vapor_chaqueta` abierta y `vapor_camara` cerrada (kPa/s), y caída de cámara sin vapor con el escape lento abierto (kPa/s), con la carga de líquidos.
- CRI-H2 (MEDIA): con la integral, la chaqueta puede quedar decenas de kPa sobre la cámara. Un ascenso de cámara lo corta la cascada («alta» → OFF) y, en el techo, VCH-AIS. Hay que vigilar CIC-16 (6 aislamientos en 15 min) en el banco con 134 °C.

## 5. Riesgos (para `docs/riesgos/registro_riesgos.md`)

- HAZ-CRI-01: chaqueta alta con `vapor_camara` abierta → sobreimpulso de cámara. Controles: nivel «alta» OFF, VCH-AIS, D-CHQ − 10 como tope de consigna, alivio de cámara, integral que baja `dp` con error negativo.
- HAZ-CRI-02: cambio de significado de `brecha_segura_presion` en programas instalados. Controles: auditoría única, rótulo nuevo, regla CRI-03.

## 6. Requisitos para la implementación

6.1. Constantes en `cascada_chaqueta.py`: `KI_CRI`, `DP_MIN_KPA`, `DT_MAX_S` = 2. `MARGEN_TECHO_KPA` queda solo si algo más lo usa.

6.2. Pruebas unitarias de CRI-01 (integración, cotas, congelamiento por cada prevalencia, valor inicial y herencia de CALENTAMIENTO, consigna de banda sin techo), CRI-02 (umbrales nuevos en los dos modos, recorte `p_ref - 1`), CRI-03 (rechazo y aviso) y CRI-04 (auditoría una sola vez).

6.3. Planta (`tests/test_cri_planta.py`): el escenario de §1.4 (16 combinaciones, desde ESTERILIZACION, programa con los valores del equipo: `presion_add_esterilizacion` 11, `brecha_segura_temperatura` 0, `margen_chaqueta_est` 20, Principal −0,6 K, desfase heredado 7) con la alpha.26 como referencia, más los ciclos completos de `test_t33_cas04_planta.py` y `test_pam_planta.py`. Criterio de liberación:
- todo caso que completa con la alpha.26 sigue completando;
- ningún caso nuevo con aislamientos que no tuviera;
- 134 °C sin CIC-16;
- en el informe, el resultado de las 16 combinaciones antes y después, sin `xfail` que oculte un caso: los que sigan fallando se reportan como límite físico con su pérdida y su capacidad.

6.4. Trazabilidad: REQ nuevos uno por CRI-01..04; banco: bloque CRI en la hoja de pruebas con las mediciones de CRI-H1.
