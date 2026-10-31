# Planeación — Enlace Modbus TCP con los módulos Ebyte M31-U (tanda 19)

Fecha: 27-oct-2026. Decisiones confirmadas por Cristian en el chat del 27-oct (ver `decisiones_tanda_19.md`). Lo marcado «DECISIÓN SIN CONFIRMAR» lo propone el diseño y se valida en el banco.

> **Tanda 23 (29-oct, `decisiones_tanda_23.md`):** el hardware de E/S (principal + expansiones) se llama «módulo E/S» (MES-01) y los identificadores `tarjeta` pasan a `modulo_es` (`EventoModuloEs`, `modulo_es()`, `modulo_es_st`); los códigos `TARJETA_*` se conservan y se muestran como `MODULO_ES_*` (MES-04). La presión se lee con fc04 0x0000 ×16 (AI 1–16 del principal → `ai[8..23]`, largo 24, AIN-03) y se numera AI 01–16; la temperatura, RTD 01–06 (AIN-01/02). MOD-04 y MOD-05 quedan actualizados abajo.

## 1. Contexto

- La tarjeta KinCony KC868-AIO (ESP32, protocolo serial v2) se reemplaza por módulos de E/S remotas Ebyte M31-U con el PC como maestro Modbus TCP. Motivos de Cristian: ruido del ADC interno (saltos de más de 100 cuentas) y fiabilidad del ESP32.
- Las pruebas de banco con la ESP32 no se habían empezado. La validación se hace directamente con Modbus.
- El enlace serial **se conserva como alternativa seleccionable** (MOD-01). Su retiro es una tanda posterior.
- Manuales en `docs/referencia/m31/`:
  - `M31-U_manual_principal_V1.4.pdf` (inglés) y su texto `M31-U_manual_principal_V1.4.txt`;
  - `M31-U_manual_expansiones_V1.3.pdf` (chino) y su texto `M31-U_manual_expansiones_V1.3.txt`.

  Las direcciones de esta planeación salen de ahí. Ante una diferencia, prevalece el manual del principal y se anota.

## 2. Hardware

Módulos (según sus etiquetas), en este orden en el riel:

1. Principal **M31-XAXX0A00G-U**: 16 AI de corriente de una sola terminal (0–20 / 4–20 mA, 3 ‰), 2 RJ45 con switch interno, RS485, switch DIP de dirección (4 bits), alimentación 9–36 VDC.
2. **M31-GAXXXA000-U**: 16 DI, NPN o PNP, 10–28 V, filtro de 6 ms.
3. **M31-GXXAX00A0-U** n.º 1: 16 DO de relé normalmente abierto, 5 A, común cada 8 salidas (máx. 8 A por común). Corresponde a DO 01–16.
4. **M31-GXXAX00A0-U** n.º 2: DO 17–32.
5. **M31-GXDXX0600-U**: 6 PT100 de 2 o 3 hilos, resolución 0,1 °C, exactitud ±(0,1 % + 1 °C).

Parámetros de fábrica del principal:
- IP 192.168.3.7/24, puerto 502, dirección Modbus 1 (DIP en 0 + desplazamiento 1);
- web en http://192.168.3.7 (admin/admin);
- hasta 5 clientes TCP.

Reglas del fabricante:
- Los módulos se unen y se separan siempre sin energía.
- Después de cambiar la composición o el orden hay que hacer la negociación (doble pulsación de Reload).
- El firmware del principal debe ser igual o más nuevo que el de las expansiones.

Mantener el botón Reload de 5 a 10 s restablece la configuración de fábrica. Por eso el software no confía en la configuración guardada en el módulo (MOD-07).

## 3. Alcance

Entra:
- `ModbusLink` con la misma interfaz que `SerialLink`;
- selección del enlace;
- mapa de datos y conversión;
- calibración de fábrica para Modbus;
- puertos ofrecidos según el enlace;
- buzzer en DO 25;
- conexión verificada y configuración de seguridad escrita y comprobada;
- vigilancia del lazo de control;
- diagnóstico de los módulos y alarmas;
- simulador M31 para las pruebas automáticas;
- SOUP, catálogo de alarmas, hoja de banco y riesgos.

