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
- `docs/riesgos/matriz_trazabilidad.md`: fila `REQ-64` (en la rama, `REQ-T28B-A9` provisional para no chocar con los otros flujos; numerada al unir a dev).
- `CLAUDE.md`: viñeta nueva al final de la sección de arranque de la tanda 26.
- Banco: T28-A9-01 en el bloque T28 (flujo B).

### Evaluación normativa (puerta de entrada, NTC-IEC 62304:2019 / IEC 62304:2006)

- Clase C: toca el estado seguro de arranque, una medida de control de riesgo.
- Solicitud de cambio (8.2.1): punto A9 del prompt de la tanda 28, decisión de Cristian del 5-nov.
- 7.4.1/7.4.2: retira una medida de control (el protocolo) en el encendido normal. La reemplazan las reglas de PREPARACION, NO ABRIR y la falla segura del contexto. El riesgo nuevo queda en HAZ-A9-01.
- 5.2/5.4: requisito y diseño actualizados en CLAUDE.md, el registro de riesgos y la trazabilidad.
- 5.5.5/5.6.6/8.2.3: se repitieron las pruebas de unidad e integración del arranque y del estado seguro. Falta el banco (T28-A9-01) y la revisión de seguridad.
- SOUP: sin cambios.

### Revisión de seguridad de A9 (tanda 28b): correcciones

Dos revisores de seguridad rechazaron 2a5d7000. Cristian decidió la solución de A9-R1: marca persistente.

- **A9-R1 (ALTA, corregido).** El `CycleLogger` cierra el ciclo (`fecha_fin`) y borra la marca del contador apenas la fase sale de «en curso» (`cycle_logger.py`, cierre en `update()` y `_limpiar_marca`), antes y durante el protocolo de fin de ciclo. Un corte de energía, «Apagar equipo», el reinicio por reasignación en FALLA o una caída del backend con `ProtocoloFallo`/`ProtocoloEstadoSeguro` en marcha dejaban `hubo_ciclo_interrumpido()` en False y el arranque se tomaba como normal. Corrección:
  - `core/runtime/marca_estado_seguro.py` (nuevo): `MarcaEstadoSeguro` sobre `data/estado_seguro_en_curso.json`, independiente de la base y del contador. Escritura atómica como `contador_ciclos.py` (temporal + fsync + `os.replace` con reintentos). `presente()` falla cerrada: ilegible, corrupta o cualquier error = presente; solo «no existe» es ausencia.
  - `ControlLoop.protocolo_fin_ciclo_en_curso()` y `_sincronizar_marca_estado_seguro()` (paso 5a del tick, bajo `_sm_lock`, también en modo prueba). La marca está presente mientras (a) el estado seguro esté activo (también en pausa por paro o modo prueba, con la confirmación pendiente o en PREPARACION con solo la lenta tras salir de FALLA); (b) en CICLO, el `ProtocoloFallo` del ciclo ya se ejecutó (FALLO o CANCELADO esperando la confirmación: el ciclo ya está cerrado en la base); (c) el arranque tras un ciclo interrumpido todavía no decidió. Se borra solo cuando eso deja de ser cierto: `estado_seguro_alcanzado` (3 lecturas seguras), arranque con la cámara segura (3 lecturas) o un ciclo nuevo (`terminar()` en la entrada a CICLO; el ciclo nuevo tiene su propia marca en el contador). Solo se escribe en los cambios; si la escritura o el borrado fallan, se reintenta en el tick siguiente (aviso en el log una vez por episodio). Ante un error al evaluar, se mantiene (falla cerrada). Con el apagado aceptado, el retenido o un tick que lanza antes del paso 5a, no se toca: queda como estaba.
  - `BackendContext.marca_estado_seguro` (propiedad, como `contador_ciclos`) se pasa al `ControlLoop`; `hubo_ciclo_interrumpido()` devuelve True primero si la marca está presente (o si consultarla falla).
  - Ninguna regla de borrado depende de la interfaz. El paro, el modo prueba, la confirmación pendiente y la salida de FALLA a PREPARACION no la borran porque el protocolo sigue activo.
