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

### s2 · Retiro del serial (rama `tanda-20-s2`, e6b2ac7..2828d25; unida en 20577d8)

Commits propios del retiro: `chore(t20): retiro` de código (e6b2ac7), empaquetado y dependencias (658692a), `Hardware/` (98c34da), migración de pruebas (f75e9d4, `test(t20)`) y documentación (2828d25).

- **Borrados:** `protocols/serial_link.py`, `serial_link_config.py`, `crc16.py`, `device_reset.py`, `config/serial_link.json`, `config/enlace_io.py` y `.json`, `config/calibration.yaml`, `config/plantillas/calibration_neutra.yaml`, `tools/log_calibracion_sensores.py` (DECISIÓN SIN CONFIRMAR: se borra, no se reescribe), `Hardware/Comunicacion_esclava_ESP32_V2/` y `_V3/`, `tests/helpers/serial_doble.py`; `pyserial` fuera de `pyproject.toml`, `requirements.lock.txt` y la lista SOUP, y desinstalado del entorno del proyecto en I.
- **Migrados:** `factory.build_enlace` (conserva el nombre) → `build_modbus`; `converters` sin `_enlace_modbus`, `ADC_MAXIMO` ni escala raw/4095 (sin calibración de fábrica completa → `None`); `asignacion_io.enlace() == "modbus"` y `puertos()` con los rangos Modbus; `paths` solo con `calibration_modbus.yaml`; `/status.enlace_io` e Información del equipo con la constante `"modbus"`; `ALARMAS_HANDSHAKE`/`ALARMAS_OPERACION` y `ALARMAS_SOLO_SERIAL` (historial) trasladadas a `protocols/enlace.py`; `ENLACES_IO = ("modbus",)` y sin la clave i18n `equipo.enlace_io_serial` (un `"serial"` antiguo se muestra «—»); «cable USB» → «cable de red» en COM-01, COM-02, CIC-11 y `TARJETA_SIN_TRAMA_VALIDA`; `Autoclave.spec` sin la plantilla serial y `verificar_calibracion_neutra.py` solo Modbus (falla si la compilación trae `calibration.yaml`); `info_compilacion.py` sin `Hardware/`; comentarios de `src/` sin el serial.
- **Conservados:** `_ALARMAS_PIDEN_HANDSHAKE` y el handshake de `EnlaceES` (ver §8), el 422 `calibracion_otro_enlace` (ahora rechaza respaldos de equipos serial), el atributo `context.serial`, `.gitignore`.
- Prueba nueva `tests/test_t20_s2_retiro_serial.py` (35).

**Pruebas borradas (T20-03, único objeto: enlace serial, firmware o ADC del serial) — 180 elementos recolectados:**

