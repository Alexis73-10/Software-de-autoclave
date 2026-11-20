# Informe de la tanda registro_carga (RCB): registro de la carga con lector de código de barras

Fecha: 19-nov-2026. Rama `registro-carga` desde `dev` (75189880, 1.0.0-beta.4). Especificación: `docs/mis_plans/planeacion_registro_carga.md` (decisiones de Cristian del 19-nov). Entrega **no compilada**.

## 1. Resumen

El equipo registra la carga de cada ciclo (lote y elementos) leída con un lector USB en modo teclado, la guarda con el ciclo (misma transacción), la imprime en la tirilla según el programa, la muestra completa en el PDF, el correo y el detalle del Historial, y permite buscar los ciclos de un lote o de un código. El catálogo código → nombre lo mantienen el ingeniero y el admin desde Opciones (alta, edición, baja/reactivación e importación CSV desde USB). No se tocó el control del ciclo, las fases, las salidas ni la seguridad de la cámara.

## 2. Cambios por requisito

### RCB-01 Hardware y captura (REQ-107)
- Reglas de lectura puras en `core/runtime/registro_carga.py` (`validar_codigo`: espacios de los extremos fuera, 1 a 64 ASCII 0x20–0x7E, sin `|`), usadas por la UI y por el backend.
- `Componentes/VentanaCarga.qml`: un `TextInput` invisible (`capturaLector`) conserva el foco mientras la ventana está abierta (lo recupera al perderlo, al cerrarse el teclado en pantalla y tras los diálogos); cada Enter entrega el texto a `RegistroCarga.leer`. Fuera de la ventana no hay captura.
- Entrada manual con «Escribir código» (`abrirAlfanumericoAccion`, regla de la tanda 22), marcada `manual`.

### RCB-02 Lote y elementos (REQ-108)
- `ui_qml/domain/registro_carga.BorradorCarga` (puro): paso 1 lote (un código del catálogo activo se rechaza con «Ese código es un elemento; lea primero el lote»), paso 2 elementos; cada lectura suma 1; «−1» (con 1 la fila desaparece); «Cambiar lote» conserva los elementos; «Vaciar» con confirmación (`ModalConfirmacion`); límites 200 códigos y 999 por código.
- Puente `ui_qml/bridge/registro_carga_qml.RegistroCarga`: lee el catálogo activo al abrir la ventana (`GET /carga/catalogo?activos=true`, fuera del hilo de la GUI) y publica paso, lote, filas, totales, resumen, aviso y `requerida`.
- El borrador vive solo en memoria y se limpia al aceptarse el inicio (`ComandoIniciarCiclo`), con «Vaciar» y al entrar en standby (`app.py` conecta `Standby.activoChanged`).
- El nombre del catálogo se copia a `ciclo_carga.nombre` al iniciar (HAZ-RCB-04).

### RCB-03 Configuración por programa (REQ-109)
- `globals.registro_carga_obligatorio` (bool, false) e `impresion_carga` (enum `ninguna` | `lote` | `lote_elementos`; defecto `lote_elementos`, `ninguna` en Bowie & Dick) en los 12 JSON (fábrica y usuario).
- Migración al cargar `cycle_manager._agregar_claves_rcb` por el canal `agregadas`: auditoría `param_ciclo_cambio` con origen «registro de carga (RCB)», reescritura del JSON de usuario con `.bak`, idempotente, sin SIS-06. El defecto de impresión depende del `cycle_id` (`catalogo_parametros.impresion_carga_defecto`).
- Rótulos y ayuda es/en (`parametros.globals.*`, `parametros_desc.globals.*`) y opciones del enum (`opciones.valor_ninguna|lote|lote_elementos`); la pantalla de Parámetros del ciclo ya dibuja bool y enum.

