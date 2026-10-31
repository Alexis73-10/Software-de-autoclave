# Planeación — Control de ingreso de vapor por la válvula de chaqueta (VCH)

Fecha: 2026-10-25 · Estado: especificación, sin código · Software de Autoclave (NTC-IEC 62304 Clase C)

## 1. Objetivo

En los equipos con chaqueta, el ingreso de vapor a la cámara durante CALENTAMIENTO y ESTERILIZACIÓN se controla con la válvula de chaqueta (`vapor_chaqueta`) y no con la de cámara (`vapor_camara`). La chaqueta actúa como amortiguador térmico y hace menos brusco el ingreso de vapor. Todas las válvulas son on-off: el control sigue siendo por tiempo abierta / tiempo cerrada dentro de cada intervalo.

## 2. Decisiones de Cristian (2026-10-25)

| # | Decisión |
|---|----------|
| D1 | Se planea desde cero (no se retoma ningún documento anterior). |
| D2 | Válvula controlada en CALENTAMIENTO y ESTERILIZACIÓN: `vapor_chaqueta`. |
| D3 | `vapor_camara` se abre al iniciar CALENTAMIENTO y queda abierta hasta el fin de ESTERILIZACIÓN. |
| D4 | Ante sobrepresión en cámara se cierra `vapor_camara` (aislamiento). |
| D5 | El golpe inicial de vapor al abrir `vapor_camara` después del prevacío se acepta tal cual (sin apertura gradual). |
| D6 | `vapor_camara` se cierra definitivamente al terminar ESTERILIZACIÓN. |
| D7 | Equipos de mesa (sin chaqueta) conservan el control actual con `vapor_camara`. |

## 3. Comportamiento actual (código revisado el 2026-10-25)

- `calentamiento.py` y `esterilizacion.py` conmutan `vapor_camara` (tramo de subida con tres criterios + techo; esterilización con RECUPERACION / PWM_ACTIVO).
- `ciclo.py::_mantener_chaqueta()` controla `vapor_chaqueta` con banda ± sobre la consigna de chaqueta durante todas las fases del ciclo (salvo secado y enfriamiento de modos 4/5).
- Los equipos de mesa no tienen chaqueta.

## 4. Diseño

### 4.1 Selección del modo de control (VCH-SEL)

- Al iniciar CALENTAMIENTO se fija el modo para todo el ciclo, sin cambio a mitad de ciclo:
  - **Modo chaqueta**: el perfil de instalación tiene habilitada la salida `vapor_chaqueta` y asignado el sensor `pres_chaqueta`.
  - **Modo cámara**: cualquier otro caso (equipos de mesa). Comportamiento idéntico al actual.
- El modo se registra en el log al iniciar CALENTAMIENTO.
- V-01 (verificar en código): función del perfil que indica salida habilitada / sensor asignado; usar la existente, no crear una paralela.

### 4.2 Válvula actuadora (modo chaqueta)

- Toda la lógica de decisión de las dos fases se conserva tal cual (criterios, umbrales, sensores de cámara como referencia). Solo cambia la salida: donde hoy se enciende/apaga `vapor_camara`, en modo chaqueta se enciende/apaga `vapor_chaqueta`.
- Las variables de control siguen siendo la temperatura del Principal y la presión de cámara. La presión de chaqueta no es variable de control; solo se usa para la protección de 4.6.

### 4.3 Válvula de cámara (modo chaqueta)

- Se abre en el primer tick de CALENTAMIENTO (después de la inicialización) y se mantiene abierta.
- Se cierra solo por:
  1. Aislamiento por sobrepresión (4.4), de forma temporal.
  2. COMPLETADO de ESTERILIZACIÓN (D6).
  3. FALLO, cancelación o paro de emergencia (rutas existentes).
- En el COMPLETADO de CALENTAMIENTO **no** se cierra `vapor_camara`: el apagado de salidas de esa transición debe excluirla en modo chaqueta. `vapor_chaqueta` sí puede quedar en OFF; ESTERILIZACIÓN la retoma en su primer tick.

