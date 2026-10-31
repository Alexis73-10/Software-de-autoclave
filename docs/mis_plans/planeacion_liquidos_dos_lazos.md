# Planeación: Líquidos — control en dos lazos y eliminación de aire (C-11, C-12)

**Proyecto:** Software de Autoclave (Especifika S.A.S.), IEC 62304 Clase C.
**Origen:** `docs/mis_plans/decisiones_tanda_12.md`, puntos C-11 y C-12 (pedido de Cristian del 24-oct-2026, confirmado a las 17:21). Hallazgo de origen: **LIQ-01**.
**Estado:** especificación, **sin código**. Redactada en la tanda 12, etapa L12, sin supervisión. Lo que no está en las decisiones va marcado **DSC** (decisión sin confirmar) o en las preguntas abiertas de la §10.
**Relación con la tanda 12:** C-02 (coherencia T–P para entrar a esterilizar) y C-03 (falla de saturación durante la exposición) se aplican en la tanda 12 **solo con `globals.tipo_carga = "solido"`**. Con líquidos quedan desactivados hasta que se implemente este documento, que es el que define cómo se aplican con carga líquida.

---

## 1. Objetivo y alcance

### Objetivo

1. **C-11.** Con carga líquida, controlar la válvula de vapor de cámara (`vapor_camara`) con un **lazo de presión** hacia `Psat(T_est + delta)`, y dejar a la sonda del líquido solo las decisiones que le corresponden: **inicio y pérdida de la exposición, F0 y fallas de temperatura de la carga**. La sonda del líquido **no mueve la válvula**.
2. **C-11 (sonda en el vapor).** En líquidos, la coherencia temperatura–presión (C-02) y la falla de saturación (C-03) se evalúan con una **sonda en el vapor** (sin contacto con el líquido), **nunca** con la sonda del líquido. Se define el rol de sensor necesario y qué pasa si esa sonda no está cableada o no lee.
3. **C-12.** Quitar el aire de la cámara antes de calentar una carga líquida, con una de dos opciones: **A** (purga con el drenaje abierto hasta `temp_ref > 95 °C`) o **B** (prevacío solo con el líquido frío). Se comparan riesgos, parámetros e interlocks y se recomienda una.

### Por qué van juntos C-11 y C-12

Un lazo de presión **con aire en la cámara** sostiene la presión pero no la temperatura: la presión total es la del vapor más la del aire. Hecho de origen (decisiones C-12): sin quitar el aire, la cámara a **226 kPa** queda en **~106 °C** reales. Comprobación con la ecuación de `steam.py`: `Psat(106 °C) = 125.4 kPa`; el aire atrapado de Bogotá (74.6 kPa a ~20 °C) calentado a 106 °C sube a `74.6 × 379.15 / 293.15 ≈ 96.5 kPa`; `125.4 + 96.5 ≈ 222 kPa`, coherente con lo medido. Con el lazo de C-11 y sin C-12, la coherencia T–P de la sonda de vapor daría `Tsat(226) − 106 = 124.3 − 106 ≈ 18 K` y el ciclo fallaría siempre con CIC-12. **C-11 no se debe habilitar sin C-12.**

### Fuera de alcance

- Cambios en sólidos (C-01..C-10 y C-13 de la tanda 12 ya los cubren).
- Enfriamiento con contrapresión (modos 4/5 de `descompresion.py`) y apertura en líquidos (`temp_max_apertura`): siguen igual, decididos con el Principal (HAZ-LIQ-01).
- PRG-01 (validar al cargar que cada rol corresponda a una sonda cableada en el perfil): pendiente registrado aparte; aquí solo se usa para la sonda de vapor (§3.5).
- DEU-01 (límites de presión desde el perfil): se usan las constantes de la tanda 12 (`PRESION_SUMINISTRO = 350`, `PRESION_ALIVIO_CAMARA = 385` kPa abs).

---

## 2. Comportamiento actual (verificado en el código de `tanda-12`, commit c462114)

### 2.1 Secuencia y programa de fábrica de Líquidos

Secuencia común (`states/ciclo.py:151-156`): PRECALENTAMIENTO → PREVACIO → CALENTAMIENTO → ESTERILIZACION → DESCOMPRESION → SECADO. El programa `cycles/factory/liquidos.json` (y su copia de usuario) trae `tiempo_precalentamiento = 0`, los cuatro `conteo_pulso_* = 0` (**sin prevacío**), 121 °C / 15 min, `presion_add_* = 11`, `tiempo_secado = 0`, descompresión modo 4 (contrapresión 250 kPa hasta 80 °C) y roles `temp_camara = principal`, `temp_2_camara` y `temp_ref` = `no_en_uso`. No hay ninguna fase que quite el aire: PURGA se eliminó el 2026-10-01 (todos los perfiles la tenían en 0).

En líquidos el Principal es, por diseño (HAZ-LIQ-01, informe de la tanda del 14-oct §3, caso de banco G-01), la **sonda flexible dentro del líquido** del frasco de mayor volumen. Esa sonda va **minutos por detrás** del vapor.

### 2.2 Hallazgo LIQ-01: el vapor se controla con la temperatura del líquido

Todas las decisiones de control de `vapor_camara` usan `self._temp_principal()` (`base_fase.py:69-72`), que en líquidos es la sonda del líquido:

