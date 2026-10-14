/*
 * Comunicacion_esclava_ESP32_V3 — firmware 1.0.0, protocolo serial 2
 *
 * Tarjeta de E/S del autoclave (Especifika S.A.S.). Especificación:
 *   docs/mis_plans/planeacion_firmware_1_5.md (v2, FW-D1 a FW-D7, §4)
 *   docs/mis_plans/planeacion_protocolo_serial_esp32.md (§4 y §5, normativo)
 * V2 (Hardware/Comunocacion_esclava_ESP32_V2) se conserva como retorno.
 *
 * Mapa de pines, direcciones I2C, ADC y temporizaciones idénticos a V2,
 * salvo: CRC en ambas direcciones, BOOT/VER con ID, trama ST, buffer de
 * recepción fijo, lastError() tras cada operación I2C, lectura de vuelta de
 * salidas, selector del MUX con | 0x00FF (FW-07), uptime de 64 bits,
 * arranque NO_SINCRONIZADO y watchdog sobre líneas válidas.
 *
 * Librería requerida: PCF8575 de Rob Tillaart, versión 0.2.5.
 *
 * Toda decisión de fallo es del PC (FW §4.7): este firmware solo informa
 * (ST, WD, BOOT) y lleva las salidas al estado seguro 0xFFFF cuando
 * corresponde (arranque, ALL_OFF, watchdog).
 */

#include <Wire.h>
#include <PCF8575.h>
#include <esp_timer.h>

/* -------------------- VERSIÓN (FW-D1) -------------------- */
#define FW_VERSION "1.0.0"
#define PROTOCOLO  2

/* -------------------- I2C -------------------- */
#define I2C_SDA 4
#define I2C_SCL 16

PCF8575 pcf_out_1(0x24); // DO1–DO16
PCF8575 pcf_out_2(0x25); // DO17–DO32
PCF8575 pcf_in_1(0x21);  // DI1–DI16
PCF8575 pcf_in_2(0x22);  // DI17–DI32
PCF8575 pcf_in_3(0x23);  // DI33–DI48
PCF8575 pcf_mux(0x26);   // DI49–DI56 + MUX

// Bits de pcf_ok (plan de protocolo §4.5). 1 = sin error en la ventana.
#define BIT_OUT_1 0x01   // 0x24
#define BIT_OUT_2 0x02   // 0x25
#define BIT_IN_1  0x04   // 0x21
#define BIT_IN_2  0x08   // 0x22
#define BIT_IN_3  0x10   // 0x23
#define BIT_MUX   0x20   // 0x26
#define PCF_TODOS 0x3F

/* -------------------- ANALÓGICO -------------------- */
const int analogPin = 36;
const int numAnalogInputs = 16;
uint16_t analogValues[numAnalogInputs];
uint8_t analogChannel = 0;
uint16_t analogMin[numAnalogInputs];
uint16_t analogMax[numAnalogInputs];

/* -------------------- SALIDAS -------------------- */
// Activas en bajo: 1 = OFF. 0xFFFF es el estado seguro.
uint16_t estadoOut1 = 0xFFFF;
uint16_t estadoOut2 = 0xFFFF;

/* -------------------- TIMERS -------------------- */
unsigned long tAnalog = 0;
unsigned long tIO = 0;
unsigned long tPublish = 0;

/* -------------------- WATCHDOG Y SINCRONÍA (FW-D3 a FW-D5) -------------------- */
const unsigned long WD_TIMEOUT_MS = 5000; // 5 s sin líneas válidas => ALL_OFF
unsigned long tLastRx = 0;
// NO_SINCRONIZADO (false) tras BOOT y tras disparo del watchdog: se rechaza
// SET DOn hasta recibir un ALL_OFF válido. Evita que un comando rezagado del
// PC encienda una salida tras un reinicio o un disparo del watchdog (HAZ-FC-09).
bool sincronizado = false;
uint8_t wdFlag = 0;      // 1 = watchdog disparó y no llegó comando válido posterior

/* -------------------- DIAGNÓSTICO (trama ST) -------------------- */
uint32_t crcRxErr = 0;   // líneas recibidas descartadas (CRC, o largas sin \n)
uint32_t i2cErr = 0;     // errores I2C acumulados
uint32_t rxLargas = 0;   // líneas que desbordaron el buffer (no se publica en ST)
uint32_t rechazados = 0; // SET DOn rechazados por NO_SINCRONIZADO (no se publica en ST)
uint8_t pcfErrVentana = 0;  // bits de expansores con error desde la última ST
uint32_t discDo = 0;     // bit n-1 = pin real de DOn distinto de la sombra
uint16_t aiInv = 0;      // canales cuya última muestra se descartó por error del MUX

