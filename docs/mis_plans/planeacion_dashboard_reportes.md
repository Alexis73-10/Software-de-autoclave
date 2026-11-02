# Planeación — Dashboard de Reportes (pantalla completa)

Versión 1.1 · 2026-11-02 · Autor: Claude (chat) · Aprueba: Cristian
Estado: listo para tanda. Preguntas P-01 a P-05 resueltas (§12). Incluye el ajuste menor AJ-01 (§13).
Mockup aprobado: lienzo «Dashboard de reportes — Autoclave», artboard «Reportes — v2, estilo de la referencia» (https://claude.ai/artifact/5FF9v57Jxp5AR9W46QQkNn). El mockup es la referencia visual; este documento es la referencia funcional. Si discrepan, manda este documento.

---

## 1. Objetivo y alcance

Reemplazar la ventana flotante de Reportes del Menú Principal (`ventanaReportes`, pestañas Resumen y Consolidado) por una pantalla completa de solo lectura con indicadores, gráficas y un calendario de ejecución por programa.

Dentro del alcance:
- Pantalla QML `Pantallas/Reportes.qml` y sus componentes.
- Endpoints de solo lectura nuevos en `backend/rutas/reportes.py` y un servicio puro en `services/domain/reportes/`.
- Periodo «Año» en `utils/periodos.py` y en las rutas de reportes.
- Regla de envío por correo sin sesión (REP-13).
- Textos es/en, pruebas, riesgos y trazabilidad.

Fuera del alcance:
- Registro del resultado de lectura de la hoja Bowie & Dick (no existe en el software y no se agrega).
- Cualquier bloqueo, aviso o alarma por falta de Bowie & Dick (decisión de Cristian: solo informativo).
- Cambios en la máquina de estados, fases, alarmas o control.
- Rediseño del ticket térmico y de los PDF (P-05: tanda posterior).
- Bowie & Dick por turnos (FUT-01, próxima versión).

## 2. Decisiones de Cristian (2026-11-02)

- DR-D01: el dashboard es pantalla completa y reemplaza la ventana flotante. «Consolidado» deja de ser pestaña y queda como acción «Enviar consolidado».
- DR-D02: entran en esta versión duración media, comparación con el periodo anterior, alarmas del periodo y ciclos por operador.
- DR-D03: el calendario de Bowie & Dick se reemplaza por un calendario de ejecución por programa, con selector de programa. Motivo: el Bowie & Dick debe completarse con éxito todos los días.
- DR-D04: estados del día: con éxito, éxito con fallo previo (distinto, para diagnóstico), sin éxito, faltó (solo programa 01), no ejecutado (demás programas), sin operación (día sin ningún ciclo).
- DR-D05: tocar un día abre la lista de ciclos de ese programa en ese día, con acceso a su detalle como en el Historial.
- DR-D06: el selector de programa muestra solo los programas con ciclos en el periodo seleccionado, con una excepción (P-01): el programa 01 aparece siempre que el equipo lo tenga y el periodo tenga algún ciclo, y es el seleccionado por defecto.
- DR-D07: en «Año», vista de 12 meses interactiva; al tocar un mes se despliega su vista de mes.
- DR-D08: el calendario es solo informativo: no bloquea ciclos ni avisa en el Menú Principal.
- DR-D09: Reportes sigue en el Menú Principal, sin inicio de sesión. Todas las secciones son visibles sin sesión.
- DR-D10: sin sesión, el correo solo se envía a los destinatarios guardados; escribir una dirección a mano exige sesión iniciada.
- DR-D12 (P-02): un intento no exitoso posterior a todos los éxitos del día no cambia el estado: el día queda «con éxito» y el fallo se ve en el panel del día.
- DR-D13 (P-03): los ciclos guardados como NO CONFORME (anteriores a la tanda 21) cuentan como intento sin éxito en el calendario.
- DR-D14 (P-04): «Ciclos por día» con Día por hora, Semana y Mes por día, Año por mes.
- DR-D15 (P-05): ticket térmico y PDF de resumen/consolidado sin secciones nuevas en esta tanda (solo aceptan el periodo «anio»).
- DR-D16: el deslizador de inicio de ciclo de la pantalla previa al ciclo pasa a un verde más claro, tipo pastel, acorde con el resto de la pantalla (AJ-01, §13).
- DR-D11: estilo visual del mockup v2: fondo gris claro, tarjetas blancas, curvas suavizadas, dona y anillos, conservando la identidad de la app (barra superior navy, azul primario, colores de estado, Inter, tokens de `docs/diseno/tokens.css`).

## 3. Estado actual del código (leído el 2026-11-02)

- `GET /report/summary` (periodo `dia|semana|mes`) arma totales por resultado, por programa y causas de fallo con `services/domain/reportes/resumen_periodo.resumir()` sobre `DbManager.get_conteo_resultados()`. Sin token.
- `GET /report/failures` (D8-5.6) lista los ciclos de una causa de fallo, paginados. `POST /report/summary/print` imprime el resumen en la térmica.
- La ventana `ventanaReportes` vive en `qml/Pantallas/MenuPrincipal.qml` (≈ líneas 779–1000) con `SelectorPeriodo`, `ResumenPeriodo`, `ListaCiclos` y `SelectorDestino`. El controlador de datos es `raiz.reporte` (ReporteResumen) y las acciones son `raiz.acciones` (AccionesCiclos: imprimir y enviar).
- Tabla `ciclos`: `numero_ciclo`, `fecha_inicio`, `fecha_fin`, `tipo_ciclo` (id del programa), `nombre_ciclo`, `numero_programa` (columna agregada por migración; NULL en ciclos anteriores), `resultado`, `operador`, `motivo_fallo`, `codigo_fallo`, `avisos_ticket`, etc. Fechas ISO local sin zona (`datetime.now().isoformat()`).
- `operador` se guarda desde O1 (tanda 3) en `CycleLogger` (`estado.operador_inicio`).
- Tabla `alarmas_historial`: `codigo`, `nivel`, `titulo`, `aparecida`, `resuelta`, `ciclo_id`. Niveles del catálogo: INFORMATIVO, AVISO, ALARMA, FALLO_CRITICO (`state_machine/alarms/catalogo.Nivel`).
- `utils/periodos.rango/es_actual/desplazar` solo aceptan `dia|semana|mes`.
- El correo lo envía el proceso de la UI (`ui_qml/exportacion/correo.py`); el backend solo audita con `POST /email/sent`. La dirección manual se escribe en `Componentes/SelectorDestino.qml` (`manual`, «Solo este correo», «Este correo y los guardados»), hoy sin condición de sesión.
- Mantenimiento: `GET /maintenance` y `GET /maintenance/records` ya existen.

## 4. Hallazgos

- DR-H01 (ALTA, seguridad de la información): el calendario muestra si el ciclo del programa 01 terminó COMPLETADO, no si la hoja Bowie & Dick fue conforme (eso se lee a mano y el software no lo registra). Un texto como «conforme» o «equipo apto» induciría a liberar el equipo con base en un dato que el software no tiene. Mitigación obligatoria: los textos dicen «Completado», «Con éxito (ciclo completado)», nunca «conforme» ni «apto»; leyenda fija bajo el calendario: «Muestra el resultado del ciclo. La lectura de la hoja de prueba no se registra en el equipo.» Riesgo HAZ-REP-01 (§10).
- DR-H02 (MEDIA): ciclos anteriores a la columna `numero_programa` la tienen en NULL. Regla: número = `ciclos.numero_programa`; si es NULL, el número del programa actual con ese `tipo_ciclo` (como `_ciclo_json`); si tampoco existe, el ciclo cuenta para totales y para «sin operación/no ejecutado» del día, pero no aparece en el selector ni en el calendario por programa. El Bowie & Dick se identifica solo por número de programa 1 (decisión de numeración vigente).
- DR-H03 (MEDIA): la app puede cambiar la hora del sistema (decisión de estación sin NTP) y las fechas son de reloj de pared. Una duración `fecha_fin - fecha_inicio` puede salir negativa o absurda. Regla: la duración media solo usa ciclos COMPLETADOS con duración > 0 y ≤ 24 h; el endpoint publica cuántos se excluyeron (`duraciones_excluidas`) y la pantalla lo indica en el pie de la tarjeta si es mayor que 0.
- DR-H04 (MEDIA): `utils/periodos` no tiene «anio». Se agrega en `rango`, `es_actual` y `desplazar`, y en los `Literal` de todas las rutas `/report/*` (incluido `/report/summary/print` y el envío del consolidado). Sin cambiar el comportamiento de los otros periodos.
- DR-H05 (MEDIA): el mockup rotula las alarmas ALTA/MEDIA/BAJA; el sistema tiene 4 niveles (Informativo, Aviso, Alarma, Fallo crítico). La pantalla usa los niveles del catálogo con los mismos colores y textos que ya usa el panel de alarmas (`FilaAlarma.qml`), no una prioridad nueva. El título se toma del catálogo por código en el idioma activo (no del texto guardado en `alarmas_historial.titulo`) y el código se muestra con `catalogo.codigo_visible()` (MES-04). Código desconocido: se muestra el título guardado.
- DR-H06 (MEDIA): pendiente reportado el 20-oct: un correo escrito a mano no llega aunque el software indica «enviado». Esta tanda toca `SelectorDestino`, así que incluye una etapa de diagnóstico (§11, etapa F). Se corrige solo si la causa queda demostrada con una prueba; si no, se documenta en el informe y no se cambia nada.
- DR-H07 (BAJA): el comentario de `backend/rutas/_comun._ciclo_json` dice que `CycleLogger` no guarda el operador; ya lo guarda desde O1. Corregir el comentario.
- DR-H08 (BAJA): el control del correo sin sesión (DR-D10) solo puede aplicarse en la UI, porque la UI envía el SMTP directamente. Se acepta: la estación está en modo quiosco y el envío queda auditado en `correo_enviado`. Va al riesgo HAZ-REP-02.
- DR-H09 (BAJA): con dos puertas, cada proceso de UI abre su propio Reportes. Es solo lectura; no hay conflicto. Cada pantalla conserva su propio periodo y programa seleccionado.

## 5. Pantalla y navegación (REP-01)

- La tarjeta «Reportes» del Menú Principal (`tarjetaReportes`) navega a `Pantallas/Reportes.qml`; se elimina `ventanaReportes` de `MenuPrincipal.qml` y su código asociado que quede sin uso (sin romper `seleccionarTarjeta("reportes")` del arnés: ahora navega).
- Base 1200×1920 vertical, escala con la convención `m()`. Barra superior (título REPORTES, equipo y puerta, reloj) y barra inferior (Inicio a la izquierda, Salir a la derecha, como en el Menú Principal) fijas; el contenido entre ambas es un `Flickable` vertical.
- Orden de secciones (igual al mockup v2): Periodo, Indicadores, Resultado, Ciclos por día, Por programa, Calendario de ejecución, Causas de fallo, Mantenimiento / Alarmas / Por operador (tres columnas), Acciones.
- La pantalla se abre en «Mes» con el mes actual y el programa 01 seleccionado (DR-D06/P-01); si el equipo no tiene programa 01 o el periodo no tiene ciclos, el primero disponible.
- Volver (Inicio) regresa al Menú Principal. No hay sesión implicada.
- Textos que no caben bajan la letra (`HorizontalFit`/`TextoAjustable`); nunca `elide` (regla D8-5.4).
- Colores solo desde el módulo de tema (`Tema`/`Colores`), sin hexadecimales en QML (regla de `tokens.css`).

## 6. Periodo (REP-02)

- Selector Día | Semana | Mes | Año y flechas anterior/siguiente. No se navega más allá del periodo actual (como hoy).
- Título: «Octubre 2026», «Semana del 26/10 al 01/11», «Lunes 2 de noviembre», «2026». Subtítulo: rango y «comparado con …» (REP-03).
- Todo el dashboard (indicadores, gráficas, listas y calendario) responde al periodo.
- Calendario: en Día y Semana muestra el mes que contiene el periodo, con los días del periodo resaltados; en Mes, el mes; en Año, la vista de 12 meses.

## 7. Secciones

### REP-03 Indicadores y comparación
- Ciclos (total del periodo), Éxito (% de COMPLETADOS sobre el total, entero), Fallos (con «N cancelados · N sin cierre» en el pie), Duración media (min, ver DR-H03).
- Agrupación de resultados idéntica a `resumen_periodo.resumir()` (`progreso_ciclo.resultado`).
- Comparación: mismo indicador en el periodo de calendario inmediatamente anterior y de igual tipo (mes anterior, semana anterior, día anterior, año anterior). Se muestra la diferencia absoluta (ciclos, fallos, minutos) o en puntos porcentuales (éxito), con flecha. Si el periodo anterior no tiene ciclos: «Sin datos del periodo anterior». Colores: más éxito y menos fallos en verde; lo contrario en rojo; ciclos y duración en gris (no son buenos ni malos).
- Minigráfica de cada tarjeta: la misma serie de REP-05 (por día del periodo) para ciclos, éxito diario, fallos acumulados y duración media diaria.

### REP-04 Resultado
- Dona con COMPLETADOS, fallos, cancelados y sin cierre; centro con el % de éxito; leyenda con cantidad y %. Sin ciclos: dona gris y «Sin ciclos en el periodo».

### REP-05 Ciclos por día
- Curva de área (total) y línea (completados); punto rojo en cada intervalo con al menos un fallo. Al tocar un punto o intervalo, burbuja con fecha, total y fallos (como el mockup); se cierra sola a los 5 s.
- Granularidad (DR-D14): Día → por hora (24), Semana y Mes → por día, Año → por mes.
- Implementación con `Shape`/`PathCubic` (Catmull-Rom → Bézier con puntos de control acotados al área), sin SOUP nuevo. Eje y autoajustado al máximo con paso entero.

### REP-06 Por programa
- Lista de programas con ciclos en el periodo: número, nombre, detalle de incidencias, barra de % de éxito y cantidad. Orden por cantidad descendente (como hoy). Barra verde con éxito ≥ 95 %, naranja por debajo (umbral visual, sin efecto de control).

### REP-07 Calendario de ejecución por programa
Definiciones:
- Intento: un ciclo del programa P con `fecha_inicio` en el día local D.
- Éxito: `progreso_ciclo.resultado(resultado) == "exitoso"` y el ciclo no está guardado como NO CONFORME (`ticket_formatter.ciclo_no_conforme`); un NO CONFORME cuenta como intento sin éxito (DR-D13).
- Ciclo activo: el ciclo en curso (`resultado` NULL y es el ciclo activo del equipo); no cuenta como intento fallido.
- N(D): total de ciclos de cualquier programa iniciados en D, excluido el activo.

Estado del día D para el programa P (en este orden):
1. `futuro`: D posterior a hoy.
2. `en_curso`: el único intento de P en D es el ciclo activo.
3. `sin_operacion`: N(D) = 0 y no hay ciclo activo.
4. Con intentos de P en D (sin contar el activo):
   - `exito`: hay éxito y ningún intento no exitoso anterior al último éxito.
   - `exito_fallo_previo`: hay éxito y al menos un intento no exitoso anterior al último éxito.
   - `sin_exito`: ningún éxito (fallos, cancelaciones, sin cierre).
   - Un intento no exitoso posterior a todos los éxitos no cambia el estado (`exito`); el panel del día lo muestra (DR-D12).
5. Sin intentos de P en D y N(D) > 0: `falto` si P es el programa 1; `no_ejecutado` en los demás.

Presentación:
- Selector de programa (píldora con desplegable): el programa 01 si el equipo lo tiene y el periodo tiene algún ciclo (aunque no tenga intentos del 01), más los programas con al menos un intento en el periodo; número y nombre; el 01 primero.
- Fila de conteo por estado del periodo visible.
- Vista de mes: cuadrícula lunes a domingo, círculos táctiles ≥ 64 px. Colores y forma (no solo color, para distinguir sin depender del tono): con éxito = relleno verde claro; éxito con fallo previo = verde claro + punto rojo; sin éxito = rojo sólido; faltó = blanco con borde rojo grueso; no ejecutado = gris; sin operación = borde punteado; en curso = azul primario; futuro = deshabilitado.
- Panel del día (a la derecha): fecha, estado, explicación y lista de intentos del programa ese día en orden de inicio (número de ciclo, hora, operador, resultado con causa). Tocar un intento abre el detalle del ciclo como desde el Historial (curva, imprimir, enviar). Sin día elegido: «Toque un día para ver sus ciclos». Para `falto`: «No se ejecutó Bowie & Dick. El equipo realizó N ciclos de otros programas ese día.»
- Vista de año: 12 tarjetas de mes con mini cuadrícula y resumen («Sin novedad», «N con fallo previo», «N sin éxito o faltó», «Sin datos»); al tocar un mes se abre su vista de mes con un botón «Ver año». Meses sin datos (anteriores a la instalación o futuros) deshabilitados.
- Leyenda fija de DR-H01.

### REP-08 Causas de fallo
- Igual que hoy (D8-5.6): cada causa lleva a la lista paginada de sus ciclos y de ahí al detalle. Dos columnas.

### REP-09 Mantenimiento
- Solo lectura desde `GET /maintenance` y `GET /maintenance/records`: anillo «ciclos desde el último preventivo / intervalo», «próximo en N ciclos», fecha y técnico del último preventivo, correctivos en el periodo y solicitudes de repuesto anotadas en el periodo. No depende del periodo salvo los dos últimos datos. Si no hay preventivo registrado: «Sin preventivo registrado».

### REP-10 Alarmas del periodo
- Alarmas con `aparecida` en el periodo, agrupadas por código: título (catálogo, idioma activo), nivel (DR-H05) y cantidad; total y barra de proporción por nivel. Orden: nivel descendente y luego cantidad. Máximo 8 filas y «Ver todas» que abre la lista completa del periodo (paginada) en un panel; tocar una abre `VentanaDetalleAlarma`.

### REP-11 Por operador
- Ciclos iniciados en el periodo agrupados por `ciclos.operador`; vacío = «Sin operador». Iniciales en círculo, cantidad y barra relativa al mayor. Máximo 5 filas y el resto como «Otros (N)».

### REP-12 Acciones
- Imprimir resumen (térmica, `POST /report/summary/print`, ahora acepta «anio»), Enviar resumen (PDF de `pdf_resumen`), Enviar consolidado (PDF de `pdf_consolidado`). Contenido de ticket y PDF sin cambios en esta tanda (DR-D15), salvo aceptar el periodo «anio».
- El consolidado de un año puede ser muy grande: si el periodo tiene más de 300 ciclos, se pide confirmación con la cantidad y el tamaño estimado antes de generar. (Umbral a confirmar en el banco con el tamaño real del PDF.)

### REP-13 Correo sin sesión (DR-D10)
- `SelectorDestino` recibe `sesionActiva` (de la sesión de la UI). Sin sesión: se ocultan «Otro correo», «Solo este correo» y «Este correo y los guardados»; se muestra la lista de guardados y la nota «Inicie sesión para escribir otro correo». Sin destinatarios guardados y sin sesión: «Enviar» deshabilitado con «No hay destinatarios guardados».
- Con sesión: comportamiento actual. La regla vigente «el rol técnico no modifica los destinatarios guardados» no cambia (escribir una dirección para un envío no modifica la lista).
- Aplica a todos los puntos donde se usa `SelectorDestino` (Reportes, detalle de ciclo desde Historial y desde Reportes). `correo_enviado` sigue auditando igual.

### REP-14 Idiomas y textos
- Todos los textos nuevos en `i18n/es.json` y `en.json` bajo `reportes.*` (pruebas de paridad existentes). Abreviaturas por clave `abrev.*` donde aplique. Fechas y números con el formato del idioma activo.

## 8. Backend (solo lectura, sin token, como `/report/summary`)

Servicio nuevo `services/domain/reportes/dashboard.py`, funciones puras y probadas sin base de datos:
- `estado_dia(intentos, n_dia, es_programa_1, activo_id, hoy, dia) -> str` (REP-07).
- `duracion_media(filas) -> (segundos | None, excluidas)` (DR-H03).
- `serie(filas, periodo, desde, hasta)` (REP-05), `periodo_anterior(periodo, fecha)`.
- `agrupar_alarmas(filas)`, `agrupar_operadores(filas)`.

DbManager (consultas de solo lectura, una por necesidad, sin N+1):
- `get_ciclos_periodo(desde, hasta)`: `id, numero_ciclo, fecha_inicio, fecha_fin, tipo_ciclo, nombre_ciclo, numero_programa, resultado, operador, avisos_ticket` ordenado por `fecha_inicio`.
- `get_alarmas_periodo(desde, hasta)`: `codigo, nivel, titulo` con `aparecida` en el rango.
- Índice `idx_ciclos_fecha_inicio` solo si no existe, vía la siguiente migración (`ESQUEMA_VERSION` + 1), idempotente. Si la tanda no lo considera necesario por volumen (un año ≈ 3.000 ciclos), lo justifica en el informe y no lo crea.

Endpoints nuevos en `backend/rutas/reportes.py`:
- `GET /report/dashboard?periodo=dia|semana|mes|anio&fecha=` → `{periodo, desde, hasta, anterior: {desde, hasta}, indicadores: {total, completados, fallos, cancelados, sin_cierre, exito_pct, duracion_media_s, duraciones_excluidas}, indicadores_anterior: {…} | null, serie: [{etiqueta, inicio, total, completados, fallos}], por_programa, causas_fallo, alarmas: [{codigo, codigo_visible, nivel, cantidad}], operadores: [{operador, cantidad}]}`. `por_programa` y `causas_fallo` con la misma forma de `/report/summary`.
- `GET /report/calendar?periodo=&fecha=&programa=<número>` → `{programas: [{numero, programa_id, nombre}], programa, dias: [{fecha, estado, intentos, exitos}]}`. Con `periodo=anio` devuelve los días del año; en los demás, los del mes que contiene el periodo. `programa` ausente o no disponible: el 01 según DR-D06; si no aplica, el primero de la lista.
- `GET /report/day-cycles?programa=&fecha=` → `{fecha, estado, ciclos: [_ciclo_json…]}` en orden de inicio, para el panel del día.
- `/report/summary`, `/report/failures` y `/report/summary/print` aceptan `anio`.
- Rutas fijadas: actualizar `docs/informes/tanda15/base/` y `tests/test_t15_rutas_equivalentes.py` con las rutas nuevas (es esperado que cambie el OpenAPI).
- `tests/test_arquitectura_capas.py` debe seguir pasando (el servicio no importa la UI).

## 9. UI (QML y Python)

- `ui_qml/domain/reporte_dashboard.py`: `presentable(respuesta, idioma)` que arma textos, porcentajes, colores semánticos (claves de tema, no hexadecimales) y la geometría de las curvas (puntos normalizados 0..1). QML solo dibuja (patrón de `reporte_resumen.py` y `fin_de_ciclo.py`).
- Controlador/puente `ReporteDashboard` (reemplaza a `ReporteResumen` en la pantalla; se conserva `ReporteResumen` mientras lo use otra pantalla): `cambiarPeriodo`, `anterior/siguiente`, `elegirPrograma`, `elegirDia`, `elegirMes`, `verAnio`. Consultas en hilo aparte, sin bloquear la UI; error de backend → tarjeta con «No se pudieron cargar los datos» y reintento.
- Componentes nuevos en `qml/Componentes/`: `TarjetaIndicador`, `GraficaArea`, `GraficaDona`, `AnilloProgreso`, `CalendarioEjecucion`, `MesMiniatura`, `PanelDiaCalendario`, `ListaProgramasReporte`, `ListaAlarmasPeriodo`, `ListaOperadores`. Reutilizar `SelectorPrograma`, `ListaCiclos`, `DetalleCiclo`, `SelectorDestino`, `VentanaDetalleAlarma`, `ModalConfirmacion`.
- Arnés `qml/Pruebas/PruebaReportes.qml` + `tests/banco/rep_capturas_reportes.py` con datos de ejemplo (los del mockup) para capturas a 1200×1920 y a 9:16 en ambos idiomas: Mes, Año, un día con fallo previo, un día «faltó», selector abierto y sin sesión en el correo.

## 10. Riesgos (agregar a `docs/riesgos/registro_riesgos.md`)

- HAZ-REP-01 (MEDIA): el calendario se interpreta como confirmación de que el equipo está apto para esterilizar, aunque solo refleja que el ciclo del programa 01 terminó COMPLETADO. Causa posible: textos ambiguos o un ciclo 01 completado con hoja no conforme. Control: DR-H01 (textos y leyenda), estado «éxito con fallo previo» visible, información solo de consulta. Verificación: prueba de textos (ninguna clave `reportes.*` contiene «conforme» ni «apto») y revisión de capturas.
- HAZ-REP-02 (BAJA): envío de reportes a una dirección no autorizada sin sesión. Control: REP-13 y auditoría `correo_enviado`; residual DR-H08 (control solo en la UI).
- HAZ-REP-03 (BAJA): indicadores erróneos por cambios de hora del sistema. Control: DR-H03.
- Requisitos nuevos en la matriz de trazabilidad con el siguiente número REQ libre, uno por REP-01 a REP-14, enlazados a sus pruebas con el marcador `req(id)`.

## 11. Etapas de la tanda (Claude Code)

Convenciones del repo: `docs/informes/dashboard_reportes/estado.md` al día tras cada commit, `CERRADO.txt` al final (o `BLOQUEADO:`), informe `R_informe.md` en español, máximo 4 subagentes a la vez y sin suite completa en los subagentes. No compilar la entrega; al cerrar, decir que no se compiló y dar el comando.

- A. Lectura y verificación del §3 contra el código; cualquier diferencia se anota en el informe antes de cambiar nada.
- B. `utils/periodos` con «anio» y rutas existentes con «anio» (DR-H04), con pruebas.
- C. Servicio `dashboard.py` con pruebas unitarias exhaustivas de `estado_dia` (cada estado, orden de evaluación, activo, programa 1 frente a otros, día sin ciclos, NULL en `numero_programa`), duración media (DR-H03) y periodo anterior (incluye enero → diciembre del año anterior y semanas que cruzan de año).
- D. DbManager y endpoints (§8), pruebas de API, rutas fijadas y arquitectura de capas.
- E. Dominio UI, controlador, componentes y pantalla; retiro de `ventanaReportes`; arnés y capturas.
- F. REP-13 en `SelectorDestino` + diagnóstico de DR-H06 (reproducir con un servidor SMTP local de prueba; corregir solo con causa demostrada).
- G. i18n es/en, DR-H07, riesgos y trazabilidad.
- J. AJ-01 (deslizador de inicio de ciclo), con capturas antes/después para aprobación visual de Cristian.
- H. Revisión de seguridad enfocada (un revisor): textos de DR-H01, que nada del dashboard escriba en BD o actúe sobre el equipo, y REP-13.
- K. Suite completa, unir a `dev`, `CERRADO.txt`.

Criterio de terminado: suite completa en verde, capturas del arnés en `docs/informes/dashboard_reportes/capturas/`, informe con la lista de archivos tocados, decisiones tomadas por la tanda (si alguna) marcadas como DECISIÓN SIN CONFIRMAR, y verificación en el banco pendiente para Cristian (navegación táctil, rendimiento de la vista Año con datos reales, envío sin sesión).

## 12. Preguntas resueltas (2026-11-02)

- P-01: de acuerdo con la excepción del programa 01 → DR-D06.
- P-02: el día queda «con éxito» → DR-D12.
- P-03: NO CONFORME cuenta como sin éxito → DR-D13.
- P-04: granularidad propuesta aprobada → DR-D14.
- P-05: ticket y PDF en una tanda posterior → DR-D15.

## 13. AJ-01 — Deslizador de inicio de ciclo más claro (ajuste menor, misma tanda)

Pedido de Cristian: el verde del deslizador «Iniciar ciclo» de la pantalla previa al ciclo está muy oscuro y contrasta demasiado con el resto de la pantalla; pasarlo a un verde más claro, hacia el pastel, conservando las líneas visuales de la pantalla.

Estado actual (`qml/Componentes/DeslizadorInicio.qml`, usado en `Pantallas/PantallaPreciclo.qml`): la pista es casi negra (`mezcla("#052a17", "#063a1f")`) con sombra interior negra al 80 %, brillo exterior verde neón y acentos `#28be5f → #6effa0`. Los textos de la pista usan el acento al 85 %.

Cambios (solo apariencia; comportamiento, medidas, animaciones, `completado()`, `enabled`/`visible` y `objectName` sin cambios):
- Pista: de verde casi negro a verde pastel claro: reposo `#E9F8EE` (éxito 050 de `tokens.css`) → listo `#D3F1DD` según el avance; borde 1 u del acento al 45 %.
- Sombra interior: de negro 0,8 a verde oscuro suave (`#007A29` al 12 %), para conservar el relieve sin oscurecer.
- Brillo exterior de la pista: opacidad de sombra de 0,4 a 0,2.
- Acentos: reposo `#2DBE66` → listo `#5ED68C` (menos neón; mismas transiciones). Brillos `#BDEBCB` → `#DDF7E5`.
- Textos de la pista («Iniciar ciclo» / «Iniciando…»): color fijo `#007A29` (éxito fuerte, contraste ≥ 4,5:1 sobre la pista pastel) en lugar del acento translúcido; se retira su sombra de color (sobre fondo claro emborrona el texto).
- Manija: núcleo en `#009933` (éxito) para que el triángulo blanco conserve contraste ≥ 3:1; anillos, partículas y barrido con el acento nuevo.
- Degradados internos (`::before`, franja superior, línea de puntos): mismos elementos y opacidades, recalculados sobre el acento nuevo; sin colores negros.
- Los colores nuevos van como propiedades del módulo `Tema/Colores.qml` (p. ej. `deslizadorPista`, `deslizadorPistaListo`, `deslizadorAcento`, `deslizadorAcentoListo`, `deslizadorTexto`), no como literales en el componente (regla de `tokens.css`). Los literales que el componente ya tiene y que no se tocan se anotan en el informe como deuda, sin cambiarlos.
- Deshabilitado (`opacity 0.4`): sin cambio.
- Verificación: capturas antes/después de la pantalla previa al ciclo (reposo, a mitad del arrastre y al final) a 1200×1920 en `docs/informes/dashboard_reportes/capturas/aj01_*`; el commit de AJ-01 queda separado para poder revertirlo solo, y la aprobación visual la da Cristian. Si con los valores propuestos la pista no se distingue del fondo de la pantalla, la tanda puede subir un paso de saturación del verde y lo anota como DECISIÓN SIN CONFIRMAR.

## 14. FUT-01 — Bowie & Dick por turnos (próxima versión, fuera de esta tanda)

Idea de Cristian: algunas clínicas trabajan varios turnos al día y cada turno debe ejecutar su prueba. Cada Bowie & Dick exitoso marcaría el inicio de un turno, y la función debe poder desactivarse si la clínica no la requiere. Pendiente de definir en su propia planeación: qué es un turno (cortes horarios fijos o «desde el último Bowie & Dick exitoso»), dónde se configura y con qué rol, cómo se muestra en el calendario (día con varios turnos) y si hay aviso cuando un turno no tiene prueba. Esta tanda no debe preparar nada para FUT-01 más allá de no impedirlo (por ejemplo, `estado_dia` recibe los intentos ordenados, no solo un conteo).
