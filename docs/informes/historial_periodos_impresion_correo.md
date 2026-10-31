# Historial: elegir periodo, abrir ciclos, imprimir y enviar por correo

Fecha: 2026-10-06. Rama: `dev`, sin commit (espera tu revisión).

Diseño aprobado en el chat el 2026-10-06, con el PDF **con gráfica**. Reportes quedó para después, como pediste.

## 1. Qué cambió en la ventana Historial

- **Periodo de calendario.** Diario = un día. Semanal = de lunes a domingo. Mensual = del día 1 al último día. Antes eran 7 y 30 días hacia atrás.
- **Flechas.** Debajo de Diario / Semanal / Mensual aparece el periodo con flechas: `<  Septiembre 2026  >`. La flecha izquierda va al periodo anterior y la derecha al siguiente.
  - La flecha derecha se apaga en el periodo actual, para no avanzar al futuro.
  - Al cambiar entre Diario, Semanal y Mensual se vuelve al periodo actual.
- **Rótulos.** Diario: "Martes 6 oct 2026". Semanal: "28 sep – 4 oct 2026" (con los dos años si la semana cruza de año). Mensual: "Octubre 2026".
- **Abrir un ciclo.** Al tocar una fila se abre "CICLO N" con sus datos y su gráfica, igual que en Ciclos hoy. Tiene un botón "Volver al listado".
- **Marcar ciclos.** Cada fila lleva una casilla a la izquierda y el encabezado tiene una para marcar todas. Tocar la casilla marca la fila; tocar el resto de la fila la abre. Al cambiar de periodo los ciclos se desmarcan.
- **Barra de acciones.** Abajo se muestran "N seleccionados", **ENVIAR POR CORREO** e **IMPRIMIR**. Los botones se activan cuando hay al menos un ciclo marcado y no hay otra acción en curso.
- **Vista de un ciclo.** Tiene los mismos dos botones, pero solo para ese ciclo.
- **Avisos.** Mientras trabaja se muestra "Imprimiendo…" o "Enviando…". Al terminar se muestra el resultado: verde si salió bien, rojo si hubo error. Tocar el aviso lo cierra.

## 2. Imprimir

- La UI envía `POST /cycle/history/print` con `{"ids": [...]}`. El backend pone cada ticket en la **misma cola de la impresora térmica** que se usa durante el ciclo, en el orden pedido y con el formato de siempre (`format_ticket`).
- **Durante un ciclo se rechaza** (409) y la UI muestra "No se puede imprimir mientras hay un ciclo en curso". Esto evita que una reimpresión quede intercalada en el ticket en vivo, que se imprime línea por línea.
- Si alguno de los ciclos no existe (404), no se imprime ninguno.

## 3. Enviar por correo

- Al tocar Enviar se abre la elección de destino:
  - **Administrativo**: ventasmantenimiento.especifika@gmail.com
  - **Mantenimiento**: ingenieria.ccubides@gmail.com
  - **Otro correo…**: abre el teclado alfanumérico.
  - Cancelar.
- Se genera un **PDF A4 por ciclo** con lo siguiente:
  - Título y datos del ciclo: inicio, fin y resultado (con el detalle, por ejemplo "Fallo (FALLO_SECADO)").
  - La **gráfica**: temperatura de cámara y de referencia en °C a la izquierda, presión en kPa a la derecha, y las divisiones y nombres de las fases. Usa los colores de la gráfica de la pantalla.
  - El **ticket**, el mismo texto de la impresora térmica, en columnas de ancho fijo. Si no cabe, sigue en más páginas.
- Si es un solo ciclo, se adjunta el PDF. Si son varios, van en `ciclos_autoclave.zip`.
- El correo se envía por SMTP con STARTTLS, igual que en PySide.
- Errores que se distinguen:
  - correo no válido;
  - correo no configurado;
  - sin conexión con el equipo;
  - remitente o contraseña rechazados;
  - sin internet.

