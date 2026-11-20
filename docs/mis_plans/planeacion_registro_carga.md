# Planeación: registro de la carga con lector de código de barras (RCB)

Fecha: 19-nov-2026. Estado: decisiones de Cristian del 19-nov (respuestas 1 a 14). Lo que no se decidió y se tomó por criterio propio va marcado `DECISIÓN SIN CONFIRMAR`.

Origen: pedido de un cliente, comprometido por la empresa. El equipo debe registrar qué carga se esterilizó en cada ciclo (lote y elementos) leyéndola con un lector de código de barras, imprimirla en la tirilla según la configuración del programa y guardarla en la base de datos para el informe y el reporte.

Alcance: trazabilidad de la carga. No toca el control del ciclo, ni las fases, ni las salidas, ni la seguridad de la cámara. El software sigue siendo clase C, así que lleva requisitos, riesgos, pruebas y migración de esquema como cualquier cambio.

## 1. Decisiones de Cristian (19-nov)

- RCB-D1: lector USB elegido por Especifika.
- RCB-D2: se conecta a la pantalla del lado de carga (puerta 1).
- RCB-D3: catálogo código → nombre en el equipo (opción A), sujeto a confirmación del cliente. Un código fuera del catálogo se guarda como texto crudo, marcado «sin catálogo».
- RCB-D4: el catálogo lo mantienen el ingeniero y el admin desde Opciones, con alta manual (leyendo el código con el lector) y carga desde CSV en USB.
- RCB-D5: la cantidad de un elemento es el número de veces que se lee su código.
- RCB-D6: el lote tiene su propio código de barras y se lee con el lector. El equipo no genera el número de lote.
- RCB-D7: la carga se registra en Preciclo antes de INICIAR y queda cerrada al iniciar.
- RCB-D8: el registro es obligatorio u opcional según el programa.
- RCB-D9: si el ciclo falla o se cancela, la carga queda ligada a ese ciclo con su resultado y la tirilla y el reporte dicen que no está estéril. La carga no pasa sola al ciclo siguiente.
- RCB-D10: por programa se elige qué se imprime: nada, solo el lote, o el lote y los elementos. La base guarda siempre todo.
- RCB-D11: la tirilla imprime hasta un máximo de elementos y luego «y N más (ver reporte)». El PDF y el correo llevan siempre la lista completa.
- RCB-D12: aparece en el PDF, el correo, el historial y el detalle del ciclo, y hay búsqueda inversa en Historial por lote o por código.
- RCB-D13: sin exportación a sistemas del hospital por ahora.
- RCB-D14: va en una sola tanda.

## 2. Hardware y captura (RCB-01)

- RCB-01.1: lector USB en modo teclado (HID), con sufijo Enter. Sin driver ni librería nueva, sin SOUP nuevo.
- RCB-01.2: la lectura solo se acepta con la ventana «Carga del ciclo» abierta en la pantalla de carga. Mientras está abierta, un campo de captura invisible conserva el foco; cada Enter cierra una lectura. Fuera de esa ventana el software no interpreta lecturas del lector. Si el foco cae en otro campo de texto, el código se escribe ahí como si fuera teclado: es el riesgo HAZ-RCB-03.
- RCB-01.3: validación de la lectura en la UI y otra vez en el backend: se quitan los espacios de los extremos; de 1 a 64 caracteres ASCII imprimibles (0x20–0x7E); sin el carácter `|`. Una lectura inválida se rechaza con un aviso y no se agrega nada.
- RCB-01.4: entrada manual de respaldo para etiquetas dañadas, con el teclado en pantalla (`abrirAlfanumericoAccion`), sujeta a la misma validación. Queda marcada como «manual» en la base. `DECISIÓN SIN CONFIRMAR`.
- RCB-01.5 (pendiente de hardware, no de código): el lector debe configurarse con la distribución de teclado de la estación (español Latinoamérica) o usar códigos solo alfanuméricos. Con un lector en US y Windows en español, símbolos como `-`, `/` o `_` llegan cambiados. Va en el banco (RCB-B2).
- RCB-01.6: equipos de dos puertas: el botón «Carga» solo aparece en la ventana de la puerta 1. En equipos de una puerta aparece en su única pantalla. `DECISIÓN SIN CONFIRMAR`: la puerta 1 es la de carga.