- **A9-R2 (corregido).** `tests/test_ess07_reasignacion_reinicio.py` ya no llama `recuperar_ciclo_interrumpido(programa)` con True por omisión. `_reiniciar` sigue el camino de producción: el proceso anterior crea y cierra el ciclo FALLO en una base SQLite real y su `ControlLoop` (con el estado seguro activo) escribe la marca; el proceso nuevo abre esa base, corre `_numeracion_y_ciclos_interrumpidos()` y clasifica con `hubo_ciclo_interrumpido()`, y ese resultado decide. Las pruebas del archivo, incluidos los 4 `xfail(strict=True)` de ESS07-H1, siguen igual. Integración nueva (sección 3b): FALLO cerrado → reinicio → clasificación con marca (protocolo), sin marca (encendido normal, NO ABRIR igual) y con marca corrupta (protocolo); corte con el ciclo en curso (fila sin fin = interrumpido); COMPLETADO cerrado sin protocolo = normal; y la marca borrada al terminar el protocolo deja el encendido siguiente normal.
- **A9-R3 (corregido).** `respaldo_ciclos.reimportar` devuelve además `interrumpidos` (importados sin cierre, que quedaron INTERRUMPIDO y que `cerrar_ciclos_interrumpidos` ya no ve). `_reimportar_respaldos` marca `_respaldo_interrumpido` con un importado sin cierre, con un respaldo no reimportado (`errores`) o si la reimportación lanza (falla segura, `DECISIÓN SIN CONFIRMAR` para `errores`). El segundo intento de la etapa 6 (`abrir_base_datos`) ya no deja `_ciclo_interrumpido = None`: conserva la fila del primero, y la marca del contador se acumula. Un fallo de `cerrar_ciclos_interrumpidos` en cualquier intento deja `_cierre_interrumpidos_fallido` (True).
- **A9-R4 (documentado, residual por diseño).** Tras un corte con el protocolo en marcha, cada encendido vuelve a correr el protocolo de arranque hasta que uno termine con la cámara segura. Si la cámara ya está segura al arrancar, la marca se borra con 3 lecturas y no aparece el estado seguro. Un COMPLETADO sin confirmar no pone la marca (no hay protocolo): un corte en esa ventana arranca como encendido normal (PREPARACION; el programa del último ciclo sigue contando para NO ABRIR).
- **A9-R5 (corregido).** Docstrings y comentarios de `estado_seguro.py` (cabecera, `origen`, `causa`, `iniciar`) dicen `ciclo_interrumpido` en vez de «arranque».

**Pruebas:** `tests/test_t28b_a9r_marca_estado_seguro.py` (32, nuevo): marca ausente/escrita/borrada y atómica; corrupta (4 formas) o ilegible = presente; contexto con la marca, la marca corrupta y la consulta que lanza; A9-R3 (reimportación con base real que separa el respaldo sin cierre, respaldo sin cierre o no reimportado, reimportación que lanza, segundo intento que no olvida, segundo intento con cierre fallido); lazo: sin protocolo no hay marca, FALLO esperando confirmación en CICLO, estado seguro con los 4 orígenes y su borrado, paro/modo prueba/confirmación/salida de FALLA no la borran, ciclo nuevo la borra, arranque interrumpido la conserva hasta decidir, arranque normal no la escribe, reintento tras error de escritura, error al evaluar = se mantiene; integración con el `ControlLoop` real y la planta simulada de S9: corte a mitad del protocolo (el proceso nuevo clasifica interrumpido), modo prueba a mitad (la marca sigue) y fin del protocolo (marca borrada, el encendido siguiente es normal). `tests/test_ess07_reasignacion_reinicio.py`: 55 (6 nuevas). `tests/test_t28b_a9_arranque_sin_protocolo.py`: fixture que aísla la marca en `tmp` (sin cambiar aserciones).

