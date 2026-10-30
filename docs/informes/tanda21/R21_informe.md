# R21 — Informe de la tanda 21: fin de ciclo, puerta sin actuador y textos

Fecha: 28-oct-2026. Rama `tanda-21` (desde `dev` 92abead), unida a `dev` en 3531c19.
Spec: `docs/mis_plans/planeacion_fin_de_ciclo.md` (FC-01 a FC-13). Estado paso a paso: `estado.md`.
Versión entregada: 1.0.0-alpha.8 (commit e8d5712, etiqueta `v1.0.0-alpha.8`).

## Resumen

- La pantalla de ciclo terminado sin éxito muestra el **panel de fin de ciclo** («CARGA NO ESTÉRIL», causa, alarmas del ciclo en acordeón) en lugar de la gráfica; «Ver gráfica» con píldora roja y regreso automático a los 30 s.
- Un ciclo exitoso con alarmas, avisos o pérdida de Referencia muestra la píldora ámbar «Observaciones (N)».
- **FC-08:** con la Referencia sin lectura, en carga sólida el ciclo termina **COMPLETADO con una observación** (ya no NO CONFORME). En carga líquida termina en **FALLO CIC-19**. Es un riesgo aceptado por Cristian (HAZ-T21-01).
- Todas las confirmaciones de Ciclo en curso y Preciclo usan `ModalConfirmacion`. CANCELAR envía el token de la sesión, si la hay (FC-12).
- En Preciclo, una puerta sin actuador se muestra con un **indicador de estado sin acción** (FC-11).
- **FC-10:** ningún botón revisado recorta su texto. «Confirmar y llevar a estado seguro» ya cabe.

## Qué cambió, por FC