| Lugar | Qué hace con la temperatura del líquido | Efecto con carga líquida |
|---|---|---|
| `calentamiento.py:257` y `:308-322` | `duty_proximidad` y `sobrepaso` se calculan con `t_obj − temp` | Con el líquido frío el término de temperatura queda en 1.0 durante minutos: la válvula solo la frena el término de presión y el techo |
| `calentamiento.py:327` (`_duty_por_calidad_vapor`) | corta si `temp ≥ 0.97·t_obj` y `P < Psat(temp) + p_add` | Mide la calidad del vapor con una sonda que no está en el vapor |
| `calentamiento.py:395` y `:401` | entrada a ESTABLE_PREESTERILIZACION y banda de sostenimiento con `temp` | Correcto como condición de inicio (el líquido debe llegar), pero hoy es la misma variable que controla la válvula |
| `esterilizacion.py:330-333` | `RECUPERACION` si `temp < T_est + brecha_segura_temperatura` → `vapor_camara` ON **continuo** (`:336-337`) | El líquido llega a la meseta justo en `T_est` y tarda en pasar `T_est + brecha`: la fase queda en RECUPERACION con vapor abierto; hasta la tanda 12 sin techo (C-08.3 agrega el techo `P_control_max` en RECUPERACION) |
| `esterilizacion.py:208-221` (`_control_vapor_pwm`) | banda `[Psat(T_actual) − 2, Psat(T_actual) + 1]` con `T_actual` del líquido | Cuando el líquido va por detrás, `Psat(T_líquido)` queda por debajo de la presión real → OFF forzado; cuando el líquido alcanza, la banda sube → ON. La válvula sigue a una señal con minutos de retardo |
| `esterilizacion.py:302-308` | FALLO por presión alta `P > Psat(T_est) + rango_presion_ester` (debounce de 3 lecturas; en la tanda 12, 5 s por C-07) | Es el FALLO al que lleva la oscilación |

**Resultado (LIQ-01):** el lazo de vapor tiene en su realimentación el retardo térmico de la carga. Oscila (vapor abierto mientras el líquido no llega, cerrado cuando la banda de PWM se calcula con el líquido) y la presión se escapa hasta el FALLO por presión alta. En sólidos no se nota porque el Principal está en el vapor (zona más fría de la cámara, parte inferior opuesta a la entrada de vapor).

### 2.3 Otros puntos relevantes

- **F0** (`services/domain/loop/control_loop.py:1275-1277`) ya usa solo el Principal: en líquidos, la sonda del líquido. Es lo correcto y no cambia.
- **Vigilancia de sensores** (`states/ciclo.py:873-906`, §4 SENSOR_AUSENTE): un sensor en uso sin lectura (Principal o Referencia) → FALLO SEN-02; la tanda 12 (C-13.7b, etapa E12) cambia la Referencia sin lectura a "el ciclo continúa + SEN-11 + NO CONFORME". Un sensor `no_en_uso` no se lee ni se vigila (`sensores_ciclo.py:12`).
- **Roles disponibles hoy** (`core/runtime/sensores_ciclo.py:30-31`): `principal`, `referencia`, `no_en_uso`; sensores `temp_camara` (Cámara 1), `temp_2_camara` (Cámara 2), `temp_ref` (Referencia). No existe un rol "sonda de vapor".
- **Escape lento** en CALENTAMIENTO y ESTERILIZACION de Líquidos: `escape_lento_on = 1`, `off = 0` → enclavado abierto toda la fase: es una purga continua pequeña que no alcanza para quitar el aire (hecho de los 226 kPa / 106 °C).
- **Drenaje en ciclo** (`states/ciclo.py:512-541`, `_mantener_drenaje`): enfría con `agua_intercambiador` si `temp_drenaje > temp_segura_drenaje` y activa PRE-06.
- **Chaqueta** (C-05, etapa J12): en CICLO la consigna es `max(Psat(T_est + delta_temp_chaqueta), Psat(T_est) + presion_add_esterilizacion + margen_flujo_chaqueta)`; para Líquidos 121 °C / 11 → ≈ 230.3 kPa (≈ 124.9 °C). Aplica igual a líquidos; ver §3.6.

---

## 3. Diseño propuesto C-11 — dos lazos

### 3.1 Roles de sensor con carga líquida

| Rol | Sensor recomendado | Ubicación | Decide |
|---|---|---|---|
| `principal` | la sonda flexible (hoy `temp_camara`, Cámara 1) | **dentro del líquido** del frasco de mayor volumen | inicio y pérdida de exposición, F0, fallas de temperatura de la carga, enfriamiento, apertura (como hoy) |
| `vapor` (**rol nuevo**) | `temp_ref` (Referencia) | **en el vapor**, sin tocar líquido ni frascos, en la parte inferior de la cámara (donde se acumula el aire), lejos de la entrada de vapor y de las paredes | solo coherencia T–P (C-02) y falla de saturación (C-03). **No** mueve la válvula, **no** cuenta exposición, **no** suma F0 |
| `referencia` | opcional (`temp_2_camara`) | en otro frasco | como en sólidos (C-13): uniformidad; excursión detiene y reinicia el conteo |