### 4.4 Aislamiento por sobrepresión de cámara (VCH-AIS)

Aplica en las dos fases, en modo chaqueta.

- **Entrada**: presión de cámara ≥ techo de la fase (saturación a la temperatura objetivo + `presion_add_calentamiento` o `presion_add_esterilizacion`). Reacción inmediata, sin espera de confirmación.
- **Acción**: `vapor_camara` OFF y `vapor_chaqueta` OFF forzada (prevalece sobre cualquier otro criterio).
- **Salida**: presión de cámara ≤ techo − `histeresis_cierre_camara` sostenida durante 3 s continuos (reloj monotónico). Al salir se reabre `vapor_camara` y el control normal retoma `vapor_chaqueta`.
- En ESTERILIZACIÓN, este aislamiento reemplaza la histéresis del techo de RECUPERACION (C-08.3, 2 kPa sin confirmar) para que haya un solo mecanismo de techo.
- Durante el aislamiento siguen activas todas las vigilancias de falla, los escapes y el conteo de exposición. F0 sigue acumulando: el aislamiento es una acción de control, no una interrupción de la esterilización.
- En modo cámara no hay aislamiento: el techo actual sigue cerrando `vapor_camara` como hoy.

### 4.5 Fallas del aislamiento

| Código provisional | Condición | Resultado |
|---|---|---|
| SOBREPRESION_CAMARA_SOSTENIDA | Un aislamiento dura más de `timeout_aislamiento_camara` sin cumplir la condición de salida (la presión no baja con la cámara aislada). | FALLO |
| SOBREPRESION_RECURRENTE_CAMARA | `max_aislamientos_camara` aislamientos o más dentro de una ventana móvil de `ventana_aislamientos_camara`. | FALLO |

- Los códigos de alarma definitivos los asigna Claude Code con los siguientes números libres del catálogo (CIC-xx), con textos en español e inglés (i18n).
- Ambas fallas pasan por el protocolo de fallo existente.

### 4.6 Protección de presión de chaqueta (VCH-CHQ)

- Si `pres_chaqueta` ≥ `presion_max_chaqueta_control`: `vapor_chaqueta` OFF mientras dure la condición y alarma no bloqueante. No hay FALLO por esta vía: la cámara queda protegida por 4.4 y por las fallas de presión de la fase.
- Si `pres_chaqueta` queda sin lectura: `vapor_chaqueta` OFF (mismo criterio A-5 de `_mantener_chaqueta`) y alarma de sensor existente. Los tiempos límite y fallas de cada fase resuelven el caso si no se recupera.

### 4.7 Convivencia con `_mantener_chaqueta()`

- En modo chaqueta, mientras la fase activa sea CALENTAMIENTO o ESTERILIZACIÓN, `_mantener_chaqueta()` no actúa sobre `vapor_chaqueta`. Mecanismo sugerido: atributo de fase `controla_vapor_chaqueta = True`, análogo al existente `chaqueta_en_enfriamiento`.
- La vigilancia del presostato de suministro (SUM-06) se conserva en esas fases. Sin suministro: `vapor_chaqueta` OFF y la alarma, como hoy.
- Al terminar ESTERILIZACIÓN, `_mantener_chaqueta()` retoma la chaqueta con su consigna (secado y fases siguientes sin cambio).

### 4.8 Sin cambios

Prevacío, precalentamiento, secado, descompresión, escapes lento y rápido, ciclos de líquidos, F0, vigilancias de falla de ESTERILIZACIÓN, sondas de referencia y modo cámara (equipos de mesa).

## 5. Parámetros nuevos