## 3. Lote y elementos (RCB-02)

- RCB-02.1: la ventana trabaja en dos pasos. Paso 1, «Lea el código del lote»: la primera lectura válida que no esté en el catálogo es el lote. Si la lectura está en el catálogo activo, se rechaza con el aviso «Ese código es un elemento; lea primero el lote». Paso 2, «Lea los elementos»: toda lectura es un elemento.
- RCB-02.2: un lote por ciclo. «Cambiar lote» lo borra y vuelve al paso 1 sin borrar los elementos.
- RCB-02.3: cada lectura de un elemento suma 1 a la cantidad de su código (RCB-D5). La lista muestra cantidad, nombre (o el código con la marca «sin catálogo») y el código. Cada fila tiene un botón «−1»; con cantidad 1 la fila desaparece. «Vaciar» limpia todo, con confirmación.
- RCB-02.4: máximo 200 códigos distintos y 999 de cantidad por código; pasado el límite, la lectura se rechaza con aviso. `DECISIÓN SIN CONFIRMAR`.
- RCB-02.5: el borrador vive solo en la UI de la pantalla de carga. Se limpia al iniciar el ciclo con éxito, con «Vaciar» y al entrar en standby. No se guarda en disco antes del inicio. `DECISIÓN SIN CONFIRMAR`.
- RCB-02.6: el nombre del catálogo se copia a la carga del ciclo al iniciar. Si después se edita o se da de baja el elemento del catálogo, la historia no cambia (HAZ-RCB-04).

## 4. Configuración por programa (RCB-03)

Dos parámetros nuevos en `parameters.globals` de los 6 programas de fábrica y de usuario, con rótulos y ayuda es/en, visibles en Opciones › Parámetros del ciclo:

- `registro_carga_obligatorio`: bool. Defecto false en todos (RCB-D8).
- `impresion_carga`: enum `ninguna` | `lote` | `lote_elementos` (RCB-D10). Defecto `lote_elementos`, salvo en Bowie & Dick (`bowe_dick.json`), donde es `ninguna`. `DECISIÓN SIN CONFIRMAR`.

Migración al cargar, igual que las anteriores: agrega los faltantes con sus defectos, deja una fila de auditoría `param_ciclo_cambio` con origen «registro de carga (RCB)», crea `.bak`, es idempotente y no emite SIS-06.

## 5. Inicio del ciclo con la carga (RCB-04)

- RCB-04.1: la carga viaja en el mismo `POST /cycle/start`, como campo opcional `carga: {"lote": str, "elementos": [{"codigo": str, "cantidad": int, "manual": bool}]}`. No hay una ruta aparte para la carga: así es imposible que la carga quede en un ciclo distinto del que se inició (HAZ-RCB-01).
- RCB-04.2: el backend valida todo otra vez (formato RCB-01.3, límites RCB-02.4, elementos con lote). Si algo falla, responde 422 `carga_invalida`. Si el programa tiene `registro_carga_obligatorio` y falta el lote o no hay al menos un elemento, responde 409 `carga_requerida`. Las dos validaciones se hacen dentro de `bloqueo_maquina()`, junto a `_validar_inicio`, antes de `START_CICLO`, y en todos los casos fallan cerradas (sin ciclo).
- RCB-04.3: sigue el mismo camino que el operador de T30-01 (`rutas/ciclo.py`, `estado.operador_inicio`). Bajo el mismo lock, el backend resuelve los nombres contra el catálogo activo y deja la carga ya resuelta en `estado.carga_inicio`, junto con `impresion_carga` del programa. `CycleLogger` la escribe en `crear_ciclo`, en la misma transacción que la fila del ciclo, y en el respaldo y el ticket. Si la base falla, rige el comportamiento que ya existe para todo el ciclo: el ciclo sigue, y la carga queda en el respaldo y el ticket y se restaura al reimportar. `estado.carga_inicio` se limpia donde se limpia `operador_inicio`.
- RCB-04.4: el respaldo del ciclo (archivo de respaldo de `CycleLogger`) lleva la carga en el registro de inicio, para que la reimportación la restaure.
- RCB-04.5: sin carga y con el programa en opcional, el ciclo arranca como hoy y no se imprime nada de carga.
- RCB-04.6: la bitácora del inicio de ciclo agrega `lote` y `n_elementos` al detalle. No va la lista completa.
- RCB-04.7: la carga no se puede modificar después del inicio, ni por API ni por UI.