| FC | Cambio | Archivos principales | Pruebas |
|---|---|---|---|
| FC-01 | Panel de fin de ciclo en el rectángulo de la gráfica, vista por defecto en fallo/cancelado/emergencia. Un resultado o una terminación desconocidos se muestran como fallo. Se eliminaron `cargaNoEsteril` y la franja NO CONFORME. Los avisos de seguridad y sin conexión pasaron a `capaAvisos`, por encima del panel y de la gráfica. | `Componentes/PanelFinCiclo.qml`, `Pantallas/PantallaCicloEnCurso.qml` | `test_t21_panel_fin_ciclo_qml.py`, `test_t21_pantalla_fin_ciclo_qml.py`, `test_s2b_d8_2_16_carga_no_esteril_qml.py` |
| FC-02 | Fila de causa: fallo de fase («Fallo en <fase>», título del catálogo, descripción con valores, QUÉ HACER, meta), paro de emergencia (SIS-01), cancelación (barra gris, «Cancelado por <usuario>»), fallo sin código («Fallo del ciclo» + motivo crudo). | `ui_qml/domain/fin_de_ciclo.py` | `test_t21_fin_de_ciclo_ui.py` |
| FC-03 | Alarmas del ciclo en orden de aparición, sin la causa. Toda alarma en CICLO queda con `ciclo_id`, también en el arranque y mientras se espera la confirmación; se corrigió en el escritor, que resuelve el id en su propio hilo con espera acotada. | `historial_alarmas.py`, `cycle_logger.py`, `context.py`, `db_manager.get_alarmas_de_ciclo` | `test_t21_alarmas_con_ciclo.py` |
| FC-04 | Acordeón con una sola fila abierta, chevron y `TextoAjustable` en el título. | `Componentes/FilaAcordeon.qml` | `test_t21_panel_fin_ciclo_qml.py` |
| FC-05 | «Ver gráfica», píldora roja «Alarmas (N) · SS s» y regreso automático (`RegresoPanel.regresoPanelS = 30`). Un toque reinicia la cuenta, un modal la detiene, y el regreso cierra la pantalla completa. | `RegresoPanel.qml`, `PildoraFinCiclo.qml`, `PantallaCicloEnCurso.qml` (`detectorToques`) | `test_t21_pantalla_fin_ciclo_qml.py` (tiempo inyectable) |
| FC-06 | `fase_terminacion` y los estados `fallida`/`interrumpida` en el progreso y en `BarraFases` (rojo y ámbar). | `core/runtime/progreso_ciclo.py`, `BarraFases.qml`, `ciclo_en_curso.py` | `test_t21_fin_de_ciclo_backend.py`, `test_t21_fin_de_ciclo_ui.py` |
| FC-07 | Exitoso: la gráfica sigue siendo la vista por defecto. Con alarmas o una observación aparece la píldora ámbar, que abre el panel «OBSERVACIONES DEL CICLO» (sin regreso automático). | `PantallaCicloEnCurso.qml`, `fin_de_ciclo.py` | `test_t21_pantalla_fin_ciclo_qml.py` |
| FC-08 | Sólido: SEN-11 con los textos nuevos, observación en `avisos_ciclo`, sin apertura automática; se retiró NO CONFORME (estado, `/cycle/acknowledge-no-conforme`, 409, franja, botón, `reconocerNoConforme`). Líquido: FALLO CIC-19. Ticket, PDF, historial y **correo** (una línea por observación en el cuerpo) muestran «Observación: …». Los ciclos viejos NO CONFORME se muestran como quedaron. | `states/ciclo.py`, `catalogo.py`, `ticket_formatter.py`, `rutas/ciclo.py`, `_comun.py`, `acciones_ciclos.py`, `registro_riesgos.md` (HAZ-T21-01), `CLAUDE.md` | `test_t21_fin_de_ciclo_backend.py`, `test_t12_c13_7b_*`, `test_t16_s5_*` (reducidas al historial), `test_t21_fin_de_ciclo_ui.py` (correo) |
| FC-09 | `ModalConfirmacion` para cancelar, confirmar (exitoso con nota de observación, o fallo/cancelado), estado seguro tras un paro y `confirmarSinRegistro` de Preciclo. Los botones miden 340 o lo que pida su texto. | `Componentes/ModalConfirmacion.qml`, las dos pantallas | `test_cancelacion_ciclo_en_curso_qml.py`, `test_t2_p6_dialogo_estado_seguro.py`, `test_t21_*` |
| FC-10 | Ver la sección «Textos corregidos». | P4 y ola 2 | `test_t21_textos_caben_qml.py` (nueva) |
| FC-11 | `/status.puertas_con_actuador` (misma regla que el endpoint de puertas; ante un error, false). `UiBridge.puertaConActuador`: solo un True estricto. `IndicadorPuerta` muestra CERRADA (solo con `CERRADO` y datos vigentes), ABIERTA (cualquier otro estado) o «PUERTA —» sin datos. No tiene MouseArea. | `rutas/sistema.py`, `ui_bridge.py`, `Componentes/IndicadorPuerta.qml`, `PantallaPreciclo.qml` | `test_t21_indicador_puerta_qml.py`, `test_t21_fin_de_ciclo_backend.py`, `test_t21_fin_de_ciclo_ui.py` |
| FC-12 | `POST /cycle/abort` acepta `Authorization: Bearer` opcional. `cancelado_por` queda en el estado, en la bitácora (`ciclo_cancelado`) y en el ticket. La UI envía el token de la ventana. | `rutas/ciclo.py`, `cliente/ui_service_backend.abort_cycle` | `test_t21_fin_de_ciclo_backend.py`, `test_t21_fin_de_ciclo_ui.py` |
| FC-13 | `terminacion` y `alarmas_ciclo` en `/cycle/current/progress`. `normalizar_progreso` valida y falla cerrado. | `progreso_ciclo.py`, `_comun.py`, `ciclo_en_curso.py`, `progreso_ciclo.py` (puente: `armarFin`, `revisionFin`, `faseTerminacion`) | ídem |

Base de rutas de la tanda 15 (`docs/informes/tanda15/base/`) actualizada solo en lo justificado: se retiró `/cycle/acknowledge-no-conforme` (FC-08) y se agregó la cabecera `authorization` opcional a `/cycle/abort` (FC-12).

## Revisión de seguridad (R) y correcciones

Un subagente revisó el diff completo en solo lectura. No encontró hallazgos críticos ni altos. Todo lo que encontró quedó corregido (2c58ff9):