/* -------------------- ID (FW-D2) -------------------- */
char idTarjeta[13];      // MAC de fábrica, 12 dígitos hex mayúscula

/* -------------------- SERIAL -------------------- */
#define RX_MAX 64
char rxBuf[RX_MAX];
uint8_t rxLen = 0;
bool rxDescartando = false;  // línea que desbordó: se descarta hasta el \n

#define TX_MAX 160

/* ==================== CRC-16/CCITT-FALSE ==================== */
// Polinomio 0x1021, inicial 0xFFFF, sin reflexión, sin XOR final.
// Vector obligatorio: "123456789" -> 0x29B1 (plan de protocolo §4.1).
uint16_t crc16(const char *datos, size_t n) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= (uint16_t)((uint8_t)datos[i]) << 8;
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

// Envía `payload*HHHH\n` de una sola vez (sin String, buffer fijo).
void enviarLinea(const char *payload) {
  char tx[TX_MAX];
  size_t n = strlen(payload);
  if (n + 7 > sizeof(tx)) return;   // no ocurre con las tramas de este firmware
  memcpy(tx, payload, n);
  int k = snprintf(tx + n, sizeof(tx) - n, "*%04X\n", crc16(payload, n));
  if (k != 6) return;
  Serial.write((const uint8_t *)tx, n + 6);
}

/* ==================== I2C con verificación (FW-01, §4.8) ==================== */
// Se llama inmediatamente después de cada read16/write16 sobre el mismo
// objeto y antes de cualquier otra operación sobre él: en la librería 0.2.5
// un write16 posterior pisa el error de un read16 previo, y read16 exitoso
// no limpia _error (lo limpia lastError()).
bool verificarI2C(PCF8575 &dev, uint8_t bitPcf) {
  if (dev.lastError() != PCF8575_OK) {
    i2cErr++;
    pcfErrVentana |= bitPcf;
    return false;
  }
  return true;
}

bool escribirOut1() { pcf_out_1.write16(estadoOut1); return verificarI2C(pcf_out_1, BIT_OUT_1); }
bool escribirOut2() { pcf_out_2.write16(estadoOut2); return verificarI2C(pcf_out_2, BIT_OUT_2); }

// Lleva ambas salidas al estado seguro. True si las dos escrituras se confirmaron.
bool apagarTodo() {
  estadoOut1 = 0xFFFF;
  estadoOut2 = 0xFFFF;
  bool ok1 = escribirOut1();
  bool ok2 = escribirOut2();
  return ok1 && ok2;
}

/* ==================== SETUP ==================== */
void setup() {
  // FW-D3: antes de Wire.begin() no se toca ninguna salida. Los PCF8575
  // arrancan por hardware con todos los pines en alto (= salidas OFF).
  Serial.begin(115200);
  analogReadResolution(12);        // fija 12-bit explícito, no depende del default del core
  analogSetAttenuation(ADC_11db);  // fija rango ~0-3.3V explícito, evita cambios de rango entre versiones
  Wire.begin(I2C_SDA, I2C_SCL);

  // FW-D3: primera acción útil = salidas a 0xFFFF, verificadas. No se usa
  // begin() de la librería para que esta sea la primera escritura.
  pcf_out_1.lastError();
  pcf_out_2.lastError();
  apagarTodo();

  // Entradas y MUX en alto (pines cuasi-bidireccionales: alto = lectura).
  pcf_in_1.write16(0xFFFF); verificarI2C(pcf_in_1, BIT_IN_1);
  pcf_in_2.write16(0xFFFF); verificarI2C(pcf_in_2, BIT_IN_2);
  pcf_in_3.write16(0xFFFF); verificarI2C(pcf_in_3, BIT_IN_3);
  pcf_mux.write16(0xFFFF);  verificarI2C(pcf_mux, BIT_MUX);

  for (int i = 0; i < numAnalogInputs; i++) {
    analogValues[i] = 0;
    analogMin[i] = 4095;
    analogMax[i] = 0;
  }

  // Autoprueba del CRC: si falla, toda línea saldría con un CRC que el PC
  // rechaza. Se queda con las salidas apagadas, sin BOOT y sin aceptar
  // órdenes; el PC lo ve como TARJETA_SIN_TRAMA_VALIDA.
  if (crc16("123456789", 9) != 0x29B1) {
    for (;;) { apagarTodo(); delay(500); }
  }

  // FW-D2: ID = MAC de fábrica. getEfuseMac() guarda el primer byte de la
  // MAC en el byte bajo: se imprime en el orden habitual de la MAC.
  uint64_t mac = ESP.getEfuseMac();
  for (int i = 0; i < 6; i++) {
    snprintf(&idTarjeta[i * 2], 3, "%02X", (unsigned)((mac >> (8 * i)) & 0xFF));
  }
  idTarjeta[12] = '\0';

  sincronizado = false;   // FW-D3: estado inicial NO_SINCRONIZADO
  wdFlag = 0;
  tLastRx = millis();

  char boot[48];
  snprintf(boot, sizeof(boot), "BOOT %s %d %s", FW_VERSION, PROTOCOLO, idTarjeta);
  enviarLinea(boot);
}

