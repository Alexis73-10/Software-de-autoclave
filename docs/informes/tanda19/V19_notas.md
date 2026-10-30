# Tanda 19 — notas de las verificaciones V (resumen; archivo:línea sobre tanda-18 1dd3e94)

## V-01 · Interfaz del enlace
- Instancia: `BackendContext.serial` (`backend/context.py:120`, asignada en `:620`); `SetOutput.io` (`devices/io/set_io.py:35`); `ControlLoop.link` (`services/domain/loop/control_loop.py:87`); `StateMachine.io` (sin uso, `state_machine/state_machine.py:19`).
- Usos en src fuera del enlace: `control_loop.py` (`edad_ultima_di` 546/777/864/1065/1083, `secuencia_ultima_di` 734, `secuencia_ultima_ai` 578, `estado_ultima_ai` 591, `edad_ultima_ai` 556/566, `puerto_presente` 822/927, `is_connected` 713/978, `marcar_tick_control` 268, `expansor_fuera_de_linea` 973, `solicitar_handshake` 956/976/1570, `tomar_eventos` 911, `all_off` 1383/1405, `stop` 1412); `set_io.py:101,310,314` (`set_output`, `all_off`); `backend/rutas/sistema.py:209,219,451` (`get_diagnostico`, `tarjeta`, `is_connected`); `context.py:1069` (`is_connected`); `factory.py:56-59` (`on_update`, `al_conectar`, `_scan_ports`, `start`).
- `handshake_completo` y `get_state` solo los usan pruebas; entran al Protocol por MOD-02.
- `EventoTarjeta` (`serial_link.py:79-87`) no lo importa src; dos pruebas lo importan de `serial_link` (se reexporta).
- `build_hardware` solo lo usan pruebas (`tests/test_door_from_profile.py`).
- Resultado: `protocols/enlace.py` (`EnlaceES`, `MIEMBROS_ENLACE`).

## V-02 · Medidas y calibración
- Un `None` hoy lanza `TypeError` en `converters.py:163` (temperatura) o `:269` (presión) y `Units.update_from_serial` (`units.py:90`) deja las 16 lecturas congeladas en silencio.
- `ADC_MAXIMO = 4095` (`converters.py:209`) desactiva el umbral alto de falla de lazo cuando pasa de 4095 (`:261-262`): con 4000–20000 µA el umbral 21000 quedaría inactivo.
- Temperatura: crudo 0 o >= 4095 se trata como sin sonda (`converters.py:163-167`); con Modbus 0 décimas es 0,0 °C válido.
- `CALIBRATION_PATH = calibration_path()` se calcula al importar `backend/dependencias.py:48`; lo usan `rutas/io.py`, `rutas/mantenimiento.py:254`, `rutas/respaldo.py:130,250`, `server_reasignacion.py:250`.
- Esquema `config/schema.py:24-49` (`FactorySensorCalibration`): pydantic ignora claves desconocidas.
- Empaquetado: `packaging/Autoclave.spec:124-129` reemplaza `calibration.yaml` por la plantilla neutra.

## V-03 · Asignación de E/S
- `PUERTOS_*` y `_OFFSET_PRES` en `core/runtime/asignacion_io.py:52-56`; validación única por `puertos_validos()` (`:146-155`) → `validar()` (`:272`).
- Asignación guardada inválida al arrancar (`context.py:326-333`): fábrica en memoria solo para construir, alarma `CONFIGURACION_INVALIDA` (bloquea), `logger.critical`, `bloquear_por_configuracion` antes de `start()`. Un puerto fuera del rango del enlace activo sigue este camino (`puerto_inexistente`).
- Buzzer: `status.py:99` (`"buzer_alarma": 23`), `ACV-2026-001.yaml:139` (24). Pruebas que fijan DO 24 o usan DO 25 como libre: `test_r8_asignacion_io.py`, `test_e11_retiro_aire_chaqueta.py:33`, `test_r8_salidas_puertas.py`, `test_r8_arranque.py`, `test_r8_reasignacion_api.py` (unas 35 aserciones).
- `_CANALES_APAGADO_BASE = range(1, 25)` (`set_io.py:26`); pruebas `test_set_io_reset_outputs.py:23`, `test_r8_salidas_puertas.py:87`.

## V-04 · Alarmas y estado
- Traducción de eventos: `control_loop.py:904-960`; COM-03 solo con `origen == "operacion"` en CICLO (`:941-947`, `ciclo.py:1275-1299`); handshake → alarma bloqueante resuelta por `conectada`.
- `get_diagnostico()` solo lo publica `/status["comunicacion"]` (`rutas/sistema.py:206-212,454`); ninguna UI lo consume. `/status["tarjeta"]` alimenta `ui_qml/bridge/info_equipo.py:172-173`.
- `/status` es un dict sin `response_model`; un campo nuevo no rompe `test_t15_rutas_equivalentes.py` (sí un docstring nuevo en la ruta).
- `test_alarmas_catalogo.py:194-201` exigía que los ids citados en `serial_link.py` fueran `CODIGOS_TARJETA`: ahora busca en los dos enlaces (F3).
- Manuales: el filtro de AI 0x0DA2 se describe como un único registro (principal `:2352-2358`), pero la tabla trae un registro por canal en 0x0FA0 (`:3005-3017`). DECISIÓN SIN CONFIRMAR: se escribe y verifica 0x0DA2 como registro único; se confirma en M-3.
- 0x758A y 0x7586 solo están en el manual del principal; el de expansiones no trae la tabla de parámetros básicos (0x0C1F, 0x0C20, 0x0C35, 0x0C37, 0x0C80, 0x0D80, 0x7534). El decimal de 0x7587 es 4-30088 en la tabla y 4-30087 en §4.8 y en expansiones (errata; la dirección hex coincide).
- 0x0C35: el texto dice 300 (30 s) por defecto y la tabla 100 (10 s); no afecta, se escribe siempre.
- Formatos: firmware 0x0C1F/0x0D80 = byte alto mayor, byte bajo menor (v1.5 = 0x0105); modelo 0x0C20 (12 reg) y 0x0C80 (8 reg por esclavo, «NONE» ausente) como texto, sin orden de bytes documentado (se asume byte alto primero, DECISIÓN SIN CONFIRMAR, M-2); MAC 0x7534 3 registros sin orden documentado; 0x7588 32 bits sin orden de palabras documentado (se trata «distinto de 0» en cualquiera).
- Las direcciones de DO, PT100, DI, AI y bobinas coinciden en los dos manuales.
