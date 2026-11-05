# SMP — respuesta de las salidas en modo prueba (tanda 26)

Síntoma (Cristian): al activar una salida por error no se puede desactivar hasta que el botón cambia, y el cambio tarda.

## Qué se hizo

- **Orden pendiente por salida sostenida** (`ui_qml/controllers/entradas_salidas_controller.py`): tras un PATCH `/io/test/output/{nombre}` **aceptado** el controlador guarda `{nombre: (valor ordenado, monotonic de la respuesta)}`. Mientras está pendiente, el botón muestra lo ordenado («Apagar» si se ordenó ON) con la marca «Orden enviada, esperando confirmación» (`io.ui.orden_pendiente`, es/en) y un toque envía el **inverso del último valor ordenado** (slot nuevo `alternar(nombre)`; la QML ya no decide el valor con `encendida !== true`). La orden se resuelve con el primer `/status` pedido después de la respuesta que muestre el valor ordenado, o vence a los **3 s** (`PLAZO_ORDEN_PENDIENTE_S`, `DECISIÓN SIN CONFIRMAR`) y entonces manda el `/status`.
- **Armado en Python:** `presentar_con_pendientes()` agrega a cada salida `pendiente`, `apagar` (el próximo toque apaga) y `claveBoton`; la QML solo dibuja (`puedeApagar` usa `modelData.apagar`, el texto `modelData.claveBoton`, la marca `modelData.pendiente`). Colores solo de `Tema/` (`Colores.textoGuia`), sin `elide` (la marca va con `WordWrap` en 190 px).
- **Relectura rápida:** con alguna orden pendiente, un `QTimer` de 200 ms (`SONDEO_PENDIENTE_MS`) llama a `actualizar()` (lee el caché, sin red); se detiene al no quedar órdenes. El `Timer` de 1 s de la pantalla no cambia. No se agregó señal al caché (`cliente/ui_service_backend.py` fuera del alcance).
- Se conserva: apagar sale siempre (fase 6); encender exige `salidasHabilitadas` (rechazo local sin enviar) y las protecciones ESG-02 del backend; un ON rechazado **no** queda pendiente y no borra una orden aceptada anterior; un OFF con `modo_prueba_inactivo` cuenta como hecho (pendiente OFF); con atrapamiento (D-ES-16) se toma el `value` respondido; las momentáneas no cambian; `accionar` sigue síncrono. Al confirmarse el modo prueba inactivo sin dudas se limpian las órdenes pendientes.
- **Log de desarrollo** (logger `autoclave.ui_qml.controllers.entradas_salidas_controller.latencia`, DEBUG, no bitácora): respuesta del PATCH y primer `/status` que refleja la orden, con `time.monotonic()`. **Backend sin tocar** (ni rutas, ni ModbusLink, ni ControlLoop): la escritura fc05 y el tick del lazo se miden desde fuera en el banco.

## Medición (simulador M31, `tests/banco/t26_smp_latencia_salidas.py`)

Backend completo en proceso (BackendContext, arranque, ModbusLink con sondeo 0,1 s de producción, ControlLoop real 0,5 s, rutas por TestClient), caché `UIServiceBackend` real (0,2 s) y el controlador real. 12 órdenes ON/OFF alternas sobre `vapor_generador` (DO 1), 5-nov. Segundos desde el toque:

| Instante | Mediana | Máximo |
|---|---|---|
| Respuesta del PATCH (fc05 incluido) | 0,009 | 0,011 |
| Bobina cambiada en el simulador (fc05) | 0,010 | 0,012 |
| `EstadoAutoclave.salidas_do` refleja (tick del lazo) | 0,340 | 0,519 |
| Primer `/status` del caché que lo refleja | 0,421 | 0,640 |
| Pantalla **antes** (Timer 1 s, fase al azar, modelado) | 0,809 | 1,392 |
| Orden pendiente resuelta **ahora** (relectura 0,2 s) | 0,422 | 0,641 |
| Botón muestra lo ordenado **ahora** | ≈ 0,01 (al volver el PATCH) | — |

Limitaciones: HTTP en proceso (sin uvicorn ni red local: en el PC real se suman algunos ms); el «repintado» es la emisión de `cambioDatos` (sin QML); la columna «antes» es un modelo del Timer de 1 s sobre los instantes medidos. Peor caso teórico antes: 1 s de Timer + ~0,6 s de lazo y caché ≈ 1,6–2 s, coherente con el síntoma. Pendiente de banco con el M31 real (bloque T26).

## Hallazgos