**Archivos:** `src/autoclave/core/runtime/marca_estado_seguro.py` (nuevo), `src/autoclave/services/domain/loop/control_loop.py`, `src/autoclave/backend/context.py`, `src/autoclave/core/runtime/respaldo_ciclos.py`, `src/autoclave/state_machine/estado_seguro.py` (docstrings), pruebas citadas, `docs/riesgos/registro_riesgos.md` (HAZ-A9-01), `docs/riesgos/matriz_trazabilidad.md` (REQ-64), `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (T28-A9-01 pasos 5 y 6: corte de energía a mitad del protocolo).

**`DECISIÓN SIN CONFIRMAR`:** (1) la marca también cubre la ventana FALLO/CANCELADO en CICLO esperando la confirmación y el arranque interrumpido todavía sin decidir; (2) un respaldo que no se pudo reimportar cuenta como interrumpido; (3) el COMPLETADO sin confirmar no pone la marca.

**Pendiente:** ~~CLAUDE.md (viñeta de A9)~~ (agregada con M3–M5). Revisión de seguridad de esta corrección y banco T28-A9-01.

## A13. Secado corto tras un ciclo fallido

**Pedido (Cristian, 5-nov):** tras un fallo, la cámara llega a la presión atmosférica con vapor de agua a alta temperatura, y abrir la puerta así puede quemar al operador. Con carga sólida, el equipo hace un minuto de vacío para retirar ese vapor y rompe el vacío con aire antes de dar la cámara por segura.

> **Para el revisor: cambio de proceso clase C. Toca actuadores (bomba de vacío, vacío de cámara, aire atmosférico), el protocolo de fallo y el fin del estado seguro.** La revisión de seguridad obligatoria está pendiente. El implementador no puede lanzar el revisor: la debe pedir el director antes de unir.

### Diseño

El secado vive en `ProtocoloFallo` (`state_machine/cycle_phases/protocolo_fallo.py`) porque el mismo objeto corre en `CicloState`, mientras espera la confirmación, y después en `ProtocoloEstadoSeguro`.

1. **Decisión al disparar** (`ejecutar`). El resultado queda en `pendiente`, salvo que ya se sepa que no corre. En ese caso queda en `omitido` con su motivo:
   - parámetro en 0 → `desactivado`;
   - `tipo_carga` distinto de `"solido"` exacto → `carga_liquida`;
   - sin bomba ni vacío instalados → `sin_bomba`. Lo decide `profile.vacio_instalado`: capacidad `has_vacuum` de la clase y `bomba_vacio`/`vacio_camara` en el io_enabled filtrado por el perfil. Sin perfil real, False;
   - programa sin secado (modo 0 o `tiempo_secado` 0) → `sin_secado_programa`;
   - fallo del sistema de vacío → `fallo_vacio`. Cuenta como tal: código de fallo CIC-02 (prevacío) o CIC-06 (secado), SUM-03 activa, DI `agua_bomba` declarada y en 0, o falta de suministro eléctrico;
   - `ejecutar(secado_tras_fallo=False)` → `no_aplica`. Solo se usa en el COMPLETADO reconocido con la cámara no segura (`state_machine.py`).
2. **Inicio** (`_iniciar_secado`), la primera vez que la cámara llega a la banda atmosférica (rama «rango normal» de `update()`). Se vuelven a evaluar las condiciones de arriba y se exige además:
   - sin paro;
   - trama AI vigente;
   - presión y Principal con lectura;
   - todas las puertas instaladas confirmadas cerradas (DI == 1 o True);
   - ni sellado ni alivio D8-2.10.
   Si alguna falla, el secado queda `omitido` con su motivo y el protocolo sigue como hoy.
3. **SECADO** (`_tick_secado`):
   - salidas: `vapor_camara`, `vapor_chaqueta`, las tres descompresiones, el aire comprimido, el aire atmosférico y `agua_chaqueta` en OFF; `bomba_vacio` y `vacio_camara` en ON. El agua de la bomba y la del intercambiador las ponen `bomba_vacio_on`/`vacio_camara_on`, como en la fase SECADO;
   - duración: `secado_tras_fallo_s`;
   - en cada tick se revisan las condiciones del punto 2 y, solo durante el vacío, el fallo del sistema de vacío. Si alguna falla, `cortar_secado` apaga la bomba y el vacío en ese mismo tick, el resultado queda `cortado` con los segundos y el motivo, y el protocolo sigue normal desde ese tick. El secado no se reanuda.
4. **Apagado escalonado:** primero la bomba (con su agua) y, `_STAGGER_APAGADO_VACIO` (0,15 s, el de PRE_VACIO) después, el vacío.
5. **RUPTURA:** aire atmosférico hasta `pres >= atm − rango`. Solo con la referencia atmosférica configurada (`_referencia_atm_configurada`), y se cierra con presión. Tiene un tope de 120 s (`_RUPTURA_LIMITE_S`, **DECISIÓN SIN CONFIRMAR**). Al vencer, el resultado queda `sin_ruptura`, se avisa en el log y la bitácora, y sigue el protocolo normal.
6. **Estado seguro** (`state_machine/estado_seguro.py`):
   - mientras `protocolo.secando is True`, no cuenta lecturas seguras y publica el motivo pendiente `secando_vapor_residual`;
   - el paro (también el `requiere_confirmacion`), los datos no vigentes y `pausar("modo_prueba")` llaman a `cortar_secado`;
   - el modo prueba conserva la pausa de siempre;
   - registra `estado_seguro_secado_iniciado` y `estado_seguro_secado_terminado` (con resultado, motivo y segundos) por `al_evento`, como los demás `estado_seguro_*`.
7. **CicloState** (`states/ciclo.py`): le da al protocolo `profile` y `alarm_manager`. Con el resultado pendiente y el paro activo, corta el secado (`cortar_secado("paro")`). La apertura y el inicio ya están bloqueados en CICLO.
8. **Ciclo interrumpido** (A9, `control_loop.py`): el protocolo del arranque recibe `profile` y `alarm_manager`. Rige la misma regla (**DECISIÓN SIN CONFIRMAR**, como dice el prompt). El programa desconocido o sin tipo de carga se toma como líquido, y así no corre.
9. **Parámetro** `secado_tras_fallo_s` en `config/global_params.json`:
   - grupo `camara_segura`, int, `seg`, defecto 60, rango 0–300;
   - validación, auditoría (`param_sistema_cambio`) y pantalla de Parámetros del equipo usan el mecanismo común;
   - i18n `parametros_equipo(_desc).secado_tras_fallo_s` y la descripción del grupo Cámara segura;
   - el protocolo lo lee en cada uso. Un valor fuera de rango o ilegible da el defecto, con error en el log.
10. **Ticket, PDF e historial:**
    - `estado.secado_tras_fallo` guarda `{estado, motivo, segundos}`;
    - `CycleLogger._on_fin` agrega el aviso `ticket_ciclo.secado_tras_fallo` a todo ciclo no COMPLETADO. Al cierre (fin de la fase) casi siempre dice «pendiente al cerrar el ciclo»;
    - al conocerse el resultado, `CycleLogger._seguir_secado_tras_fallo` reescribe esa línea en `avisos_ticket` del ciclo cerrado (`DbManager.actualizar_avisos_ticket`, en el ejecutor de la base). Con eso, el historial, la reimpresión y el PDF (que dibuja el ticket) dicen «Secado tras fallo: 60 s», «omitido (carga líquida)», «cortado a los N s (paro de emergencia)» o «N s (la ruptura del vacío no llegó a la presión atmosférica)»;
    - el ticket impreso al cierre no cambia.
11. **Interfaz:** `detalle_aviso.texto_espera` da «Secando vapor residual» / «Drying residual steam» (`sistema.estado_seguro_secando`) para ese motivo, en la nota de la fila de estado seguro y en su detalle ALD. No hubo cambios en QML ni en el puente: se aprovecha `motivo_pendiente` de A10.

### Pruebas

- Nuevas: `tests/test_t28b_a13_secado_tras_fallo.py` (33; decía 35 por error, recontado en la revisión de la tanda 28b), con `ProtocoloFallo` y `ProtocoloEstadoSeguro` reales y salidas en un doble:
  - FALLO y CANCELADO sólidos con el equipo completo: 60 s de vacío con bomba y vacío en ON y vapor, escapes y aire en OFF; apagado escalonado; ruptura con aire; el estado seguro solo termina después, con 3 lecturas;
  - el estado seguro no se da por alcanzado antes de terminar la ruptura, aunque la cámara parezca segura;
  - ruptura que no llega a la banda: `sin_ruptura` y sigue el protocolo;
  - no corre con: carga líquida, tipo de carga ilegible, sin bomba en el perfil, programa sin secado, fallo de vacío CIC-02/CIC-06, sin agua de la bomba (alarma y DI), parámetro en 0, COMPLETADO, puerta no confirmada o Principal sin lectura al llegar;
  - lo cortan, sin reanudarse: un paro (también visto por el propio protocolo), una puerta que se abre, la falta de agua de la bomba, el modo prueba, los datos no vigentes y la presión sin lectura;
  - parámetro cambiado en vuelo y parámetro inválido;
  - `vacio_instalado`;
  - líneas del ticket es/en;
  - reescritura de `avisos_ticket` al conocerse el resultado (CycleLogger y DbManager reales sobre una base temporal);
  - texto y detalle ALD «Secando vapor residual».
- Ajustadas, sin relajar:
  - `test_t2_p1_completado_estado_seguro.py`: el COMPLETADO ahora llama `ejecutar(..., secado_tras_fallo=False)`;
  - `test_o2a_parametros_equipo.py`: el parámetro nuevo y el grupo Cámara segura con 3 claves;
  - `test_i18n.py`: familias `ticket_ciclo.secado_estado.` y `ticket_ciclo.secado_motivo.`.
- Las pruebas existentes del protocolo y del estado seguro no tienen perfil con bomba, así que quedan con el secado omitido (`sin_bomba`) y el comportamiento de antes.
- Resultado de la tanda relacionada: 1693 passed, 5 skipped, 4 xfailed, 1 failed. La que falla es `test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite`, preexistente y ajena (AJ28B-05: falla igual sin estos cambios). La tanda incluye arquitectura, rutas/OpenAPI (T15), ciclo, CycleLogger, ensayos con simulador (E1, Q1, T8-S2a, T11), estado seguro (S9, T5, T2, ESS, T17), protocolo de fallo, PREPARACION, prevacío, secado, ticket, PDF, i18n, O2a, tema oscuro, A9, A10 y A13.

### Hallazgos

- **AJ28B-06 (ALTA, corregido por el pedido):** tras un fallo con carga sólida, el estado seguro se daba por alcanzado con la cámara a la presión atmosférica pero llena de vapor caliente: riesgo de quemadura al abrir. Ahora se seca antes de contar las lecturas seguras.
- **AJ28B-07 (MEDIA, informativo):** `camara_segura` (NO ABRIR en `/status`) no conoce el secado. Durante el vacío la presión ya da «no segura». En el primer tick del secado y en el último de la ruptura la cámara puede verse segura, pero la puerta está bloqueada por el estado seguro activo (`ser_puertas._estado_seguro_activo`), el inicio también, y la fila «NO ABRIR» ya se oculta con el estado seguro en curso (A10). No se cambió el criterio de cámara segura. Que lo decida el revisor.
- **AJ28B-08 (BAJA):** los eventos `estado_seguro_secado_*` se registran como los demás `estado_seguro_*`, sin categoría propia (el filtro central los registra con aviso). Si Cristian quiere filtrarlos, hay que agregarlos a `bitacora.EVENTOS`/`_CATEGORIA`.
- **AJ28B-09 (BAJA):** en `CicloState`, mientras espera la confirmación, el protocolo no sabe si las DI están vigentes: solo ve la trama AI. Con una DI vencida en CICLO, el ciclo ya cae por FALLO_CONEXION, pero el secado podría ver una puerta «cerrada» congelada durante la tolerancia. En `ProtocoloEstadoSeguro` no pasa (solo actualiza con datos vigentes).
- **`DECISIÓN SIN CONFIRMAR`:**
  1. CANCELADO y el arranque tras un ciclo interrumpido siguen la misma regla (lo marca el prompt).
  2. Tope de la ruptura: 120 s.
  3. «Programa con secado» = sección `secado` con modo ≠ 0 **y** `tiempo_secado` > 0.
  4. Fallo del sistema de vacío = CIC-02 (cualquier fallo de prevacío) o CIC-06, SUM-03, DI `agua_bomba` declarada en 0 o falta de suministro eléctrico.
  5. La decisión se toma una sola vez, al llegar por primera vez a la banda. Si una condición falla en ese momento, el secado queda omitido y no se reintenta.
  6. El modo prueba corta el secado (no lo pausa) y no se reanuda.
  7. Ticket en vivo con «pendiente al cerrar el ciclo». El resultado final va solo a la base (historial, reimpresión, PDF), no al respaldo JSONL.
  8. Sin perfil de instalación no hay secado (falla cerrada).
  9. Redacción de los textos es/en.

### Riesgo, trazabilidad, CLAUDE.md y banco

- `docs/riesgos/registro_riesgos.md`: sección nueva al final, HAZ-SFF-01 (MEDIA). Cubre el vapor residual al abrir y el riesgo nuevo de hacer vacío con la cámara caliente, mitigado solo con carga sólida.
- `docs/riesgos/matriz_trazabilidad.md`: fila `REQ-65` (provisional `REQ-T28B-A13`, numerada al unir a dev).
- `CLAUDE.md`: viñeta nueva al final de la sección de la tanda 26, después de la de A9.
- Banco: T28-A13-01.

### Evaluación normativa (puerta de entrada, NTC-IEC 62304:2019 / IEC 62304:2006)

- Clase C: cambio de proceso que mueve actuadores (bomba de vacío, vacío, aire atmosférico) después de un fallo.
- Solicitud de cambio (8.2.1): punto A13 del prompt de la tanda 28, decisión de Cristian del 5-nov.
- 7.4.1/7.4.2: agrega una medida de control (contra la quemadura por vapor residual) y una causa nueva de situación peligrosa (vacío con la cámara caliente). La nueva causa queda acotada por las condiciones de omisión y de corte, con falla cerrada en cada una. No interfiere con las medidas existentes: el criterio de cámara segura y los 3 ticks no cambian, y el estado seguro solo espera más.
- 5.2/5.3/5.4: requisito, parámetro y diseño en CLAUDE.md y el registro de riesgos.
- 5.5.5/5.6.6/8.2.3: unidad e integración del protocolo, del estado seguro, del ticket y de la base. Falta la revisión de seguridad, la suite completa (paso del director) y el banco (T28-A13-01).
- SOUP: sin cambios.

### Revisión de seguridad de A13 (tanda 28b): correcciones sin decisión pendiente

Dos revisores de seguridad rechazaron 4db38ed8. Se corrigió lo que no requiere decisión de Cristian.

- **M1 (MEDIA, corregido).** `StateMachine.update` atrapa cualquier excepción de `estado_seguro.update` y el lazo sigue. Si `ProtocoloFallo.update()` lanzaba antes de `_tick_secado`, `bomba_vacio` y `vacio_camara` quedaban con la última orden ON y MOD-08 no apagaba (el lazo seguía vivo). Ahora:
  - `ProtocoloFallo.update()` envuelve el cuerpo (`_update()`): ante cualquier excepción con el secado en curso llama `cortar_secado("error")` (bomba, vacío y aire atmosférico OFF, resultado `cortado`, no se reanuda) y vuelve a lanzar, para que quien llama la registre como siempre. Cubre el bloque del secado y todo lo anterior, en `CicloState` y en el estado seguro.
  - El `except` de `StateMachine.update` llama `estado_seguro.cortar_secado("error")` (método público nuevo que nunca lanza), para un error del estado seguro fuera del protocolo.
- **M2 (MEDIA, corregido).** `_iniciar_secado` no exigía `_referencia_atm_configurada()`, pero la RUPTURA sí: sin referencia, el vacío no se rompía nunca. La referencia entra en `_motivo_corte_secado`, que rige al empezar y en cada tick: sin ella el secado queda `omitido` y, si se pierde a mitad (cambio en Parámetros del equipo), se corta. Motivo propio `sin_referencia_atm`. Evaluación de seguirla exigiendo durante el vacío: sí. Seguir haciendo vacío sin poder romperlo solo profundiza el vacío, y el protocolo normal tampoco abre el aire sin referencia: la cámara queda en vacío con NO ABRIR (lado seguro), igual que antes del secado.
- **B1 (BAJA, corregido).** `cortar_secado` con el secado todavía `pendiente` y motivo `paro`, `modo_prueba` o `error` lo deja `omitido` con ese motivo. Antes no hacía nada y el secado podía arrancar después de un paro o del modo prueba. Aplica en `ProtocoloEstadoSeguro.update` (paro, también con la confirmación pendiente), `pausar("modo_prueba")` y `CicloState` (paro con el resultado pendiente). Los datos no vigentes antes de la banda no lo omiten: al volver se decide como siempre.
- **B2 (BAJA, corregido).** Con el ALL_OFF del disparo sin confirmar, `update()` manda `reset_all_outputs` en cada tick y `_salidas_secado` volvía a encender la bomba: conmutaba cada tick. `not self._salidas_apagadas` entra en `_motivo_corte_secado` (condición de inicio y de corte), motivo `salidas_sin_confirmar`.
- **B4 (pruebas, corregido).** Ver abajo. El conteo de `tests/test_t28b_a13_secado_tras_fallo.py` es **33** (el informe y HAZ-SFF-01 decían 35; recontado con `pytest --collect-only`). Corregido en HAZ-SFF-01 y aquí.
- Textos nuevos `ticket_ciclo.secado_motivo.{error, sin_referencia_atm, salidas_sin_confirmar}` (es/en), en `MOTIVOS_SECADO` (la familia de `test_i18n`).

**Pruebas:** `tests/test_t28b_a13r_secado_revision.py` (17, nuevo), con `ProtocoloFallo`, `ProtocoloEstadoSeguro`, `CicloState`, `StateMachine` y `ControlLoop` reales:
- M1: excepción inyectada en `_seguir_presion_perdida` (antes del bloque del secado) y en `_tick_secado`; excepción del estado seguro atrapada por `StateMachine.update` (no lanza, bomba y vacío OFF y no vuelven a encenderse en los ticks siguientes); error antes de empezar = omitido.
- M2: sin `presion_admosferica` o sin `rango_presion_atm` no empieza; referencia inválida a mitad lo corta (aire cerrado).
- B1: paro y modo prueba antes de la banda lo omiten; datos no vigentes antes de la banda no.
- B2: ALL_OFF sin confirmar desde el disparo (la bomba nunca recibe ON) y ALL_OFF que deja de confirmarse a mitad.
- B4: `CicloState` real con el resultado FALLO pendiente y paro (`ciclo.py`, paro con resultado pendiente): omitido por paro; paro durante el secado en `CicloState`: cortado; secado empezado en `CicloState` que sigue en el estado seguro al confirmar (`iniciar` → `reanudar` sin perder el secado ni su fin) y termina `hecho` con sus 10 s; arranque tras un ciclo interrumpido (`_procesar_recuperacion`): el protocolo recibe `profile` y `alarm_manager` y el secado queda pendiente; trama AI vencida vista por el propio protocolo (datos DI vigentes): cortado por `datos_no_vigentes`.

**Archivos:** `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, `src/autoclave/state_machine/estado_seguro.py` (`cortar_secado` público), `src/autoclave/state_machine/state_machine.py`, `src/autoclave/i18n/es.json`, `src/autoclave/i18n/en.json`, `tests/test_t28b_a13r_secado_revision.py`, `docs/riesgos/registro_riesgos.md` (HAZ-SFF-01), `docs/riesgos/matriz_trazabilidad.md` (REQ-65).

