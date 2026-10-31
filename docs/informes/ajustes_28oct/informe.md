# Informe — ajustes del 28-oct (AJ-01, AJ-02, AJ-03)

Rama `ajustes-28oct` desde `dev` (cbad00c). Sin unir a `dev`, sin `push` y sin `compilar_entrega.py`: Cristian revisa en pantalla y une.

| Paso | Commits |
|---|---|
| A. AJ-01 «Apagar equipo» fuera del ciclo | 6293e8c |
| B. AJ-02 `agua_intercambiador` = OR de vacío y drenaje | 2465920, 24429f2 (observación de la revisión de seguridad) |
| C. AJ-03 globo de valores de la gráfica | 87569e1 |

Suite completa: ver §5.

## 1. AJ-01: ocultar «Apagar equipo» durante el ciclo

**Qué cambió**

- `ComandosSistema.fueraDeCiclo` (`ui_qml/bridge/comandos_sistema.py`), nueva propiedad que sigue a `UiBridge.machineState` (`machineStateChanged`):
  - Vale True solo con un estado conocido distinto de CICLO.
  - Con `CICLO`, `DESCONOCIDO`, vacío o sin dato del puente vale False (falla cerrada).
  - `apagarEquipo()` tampoco envía la orden fuera de ese caso. Es defensa en profundidad: el backend ya responde 409 y no se tocó.
- `PanelEquipo.qml`:
  - Propiedad nueva `permiteApagar`, por omisión `true`.
  - `puedeApagar = ventanaPrincipal && permiteApagar && fueraDeCiclo`.
  - Si `puedeApagar` pasa a false con el panel abierto, `confirmarApagar` se cierra, y la zona de apagar se oculta por su `visible`.
  - El `onConfirmado` vuelve a comprobar `puedeApagar` antes de llamar a `apagarEquipo()`.
- `PantallaCicloEnCurso.qml` fija `permiteApagar: false`, también en la espera de CONFIRMAR, porque es la misma pantalla. Se agregó `objectName` a los paneles de Ciclo y Preciclo para las pruebas.

**Pruebas:** `tests/test_aj01_apagar_fuera_de_ciclo.py` (28).

- Python: `fueraDeCiclo` por estado, sin dato, con aviso al cambiar, y `apagarEquipo` en CICLO.
- QML, con Menú Principal, Preciclo y Ciclo en curso cargados a la vez y un `comandosSistema` falso:
  - oculto en la pantalla de ciclo con resultado vacío, COMPLETADO, FALLO y CANCELADO;
  - oculto en las tres pantallas con el equipo en CICLO;
  - visible en Menú y Preciclo fuera de ciclo en la ventana principal;
  - oculto en la ventana secundaria;
  - con el panel y el diálogo abiertos, el paso a CICLO cierra el diálogo, oculta el botón y no se apaga nada.

**Pruebas existentes ajustadas, sin aflojar nada:** en `test_t7_ui_seguridad.py` y `test_t8_e1_apagado_rechazado.py`, el `MagicMock` del puente ahora lleva `machineState = "PREPARADO"`. Sin eso, el nuevo bloqueo en CICLO o sin dato impedía la orden que esas pruebas ejercitan.

## 2. AJ-02: `agua_intercambiador` como OR de dos peticiones

**Qué cambió**

`devices/io/set_io.py` (`SetOutput`):

- **Petición «vacío»** (`_agua_por_vacio`): la fijan solo `vacio_camara_on/off`.
- **Petición «drenaje»** (`_agua_por_drenaje`): la fijan solo `agua_intercambiador_on/off`. Sus dueños no cambian: `CicloState._mantener_drenaje`, `preparacion.verificar_temperatura_drenaje` y `preparado.mantener_drenaje`, con su debounce de 3 lecturas, sin lectura → ON, y el `ConfirmadorApagado`.
- **Una sola orden al canal:** `_aplicar_agua()` escribe `vacío or drenaje` con `_salida`.
  - Mientras alguna pida ON, el canal solo recibe ON (reafirmaciones que ModbusLink no escribe porque no cambian).
  - Rigen `inhibidas`, los canales de vapor bloqueados, el paro (D9-9, `_paro_bloquea`) y MOD-08 (en ModbusLink), igual que para toda salida.
