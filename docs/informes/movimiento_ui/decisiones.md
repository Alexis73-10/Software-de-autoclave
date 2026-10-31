# Movimiento de la interfaz: elemento compartido y crossfade (31-oct)

Pedido de Cristian: (1) aplicar *shared element* a todas las tarjetas que abren algo (alarmas,
calibración y demás); (2) que los cambios de ventana del menú de Opciones (p. ej. Parámetros del
ciclo → Parámetros del equipo) sean *crossfade*. Ejecutado sin supervisión; las decisiones tomadas
están aquí para revisarlas.

## Qué se hizo

| Pieza | Archivo |
|---|---|
| Duraciones y origen de la última tarjeta tocada | `qml/Tema/Movimiento.qml` (singleton) |
| Crossfade de sección (Loader que se desvanece) | `qml/Componentes/CargadorSeccion.qml` |
| Elemento compartido (fantasma tarjeta → destino) | `qml/Componentes/ElementoCompartido.qml` |
| Secciones de Opciones con crossfade (11) | `qml/Pantallas/Opciones.qml` |
| Tarjeta → ventana | `VentanaFlotante.qml` (Menú Principal, selector de ciclo de Preciclo), `PanelModal.qml` (Información del equipo), `VentanaDetalleAlarma.qml` |
| Tarjeta/fila → vista dentro de Opciones | `OpcionesParametrosEquipo.qml` (tarjeta de grupo → lista; fila → ajuste), `OpcionesParametrosCiclo.qml` (fila → sección/sensores/entradas; fila → ajuste), `OpcionesMantenimiento.qml` (botón Calibrar → calibración atmosférica) |
| Tarjetas que registran su origen al tocarlas | `TarjetaMenu`, `TarjetaResumen`, `FilaAlarma`, y las filas/tarjetas internas citadas |
| Prueba | `tests/test_movimiento_ui_qml.py` + `qml/Pruebas/PruebaMovimiento.qml` |

## Decisiones (todas revisables)

1. **Qt Quick no tiene *shared element* nativo.** Se implementó como *container transform*: un
   rectángulo "fantasma" viaja del rectángulo de la tarjeta al del destino (posición, tamaño,
   radio y color interpolados, 320 ms, `InOutCubic`), el fondo se atenúa y el contenido del
   destino aparece en la segunda mitad. **Solo el contenedor es compartido**; los textos y los
   iconos de la tarjeta no viajan (habría que duplicarlos). Si se quiere que viaje el icono o el
   título, es un paso siguiente.
2. **Origen por registro global, no por parámetro.** Cada tarjeta, al tocarse, llama
   `Movimiento.registrarOrigen(self)`; la ventana que se abre a continuación lo toma con
   `Movimiento.tomarOrigen()` (caduca al segundo). Así no se tocaron las ~30 señales `pulsada` de
   las pantallas. Una apertura sin tarjeta (por ejemplo una alarma que abre su propio detalle, o
   el recuadro de Programa de Preciclo) crece desde el centro del destino, sin viaje.
3. **Cierre inverso.** Al cerrar, el fantasma vuelve a la tarjeta si sigue en pantalla. Durante
   esos 320 ms la ventana sigue `visible`, pero la lógica ya la da por cerrada (`abierta` /
   `abierto` en false, señal `cerrada()` inmediata, `Atrás` ya no la considera abierta).
4. **Crossfade de Opciones.** `CargadorSeccion` conserva cargada la sección saliente 220 ms
   (desvaneciéndose, sin recibir toques) mientras la entrante aparece. `itemActivo` devuelve
   `null` para la saliente, así `cambiosPendientes`, `retroceder()` y `navegacionBloqueada`
   nunca consultan una sección que ya se dejó. Dentro de Parámetros del equipo/ciclo y
   Mantenimiento, las vistas internas también se funden (mismos 220 ms).
5. **Pruebas sin animación.** `Movimiento.instantaneo` vale `true` con la plataforma `offscreen`
   (la de todas las pruebas QML existentes), así que no cambió ninguna. Solo
   `PruebaMovimiento.qml` lo pone en `false` para ejercitar el movimiento.
6. **Fuera de alcance (a propósito):**
   - `OpcionTarjeta` (Instalación): son opciones de selección única, no abren nada.
   - Cambios de pantalla completa del Menú Principal (Main.qml, p. ej. tarjeta → Login/Opciones):
     requieren animar el `StackView`/cargador raíz y la doble pantalla; no se tocó para no
     arriesgar la navegación de seguridad.
   - Diálogos de confirmación (`DialogoConfirmacion`, `ModalConfirmacion`): son avisos, no
     detalle de una tarjeta.
   - Panel de la campana (`PanelNotificaciones`): su origen es el icono de la campana, no una
     tarjeta; abre con fundido simple.
7. **No se hizo commit.** El árbol ya traía cambios sin confirmar de otro trabajo
   (rama `automatizacion-instalacion`); mezclarlos habría ensuciado esa rama.

## Pendiente de verificar a ojo en el equipo

El movimiento se comprobó por pruebas (progreso del fantasma, ventana visible durante el viaje,
sección saliente descargada al terminar), no mirándolo. Falta verlo en la pantalla real: duración
(`Movimiento.compartidoMs`, `crossfadeMs`) y si el fantasma se nota sobre el fondo de cada tarjeta
(`TarjetaResumen` tiene otro color que `fondoTarjeta`; el fantasma parte de blanco).