### Configuración provisional del correo (hasta la pantalla de Configuración)

- **Archivo `src/autoclave/config/correo.json`.** Contiene el remitente, el servidor SMTP, el puerto y los destinos por defecto. Se edita a mano y se relee cada vez que se abre Historial.
- **Contraseña de aplicación del remitente.** **No** va en el archivo: se guarda en el almacén de credenciales de Windows, en la misma entrada que usaba PySide. Para guardarla:

  ```
  python -m autoclave.ui_qml.exportacion.config_correo
  ```
- **Hoy `remitente` está vacío**, así que el botón dice "Correo no configurado". Para probar el envío real:
  1. Escribe el remitente en el archivo (por ejemplo, una cuenta de Gmail con verificación en dos pasos).
  2. Guarda su contraseña de aplicación con el comando de arriba.
- El código tiene un `TODO(configuracion)` que apunta a la futura pantalla.

## 4. Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/utils/periodos.py` | nuevo | Rango del día, la semana o el mes de calendario; navegación sin pasar del periodo actual. Lo usan el backend y la UI. |
| `src/autoclave/backend/server.py` | compartido | `/cycle/list` acepta `fecha` y devuelve `desde`/`hasta`; nuevo `POST /cycle/history/print`; arreglo en `/ticket.txt` (ver §6). |
| `src/autoclave/services/domain/logging/db_manager.py` | compartido | `get_ciclos_desde(..., hasta=)` con tope exclusivo. |
| `src/autoclave/ui_qml/bridge/ciclos_historial.py` | modificado | `consultarHistorial`, `moverPeriodo`, `rotuloPeriodo`, `esPeriodoActual`, ciclos marcados. |
| `src/autoclave/ui_qml/bridge/acciones_ciclos.py` | nuevo | Puente `AccionesCiclos`: imprimir y enviar, en un hilo, una acción a la vez. |
| `src/autoclave/ui_qml/exportacion/` | nuevo | `config_correo.py`, `pdf_ciclo.py` (QPdfWriter) y `correo.py` (SMTP). |
| `src/autoclave/config/correo.json` | nuevo | Configuración provisional del correo. |
| `src/autoclave/ui_qml/domain/resumen_sistema.py` | modificado | `rotulo_periodo`. |
| `src/autoclave/ui_qml/qml/Componentes/ListaCiclos.qml` | modificado | Columna de casillas opcional (`marcable`); Ciclos hoy no cambia. |
| `src/autoclave/ui_qml/qml/Pantallas/MenuPrincipal.qml` | modificado | La ventana Historial completa (§1). |
| `Main.qml`, `app.py` | modificados | Crean y pasan `acciones` y el teclado al menú. |
| `Pruebas/PruebaMenuPrincipal.qml`, `prueba_menu_principal.py`, `historial_ejemplo.py` | arnés | El arnés usa los puentes reales sobre un backend simulado que no imprime ni envía nada. Con `--backend` todo es real. |
| `assets/textos/es.json` | compartido | Claves nuevas en `menu` y una sección nueva, `exportacion`. |

## 5. Pruebas

- `tests/test_periodos_calendario.py` (nuevo): rangos, cambio de año y flechas sin pasar del periodo actual.
- `tests/test_backend_cycle_summary.py` (pruebas agregadas): rango de calendario, tope `hasta`, listado de un mes anterior, fecha inválida (422), impresión en orden, rechazo durante un ciclo (409), ciclo inexistente (404), lista vacía (422) y `/ticket.txt` con lecturas.
- `tests/test_ciclos_historial_puente.py` (pruebas agregadas): periodo con fecha, flechas, rótulos y marcado de ciclos.
- `tests/test_config_correo.py`, `tests/test_correo_ciclos.py`, `tests/test_acciones_ciclos_puente.py` (nuevos): configuración, ZIP/PDF, SMTP y los mensajes de cada error.
- `tests/test_pdf_ciclo.py` (nuevo, en subproceso): PDF de una página, ticket largo en varias páginas y PDF sin gráfica.
- `tests/test_menu_principal_pantalla_qml.py`: la prueba del historial "solo listado" se reemplazó por tres pruebas nuevas (flechas, marcar/imprimir/enviar y abrir un ciclo con sus acciones). Sigue sin avisos del motor QML.

