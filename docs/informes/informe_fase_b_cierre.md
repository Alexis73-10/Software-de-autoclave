# Informe — Cierre de la fase B: ARR-01, separación de cambios, seguridad de la etapa 7

Fecha: 12-oct-2026 · Sin commit. Continúa `informe_fase_b_arranque_backend.md`.

## 1. Renombrado ARR-01 (`Arranque.qml` → `Reposo.qml`)

`Reposo.qml` ya existía como archivo sin versionar y es el antiguo `Arranque.qml`. La única diferencia es que usa `Colores.textoFechaReposo` en vez del hex, cambio de la tarea de la intro. Cambios hechos:

- `qml/Main.qml:308`: la instancia `Arranque {` pasa a `Reposo {`. Era la única instancia del tipo.
- Comentarios que nombraban el tipo: `Main.qml:75`, `Componentes/FondoApp.qml:4` y la cabecera de `Pantallas/Reposo.qml`.
- Pruebas: en `test_intro_arranque_qml`, `test_main_menu_principal_qml`, `test_navegacion_ciclo_en_curso`, `test_navegacion_sesion_qml`, `test_opciones_qml`, `test_reconocer_falla` y `test_ui_qml_app`, `"Arranque"` / `"Arranque_QML"` pasan a `"Reposo"` / `"Reposo_QML"`. Las etiquetas internas de las pruebas (p. ej. `"arranque"` en `visibles()`) no cambian.

Sin cambios de comportamiento ni de estilo: solo cambia el nombre del tipo.

Suite completa (excluye `test_adenda_estados.py`, que no se puede recolectar):

| | Pasan | Fallan | Errores |
|---|---|---|---|
| Antes | 2551 | 19 | 14 |
| Después | 2584 | 0 | 0 |

Los 33 fallos de antes eran todos del renombrado a medias: con este cambio desaparecen y no aparece ningún fallo nuevo. La corrida de "después" empezó antes de crear `test_arranque_sin_tarjeta.py` (paso 3). Esas 2 pruebas y la prueba de host reformateada (paso 4) las corrí aparte y pasan. `tests/test_adenda_estados.py`, que antes no se podía recolectar por `TEMPERATURE_PROBE_KEYS`, ahora sí se recolecta y pasa (70 pruebas): `installation/profile.py`, cambio E0/E1 ajeno, se actualizó durante la sesión. En total: **2656 pasan, 0 fallan**.

## 2. Separación de cambios

### (a) Cambiados por la fase B (y por la intro de arranque, también de esta sesión)

**Fase B: arranque del backend por etapas**
- `src/autoclave/backend/arranque/` (nuevo): registro de etapas, secuencia y `BdNoDisponible`.
- `src/autoclave/backend/context.py`: **mixto**. La fase B rehízo el constructor por etapas. Antes de la fase B ya tenía sin commit `avisar_entradas_no_monitoreadas`, `SetOutput(..., profile=)` y `ControlLoop(..., profile=)`, que son de E0/E1 y se conservaron.
- `src/autoclave/backend/server.py`: **mixto**. Fase B: registro, compuerta 503, `/arranque`, 503 sin BD, `/cycle/start` sin BD, apagado tolerante y aviso de paro fuera del import. Ya estaba sin commit (E0/E1): `entradas_no_monitoreadas`/`sondas_no_vigiladas` en `/status`, quitar `drenaje_camara` y `_rechazar_si_sin_datos_vigentes` en modo prueba.
- `src/autoclave/backend/main.py`: `uvicorn.Server` y el arranque disparado con el puerto enlazado.
- `src/autoclave/devices/factory/factory.py`: `build_hardware` dividido en `build_serial` y `build_doors_cfg`.
- `src/autoclave/core/managers/cycle_manager.py`: lista `errores_carga`.
- `docs/catalogo_alarmas.md`: **mixto**. Fase B: `OPERANDO_SIN_BD`, `CONFIGURACION_INVALIDA` actualizada y §2.1 de códigos de arranque. El resto del diff (secciones renumeradas, §8, §9 Parte A) ya estaba.
- `docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md`: **mixto**. Fase B: `ARR_PERFIL`/`ARR_RELOJ` en §5 (paso 5 de esta tarea). Lo demás (excepción D-E en §4.7 y D-02 confirmada) es tuyo.
- `tests/test_backend_autenticacion.py`: 3 pruebas ajustadas (ver §4).
- `tests/test_registro_arranque.py`, `test_secuencia_arranque.py`, `test_endpoint_arranque.py`, `test_arranque_sin_tarjeta.py` (nuevos).
- `docs/informes/propuesta_fase_b_arranque_backend.md`, `informe_fase_b_arranque_backend.md` y este informe (nuevos).