| Parámetro | Ámbito | Defecto | Rango | Uso |
|---|---|---|---|---|
| `histeresis_cierre_camara` | programa (calentamiento y esterilización) | 3 kPa | 1–10 kPa | Cuánto debe bajar la presión bajo el techo para reabrir `vapor_camara`. |
| `timeout_aislamiento_camara` | equipo | 3 min | 1–10 min | Duración máxima de un aislamiento. |
| `max_aislamientos_camara` | equipo | 6 | 2–20 | Aislamientos que disparan la falla recurrente. |
| `ventana_aislamientos_camara` | equipo | 15 min | 5–60 min | Ventana móvil de conteo. |
| `presion_max_chaqueta_control` | equipo | 390 kPa abs | 300–399 kPa abs | Límite de presión de chaqueta durante el control. Bajo el fondo de escala del transductor QDW90A 0–4 bar. |

Valor no numérico o fuera de rango: se recorta al rango; si falta, se usa el defecto (mismo patrón que `pausa_max_esterilizacion_s`).

## 6. Hallazgos

| Código | Severidad | Descripción |
|---|---|---|
| VCH-01 | Alta | Los valores actuales de intervalos, factores, tasas y rangos de las dos fases se ajustaron para `vapor_camara`. Con la chaqueta en medio hay más retardo y más riesgo de sobrepaso: hay que reajustarlos con ciclos reales en el equipo de pruebas antes de liberar. |
| VCH-02 | Media | El golpe inicial al abrir `vapor_camara` después del prevacío (D5) descarga el vapor acumulado en la chaqueta. Aceptado. Verificar en pruebas que no dispare sobrepresión ni falla de saturación al inicio del calentamiento. |
| VCH-03 | Media | Con `vapor_camara` atascada cerrada, la cámara no calienta: lo cubre el tiempo límite de calentamiento. Con `vapor_camara` atascada abierta, el aislamiento no actúa: lo cubren la falla de presión alta de la fase, la falla de aislamiento sostenido y la válvula de alivio mecánica (45 psi). |
| VCH-04 | Baja | Con suministro regulado a 40 psig, la chaqueta no debería alcanzar `presion_max_chaqueta_control` salvo que falle el regulador. La protección 4.6 es redundante a propósito. |

## 7. Impacto normativo (IEC 62304 / ISO 14971)

- Cambio en código de seguridad (control de presión y temperatura): requiere solicitud de cambio, actualización del fichero de gestión de riesgos y pruebas de regresión de las dos fases.
- Peligros que deben registrarse o actualizarse: sobrepresión de cámara, sobrepresión de chaqueta, falla de `vapor_camara` abierta o cerrada, y pérdida del sensor de chaqueta.

## 8. Pruebas mínimas

1. Modo chaqueta: `vapor_camara` abierta desde el inicio de calentamiento hasta el fin de esterilización; el control conmuta solo `vapor_chaqueta`.
2. Modo cámara (perfil sin chaqueta): comportamiento idéntico al actual (las pruebas existentes pasan sin cambios).
3. Aislamiento: entrada en el techo, salida con histéresis y 3 s sostenidos, `vapor_chaqueta` forzada OFF durante el aislamiento.
4. Fallas: aislamiento sostenido y aislamiento recurrente.
5. F0 y conteo de exposición siguen avanzando durante el aislamiento.
6. Protección de chaqueta: límite alcanzado y sensor sin lectura.
7. `_mantener_chaqueta()` no actúa en las dos fases en modo chaqueta y retoma el control al terminar esterilización.
8. Transición CALENTAMIENTO → ESTERILIZACIÓN sin cierre de `vapor_camara`.
9. FALLO, cancelación y paro de emergencia cierran ambas válvulas.

## 9. Verificaciones previas para Claude Code

- V-01: función del perfil para detectar chaqueta (4.1).
- V-02: confirmar que `protocolo_fallo.py`, la cancelación y el paro de emergencia cierran `vapor_camara` y `vapor_chaqueta`.
- V-03: ubicar dónde se definen los parámetros de programa y de equipo (catálogo de parámetros, JSON de perfil, UI de opciones) para agregar los nuevos con sus rangos y textos i18n.
- V-04: listar las pruebas existentes de las dos fases que asumen `vapor_camara` como actuador.
