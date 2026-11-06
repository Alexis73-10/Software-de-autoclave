# Tanda 28, flujo B — informe de la Parte A

## A10. El estado seguro no termina tras corregir un parámetro

**Síntoma (Cristian, 5-nov):** el estado seguro se activó con `rango_presion_atm` muy estrecho; al ampliarlo en Parámetros del equipo, con la cámara ya dentro del nuevo rango, la fila de estado seguro no se apagaba.

### Diagnóstico

Prueba de reproducción: `tests/test_t28b_a10_estado_seguro_rango.py`, con piezas reales (ControlLoop, `ProtocoloEstadoSeguro`, `ProtocoloFallo`, `ConfigManager` con base) y el cambio por la API real, `PATCH /global_params/rango_presion_atm` (el prompt dice PUT, pero esa ruta no existe). La presión atmosférica de fábrica es 75 kPa y la brecha 1 kPa. El protocolo arranca con la cámara a 78 kPa (sobrepresión) o a 72 kPa (vacío). Durante el protocolo la brecha pasa a 5 kPa.

| Candidato | Resultado | Prueba |
|---|---|---|
| (a) protocolo en pausa por el modo prueba | **Posible causa en el equipo.** Es un comportamiento correcto: en modo prueba la máquina de estados no corre y no se cuentan ticks. Pero la fila solo decía «Llevando la cámara a estado seguro». | `test_modo_prueba_muestra_la_pausa_y_termina_al_salir` |
| (b) temperatura sobre `min(temp_max_apertura` del equipo y del programa del protocolo`)` | **Posible causa en el equipo.** Correcto: no termina, pero la fila no decía por qué. | `test_temperatura_alta_no_termina_y_el_detalle_nombra_valor_y_limite`, `test_limite_de_temperatura_es_el_menor_con_el_del_programa` |
| (c) trama AI vencida o sonda sin lectura | **Posible causa.** Correcto: no termina, pero la fila no decía por qué (salvo cuando hay CIC-10 o silencio ESS). | `test_ai_vencida_no_termina_y_lo_dice`, `test_principal_sin_lectura_no_termina_y_lo_dice`, `test_sin_datos_vigentes_el_motivo_es_la_comunicacion` |
| (d) valor cacheado | **Descartado.** `ConfigManager.get` devuelve el valor nuevo justo después de `aplicar_valor`. `ProtocoloEstadoSeguro.update` llama a `camara_segura.evaluar(self.config…)` en cada tick. `ProtocoloFallo` lee `presion_admosferica`/`rango_presion_atm` en cada uso, también el bloque de `protocolo_fallo.py:700` (`_referencia_atm_configurada`). La UI recibe `camara_segura_limites` del `/status` de ese momento. Ningún atributo guarda el rango ni la atmosférica (análisis AST de `estado_seguro.py`, `protocolo_fallo.py` y `camara_segura.py`). Además, un config que cuenta las lecturas confirma que se vuelven a leer en cada tick. | `test_cambio_de_rango_durante_el_protocolo_termina_en_tres_ticks[sobrepresion/vacio]`, `test_tambien_un_cambio_de_atmosferica_rige_en_vuelo`, `test_ningun_atributo_guarda_el_rango_ni_la_atmosferica`, `test_el_protocolo_lee_la_configuracion_en_cada_tick` |
| (e) `ConfirmadorApagado` o el venteo retienen el estado | **Descartado.** El fin depende solo de 3 evaluaciones seguras seguidas, que se hacen después de `ProtocoloFallo.update()`. El venteo no participa, y `ConfirmadorApagado` no interviene en el estado seguro (solo en PREPARACION/PREPARADO). | `test_venteo_del_protocolo_no_retiene_el_estado_seguro`, `test_estado_de_maquina_no_interviene` |
| (f) la UI lee un campo de `/status` que no se recalcula | **Descartado.** `/status.estado_seguro.activo` se calcula en cada petición a partir de `estado_seguro.activo`. El puente (`UiBridge._seguridad_de`) lo copia en cada refresco y la fila cae en el mismo refresco. | `test_status_y_puente_dejan_de_mostrar_el_estado_seguro` |

