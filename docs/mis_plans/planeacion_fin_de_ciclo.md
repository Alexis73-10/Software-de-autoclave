# Planeación — Fin de ciclo, puerta sin actuador y textos que desbordan (tanda 21)

Fecha: 28-oct-2026. Decisiones de Cristian tomadas en el chat del 28-oct, a partir de los renders de la pantalla actual y de los mockups aprobados.
Mockups de referencia: `docs/diseno/mockups/fin_de_ciclo/*.png` (renderizados con el QML real a 800 × 1280; lo nuevo es un prototipo superpuesto con los colores y la tipografía del tema).
Código Clase C (NTC-IEC 62304). Todo cambio de comportamiento del ciclo (FC-08) va al registro de riesgos.

Hoy la pantalla de ciclo terminado tiene: insignia de estado, recuadro «CARGA NO ESTÉRIL» sobre la gráfica (D8-2.16), franja NO CONFORME con botón de reconocimiento (P4, D-14.4), botón CONFIRMAR y `DialogoConfirmacion` para cancelar y para el estado seguro. Todo eso está marcado PROVISIONAL en el código. Problemas que Cristian señaló:
- El recuadro «CARGA NO ESTÉRIL» tapa el título de la gráfica y parece ajeno a la pantalla.
- No distingue un fallo de una cancelación ni dice la causa del fallo.
- «Completo NO CONFORME / carga no liberable» es confuso.
- El texto «Confirmar y llevar a estado seguro» se sale del botón (ancho fijo de 340 px en `DialogoConfirmacion.qml`, sin ajuste).
- En preciclo, con puertas sin actuador, la puerta sigue siendo un botón de acción que dice «ABRIR/CERRAR PUERTA».

---

## FC-01 Panel de fin de ciclo (resultado ≠ exitoso)

Cuando `resultado` es `fallo` o `cancelado` (y ante un resultado desconocido: falla cerrada, se trata como `fallo`), la tarjeta de la gráfica se reemplaza por el **panel de fin de ciclo**, en el mismo rectángulo (x 33, y 804, ancho 1129, alto flexible hasta `yb(1598)`; mismo radio 30 y borde de la tarjeta de la gráfica). Mockups 01, 05 y 06.

Contenido de arriba hacia abajo:
- Título «CARGA NO ESTÉRIL» (Montserrat Bold 36, `Colores.peligroTexto`). Reemplaza al recuadro `cargaNoEsteril`, que se elimina. SAF-04 (S2b) se conserva: el panel es la vista por defecto, y si la gráfica está a pantalla completa, el aviso la cierra.
- Subtítulo (22, `textoSecundario`): «Ciclo NN terminó en FALLO a las HH:MM» / «Ciclo NN cancelado a las HH:MM» / «Ciclo NN abortado por paro de emergencia a las HH:MM».
- Botón de contorno «Ver gráfica» arriba a la derecha (FC-05).
- Divisor; fila de **causa** (FC-02), abierta al entrar.
- Rótulo «ALARMAS Y AVISOS DEL CICLO (N)» y las filas de alarmas (FC-03).
- Si el contenido no cabe, el área bajo el divisor se desplaza (Flickable); el título, el subtítulo y el botón quedan fijos.

Los relojes, la barra de progreso, la tarjeta de parámetros y la barra inferior no cambian.

## FC-02 Fila de causa

Primera fila del panel, más destacada (título Bold 32 y una línea de subtítulo). Contenido según la terminación:
- **Fallo de fase** (FALLO_*, CIC-xx, SENSOR_AUSENTE, etc.): título «Fallo en <fase>» (fase de la UI en la que terminó, FC-06). Subtítulo: el título del catálogo del código (p. ej. «Aire o gases no condensables en la cámara»). Al abrirla: descripción con valores (`alarmas_i18n.motivo_fallo(codigo, valores, motivo, idioma)`), «QUÉ HACER» con la acción del catálogo, y la línea meta «Fase: X · fecha hora · Código CIC-12». Barra de nivel roja.
- **Paro de emergencia**: título «Paro de emergencia», subtítulo «Activado en la fase X», código SIS-01, acción «La carga NO está estéril. Antes de confirmar, verifique que no hay fugas de vapor ni de agua.» Barra roja.
- **Cancelación**: título «Ciclo cancelado por el operador», subtítulo «Cancelado por <usuario> en la fase X» (sin usuario identificado: «Cancelado en la fase X», FC-12). Acción «La carga NO está estéril. Reprocésela con un ciclo completo.» Barra gris (no es una alarma).
- **Fallo sin código conocido**: título «Fallo del ciclo», detalle = `motivo_fallo` crudo. Nunca una fila vacía.