| Archivo | Pruebas | Motivo |
|---|---|---|
| `tests/test_crc16.py` (entero, 10) | todas | CRC de las tramas serie (`protocols/crc16.py`, retirado). |
| `tests/test_device_reset.py` (entero, 10) | todas | Reinicio PnP del adaptador USB-serie (`device_reset.py`, retirado). |
| `tests/test_e6_enlace_handshake.py` (entero, 57) | todas | Handshake VER/HB/ALL_OFF, ST/BOOT/WD y discrepancia de `SerialLink`. |
| `tests/test_serial_link_reset.py` (entero, 5) | todas | Reinicio del USB tras WinError 31 en `SerialLink`. |
| `tests/test_serial_link_v2_lector.py` (entero, 33) | todas | Lector de tramas v2, CRC, latido y `serial_link_config`. |
| `tests/test_serial.py`, `test_serial_directo.py`, `test_enviar_comando.py`, `test_flujo_unidades.py` | (guiones sin pruebas) | Guiones manuales contra la ESP32 / COM7. |
| `tests/test_adenda_enlace_paro.py` | `test_sin_trama_di_la_edad_es_none`, `test_trama_di_fija_el_sello_monotonico`, `test_trama_ai_no_renueva_el_sello_di`, `test_di_malformada_no_renueva_el_sello`, `test_connect_pone_di_en_cero_y_borra_el_sello`, `test_disconnect_borra_el_sello` | Sello DI dentro de `SerialLink` (la propiedad A-3 de la DI a cero al reconectar se migró a ModbusLink en `test_t20_r2_enlace_migradas.py`, V20-s2-01). |
| `tests/test_t8_s2a_29_tramas_di_distintas.py` | `test_sin_trama_di_la_secuencia_es_none`, `test_cada_trama_di_valida_avanza_la_secuencia`, `test_di_malformada_no_avanza_la_secuencia`, `test_disconnect_deja_la_secuencia_en_none_y_la_siguiente_es_distinta` | Secuencia DI de `SerialLink` (ModbusLink la cubre en `test_t19_s1_enlace.py`). |
| `tests/test_t8_e1_aire_atmosferico_prueba.py` | `test_enlace_sin_trama_ai_la_edad_es_none`, `test_enlace_trama_ai_fija_su_sello`, `test_enlace_ai_malformada_no_renueva_el_sello`, `test_enlace_disconnect_borra_el_sello_ai`, `test_enlace_connect_borra_el_sello_ai`, `test_serial_link_numera_las_tramas_ai` | Sello AI y `ai_seq` de `SerialLink`. |
| `tests/test_u4_tarjeta_desconectada.py` | `test_sin_escanear_el_puerto_no_esta_presente`, `test_escaneo_sin_puerto_no_esta_presente`, `test_puerto_abierto_esta_presente`, `test_puerto_que_no_abre_no_esta_presente`, `test_timeout_de_datos_cierra_pero_el_puerto_sigue_presente`, `test_lineas_invalidas_cierran_pero_el_puerto_sigue_presente`, `test_error_de_lectura_es_puerto_perdido`, `test_error_de_escritura_no_basta_para_puerto_perdido`, `test_stop_deja_el_puerto_ausente`, `test_conectar_notifica_la_di_en_cero_a_units` | Presencia del puerto COM en `SerialLink` (la DI a cero al conectar: migrada, V20-s2-01). |
| `tests/test_s9_revision_2.py` | `test_serial_link_estado_ultima_ai` | Detalle interno de `SerialLink`. |
| `tests/test_t2_p3_di_vencida.py` | `test_tolerancia_no_supera_el_watchdog_del_firmware_menos_un_segundo` | Leía `WD_TIMEOUT_MS` del `.ino` (firmware); queda la anomalía HAZ-T2-03 (§8). |
| `tests/test_s1_sen01_convertidor.py` | `test_tarjeta_que_satura_en_4095_antes_de_21_ma_deja_inactiva_la_alta`, `test_canal_sin_calibracion_de_fabrica_conserva_el_comportamiento_previo` | ADC 4095 / raw/4095 (la mitad no serial de la segunda se migró, V20-s2-03). |
| `tests/test_t19_f2_enlace.py` | `test_archivo_del_producto_selecciona_modbus`, `test_valores_admitidos_y_defecto` (7), `test_archivo_ausente_o_invalido_da_modbus`, `test_se_lee_una_vez_por_proceso`, `test_fijar_enlace_rechaza_valores_no_admitidos`, `test_build_enlace_serial_usa_build_serial`, `test_evento_tarjeta_se_reexporta_desde_serial_link`, `test_serial_link_cumple_la_interfaz`, caso serial de `test_status_publica_el_enlace_activo` | Selección por `enlace_io.json` y conformidad/reexportación de `serial_link`. |
| `tests/test_t19_s2_conversion.py` | `test_serial_sin_calibracion_conserva_raw_4095`, `test_serial_no_cambia_con_lista_de_16_enteros` | Conversión serial. |
| `tests/test_t19_r2_conversion.py` | `test_serial_no_cambia` | Conversión serial. |
| `tests/test_t19_s2_puertos.py` | `test_puertos_serial_sin_cambios`, `test_puertos_se_leen_en_cada_llamada`, `test_api_publica_los_puertos_serial`, casos serial de `test_fabrica_valida_en_los_dos_enlaces` y `test_buzzer_enciende_el_canal_25` | Puertos y selección del serial. |
| `tests/test_t19_r2_respaldo.py` | `test_serial_rechaza_otra_fabrica_del_mismo_enlace`, `test_serial_misma_fabrica_se_restaura` | Calibración serial activa. |
| `tests/test_t19_s3_exposicion_enlace.py` | casos serial de `test_status_y_system_info_publican_el_enlace`, `test_info_sistema_fila_del_enlace`, `test_panel_equipo_fila_del_enlace` | Enlace serial seleccionado. |
| `tests/test_t8_k8_calibracion_neutra.py` | `test_plantilla_usuario_neutra`, `test_plantilla_fabrica_igual_a_la_del_repositorio`, `test_plantilla_valida_con_el_esquema`, `test_spec_empaqueta_la_plantilla`, `test_verificador_acepta_la_plantilla`, `test_verificador_rechaza_la_calibracion_de_banco` | Plantilla neutra serial y escala ADC del banco. |
| `tests/test_t9_e9_entrega_neutra.py` | `test_verificador_rechaza_calibracion_de_banco` (versión serial) | Calibración serial del banco; migrada a Modbus con el mismo nombre (V20-s2-02). |