No entra:
- la configuración de la red del PC (se hace a mano en el banco, MOD-17);
- el retiro de `SerialLink` y del firmware de la ESP32;
- Modbus RTU/RS485, AO, contadores de DI y modo pulso;
- cambios en las fases del ciclo o en la UI más allá de lo indicado.

## 4. Decisiones de diseño

### MOD-01 · Selección del enlace
- Archivo `src/autoclave/config/enlace_io.json` con `{"enlace": "modbus"}`. Valores admitidos: `"modbus"` o `"serial"`.
- Archivo ausente o inválido: `"modbus"`, con advertencia en el log. DECISIÓN SIN CONFIRMAR: valor por defecto.
- Se lee una vez al arrancar el backend; cambiarlo exige reiniciar.
- Una función de fábrica única (`devices/factory`: `build_enlace(units, al_conectar)`) construye `ModbusLink` o `SerialLink`. `backend/context.py` y `build_hardware` la usan en lugar de `build_serial`. El atributo del contexto conserva su nombre (`context.serial`) para no tocar los llamadores; Code puede añadir el alias `context.enlace`.
- El enlace activo se muestra en Información del equipo y se publica en `/status` (`enlace_io: "modbus" | "serial"`).

### MOD-02 · Interfaz común
- Code extrae la interfaz pública que usa hoy el resto del programa a un `Protocol` (`protocols/enlace.py`, `EnlaceES`). Ambas clases la cumplen.
- La interfaz incluye:
  - `start`, `stop` y `solicitar_handshake`;
  - `is_connected`, `puerto_presente` y `handshake_completo`;
  - `modulo_es` (antes `tarjeta`, tanda 23), `al_conectar` y `on_update`;
  - `edad_ultima_di`, `secuencia_ultima_di`, `secuencia_ultima_ai`, `estado_ultima_ai` y `edad_ultima_ai`;
  - `marcar_tick_control` y `expansor_fuera_de_linea`;
  - `tomar_eventos` (con el mismo `EventoModuloEs`, antes `EventoTarjeta`);
  - `get_state`, `get_diagnostico`, `set_output` y `all_off`.

  Code completa la lista con lo que V encuentre que se usa desde fuera de `serial_link.py`.
- Una prueba de conformidad compara los miembros públicos de las dos clases contra el `Protocol`.
- Equivalencias de significado en `ModbusLink`:
  - `puerto_presente()`: el último intento de abrir el socket TCP tuvo éxito, aunque luego no haya respuesta.
  - `is_connected()`: socket abierto, datos vivos y conexión verificada (MOD-06).
  - `handshake_completo`: conexión verificada.
  - `get_state()`: las mismas claves que hoy (`ai`[16], `ai_seq`, `di`[56], `do`[32], `port_open`, `data_alive`, `last_update`).

### MOD-03 · Mapa de datos

Lectura cíclica cada `periodo_sondeo_s` (0,1 s):
- **DI:** función 02, dirección 0x0000, 16 bits → `di[0..15]`; `di[16..55]` = 0.
- **DO leídas:** función 01, dirección 0x0000, 32 bits → `do[0..31]`.
- **Temperatura:** función 04, dirección 0x0DAC, 6 registros (PT100 1–6, entero con signo en décimas de °C) → `ai[0..5]`; `ai[6]` y `ai[7]` = `None` (no hay puerto).
- **Presión:** función 04, dirección 0x0000, 16 registros (AI 1–16 del principal, µA, contiguos 0x0000–0x000F según el manual del principal V1.4 §4.10.3) → `ai[8..23]`; la lista `ai` mide 24 (`N_AI`). Tanda 23 (AIN-03); antes 8 registros → `ai[8..15]`.

