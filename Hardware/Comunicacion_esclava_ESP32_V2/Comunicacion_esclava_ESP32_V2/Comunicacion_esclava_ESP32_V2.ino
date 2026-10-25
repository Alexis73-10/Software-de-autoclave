#include <Wire.h>
#include <PCF8575.h>

/* -------------------- I2C -------------------- */
#define I2C_SDA 4
#define I2C_SCL 16

PCF8575 pcf_out_1(0x24); // DO1–DO16
PCF8575 pcf_out_2(0x25); // DO17–DO32
PCF8575 pcf_in_1(0x21);  // DI1–DI16
PCF8575 pcf_in_2(0x22);  // DI17–DI32
PCF8575 pcf_in_3(0x23);  // DI33–DI48
PCF8575 pcf_mux(0x26);   // DI49–DI56 + MUX

/* -------------------- ANALÓGICO -------------------- */
const int analogPin = 36;
const int numAnalogInputs = 16;
uint16_t analogValues[numAnalogInputs];
uint8_t analogChannel = 0;
uint16_t analogMin[numAnalogInputs];
uint16_t analogMax[numAnalogInputs];

/* -------------------- SALIDAS -------------------- */
uint16_t estadoOut1 = 0xFFFF; // 1 = OFF
uint16_t estadoOut2 = 0xFFFF;

/* -------------------- TIMERS -------------------- */
unsigned long tAnalog = 0;
unsigned long tIO = 0;
unsigned long tPublish = 0;

/* -------------------- WATCHDOG CONEXIÓN -------------------- */
unsigned long tLastRx       = 0;
bool          wdActivo      = false;
const unsigned long WD_TIMEOUT_MS = 5000; // 5 s sin datos => ALL_OFF

/* -------------------- SERIAL -------------------- */
String serialBuffer = "";

/* -------------------- SETUP -------------------- */
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);        // fija 12-bit explícito, no depende del default del core
  analogSetAttenuation(ADC_11db);  // fija rango ~0-3.3V explícito, evita cambios de rango entre versiones
  Wire.begin(I2C_SDA, I2C_SCL);

  pcf_out_1.begin();
  pcf_out_2.begin();
  pcf_in_1.begin();
  pcf_in_2.begin();
  pcf_in_3.begin();
  pcf_mux.begin();

  pcf_out_1.write16(estadoOut1);
  pcf_out_2.write16(estadoOut2);

  for (int i = 0; i < numAnalogInputs; i++) {
    analogMin[i] = 4095;
    analogMax[i] = 0;
  }
}

/* -------------------- LOOP -------------------- */
void loop() {
  leerSerial();          // PRIORIDAD 1
  leerAnalogico();       // PRIORIDAD 2
  leerDigital();         // PRIORIDAD 3
  publicarEstados();     // PRIORIDAD 4
  verificarWatchdog();   // PRIORIDAD 5
}

/* -------------------- SERIAL NO BLOQUEANTE -------------------- */
void leerSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      procesarComando(serialBuffer);
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}

/* -------------------- WATCHDOG -------------------- */
void verificarWatchdog() {
  if (!wdActivo) return;
  if (millis() - tLastRx > WD_TIMEOUT_MS) {
    estadoOut1 = 0xFFFF;
    estadoOut2 = 0xFFFF;
    pcf_out_1.write16(estadoOut1);
    pcf_out_2.write16(estadoOut2);
    wdActivo = false;
    Serial.println("WD: ALL_OFF");
  }
}