Reglas del rol `vapor` (validadas en `errores_asignacion`, `sensores_ciclo.py:62-79`):
1. Como máximo **uno** por programa; no puede ser el Principal (ya garantizado: un sensor tiene un solo rol).
2. Solo admitido con `tipo_carga = "liquido"`. Con sólidos se rechaza al guardar ("en sólidos el Principal ya mide el vapor"). **DSC.**
3. Cuenta para la vigilancia de sensores del ciclo de forma propia (§3.5), no como Referencia.
4. Programa de fábrica de Líquidos: `temp_ref = vapor`. **DSC** y sujeta a PRG-01: si la instalación no declara `temp_ref`, el programa queda como se describe en §3.5.
5. El cambio de rol de `no_en_uso` a `vapor` en un programa ya instalado lo hace la migración (`migrar_parametros`) solo si la instalación declara la sonda (`sonda_instalada(profile, "temp_ref")`); si no, se deja `no_en_uso` y se aplica §3.5. Queda en la auditoría de parámetros como "migración" (mismo mecanismo que C-04.4).

**Alternativa evaluada y descartada:** usar `temp_2_camara` como sonda de vapor fija por código. Se descarta porque los roles son por programa (planeación de sensores del ciclo, rev. 2) y el equipo de pruebas tiene las tres sondas.

### 3.2 Lazo de cámara por presión (`vapor_camara`)

Solo con `tipo_carga = "liquido"`; en sólidos nada cambia.

- **Consigna de presión:** `P_lazo = Psat(T_est + delta_temp_lazo_presion)` (parámetro nuevo, §5; defecto 1.0 K). Para 121 °C: `Psat(122) = 210.7 kPa`. En CALENTAMIENTO se usa `temperatura_calentamiento` en lugar de `T_est`.
- **Techo independiente:** `P_control_max = Psat(T_est) + presion_add_esterilizacion` (igual que en sólidos; en CALENTAMIENTO `Psat(T_cal) + presion_add_calentamiento`, C-01.4). Para Líquidos 121/11 → 215.3 kPa. Con `P ≥ P_control_max` → vapor OFF sin importar nada más.
- **Validación al guardar/cargar:** `P_lazo + _BANDA_PWM_ALTA (1 kPa) < P_control_max`; si no, se rechaza con el valor máximo admisible de `delta_temp_lazo_presion`. Y `delta_temp_lazo_presion < rango_temperatura_ester` (el líquido tiende a la temperatura del vapor; si la consigna queda sobre el umbral de falla por temperatura alta, el ciclo fallaría al equilibrarse).
- **CALENTAMIENTO (RAMPA):** el duty de `vapor_camara` se calcula solo con presión: `duty_tasa` con `tasa_presion` (el término `tasa_calentamiento` se ignora en líquidos: la pendiente del líquido no es la del vapor), `duty_proximidad`/`sobrepaso` solo con `P_lazo − P` y `rango_calentamiento_pres`; `duty_calidad_vapor` **no aplica** (lo sustituye la coherencia de la sonda de vapor, §3.4). Techo como arriba.
- **CALENTAMIENTO (ESTABLE_PREESTERILIZACION):** la válvula sigue en el lazo de presión. Entrada y ventana como en sólidos pero con el líquido como condición de inicio: `T_líquido ≥ T_cal` **y** `P_lazo − 2 ≤ P ≤ P_control_max` **y** coherencia de la sonda de vapor (§3.4) durante `tiempo_estable_preesterilizacion`. El tiempo que el líquido tarda en llegar lo cubre `timeout_calentamiento` (60 min en Líquidos); no se agrega otro timeout. **DSC.**
- **ESTERILIZACION:** no hay RECUPERACION/PWM_ACTIVO por temperatura. Un solo control:
  - `P < P_lazo − _BANDA_PWM_BAJA (2 kPa)` → ON;
  - `P > P_lazo + _BANDA_PWM_ALTA (1 kPa)` → OFF;
  - dentro de la banda → PWM con `factor_esterilizacion` e `intervalo_segmentos_ester` (como hoy);
  - `P ≥ P_control_max` → OFF.
  La banda se calcula sobre la consigna **fija** `P_lazo`, nunca sobre `Psat(T_actual)`; así desaparece el retardo de la carga del lazo (corrige LIQ-01).
- **Fallas de presión** (alta/baja) sin cambios: contra `Psat(T_est)` fija, 5 s continuos (C-07.2).

### 3.3 La sonda del líquido (Principal): exposición, F0 y fallas

- **Inicio de exposición:** el conteo de `tiempo_esterilizacion` empieza al entrar a ESTERILIZACION, igual que hoy; la condición "el líquido llegó" la exige la ventana de CALENTAMIENTO (§3.2).
- **Pérdida de exposición:** `T_líquido < T_est − brecha_error_temperatura` sostenido 5 s. Hoy (y en sólidos) eso es FALLO por temperatura baja. **Propuesta DSC:** mantener el FALLO también en líquidos (es la carga misma la que salió de la temperatura de esterilización; no hay sonda "más representativa" que la del líquido). Alternativa en la pregunta 4: detener y reiniciar el conteo como C-13.
- **Temperatura alta:** `T_líquido > T_est + rango_temperatura_ester` 5 s → FALLO, sin cambios.
- **F0:** sin cambios (ya usa el Principal).
- **Referencias** en otros frascos: C-13 sin cambios (excursión detiene y reinicia; sin lectura → SEN-11 + NO CONFORME).
- **Principal sin lectura:** FALLO SEN-02 sin cambios (en el enfriamiento con contrapresión, cámara sellada: D8-2.10).