Códigos de diagnóstico de las PT100: 32766 (sensor desconectado o cable roto), −32766 (corto), 32765 (falla del chip), 32767 y −32768 (fuera de rango), −32767 (canal deshabilitado). El enlace los convierte en `None` y anota el código en el log una sola vez por episodio y canal.

Cuando el módulo de AI mide menos de 3,85 mA entrega 0. Ese 0 llega como valor crudo y la detección de falla de presión existente lo trata como fuera de rango bajo (MOD-04).

Secuencias:
- `ai_seq` aumenta en 1 por cada sondeo en el que temperatura y presión se leyeron bien en el mismo ciclo. La edad de la AI es la de ese sondeo.
- La DI tiene su propia secuencia y su propia edad, igual que hoy.

Conversión: `converters.convert_temperatures` y `convert_pressures` deben aceptar `None` en un canal crudo. El resultado de ese canal es `None` y su filtro se reinicia. El enlace serial nunca entrega `None`, así que su comportamiento no cambia (las pruebas existentes lo cubren).

### MOD-04 · Calibración de fábrica por enlace
- Archivo empaquetado nuevo `src/autoclave/config/calibration_modbus.yaml`, con su copia en `data/` en el compilado, por el mismo mecanismo que `calibration.yaml`. `utils/paths.calibration_path()` devuelve el del enlace activo. El escritor de calibración escribe en el del enlace activo.
- Fábrica de los canales Modbus:
  - **Temperatura (canales 0–5):** `adc_min` 0, `adc_max` 1000, `temp_min` 0, `temp_max` 100. Es la identidad: décimas de °C a °C.
  - **Presión (canales 0–15 desde la tanda 23, AIN-04; antes 0–7):** `adc_min` 4000, `adc_max` 20000, `pres_min` 0, `pres_max` 400 (kPa abs, transmisores de 0–4 bar abs). Los umbrales de falla de lazo calculados con los márgenes por defecto quedan en 3600 y 21000 µA.
- Piso de «señal presente»: hoy `Units._piso_adc_presion` usa `adc_min`. Se agrega el campo opcional `adc_piso_senal` a `FactorySensorCalibration` (si no está, se usa `adc_min`). En el archivo Modbus vale 3850, porque por debajo de 3,85 mA el módulo entrega 0 y cualquier valor de 3850 o más es señal real. DECISIÓN SIN CONFIRMAR.
- La calibración de usuario (offset/ganancia) no cambia.
- Tanda 23 (AIN-04): una copia en `data/` o un respaldo con 8 entradas de presión se completa al cargar con las nominales en los canales 8–15, sin tocar los 0–7, con registro en el log (`config/completar_presion.py`). Las AI 09–16 quedan con calibración nominal hasta calibrarlas en sitio (AIN-R3). `tools/verificar_calibracion_neutra.py` exige las 16.
- La compensación interna de las PT100 del módulo se fija en 0 (MOD-07): una sola fuente de calibración, el software.

### MOD-05 · Puertos ofrecidos y asignación de fábrica
- Con el enlace Modbus, `asignacion_io` ofrece:
  - DI 01–16;
  - DO 01–32;
  - temperatura RTD 01–06 (grupo `AI_TEMP`);
  - presión AI 01–16, que son AI 1–16 del principal (grupo `AI_PRES`).

  Tanda 23 (AIN-01/02): antes la temperatura se rotulaba AI 01–06 y la presión AI 09–16 (AI 1–8 del principal). El tipo sigue siendo `"AI"`; la ocupación y los conflictos van por grupo (AIN-R1). `asignacion_io.FORMATO` = 2; un archivo FORMATO 1 se migra al cargar (presión p → p − 8, mismo canal físico, AIN-05).

  Con el enlace serial se conservan los rangos de hoy.
