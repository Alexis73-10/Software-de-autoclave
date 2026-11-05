# Inventario de rastros del ESP32 / enlace serial (tanda 27)

Solo análisis; nada editado fuera de este archivo. Búsquedas con `rg -i` sobre `src/`, `tests/`, `tools/`, `packaging/`, `docs/` (sin `docs/informes/tanda*/`; `docs/mis_plans` solo contado), `CLAUDE.md`, `pyproject.toml`, `requirements*`.
Clases: A comentario/doc a reescribir sin nombrar el ESP32; B código muerto; C dato persistido o texto de historial que se conserva; D doc vigente a editar; E doc a mover a `docs/referencia/obsoleto/` con cabecera; F riesgo/trazabilidad a marcar «Obsoleto (tanda 20, retirado en la 27)»; G falso positivo.

Hechos de partida: no existe `Hardware/`; no hay `.ino`, `serial_link*`, `device_reset` ni `enlace_io.json` en `src/`; `pyserial` ya no está en `pyproject.toml` ni en el lock (solo un comentario). `src/logs/autoclave.log` (332 coincidencias) está ignorado por git: no cuenta. `pyproject.toml`: 0 hallazgos.

## 1. src/ (todo A salvo lo indicado)

| Archivo:línea | Texto | Clase / regla |
|---|---|---|
| protocols/enlace.py:3-4 | «retiro del enlace serial con la ESP32» | A: «interfaz con una sola implementación (ModbusLink)» |
| protocols/enlace.py:34-39 | «heredadas del enlace serial (trasladadas desde serial_link.py…)» | A: alarmas del plan de protocolo; quitar historia de traslado |
| protocols/enlace.py:54-59 `ALARMAS_SOLO_SERIAL` | tupla de 3 TARJETA_* | B/C: sin uso en `src` (solo la lee `test_t20_s2_retiro_serial.py:196-201`). Se conserva por el historial (C); renombrar a `ALARMAS_RETIRADAS` o `ALARMAS_SOLO_HISTORIAL` y adaptar la prueba. Los códigos no se tocan |
| state_machine/states/ciclo.py:70 | «watchdog del firmware de la ESP32 (5 s menos 1 s…)» | A: explica la regla de la tolerancia de DI vencida (4 s). Reescribir con el corte del módulo (MOD-08, 1,0 s) y la tolerancia 4 s; ver `registro_riesgos` HAZ-T2-03 |
| state_machine/cycle_phases/prevacio.py:48 | «observado con la ESP32 del enlace serial…» | A: regla de la observación de vacío/presión; dejar «observado en equipo de pruebas» |
| hal/measures/converters.py:140, 263 | «ADC del módulo E/S serial retirado», «ADC de 12 bits del módulo E/S serial» | A: regla del centinela/saturación; con Modbus: el piso de señal `adc_piso_senal` 3850 µA |
| utils/paths.py:30-31 | «la calibración serial (`calibration.yaml`, cuentas del ADC) se retiró» | A: dejar «única calibración: `calibration_modbus.yaml`» |
| core/managers/catalogo_parametros.py:618 | «calibración serial (calibration.yaml…)» | A |
| backend/rutas/respaldo.py:64, 222, 229 | respaldos de equipos serial; `Path(tmp)/"calibration.yaml"` | A en 64/229. **222 es literal vivo**: nombre de archivo temporal para validar; revisar (no es código del serial en sí, pero conserva el nombre). Rechazo `calibracion_otro_enlace` = **vigente** (C, no tocar) |
| backend/rutas/sistema.py:576 | «B-ES-1: cuentas ADC crudas» | A (ya visto) |
| backend/context.py:691, 1173 | `context.serial` «histórico» | A: nombre conservado por decisión (CLAUDE.md); solo el texto |
| devices/factory/factory.py:69 | «retiró el serial y la selección por…» | A |
| devices/puertas/advanced_door.py:2 | «No habla directamente con el serial» | A |
| exe_unico.py:99 | «sin abrir el puerto serial» | A (o G si se refiere al rol) |
| hal/measures/units.py:213 | «cuenta ADC CRUDA… última trama» | G: trama AI vigente (Modbus) |
| core/runtime/aire_atmosferico_prueba.py:22-23 | «tramas», «cuenta ADC cruda» | G |
| services/domain/loop/control_loop.py:870 | «CRC malo, firmware incompatible o DI vencida» | A: «CRC malo» ya no existe; reescribir |
| config/schema.py:25-55, config/calibration_modbus.yaml (`adc_min/adc_max/adc_piso_senal`, ~80 líneas) | nombres de campo ADC | C/G: **claves persistidas** en calibraciones y respaldos; no se renombran |
| state_machine/alarms/catalogo.py:131 `CODIGOS_TARJETA`, i18n `TARJETA_SIN_TRAMA_VALIDA` (es.json/en.json:970) | códigos guardados | C |
| backend/context.py:546-606, server_reasignacion.py:160, i18n verif_trama_presente | `trama_presente` | G (Modbus vigente) |
| protocols/modbus_link*.py, rutas/respaldo.py, rutas/sistema.py | comentarios ya vistos | A (ya listados por el director) |
| i18n es/en: `serial_especifika`, `error_serial_v2`, `rotulo_serial_especifika`; activation*.py, identidad.py, `serial_number` | serie Especifika | G (vigente) |
| i18n `enlace_io`, `enlace_io_modbus`, `rotulo_enlace_io` | rótulo «Enlace de E/S» | G (la fila vigente de Información del equipo) |
| `TARJETA_*` en otros .py/.ts | códigos guardados | C |
| ui_qml/controllers/*, ui_pyside `tarjeta` | recuadro de interfaz | G |

Código muerto real en `src/` por el ESP32: **ninguno** aparte de `ALARMAS_SOLO_SERIAL` (solo lo usa una prueba). `ALARMAS_HANDSHAKE` incluye `TARJETA_SIN_ACK`/`TARJETA_ALL_OFF_SIN_CONFIRMAR` que ya no se emiten (el CLAUDE.md lo acepta: catálogo conservado); marcarlo en el comentario, no borrar.

## 2. tools/ y packaging/

| Archivo:línea | Texto | Clase |
|---|---|---|
| packaging/AutoclaveBackend.spec:70 | `excludes=['serial']  # …pyserial retirado; pymodbus lo importa como opcional` | A el comentario («módulo opcional de pymodbus no usado»); el `'serial'` es **vigente** (lo exige `tests/test_b2_spec_excludes.py`) |
| packaging/Autoclave.spec:125-128, 136 | comentario pyserial; `'serial'`; «serial y su plantilla se retiraron» | A (idem) |
| tools/entrega/info_compilacion.py:24 | «(Hardware/, con el firmware de la ESP32, se retiró…)» | A |
| tools/verificar_calibracion_neutra.py:14-24, 117-120 | `NOMBRE_SERIAL_RETIRADA = "calibration.yaml"`, falla si se cuela | A en docstring; **la comprobación es vigente** (CLAUDE.md) |
| tools/verificar_entrega_neutra.py:13 | «no viaja la serial retirada» | A |
| tools/ensayo_actualizacion_b_d.py:124-128 | copia `calibration.yaml` de plantilla inexistente | A/B: bloque del ensayo que ya cita la plantilla serial «que ya no existe»; revisar si es rama muerta |
| tools/ensayo_actualizacion_f_g.py:66, b_d.py:167 | `g["serial"]` | G (`serial` del perfil) |
| tools/registro_pruebas/almacen.py:32-34 | `id_tarjeta`, `firmware` | C (clave guardada, comentario ya lo dice) |
| tools/instalador/autoclave.iss:389, 560, 762 | «tarjeta» = lector de tarjetas / texto; `firmware` = módulo | G |
| tools/generador/db.py:32,53 | `serial` | G |
| tools/instalador y tools/estacion con `esp32`/`serial_link` | ninguno | – |

## 3. tests/ (esp32|pyserial|serial_link|.ino)

| Archivo:línea | Clase |
|---|---|
| test_t20_s2_retiro_serial.py (24 coincidencias: módulos, rutas y `Comunicacion_esclava_ESP32_V2/V3`, pyserial, crc16, device_reset, ALARMAS_SOLO_SERIAL) | **Excepción total**: es la prueba del retiro; lleva los nombres a propósito |
| test_b2_spec_excludes.py:16 | A (comentario «pyserial») |
| test_alarmas_catalogo.py:203 | A (serial_link.py) |
| test_control_loop_resilience.py:27 | A (SerialTimeoutException de pyserial) |
| test_b9_buzzer_paro.py:9 | A (firmware V3 de la ESP32) |
| test_t19_f2_enlace.py:3-5, 28 | A (enlace_io.json) |
| test_t19_s1_config.py:2 | A (serial_link_config) |
| test_t19_s1_enlace.py:82 | A (serial_link.py) |
| test_t19_s2_conversion.py:56 | A (ADC… serial (ESP32)) |
| test_t2_p3_di_vencida.py:5 | A (ESP32; regla: tolerancia 4 s de DI vencida) |
| test_ver_entrega.py:59 | A (Hardware/ firmware de la ESP32) |
| test_o2d_info_sistema.py:15, 30, 48, 90; test_e2_nombres_familia.py:244 | A: son datos de ejemplo `ESP32-A1B2C3`/`ESP32-X` en `id_modulo_es`; cambiar a `MOD-A1B2C3`/`MOD-X` (no es dato persistido) |
| tests/helpers, tests/banco | 0 |

## 4. Documentación

| Archivo | Hallazgos | Clase |
|---|---|---|
| CLAUDE.md:38 (frase del retiro: «enlace serial de la ESP32 (`serial_link.py`, … `device_reset`, … `enlace_io.json`, pyserial y el firmware `Hardware/`) … copia en `G:\Respaldos…`, etiqueta `respaldo-serial-pre-t20`») | 1 | D: reducir a «el enlace serial se retiró en la tanda 20; ver `docs/informes/tanda20/`». La copia y la etiqueta se citan en tanda20 |
| CLAUDE.md:42 («Ya no se instala `enlace_io.json`»), :43 («falla si la compilación trae `calibration.yaml`») | 2 | D: la 43 es regla vigente de la verificación; reescribir sin `calibration.yaml` genérico («el archivo de calibración del enlace retirado») o dejar solo como nombre de archivo de la prueba; la 42 se quita |
| docs/README.md:18 | 1 | D (cita `plan_modificaciones_adc_ino.md`; actualizar al mover) |
| docs/plan_modificaciones_adc_ino.md (3) | 1 doc | E (obsoleto: ya visto) |
| docs/mis_plans/planeacion_protocolo_serial_esp32.md (12), planeacion_firmware_1_5.md (14), instruccion_claude_code_e6_firmware.md (4) y planes de firmware similares | tandas cerradas | E si se consideran vigentes por ubicación; si no, cabecera «Obsoleto». Inventario completo: 35 archivos en `mis_plans` (solo contados) |
| docs/superpowers/ (11 archivos; el mayor `plans/2026-07-16-reconexion-tarjeta-arranque-plan.md` 60 y `specs/2026-07-16-…design.md` 18) | 11 | E: planes/specs del serial; mover los dos de reconexión de tarjeta, el resto son menciones laterales (impresora, puertas, voz) = G/A de poco valor |
| docs/informes/ (no tanda) 47 archivos: `lotes_auditoria/lote_2` 22, `informe_verificaciones_fin_de_ciclo` 16, `informe_e6_firmware` 13, `lote_3` 10, `informe_tanda_2026-10-27_t20/t19`, `inventario_sensores_y_base_de_datos`, `secuencia_arranque`, etc. | 47 | E/históricos: informes de sesiones cerradas; cabecera de obsoleto (contarlos como históricos). `informe_e6_firmware.md` mover |
| docs/catalogo_alarmas.md:36, 68-80, 97 (7) | 7 | D: texto vigente que explica los TARJETA_*; reescribir 36 sin «hasta la tanda 19, el serial con la ESP32» y dejar los TARJETA_* retirados como «historial»; 68-80 es la nota de retiro (C: conservar, sin nombrar el ESP32 salvo la ruta histórica) |
| docs/riesgos/registro_riesgos.md:77, 167-169, 175, 177, 193 (7) | 7 | F: HAZ-TAR-01 (77 y 177), HAZ-T2-03 (175), nota de retiro 167-169 y AN-31 (193) → marcar «Obsoleto (tanda 20, retirado en la 27)» donde corresponda |
| docs/riesgos/matriz_trazabilidad.md:16 (REQ-10, cita planeacion_protocolo_serial_esp32) | 1 | F |
| docs/riesgos/lista_soup.md:18, 68 (3) | 3 | C/F: pyserial y firmware ESP32 ya figuran como retirados; es el registro SOUP, conservar |
| docs/versiones/HISTORIAL_VERSIONES.md (7), anomalias_conocidas_1.0.0-alpha.3/.4.md (7) | 14 | C: historial; no se tocan |
| docs/instalacion/LEEME_INSTALACION.md:470 (`serial_link.json`), :507 (`data\calibration.yaml`) | 2 | E: LEEME de la compilación I (2026-10-24); mover a obsoleto con cabecera (ya no instrucciones vigentes) |
| docs/mis_plans/inventario_cadenas_i18n.{md,csv} (46) | 46 | E/histórico (inventario de la tanda de i18n) |
| docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.{md,html}, hoja_pruebas_banco/pruebas.py:53 | 3 | A/G: «La ESP32 (enlace serial) ya no es compatible» es nota de precondición vigente; reescribir «Solo Modbus TCP» (el .md/.html se generan desde pruebas.py) |
| docs/arquitectura, referencia, diseno, handoff, mockups | 0 | – |
| requirements.lock.txt:5 | 1 | A: dejar «sin dependencia de puerto serial» sin nombrar pyserial (o excepción) |
| requirements*, pyproject.toml | 0 | – |

## 5. Conteo por clase (aprox., por línea/hallazgo)

- A: ≈55 (src 14, tools/packaging 9, tests 14, docs/lock 6, textos de test/datos ESP32-A1B2C3 ≈6, CLAUDE.md 3, doc de pruebas 3).
- B: 1 (`ALARMAS_SOLO_SERIAL`, sin uso en src) y a revisar 1 (bloque calibration.yaml en `ensayo_actualizacion_b_d.py:124-128`).
- C: ≈24 de rastros a conservar (códigos TARJETA_*, `adc_*` persistidos, `id_tarjeta`, historial, SOUP, rechazo `calibracion_otro_enlace`).
- D: 6 (CLAUDE.md 3, docs/README.md, catalogo_alarmas.md 36, pruebas banco 53).
- E: unos 100 archivos (35 mis_plans solo contados + 47 informes no tanda + 11 superpowers + plan ADC + LEEME).
- F: ≈10 filas (registro de riesgos y matriz).
- G: ≈20 (serial_number/serial Especifika, trama AI, `adc_*`, lector de tarjetas).

## 6. Excepciones para `tests/test_t27_sin_esp32.py`

Patrón: `rg -i "esp32|pyserial|serial_link|\.ino\b"` sobre `src`, `tests`, `tools`, `packaging`, `CLAUDE.md`, `pyproject.toml`, `requirements*` y `docs` vigentes. Tolerar exactamente (después de reescribir los A):

1. `tests/test_t20_s2_retiro_serial.py` (completo).
2. `tests/test_t27_sin_esp32.py` (la propia prueba).
3. `docs/informes/` completo, `docs/mis_plans/`, `docs/superpowers/` y `docs/referencia/obsoleto/` (históricos y obsoletos, con cabecera).
4. `docs/versiones/HISTORIAL_VERSIONES.md` y `docs/versiones/anomalias_conocidas_*.md`.
5. `docs/riesgos/registro_riesgos.md`, `docs/riesgos/matriz_trazabilidad.md`, `docs/riesgos/lista_soup.md` (entradas marcadas obsoletas / SOUP retirado).
6. `docs/catalogo_alarmas.md` solo la nota de retiro (líneas con `serial_link.py`/ESP32 en la sección de la tanda 20; si se reescriben sin nombrarlo, sin excepción).
7. `src/logs/` (no versionado, ignorado).

Sin excepción: CLAUDE.md, pyproject.toml, requirements*, packaging/, tools/, el resto de `src/` y `tests/` (los comentarios se reescriben; `'serial'` en `excludes` no coincide con el patrón). Si se quiere conservar un nombre en un comentario de `ensayo_actualizacion_b_d.py` o `requirements.lock.txt`, añadirlo explícito; la propuesta es reescribir y no dejar excepciones.