### 3.4 Coherencia T–P (C-02) y falla de saturación (C-03) con la sonda de vapor

Mismas reglas y constantes que en sólidos, cambiando la temperatura que se compara:

- **C-02 (CALENTAMIENTO, banda de sostenimiento):** `|Tsat(P) − T_vapor| ≤ _COHERENCIA_TP_K (1.0 K)`. Fuera de coherencia = fuera de banda: reinicia la ventana y arma el timeout de recuperación existente. Log con `Tsat(P)`, `T_vapor` y la diferencia.
- **C-03 (ESTERILIZACION, toda la exposición):** `dT = Tsat(P) − T_vapor`; `dT > +2 K` 5 s → FALLO **CIC-12** (aire / gases no condensables); `dT < −2 K` 5 s → FALLO **CIC-13** (vapor sobrecalentado o falla de la sonda). Mismos códigos y textos que en sólidos (no se crean alarmas nuevas para líquidos).
- Antes de la ventana de sostenimiento (rampa) la coherencia **no** se evalúa: con la carga fría, la sonda de vapor puede leer bajo cerca de frascos fríos (condensación) y no indica aire.
- La sonda del líquido **nunca** entra en estas comparaciones (diferencia de minutos con el vapor = falsa alarma segura).

### 3.5 Sonda de vapor no cableada o sin lectura

| Situación | Cuándo se detecta | Comportamiento propuesto |
|---|---|---|
| El programa de líquidos **no tiene** sensor con rol `vapor` | al guardar, al cargar y en `verificar_inicio` | **Se bloquea el inicio** con motivo "programa de líquidos sin sonda de vapor asignada" (texto es/en). **DSC** — alternativa en la pregunta 2 (permitir con NO CONFORME). |
| Rol `vapor` asignado a una sonda que la instalación **no declara** (`sonda_instalada(...) == False`) | al cargar (PRG-01 aplicado a este rol) y en `verificar_inicio` | Igual que la fila anterior: inicio bloqueado, con el nombre de la sonda. |
| La sonda de vapor está declarada pero **no lee al iniciar** | `verificar_inicio` | Inicio bloqueado (mismo criterio que hoy para el Principal: sensor en uso sin lectura). |
| La sonda de vapor **deja de leer en CALENTAMIENTO** | vigilancia §4 de `ciclo.py` (distinguiendo el rol `vapor`) | El lazo de presión sigue (no la necesita). La ventana de sostenimiento **no puede completarse** sin coherencia: queda fuera de banda y vence el timeout de recuperación → FALLO con el motivo del timeout. Alarma no bloqueante con el sensor desde el primer tick sin lectura (código SEN libre siguiente, p. ej. **SEN-12** "sonda de vapor sin lectura"; no se reutiliza SEN-11, que es de Referencia). **DSC.** |
| La sonda de vapor **deja de leer en ESTERILIZACION** | idem | El ciclo **continúa** (la letalidad la mide directamente la sonda del líquido y la presión está controlada); C-03 queda suspendida mientras no lea; alarma no bloqueante SEN-12; el ciclo queda marcado **"NO CONFORME: saturación del vapor sin verificar"** (mecanismo de la bandera NO CONFORME de C-13.7b, clave i18n propia) aunque la sonda vuelva a leer; sin apertura automática. **DSC** — alternativa en la pregunta 3 (FALLO). |
| La sonda de vapor vuelve a leer | — | C-03 se reanuda con el conteo de 5 s desde cero; la marca NO CONFORME se mantiene. |

### 3.6 Chaqueta

C-05 aplica igual a líquidos: la consigna de chaqueta (≈ 230.3 kPa para 121/11) queda por encima de `P_control_max` (215.3) y de `P_lazo` (210.7), condición necesaria para que la cámara, alimentada desde la chaqueta, pueda llegar a la consigna. La validación de J12 (rechazo si `consigna + 10 ≥ 385`) cubre líquidos. **Riesgo a vigilar:** la pared de la chaqueta a ~124.9 °C y el estrangulamiento de 230 a 211 kPa pueden dar un vapor ligeramente sobrecalentado cerca de la entrada; por eso la sonda de vapor va lejos de la entrada y de las paredes (si no, falso CIC-13).

---

## 4. Diseño propuesto C-12 — eliminación de aire en líquidos

### 4.1 Opción A — purga con el drenaje abierto hasta `temp_ref > 95 °C`

**Principio:** desplazamiento por gravedad. El vapor entra por arriba con el drenaje inferior abierto; el aire, más pesado, sale por abajo. Cuando por el fondo ya sale vapor (la sonda en el vapor del fondo llega a la temperatura del vapor), el aire se fue.

**Secuencia (fase nueva PURGA, solo si `tipo_carga = "liquido"` y `purga_activa = true`, entre PRECALENTAMIENTO y PREVACIO):**
1. Abre la(s) válvula(s) de drenaje de cámara (`valvula_purga`, §5) y `vapor_camara`.
2. Vigila `T_vapor` (rol `vapor`, §3.1; Cristian lo nombra `temp_ref`) y la presión de cámara.
3. Fin de purga: `T_vapor ≥ temp_fin_purga` **y** `|Tsat(P) − T_vapor| ≤ 1.0 K`, ambos sostenidos `tiempo_purga_extra` segundos → cierra el drenaje y pasa a la fase siguiente.
4. Si `P > presion_max_purga` (drenaje restringido, la cámara se presuriza con aire dentro) → `vapor_camara` OFF hasta que baje (el drenaje sigue abierto).
5. Timeout `timeout_purga` sin cumplir el fin → FALLO con motivo propio ("purga incompleta: no se eliminó el aire") y protocolo de fallo normal.