- `server_reasignacion` ya publica los puertos desde esas constantes; se vuelven funciones del enlace activo.
- Una asignación guardada con un puerto fuera del rango del enlace activo recibe el mismo tratamiento que hoy tiene una asignación inválida. V lo localiza y Code lo documenta.
- **Buzzer en DO 25:** `buzer_alarma` pasa de DO 24 a DO 25 en la fábrica del código (`EstadoAutoclave.map_do`, índice 24) y en `config/instances/ACV-2026-001.yaml`. Motivo: el buzzer es de 24 VDC y el grupo de relés 17–24 conmuta cargas de otra tensión. Aplica a los dos enlaces.
- `set_io._CANALES_APAGADO_BASE` pasa a `range(1, 33)`: el apagado individual cubre todos los canales.
- El resto de las funciones conserva su número:
  - DI 01–14;
  - DO 01–23, con la DO 13 libre;
  - temperatura en 01, 02, 03 y 05;
  - presión en 09–12.

### MOD-06 · Conexión verificada (equivale al handshake)

Configuración en `src/autoclave/config/modbus_link.json`, validada como `serial_link_config` (tipo y rango por clave; un valor malo se rechaza con advertencia y se usa el interno):
- `ip` "192.168.3.7", `puerto` 502, `unit_id` 1 (1–247);
- `periodo_sondeo_s` 0,1 (0,05–1,0);
- `timeout_s` 0,3 (0,05–2,0);
- `fallos_para_desconexion` 3 (1–20);
- `reintento_conexion_s` 3,0;
- `presupuesto_conexion_s` 15,0;
- `tiempo_desconexion_modulo_ds` 10 (5–100, es decir, 0,5–10 s);
- `intentos_escritura_config` 3;
- `filtro_pt100` 1 (1–16);
- `filtro_ai` 0 (0–4);
- `composicion_esperada`: principal `XAXX0A00G` y expansiones, en orden, `["GAXXXA000", "GXXAX00A0", "GXXAX00A0", "GXDXX0600"]`;
- `tramas_discrepancia` 2;
- `discrepancia_dispara_fallo` true.

Pasos de la conexión, dentro de `presupuesto_conexion_s`. Un fallo produce un evento `handshake` con su alarma y un reintento cada `reintento_conexion_s`:
1. Abrir el socket TCP.
2. Leer:
   - código de error 0x7587 (debe ser 0) y negociación pendiente 0x758A (debe ser 0). Si no, `TARJETA_MODULOS_ORDEN`.
   - modelo del principal 0x0C20 (12 registros, texto) y de las expansiones 0x0C80 (8 registros por esclavo). Se comparan sin el prefijo «M31-» ni el sufijo «-U», sin espacios y sin distinguir mayúsculas, contra `composicion_esperada`. Un esclavo «NONE» cuenta como ausente. Si no coinciden, `TARJETA_VERSION_INCOMPATIBLE` con el detalle.
   - firmware del principal 0x0C1F y de cada expansión 0x0D80. Si el principal es más antiguo que alguna expansión, `TARJETA_VERSION_INCOMPATIBLE`.
3. Escribir y verificar la configuración de seguridad (MOD-07). Si falla, `TARJETA_CONFIG_SEGURIDAD`.
4. Apagar todo: función 0F con 32 bobinas en 0 y lectura con la función 01. Si no están todas en 0, `TARJETA_SALIDAS_NO_APAGADAS`.
5. Leer la MAC (0x7534, 3 registros) como ID de 12 hex en mayúscula. `modulo_es()` (antes `tarjeta()`) = `{"version": "<fw principal> / <fw expansiones>", "protocolo": "modbus-tcp", "id": <MAC>}`. Se llama `al_conectar(modulo_es)`; el emparejamiento FW-D7 con `board_id` del perfil funciona igual (solo advertencia).
6. Leer la bandera de falla 0x0C37. Si vale 1, se anota en el log que el módulo venía de un corte por desconexión (sin alarma: las salidas ya estaban apagadas).
7. Hacer un primer sondeo completo, DI y AI, válido. Desde ahí la conexión queda verificada y se emite el evento `conectada`.

Si las lecturas de texto o de versión no tienen el formato esperado, se anota el valor crudo en el log y la comparación falla cerrada. Si en el banco aparece un formato distinto, se corrige la comparación: no se relaja la regla.