### RCB-04 Inicio del ciclo con la carga (REQ-110)
- `POST /cycle/start` acepta `carga` opcional. El catálogo activo se lee antes del lock (la base no se consulta con el lock de la máquina tomado) y, bajo `bloqueo_maquina()`, después de `_validar_inicio`, `_carga_del_inicio` valida (422 `carga_invalida` con `motivo` y `campo`), exige la carga si el programa lo pide (409 `carga_requerida`) y la resuelve; ningún rechazo marca `START_CICLO`. Falla cerrada ante un error al leer el programa o validar.
- `estado.carga_inicio` se fija siempre junto con `START_CICLO` (None sin carga) y la consume `CycleLogger._on_inicio`: `crear_ciclo(carga=...)` escribe lote, modo de impresión y filas en la misma transacción que la fila del ciclo; el encabezado del respaldo la lleva y `importar_ciclo_respaldo` la restaura (revisada con las mismas reglas: un respaldo dañado importa el ciclo sin carga).
- Bitácora `ciclo_iniciado` con `lote` y `n_elementos` (suma de cantidades), sin la lista.
- Cliente: `UIServiceBackend.start_cycle(carga=...)`, `ComandoIniciarCiclo(registro_carga=...)` envía la carga del borrador en todas las variantes (con operador, sin registro); ante 409/422 publica `mensajeCargaClave` (texto en la zona de avisos de Preciclo) y no limpia el borrador. Textos es/en en `sesion_backend._CLAVES_INICIO_CICLO`.

### RCB-05 Base de datos (REQ-111)
- Migración v15 (`db_manager._migracion_v15`): `catalogo_carga` (código único, baja lógica, trigger que impide DELETE), `ciclo_carga` (+ índices por ciclo y por código), `ciclos.lote_carga` (+ índice) e `impresion_carga`. Aditiva e idempotente.

### RCB-06 Tirilla (REQ-112)
- `ticket_formatter.lineas_carga`: bloque entre separadores después de la línea de unidades y antes de las columnas, según el modo guardado con el ciclo; elementos «Nx nombre» o «Nx código (sin catálogo)» partidos por palabras a 24 columnas sin recortar (sangría bajo el nombre; una palabra más larga que la línea se parte por caracteres); tope `MAX_ELEMENTOS_CARGA_TICKET` = 15 y «... y N más (ver reporte)».
- Reimpresión (`POST /cycle/history/print`) y `GET /cycle/history/{id}/ticket` usan la carga guardada (`_con_carga`), con el modo de impresión del ciclo.
- «CARGA NO ESTÉRIL»: ver §6 (decisión 1).

### RCB-07 Informe y reporte (REQ-113)
- PDF: lote en la cabecera y sección «Carga del ciclo» (resumen con operador, tabla cantidad / elemento / código / observación con «Ingreso manual» y «Sin catálogo», nota, y aviso «CARGA NO ESTÉRIL» en rojo si el ciclo no terminó COMPLETADO); pasa de página con listas largas (`pdf_ciclo._seccion_carga`). Los textos se arman en `ui_qml/domain/registro_carga.seccion_carga`.
- Correo: además del PDF adjunto, una línea por ciclo con carga en el cuerpo y «CARGA NO ESTÉRIL» si corresponde.
- Historial: «Lote o código» (teclado en pantalla, `buscarCarga`) → `GET /cycle/history?carga=`; detalle del ciclo con resumen, aviso de no estéril y «Ver carga» (lista completa en el lugar de la gráfica).

### RCB-08 Catálogo (REQ-114)
- Rutas en `backend/rutas/carga.py` (ver §4); bitácora de configuración; importación CSV (UTF-8 con o sin BOM, `;` o `,` por el encabezado, hasta 5000 filas, 2 MB) con vista previa y aplicación de las filas válidas en una transacción, protegida por la huella del archivo de la vista previa (409 `csv_cambio`).
- Respaldo USB: `catalogo_carga.json` con la parte «parámetros y programas»; la restauración valida todo antes de escribir (422 `catalogo_carga_invalido`) y agrega, renombra y reactiva.
- Pantalla Opciones › Catálogo de carga: ver §5.