## 6. Base de datos (RCB-05)

Migración v15 (`db_manager._migracion_v15`), aditiva e idempotente:

- `catalogo_carga(id INTEGER PK, codigo TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1, creado TEXT, modificado TEXT, modificado_por TEXT)`. La baja es lógica: un código dado de baja no se reutiliza para otro nombre; si se vuelve a dar de alta, se reactiva con su nombre nuevo.
- `ciclos.lote_carga TEXT` (NULL si el ciclo no tiene carga).
- `ciclo_carga(id INTEGER PK, ciclo_id INTEGER NOT NULL REFERENCES ciclos(id), codigo TEXT NOT NULL, nombre TEXT, en_catalogo INTEGER NOT NULL, cantidad INTEGER NOT NULL, manual INTEGER NOT NULL DEFAULT 0, orden INTEGER NOT NULL)`, con índices por `ciclo_id` y por `codigo`. `nombre` es la copia del catálogo al iniciar; NULL si el código no estaba en el catálogo.
- Índice en `ciclos(lote_carga)`.

## 7. Tirilla (RCB-06)

- RCB-06.1: bloque «CARGA» en la cabecera del ticket, después de la línea «Unidades» y antes de las columnas de lecturas, según `impresion_carga` (el operador va en el pie, así que la carga no puede ir junto a él). Con `ninguna` no se imprime nada. Con `lote` se imprime «Lote: X». Con `lote_elementos` se imprime el lote y luego una línea por elemento, «Nx nombre» o «Nx código (sin catálogo)», partida al ancho del ticket (`ANCHO_TICKET` = 24) con el mismo criterio de partir líneas que ya usa `ticket_formatter`, sin recortar. El código de un elemento con catálogo no se imprime en la tirilla, por el ancho; sí va en el PDF. `DECISIÓN SIN CONFIRMAR`.
- RCB-06.2: máximo 15 elementos (`MAX_ELEMENTOS_CARGA_TICKET`); si hay más, una línea «… y N más (ver reporte)». `DECISIÓN SIN CONFIRMAR` (el plan del chat decía 20 líneas; con 24 columnas un nombre suele ocupar 2).
- RCB-06.3: el pie del ticket de un ciclo que no termina en COMPLETADO (FALLO, CANCELADO o interrumpido) y que tiene carga lleva la línea «CARGA NO ESTÉRIL» (RCB-D9), en todos los modos de impresión salvo `ninguna`. `DECISIÓN SIN CONFIRMAR`: con `ninguna` tampoco se imprime.
- RCB-06.4: la reimpresión respeta la configuración vigente del ciclo al iniciar, no la actual. Para eso `impresion_carga` se guarda con el ciclo (columna `ciclos.impresion_carga TEXT` en la misma migración v15).

## 8. Informe y reporte (RCB-07)

