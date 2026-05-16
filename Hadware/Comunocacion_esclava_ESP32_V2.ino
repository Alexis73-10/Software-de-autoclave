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

/* -------------------- SALIDAS -------------------- */
uint16_t estadoOut1 = 0xFFFF; // 1 = OFF
uint16_t estadoOut2 = 0xFFFF;

/* -------------------- TIMERS -------------------- */
unsigned long tAnalog = 0;
unsigned long tIO = 0;
unsigned long tPublish = 0;

/* -------------------- SERIAL -------------------- */
String serialBuffer = "";

/* -------------------- SETUP -------------------- */
void setup() {
  Serial.begin(115200);
  Wire.begin(I2C_SDA, I2C_SCL);

  pcf_out_1.begin();
  pcf_out_2.begin();
  pcf_in_1.begin();
  pcf_in_2.begin();
  pcf_in_3.begin();
  pcf_mux.begin();

  pcf_out_1.write16(estadoOut1);
  pcf_out_2.write16(estadoOut2);
}

/* -------------------- LOOP -------------------- */
void loop() {
  leerSerial();          // PRIORIDAD 1
  leerAnalogico();       // PRIORIDAD 2
  leerDigital();         // PRIORIDAD 3
  publicarEstados();     // PRIORIDAD 4
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

/* -------------------- COMANDOS -------------------- */
void procesarComando(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  Serial.println("ACK"); // respuesta inmediata

  if (cmd == "ALL_OFF") {
    estadoOut1 = 0xFFFF;
    estadoOut2 = 0xFFFF;
    pcf_out_1.write16(estadoOut1);
    pcf_out_2.write16(estadoOut2);
    Serial.println("OK ALL_OFF");
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
void leerAnalogico() {
  if (millis() - tAnalog < 5) return; // 1 canal cada 5 ms
  tAnalog = millis();

  uint16_t muxBits = ((analogChannel & 0x0F) << 8);
  pcf_mux.write16(muxBits);
  analogValues[analogChannel] = analogRead(analogPin);

  analogChannel++;
  if (analogChannel >= numAnalogInputs) {
    analogChannel = 0;
  }
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