**Causa encontrada:** con el código vigente, el protocolo **sí termina** a las 3 lecturas seguras tras ampliar el rango: no hay defecto de control. En el equipo, la causa tuvo que ser (a), (b) o (c). Las tres son correctas, pero no se veían en la pantalla:

- mientras el estado seguro está en curso, la fila «NO ABRIR» (que tiene el motivo) se oculta (`SeccionEstadoSeguro.qml`, `noAbrir` excluye `activoSinConfirmar`);
- la fila de estado seguro y su detalle solo decían la causa de origen;
- no había forma de distinguir «está esperando la temperatura» o «está en pausa por el modo prueba» de «está colgado».

**No se pudo confirmar cuál de las tres fue** sin el log del backend de ese día. Lo más probable es (a) (pruebas de banco en Entradas/Salidas) o (b) (cámara caliente tras un fallo). Para la próxima vez, el log de desarrollo registra ahora cada cambio de motivo pendiente: «Estado seguro: la cámara aún no es segura (…)».

### Corrección (solo presentación; criterio de cámara segura y 3 ticks sin cambio)

- `state_machine/estado_seguro.py`:
  - guarda el motivo de la última evaluación (`_fijar_pendiente`, el resultado del tick y no una copia de la configuración) y la publica en `motivo_pendiente`: `{codigo, valores, texto, limites}`, con los límites leídos del config en el momento de la llamada (`camara_segura.limites`);
  - agrega `en_pausa_modo_prueba`;
  - la AI vencida da el motivo `sin_presion_camara` y la falta de datos vigentes da `sin_datos_vigentes`;
  - con paro, confirmación pendiente, pausa o fin no hay motivo.
- `core/runtime/camara_segura.py`: `limites(config, temp_max_ciclo)`, solo presentación, sin ningún uso en interlocks.
- `backend/rutas/sistema.py`: `/status.estado_seguro` suma `en_pausa_modo_prueba` y `motivo_pendiente`.
- `ui_qml/bridge/ui_bridge.py`: `es_pausa_prueba`, `es_pendiente` y `contextoAviso.pausaPrueba/pendiente`; si falta el campo, no se muestra nada.
- `ui_qml/domain/detalle_aviso.py`:
  - `texto_espera()` arma «En pausa: modo prueba activo» o «Pendiente: Temperatura 92.0 °C, límite 80.0 °C» / «Pendiente: Presión …, rango seguro de … a …», en es y en, en las unidades vigentes;
  - el detalle ALD de `estado_seguro_en_curso` lo agrega a la descripción.
- `ui_qml/bridge/detalle_aviso_qml.py`: slot `textoEspera`.
- `SeccionEstadoSeguro.qml`: nota `avisoEsperaEstadoSeguro` debajo de la causa.
- i18n es/en: `sistema.estado_seguro_pausa_modo_prueba`, `sistema.estado_seguro_espera`, `aviso_detalle.estado_seguro_espera.<motivo>` (familia dinámica en `sufijos_i18n`).
- Al salir del modo prueba, el protocolo se reanuda y termina solo en 3 ticks si la cámara ya es segura. Ese comportamiento ya existía, y ahora lo fija una prueba.

### Pruebas

- Nuevas: `tests/test_t28b_a10_estado_seguro_rango.py`, 24 pruebas. Incluyen 4 de carga real de `Main.qml` (offscreen) que comprueban la nota de pausa, la del motivo con valor y límite, que no haya nota sin motivo y que el motor QML no dé avisos.
- Relacionadas, en verde: estado seguro (S9, T5, T2-P1/P6, ESS, ESS-07, T17-ESG), cámara segura (T4), protocolo de fallo, ALD (T26), `test_arquitectura_capas`, `test_i18n`, `test_tema_oscuro`, O2a, rutas/OpenAPI (T15) y todas las pruebas que nombran `SeccionEstadoSeguro`, `_estado_seguro_status`, `detalle_aviso`, `contextoAviso` o `camara_segura`. Resultado: 1090 passed, 3 skipped, 4 xfailed, más 494 passed y 4 xfailed en la tanda de estado seguro, sin fallos. No se corrió la suite completa (eso queda para el cierre del flujo).
- Banco: hoja `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`, bloque nuevo «T28 (flujo B)», prueba T28-A10-01.