**ARR-01 (paso 1 de esta tarea)**
- `src/autoclave/ui_qml/qml/Main.qml` (también tiene la intro, ver abajo), `Componentes/FondoApp.qml`, `Pantallas/Reposo.qml` (nuevo), `Pantallas/Arranque.qml` (borrado, no por mí) y las 7 pruebas listadas en §1.

**Intro de arranque (tarea anterior de esta sesión, `planeacion_animacion_arranque.md`)**
- `src/autoclave/ui_qml/qml/Pantallas/IntroArranque.qml`, `bridge/progreso_arranque.py`, `assets/fondos/halo_arranque.png`, `voluta_vapor.png` y `tools/generar_assets_arranque.py` (nuevos).
- `src/autoclave/ui_qml/qml/Main.qml`: `Loader` de la intro y capa provisional `alarmaArranque`.
- `src/autoclave/ui_qml/app.py`: inyección de `progresoArranque` y `versionSoftware`.
- `src/autoclave/ui_qml/assets/textos/es.json`: sección `arranque`.
- `src/autoclave/ui_qml/qml/Tema/Colores.qml`: token `textoFechaReposo`.
- `tests/test_intro_arranque_qml.py`, `test_progreso_arranque.py` y `docs/informes/informe_animacion_arranque.md` (nuevos).

### (b) Modificados que NO son de la fase B