- **SAF-01 (MEDIA):** si el paro se liberaba con el modal de CONFIRMAR abierto, «Confirmar» llevaba a estado seguro sin la nota de fugas. Ahora el modal revalida `ackConfirmaEstadoSeguro` al aceptar y, si hace falta, abre el modal de estado seguro sin enviar nada. Los modales se cierran cuando cambia el resultado o el estado seguro pendiente.
- **SAF-02 (MEDIA):** una Referencia con una excursión aún sin confirmar que perdía la lectura descartaba la excursión, y con FC-08 el ciclo podía terminar COMPLETADO. Ahora esa excursión **se confirma**: la exposición se detiene y CIC-14 acota la espera (`EsterilizacionFase._confirmar_excursion`). Agregado a HAZ-T21-01. DECISIÓN SIN CONFIRMAR.
- **SAF-03 (BAJA):** un tipo de carga distinto de `"solido"` (desconocido, vacío o con otra grafía) se trata como líquido, tanto en `CicloState` como en `protocolo_fallo.es_liquido`.
- **SAF-04 (BAJA):** la observación de Referencia se ve aunque falte su fila SEN-11 en la base (por ejemplo, sin BD).
- **SAF-05 (BAJA):** el modal de cancelar se cierra si el ciclo termina con él abierto.

Preguntas abiertas de R, para Cristian:

1. `IndicadorPuerta` solo mira la conexión con el backend, no `estadoTarjeta`. Si el backend conserva el último `CERRADO` con la trama DI vencida, el indicador diría «PUERTA CERRADA». Hay que verificar en el banco qué publica `/status` en ese caso.
2. CIC-19 en líquidos se dispara con el mismo criterio que SEN-11, es decir, sin debounce propio. Un `None` aislado (código de diagnóstico PT100) aborta el ciclo. Es seguro, pero afecta la disponibilidad. ¿Se confirma?
3. Con la gráfica a pantalla completa, el aviso «sin conexión / tarjeta sin datos» queda tapado, como en `dev` (U4).
4. `/cycle/abort` ahora consulta la base (ciclo y auditoría) antes de responder. Con la base ocupada, la UI podría mostrar «no se pudo cancelar» aunque la cancelación ya se haya registrado.

La revisión V (compatibilidad histórica) no encontró bloqueantes. El token al cancelar y la observación en el correo, que ella señaló, se completaron en la ola 2. Quedan dos hallazgos bajos sin cambio:

- Una doble cancelación en el mismo tick escribe dos filas `ciclo_cancelado`.
- Sin base de datos, la bitácora de cancelación no lleva el número del ciclo.

## Decisiones sin confirmar

1. **P1, CIC-19:** usa `fase_ciclo = "SENSOR_AUSENTE"` y el protocolo de fallo normal (en líquidos, solo la descompresión lenta). Con un tipo de carga ilegible o desconocido, el ciclo aborta (SAF-03).
2. **P1, auditoría de cancelación:** una cancelación ahora siempre escribe la fila `ciclo_cancelado` (antes no escribía ninguna).
3. **P1, `fase_terminacion` y `alarmas_ciclo`:** sin registros de fase, `fase_terminacion` es `null` (no se adivina). De `alarmas_ciclo` se quita solo la fila más reciente con el código de la causa. FC-03 espera hasta 5 s por el id de un ciclo que todavía se está creando.
4. **Ola 2, descripción de la causa:** es la plantilla con valores, sin el prefijo «CÓDIGO · título:» de `motivo_fallo` (el código y el título ya están en el subtítulo y en la meta). Sin valores, se usa el motivo registrado.
5. **Ola 2, resultado desconocido en `/progress`:** se sigue tratando como «sin resultado» (no como fallo). Tratarlo como terminado con el ciclo en marcha quitaría CANCELAR. La falla cerrada de FC-01 rige dentro del panel: una terminación desconocida se muestra como fallo.
6. **Ola 2, textos nuevos:** el subtítulo del panel de observaciones dice «Ciclo NN terminó con éxito a las HH:MM». El título del modal sin registro, «Iniciar sin registro», es nuevo (`ciclo.sin_bd_titulo`); el cuerpo y el botón conservan su texto.
7. **Ola 2, píldora:** se centró en y 58 de la gráfica para no pisar la leyenda. La píldora ámbar dice «Observaciones (N)», como la spec (el mockup 09 dice «Observación (1)»).
8. **P2:**
   - En modo observaciones se abre primero la primera observación.
   - El rótulo de alarmas lleva «(N)» solo si N > 0.
   - Cerrar un modal reinicia la cuenta de 30 s.
   - `ModalConfirmacion` copia el estilo de `PanelModal` en vez de envolverlo.
   - La barra de cancelación es `textoGuia`.