### MOD-07 · Configuración de seguridad (escrita y verificada en cada conexión)

El módulo ignora en silencio una escritura con un valor fuera de rango y no devuelve error. Por eso cada bloque se escribe con la función 10, se lee con la función 03 y se compara exacto, hasta `intentos_escritura_config` veces. Nunca se confía en lo guardado en el módulo. Registros:
- 0x0C35 tiempo de desconexión = `tiempo_desconexion_modulo_ds` (10 = 1,0 s). DECISIÓN SIN CONFIRMAR hasta la prueba de banco M-1.
- 0x0C36 modo de falla por desconexión = 1.
- 0x1B58–0x1B77 estado de falla de cada DO = 1 (apagada).
- 0x2904–0x2923 estado de cada DO al encender = 0 (abierta).
- 0x32C8–0x32E7 modo de cada DO = 0 (nivel).
- 0x0DAC–0x0DBB (holding) rango de AI 1–16 = 1 (4–20 mA).
- 0x0DA2 filtro de AI = `filtro_ai`. V aclara en el manual si es un registro o uno por canal.
- 0x39A4–0x39A9 unidad de PT100 = 0 (°C).
- 0x38A4–0x38A9 compensación de PT100 = 0.
- 0x3AA4–0x3AA9 filtro de PT100 = `filtro_pt100`. DECISIÓN SIN CONFIRMAR: 1, para no sumar retardo a los filtros del software; el ruido se mide en el banco.
- 0x3BA4–0x3BA9 PT100 deshabilitada = 0.

Las direcciones holding de los canales de expansión siguen la numeración continua del manual: DO 1–32 son las de los dos módulos de relés en orden y PT100 1–6 las del módulo de PT100. Se confirma en el banco (M-3).

### MOD-08 · Vigilancia del lazo de control (equivale a FW-D6)
- El hilo de sondeo **solo hace tráfico Modbus**, sea lectura o escritura, si se cumple al menos una de estas condiciones:
  - el `ControlLoop` marcó un tick hace 1,5 s o menos (`MARGEN_TICK_CONTROL`, igual que en serial);
  - ninguna salida está comandada en ON ni leída en ON en el último sondeo, por ejemplo al arrancar o fuera de ciclo sin salidas.
- Si no se cumple ninguna, el hilo suspende todo el tráfico. A los `tiempo_desconexion_modulo_ds` sin tráfico el módulo pone las salidas en su estado de falla, que es apagado. Mismo efecto si el proceso muere, se cae la red o se desconecta el cable.
- Al reanudarse el tick, el enlace rehace la conexión verificada (MOD-06) y, si 0x0C37 = 1, emite `TARJETA_WATCHDOG` (evento `operacion`).
- Durante la operación, 0x0C37 = 1 también emite `TARJETA_WATCHDOG` e invalida la conexión.
- Este diseño no depende de qué peticiones reinician el temporizador del módulo, porque se corta todo el tráfico. La prueba M-1 confirma que el corte ocurre y cuánto tarda.

### MOD-09 · Pérdida de comunicación
- `fallos_para_desconexion` transacciones fallidas seguidas (timeout, excepción o respuesta de excepción Modbus) marcan `port_open`/`data_alive` en False, notifican a `Units` (DI de paro en 0, igual que hoy, A-3) y cierran el socket. La reconexión sigue MOD-06.
- La edad de DI y AI se toma del último sondeo correcto. Los umbrales del `ControlLoop` (DI vigente, AI vencida, ESG-01) no cambian.
- Todo temporizador usa `time.monotonic()`.