## FC-03 Alarmas del ciclo

Todas las filas de `alarmas_historial` con `ciclo_id` = ciclo actual, en orden cronológico (`aparecida` ascendente). Se incluyen las resueltas y se excluye la alarma que ya es la causa (sin duplicar).
- Fila cerrada: barra de nivel (mismos colores que `FilaAlarma`, por `UiBridge.prioridad_de`), título y hora de aparición.
- Fila abierta: descripción (`descripcion_final` si existe, si no `descripcion_inicial`, en el idioma actual vía `alarmas_i18n`), «QUÉ HACER» con la acción del catálogo (se omite si no hay), y la línea meta «HH:MM:SS · Código X · Se despejó a las HH:MM:SS» o «· Sigue activa».
- Sin filas: «No hubo alarmas ni avisos durante el ciclo.»

Verificar (etapa A0) que toda alarma que aparece en CICLO se escribe con `ciclo_id`. Si hay rutas que la dejan en NULL, se corrigen en el escritor, no en la lectura.

## FC-04 Acordeón

- Una sola fila abierta a la vez. Al entrar, la causa está abierta. Tocar una fila cerrada la abre y cierra la otra; tocar la fila abierta la cierra.
- Chevron «›» a la derecha, rotado 90° cuando la fila está abierta.
- Los textos nunca se recortan ni se eliden (D8-5.4). El cuerpo usa WordWrap; el título de la fila usa `TextoAjustable` (abreviado, y si no cabe, ajuste de tamaño). Fondo `fondoSutil` en la fila abierta (mockups 01 y 02).
- Componente nuevo `Componentes/FilaAcordeon.qml`; el panel completo en `Componentes/PanelFinCiclo.qml`.

## FC-05 Ver gráfica y regreso automático (30 s)

- «Ver gráfica» muestra la gráfica normal. Junto a «Tiempos» aparece una píldora roja «Alarmas (N) · SS s» (N = causa + alarmas; SS = segundos que faltan), alineada a la derecha y terminando antes de «Tiempos» (mockup 03). Tocar la píldora vuelve al panel.
- **Regreso automático:** a los 30 s sin toques en la pantalla, la vista vuelve sola al panel. Cualquier toque en la pantalla (incluido el cursor de la gráfica) reinicia la cuenta. Con un modal abierto la cuenta se detiene. Si la gráfica está a pantalla completa, también se cierra y vuelve al panel. Constante `REGRESO_PANEL_S = 30` en un solo lugar.
- Cada vez que se vuelve al panel, la causa queda abierta otra vez.

## FC-06 Fase de terminación en la barra de fases

- El backend publica en `/cycle/current/progress` la fase de la UI en la que terminó el ciclo (`fase_terminacion`) y le asigna un estado nuevo: `fallida` (fallo y emergencia) o `interrumpida` (cancelación). Las fases anteriores quedan `completada` y las siguientes `pendiente`.
- `BarraFases.qml`: `fallida` se dibuja con el círculo en `Colores.alarmaAlta`; `interrumpida` en `Colores.advertencia`. Mismo ícono de la fase en blanco. `ciclo_en_curso.py` acepta los dos estados nuevos (`_ESTADOS_FASE`).
- Esto también corrige que hoy la fase en la que se cortó el ciclo pueda verse como completada.

## FC-07 Ciclo exitoso

