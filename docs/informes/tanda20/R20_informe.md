# Informe R20 — Tanda 20: cierre de la migración a Modbus TCP (M31-U) y Setup con Modbus

Fecha: 27-oct-2026. Rama `tanda-20` desde `dev` (391aedf). Ejecución sin supervisión (Claude Code).
Fuentes: `docs/mis_plans/decisiones_tanda_20.md` (T20-01 a T20-06), `adenda_tanda_19_banco.md` (ADB-01 a ADB-05), `docs/informes/banco_m31_2026-10-27.md`, `planeacion_enlace_modbus.md`.

> BORRADOR: se completa en I, R, K y Z.

## 1. Resumen

(se completa en Z)

## 2. A0 y línea base

- Árbol limpio, sin cambios de fin de línea. Commit de documentos 2c05e2f.
- Línea base (`base_suite.txt`): 8838 pruebas recolectadas; en paralelo 8822 passed, 10 skipped, 3 xfailed y 3 fallidas solo en paralelo (Qt: `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`, `test_main_window_navigate_payload.py::test_navigate_to_payload_none_no_llama_set_context` y `::test_navigate_to_sin_payload_no_falla`), verdes en serie.

## 3. B · Copia de seguridad previa al retiro del serial (T20-01)

- Carpeta: `G:\Respaldos_autoclave\pre_tanda20_20261027_1448\`.
- `repo_completo.bundle` (`git bundle create --all`), 214 976 422 bytes, SHA-256 `2224aa05770c2249b44d8819decc2af113f71b9cc411d010f863118503b9a86e`; `git bundle verify` «okay», releído desde G:.
- `dev_391aedf.zip` (`git archive` de `dev` en 391aedfdd74f486183caba18e8664adb66bdc78c; incluye `Hardware/Comunicacion_esclava_ESP32_V2` y `_V3`, `serial_link.py`, `calibration.yaml`), 171 380 887 bytes, SHA-256 `32c6cba444563f31e5a469b8d010ca3cb2fb17a2d7b668682fe2a730681a29ae`.
- `LEEME.txt` con fecha, commit, etiqueta, SHA-256 y cómo restaurar (`git clone repo_completo.bundle`).
- Etiqueta local anotada `respaldo-serial-pre-t20` sobre 391aedf (sin push).

## 4. V · Verificaciones (resumen)

- **V-01 (inventario del serial):** lista de borrado/migración/conservación por archivo. Puntos que condicionaron el trabajo: `enlace_io` se importa al cargar `converters.py`, `rutas/sistema.py` y `factory.py`; la calibración neutra de la compilación son 4 piezas (`Autoclave.spec`, `verificar_calibracion_neutra.py`, `verificar_entrega_neutra.py`, `compilar_entrega.py`); `_ALARMAS_PIDEN_HANDSHAKE` contiene 4 alarmas que emite ModbusLink (se conserva, ver §8); `crc16.py`, `device_reset.py` y `serial_link.json` solo los usa el serial; `pyserial` solo lo importa `serial_link.py` (pymodbus y escpos lo tratan como opcional).
- **V-02 (pruebas):** ~135 funciones a borrar (+20 de `crc16`/`device_reset`), ~90 a migrar; propuesta de doble en memoria de `EnlaceES`; 5 conflictos con la letra de T20-03 resueltos como se indica en §8.
- **V-03 (adenda):** ubicación de composición, firmware, 0x0C37 y configuración de seguridad en `modbus_link.py`; `_escribir_configuracion` no leía antes de escribir (ADB-04 lo necesita); el manual solo admite fc06 en 0x0C1D; la tabla de compatibilidad del manual (cap. 6) no es monótona; `_puerto_backend_ocupado` importa PySide6 (el rol usa un socket directo).
- **V-04 (Setup):** pasos de estación, Reparar, desinstalación y silencioso en `autoclave.iss`; pruebas estáticas existentes del `.iss`; la casilla de red no va en `[Tasks]` para no romper pruebas existentes; la contraseña de autologon ya viaja por entorno, nunca por línea de comandos; `enlace_io.json` llega por los `.spec`, no por el `.iss`.

## 5. F · Fundaciones

- F2 (bfc6f93): sección i18n `configurar_modulo.*` (es/en) para el resultado del rol. Los textos del Setup van en `[CustomMessages]` del `.iss` (dueño s3) — DECISIÓN SIN CONFIRMAR, para no partir el archivo entre dos agentes.
- F1 (0da003a): `tests/helpers/enlace_doble.py` (`EnlaceDoble`, doble en memoria de `EnlaceES`) y fixture `enlace_doble`; 7 pruebas en `tests/test_t20_f1_enlace_doble.py`.

## 6. P · Implementación

### s1 · Adenda y rol (rama `tanda-20-s1`, 75857ed y d0510ac; unida en 9fce64a)

- **ADB-01:** composición esperada de 5 esclavos (ID 0..4) `GXAXX0A00, GAXXXA000, GXXAX00A0, GXXAX00A0, GXDXX0600`; se lee el ID 5, que debe ser NONE; el principal `XAXX0A00G` se sigue comparando aparte; mensajes «esclavo ID i».
- **ADB-02:** firmware solo por la versión (byte bajo de 0x0C1F y de 0x0D80; texto 0x0C2C del principal, que prevalece si discrepa, con aviso en el log); byte bajo 0 → ilegible (falla cerrada); cada esclavo ≤ principal. El caso real (`9232-0-13` frente a 10, 12, 12, 12, 10) conecta; `tarjeta()["version"] = "9232-0-13 / 10,12,12,12,10"`. La tabla del manual no es monótona (9232-0-11 admite 9233-0-12; 9232-0-12 no lista 9304-0-10): la regla es una simplificación (va a MED-04/registro).
- **ADB-03:** id = MAC del principal `005404849DB1` (prueba fija el caso).
- **ADB-04:** lee cada bloque antes de escribir; solo si alguno difiere: escribe y verifica, apaga todas las bobinas (fc0F), reinicia el módulo (fc06 0x0C1D = 0x5BB5), desconecta, espera `espera_reinicio_s` (5 s), reabre dentro de `presupuesto_reinicio_s` (30 s), relee identidad y TODA la configuración sin escribir; diferencia → `TARJETA_CONFIG_SEGURIDAD`. Sin diferencias, no reinicia. Contador `reinicios_modulo` en el diagnóstico. Todo con `_handshake_ok` en False (las salidas se rechazan).
- **ADB-05:** 0x0C37 solo se lee y se registra (`registro_0c37`, log en la conexión y como mucho cada 60 s en operación); no se escribe, no se exige 0, no da `TARJETA_WATCHDOG` ni invalida. Se eliminó `_tras_suspension`.
- **T20-04 · `--rol configurar-modulo`** (`src/autoclave/estacion/configurar_modulo.py`, despacho en `exe_unico.py`): `ModbusLink.leer_identidad()` (sin hilo, sin escribir) y `escribir_credenciales_web()` con el mismo cliente y lock; comprueba backend en 127.0.0.1:8000 (socket, sin PySide); `--ip`/`--puerto` solo con 127.0.0.1; presupuesto de 30 s con reintentos solo sin conexión; contraseña por `--clave-archivo` (se borra en `finally`; 1–6 ASCII imprimibles; fc10 en 0x758B y 0x7590 y relectura); resultado JSON plano ASCII; códigos 0/2/3/4/5/6/7. No escribe bobinas, configuración de seguridad ni 0x0C37, ni reinicia.
- Simulador: composición y firmware reales, reinicio por 0x0C1D (cierra conexiones, silencio, `reinicios`, `config_no_persiste`, `config_activa_tras_reinicio`), 0x0C37 como contador desde 100, credenciales web, `escrituras_bobinas()`.
- Pruebas nuevas: `tests/test_t20_s1_adb.py` (27) y `tests/test_t20_s1_rol.py` (19). Ninguna borrada. Aserciones cambiadas por decisión (comentario en cada una): en `test_t19_s1_enlace.py` (interfaz contra `EnlaceES` en vez de `SerialLink`; claves de diagnóstico; versión y firmware por ADB-02; V19-s1-07 «fc16 en cada bloque siempre» → solo en los bloques que difieren, con `reinicios == 1`, decisión 8/ADB-04; bandera 0x0C37, corte y watchdog por ADB-05) y en `test_t19_r1_enlace.py` (tres pruebas de la bandera 0x0C37 por ADB-05).

### s2 · Retiro del serial

(se completa al recibir el resultado)

### s3 · Setup y estación

(se completa al recibir el resultado)

## 7. T20-06 · Hoja de banco (f95e624)

- `pruebas.py` regenerado. Hallazgo: el `.md` tenía 29 pruebas que no estaban en `pruebas.py` (bloques E9, N11 y T12 y las filas C-05b..C-05i, D-39, D-X9-01/02, G-04, más 9 campos extra); regenerar sin portarlas las habría perdido. Se portaron todas a `pruebas.py` (campo `modo_texto` y `extra`, que `generar.py` ahora imprime). La hoja queda en 162 pruebas.
- Sin la ESP32: «USB de la tarjeta» → «cable de red de los módulos»; A-03 pasa a firmware de los módulos e ID (MAC); la prueba del buzzer con el paro usa DO 25; la de COM-03 en ciclo usa el corte por desconexión de los módulos; C-05h marcada como no aplicable con los M31-U reales (solo simulador).
- Bloque M: M-0 con el Setup (paso 08) y comprobación con `ipconfig`; M-1 sin `TARJETA_WATCHDOG` (ADB-05); M-5 ampliado (log del reinicio de ADB-04) y M-5b (prueba aislada de ADB-04); M-6 (cambio de enlace) retirado; M-7 nuevo «Setup con Modbus».

## 8. Decisiones sin confirmar y desvíos justificados

(se completa)

## 9. I · Integración

(se completa)

## 10. R · Revisión

(se completa)

## 11. K · Unión y entrega

(se completa)