**Problema de altitud (hallazgo L12, importante):** en Bogotá (74.6 kPa) el vapor a presión atmosférica está a `Tsat(74.6) = 91.4 °C`. Con el drenaje totalmente abierto la cámara queda cerca de la atmósfera y **la sonda de vapor no puede pasar de ~91–92 °C**: el umbral fijo de 95 °C exige que la cámara esté a `Psat(95) = 85.3 kPa`, es decir ~10.7 kPa sobre la atmósfera local, lo que depende de la restricción del drenaje. A nivel del mar (101.3 kPa, 100 °C) el mismo 95 °C sí se cumple. Por eso se propone:
- el criterio principal de fin es la **coherencia** `|Tsat(P) − T_vapor| ≤ 1 K` (independiente del sitio: indica vapor saturado sin aire a la presión que haya);
- `temp_fin_purga` queda como piso absoluto, con defecto 95 °C (valor de Cristian) y **validación** al guardar: advertencia no bloqueante si `temp_fin_purga > Tsat(presion_admosferica del equipo) + 2 K` ("la purga solo terminará si la cámara se presuriza; revise el umbral para la altitud del sitio"). Para Bogotá eso es > 93.4 °C → el defecto 95 daría la advertencia. Ver pregunta 1.

**Riesgos:**
- Umbral inalcanzable por altitud (arriba) → timeout de purga en todos los ciclos.
- Consumo de vapor y agua de enfriamiento: el vapor que sale por el drenaje calienta `temp_drenaje`; `_mantener_drenaje` enciende `agua_intercambiador` y activa PRE-06. Interlock §6.4.
- Purga incompleta en cargas que retienen aire (frascos muy juntos, bandejas cerradas): la coherencia de la sonda de vapor no detecta el aire atrapado lejos de ella; mitigación: C-03 durante la exposición (§3.4) y el B&D no aplica a líquidos (prueba de eficacia de aire con indicador en el frasco, pregunta 6).
- Válvula de drenaje que no cierra al terminar: la cámara no sube de presión → timeout de CALENTAMIENTO (falla detectada, no silenciosa).
- Sin riesgo de ebullición del líquido: a presión atmosférica el líquido no puede superar la temperatura de saturación local.

### 4.2 Opción B — prevacío solo con el líquido frío

**Principio:** igual que en sólidos (PREVACIO), pero restringido a que el líquido esté lo bastante frío para no hervir a la presión de vacío: el agua hierve cuando `Psat(T_líquido) ≥ P_cámara`.

**Secuencia (en PREVACIO, solo si `tipo_carga = "liquido"` y `prevacio_liquido_activo = true`):**
1. Antes de cada pulso de vacío: exige `T_líquido ≤ temp_max_liquido_vacio` (Principal, con lectura). Si no se cumple, **no hace más pulsos de vacío**: termina el prevacío con lo hecho (con aviso en el ticket si no se hizo ninguno) y sigue a CALENTAMIENTO. **DSC.**
2. Vacío hasta `presion_min_vacio_liquido` (nunca más bajo), luego vapor hasta la presión alta del pulso; `conteo_pulsos_liquido` pulsos como máximo.
3. Durante el vacío, si `T_líquido` sube o la presión baja de forma que `Psat(T_líquido) + margen_ebullicion_kpa ≥ P` → corta el vacío (bomba y `vacio_camara` OFF) y rompe con vapor.

**Validación al guardar:** `presion_min_vacio_liquido ≥ Psat(temp_max_liquido_vacio) + margen_ebullicion_kpa`; con los defectos `Psat(40) = 7.4 kPa` + 5 = 12.4 ≤ 20 → válido.

**Aire residual estimado:** cada pulso deja una fracción `p_baja / p_alta` del aire. Un pulso de 74.6 a 20 kPa deja ~27 %; dos pulsos (con rotura a ~100 kPa) ~5 %. El primer pulso de vapor casi no calienta el líquido (gran masa térmica), así que el segundo pulso suele ser posible; el interlock lo decide con la lectura.

**Riesgos:**
- **Ebullición violenta / derrame / rotura** si el líquido está tibio (carga recién preparada, ciclo encadenado con `ciclos_multiples`). El interlock la evita solo si la sonda del líquido es representativa del frasco más caliente.
- **Frascos cerrados:** la diferencia de presión (frasco a 74.6 kPa, cámara a 20 kPa) puede destapar, deformar o romper recipientes y tapas; obliga a tapas flojas/ventiladas.
- **Pérdida de volumen** por evaporación en vacío (medios de cultivo).
- Sonda del líquido sin lectura en PREVACIO → hoy el Principal sin lectura es FALLO SEN-02; se mantiene (cortar vacío, romper con aire/vapor por el protocolo de fallo).
- Requiere bomba de vacío en el equipo (`bomba_vacio`); un equipo sin bomba no puede usar la Opción B.