| Archivo | A qué parece pertenecer (según `git diff`) |
|---|---|
| `docs/mis_plans/planeacion_protocolo_serial_esp32.md` | D-02 actualizada: el splash se libera a los 15 s (tu edición del plan, D-E). |
| `src/autoclave/config/calibration.yaml` | Adenda E0/E1: `temp_drenaje_cam` eliminado, `temp_drenaje` pasa a la entrada 4. |
| `src/autoclave/core/runtime/status.py` | Adenda E0/E1: mismo reacomodo de `temp_drenaje` (posición 4, la 5 queda sin sensor). |
| `src/autoclave/devices/buzer/buzer.py` | Timers con `time.monotonic()` en vez de `time.time()` (regla de CLAUDE.md, TMG). |
| `src/autoclave/devices/io/set_io.py` | Adenda A-7: `apagar_por_paro()`, ALL_OFF limitado durante el paro; recibe `profile`. |
| `src/autoclave/devices/paro_emergencia/paro_emergencia.py` | D-16 / E1-5: paro con contacto NC y texto `AVISO_CABLEADO_NC`. |
| `src/autoclave/devices/puertas/door_factory.py` | E1-4: `tipo_tiene_actuador()`. |
| `src/autoclave/devices/puertas/simple_door.py` | E1-3: lectura inválida = puerta abierta (HAZ-FC-02). |
| `src/autoclave/devices/pump/pump.py` | Adenda A-1: `agua_bomba` según el perfil (`entrada_requerida`). |
| `src/autoclave/installation/profile.py` | E1-1 / A-2: `supply_inputs` y `temperature_probes` en el perfil (incluye `TEMPERATURE_PROBE_KEYS`). |
| `src/autoclave/installation/storage.py` | E1-1 / A-2: normaliza `supply_inputs` y `temperature_probes` al leer y escribir. |
| `src/autoclave/installation/wizard.py` | E1-1: paso del asistente para declarar entradas de suministro y sondas. |
| `src/autoclave/protocols/serial_link.py` | Adenda A-3 (E6): vigencia de la trama DI (`_ultima_di_mono`, DI a 0 al reconectar). |
| `src/autoclave/services/domain/loop/control_loop.py` | A-3 / TMG-01: DI vencida = paro; perfil de instalación (E1). |
| `src/autoclave/simulador/servidor.py` | E0/E1: quita `drenaje_camara`, agrega `entradas_no_monitoreadas`/`sondas_no_vigiladas` a `/status`. |
| `src/autoclave/state_machine/state_machine.py` | E1: pasa `profile` a PREPARACION, PREPARADO y CICLO. |
| `src/autoclave/state_machine/states/ciclo.py` | E1-2 / A-9: puertas según el perfil y lecturas inválidas. |
| `src/autoclave/state_machine/states/falla.py` | A-7 y D-16: `apagar_por_paro()` y texto NC. |
| `src/autoclave/state_machine/states/hibernacion.py` | A-7 y D-16: igual que `falla.py`. |
| `src/autoclave/state_machine/states/preparacion.py` | E1 / E1-5 / A-7: perfil, flag `PARO_EMERGENCIA` en vez del DI crudo, ALL_OFF limitado. |
| `src/autoclave/state_machine/states/preparado.py` | E1 / A-2 / A-7: perfil, supervisor por sensor analógico, ALL_OFF limitado. |
| `src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py` | E0/E1: quita `temp_drenaje_cam`. |
| `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py` | E1-4 / D-11: oculta la apertura automática con puerta sin actuador. |
| `tests/test_ciclo_drenaje.py` | Adenda A-4 (SAF-02): sin lectura de drenaje se enfría siempre. |
| `tests/test_control_loop_f0.py` | D-16: el paro se publica al construir `EmergencyStop`. |
| `tests/test_control_loop_set_active_cycle.py` | E1: `profile=` en la máquina de estados. |
| `tests/test_control_loop_test_mode.py` | D-16 / A-3: paro NC y vigencia de DI. |
| `tests/test_preparacion_ejecutor_paralelo.py` | E1-5 / A-7. |
| `tests/test_preparado_suministro.py` | E0/E1: quita `temp_drenaje_cam`. |
| `tests/test_puertas_fallas_endpoints.py` | E0/E1: `temp_drenaje` en la posición 4. |
| `tests/test_sin_temp_chaqueta.py` | E0/E1: quita `temp_drenaje_cam`. |

También hay archivos sin versionar que no son de esta sesión: los `test_adenda_*`, `test_e0_*` y `test_e1_*`, `core/runtime/lectura.py`, `installation/cambio_perfil.py`, `tools/declarar_*`, planes e informes de E0/E1, firmware y alarmas Parte A. No los revertí, no los mezclé ni hice stash de nada.

## 3. Seguridad de la etapa 7 sin tarjeta

Prueba nueva `tests/test_arranque_sin_tarjeta.py`, de integración real. Usa `BackendContext`, la secuencia de arranque, `ControlLoop`, la máquina de estados, puertas avanzadas y la configuración y los ciclos del repo. Solo se sustituyen el perfil, la BD (SQLite temporal), la impresora y el `SerialLink`: este último es una subclase real sin puerto que registra cada `set_output` y `all_off`.