### RCB-09 Preciclo (REQ-115)
- Botón «Carga» entre la puerta y INICIAR solo en la pantalla de carga (el puente solo existe con `--door 1`), con el resumen; en ámbar si el programa la exige y falta; el deslizador dice «Registre la carga para iniciar» y, al completarse, abre la ventana en lugar de iniciar. Disponible con el modo prueba.
- Tema claro y oscuro solo con `Colores.qml`, sin `elide`, textos que bajan de tamaño (`HorizontalFit`/`Fit`), es/en.

## 3. Migraciones
- Base de datos v14 → v15 (aditiva, idempotente). Las pruebas que fijaban `ESQUEMA_VERSION == 14` se actualizaron a 15.
- Programas: dos parámetros nuevos agregados al cargar con auditoría y `.bak`, sin SIS-06.

## 4. Rutas nuevas o cambiadas
| Ruta | Rol | Nota |
|---|---|---|
| `GET /carga/catalogo[?activos=true]` | sin rol | lectura |
| `POST /carga/catalogo` | ingeniero, admin | alta (reactiva un código de baja con su nombre nuevo); 409 `codigo_existe`; 422 `validacion` |
| `PATCH /carga/catalogo/{id_}` | ingeniero, admin | nombre y/o `activo`; 404 `no_existe` |
| `GET /carga/catalogo/usb` | ingeniero, admin | CSV en la raíz de cada USB |
| `POST /carga/catalogo/importar` | ingeniero, admin | vista previa / aplicación con huella; 409 `csv_cambio`; 422 `csv_invalido` |
| `POST /cycle/start` | sin cambio | campo opcional `carga`; 409 `carga_requerida`, 422 `carga_invalida` |
| `GET /cycle/history?carga=` | sin cambio | búsqueda inversa; 422 `carga_invalida` |
| `GET /cycle/history/{id}/ticket` | sin cambio | `ciclo.carga` si la tiene |

La base de `tests/test_t15_rutas_equivalentes.py` (`docs/informes/tanda15/base/rutas.json` y `openapi.json`) se regeneró: las cinco rutas nuevas se agregaron al final de `rutas.json` sin reordenar las demás; el OpenAPI regenerado con `openapi_ordenado` solo difiere en esos paths, el parámetro `carga` y la descripción de `/cycle/history`, y los esquemas `_AltaBody`, `_ModificarBody` e `_ImportarBody`. El cambio queda anotado en la cabecera de la prueba.

## 5. Pruebas

Agregadas (99 pruebas, varias parametrizadas):
- `tests/test_rcb_migracion_v15.py` (3): v15 sobre una base v14 con datos, repetida, código único y sin borrado.
- `tests/test_rcb_parametros.py` (8): los 12 programas, migración idempotente con auditoría y `.bak`, Bowie & Dick con `ninguna`, no pisa valores, lectores, coerción del enum, rótulos es/en.
- `tests/test_rcb_catalogo.py` (12): reglas puras, CSV mixto, coma y errores, bitácora, alta/baja/reactivación, todo o nada, roles, importación, respaldo del catálogo.
- `tests/test_rcb_inicio_carga.py` (13): inicio con y sin carga, obligatoria u opcional, inválida sin ciclo, catálogo ilegible, textos es/en, dos inicios seguidos (cada carga en su ciclo), transacción, respaldo y reimportación (también dañado).
- `tests/test_rcb_tirilla_pdf.py` (16): tres modos, partición a 24 columnas sin recorte, tope de 15, «CARGA NO ESTÉRIL» en FALLO, CANCELADO e INTERRUMPIDO, reimpresión con el modo guardado, PDF (lista completa, 200 elementos con salto de página), correo.
- `tests/test_rcb_historial.py` (4): búsqueda por lote y por código, exacta y sin mayúsculas, 422 y puente.
- `tests/test_rcb_ventana_carga.py` (17): dos pasos, «−1», «Cambiar lote», «Vaciar», límites, manual, envío con el inicio, limpieza, rechazo que conserva, respuesta perdida (SAF-01), QML: botón solo en la puerta 1, captura solo con la ventana abierta y Enter simulado, sin colores literales ni `elide`.
- `tests/test_rcb_catalogo_ui.py` (26): controlador de la pantalla del catálogo, códigos por ruta, permisos, QML offscreen (carga sin avisos, lector solo en el alta).