**`DECISIÓN SIN CONFIRMAR`:** (1) un error interno antes de empezar también omite el secado (como el paro); (2) la referencia atmosférica se exige también durante el secado y la ruptura (corte, no espera); (3) redacción de los tres motivos nuevos.

**Pendientes de decisión de Cristian (no implementados):**
- **M3:** verificar que el vacío se logró durante el SECADO (hoy solo se cuenta el tiempo; una bomba que no hace vacío termina «hecho»).
- **M4:** NO ABRIR durante el secado en `camara_segura` y `/status` (AJ28B-07: hoy la puerta queda bloqueada por el estado seguro activo, pero `camara_segura` no conoce el secado).
- **M5:** tipo de carga en el ciclo interrumpido (el programa reconstruido o el desconocido decide si corre el secado).

**Pendiente:** ~~CLAUDE.md (viñeta de A13)~~ (hecho con M3–M5, abajo). Revisión de seguridad de esta corrección y banco T28-A13-01.

### Decisiones de Cristian sobre la revisión de A13 (6-nov): M3, M4 y M5

> **Para el revisor: cambio de proceso clase C** (bomba de vacío, aire atmosférico, criterio de cámara segura y arranque tras un ciclo interrumpido). La revisión de seguridad de estos tres cambios está pendiente; la pide el director antes de unir.