- RCB-07.1: el PDF y el correo del ciclo llevan una sección «Carga» con el lote y la lista completa (cantidad, nombre, código, marcas «sin catálogo» y «manual»), sin importar `impresion_carga`. Si el ciclo no terminó en COMPLETADO, la sección incluye el aviso «Carga no estéril».
- RCB-07.2: el detalle del ciclo en Historial muestra lo mismo.
- RCB-07.3: búsqueda inversa en Historial: campo «Lote o código» (teclado en pantalla o lector, si la ventana de Historial está en la pantalla de carga; si no, solo teclado). Devuelve los ciclos cuyo `lote_carga` es igual al texto o que tienen ese `codigo` en `ciclo_carga`, en coincidencia exacta y sin distinguir mayúsculas. Ruta `GET /cycle/history?carga=<texto>`, mismo rol que la consulta de historial actual.
- RCB-07.4: el dashboard de Reportes no cambia en esta tanda. `DECISIÓN SIN CONFIRMAR`.

## 9. Catálogo (RCB-08)

- RCB-08.1: pantalla Opciones › Catálogo de carga, para ingeniero y admin. Lista con búsqueda; acciones Alta, Editar nombre, Dar de baja / Reactivar e Importar CSV.
- RCB-08.2: Alta: el código se lee con el lector (si la pantalla es la de carga) o se escribe con el teclado; el nombre, con el teclado. Nombre de 1 a 60 caracteres, sin control ni `|`. El código sigue la misma regla que RCB-01.3.
- RCB-08.3: Importar CSV desde USB (mismo descubrimiento de unidades que `rutas/respaldo.py`): UTF-8 (también con BOM), separador `;` o `,` detectado por el encabezado `codigo;nombre`. Antes de aplicar se muestra una vista previa: altas, cambios de nombre y líneas rechazadas con su motivo. Se aplica todo junto o nada. Un código ya existente cambia de nombre y se reactiva. Tope: 5000 filas.
- RCB-08.4: rutas `GET /carga/catalogo` (sin rol, solo lectura; la usa Preciclo para mostrar nombres en vivo), y `POST`, `PATCH`, `POST /carga/catalogo/importar` y `GET /carga/catalogo/usb` con rol ingeniero o admin.
- RCB-08.5: bitácora, categoría configuración: `catalogo_carga_alta`, `catalogo_carga_editado` (nombre anterior y nuevo), `catalogo_carga_baja`, `catalogo_carga_reactivado` y `catalogo_carga_importado` (con conteos, sin la lista).
- RCB-08.6: el respaldo y la restauración por USB del equipo incluyen el catálogo, porque va en la base.

## 10. Pantalla de Preciclo (RCB-09)

- RCB-09.1: botón «Carga» en la fila inferior del panel, entre el botón de la puerta y el deslizador INICIAR, solo en la pantalla de carga. Muestra el resumen: «Carga: sin registrar» o «Lote X · N elementos». Si el programa la exige y falta, el botón se marca en ámbar y el deslizador INICIAR muestra el motivo.
- RCB-09.2: la ventana «Carga del ciclo» (`Componentes/VentanaCarga.qml`) es un modal a pantalla completa con el indicador del paso, el lote, la lista, los botones «Escribir código», «Cambiar lote», «Vaciar» y «Listo», y un aviso breve de la última lectura (aceptada o rechazada). Los textos y la lógica van en un módulo de dominio (`ui_qml/domain/registro_carga.py`) y su puente; el QML solo dibuja, como en las pantallas anteriores.
- RCB-09.3: el inicio (`comandos_ciclo`) envía la carga del borrador en el cuerpo de `/cycle/start`. Si la respuesta es 409 `carga_requerida` o 422 `carga_invalida`, la pantalla muestra un texto propio (es/en) y no limpia el borrador.
- RCB-09.4: con el modo prueba activo no se inicia ciclo (ya rige), y el botón «Carga» sigue disponible.
- RCB-09.5: tema claro y oscuro solo con colores de `Tema/Colores.qml`, sin `elide` y con los textos largos que bajan de tamaño (regla D8-5.4). Todos los textos en es y en.

## 11. Riesgos (para `docs/riesgos/registro_riesgos.md`)

