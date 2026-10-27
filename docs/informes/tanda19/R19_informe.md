# Tanda 19 — informe R19: enlace Modbus TCP con los módulos Ebyte M31-U

Fecha: 27-oct-2026. Sesión sin supervisión (`claude -p`). Fuentes: `docs/mis_plans/decisiones_tanda_19.md`, `docs/mis_plans/planeacion_enlace_modbus.md` (MOD-01 a MOD-17) e instrucción `docs/mis_plans/instruccion_claude_code_tanda_19.md`. Estado paso a paso: `estado.md`. Verificaciones V con archivo:línea: `V19_notas.md`.

**Resultado (se completa en K/Z):** ver «Unión y entrega» al final.

## 1. Qué se hizo

| Requisito | Dónde | Resumen |
|---|---|---|
| MOD-01 | `config/enlace_io.py`, `config/enlace_io.json`, `devices/factory/factory.py` (`build_enlace`, `build_modbus`), `backend/context.py` | `{"enlace": "modbus"}`; ausente o inválido → `modbus` con advertencia (DECISIÓN SIN CONFIRMAR); se lee una vez por proceso; `context.serial` conserva el nombre y `context.enlace` es su alias; `/status.enlace_io` y `/system/info.software.enlace_io`; fila «Enlace de E/S» en Información del equipo y del sistema. |
| MOD-02 | `protocols/enlace.py` | `EnlaceES` (`Protocol`, `runtime_checkable`), `MIEMBROS_ENLACE`, `EventoTarjeta` (trasladado; `serial_link` lo reexporta), `ALARMAS_MODBUS`. Prueba de conformidad de las dos clases (miembros y firmas). |
| MOD-03 | `protocols/modbus_link.py`, `hal/measures/converters.py`, `hal/measures/units.py` | Mapa DI/DO/PT100/AI; códigos de PT100 → `None` (log una vez por episodio y canal); `None` por canal reinicia solo su filtro (antes un `None` congelaba las 16 lecturas); con Modbus 0 décimas = 0,0 °C y una cuenta fuera de −500…2500 décimas = `None`; `ai` inicial `None` y `ai_seq` 0 no se publica. Serial sin cambios. |
| MOD-04 | `config/calibration_modbus.yaml`, `config/schema.py` (`adc_piso_senal`), `utils/paths.py`, `backend/rutas/respaldo.py`, `tools/verificar_calibracion_neutra.py` | Calibración por enlace (archivo y copia en `data/` propios); fábrica identidad (temperatura) y 4000–20000 µA → 0–400 kPa con umbrales de lazo 3600/21000 activos (`ADC_MAXIMO` solo en serial) y piso 3850; un respaldo con otra fábrica se rechaza (422 `calibracion_otro_enlace`); el verificador de la entrega falla sin `calibration_modbus.yaml` o con una fábrica distinta de la nominal. |
| MOD-05 | `core/runtime/asignacion_io.py`, `server_reasignacion.py`, `core/runtime/status.py`, `config/instances/ACV-2026-001.yaml`, `devices/io/set_io.py` | Puertos según el enlace (Modbus: DI 01–16, DO 01–32, temperatura 01–06, presión 09–16); una asignación guardada fuera de rango sigue el camino existente (`puerto_inexistente` → CONFIGURACION_INVALIDA bloqueante, `context.py:324-333`); buzzer en DO 25 (los dos enlaces); `_CANALES_APAGADO_BASE = range(1, 33)`. |
| MOD-06/07 | `protocols/modbus_link.py`, `modbus_link_config.py`, `config/modbus_link.json` | Conexión verificada en 7 pasos con presupuesto y reintento; configuración de seguridad escrita (fc10), leída (fc03) y comparada exacta con reintentos; apagado 0F + lectura; MAC como ID; bandera 0x0C37 borrada y releída. |
| MOD-08 | `modbus_link.py` | Sin tick del lazo en 1,5 s y con alguna salida en ON: cero tráfico (el módulo apaga solo). Encender exige tick reciente. `all_off` y el 0F tras una conexión fallida salen siempre (llevan al estado seguro). |
| MOD-09 | `modbus_link.py` | `fallos_para_desconexion` transacciones fallidas o socket caído → pérdida, `port_open`/`data_alive` en False, reconexión verificada. |
| MOD-10 | `modbus_link.py`, `backend/rutas/sistema.py` | Diagnóstico de 1 s: 0x7587/0x7588/0x758A, 0x0C35–0x0C37 en una transacción (configuración alterada en operación → TARJETA_CONFIG_SEGURIDAD); `get_diagnostico()["modulos"]` en `/status.comunicacion`. |
| MOD-11 | `modbus_link.py` | fc05 solo en cambios; un lock único del cliente; orden + escritura atómicas; `all_off` 0F + lectura; discrepancia con reenvío único y DISCREPANCIA_SALIDAS. |
| MOD-12 | `state_machine/alarms/catalogo.py`, i18n, `docs/catalogo_alarmas.md`, `control_loop.py` | TARJETA_CONFIG_SEGURIDAD y TARJETA_MODULOS_ORDEN, misma clase que TARJETA_ALL_OFF_SIN_CONFIRMAR (bloqueantes; en ciclo COM-03). TARJETA_REINICIO no aplica a Modbus. |
| MOD-13 | `pyproject.toml`, `requirements.lock.txt`, `docs/riesgos/lista_soup.md`, `packaging/*.spec` | pymodbus 3.16.1 (sin dependencias propias; importa en Python 3.14.3), clase C, solo `ModbusTcpClient`; instalado también en `_venv_t8_producto`; `hiddenimports` en Autoclave y AutoclaveBackend. |
| MOD-14 | `tests/helpers/m31_simulado.py`, `tests/test_t19_*.py` | Simulador pymodbus en 127.0.0.1 y puerto libre (temporizador de desconexión, descarte silencioso, códigos PT100, 0 bajo 3,85 mA, fallas inyectables, restablecimiento de fábrica, contador de peticiones). |
| MOD-15/17 | `docs/mis_plans/hoja_pruebas_banco/pruebas.py`, `hoja_pruebas_banco_equipo_pruebas.md/.html` | Bloque M: M-0 (red dedicada 192.168.3.10/24, contraseña web) y M-1 a M-6. El `.md` tiene pruebas a mano que no están en `pruebas.py`: el bloque M se insertó sin regenerarlo. |
| MOD-16 | `docs/riesgos/registro_riesgos.md` | MED-01 (ALTA), MED-02 (MEDIA), MED-03 (MEDIA). |