9. **P3, indicador de puerta:** `DESCONOCIDO`, `ERROR`, `ABRIENDO`, `CERRANDO` y `ATRAPADA` con conexión se muestran como «PUERTA ABIERTA». El gris queda solo para sin datos o estado vacío. El texto usa tamaño fijo 22 con ajuste de línea (la ola 2 retiró `Fit`, que hacía que la caja del texto se midiera fuera de la tarjeta).
10. **P4:**
    - Los botones de diálogo se ensanchan antes que abreviar o reducir la letra, para no cambiar el sentido de una orden de seguridad.
    - Confirmar puede quedar más ancho que Cancelar.
    - `BotonFormulario` sin ancho ahora toma el ancho de su texto.
11. **R, SAF-02:** confirmar la excursión al perder la lectura (ver arriba).

## Textos corregidos (FC-10)

| Archivo | Texto (es / en) | Solución |
|---|---|---|
| `Componentes/DialogoConfirmacion.qml` | «Confirmar y llevar a estado seguro» / «Confirm and bring to safe state» (se salía en es a 1024 px; además cubre sus otros usos) | El botón mide 340 o lo que pida su texto, dentro del ancho útil de la tarjeta; `HorizontalFit` con `Escala.fuenteMinima` como respaldo. |
| `Componentes/PanelModal.qml` | Botón de cierre («Seguir editando», «Cerrar»…) | El mismo patrón, preventivo. |
| `Componentes/SeccionEstadoSeguro.qml` | «Confirmar y llevar a estado seguro», «En curso…», «Asignar sonda Principal» | `HorizontalFit` con mínimo como respaldo. |
| `Componentes/BotonFormulario.qml` | «Cerrar», «psig»/«inHg» | Error real: sin ancho fijado medía 0. Ahora toma el ancho de su texto, con `HorizontalFit` si el ancho fijo no alcanza. |
| `Pantallas/OpcionesParametrosCiclo.qml` | Aviso con «Cerrar» | La banda del aviso contiene el botón nuevo (97 px). |
| `Componentes/SelectorSegmentos.qml` | Rótulos de segmento | `HorizontalFit` con mínimo como respaldo. |
| `Componentes/ModalConfirmacion.qml` (ola 2) | «Continue without record» (en; no cabía en 340) | Botones de 340 o lo que pida el texto, como `DialogoConfirmacion`. |
| `Pantallas/PantallaPreciclo.qml`, `BotonAccion` (ola 2) | «ABRIR PUERTA», «CERRAR PUERTA», «INICIAR CICLO», «RECONOCER FALLA» | Ancho hasta el borde del botón con `HorizontalFit` (mínimo `Escala.fuenteMinima`). Hoy ninguno se reduce. |
| `Componentes/IndicadorPuerta.qml` (ola 2) | «PUERTA CERRADA» / «DOOR CLOSED» | Tamaño fijo con ajuste de línea; el alto sigue al contenido. |

Revisados sin cambios: `BotonPildora` (ya se ensancha), las barras inferiores (solo íconos), las pestañas de Opciones, Usuarios y Reportes (U10b) y `SelectorPeriodo`.

## Usos de `DialogoConfirmacion` que quedan (no se tocan, FC-09)

| Archivo | `objectName` |
|---|---|
| `Componentes/PanelEquipo.qml` | `confirmarApagar` (el panel se abre también desde Preciclo; en Ciclo en curso no se puede apagar, AJ-01) |
| `Pantallas/Instalacion.qml` | `dialogoInstalar` |
| `Pantallas/Opciones.qml` | `dialogoSalirOpciones`, `dialogoCambiarSeccion` |
| `Pantallas/OpcionesAvanzadas.qml` | `dialogoCambiarAvanzadas` |
| `Pantallas/OpcionesCalibracionAtm.qml` | `dialogoConfirmarCalibracionAtm` |
| `Pantallas/OpcionesCalibracionSensor.qml` | `dialogoCalibracionFueraDeRango`, `dialogoRestaurarCalibracion` |
| `Pantallas/OpcionesEntradasSalidas.qml` | `dialogoModoPrueba` |
| `Pantallas/OpcionesManejoCiclos.qml` | `dialogoBorrarManejo` |
| `Pantallas/OpcionesMantenimiento.qml` | `confirmarMantenimiento` |
| `Pantallas/OpcionesParametrosCiclo.qml` | `dialogoGuardarAjuste` |
| `Pantallas/OpcionesParametrosEquipo.qml` | `dialogoMaquinaEquipo`, `dialogoReinicioImpresora`, `dialogoGuardarAjusteEquipo` |
| `Pantallas/OpcionesReasignacion.qml` | `dialogoAlertaReasignacion`, `dialogoReforzadaReasignacion`, `dialogoReinicioReasignacion`, `dialogoFabricaReasignacion`, `dialogoVerificarReasignacion` |
| `Pantallas/OpcionesRespaldo.qml` | `dialogoRestaurar` |
| `Pantallas/OpcionesUsuarios.qml` | `confirmarActivoUsuario`, `confirmarRestablecerClave` |