- HAZ-RCB-01 (MEDIA): la carga queda registrada en un ciclo distinto del que la esterilizó. Control: va en el mismo `/cycle/start` y en la misma transacción (RCB-04.1/04.3); el borrador se limpia al iniciar.
- HAZ-RCB-02 (ALTA): la carga de un ciclo fallido, cancelado o interrumpido se toma como estéril. Control: «CARGA NO ESTÉRIL» en la tirilla, el PDF, el correo y el historial (RCB-06.3, RCB-07.1); el resultado del ciclo sigue mandando.
- HAZ-RCB-03 (MEDIA): el lector escribe en otro campo de texto (por ejemplo una contraseña o un parámetro) si el foco no está en la ventana de carga. Control: la captura solo existe en la ventana; los campos de parámetros piden Confirmar. Residual: aceptación de Cristian pendiente; prueba de banco RCB-B3.
- HAZ-RCB-04 (BAJA): editar el catálogo cambia lo que dice la historia. Control: copia del nombre al iniciar (RCB-02.6).
- HAZ-RCB-05 (BAJA): una lectura mal decodificada por la distribución del teclado registra un código distinto. Control: configuración del lector (RCB-01.5) y la marca «sin catálogo», que lo hace visible.

Trazabilidad: REQ-107 a REQ-115, uno por RCB-01 a RCB-09.

## 12. Pruebas

- Unidad: validación de lecturas y límites; los dos pasos lote/elementos; suma por lectura y «−1»; resolución de nombres y copia del nombre; parámetros y migración del programa (idempotente, auditoría, `.bak`); migración v15 sobre una base v14 con datos; `/cycle/start` con y sin carga, obligatorio u opcional, inválida (sin ciclo creado); la carga llega a la fila del ciclo de ese inicio y no a otro (dos inicios seguidos); respaldo y reimportación con carga.
- Ticket: los tres modos de impresión, partición a 24 columnas sin recorte, límite de 15 con «y N más», «CARGA NO ESTÉRIL» en FALLO, CANCELADO e interrumpido, y reimpresión con el modo guardado del ciclo.
- PDF, correo y detalle: lista completa y aviso de no estéril.
- Historial: búsqueda por lote y por código, en coincidencia exacta y sin distinguir mayúsculas.
- Catálogo: alta, edición, baja, reactivación, roles, bitácora, CSV válido, mixto (vista previa con rechazos) y todo o nada.
- QML: carga de `VentanaCarga.qml` y de la pantalla del catálogo sin errores; el botón «Carga» solo en la pantalla de carga; captura con Enter simulada por eventos de teclado; textos es/en; prueba de tema sin literales.
- Arquitectura: siguen en verde `test_arquitectura_capas.py` y `test_t15_rutas_equivalentes.py` (con la base regenerada, porque hay rutas nuevas).

Banco (bloque RCB en la hoja de pruebas):
- RCB-B1: lector real, lectura de lote y elementos.
- RCB-B2: símbolos `-`, `/`, `_` con la distribución de la estación.
- RCB-B3: lector con el foco en otra pantalla o campo.
- RCB-B4: tirilla real con 20 elementos.
- RCB-B5: CSV desde USB real.
- RCB-B6: ciclo fallido con carga.

## 13. Mockups

`docs/diseno/mockups/registro_carga/`: `rcb_pantallas.png` (Preciclo, ventana de carga y catálogo, tema claro, 1080 × 1920) y `pdf_ciclo_con_carga.pdf` (generado con `pdf_ciclo.py` y `format_ticket` reales sobre un ciclo sintético, con la sección «Carga del ciclo» y el bloque de la tirilla agregados). Son referencia visual; la implementación sigue esta especificación.

## 14. Pendiente de Cristian

- Confirmar con el cliente la opción A (catálogo), el formato de sus etiquetas (1D/2D, si traen símbolos) y si su lote ya tiene código de barras.
- Elegir el lector (USB HID, sufijo Enter, distribución configurable; un lector 2D lee también los 1D).
- Revisar las `DECISIÓN SIN CONFIRMAR` del informe de la tanda.