**M3, verificar el vacío (commit `8c12a72d`).**
- `_tick_secado` ya no da «hecho» solo por tiempo. Mientras la bomba trabaja (fase SECADO), `_seguir_vacio` cuenta el tiempo continuo (monotonic) con la presión de cámara bajo `atm − rango_presion_atm` (las mismas claves `presion_admosferica` y `rango_presion_atm` del equipo). Si se sostiene `secado_tras_fallo_vacio_s` segundos, el vacío queda verificado.
- Al terminar la ruptura: «hecho» solo con el vacío verificado; si no, **«sin_vacio»** (nunca «hecho»), con `logger.error`, aviso no bloqueante **CIC-21** «Secado tras fallo sin vacío» (despeje manual; detalle con el límite y los segundos) y el evento `estado_seguro_secado_terminado` con `resultado: "sin_vacio"`.
- La ruptura corre siempre, también sin vacío (tope de 120 s, sin cambio). Si la ruptura vence, el resultado sigue siendo «sin_ruptura».
- Falla cerrada: una lectura sin valor, no finita, la trama AI vencida o un error ponen el conteo en cero. Además, sin lectura de presión el secado se sigue cortando como antes (bomba OFF, «cortado (presión de cámara sin lectura)»): nunca «hecho».
- Parámetro `secado_tras_fallo_vacio_s` en `global_params.json`, grupo Cámara segura: int, `seg`, defecto 10, rango 1–60, leído en cada uso (fuera de rango: el defecto, con error en el log). Si es mayor que `secado_tras_fallo_s`, se avisa en el log al empezar (el resultado será «sin_vacio»). i18n es/en del nombre y la descripción.
- Bitácora: `estado_seguro_secado_iniciado` y `estado_seguro_secado_terminado` pasan a `bitacora.EVENTOS` con texto propio y categoría `seguridad` (resuelve AJ28B-08; ya no son eventos desconocidos).
- Ticket, PDF e historial: estado `sin_vacio` en `ticket_formatter._ESTADOS_SECADO` y `ProtocoloFallo.ESTADOS_SECADO`; texto «Secado tras fallo: 60 s sin lograr vacío (la cámara puede conservar vapor residual)» / «… without reaching vacuum …».