/* -------------------- COMANDOS -------------------- */
void procesarComando(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  // Cualquier comando recibido resetea el watchdog
  tLastRx  = millis();
  wdActivo = true;

  Serial.println("ACK"); // respuesta inmediata

  if (cmd == "HB") return; // heartbeat — solo mantiene la conexión viva

  if (cmd == "ALL_OFF") {
    estadoOut1 = 0xFFFF;
    estadoOut2 = 0xFFFF;
    pcf_out_1.write16(estadoOut1);
    pcf_out_2.write16(estadoOut2);
    Serial.println("OK ALL_OFF");
    return;
  }

  if (cmd == "RESET_MINMAX") {
    for (int i = 0; i < numAnalogInputs; i++) {
      analogMin[i] = 4095;
      analogMax[i] = 0;
    }
    Serial.println("OK RESET_MINMAX");
    return;
  }

  if (!cmd.startsWith("SET DO")) return;

  int espacio = cmd.indexOf(' ', 7);
  if (espacio < 0) return;

  int num = cmd.substring(6, espacio).toInt();
  String estado = cmd.substring(espacio + 1);

  if (num < 1 || num > 32) return;

  bool on = (estado == "ON");

  if (num <= 16) {
    bitWrite(estadoOut1, num - 1, !on);
    pcf_out_1.write16(estadoOut1);
  } else {
    bitWrite(estadoOut2, num - 17, !on);
    pcf_out_2.write16(estadoOut2);
  }

  Serial.print("OK DO");
  Serial.print(num);
  Serial.print(" ");
  Serial.println(estado);
}

/* -------------------- ANALÓGICO ESCALONADO -------------------- */
#define ADC_SAMPLES     64      // muestras promediadas por canal (era 8 — reduce ruido aleatorio ~2.8x)
#define ADC_SETTLE_US  800      // µs de espera tras cambio de MUX (era 500 — margen adicional de asentamiento)
#define ADC_MS_PER_CH   20      // ms entre canales (16 ch × 20 ms = 320 ms ciclo)
#define ADC_DISCARD      2      // muestras descartadas tras cambio de canal, antes de promediar

void leerAnalogico() {
  if (millis() - tAnalog < ADC_MS_PER_CH) return;
  tAnalog = millis();

  // 1. Cambiar canal del MUX
  uint16_t muxBits = ((analogChannel & 0x0F) << 8);
  pcf_mux.write16(muxBits);

  // 2. Esperar que el condensador S&H del ADC se estabilice
  delayMicroseconds(ADC_SETTLE_US);

  // 3. Descartar primeras lecturas (aún influenciadas por el canal anterior)
  for (int d = 0; d < ADC_DISCARD; d++) {
    analogRead(analogPin);
    delayMicroseconds(50);
  }

  // 4. Promediar ADC_SAMPLES lecturas para reducir ruido térmico
  uint32_t sum = 0;
  for (int k = 0; k < ADC_SAMPLES; k++) {
    sum += analogRead(analogPin);
    delayMicroseconds(50);
  }
  analogValues[analogChannel] = (uint16_t)(sum / ADC_SAMPLES);

  if (analogValues[analogChannel] < analogMin[analogChannel]) analogMin[analogChannel] = analogValues[analogChannel];
  if (analogValues[analogChannel] > analogMax[analogChannel]) analogMax[analogChannel] = analogValues[analogChannel];

  analogChannel++;
  if (analogChannel >= numAnalogInputs) analogChannel = 0;
}

/* -------------------- DIGITALES -------------------- */
uint16_t d1, d2, d3, d4;

void leerDigital() {
  if (millis() - tIO < 50) return;
  tIO = millis();

  d1 = pcf_in_1.read16();
  d2 = pcf_in_2.read16();
  d3 = pcf_in_3.read16();
  d4 = pcf_mux.read16();
}

/* -------------------- PUBLICAR ESTADOS -------------------- */
void publicarEstados() {
  if (millis() - tPublish < 500) return;
  tPublish = millis();

  Serial.print("AI:");
  for (int i = 0; i < numAnalogInputs; i++) {
    Serial.print(analogValues[i]);
    if (i < numAnalogInputs - 1) Serial.print(",");
  }
  Serial.println();

  Serial.print("DI:");
  for (int i = 0; i < 16; i++) Serial.print(!bitRead(d1, i));
  for (int i = 0; i < 16; i++) Serial.print(!bitRead(d2, i));
  for (int i = 0; i < 16; i++) Serial.print(!bitRead(d3, i));
  for (int i = 0; i < 8;  i++) Serial.print(!bitRead(d4, i));
  Serial.println();

  Serial.print("DO:");
  for (int i = 0; i < 16; i++) Serial.print(!bitRead(estadoOut1, i));
  for (int i = 0; i < 16; i++) Serial.print(!bitRead(estadoOut2, i));
  Serial.println();
}