/* ==================== LOOP ==================== */
void loop() {
  leerSerial();          // PRIORIDAD 1
  leerAnalogico();       // PRIORIDAD 2
  leerDigital();         // PRIORIDAD 3
  publicarEstados();     // PRIORIDAD 4
  verificarWatchdog();   // PRIORIDAD 5
}

/* ==================== RECEPCIÓN (FW §4.3) ==================== */
void leerSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;            // se elimina \r antes de todo
    if (c == '\n') {
      if (rxDescartando) {
        rxDescartando = false;           // fin de la línea larga, ya contada
      } else {
        rxBuf[rxLen] = '\0';
        procesarLinea(rxBuf, rxLen);
      }
      rxLen = 0;
      continue;
    }
    if (rxDescartando) continue;
    if (rxLen >= RX_MAX - 1) {
      // Desborde: la línea entera se descarta hasta el próximo \n. Cuenta
      // como línea inválida (crc_rx_err) y no reinicia el watchdog.
      rxDescartando = true;
      rxLen = 0;
      rxLargas++;
      crcRxErr++;
      continue;
    }
    rxBuf[rxLen++] = c;
  }
}

bool esHexMayuscula(char c) {
  return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F');
}

// Valida `payload*HHHH` sobre el texto recibido tal cual. Devuelve la
// longitud del payload o -1 si el CRC falta, está mal formado o no coincide.
int validarCRC(const char *linea, uint8_t n) {
  if (n < 5 || linea[n - 5] != '*') return -1;
  uint16_t recibido = 0;
  for (uint8_t i = n - 4; i < n; i++) {
    char c = linea[i];
    if (!esHexMayuscula(c)) return -1;
    recibido = (uint16_t)((recibido << 4) | (c <= '9' ? c - '0' : c - 'A' + 10));
  }
  uint8_t largo = n - 5;
  if (crc16(linea, largo) != recibido) return -1;
  return largo;
}

void procesarLinea(char *linea, uint8_t n) {
  int largo = validarCRC(linea, n);
  if (largo < 0) {
    // Línea inválida: se descarta, se cuenta, sin ACK y sin reiniciar el
    // watchdog (FW-03, FW-D5).
    crcRxErr++;
    return;
  }

  // FW-D5: solo una línea de CRC válido reinicia el watchdog y borra wd.
  tLastRx = millis();
  wdFlag = 0;

  // Normalización después del CRC: trim y mayúsculas.
  char cmd[RX_MAX];
  int ini = 0;
  while (ini < largo && linea[ini] == ' ') ini++;
  int fin = largo;
  while (fin > ini && linea[fin - 1] == ' ') fin--;
  int m = 0;
  for (int i = ini; i < fin; i++) cmd[m++] = (char)toupper((unsigned char)linea[i]);
  cmd[m] = '\0';

  enviarLinea("ACK");

  if (strcmp(cmd, "HB") == 0) return;   // latido: solo mantiene viva la conexión

  if (strcmp(cmd, "VER") == 0) {
    char ver[48];
    snprintf(ver, sizeof(ver), "VER %s %d %s", FW_VERSION, PROTOCOLO, idTarjeta);
    enviarLinea(ver);
    return;
  }

  if (strcmp(cmd, "ALL_OFF") == 0) {
    // Solo se confirma (y se sale de NO_SINCRONIZADO) si las dos escrituras
    // se verificaron: un OK ALL_OFF falso dejaría al PC creyendo que todo
    // está apagado. Sin OK, el PC reintenta y luego alarma.
    if (apagarTodo()) {
      sincronizado = true;
      enviarLinea("OK ALL_OFF");
    }
    return;
  }

  if (strcmp(cmd, "RESET_MINMAX") == 0) {
    for (int i = 0; i < numAnalogInputs; i++) {
      analogMin[i] = 4095;
      analogMax[i] = 0;
    }
    enviarLinea("OK RESET_MINMAX");
    return;
  }

  if (strncmp(cmd, "SET DO", 6) == 0) {
    procesarSet(cmd + 6);
    return;
  }
  // Comando desconocido con CRC válido: solo ACK (igual que V2).
}