**Pruebas migradas con aserción intacta** (literal cambiado con comentario cuando lo exige una decisión): `test_b9_buzzer_paro` (`EnlaceRegistrador`, extensión de `EnlaceDoble`; además variante con ModbusLink real y el simulador en `test_t20_r2_enlace_migradas.py`, V20-s2-04), `test_arranque_sin_tarjeta` (`_EnlaceSinTarjeta` sobre `EnlaceDoble`), `test_door_from_profile` (5) y `test_e6_emparejamiento_tarjeta` (parchean `ModbusLink`), `test_control_loop_resilience` (`TimeoutError` genérico), `test_converters_smoothing` (calibración de fábrica Modbus explícita; 3500 → 2400 para quedar dentro del rango PT100), `test_t19_f2_enlace` (mensaje «enlace Modbus no está disponible»), `test_t19_s2_calibracion`, `test_t19_s2_conversion`, `test_p1_rutas_build_congelado`, `test_t9_e9_refresco_config_fabrica`, `test_t19_r2_verificador`, `test_t9_e9_entrega_neutra` (`calibration_modbus.yaml`), `test_alarmas_catalogo` (ids desde `enlace.py`, igualdad intacta), `test_t19_integracion_modbus`, `test_t19_s3_exposicion_enlace` (`"serial"` como valor desconocido), `test_r8_asignacion_io` y `test_r8_reasignacion_api` (DI ≤ 16 por MOD-05: paro 30 → 16, puerta 20 → 15, `DI[-1]` 48 → 16), alias `PUERTOS_*` → `aio.puertos()[...]` en 5 archivos `test_r8_*`, `test_u4::test_com01_texto_de_tarjeta_desconectada` («cable de red»), `test_ver_entrega` (`Hardware/placa.txt` → `src/autoclave/placa.txt`), `test_b2_spec_excludes` (sin "serial"); `conftest` sin `enlace_io` ni `enlace_modbus`.

### s3 · Setup y estación (rama `tanda-20-s3`, 30499a8 y f2cc939; unida en cab7dfd)

- **Paso 08** (`tools/estacion/08_red_modulos.ps1`, `08_revertir_red_modulos.ps1`, funciones puras en `_red_modulos_puras.ps1`): adaptador elegido por MAC, solo Ethernet físico (802.3, sin Wi-Fi, Bluetooth ni virtuales); conflicto si otro adaptador está en 192.168.3.0/24; respaldo (`datos\estacion\respaldo_08_red_modulos.json`, DECISIÓN SIN CONFIRMAR: nombre por la convención de `_comun.ps1`) antes de cambiar nada; 192.168.3.10/24 sin puerta de enlace ni DNS y DHCP desactivado; verificación final (una 169.254.x.x no cuenta). La reversión restaura desde el respaldo y sin respaldo no toca nada.
- **`autoclave.iss`:** página «Red de los módulos de E/S» después de la de la cuenta, con casilla marcada por defecto, independiente de la casilla de estación; preselección del adaptador con 192.168.3.10; advertencia si el elegido es el único con puerta de enlace; `/ADAPTADOR=` en silencioso; `Paso08` y `Adaptador08` en el registro; se aplica también en Reparar (antes de su `exit`); el desinstalador revierte el 08 antes que el 07. Página de contraseña web (dos campos ocultos, 1–6 ASCII imprimibles, obligatoria en instalación nueva, opcional en actualización/Reparar, archivo en `{tmp}` + `--clave-archivo`, borrado en `finally`). Prueba de conexión con `--rol configurar-modulo --resultado` y página final con un texto es/en por código. El `.iss` no nombra `enlace_io`.
- Pruebas: `tests/test_t20_s3_setup_modbus.py` (22) y `tests/test_t20_s3_red_modulos.py` (18; 1 se salta sin `Invoke-ScriptAnalyzer`, que no está instalado); `ValidateSet` 01–07 → 01–08 y el orden de reversión del LEEME con el 08 en `test_t11_n11…` y `test_t18_s1…` (T20-05). Ninguna borrada.
- DECISIONES SIN CONFIRMAR: `/ADAPTADOR=` inválido o con conflicto detiene el Setup (como `/ZONA=`); en silencioso sin `/ADAPTADOR=` se reaplica el adaptador guardado si lo hay; «única con Internet» ≈ «único adaptador con ruta 0.0.0.0/0»; sin JSON de resultado se muestra «error»; botón «Actualizar la lista»; campos de contraseña sin límite de longitud (lo que pase de 6 se rechaza en vez de recortarse); con el cable desconectado el 08 acepta la IP de la configuración persistente.
- Pendiente: primera compilación del `.iss` con ISCC (en K).

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