Suite completa (`python -m pytest`, 2026-10-06): **1721 passed**, 0 fallos.

Durante la corrida apareció una caída nativa de Qt (0xC0000409): `test_acciones_ciclos_puente.py` corre antes que las pruebas de vistas PySide y creaba un `QCoreApplication`, sobre el que esas pruebas intentaban crear widgets. Se corrigió creando un `QApplication` en esa prueba.

## 6. Hallazgos y pendientes

- **Arreglo de paso:** `GET /cycle/history/{id}/ticket.txt` fallaba siempre que el ciclo tenía lecturas. `format_ticket` usa `.get()` y recibía filas `sqlite3.Row`. Ahora recibe diccionarios, y quedó una prueba que lo cubre.
- **Pendiente:** el remitente del correo (§3) y la pantalla de Configuración que reemplace a `correo.json`.
- **Pendiente:** Reportes, para cuando lo retomemos.
- **Decisión tomada:** al cambiar entre Diario, Semanal y Mensual se vuelve al periodo actual, en vez de conservar la fecha que se estaba viendo. Si prefieres conservarla, es un cambio pequeño en `consultarHistorial`.
- **Para revisar en pantalla:** las casillas, las flechas, la barra de acciones, los avisos y la elección de destino son diseño provisional, sin diseño del diseñador.
- **Visto en el PDF:** en una prueba sin pantalla (`offscreen`) Qt no tiene fuente de ancho fijo y el ticket sale en Montserrat. Con la plataforma real de Windows sale en letra de ancho fijo y alineado (comprobado a mano).

## 7. Aviso de impresora no lista (2026-10-06, a pedido tuyo)

- **Problema.** Windows acepta un trabajo de impresión aunque la impresora térmica esté desconectada y lo deja en su cola, por lo que la UI decía "Se enviaron N ciclo(s) a la impresora". En este equipo la impresora aparecía con el atributo "trabajar sin conexión" (`WORK_OFFLINE`) y con 4 trabajos en cola: las reimpresiones de la prueba. **Esos trabajos se imprimirán solos cuando se conecte**, salvo que se borren de la cola de Windows.
- **Solución.**
  1. `win32_printer.estado_impresora()` consulta a Windows el estado y los atributos de `Impresora_Termica`. Devuelve uno de estos valores:
     - `lista`;
     - `no_instalada`;
     - `desconectada` (atributo sin conexión, o estado sin conexión / no disponible);
     - `sin_papel`;
     - `error` (en pausa, error, atasco, intervención del usuario o tapa abierta).
  2. `RealtimePrinter.estado()` la expone. `POST /cycle/history/print` responde **503** con `{"impresora": estado}` y **no encola nada** si la impresora no está lista.
  3. La UI muestra en rojo uno de estos avisos:
     - "La impresora no está conectada"
     - "La impresora no tiene papel"
     - "La impresora no está instalada"
     - "La impresora reporta un error"
- **Límite.** Solo detecta lo que el controlador informa a Windows. "Desconectada" está comprobado en este equipo; "sin papel" depende del controlador de la térmica.
- **Sin cambios.** La impresión en tiempo real del ciclo sigue encolando sin consultar el estado.
- **Arnés.** El backend de ejemplo consulta el **estado real** de la impresora, aunque sigue sin imprimir nada.
- **Pruebas.** Estados de Windows simulados (`tests/test_win32_printer.py`, +11), 503 sin encolar (`test_backend_cycle_summary.py`, +4) y mensajes del puente (`test_acciones_ciclos_puente.py`, +5).
- **Suite completa:** **1741 passed**, 0 fallos.