Modificadas:
- Versión de esquema 14 → 15: `test_automatizacion_ciclos_bd`, `test_db_audit_log`, `test_i4_ingles_backend`, `test_o1_operador_ciclo`, `test_s2b_d8_2_14_avisos_ticket_bd`, `test_t30_03_usuarios`, `test_t31_entrega_ticket`.
- `test_menu_principal_pantalla_qml`: el detalle del Historial pide además `/cycle/history/{id}/ticket` (carga del ciclo).
- `test_permisos_opciones`: sección `catalogo_carga` para ingeniero y admin.
- `test_t25_codigos_rutas_async`: códigos de `/carga/catalogo`; `archivo_invalido` y `sin_cambios` declarados como compartidos con `/io/assignment` (ya eran de Reasignación).
- `test_t15_rutas_equivalentes`: base regenerada (§4).
- Sección nueva en Opciones (12 entradas para el ingeniero, `catalogo_carga` al final para el admin): `test_opciones_qml`, `test_opciones_controller`, `test_c1b_admin_parametros_equipo`, `test_hor_d_opciones_qml` (11 → 12).
- `test_i4_ingles_qml`: `<br><b>` de la nota del catálogo en la lista blanca (marcado HTML).
- `test_v8b_textos`: «Consolas» permitido como familia. Además se corrigió en `es.json` la ayuda de `brecha_segura_temperatura`, que citaba «Margen de recuperación por presión» (rótulo anterior a CRI): la prueba ya fallaba en `dev`.

Correcciones encontradas al correr la suite completa: `Connections` de Preciclo con `ignoreUnknownSignals` (avisos QML con puentes de prueba), `AccionesCiclos._campo_lote` llamado por la clase, y los `cycles/user/*.json` que la suite había reescrito (marcas `migrado_t28_m3`/`migrado_cri`) y que entraron por error en dc692670, revertidos en 13b7eee3.

**Suite completa (en serie, 20-nov):** 12715 pasan, 26 fallan, 13 errores, 11 omitidas, 15 xfail. Ninguno es de RCB:
- Fallan igual en `dev` (75189880), verificado sobre un worktree de `dev`: `test_s9_planta_simulada` (4, `arranque_sin_presion`), `test_t12_c07_c13_json::test_son_los_10_programas` y `test_q1_r1p3_rango_calentamiento::test_hay_10_perfiles` (12 programas desde Prion), `test_t29_descompresion_fin_modo_solido` (6), `test_s1_sen01_fuera_de_ciclo` (1), `test_t12_v12_ventana_referencia_en_cero` (3), `test_t17_copia_programa` (1), y los errores de `test_hor_b_textos_contraste_qml` (6) y `test_hor_c_menu_reportes_qml` (7).
- Dependen del orden porque la suite reescribe `src/autoclave/cycles/user` y deja `.bak` (también en `dev`, verificado corriendo `test_c2` antes de `test_t28`): `test_t28_a14_m3_brecha` (2) y `test_c2_programas_persistentes` (1). Pasan solas con los archivos limpios.
- Pasan solas, en esta rama y en `dev`: `test_nuevo_usuario_puente` (3), `test_p1_salida_modo_prueba` (1), `test_t21_pantalla_fin_ciclo_qml` (1), `test_t26_arq_revision` (1); fallos de tiempo dentro de la corrida larga.

La suite no queda en verde por esos fallos de `dev`, que están fuera del alcance de la tanda (varios son de control: s9, s1, t12_v12). Quedan para Cristian.