### Hallazgos

- **AJ28B-01 (MEDIA, corregido):** mientras el estado seguro está en curso, la interfaz no decía qué le faltaba para terminar: «NO ABRIR» se oculta y la fila solo daba la causa de origen. Un estado seguro correctamente detenido (modo prueba, carga caliente, sensor o AI) parecía colgado y podía llevar al operador a buscar formas de «destrabarlo». Corregido con la nota y el detalle.
- **AJ28B-02 (BAJA, corregido):** el log de desarrollo no registraba por qué el estado seguro seguía activo. No se podía diagnosticar el caso del equipo a posteriori. Ahora queda una línea por cada cambio de motivo.
- **AJ28B-03 (BAJA, sin cambio, informativo):** el protocolo juzga la temperatura con `min(temp_max_apertura` del equipo y del programa del protocolo`)`. No usa el límite del programa seleccionado (cuya sonda Principal sí cuenta). «NO ABRIR» usa además el límite del último ciclo y el de la recuperación. Las dos reglas son conservadoras en su contexto y el prompt prohíbe cambiar el criterio. Queda anotado por si Cristian quiere unificarlas.
- **`DECISIÓN SIN CONFIRMAR`:** redacción de los textos nuevos: «En pausa: modo prueba activo» (pedido literal), «Pendiente: {motivo}», «Temperatura {valor}, límite {limite}», «Presión {valor}, rango seguro de {minimo} a {maximo}» y sus versiones en inglés. También la posición de la nota, debajo de la causa en la sección de emergencia.

### Evaluación normativa (puerta de entrada, NTC-IEC 62304:2019 / IEC 62304:2006)

- **Clase C:** el cambio toca la presentación del estado seguro, que es una medida de control.
- **Control y alarmas:** la lógica de control no cambia: el criterio de cámara segura, los 3 ticks, CIC-10 y NO ABRIR siguen iguales. No se introducen causas nuevas de situación peligrosa (7.4.1/7.4.2). La nota solo informa y no tiene botones (ALM-01).
- **Solicitud de cambio (8.2.1):** el punto A10 del prompt de la tanda 28 (origen: Cristian, 5-nov).
- **Verificación:** se repitieron las pruebas de unidad e integración del estado seguro, de la cámara segura y de la interfaz (5.5.5, 8.2.3). Falta la prueba de banco T28-A10-01.
- **SOUP:** sin cambios.
- **Trazabilidad:** pendiente de agregar el requisito en la matriz cuando el director una los flujos. Este punto no pedía registro de riesgos.

## A9. Arranque con la cámara no segura sin protocolo activo

**Pedido (Cristian, 5-nov):** en un encendido normal (el último ciclo terminó o no hay ciclo) con la cámara en vacío o con presión residual no se inicia el protocolo de estado seguro; PREPARACION iguala la presión con sus reglas. Tras un ciclo interrumpido se conserva el protocolo de arranque, con el origen `ciclo_interrumpido`.

> **Para el revisor: este punto toca control, actuadores y la lógica de estado seguro / NO ABRIR.** Revisión de seguridad pendiente (el implementador no puede lanzar el revisor; la debe pedir el director antes de unir).

### Cambios

- `services/domain/loop/control_loop.py`:
  - `recuperar_ciclo_interrumpido(programa, interrumpido=True)`. Por omisión `True` (falla segura: quien no sabe, obtiene el protocolo).
  - `_procesar_recuperacion`: con `interrumpido=False` y la cámara no segura, no arranca `ProtocoloEstadoSeguro`. Deja un aviso en el log y un evento `arranque_camara_no_segura` con `estado_seguro: false` (una vez por encendido). La recuperación queda pendiente hasta 3 lecturas seguras, como antes. Así el programa del último ciclo sigue contando en `programas_para_seguridad()` y `temp_max_tras_ciclo()` (NO ABRIR, bloqueo de apertura e inicio, límite de temperatura) y en el venteo de PREPARACION (`carga_liquida(programas, …)`: por la lenta en líquidos, T1/P-12).
  - Con `interrumpido=True`, el protocolo de siempre (solo la lenta, sin confirmación, D9-1.2/1.4), con `origen="ciclo_interrumpido"` y `motivo_solo_lenta` actualizado; el evento lleva `estado_seguro: true`.