- La vista por defecto sigue siendo la gráfica, sin cambios (mockup 08). No hay regreso automático.
- Si el ciclo tuvo alarmas o avisos registrados (`alarmas_historial` con su `ciclo_id`), aparece una píldora ámbar «Observaciones (N)» (`advertenciaTexto` sobre `advertenciaFondo`) en la misma posición de FC-05, sin cuenta regresiva (mockup 09). Al tocarla se abre el panel con el título «OBSERVACIONES DEL CICLO» en `advertenciaTexto`, sin fila de causa y con «Ver gráfica».
- El modal de CONFIRMAR repite las observaciones de pérdida de Referencia en una nota ámbar (mockup 10, FC-09).

## FC-08 Referencia sin lectura — opción A (reemplaza C-13.7b y P4/D-14.4)

Decisión de Cristian (28-oct): con la sonda de Referencia sin lectura, en carga sólida el ciclo termina **Exitoso** con una observación. Ya no queda NO CONFORME ni requiere reconocimiento.

- **Carga sólida** (`globals.tipo_carga != "liquido"`):
  - SEN-11 sigue siendo un aviso no bloqueante, con despeje manual. Texto nuevo: «Sin lectura de {sensor} en la fase {fase}. El ciclo sigue controlado por el sensor Principal y la presión.» Acción: «Revise la conexión de la sonda de referencia. Valide la carga según su procedimiento antes de liberarla.» (es y en).
  - Se retira la marca NO CONFORME: `_no_conforme`, `estado.no_conforme`, `motivo_no_conforme`, `no_conforme_reconocido`, la franja roja, el botón de reconocimiento y la exigencia de reconocer antes de CONFIRMAR (409 `no_conforme_sin_reconocer`). `POST /cycle/acknowledge-no-conforme` se retira. Si `tests/test_t15_rutas_equivalentes.py` lo impide, se actualiza la base de `docs/informes/tanda15/base/` y se justifica en el informe.
  - El ticket, el PDF, el historial y el correo muestran la línea «Observación: {sensor} sin lectura desde HH:MM ({fase})» en lugar de «NO CONFORME». La línea aparece aunque la Referencia vuelva a leer.
  - **Se conserva** que un ciclo con pérdida de Referencia **no use apertura automática**: pasa al flujo manual de CONFIRMAR, para que alguien vea la observación.
  - Se conserva P8: una Referencia con excursión confirmada que pierde la lectura mantiene la exposición detenida y CIC-14 sigue corriendo.
  - Se conserva C-13.7b en la ventana de estabilización: una Referencia sin lectura no bloquea la entrada a esterilización.
- **Carga líquida** (`globals.tipo_carga == "liquido"`): donde hoy se activaría SEN-11, el ciclo termina en **FALLO** con un código nuevo, **CIC-19 «Sonda de referencia sin lectura»** (alarma bloqueante como CIC-12/13). Descripción: «Sin lectura de {sensor} en la fase {fase}. En carga líquida la temperatura de la carga no se puede verificar. El ciclo se abortó.» Acción: «La carga NO está estéril. Revise la conexión de la sonda y repita el ciclo.» Mismo criterio de confirmación que hoy usa SEN-11 (sin cambiar debounce ni ventana).
- **Ciclos ya registrados** como NO CONFORME en la base: se muestran tal como quedaron. No se reescribe el historial.
- **Registro de riesgos** (`docs/riesgos/registro_riesgos.md`): se actualiza la entrada de C-13/C-13.7b como riesgo aceptado por Cristian el 28-oct, con esta justificación: en carga sólida la liberación es paramétrica, por el sensor Principal, la presión y la verificación de saturación C-03 (±2 K). Mitigaciones: observación visible en pantalla, modal, ticket y registro; apertura automática bloqueada; en líquidos, FALLO. Se actualizan también las referencias a NO CONFORME en `CLAUDE.md`.

## FC-09 Confirmaciones en modal