### 4.3 Comparación y recomendación

| Criterio | A (purga) | B (prevacío frío) |
|---|---|---|
| Riesgo para la carga | bajo (no hay vacío ni ebullición) | medio/alto (ebullición, frascos cerrados) |
| Eficacia de quitar aire | media (gravedad), verificable con la sonda de vapor | alta si se pueden hacer 2 pulsos |
| Dependencia del sitio | sí (umbral absoluto y altitud) → se resuelve con coherencia | no |
| Hardware | válvula de drenaje de cámara + sonda de vapor | bomba de vacío + sonda del líquido |
| Ciclos encadenados (líquido tibio) | funciona | se degrada a sin vacío |
| Complejidad de código | fase nueva sencilla | condiciones nuevas dentro de PREVACIO |

**Recomendación: Opción A** como método base para líquidos (es el método habitual para cargas líquidas y no pone en riesgo los recipientes), con fin de purga por **coherencia T–P de la sonda de vapor** más el piso `temp_fin_purga` ajustado a la altitud. La Opción B queda como complemento opcional (`prevacio_liquido_activo = false` por defecto) para recipientes abiertos o ventilados y cargas frías, solo en equipos con bomba. Las dos usan la sonda de vapor de C-11 para verificar el resultado; implementar C-11 sin C-12 no tiene sentido (§1).

---

## 5. Parámetros nuevos

Todos solo tienen efecto con `tipo_carga = "liquido"`. Se agregan a los JSON de Líquidos (fábrica y usuario) y a `migrar_parametros` con su defecto; en los programas de sólidos no se agregan (o se agregan inertes, a decidir al implementar). Clases según el catálogo de parámetros (`absoluto` / `diferencia`).

| Nombre | Sección | Unidad | Clase | Defecto | Rango | Rol |
|---|---|---|---|---|---|---|
| `delta_temp_lazo_presion` | `globals` | K | diferencia | 1.0 | 0 – 2.5 | Consigna del lazo: `Psat(T + delta)` (§3.2). Validación: `< rango_temperatura_ester` y `P_lazo + 1 < P_control_max` |
| rol `vapor` en `cycle_temperature_sensors` | — | — | — | `temp_ref` en Líquidos (DSC) | 0 o 1 sensor | Sonda de coherencia T–P (§3.1) |
| `purga_activa` | `purga_liquidos` (nueva) | bool | — | `true` | — | Activa la Opción A |
| `temp_fin_purga` | `purga_liquidos` | °C | absoluto | 95.0 | 85 – 110 | Piso absoluto del fin de purga (advertencia por altitud, §4.1) |
| `tiempo_purga_extra` | `purga_liquidos` | s | — | 60 | 0 – 600 | Tiempo sostenido de las condiciones de fin |
| `timeout_purga` | `purga_liquidos` | min | — | 20 | 1 – 60 | FALLO "purga incompleta" |
| `presion_max_purga` | `purga_liquidos` | kPa | diferencia (sobre la atmósfera del equipo) | 30 | 5 – 60 | Corta el vapor si el drenaje no evacúa |
| `valvula_purga` | `purga_liquidos` | enum | — | `ambas` (DSC) | `lenta`, `rapida`, `ambas` | Válvula(s) que hacen de drenaje (pregunta 5) |
| `prevacio_liquido_activo` | `prevacio` | bool | — | `false` | — | Activa la Opción B |
| `temp_max_liquido_vacio` | `prevacio` | °C | absoluto | 40.0 | 10 – 60 | Interlock antes de cada pulso |
| `presion_min_vacio_liquido` | `prevacio` | kPa | absoluto | 20 | 10 – 60 | Vacío más profundo permitido |
| `margen_ebullicion_kpa` | `prevacio` | kPa | diferencia | 5.0 | 2 – 20 | Margen sobre `Psat(T_líquido)` |
| `conteo_pulsos_liquido` | `prevacio` | — | — | 2 | 1 – 3 | Máximo de pulsos de vacío |

Constantes de módulo reutilizadas (no parámetros): `_COHERENCIA_TP_K = 1.0`, umbral ±2 K y `_DEBOUNCE_FALLA_S = 5.0` de la tanda 12; `_BANDA_PWM_BAJA = 2.0`, `_BANDA_PWM_ALTA = 1.0` de `esterilizacion.py`.

---

## 6. Interlocks

1. **Lazo de presión** (§3.2): techo `P_control_max` en todos los tramos (rampa, sostenimiento, exposición), con prioridad sobre el PWM y la banda.
2. **Sonda de vapor obligatoria** para iniciar un programa de líquidos (§3.5), mientras no se decida otra cosa (pregunta 2).
3. **Coherencia T–P** como condición de la ventana de sostenimiento y del fin de purga.
4. **Purga:** puerta cerrada y bloqueada (vigilancia de puertas existente de `ciclo.py` §3); `vapor_camara` OFF si `P > P_atm + presion_max_purga`; si PRE-06 (drenaje caliente) persiste más de 60 s con el intercambiador encendido, pausa la purga (vapor OFF) hasta que baje. **DSC.**
5. **Prevacío en líquidos:** sin lectura del Principal no hay vacío; `T_líquido ≤ temp_max_liquido_vacio` antes de cada pulso; corte inmediato del vacío si `Psat(T_líquido) + margen ≥ P`.
6. **Validaciones al guardar/cargar:** `delta_temp_lazo_presion` (§5), `presion_min_vacio_liquido ≥ Psat(temp_max_liquido_vacio) + margen`, `temp_fin_purga` vs altitud (advertencia), rol `vapor` solo en líquidos.
7. Sin cambios: enfriamiento con contrapresión, rápida solo con el Principal ≤ `temperatura_enfriamiento`, apertura ≤ `temp_max_apertura`, protocolo de fallo de líquidos (cámara sellada en contrapresión).