**M4, NO ABRIR durante el secado (commit `05cdc3a6`).**
- `ProtocoloFallo` publica `estado.secando_tras_fallo` en cada transición de la fase del secado (un setter de `_secado_fase`): True desde el mismo tick en que empieza hasta el tick en que termina la ruptura o se corta.
- `camara_segura.evaluar` y `motivos` dan «no segura» con el motivo **`secando_vapor_residual`** mientras ese indicador está activo, antes que las lecturas (solo «datos no vigentes» va primero). Con el resultado todavía «pendiente» (CicloState esperando la confirmación, o entre el tick del lazo y el del protocolo) también es «no segura», si nada más lo impide (una sobrepresión se sigue mostrando como sobrepresión).
- Lo heredan `/status.camara_segura`, el interlock de puertas, el inicio de ciclo (PREPARADO), «Apagar equipo» y el aviso de Reasignación. `evaluar_presion` (protecciones del modo prueba) no cambia: el modo prueba ya corta el secado.
- `finalizar()` con el secado pendiente lo deja «omitido (no aplica)»: un cierre forzado no deja NO ABRIR pegado.
- El estado seguro sigue sin contar lecturas seguras durante el secado. Al terminar la ruptura cuenta sus 3 lecturas como antes.
- Textos: `puerta.secando_vapor_residual`, `aviso_detalle.no_abrir_motivos.secando_vapor_residual` (descripción y acción) y `aviso_detalle.estado_seguro_espera.secando_vapor_residual`, es/en; `motivos.CODIGOS` y `detalle_aviso.MOTIVOS_NO_ABRIR`. Sin cambios en QML. Resuelve AJ28B-07.