- Componente nuevo `Componentes/ModalConfirmacion.qml` (basado en `PanelModal`). Contiene:
  - título (Bold 36), divisor y cuerpo (28, WordWrap);
  - una nota opcional resaltada (fondo `advertenciaFondo`, borde `advertencia`, texto `advertenciaTexto`);
  - dos botones de 340 × 88: «Volver» (contorno) y el botón de acción, con color configurable y texto con `fontSizeMode: HorizontalFit`.
  - Tocar el fondo equivale a «Volver», sin acción.
- Se usa para todas las confirmaciones de la pantalla de ciclo y del preciclo. Reemplaza `DialogoConfirmacion` en esas dos pantallas. Los demás usos de `DialogoConfirmacion` en el software se enumeran en el informe y no se tocan.
- Textos (es y en; claves nuevas en `ciclo.*`). Mockups 04, 07, 08, 10 y 11:
  - **Cancelar ciclo**: título «Cancelar ciclo»; cuerpo «El ciclo se detendrá y la carga quedará NO ESTÉRIL. ¿Desea cancelar el ciclo NN?»; acción «Cancelar ciclo» en `peligroTexto`.
  - **Confirmar exitoso**: título «Confirmar ciclo»; cuerpo «El ciclo NN terminó con éxito. Al confirmar se registra el resultado y la pantalla vuelve al menú.»; acción «Confirmar» en verde (`menuVerde`). Si hubo pérdida de Referencia (FC-08), se añade como nota la observación con la hora y la fase.
  - **Confirmar fallo o cancelado**: título «Confirmar resultado del ciclo»; cuerpo «El ciclo NN terminó en FALLO (o: fue cancelado). La carga NO está estéril y debe reprocesarse. Al confirmar se registra el resultado y la pantalla vuelve al menú.»; acción «Confirmar» (`accionPrimario`).
  - **Estado seguro tras un paro** (`ackConfirmaEstadoSeguro`): título «Confirmar y llevar a estado seguro»; cuerpo «El paro de emergencia se liberó. La carga NO está estéril.»; nota «Verifique que no hay fugas de vapor ni de agua. Al confirmar, la cámara se lleva a estado seguro.»; acción «Confirmar».
  - Preciclo, `confirmarSinRegistro`: mismo componente, conservando su texto actual.
- El aviso de error de comando (`avisoComando`) sigue siendo `PanelModal`.

## FC-10 Textos que desbordan (todo el software)

Regla de Cristian: la corrección aplica a todo el software, no solo a la pantalla mencionada. Ningún texto se recorta ni se elide (D8-5.4). Orden de solución:
1. abreviado `abrev.*` con `TextoAjustable`;
2. `fontSizeMode: Text.HorizontalFit` con un mínimo legible (`Escala.fuenteMinima`);
3. ensanchar el contenedor si lo permite el diseño.

- Revisar en es y en todos los botones y rótulos de ancho fijo del QML: `DialogoConfirmacion`, `BotonAccion` de preciclo, botones de `PanelModal`, `BotonPildora`, `SeccionEstadoSeguro` (su botón «Confirmar y llevar a estado seguro»), barras inferiores y pestañas de Opciones.
- Prueba nueva en la línea de `tests/test_u10a_textos_caben_qml.py`: carga cada componente con el texto más largo de es y de en y verifica que `implicitWidth` (o el ancho ajustado) cabe en su contenedor.
- El informe lista cada texto corregido y la solución aplicada.

## FC-11 Puerta sin actuador en preciclo