- `backend/context.py`: `hubo_ciclo_interrumpido()`. Da True si `cerrar_ciclos_interrumpidos` cerró una fila o si hay marca del contador (`contador_ciclos.en_curso()`, independiente de la base). Falla segura con True en estos casos: sin base (`sin_base_de_datos`), si el cierre falló (no queda `_ciclo_interrumpido`), si nunca se consultó o ante un error. `construir_control` lo pasa como `interrumpido=`.
- Interfaz: `_CAUSAS_ESTADO_SEGURO` cambia `arranque` por `ciclo_interrumpido`. La clave i18n `sistema.estado_seguro_causa_arranque` pasa a `sistema.estado_seguro_causa_ciclo_interrumpido` (es/en). El detalle ALD (`detalle_aviso._armar`, `estado_seguro_en_curso`) y `SeccionEstadoSeguro.qml` arman la clave con la causa, así que la toman sin cambios de lógica (solo se actualizó un comentario). Una causa `arranque` recibida de un backend viejo se muestra vacía.
- Sin cambios: `camara_segura`, `ProtocoloEstadoSeguro`, `ProtocoloFallo`, PREPARACION (PRE-03/PRE-04 con su nivel), la retención de arranque (`_tick_retenido`, ARQ-04) y las protecciones del modo prueba (ESG-02). Con la recuperación pendiente, `salidas_prueba_bloqueadas` mantiene el bloqueo del protocolo sin lectura vigente de presión, igual que antes (es lo conservador).

### Lo que dependía del origen «arranque»

| Lugar | Ajuste |
|---|---|
| `sistema.estado_seguro_causa_arranque` (es/en) | Reemplazada por `…_ciclo_interrumpido` |
| `ui_bridge._CAUSAS_ESTADO_SEGURO` y la familia i18n dinámica de `test_i18n` | `ciclo_interrumpido` |
| Bitácora | `estado_seguro_iniciado` lleva `origen: ciclo_interrumpido`. `arranque_camara_no_segura` se conserva en los dos casos con `estado_seguro` true/false. Las filas viejas no cambian. |
| ARQ-04 (tanda 26) | Sin cambio: la recuperación se procesa en el primer tick liberado. Prueba nueva: ninguna salida antes de liberar, en los dos casos. |
| ESS / ESG-01/02, modo prueba | Solo aplican con el protocolo activo (caso interrumpido), sin cambio. |
| Pruebas S9, T6, ESS-07, ESS, T17-ESG, U10b, S9-QML, `cap9_capturas_banco.py` | Llaman a `recuperar_ciclo_interrumpido(programa)` (caso interrumpido): solo cambia la causa esperada (`arranque` → `ciclo_interrumpido`) y el texto. No se relajó ninguna aserción. |

### Pruebas

- Nuevas: `tests/test_t28b_a9_arranque_sin_protocolo.py` (16), con el ControlLoop real y la planta simulada de S9:
  - arranque normal con vacío: sin protocolo, PREPARACION abre `aire_admosferico_camara`, la cámara llega a segura, NO ABRIR mientras no lo es, nunca LISTO con la cámara no segura, nunca aire con presión, un solo aviso en la bitácora;
  - arranque normal con sobrepresión y programa sólido: venteo de PREPARACION (rápida), sin protocolo;
  - arranque normal con el último programa de líquidos: solo la lenta;
  - ciclo interrumpido de líquidos: protocolo con causa `ciclo_interrumpido`, solo la lenta mientras manda el protocolo, evento con `origen`;
  - por omisión, interrumpido;
  - ninguna salida y NO ABRIR antes de la liberación (los dos casos);
  - contexto: sin base, sin consulta y cierre fallido = interrumpido; fila o marca = interrumpido; sin nada = normal; `construir_control` pasa `interrumpido=False`;
  - textos es/en y detalle ALD con la causa nueva.