### MOD-10 · Diagnóstico en operación
- Cada 1 s (dentro del mismo hilo) se leen 0x7587, 0x7588 (2 registros), 0x758A y 0x0C37.
- 0x7587 = 1, o una máscara 0x7588 distinta de 0, en 2 lecturas seguidas: `TARJETA_EXPANSOR_FUERA_DE_LINEA`, y `expansor_fuera_de_linea()` devuelve True mientras dure (igual que hoy).
- 0x7587 = 2 o 0x758A = 1: `TARJETA_MODULOS_ORDEN` e invalidación de la conexión.
- `get_diagnostico()` conserva las claves de hoy:
  - `lineas_invalidas_total` y `lineas_invalidas_consecutivas` pasan a contar transacciones Modbus fallidas;
  - `handshake_completo`;
  - `modulo_es_st` (antes `tarjeta_st`) = None.

  Agrega `modulos` con: modelos, firmware, MAC, `codigo_error`, `mascara_expansores`, `falla_salidas` y `enlace`.

### MOD-11 · Salidas
- `set_output(canal, estado)` (1–32) escribe con la función 05 en la bobina `canal-1`. Se rechaza sin conexión verificada.
- El cliente pymodbus síncrono no es seguro entre hilos: todo el acceso al cliente pasa por un único lock. El registro de la orden y su escritura son atómicos, como TMG-03 del serial.
- `all_off(timeout)`: función 0F con 32 en 0 y luego lectura con la función 01 hasta `timeout`. Devuelve True solo si las 32 se leen en 0.
- Discrepancia entre lo comandado y lo leído: el mismo algoritmo que `SerialLink`:
  - tolerancia de 1 s desde el último cambio;
  - `tramas_discrepancia` sondeos;
  - un reenvío único;
  - si persiste, `DISCREPANCIA_SALIDAS`.

  Con `discrepancia_dispara_fallo` true, porque aquí la lectura sale del propio módulo de relés. DECISIÓN SIN CONFIRMAR.

### MOD-12 · Alarmas
- Se reutilizan, con la misma severidad y el mismo manejo:
  - `TARJETA_SIN_TRAMA_VALIDA` (sin respuesta Modbus durante la conexión);
  - `TARJETA_VERSION_INCOMPATIBLE`;
  - `TARJETA_SALIDAS_NO_APAGADAS` y `TARJETA_ALL_OFF_SIN_CONFIRMAR`;
  - `TARJETA_EXPANSOR_FUERA_DE_LINEA`;
  - `TARJETA_WATCHDOG`;
  - `TARJETA_REINICIO` (si el contador de vida no es aplicable, no se usa y se anota);
  - `DISCREPANCIA_SALIDAS`.
- Alarmas nuevas, de la misma clase que `TARJETA_ALL_OFF_SIN_CONFIRMAR` (bloqueante en el arranque; en ciclo, COM-03 con el origen del módulo E/S):
  - `TARJETA_CONFIG_SEGURIDAD`: no se pudo dejar verificada la configuración de seguridad de los módulos;
  - `TARJETA_MODULOS_ORDEN`: orden de módulos incorrecto o negociación pendiente.

  Acción para el técnico: «Sin energía, revisar el orden de los módulos y negociar (doble pulsación de Reload)».
- Textos en español e inglés con el mecanismo i18n. `docs/catalogo_alarmas.md` se actualiza.

### MOD-13 · SOUP
- Se agrega `pymodbus`, la versión estable 3.x más reciente que funcione con Python 3.14. Code la fija en `pyproject.toml` y `requirements.lock.txt`, y la registra en `docs/riesgos/lista_soup.md` con uso «Comunicación con los módulos de E/S (control de actuadores)» y clase C.
- Se usa solo el cliente síncrono `ModbusTcpClient`.
- Se comprueba que el `.spec` de PyInstaller la incluya (con `hiddenimports` si hace falta) y que el ejecutable la importe.

### MOD-14 · Pruebas automáticas
- Simulador M31 en `tests/helpers/m31_simulado.py`: un servidor pymodbus en el proceso, en un puerto libre de localhost, con el mapa de MOD-03, MOD-07 y MOD-10. Debe emular además:
  - el corte por desconexión (temporizador reiniciado por cualquier petición);
  - el descarte silencioso de escrituras fuera de rango;
  - los códigos de las PT100;
  - el 0 por debajo de 3,85 mA;
  - fallas inyectables: expansor sin respuesta, orden incorrecto, modelo distinto y escritura que no queda.