## Qué verificar en pantalla (capturas frente a mockups)

Las capturas están en `docs/informes/tanda21/capturas/` (800 × 1280, mismos nombres que `docs/diseno/mockups/fin_de_ciclo/`). Las generan `python tests/banco/t21_capturas_fin_ciclo.py` y el arnés `Pruebas/PruebaFinDeCiclo.qml`, con los textos reales de `fin_de_ciclo.py`.

- **01/02:**
  - La fase cortada (Esterilización) sale en **rojo** en la barra de fases (FC-06; el mockup aún la pinta como completada).
  - Las alarmas van en orden cronológico ascendente (en el mockup, Uniformidad está antes que Presión de chaqueta).
  - La meta va en una línea: «Fase · fecha hora · Código».
- **03:**
  - La píldora roja queda a la izquierda de «Tiempos», un poco más arriba que en el mockup para no tapar la leyenda.
  - En el equipo, la cuenta baja de 30 a 0 y vuelve sola al panel.
- **04, 07, 08, 10, 11:** modales con «Volver» de contorno y la acción a color. En el 07 la nota ámbar de fugas; en el 10 la nota de observación con la hora y la fase.
- **05:** barra gris y «Cancelado por cristian en la fase Esterilización». Esterilización sale en ámbar (interrumpida).
- **06:** «Paro de emergencia», «Activado en la fase Esterilización», código SIS-01.
- **09:** píldora ámbar «Observaciones (1)».
- **preciclo_01:** botón ABRIR PUERTA de hoy (con actuador).
- **preciclo_02/03:** indicador azul claro «PUERTA CERRADA» / ámbar «PUERTA ABIERTA», con el ícono teñido.
- **preciclo_04:** gris «PUERTA —», sin ícono.
- **En el equipo:**
  - Que tocar el indicador no haga nada.
  - Que con los dos tipos de puerta se vea lo correcto (`door_type` del perfil).
  - Que con la tarjeta desconectada el indicador no quede en «CERRADA» (pregunta abierta 1).
- **Banco:**
  - Desconectar la Referencia en ESTERILIZACION con carga sólida (COMPLETADO + píldora ámbar + nota en el modal + línea en ticket, PDF y correo; sin apertura automática) y con carga líquida (FALLO CIC-19).
  - Cancelar con sesión abierta y sin ella.

## Suite

`pytest tests -n auto`: 9029 passed, 11 skipped, 3 xfailed y 1 fallida por la caída conocida de un trabajador de xdist (`test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`, PySide, solo en paralelo; pasa en serie; ya figura en R20 y en ajustes_28oct). Salida completa en `suite_raw.txt`.

Pruebas que fallaban ya en `dev` y quedaron al día:
- `test_aj03_globo_grafica_qml.py` y `test_t17_s4_alarmas_qml.py`: el sufijo «(monitoreo)» se retiró el 28-oct (6f06dd0).
- `test_ver_version.py`: comparaba contra alpha.7, que ya es la vigente.

## Entrega

`python tools/entrega/compilar_entrega.py --con-generador` desde `dev` (3531c19), salida 0:

- La suite en paralelo dio la misma caída conocida de `test_home_view`, y la herramienta la repitió en serie: verde.
- Commit `e8d5712 chore(ver): 1.0.0-alpha.8` y etiqueta anotada `v1.0.0-alpha.8`.
- Carpeta `entrega/v1.0.0-alpha.8_2026-10-28/` (Setup, zip, LEEME, SHA256SUMS, usb/), con el generador de códigos.
- El .exe reporta 1.0.0-alpha.8.
- Los 38 archivos sin seguimiento ajenos a la tanda (`.claude/agents/`, `Claude outputs/`, `_suites_t11/`, `CERRADO.txt` viejos…) solo dieron aviso y no bloquearon. **No se tocó `.git/info/exclude`**, así que no hay nada que revertir.
- Sin push. Para publicar: `git push origin dev v1.0.0-alpha.8`. Ojo: la herramienta avisó que `origin/dev` (70a242e) no coincide con `dev` local según la última consulta al remoto; revisar antes de empujar.