1. **Sin tarjeta.** La etapa 7 queda `en_curso` con `ARR_SIN_ES` y sin fallo bloqueante. La etapa 8 sigue `pendiente`. El contexto es operable y `/status` responde con `card_connected: false`. `POST /cycle/start` responde **409**, `START_CICLO` y `LISTO_PARA_CICLO` siguen apagados y el estado no es CICLO. Están activos `NO_HAY_CONEXION` y `PARO_EMERGENCIA`. **No se envió ninguna salida encendida.**
2. **La tarjeta conecta.** La etapa 7 pasa a `ok` (código limpio), la 8 a `ok` y `terminado=true`. Siguen el mismo `ControlLoop`, su mismo hilo y el mismo enlace. El hilo de arranque terminó y no se relanzó nada.

Resultado: **2 pasan. El comportamiento actual cumple y no hay hallazgo.** El motivo, verificado en el código: sin enlace, `ControlLoop._tick()` sale antes de correr la máquina de estados (no hay `LISTO_PARA_CICLO`). Además, `link_was_connected` empieza en `True`, así que `NO_HAY_CONEXION` se reporta desde el primer tick del arranque.

## 4. Las 3 pruebas ajustadas en `test_backend_autenticacion.py`

```diff
 def test_backend_escucha_solo_en_localhost():
     from autoclave.backend import main
     assert main.HOST == "127.0.0.1"
-    with patch.object(main.uvicorn, "run") as run:
+    with patch.object(main.uvicorn, "Server") as servidor, \
+            patch.object(main.threading, "Thread"):
         main.main()
-    assert run.call_args.kwargs["host"] == "127.0.0.1"
+    assert servidor.call_args.args[0].host == "127.0.0.1"
@@
 def test_cancelacion_por_paro_olvida_al_dueno_y_queda_en_la_bitacora(entorno):
     client, ctx, srv = entorno
-    aviso = ctx.control_loop.al_cancelar_modo_prueba.call_args.args[0]
+    aviso = srv._prueba_cancelada_por_paro   # lo registra el arranque (construir_control)
@@
 def test_aviso_de_paro_tardio_no_toca_un_modo_prueba_nuevo(entorno):
     client, ctx, srv = entorno
-    aviso = ctx.control_loop.al_cancelar_modo_prueba.call_args.args[0]
+    aviso = srv._prueba_cancelada_por_paro   # lo registra el arranque (construir_control)
```

Confirmo que los cambios se deben solo a la forma de arrancar el backend y no debilitan ninguna comprobación de autenticación:

- **Host fijo.** Se sigue verificando que el servidor escucha en `127.0.0.1`. Ahora se lee de `uvicorn.Config`, primer argumento de `uvicorn.Server`, porque `main.py` ya no usa `uvicorn.run`. El `Thread` se parchea solo para que la prueba no lance el hilo de espera del puerto.
- **Aviso de paro (2 pruebas).** Antes la función se obtenía del registro que hacía `server.py` al importar. Ahora ese registro lo hace `construir_control()`, que en estas pruebas no corre porque el contexto es un `MagicMock`, y la función se toma directamente del módulo. Es la misma función que se registra en producción: `iniciar_arranque` pasa `al_cancelar_prueba=_prueba_cancelada_por_paro`, lo que comprueba `test_endpoint_arranque.py::test_iniciar_arranque_lanza_un_solo_hilo`. Que se registre antes de `start()` lo comprueban `test_secuencia_arranque.py::test_construir_control_registra_el_aviso_antes_de_start` y la prueba de integración del §3.
- Todas las aserciones del cuerpo siguen iguales: dueño olvidado, bitácora `modo_prueba_sale` con usuario y motivo, reingreso permitido y aviso tardío sin efecto.

Corrección de forma: en la versión anterior, la primera prueba había quedado con la continuación `\` convertida en espacios (era Python válido, pero en una línea larga). Ya está en dos líneas.

## 5. `ARR_RELOJ` en el plan

`docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md` §5, fallos bloqueantes: "Perfil de instalación inválido (`ARR_PERFIL`); reloj alterado (`ARR_RELOJ`, etapa 1: reloj del sistema anterior a la fecha de instalación)."