## 2. Etapas

- **A0:** `tanda-18` no estaba unida a `dev` → `tanda-19` sale de `tanda-18` (1dd3e94), «base tanda-18». Árbol limpio. Línea base (primera suite completa de la tanda 18): 8521 recolectadas, verde (`base_suite.txt`; `test_home_view` falló solo en paralelo y pasó en serie).
- **V:** cuatro subagentes de solo lectura (`V19_notas.md`). Hallazgos que cambiaron el plan: un `None` congelaba las 16 lecturas; `ADC_MAXIMO=4095` desactivaba el umbral alto; el 0 de temperatura era centinela; `CALIBRATION_PATH` se calcula al importar; unas 35 aserciones de reasignación usaban DO 25 como puerto libre; `test_alarmas_catalogo` solo leía `serial_link.py`; el filtro de AI 0x0DA2 es ambiguo en el manual.
- **F:** F1 7563a3e, F2 754e9a4, F3 4964934.
- **P:** s1 (d8a9f33, 0b99bad), s2 (dcdb3de, 103fbf9, b8a42be), s3 (e4d061b, a723e62), en worktrees con tabla de propiedad.
- **I:** uniones s2 → s1 → s3 sin conflictos (2851c55, b3e324f, a19e1b8). Integración `test_t19_integracion_modbus.py` (4b58f14): backend completo con `enlace: modbus` contra el simulador (arranque, conexión verificada, 134,2 °C y 200 kPa, DO 13, pérdida y reconexión). `tools/claves_sin_uso_i18n.py`: solo aparecen `alarmas.TARJETA_CONFIG_SEGURIDAD/MODULOS_ORDEN.{accion,plantilla}`, que lee el backend (igual que todas las alarmas): sin huérfanas nuevas. Suite: 8765 passed, 10 skipped, 3 xfailed (8778 = 8521 + 257).
- **R:** tres revisores (`safety-reviewer`), 0 altos. Correcciones en `tanda-19-r1` (3ae9481, f8b06f0) y `tanda-19-r2` (5a44690, ab32b2a, 8e17fcb, bf932bc), unidas en 50ebae2 y 364d16b.

## 3. Hallazgos de R