**M5, programa seguro en el ciclo interrumpido (commit `929ccbcb`).**
- `BackendContext._programa_para_arranque_con_origen()` devuelve `(programa, del_ciclo)`. `del_ciclo` es True solo con la instantánea del propio ciclo interrumpido (`programa_json` de la fila o la de la marca del contador, escrita al iniciarlo) o con la que guardó la marca persistente de estado seguro. La copia de la definición actual (`base.copia()`), el último ciclo registrado y el programa desconocido dan False. `_programa_para_arranque()` conserva su firma.
- Orden: fila / marca del contador → marca de estado seguro → último ciclo → desconocido (líquido).
- `ControlLoop.recuperar_ciclo_interrumpido(programa, interrumpido, programa_del_ciclo=False)`: por omisión, incierto (falla cerrada). El protocolo de arranque recibe `programa_incierto = not programa_del_ciclo` y `_motivo_omision_secado_inicial` devuelve `programa_incierto` (después de «desactivado» y antes de la carga).
- **Marca persistente:** sí conviene guardar el programa. En el caso de A9-R1 (FALLO ya cerrado en la base, protocolo en marcha, corte), no hay fila interrumpida ni marca del contador, y sin esto el programa salía del último ciclo registrado: incierto, sin secado. `ControlLoop._programa_para_marca()` agrega `programa` (instantánea) y `tipo_carga` a la marca (misma escritura atómica de A9-R1) solo si el programa es del propio ciclo: el del ciclo en CICLO, el del estado seguro (salvo un protocolo de arranque con programa incierto) o el de una recuperación marcada como del ciclo. Ante un error se escribe la marca sin programa. `MarcaEstadoSeguro.leer()` devuelve el contenido o None. Un `programa` ilegible se descarta y el arranque lo toma como incierto. La presencia sigue juzgándose con `presente()`, con falla cerrada.
- Tipo de carga ilegible = líquida (no seca), sin cambio.
- Texto `ticket_ciclo.secado_motivo.programa_incierto` es/en. Tras un reinicio, el resultado del secado no se reescribe en el ciclo interrumpido (el CycleLogger solo sigue el ciclo que cerró en el mismo proceso; limitación de A13 sin cambio). Queda en el log y la bitácora.

**Pruebas nuevas:**
- `tests/test_t28b_m3_vacio_secado.py` (27). Cubre:
  - vacío logrado;
  - bomba desconectada: «sin_vacio», CIC-21, bitácora, y el estado seguro que termina igual;
  - vacío parcial sin sostener, con la ruptura que abre el aire;
  - vacío tarde dentro y fuera del tiempo;
  - ruptura vencida;
  - sin lectura (corte, nunca hecho) y `_seguir_vacio` con None/NaN/inf/texto/bool;
  - trama AI vencida;
  - borde de la banda;
  - parámetro inválido y cambiado en vuelo;
  - catálogo, bitácora y línea del ticket es/en.
