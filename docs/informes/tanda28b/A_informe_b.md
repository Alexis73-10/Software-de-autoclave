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