Pantalla del catálogo comparada con `rcb_3_catalogo.png` en captura offscreen: coincide en estructura; sin el ícono de lupa en el buscador.

## 6. DECISIÓN SIN CONFIRMAR
1. «CARGA NO ESTÉRIL» también con `impresion_carga = ninguna`: es la línea existente del pie (tanda 7) para todo ciclo no COMPLETADO; la especificación (RCB-06.3) pedía omitirla con `ninguna`. Se dejó la opción más segura.
2. Límites de 200 códigos distintos y 999 por código (RCB-02.4).
3. Tope de 15 elementos en la tirilla (RCB-06.2).
4. Defecto de impresión `lote_elementos`, salvo Bowie & Dick con `ninguna` (RCB-03).
5. La puerta 1 es la de carga (RCB-01.6, RCB-09).
6. Leer otra vez el lote en el paso de elementos no lo suma como elemento (aviso).
7. Entrada manual marcada «manual» (RCB-01.4).
8. Borrador solo en memoria; se limpia al aceptarse el inicio, al entrar en CICLO, con «Vaciar» y en standby (RCB-02.5).
9. El catálogo se edita en cualquier estado de la máquina, también en CICLO (el backend no lo restringe).
10. La restauración del respaldo agrega, renombra y reactiva el catálogo; no da de baja (RCB-08.6).
11. Reportes (dashboard) sin cambios (RCB-07.4).
12. Códigos del catálogo en «Consolas» (monoespaciada de Windows), como el mockup.

## 7. Hallazgos del revisor
Revisión de seguridad (un subagente) sobre HAZ-RCB-01/02/03. Confirmó que no se tocan `state_machine/`, `cycle_phases/`, el `ControlLoop` ni las salidas.
- **SAF-01 (ALTA, corregido en dc692670):** si el `POST /cycle/start` aceptado no devolvía respuesta (plazo de 0,8 s vencido o conexión cortada), la UI conservaba el borrador mientras el ciclo arrancaba con esa carga; el siguiente operador podía sumar su carga a la anterior. Ahora `RegistroCarga.seguir_estado` vacía el borrador en la transición a CICLO (`app.py` conecta `machineStateChanged`); lo leído durante el ciclo queda para el siguiente. Prueba en `test_rcb_ventana_carga.py`.
- **SAF-02 (BAJA, residual):** dos inicios en el mismo tick desde las dos pantallas: el segundo pisa `carga_inicio` (la puerta 2 la deja en None). Patrón heredado de `operador_inicio` (T30-01). Propuesta: 409 si `START_CICLO` ya está pendiente.
- **SAF-03 (BAJA, residual):** si la máquina rechaza el inicio en el tick siguiente, `carga_inicio` queda en memoria; el siguiente inicio aceptado siempre la reescribe, así que no hay fuga. Limpiarla exigiría tocar `state_machine`/`control_loop`, fuera del alcance de la tanda.
- **SAF-04 (BAJA, residual):** si falla la lectura de la carga, el PDF y el detalle del Historial omiten la sección y su aviso de no estéril; el pie del ticket (en la tirilla y en el PDF) y el resultado siguen diciendo «CARGA NO ESTÉRIL».
- **SAF-05 (BAJA, residual):** la reimportación del respaldo no revisa `nombre` ni `impresion` de la carga (solo lote, códigos y cantidades).

## 8. Pendiente de Cristian
- Las `DECISIÓN SIN CONFIRMAR` de §6, en especial la 1 y la 9.
- Los residuales SAF-02 a SAF-05.
- Banco RCB-B1..B6 (lector real, distribución del teclado, foco, tirilla con 20 elementos, CSV en USB, ciclo fallido con carga).
- Trazabilidad REQ-107..REQ-115 (estaban libres).
- Fallos de la suite que vienen de `dev` y la reescritura de `cycles/user` por la suite (§5).
- Entrega no compilada: `python tools/entrega/compilar_entrega.py`.
