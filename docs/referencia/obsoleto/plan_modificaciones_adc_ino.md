# Plan de Modificaciones — Captura ADC (Comunicacion_esclava_ESP32_V2.ino)

## Objetivo
Reducir el ruido de captura ADC actual (~45 cuentas pico-a-pico) para permitir una calibración de 2 puntos con offset/gain que cumpla el presupuesto de ruido de presión ≤ 1.5 kPa en todo el rango. Todos los sensores (temperatura 0-5V y presión 4-20mA) están dentro de los 16 canales del MUX CD74HC4067 hacia GPIO36.

**Fuera de alcance de este documento**: la conversión absoluto→relativo del transductor de presión (el sensor es absoluto; la presión atmosférica de Bogotá ~74.6 kPa debe restarse). Esa resta ocurre en la capa de calibración en Python (`converters.py` / `calibration.yaml`), no en el firmware. El `.ino` solo debe entregar counts crudos lo más limpios y estables posible.

---

## Cambio 1 — Fijar atenuación y resolución del ADC explícitamente

**Problema**: el código actual no llama `analogReadResolution()` ni `analogSetAttenuation()`, por lo que depende de los defaults del core Arduino-ESP32, que pueden variar entre versiones del core o al reflashear en otro equipo.

**Modificación** (en `setup()`):
```cpp
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);        // fija 12-bit explícito, no depende del default del core
  analogSetAttenuation(ADC_11db);  // fija rango ~0-3.3V explícito, evita cambios de rango entre versiones
  Wire.begin(I2C_SDA, I2C_SCL);
  ...
```

**Riesgo**: ninguno funcional. Cambia solo la garantía de reproducibilidad.

---

## Cambio 2 — Aumentar oversampling por canal

**Problema**: `ADC_SAMPLES = 8` deja mucho margen de tiempo sin usar (20 ms disponibles por canal, se usa <1 ms). Un ruido aleatorio/térmico se reduce por √N.

**Modificación**:
```cpp
#define ADC_SAMPLES      64     // era 8 — reduce ruido aleatorio en un factor ~2.8x (sqrt(64/8))
```

**Nota**: este cambio **solo ayuda si el ruido es aleatorio**. Si es estructurado (crosstalk de MUX, acoplamiento de red 50/60 Hz), el promedio no lo elimina — pasa al Cambio 3.

---

## Cambio 3 — Descarte de primera muestra tras cambio de canal (anti-crosstalk)

**Problema**: 500 µs de asentamiento tras cambiar de canal puede ser insuficiente si canales adyacentes (0-7 presión / 8-15 temperatura) tienen tensiones muy distintas. El capacitor de sample-and-hold del ADC puede retener carga residual del canal anterior, generando un error correlacionado con el canal previo (no ruido aleatorio puro).

**Modificación**: descartar explícitamente 1-2 lecturas iniciales antes de empezar a promediar, y hacer el settle time medible/ajustable:
```cpp
#define ADC_SETTLE_US    800      // era 500 — margen adicional de asentamiento
#define ADC_DISCARD       2       // muestras descartadas tras cambio de canal, antes de promediar

void leerAnalogico() {
  if (millis() - tAnalog < ADC_MS_PER_CH) return;
  tAnalog = millis();

  uint16_t muxBits = ((analogChannel & 0x0F) << 8);
  pcf_mux.write16(muxBits);
  delayMicroseconds(ADC_SETTLE_US);

  // Descartar primeras lecturas (aún influenciadas por el canal anterior)
  for (int d = 0; d < ADC_DISCARD; d++) {
    analogRead(analogPin);
    delayMicroseconds(50);
  }

  uint32_t sum = 0;
  for (int k = 0; k < ADC_SAMPLES; k++) {
    sum += analogRead(analogPin);
    delayMicroseconds(50);
  }
  analogValues[analogChannel] = (uint16_t)(sum / ADC_SAMPLES);

  analogChannel++;
  if (analogChannel >= numAnalogInputs) analogChannel = 0;
}
```

**Validación necesaria**: confirmar que el ciclo completo (16 canales × (800µs settle + 2×50µs descarte + 64×50µs muestreo) ≈ 16 × ~4.1ms ≈ 66ms) sigue siendo << `tPublish` (500ms). Sin problema de margen.

---

## Cambio 4 — Modo diagnóstico opcional (pico-a-pico por canal)

**Propósito**: verificar en campo, sin instrumentos externos, si los cambios anteriores redujeron el ruido antes de tener manómetro/termómetro patrón disponibles.

**Modificación** (agregar min/max por canal, resettable por comando):
```cpp
uint16_t analogMin[numAnalogInputs];
uint16_t analogMax[numAnalogInputs];

// Dentro de leerAnalogico(), tras calcular analogValues[analogChannel]:
uint16_t v = analogValues[analogChannel];
if (v < analogMin[analogChannel]) analogMin[analogChannel] = v;
if (v > analogMax[analogChannel]) analogMax[analogChannel] = v;

// Nuevo comando serial: "RESET_MINMAX"
if (cmd == "RESET_MINMAX") {
  for (int i = 0; i < numAnalogInputs; i++) {
    analogMin[i] = 4095;
    analogMax[i] = 0;
  }
  Serial.println("OK RESET_MINMAX");
  return;
}
```

Esto permite correr el sensor en reposo 30-60s y leer directamente `analogMax[i] - analogMin[i]` por canal, sin depender de capturar la trama `AI:` completa en el lado Python para cada muestra.

---

## Validación posterior (checklist)

1. Reflashear con Cambios 1-3.
2. Dejar sensores en reposo (presión: sin variación de proceso; temperatura: ambiente estable).
3. Registrar pico-a-pico por canal (Cambio 4 o capturando ráfaga de tramas `AI:` en Python).
4. Comparar contra línea base (45 cuentas):
   - Si baja sustancialmente (ej. a <15-20 cuentas) → ruido era mayoritariamente aleatorio, el oversampling resolvió.
   - Si se mantiene similar → ruido estructurado, pasar a mitigación de hardware (blindaje del lazo 4-20mA, capacitor de filtro en el pin común GPIO36, o revisar routing de PCB si es exportable).
5. Con el pico-a-pico final, verificar contra presupuesto: **1.5 kPa** en counts, usando el gain que resulte de la calibración de 2 puntos (pendiente de datos de manómetro/termómetro patrón).

---

## Pendiente para cerrar la calibración de 2 puntos (no cubierto en este plan)
- Presión atmosférica local de Bogotá en el momento de la calibración (para conversión absoluto→relativo).
- Segundo punto de referencia con manómetro patrón (presión) y termómetro/baño patrón (temperatura).