| Id | Sev. | Estado |
|---|---|---|
| V19-s1-01 | media | Corregido: 0F de las 32 bobinas al fallar una conexión con socket abierto (no quedan salidas encendidas mientras los reintentos mantienen vivo el módulo). |
| V19-s1-02 / V19-s3-01 | media | **No cambiado, DECISIÓN SIN CONFIRMAR (pregunta para Cristian):** con Modbus, TARJETA_MODULOS_ORDEN y TARJETA_WATCHDOG en ciclo invalidan la conexión (MOD-08/MOD-10 lo piden) y la reconexión apaga todo; el protocolo de fallo no puede ventear mientras no hay conexión verificada (equivale a una pérdida de comunicación; NO ABRIR se mantiene). Con el serial, el WD de la tarjeta hace lo mismo; la decisión 8 se refiere a que el lazo no pida handshake en ciclo. Con el orden de módulos incorrecto, escribir bobinas podría mover la carga equivocada. |
| V19-s1-03 | media | Corregido: 0x0C35/0x0C36 verificados cada 1 s. |
| V19-s2-01 | media | Corregido: verificador de la entrega estricto. |
| V19-s3-02 | media | Aceptado y documentado (DECISIÓN SIN CONFIRMAR): `tests/conftest.py` fija el enlace serial para las pruebas anteriores; lo propio de Modbus lo cubren las `test_t19_*` y la integración. Recomendación para una tanda posterior: parametrizar con los dos enlaces las suites críticas. |
| V19-s1-04..07, V19-s2-02..04, V19-s3-04 | baja | Corregidos. |
| V19-s2-05 | baja | Anotado: el piso exige cuenta > 3850 (más estricto que la planeación; falla cerrada). |
| V19-s3-03 | baja | Anotado: `_ALARMAS_PIDEN_HANDSHAKE` con los dos ids nuevos es una segunda barrera casi siempre sin efecto (inocua). |
| V19-s3-05 | baja | Anomalía: `enlace_io.json` ausente o inválido → `modbus` solo con advertencia; la elección vive en la carpeta del programa (una actualización con el Setup puede devolverla a `modbus`). |
| V19-s3-06 | baja | Sin cambio: la prueba original ya usaba `in` (no se relajó); solo se espera el evento. |
| V19-s3-07 | baja | Anomalía: los `motivo` de los eventos Modbus están solo en español (mismo patrón que el serial). |

## 4. Pruebas

Nuevas (con `req`): `test_t19_f2_enlace.py`, `test_t19_s1_config.py`, `test_t19_s1_enlace.py`, `test_t19_s2_conversion.py`, `test_t19_s2_calibracion.py`, `test_t19_s2_puertos.py`, `test_t19_s3_alarmas_modbus.py`, `test_t19_s3_exposicion_enlace.py`, `test_t19_integracion_modbus.py`, `test_t19_r1_enlace.py`, `test_t19_r2_conversion.py`, `test_t19_r2_respaldo.py`, `test_t19_r2_verificador.py`.

Pruebas existentes tocadas (solo las excepciones autorizadas o fortalecidas; cada una con comentario):
- `build_serial` → `build_enlace` (decisión de la tanda): `test_arranque_sin_tarjeta.py` (fixture `backend`), `test_r8_arranque.py::test_construir_control_bloquea_antes_de_start_si_el_archivo_esta_danado`, `test_secuencia_arranque.py::test_el_constructor_no_hace_e_s` y `::test_construir_control_registra_el_aviso_antes_de_start`, `test_endpoint_arranque.py::test_importar_server_no_construye_hardware`.
- Buzzer en DO 25, `_CANALES_APAGADO_BASE` y puertos (decisión 4 de Cristian, MOD-05): `test_set_io_reset_outputs.py`, `test_e11_retiro_aire_chaqueta.py`, `test_r8_asignacion_io.py` (3), `test_r8_salidas_puertas.py` (3; además fortalecida `test_apagado_individual_cubre_los_canales_reasignados` con una base reducida), `test_r8_arranque.py` (7), `test_r8_reasignacion_api.py` (20: DO 25 → DO 27/26 conservando `ocupado_por == "vapor_camara"`), `test_p1_rutas_build_congelado.py` (el subproceso fija el enlace serial; aserciones intactas).
- `test_alarmas_catalogo.py::test_ids_de_la_tarjeta_que_emite_el_enlace_estan_en_el_catalogo`: los ids se buscan en los dos enlaces; sigue exigiendo igualdad con `CODIGOS_TARJETA`.
- `test_f1_registro_pruebas.py`: el conjunto exacto de bloques incluye M (MOD-15).
- `test_b2_spec_excludes.py`: `pymodbus` imprescindible (más estricta).
- `test_e6_enlace_handshake.py::test_uptime_que_retrocede_es_reinicio`: carrera anterior a la tanda (la bandera baja antes de encolar el evento); se espera el evento, que sigue siendo obligatorio.
- `test_t8_k8_calibracion_neutra.py` y `test_t9_e9_entrega_neutra.py`: el compilado falso incluye `calibration_modbus.yaml` (el real lo trae).
- `tests/conftest.py`: enlace serial fijado para las pruebas anteriores y fixture `enlace_modbus`.
- Pruebas de esta misma tanda ajustadas en R: `test_t19_s1_config.py::test_valores_validos_se_aceptan` (timeout 0,45), `test_t19_s1_enlace.py::test_modulos_orden_en_operacion_invalida` (origen "operacion"), `test_t19_s2_conversion.py` (4095 décimas → None), `test_t19_s2_calibracion.py` (verificador falla sin el archivo).