// `resto` = "<n> ON|OFF" (sin espacio entre DO y el número).
void procesarSet(const char *resto) {
  // FW-D4: en NO_SINCRONIZADO se rechaza toda orden de salida, sin OK.
  if (!sincronizado) {
    rechazados++;
    return;
  }

  int num = 0;
  int i = 0;
  while (resto[i] >= '0' && resto[i] <= '9' && i < 3) {
    num = num * 10 + (resto[i] - '0');
    i++;
  }
  if (i == 0 || resto[i] != ' ' || num < 1 || num > 32) return;
  const char *estado = resto + i + 1;
  bool on;
  if (strcmp(estado, "ON") == 0) on = true;
  else if (strcmp(estado, "OFF") == 0) on = false;
  else return;   // V2 tomaba cualquier otro texto como OFF; ahora se ignora

  bool ok;
  if (num <= 16) {
    bitWrite(estadoOut1, num - 1, !on);
    ok = escribirOut1();
  } else {
    bitWrite(estadoOut2, num - 17, !on);
    ok = escribirOut2();
  }
  if (!ok) return;   // sin OK: el error queda en pcf_ok / i2c_err

  char resp[24];
  snprintf(resp, sizeof(resp), "OK DO%d %s", num, on ? "ON" : "OFF");
  enviarLinea(resp);
}

/* ==================== WATCHDOG (FW-D5) ==================== */
// Armado solo en SINCRONIZADO: fuera de él las salidas ya están en 0xFFFF y
// los SET se rechazan, así que no hay nada que apagar.
void verificarWatchdog() {
  if (!sincronizado) return;
  if (millis() - tLastRx > WD_TIMEOUT_MS) {
    apagarTodo();
    sincronizado = false;
    wdFlag = 1;
    enviarLinea("WD: ALL_OFF");
  }
}

/* ==================== ANALÓGICO ESCALONADO ==================== */
#define ADC_SAMPLES     64      // muestras promediadas por canal (era 8 — reduce ruido aleatorio ~2.8x)
#define ADC_SETTLE_US  800      // µs de espera tras cambio de MUX (era 500 — margen adicional de asentamiento)
#define ADC_MS_PER_CH   20      // ms entre canales (16 ch × 20 ms = 320 ms ciclo)
#define ADC_DISCARD      2      // muestras descartadas tras cambio de canal, antes de promediar

void leerAnalogico() {
  if (millis() - tAnalog < ADC_MS_PER_CH) return;
  tAnalog = millis();

  // 1. Cambiar canal del MUX. FW-07: el byte bajo en 0xFF deja P0-P7 del
  // 0x26 en alto, para que DI49-DI56 se lean como entradas.
  uint16_t muxBits = (uint16_t)(((analogChannel & 0x0F) << 8) | 0x00FF);
  pcf_mux.write16(muxBits);
  if (!verificarI2C(pcf_mux, BIT_MUX)) {
    // Canal no seleccionado con certeza: no se muestrea, se conserva el
    // valor previo y se marca en ai_inv (plan de protocolo §5.4).
    bitSet(aiInv, analogChannel);
  } else {
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
    bitClear(aiInv, analogChannel);

    if (analogValues[analogChannel] < analogMin[analogChannel]) analogMin[analogChannel] = analogValues[analogChannel];
    if (analogValues[analogChannel] > analogMax[analogChannel]) analogMax[analogChannel] = analogValues[analogChannel];
  }

  analogChannel++;
  if (analogChannel >= numAnalogInputs) analogChannel = 0;
}

/* ==================== DIGITALES ==================== */
// Arrancan en 0xFFFF (= todas inactivas) hasta la primera lectura válida.
uint16_t d1 = 0xFFFF, d2 = 0xFFFF, d3 = 0xFFFF, d4 = 0xFFFF;