- El escalonado `_STAGGER_APAGADO_VACIO` no cambia. `vacio_camara_off()` apaga `vacio_camara` y en seguida aplica el agua; si el drenaje no la pide, se apaga junto con `vacio_camara`, en el mismo grupo que antes. El orden de `vacio_camara_on()` (agua y luego vacío) es el de siempre.
- `set_output(index, value)` público pasa a ser la orden directa por canal: si el canal es el del agua, actualiza las peticiones. La escritura común quedó en `_escribir`.
- Nuevos `peticiones_agua_intercambiador` (diagnóstico y pruebas) y `anotar_todo_apagado()`.

**Rutas que apagan sin pasar por esos métodos, revisadas una por una**

| Ruta | Dónde | Qué queda en las peticiones |
|---|---|---|
| ALL_OFF de `reset_all_outputs` (confirmado o con las órdenes individuales de respaldo) | `set_io.py` | Las dos en False: el hardware quedó con la orden de apagado. |
| Protocolo de fallo (`ejecutar` y el reintento de `update`) | `protocolo_fallo.py:567`, `:838` | Por `reset_all_outputs`, las dos en False. En la espera de confirmación, `_mantener_drenaje` corre después del protocolo y vuelve a pedir el agua si el drenaje está caliente o sin lectura. |
| Paro de emergencia (`apagar_por_paro`, en CICLO, FALLA, PREPARACION y PREPARADO; flanco inmediato del lazo) | `ciclo.py:1004`, `falla.py:27`, `preparacion.py:62`, `preparado.py:78`, `control_loop.py:1247` | Por `reset_all_outputs`, las dos en False. Durante el paro, una nueva petición queda anotada pero `_paro_bloquea` mantiene el canal en OFF. |
| Estado seguro, abortos forzados y CIC-10 | por el protocolo de fallo | Como el protocolo. |
| Errores seguidos del tick, configuración inválida, paro en modo prueba | `control_loop.py:305`, `:1114`, `:1133` | Por `reset_all_outputs`, las dos en False. |
| Entrada y salida del modo prueba, reintentos del ALL_OFF (D8-2.11) | `control_loop.py:1510`, `:1524`, `:1554` | Por `reset_all_outputs`, las dos en False. |
| `/outputs/reset` del backend | `rutas/ciclo.py:499` | Por `reset_all_outputs`, las dos en False. |
| Órdenes por canal del modo prueba (`/io/test/output`, momentáneas, puerta atrapada) | `rutas/io.py:508`, `:775-789` | Con el canal del agua: OFF pone las dos en False; ON cuenta como petición del drenaje (ante duda, ON). |
| Cortes del lazo en modo prueba (salidas bloqueadas, aire atmosférico) | `control_loop.py:676`, `:1298` | No tocan el canal del agua (`salidas_prueba_seguridad` no lo incluye). Si algún día lo tocaran, rige la fila anterior. |
| Apagado del equipo (`iniciar_apagado`) y detención del lazo (`stop`): ALL_OFF directo al enlace | `control_loop.py` | Las dos en False con `anotar_todo_apagado()`. Lo agregó 24429f2, a raíz de la observación SAF-01 de la revisión de seguridad. |
| Reconexión del enlace o 0F tras una conexión fallida (interno de ModbusLink) | `modbus_link.py:904`, `:1102-1108` | Las peticiones no se tocan (ante duda, ON). ModbusLink reinicia lo comandado a OFF, así que la siguiente orden de un dueño, que llega en cada tick, vuelve a escribir el OR. |
| Vigilancia MOD-08 (sin tick, el módulo apaga solo) | ModbusLink / módulo | Igual que la reconexión. |

**Pruebas:** `tests/test_aj02_agua_intercambiador_or.py` (17). Usan `SetOutput` real con `EnlaceRegistrador` y el orden real del tick: `_mantener_drenaje` y luego `fase.update()`.