- `tests/test_t28b_m4_no_abrir_secado.py` (17). Cubre:
  - el primer tick;
  - el motivo durante el vacío, el apagado y la ruptura;
  - el fin de la ruptura con 3 lecturas;
  - el corte;
  - el pendiente con la cámara por lo demás segura, y el pendiente con sobrepresión;
  - un secado omitido;
  - `finalizar` con pendiente;
  - CicloState real esperando la confirmación;
  - `reset`;
  - datos no vigentes primero, y un doble MagicMock;
  - PREPARADO;
  - `solo_por_sensor`;
  - textos es/en y detalle ALD.
- `tests/test_t28b_m5_programa_interrumpido.py` (31). Cubre:
  - instantánea de la fila;
  - **instantánea líquida contra la definición actual cambiada a sólido** (rige la instantánea, no seca);
  - copia actual incierta;
  - marcas del contador;
  - último ciclo, sin nada, y contexto sin el método nuevo;
  - marca de estado seguro con y sin programa, e ilegible (4 formas);
  - protocolo con programa incierto, y tipo de carga no sólido o ilegible;
  - ticket;
  - ControlLoop (del ciclo/sólido = pendiente; incierto = `programa_incierto`; del ciclo/líquido = `carga_liquida`; sin decir el origen = incierto);
  - marca que guarda o no el programa;
  - integración: fallo sólido → marca → arranque siguiente con la definición cambiada → del ciclo;
  - error al armar la instantánea;
  - `construir_control` con el origen ilegible: incierto (corrección `352a3a00`).
- Ajustadas sin relajar:
  - A13: los dos casos que esperaban «hecho» con la presión fija en la atmosférica simulan ahora el vacío;
  - el arranque interrumpido de A13r pasa `programa_del_ciclo=True`;
  - `test_t28b_a9_arranque_sin_protocolo` espera además `programa_del_ciclo`;
  - O2a: el parámetro nuevo;
  - catálogo: el ejemplo de CIC-21.

**Pruebas ejecutadas (M3–M5):**
- Suite completa (`pytest tests -n 6`, con `PYTHONUTF8=1`): **11224 passed, 11 skipped, 7 xfailed, 4 failed**. Las 4 fallas:
  - `test_t26_arq_revision.py::test_h3_construir_control_entrega_el_evento_sin_fijar` y `test_v8b_textos.py::test_descripciones_citan_nombres_visibles_de_parametros`: causadas por M5 y M3. Corregidas en `352a3a00`, con falla cerrada en `construir_control` y el texto sin comillas angulares. Pasan.
  - `test_p9_opciones_puertas_nc.py::test_parametros_grupo_es_propiedad_que_cambia_al_guardar`: preexistente. Falla igual en `8ad21f1d`, antes de M3: espera Cámara segura con 2 claves y desde A13 tiene `secado_tras_fallo_s`. **AJ28B-10**, no corregida aquí (fuera del pedido).
  - `test_t20_s3_setup_modbus.py::test_ejecuta_consulta_de_adaptadores_solo_lectura`: preexistente. Falla igual en `8ad21f1d` (consulta de adaptadores de red de la máquina). Ajena.
- Tras la corrección, juntos: `tests/test_t28b_*.py`, arquitectura, T15 (rutas y OpenAPI sin cambio: `/status` no cambia de forma, solo el contenido de `camara_segura_motivo`), i18n, O2a, T26 ARQ y v8b. Resultado: **406 passed**.
- AJ28B-05 (`test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite`) pasó en esta máquina con `PYTHONUTF8=1`. M4 no cambia QML.

**`DECISIÓN SIN CONFIRMAR` (nuevas):**
1. `secado_tras_fallo_vacio_s` con defecto 10 s y rango 1–60, continuo y solo en la fase SECADO.
2. Vacío = presión **estrictamente** menor que `atm − rango` (el borde no cuenta).
3. Aviso CIC-21: nivel AVISO, no bloquea, despeje manual; redacción es/en.
4. Si la ruptura vence, el resultado es «sin_ruptura» aunque el vacío no se haya logrado.
5. Sin lectura de presión el secado se sigue cortando («cortado (sin presión)»), no se marca «sin_vacio»: así no se sigue evacuando sin medir.
6. Con un vacío débil que deja la presión dentro de la banda, la ruptura termina sin abrir el aire (la cámara ya está en la banda segura).
7. NO ABRIR con el resultado «pendiente» solo si nada más lo impide (el motivo de presión o temperatura tiene prioridad en el texto).
8. La instantánea de la marca del contador cuenta como del ciclo (es la misma que `programa_json`, escrita al iniciar el ciclo).
9. La marca de estado seguro guarda la instantánea completa del programa.
10. Redacción de los textos es/en nuevos.

**Riesgos:**
- HAZ-SFF-01 actualizado: M3 resuelto con verificación. Residual: con «sin_vacio» el estado seguro termina igual (aviso no bloqueante), y un transductor que lea de menos daría un falso «hecho».
- HAZ-A9-01: la marca guarda el programa del propio ciclo.
- Matriz `REQ-65` con las tres pruebas nuevas.
- Banco T28-A13-01, pasos 7 (NO ABRIR durante el secado) y 8 (bomba desconectada → «sin_vacio»).
- CLAUDE.md: viñetas de A9 (marca persistente) y A13 (M1, M2, B1, B2, M3, M4, M5 y el parámetro nuevo).