- Relacionadas, en verde: S9 (estado seguro de arranque, revisión 1, planta simulada con los 4 programas × 8 celdas, login y causa QML), T6, ESS-07, ESS, T17-ESG, T17-F2, U10b, i18n, línea base i18n, T26-ARQ, `test_tema_oscuro`, A10, secuencia de arranque, `test_arquitectura_capas`, `test_t15_rutas_equivalentes`. Resultado: 705 passed, 1 skipped, 4 xfailed en la tanda grande (una falla de texto, corregida y repetida en verde: `test_s9_login_y_causa_qml`), y 156 passed en la segunda.
- Falla preexistente, ajena: `test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite` falla igual sin los cambios (`git stash`): `UnicodeDecodeError` al leer la salida del subproceso QML (codificación de la consola). Anotada como **AJ28B-05**.

### Hallazgos

- **AJ28B-04 (MEDIA, corregido por el pedido):** en el encendido normal, el protocolo de estado seguro corría en cada arranque con la cámara no segura (D9-1.1) y mostraba «Estado seguro en curso» por una presión residual normal tras apagar con las puertas cerradas. Ahora lo resuelve PREPARACION.
- **AJ28B-05 (BAJA, preexistente, sin cambio):** la prueba QML de ALD de NO ABRIR falla en esta máquina por la codificación de la salida del subproceso. No depende de A9.
- **`DECISIÓN SIN CONFIRMAR`:**
  1. En el encendido normal, el programa del último ciclo (o el desconocido = líquido, si no hay ninguno) sigue contando para NO ABRIR, el límite de temperatura y el venteo por la lenta en líquidos hasta 3 lecturas seguras. Es lo conservador y conserva SAF-01 de T3 / SAF-02 de T6.
  2. La falla segura se extiende al cierre de ciclos que falla y a la ausencia de consulta, además de lo que pide el prompt (sin base).
  3. El evento `arranque_camara_no_segura` sigue en la bitácora en el encendido normal (con `estado_seguro: false`), una vez por encendido.
  4. Texto de la causa: «Arranque tras un ciclo interrumpido con la cámara no segura: el equipo la lleva solo a estado seguro, sin confirmación (no hubo paro de emergencia).» / inglés equivalente.

### Riesgo, trazabilidad, CLAUDE.md y banco

- `docs/riesgos/registro_riesgos.md`: sección nueva al final, HAZ-A9-01 (MEDIA), y tabla de controles modificados (HAZ-S9-01/D9-1.1 reemplazada en el encendido normal; HAZ-ARQ-01/ARQ-04 sin cambio).
- `docs/riesgos/matriz_trazabilidad.md`: fila `REQ-T28B-A9`, con número provisional para no chocar con los otros flujos; se numera al unir.
- `CLAUDE.md`: viñeta nueva al final de la sección de arranque de la tanda 26.
- Banco: T28-A9-01 en el bloque T28 (flujo B).

### Evaluación normativa (puerta de entrada, NTC-IEC 62304:2019 / IEC 62304:2006)

- Clase C: toca el estado seguro de arranque, una medida de control de riesgo.
- Solicitud de cambio (8.2.1): punto A9 del prompt de la tanda 28, decisión de Cristian del 5-nov.
- 7.4.1/7.4.2: retira una medida de control (el protocolo) en el encendido normal. La reemplazan las reglas de PREPARACION, NO ABRIR y la falla segura del contexto. El riesgo nuevo queda en HAZ-A9-01.
- 5.2/5.4: requisito y diseño actualizados en CLAUDE.md, el registro de riesgos y la trazabilidad.
- 5.5.5/5.6.6/8.2.3: se repitieron las pruebas de unidad e integración del arranque y del estado seguro. Falta el banco (T28-A9-01) y la revisión de seguridad.
- SOUP: sin cambios.