---

## 7. Modos de falla (FMEA simplificado)

| # | Modo de falla | Efecto | Detección / respuesta | Severidad residual |
|---|---|---|---|---|
| 1 | Aire residual tras la purga | Temperatura real menor que `Tsat(P)` | Coherencia de la sonda de vapor (no entra a esterilizar); CIC-12 en la exposición | Baja si la sonda de vapor está bien ubicada |
| 2 | Sonda de vapor mal ubicada (tocando un frasco o la pared) | Falsa incoherencia (CIC-12/CIC-13) o no detecta aire | Instrucción de ubicación en el manual y en el banco; ensayo con carga real | Media (procedimental) |
| 3 | Sonda de vapor sin lectura | Sin verificación de saturación | §3.5: inicio bloqueado; en ciclo SEN-12 + NO CONFORME (o FALLO, pregunta 3) | Baja |
| 4 | Sonda del líquido fuera del líquido (en el aire del frasco) | Exposición y F0 medidos sobre el vapor: la carga real puede estar más fría | No detectable por software; procedimiento (G-01) | **Alta** — ya registrado como HAZ-LIQ-01 |
| 5 | Válvula de vapor pegada abierta | Presión sube | Techo `P_control_max` no actúa; FALLO por presión alta (5 s) y alivio mecánico a 385 kPa | Igual que en sólidos |
| 6 | Purga con drenaje restringido | La cámara se presuriza con aire | `presion_max_purga` corta el vapor; timeout de purga | Baja |
| 7 | Umbral de purga inalcanzable por altitud | Timeout de purga en todos los ciclos | Criterio por coherencia y advertencia al guardar | Baja (disponibilidad, no seguridad) |
| 8 | Prevacío con líquido tibio | Ebullición, derrame, rotura | Interlock de temperatura y de `Psat(T_líquido)` | Media (depende de que la sonda sea representativa) |
| 9 | Drenaje que no cierra al terminar la purga | No sube la presión | Timeout de CALENTAMIENTO | Baja |
| 10 | Vapor ligeramente sobrecalentado cerca de la entrada (chaqueta a ~124.9 °C) | Falso CIC-13 | Ubicación de la sonda; dato a recoger en el banco (pregunta 7) | Media hasta medir |

---

## 8. Pruebas de aceptación

### 8.1 Unitarias (al implementar; reloj monotonic simulado, archivos `tests/test_<etapa>_liquidos_*.py`)

1. Lazo de presión: con `tipo_carga = liquido`, `T_líquido` fijo en 110 °C y `P` variando, `vapor_camara` depende solo de `P` contra `Psat(T_est + delta)` (ON bajo −2, OFF sobre +1, PWM dentro); con `T_líquido` variando y `P` fija, la válvula no cambia.
2. Techo: `P ≥ Psat(T_est) + presion_add` → OFF en rampa, sostenimiento y exposición.
3. Sólidos sin cambios: la misma simulación con `tipo_carga = solido` reproduce el comportamiento de la tanda 12 (pruebas existentes en verde).
4. Coherencia con la sonda de vapor: `|Tsat(P) − T_vapor| = 1.2 K` reinicia la ventana; 0.8 K completa; con `T_líquido` 5 K por debajo y la sonda de vapor coherente, completa en cuanto el líquido llega.
5. C-03 en líquidos: `dT = +2.5 K` 4.9 s no falla, 5.0 s → CIC-12; `−2.5 K` 5 s → CIC-13; la sonda del líquido nunca dispara C-03.
6. Sonda de vapor: sin rol `vapor` → inicio bloqueado; rol en sonda no declarada → inicio bloqueado; sin lectura en CALENTAMIENTO → ventana no completa, SEN-12; sin lectura en ESTERILIZACION → continúa, SEN-12, NO CONFORME que persiste al volver a leer, sin apertura automática.
7. Rol `vapor` rechazado en programas de sólidos; máximo uno.
8. Purga: fin por coherencia + piso sostenido `tiempo_purga_extra`; corte de vapor por `presion_max_purga`; timeout → FALLO con su motivo; advertencia de altitud con `presion_admosferica = 74.6` y `temp_fin_purga = 95`.
9. Prevacío en líquidos: con `T_líquido > temp_max_liquido_vacio` no hay pulso de vacío; corte por `Psat(T_líquido) + margen ≥ P`; validación de `presion_min_vacio_liquido`.
10. Migración: programa de Líquidos sin claves nuevas carga con los defectos; rol `vapor` asignado solo si la sonda está declarada; fila de auditoría.

### 8.2 Banco (equipo de pruebas, con vidrio real, al final del día como el bloque G)