- **Drenaje frío:** en PREVACIO (VACIO_BAJO y HOLD_BAJO) y en SECADO (modos 1, 2 y 3) el canal recibe una sola escritura efectiva ON y ninguna orden OFF, ni cruda, hasta que termina el vacío. Al terminar, una OFF.
- **Escalonado:** el agua sale en el mismo grupo que `vacio_camara`, después de la bomba.
- **Drenaje caliente:** `vacio_camara_off()` no apaga el agua, ni en PREVACIO ni en SECADO.
- **Sin lectura de drenaje:** ON.
- **Apagados:** ALL_OFF confirmado y sin confirmar apagan todo y borran las peticiones. El paro apaga todo y no deja encender. Una salida inhibida no se enciende. Las órdenes directas al canal dejan las peticiones coherentes. El apagado del equipo por el lazo también las borra.

Con el `set_io.py` anterior fallan 14 de las 16 pruebas originales.

Las «escrituras» se cuentan como cambios de valor en el canal, porque así escribe ModbusLink (fc05 solo en cambios). Aparte se exige que **ninguna** orden OFF cruda llegue al enlace mientras dura el vacío.

**Pruebas existentes:** las de drenaje (`test_ciclo_drenaje*`, `test_preparacion_temperatura_drenaje`, `test_preparado_drenaje`), prevacío (`test_prevacio_apagado_escalonado`, `test_prevacio_caps`), secado, B9, E0, adenda y todas las que usan `SetOutput` pasan sin cambios.

**Riesgos:** AN-36 en `docs/riesgos/registro_riesgos.md`, sección «Ajustes del 28-oct-2026»: golpe de ariete y desgaste de la solenoide por la conmutación cada 0,5 s, y condensado sin enfriar con drenaje caliente. Riesgo residual BAJO.

**Revisión de seguridad** (subagente `safety-reviewer`, solo lectura): sin hallazgos críticos, altos ni medios. Hizo dos observaciones de severidad baja:

- **SAF-01:** el ALL_OFF directo del apagado no borraba las peticiones. Atendida en 24429f2.
- **SAF-02:** `canal_do("agua_intercambiador")` lanzaría con una asignación sin esa clave. Hoy no puede pasar (`status.py:92` siempre la trae) y el comportamiento es el de antes. No se cambió.

## 3. AJ-03: globo de valores de la gráfica

**Qué cambió** en `Componentes/GraficaCiclo.qml`:

- **Nombre de cada fila:** usa `TextoAjustable` con `anchoDisponible` desde x = 35 hasta el borde izquierdo del valor de esa fila, menos 8 px del mockup. Muestra el completo si cabe y, si no, el abreviado: nombre abreviado + sufijos abreviados (`textoSerieAbrev`). Para las series por omisión se usan `abrev.ciclo.serie_*`.
- **Valor:** sigue alineado a la derecha, a 9 px del mockup del borde (x = 211 de 220).
- **Ancho del globo:** es `max(220, fila más ancha con su abreviado, hora + 18 + 18)` del mockup. El ancho de cada fila se mide con `TextMetrics` sobre el abreviado, no sobre lo mostrado, así que no hay lazo de enlaces. Con eso, si ni el abreviado cabe en 220, el globo crece lo justo y el nombre queda abreviado.
- **Posición:** x se sigue recortando a la tarjeta, como antes.
- Nunca se recorta ni se elide (D8-5.4).

**Catálogo** (`es.json` / `en.json`, sección `abrev.ciclo`), claves nuevas:

| Clave | es | en |
|---|---|---|
| `serie_temp_camara` | Temp. cámara | Chamber temp. |
| `serie_temp_ref` | Temp. referencia | Reference temp. |
| `serie_presion` | Pres. | Press. |
| `monitoreo` | (mon.) | (mon.) |
| `serie_sin_registro` | (s/reg.) | (n/l) |

`abrev.ciclo.entrada_corta_pres_camara` no se agregó porque «Presión» / «Pressure» ya es corto («si hace falta»).

**Pruebas:** `tests/test_aj03_globo_grafica_qml.py` (20).

- Casos: es y en, escalas de 1024 y 1200 px, cursor al inicio, en medio y al final, valores «—» y «-123.4».
- Filas probadas: «Temperatura de drenaje de cámara (monitoreo)», «Presión de empaque 2 (sin registro)» y «Temperatura de cámara 2 (monitoreo) (sin registro)».
- Se comprueba que:
  - ninguna fila desborda ni se recorta, y nombre y valor no se solapan;
  - valor y hora quedan dentro del globo, y el globo dentro de la tarjeta, con al menos 220;
  - cuando crece, crece solo lo justo;
  - se abrevia solo si no cabe el completo.