- **SMP-01 (MEDIA) — toque doble enviaba ON dos veces.** Entre el ON y el primer `/status` que lo reflejaba (0,25–1,4 s medidos con la pantalla anterior) el botón seguía en «Activar» y un segundo toque volvía a mandar ON; `puedeApagar` exigía `encendida === true`, así que tampoco se ofrecía apagar. Corregido con la orden pendiente: el segundo toque envía OFF a los ~10 ms. Riesgo HAZ-SMP-01.
- **SMP-02 (BAJA) — la pantalla esperaba el Timer de 1 s.** El retraso visible lo dominaba el Timer de 1 s de la pantalla más el descarte de `/status` anteriores a la orden. Reducido en la UI (relectura de 0,2 s con orden pendiente): mediana 0,81 → 0,42 s, máximo 1,39 → 0,64 s.
- **SMP-03 (INFORMATIVO) — el PATCH no espera al lazo.** `rutas/io.py` `io_test_set_output` llama a `SetOutput.set_output` → `ModbusLink.set_output`, que escribe fc05 síncrono bajo `_cmd_lock` (≈10 ms con el simulador). Lo que demora el reflejo es la publicación: el hilo de sondeo lee fc01 cada 0,1 s, pero `estado.salidas_do` solo se actualiza en el tick del `ControlLoop` (`interval` 0,5 s + duración del tick, `estado.update(units.get_all())`) y el caché de la UI pide `/status` cada 0,2 s. **No se cambió** el periodo del lazo ni MOD-08 (restricción).
- **SMP-04 (BAJA, residual) — lo ordenado puede no ser lo real hasta 3 s.** Si el backend corta la salida justo después de aceptarla (ESG-02 paso 2e, `avisos_corte_prueba`) o el módulo no la aplica, el botón muestra lo ordenado con la marca «pendiente» hasta 3 s; luego manda el `/status`. La etiqueta ON/OFF de la tarjeta sigue mostrando siempre lo leído y el aviso de corte sigue en pantalla. Ningún camino enciende nada por esto: el toque sobre una orden ON pendiente envía OFF.

## Decisiones sin confirmar

- `PLAZO_ORDEN_PENDIENTE_S` = 3 s (prompt §3.2).
- El rechazo de una orden no borra la orden aceptada anterior (lo último que el backend aceptó sigue siendo lo mejor conocido).
- La etiqueta ON/OFF muestra lo leído; solo el botón muestra lo ordenado.
- La marca de pendiente es un texto aparte sobre el botón (no un sufijo en el botón, que no cabe en 190 px).

## Puerta de entrada IEC 62304 (NTC-IEC 62304:2019 / IEC 62304:2006)

1. Toca el mando manual de actuadores en modo prueba: se trata como Clase C. 2. Solicitud de cambio: prompt de la tanda 26 §3 (8.2.1). 3. Causa nueva: SMP-04 (lo mostrado puede adelantarse a lo real ≤ 3 s), acotada; no interfiere con ESG-02, MOD-08 ni el lazo, que quedan en el backend sin cambios (7.4.2). 4. Diseño afectado: controlador y pantalla de Entradas/Salidas; CLAUDE.md la anota el hilo principal (5.4). 5. Verificación: pruebas unitarias nuevas y regresión de entradas/salidas y modo prueba (5.5.5, 8.2.3); banco con M31 real pendiente. 6. SOUP sin cambios. 7. Trazabilidad: HAZ-SMP-01 (registro de riesgos, lo agrega el hilo principal §5); las pruebas llevan `req("HAZ-SMP-01")`.

## Pruebas

`tests/test_t26_smp_orden_pendiente.py` (14): ON y toque antes del `/status` → OFF; `/status` nuevo que lo refleja la resuelve; ON rechazado no queda pendiente; un rechazo no borra la aceptada; ventana vencida manda el `/status` (viejo o nuevo distinto); modo prueba sin confirmar → apagar disponible y encender no sale; `modo_prueba_inactivo`; atrapamiento; momentáneas sin cambio; relectura de 200 ms solo con orden pendiente; limpieza al salir del modo prueba; claves i18n es/en; la QML usa el armado del controlador.
Ajustada `tests/test_f6_modo_prueba_async.py::test_m1_qml_ofrece_el_apagado_de_una_sostenida_encendida`: fijaba el texto literal `modelData.encendida === true`; ahora fija `modelData.apagar === true` y comprueba que, sin orden pendiente, `apagar` es exactamente `encendida === true` (misma regla M1, sin relajarla).