1. Ciclo de Líquidos con purga (Opción A): registrar `T_vapor`, `Tsat(P)`, `temp_drenaje` y la duración de la purga; verificar que la purga termina por coherencia y anotar a qué temperatura y presión (dato para la pregunta 1).
2. Meseta: presión estable en `Psat(122) ≈ 210.7 kPa` ±2 kPa sin oscilación sostenida de la válvula; ningún FALLO por presión alta; la exposición empieza cuando el líquido llega.
3. Diferencia `Tsat(P) − T_vapor` durante toda la exposición dentro de ±1 K (dato para la pregunta 7).
4. Desconectar la sonda de vapor en la exposición: el ciclo sigue, SEN-12, ticket NO CONFORME.
5. (Si se aprueba la Opción B) prevacío con agua a temperatura ambiente: sin ebullición; con agua a 50 °C: no hace pulsos de vacío.
6. Criterio de aceptación global: ningún frasco hierve ni se rompe; el ciclo completa con la meseta del líquido en 121 °C y sin FALLO de presión.

---

## 9. Dependencias y orden de implementación sugerido

1. Rol `vapor` en `sensores_ciclo.py` (+ validaciones, i18n, pantalla de roles de Parámetros del ciclo) y vigilancia en `ciclo.py` §4.
2. Lazo de presión en `calentamiento.py` y `esterilizacion.py` (ramas por `tipo_carga`), C-02/C-03 con la sonda de vapor.
3. Fase de purga (Opción A) y sus parámetros; migración de los programas de Líquidos.
4. (Opcional) Opción B en `prevacio.py`.
5. Banco (§8.2) antes de liberar; hasta entonces el programa de Líquidos sigue como en la tanda 12 (C-02/C-03 desactivados con líquidos).

Archivos que tocaría (para la tabla de propiedad de una tanda futura): `core/runtime/sensores_ciclo.py`, `cycle_phases/calentamiento.py`, `cycle_phases/esterilizacion.py`, `cycle_phases/prevacio.py`, fase nueva de purga, `states/ciclo.py` (lista de fases y §4), `alarms/catalogo.py` (SEN-12 y el motivo de purga), `i18n/es.json`/`en.json`, `core/managers/catalogo_parametros.py`, `core/managers/cycle_manager.py`, `cycles/*/liquidos.json`.

---

## 10. Preguntas abiertas (responder por número; sin respuesta se adopta la recomendación)

1. **Umbral de purga y altitud.** En Bogotá el vapor a presión atmosférica está a 91.4 °C, así que `temp_ref > 95 °C` solo se cumple si la cámara se presuriza ~10.7 kPa durante la purga. ¿Se acepta terminar la purga por coherencia `|Tsat(P) − T_vapor| ≤ 1 K` con `temp_fin_purga` como piso ajustable (recomendación), o se prefiere un umbral relativo `Tsat(P_atm) − x`, o mantener 95 °C fijo restringiendo el drenaje?
2. **Programa de líquidos sin sonda de vapor.** ¿Bloquear el inicio (recomendación) o permitirlo sin C-02/C-03 y marcar el ciclo NO CONFORME ("saturación sin verificar")?
3. **Sonda de vapor que deja de leer en la exposición.** ¿Continuar con SEN-12 y NO CONFORME (recomendación, la letalidad la mide la sonda del líquido) o FALLO?
4. **Pérdida de exposición del líquido** (`T_líquido < T_est − brecha_error_temperatura` 5 s). ¿FALLO como en sólidos (recomendación) o detener y reiniciar el conteo como C-13, con timeout?
5. **Válvula de drenaje de cámara.** ¿Qué salida drena físicamente el fondo de la cámara en el equipo de pruebas y en los equipos de producción: `descompresion_lenta`, `descompresion_rapida`, `vacio_camara` con la bomba apagada, u otra? ¿Hay trampa termostática en esa línea?
6. **Ubicación física de las sondas en el equipo de pruebas.** ¿Dónde está hoy la sonda "Referencia" (`temp_ref`): en el vapor del fondo o en la carga? ¿La sonda flexible es Cámara 1 (`temp_camara`)? (El contexto de la tanda dice que `temp_camara` está en la zona más fría de la cámara, y G-01 la pone dentro del líquido.) ¿Se usa `temp_drenaje` como alternativa a la sonda de vapor para la purga?
7. **Vapor sobrecalentado.** Con la chaqueta a ~124.9 °C para 121 °C, ¿se espera algún sobrecalentamiento medible en la cámara? Si en el banco `Tsat(P) − T_vapor` queda cerca de −2 K, el umbral de CIC-13 para líquidos tendría que ser distinto.
8. **Opción B.** ¿Se implementa también (opcional, apagada por defecto) o solo la A?
9. **`delta_temp_lazo_presion`.** ¿1.0 K por defecto (la cámara apunta a 122 °C para 121 °C; techo 215.3 kPa = 122.7 °C) o se prefiere otro valor? ¿Debe vivir en `globals` o en `esterilizacion`?
10. **Rol `vapor` en el programa de fábrica de Líquidos.** ¿Se asigna por defecto a `temp_ref` (requiere que la instalación la declare) o se deja `no_en_uso` y se obliga al técnico a asignarlo?
11. **Tiempo de equilibrio del líquido.** ¿Basta `timeout_calentamiento` (60 min) para que el frasco de mayor volumen llegue a la temperatura, o hace falta un timeout separado para la espera del líquido con la cámara ya en consigna?