- **Backend**: `/status` publica, por puerta, si tiene actuador. El dato sale de la misma regla que ya usa el endpoint de puertas (`servicio.tiene_actuador(door_name)` / `tipo_tiene_actuador`). La interfaz no lee el perfil por su cuenta.
- **UiBridge**: propiedad `puertaConActuador` de la puerta de esa pantalla. Sin dato vale `false` (falla cerrada: indicador sin acción).
- **PantallaPreciclo.qml**:
  - Con actuador, el `BotonAccion` de puerta no cambia («ABRIR PUERTA» / «CERRAR PUERTA»).
  - Sin actuador, en la misma caja (41, 1615, 298, 110) va un **indicador** (mockups 02 a 04):
    - Rectángulo plano de radio 14, sin degradado ni sombra, sin MouseArea; nunca envía comandos.
    - Ícono del estado (`close_door_N` si está cerrada, `open_door_N` si está abierta), coloreado con `MultiEffect.colorization`.
    - Texto Bold 22 en dos líneas como máximo.
  - Estados del indicador:
    - «PUERTA CERRADA» solo con `DoorState.CERRADO` confirmado: fondo `#EAF1F8`, borde y texto `fondoBarraSuperior`.
    - «PUERTA ABIERTA» en cualquier otro estado: fondo `advertenciaFondo`, borde `advertencia`, texto `advertenciaTexto`.
    - Sin datos vigentes: «PUERTA —» en gris (`fondoSutil` / `bordeCampo` / `textoGuia`), sin ícono.
  - Claves i18n nuevas: `ciclo.puerta_cerrada_estado` («PUERTA CERRADA» / «DOOR CLOSED») y `ciclo.puerta_abierta_estado` («PUERTA ABIERTA» / «DOOR OPEN»).
- En equipos de dos puertas, cada pantalla muestra su propia puerta. El tipo de puerta es uno por equipo, según el perfil.

## FC-12 Usuario que cancela

`POST /cycle/abort` acepta, igual que `/cycle/start` (O1, tanda 3), un token de sesión opcional. Si es válido, el usuario queda como `cancelado_por`:
- en el estado, para publicarlo en FC-13;
- en la fila de auditoría de la cancelación;
- en el ticket.

El token no es requisito: la cancelación sigue sin pedir credencial (plan §10). La UI envía el token de la sesión abierta si la hay.

## FC-13 Datos para la pantalla

Se extiende `GET /cycle/current/progress`. Solo con `resultado` distinto de None, agrega:
- `terminacion`: `{tipo: "fallo"|"emergencia"|"cancelado"|"exitoso", codigo, valores, motivo, fase, hora_fin, cancelado_por}`.
- `alarmas_ciclo`: lista de `{codigo, nivel, titulo, descripcion, valores, aparecida, resuelta}` de `alarmas_historial` del ciclo, sin la fila de la causa.

Los textos se arman en la UI con `alarmas_i18n` y el idioma vigente (bridge `ProgresoCiclo`/`ciclo_en_curso.py`), igual que el historial. `normalizar_progreso` valida los campos nuevos y, ante datos mal formados, deja listas vacías y `tipo: "fallo"` (falla cerrada).

---

## Fuera de alcance

Diseño definitivo del diseñador; la pantalla del historial; las pantallas de PySide; las puertas automáticas (su botón no cambia).

## Pruebas mínimas

- **Backend**:
  - `terminacion` y `alarmas_ciclo` para fallo, emergencia, cancelación con y sin token, y exitoso;
  - `fase_terminacion` con sus estados `fallida`/`interrumpida`;
  - toda alarma en CICLO queda con `ciclo_id`;
  - FC-08 en sólidos: COMPLETADO, sin NO CONFORME, observación en ticket y PDF, apertura automática bloqueada;
  - FC-08 en líquidos: FALLO CIC-19;
  - P8 y C-03 sin cambios;
  - `/status` con `tiene_actuador` para SimpleDoor y AdvancedDoor.
- **QML** (offscreen):
  - el panel aparece con fallo y con cancelado, y no con exitoso;
  - el acordeón deja una sola fila abierta;
  - el regreso automático con tiempo inyectable (no esperar 30 s reales);
  - la cuenta se detiene con un modal abierto;
  - la píldora roja y la ámbar;
  - el modal para cada confirmación;
  - el indicador de puerta en sus 3 estados, sin MouseArea y sin enviar comandos;
  - FC-10: ningún texto desborda en es ni en en.
- **Capturas**: con un harness de prueba (como `PruebaCicloEnCurso.qml`), capturas a 800 × 1280 de cada estado de los mockups, guardadas en `docs/informes/tanda21/capturas/` para que Cristian las compare.