Las pruebas del enlace serial (`test_e6_enlace_handshake.py`, `test_serial_link_v2_lector.py`, `test_u4_*`, `test_s1_sen01_convertidor.py`, converters/units) pasan sin cambios de aserción.

## 5. DECISIONES SIN CONFIRMAR

1. Enlace por defecto `modbus` si `enlace_io.json` falta o es inválido (MOD-01).
2. Sondeo 100 ms y tiempo de desconexión del módulo 1,0 s (decisión 3; hasta M-1).
3. Filtro de PT100 en 1; filtro de AI 0x0DA2 como registro único (el manual se contradice: tabla por canal en 0x0FA0) (MOD-07; M-3).
4. Texto del modelo con el byte alto primero; MAC y 0x7588 con la palabra alta primero; firmware 0x0000 = ilegible (falla cerrada); se lee un esclavo más de los esperados y debe ser «NONE» (M-2).
5. `discrepancia_dispara_fallo` true con Modbus (MOD-11).
6. Piso de señal 3850 con cuenta estrictamente mayor (MOD-04).
7. `None` de presión no cuenta en el debounce de lazo.
8. Rango plausible de PT100 −500…2500 décimas; fuera → `None`.
9. Encender una salida exige tick reciente del lazo; `all_off` y el 0F tras una conexión fallida salen siempre.
10. La bandera 0x0C37 se borra al conectar (y se relee); TARJETA_WATCHDOG una vez por suspensión.
11. El socket caído cuenta como pérdida inmediata; una máscara 0x7588 ≠ 0 al conectar falla con EXPANSOR_FUERA_DE_LINEA.
12. Orden de escritura: DO (falla, encendido, modo) → 0x0C35 → habilitar 0x0C36.
13. TARJETA_MODULOS_ORDEN y TARJETA_CONFIG_SEGURIDAD en operación fuera de ciclo también hacen pedir conexión al lazo.
14. Validación cruzada de tiempos (periodo < mitad del tiempo de desconexión; `timeout_s` < 0,5 s).
15. Un respaldo con otra calibración de fábrica se rechaza (también en serial).
16. Las pruebas anteriores a la tanda corren con el enlace serial (conftest).
17. Invalidación en ciclo por TARJETA_MODULOS_ORDEN/WATCHDOG con Modbus (V19-s1-02, pregunta para Cristian).
18. Fila del enlace en Información del equipo: «—» antes de la primera consulta.

## 6. Pruebas de banco pendientes (bloque M)

M-0 red dedicada; M-1 corte por desconexión (< 2 s; ¿0x0C37 se borra escribiéndolo?); M-2 composición/orden (formato del modelo y «NONE»); M-3 canal por canal, direcciones de expansiones y 0x0DA2, buzzer en DO 25 (24 VDC); M-4 exactitud PT100 (121/134 °C) y presión (100/200/300 kPa), ruido cerca de 3,85 mA, ¿satura la AI en 21 mA?; M-5 Reload largo (¿corta el TCP?); M-6 cambio de enlace. Equipos serial ya instalados: recablear el buzzer a DO 25 al actualizar.

## 7. Unión y entrega

(se completa en K/Z)