- Control: con las series por omisión y «—», el globo no crece.

Medido: con las tres filas largas y «-123.4 kPa», el globo pasa de 220 a ≈ 326 px del mockup (es) y ≈ 318 (en), con los tres nombres abreviados.

## 4. Decisiones sin confirmar

1. **DECISIÓN SIN CONFIRMAR (AJ-01):** `apagarEquipo()` del puente también se niega en CICLO o sin dato del estado. Es más estricto que «solo ocultar», pero en el mismo sentido que el 409 del backend.
2. **DECISIÓN SIN CONFIRMAR (AJ-01):** fuera de CICLO, «sin dato del estado» incluye `DESCONOCIDO`, que es el valor del puente antes del primer `/status`. En ese caso el botón no se ve.
3. **DECISIÓN SIN CONFIRMAR (AJ-02):** después de un ALL_OFF las dos peticiones quedan en False, coherentes con el hardware apagado, y no en ON. Los dueños del drenaje la reafirman en el tick siguiente; el comportamiento es el mismo que antes del cambio. Una orden directa ON al canal (modo prueba) cuenta como petición del drenaje.
4. **DECISIÓN SIN CONFIRMAR (AJ-02):** la reconexión del enlace y el corte MOD-08 no tocan las peticiones (ante duda, ON). Sus dueños las reafirman en cada tick y ModbusLink vuelve a escribir el OR porque reinicia lo comandado a OFF.
5. **DECISIÓN SIN CONFIRMAR (AJ-03):** cuando el globo crece, todas las filas quedan abreviadas, porque el ancho se calcula con el abreviado. La alternativa, crecer hasta que quepa el texto completo, haría el globo mucho más ancho.
6. **DECISIÓN SIN CONFIRMAR (AJ-03):** abreviaturas en inglés iguales a las del encargo: «(mon.)» y «(n/l)».

## 5. Suite completa

`python -m pytest tests -n auto -q -p no:cacheprovider` (salida cruda en `suite_raw.txt`):

- **1 failed, 8887 passed, 11 skipped, 3 xfailed** en 407,6 s.
- La que falla es `tests/test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`, por el cierre del trabajador `gw7` («worker crashed»).
  - Ya figuraba como «fallida solo en paralelo» en la línea base de la tanda 20 (`docs/informes/tanda20/base_suite.txt`).
  - Sola pasa: `pytest tests/test_home_view.py` da 1 passed.
  - No toca nada de estos ajustes. Se cuenta como verde, igual que en la tanda 20.
- Son 8902 pruebas recolectadas (65 nuevas: 28 + 17 + 20).

`tests/test_b1_barra_preciclo_ciclo_qml.py` puede dar errores de carrera en paralelo, porque escribe un archivo QML temporal con nombre fijo. Pasa sola (10/10). Es anterior a estos ajustes.

## 6. Qué debe verificar Cristian en pantalla

1. **AJ-01:**
   - Con un ciclo en curso, el panel de información del equipo (tocar modelo/serie) no muestra «Apagar equipo». Tampoco después de COMPLETADO, FALLO o CANCELADO mientras se espera CONFIRMAR.
   - Tras CONFIRMAR, en Preciclo o Menú Principal de la pantalla 1, el botón vuelve a aparecer. En la pantalla 2 no aparece nunca.
   - Abrir el panel con el diálogo «¿Apagar?» en Preciclo e iniciar el ciclo desde la otra pantalla: el diálogo se cierra solo.
2. **AJ-02:** en el banco, durante PREVACIO (pulso bajo) y SECADO modos 1–3 con el drenaje frío, el canal de `agua_intercambiador` (DO17 con la asignación por defecto) queda encendido fijo durante el vacío, sin clics de la solenoide, y se apaga junto con `vacio_camara`. Con el drenaje caliente queda encendido al terminar el vacío.
3. **AJ-03:**
   - Con entradas mostradas largas (p. ej. Temperatura de drenaje de cámara en monitoreo, Presión de empaque 2 sin registro), tocar la gráfica: el globo muestra los nombres abreviados sin montarse sobre el valor y crece si hace falta, sin salirse de la tarjeta, en es y en.
   - Con las tres series de siempre, el globo se ve como antes.