// Si una lectura falla se conserva el último valor válido y el bit del
// expansor baja en pcf_ok; el PC decide (FW-01, plan de protocolo §5.5).
void leerDigital() {
  if (millis() - tIO < 50) return;
  tIO = millis();

  uint16_t v;
  v = pcf_in_1.read16(); if (verificarI2C(pcf_in_1, BIT_IN_1)) d1 = v;
  v = pcf_in_2.read16(); if (verificarI2C(pcf_in_2, BIT_IN_2)) d2 = v;
  v = pcf_in_3.read16(); if (verificarI2C(pcf_in_3, BIT_IN_3)) d3 = v;
  v = pcf_mux.read16();  if (verificarI2C(pcf_mux, BIT_MUX))   d4 = v;
}

/* ==================== SALIDAS: REFRESCO Y LECTURA DE VUELTA ==================== */
// Cada 500 ms (FW-06, plan de protocolo §5.6): reescribe la sombra (corrige
// un reinicio espontáneo del expansor), verifica, lee el puerto de vuelta y
// arma disc_do. disc_do es solo diagnóstico en el PC hasta validarlo con la
// carga real (D-05). Si la lectura falla, ese expansor no aporta bits.
void refrescarSalidas() {
  uint32_t disc = 0;
  uint16_t real;

  if (escribirOut1()) {
    real = pcf_out_1.read16();
    if (verificarI2C(pcf_out_1, BIT_OUT_1)) disc |= (uint32_t)(real ^ estadoOut1);
  }
  if (escribirOut2()) {
    real = pcf_out_2.read16();
    if (verificarI2C(pcf_out_2, BIT_OUT_2)) disc |= (uint32_t)(real ^ estadoOut2) << 16;
  }
  discDo = disc;
}

/* ==================== PUBLICAR ESTADOS ==================== */
// uint64 a decimal sin depender de %llu en printf.
void u64aTexto(uint64_t v, char *out) {
  char tmp[21];
  int i = 0;
  do {
    tmp[i++] = (char)('0' + (v % 10));
    v /= 10;
  } while (v > 0);
  int j = 0;
  while (i > 0) out[j++] = tmp[--i];
  out[j] = '\0';
}

void publicarEstados() {
  if (millis() - tPublish < 500) return;
  tPublish = millis();

  refrescarSalidas();

  char linea[TX_MAX];
  int n;

  // AI:<16 valores decimales>
  n = snprintf(linea, sizeof(linea), "AI:");
  for (int i = 0; i < numAnalogInputs; i++) {
    n += snprintf(linea + n, sizeof(linea) - n, i < numAnalogInputs - 1 ? "%u," : "%u",
                  (unsigned)analogValues[i]);
  }
  enviarLinea(linea);

  // DI:<56 bits>, 1 = activa (pin en bajo)
  n = 0;
  linea[n++] = 'D'; linea[n++] = 'I'; linea[n++] = ':';
  for (int i = 0; i < 16; i++) linea[n++] = bitRead(d1, i) ? '0' : '1';
  for (int i = 0; i < 16; i++) linea[n++] = bitRead(d2, i) ? '0' : '1';
  for (int i = 0; i < 16; i++) linea[n++] = bitRead(d3, i) ? '0' : '1';
  for (int i = 0; i < 8;  i++) linea[n++] = bitRead(d4, i) ? '0' : '1';
  linea[n] = '\0';
  enviarLinea(linea);

  // DO:<32 bits> de la sombra, 1 = ON (contenido igual a V2)
  n = 0;
  linea[n++] = 'D'; linea[n++] = 'O'; linea[n++] = ':';
  for (int i = 0; i < 16; i++) linea[n++] = bitRead(estadoOut1, i) ? '0' : '1';
  for (int i = 0; i < 16; i++) linea[n++] = bitRead(estadoOut2, i) ? '0' : '1';
  linea[n] = '\0';
  enviarLinea(linea);

  // ST:<ver>,<pcf_ok>,<disc_do>,<ai_inv>,<crc_rx_err>,<i2c_err>,<wd>,<uptime_s>,<sync>
  // pcf_ok retiene un error durante la ventana de publicación en que ocurrió.
  uint8_t pcfOk = (uint8_t)(PCF_TODOS & ~pcfErrVentana);
  pcfErrVentana = 0;
  char uptime[21];
  u64aTexto((uint64_t)esp_timer_get_time() / 1000000ULL, uptime);   // 64 bits: sin desborde
  snprintf(linea, sizeof(linea), "ST:%d,%02X,%08lX,%04X,%lu,%lu,%u,%s,%u",
           PROTOCOLO, (unsigned)pcfOk, (unsigned long)discDo, (unsigned)aiInv,
           (unsigned long)crcRxErr, (unsigned long)i2cErr, (unsigned)wdFlag, uptime,
           sincronizado ? 1u : 0u);
  enviarLinea(linea);
}