- Pruebas mínimas, con el marcador `req`:
  - conformidad de la interfaz;
  - mapa de datos y códigos de PT100 → None;
  - presión por debajo de 3,85 mA → falla de lazo;
  - conexión correcta y cada paso fallido con su alarma;
  - configuración reescrita tras un restablecimiento de fábrica simulado;
  - vigilancia del lazo: sin tick y con una salida en ON → cero tráfico, y el simulador apaga las salidas al vencer el tiempo; con todo apagado, el sondeo sigue;
  - pérdida y reconexión;
  - discrepancia;
  - selección del enlace y valor por defecto;
  - puertos según el enlace;
  - buzzer en DO 25;
  - calibración Modbus y piso de señal.
- Todas las pruebas existentes del enlace serial siguen pasando sin cambios.

### MOD-15 · Hoja de banco (bloque M, nuevo)
- **M-1 · Corte por desconexión:** con una salida encendida desde la pantalla de Entradas/Salidas, probar tres casos: quitar el cable de red, matar el proceso, y congelar el lazo (si existe una forma de prueba; si no, se omite). En cada caso, medir con cronómetro el tiempo hasta que el relé abre. Criterio: menos de 2 s.
- **M-2 · Composición:** sin energía, quitar el módulo de PT100 y arrancar → `TARJETA_VERSION_INCOMPATIBLE`. Reponerlo sin negociar → `TARJETA_MODULOS_ORDEN`. Negociar → conexión correcta.
- **M-3 · Canal por canal:** cada DI (01–14) con su función, cada DO (01–23 y 25) con su carga, cada PT100 (RTD 01–06) y cada transmisor (AI 01–16, desde la tanda 23). Confirmar las direcciones de las expansiones (MOD-07).
- **M-4 · Exactitud (MED-01, MED-02):** PT100 contra patrón en baño o calibrador a 121 y 134 °C; presión contra patrón a 100, 200 y 300 kPa abs. Registrar el error antes y después de la calibración de usuario.
- **M-5 · Restablecimiento de fábrica del módulo** (Reload 5–10 s) con el software corriendo: debe reconectar y reescribir la configuración de seguridad sola.
- **M-6 · Cambio de enlace** a serial y de vuelta a modbus con reinicio. Solo se comprueba que arranca; sin la tarjeta ESP32 conectada, el arranque queda bloqueado por la tarjeta, y eso es lo esperado.

### MOD-16 · Riesgos y anomalías conocidas (se registran, no bloquean la tanda; bloquean la liberación clínica)
- **MED-01 (ALTA):** exactitud de las PT100 del módulo ±(0,1 % + 1 °C), unos ±1,1 °C a 134 °C, frente a los umbrales de 0,1 °C (temperatura baja en esterilización), 1 K (coherencia C-02) y 2 K (C-03). Requiere la medición M-4 y la decisión de Cristian.
- **MED-02 (MEDIA):** exactitud de las AI de una sola terminal (3 ‰), unos ±1,2 a 1,5 kPa en 0–400 kPa, frente a `brecha_error_presion` de 2 kPa y `brecha_segura_presion` de 1,5 kPa.
- **MED-03 (MEDIA):** la configuración de seguridad vive en el módulo y un restablecimiento de fábrica la borra. Se mitiga con MOD-07 y M-5.
- Van a `docs/riesgos/registro_riesgos.md` y a las anomalías conocidas de la entrega.

### MOD-17 · Red y acceso al módulo (manual, fuera del software)
- El PC usa un puerto de red dedicado a los módulos con IP fija 192.168.3.10/24, sin puerta de enlace. El segundo RJ45 del principal queda libre y no se conecta a la red de oficina.
- La contraseña web del módulo (admin/admin) se cambia en el banco.
- Va a la hoja de banco como paso previo de M-1. Automatizarlo en `tools/estacion` es una tanda posterior.
