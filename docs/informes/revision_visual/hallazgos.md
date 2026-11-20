# Revisión visual (RV): hallazgos

Etapa C, 19-nov. Fuente: capturas offscreen de `base/` (137 escenarios × 8 combinaciones, más la I4 a 1024 × 1638), `resumen_*.json` de los detectores (incluido el nuevo de solapes) y revisión visual de cada mosaico en cuatro grupos, consolidada y verificada contra la pasada en ventana real (`base_windows/`, etapa B2). Rutas de evidencia relativas a `docs/informes/revision_visual/`; QML relativo a `src/autoclave/ui_qml/qml/`.

Detectores en `base/` (las 8 combinaciones): 144 solapes, 80 sale_del_cuadro, 76 cruza_divisor, 54 encogido, 2 no_cabe_al_minimo, 2 tinta_ancho y 248 «fuera del lienzo»; la I4 a 1024 × 1638, sin truncados ni solapes. Casi todos son falsos positivos (ver al final) o se agrupan en las entradas de abajo.

Categorías: 1 = corrección de maquetación (se corrige en la etapa D); 2 = decisión de Cristian; FP = falso positivo.

## ALTA

### RV-01. Nuevo usuario en vertical oscuro: campos, lista de roles y «Cancelar» en blanco
- Escenarios `nuevo_usuario`, `nuevo_usuario_roles`, `nuevo_usuario_teclado`, `e_nuevo_usuario_teclado`; 1200x1920; oscuro; es y en. En horizontal y en claro está bien. Confirmado en ventana real (`base_windows/1200x1920_es/hor_oscuro_nuevo_usuario_roles.png`).
- Se ve: los recuadros de los campos y de Rol son blancos sobre la tarjeta oscura; el texto tecleado (`textoPrimario`, claro en oscuro) y las opciones de la lista de roles quedan casi invisibles; «Cancelar» sale blanco con texto blanco.
- Evidencia: `base/1200x1920_es/hor_oscuro_nuevo_usuario_roles.png`, zona 70,1000,1130,1620; `hor_oscuro_nuevo_usuario.png`, zona 40,1180,1160,1300.
- Origen: visual.
- QML: `Pantallas/NuevoUsuario.qml:241-242` (`Binding on color { when: raiz.hz }`), :446, :541, :628. El comentario del código dice «en vertical el recuadro no fija color (blanco por defecto, también en oscuro: preexistente, pendiente de decisión)».
- Categoría 1: usar `Colores.fondoCampo` (claro #FFFFFF, igual que hoy) también en vertical; solo cambia el oscuro. Se avisa en el informe porque el código lo marcaba como pendiente.

### RV-02. Cambio de contraseña en vertical oscuro: campos en blanco
- Escenarios `cambio_clave`, `cambio_clave_teclado`, `e_cambio_clave_teclado`; 1200x1920; oscuro; es y en.
- Se ve: los tres recuadros de contraseña son blancos sobre la tarjeta oscura; lo tecleado no se vería.
- Evidencia: `base/1200x1920_es/hor_oscuro_cambio_clave.png`, zona 70,580,1000,1000.
- Origen: visual.
- QML: `Pantallas/CambioClave.qml:134-135` (mismo patrón que RV-01).
- Categoría 1 (como RV-01).

### RV-03. Preciclo en vertical: nombre de programa largo encima del número de ciclo y del estado
- Escenario `b_preciclo_programa_largo`; 1200x1920; claro y oscuro; es y en. En horizontal baja a dos líneas y cabe. Confirmado en ventana real.
- Se ve: «INSTRUMENTAL ENVUELTO 134 °C LARGO» en una línea de 776 px cruza los dos divisores y se dibuja sobre el «04» de Ciclo activo y sobre el ícono de Estado.
- Evidencia: `base/1200x1920_es/hor_claro_b_preciclo_programa_largo.png`, zona 40,190,1160,260.
- Origen: detector `cruza_divisor` (x 213, ancho 776) y visual.
- QML: `Pantallas/PantallaPreciclo.qml:441-462` (ancho, ajuste de línea, `maximumLineCount` y `fontSizeMode` solo con `raiz.hz`).
- Categoría 1: limitar el texto al recuadro central también en vertical (dos líneas y ajuste de letra), como ya hace el horizontal.

## MEDIA

### RV-04. Teclado numérico en vertical: la unidad se monta sobre «Rango»
- Escenarios `teclado_num`, `login_teclado_num`, `d_ciclo_ajuste`, `d_equipo_ajuste`; 1200x1920; los dos temas; es y en.
- Se ve: con el valor vacío, «°C» queda ~16 px arriba y encima del inicio de «Rango: …».
- Evidencia: `base/1200x1920_es/hor_oscuro_teclado_num.png`, zona 160,1310,460,1365.
- Origen: detector `solape` (167,1336,29,11) y visual.
- QML: `Componentes/TecladoNumerico.qml:80-117` (fila valor/unidad alineada a la línea base de un texto vacío; en horizontal ya se resolvió con un espacio).
- Categoría 1.

### RV-05. Conectividad en horizontal: los botones cortan su texto
- Escenario `d_conectividad`; 1920x1200; claro y oscuro; es (en cabe).
- Se ve: «+ Agregar destinatario» toca los bordes y «Enviar correo de prueba» pierde letras en los extremos.
- Evidencia: `base/1920x1200_es/hor_claro_d_conectividad.png`, zona 1250,540,1870,610.
- Origen: visual.
- QML: `Pantallas/OpcionesConectividad.qml:339` y :347.
- Categoría 1 (bajar la letra con `fontSizeMode`, sin elide).

### RV-06. Parámetros del ciclo: la última fila queda cortada bajo la leyenda
- Escenario `d_parametros_ciclo_fase`; los dos tamaños; claro y oscuro; es y en.
- Se ve: la fila «Margen de recuperación…» se corta a la mitad y la leyenda «* Valor distinto del valor por defecto…» se pinta encima.
- Evidencia: `base/1200x1920_es/hor_claro_d_parametros_ciclo_fase.png`, zona 150,1690,1200,1730.
- Origen: visual.
- QML: `Pantallas/OpcionesParametrosCiclo.qml:497-529` (lista y `pieSeccion`).
- Categoría 1.

### RV-07. Preciclo en vertical: el rótulo de «RECONOCER FALLA» se encoge al mínimo
- Escenario `b_preciclo_falla`; 1200x1920; los dos temas; es (172 → 156 px) y en (202 → 156 px, no cabe ni al mínimo).
- Se ve: el rótulo baja a ~14 px de alto junto a un círculo de 84 px; en inglés se sale de su caja.
- Evidencia: `base/1200x1920_en/hor_oscuro_b_preciclo_falla.png`, zona 980,1650,1190,1690.
- Origen: detector `encogido`, `no_cabe_al_minimo`, `tinta_ancho`.
- QML: `Pantallas/PantallaPreciclo.qml:786-798` (`textoBotonAccion`) y la caja vertical en :902.
- Categoría 2: es la etiqueta de un control operativo; la salida limpia es ensanchar la caja vertical del botón (cambia su tamaño) o partirla en dos líneas dentro de un botón diseñado para una. Recomendación: dos líneas con la letra del horizontal.

### RV-08. Clave i18n cruda «estados.completado» como estado del ciclo
- Escenario `ciclo_completo`; todas las combinaciones.
- Se ve: bajo el ícono de Estado, en naranja, el texto literal «estados.completado».
- Evidencia: `base/1200x1920_es/hor_claro_ciclo_completo.png`, zona 880,300,1200,360.
- Origen: visual. El puente sí publica «completado» (`bridge/ui_bridge.py:32`, :539), pero `i18n/es.json` y `en.json` no tienen `estados.completado`.
- QML: `Pantallas/PantallaCicloEnCurso.qml:563-564`.
- Categoría 2 (agregar la clave es/en o mapear el resultado).

### RV-09. Reportes: causas de fallo con el código interno
- Escenarios `reportes_panel`, `reportes_medio`, `reportes_fallo`, `reportes_ciclo`, `reportes_dia`; es y en.
- Se ve: «Causas de fallo» lista «FALLO_ESTERILIZACION 7», el título dice «Ciclos con el fallo FALLO_ESTERILIZACION: 7» y el detalle muestra el código; en vertical se parte en «FALLO_ESTERILIZACI / ON».
- Evidencia: `base/1200x1920_es/hor_claro_reportes_panel.png`, zona 40,1350,860,1450; `base/1200x1920_es/hor_claro_reportes_ciclo.png`, zona 540,270,720,365.
- Origen: visual.
- QML: `Pantallas/Reportes.qml:580`; `Componentes/DetalleCiclo.qml:20`, :132; clave `reportes.ciclos_con_fallo`.
- Categoría 2 (traducir la causa a un texto i18n; es texto y lógica de presentación).

### RV-10. Aviso «Sin conexión con el equipo» encima de la hora, el logo y la campana
- Escenario `e_main_sin_conexion`; los dos tamaños; claro y oscuro; es y en.
- Se ve: el aviso cubre la cabecera completa; la campana de notificaciones queda tapada mientras dura la falta de conexión.
- Evidencia: `base/1200x1920_es/hor_claro_e_main_sin_conexion.png`, zona 0,0,1200,150.
- Origen: detector `solape` (banner contra `zonaCampana`, `horaMenu`, logo) y visual.
- QML: `Main.qml:313-340`.
- Categoría 2 (mover un aviso de seguridad de conexión; recomendación: bajarlo bajo la cabecera).

### RV-11. Teclado abierto sobre el botón de acción del formulario
- Escenarios `cambio_clave_teclado`, `e_cambio_clave_teclado`, `nuevo_usuario_teclado`, `e_nuevo_usuario_teclado`, `inst_teclado_*`, `f_usuarios_restablecer`; 1920x1200 (en vertical, Nuevo usuario también corta la fila Estado).
- Se ve: el teclado (45 % del alto) corta por la mitad «CAMBIAR CONTRASEÑA» o tapa «Cancelar/Guardar usuario» y la fila elegida en Usuarios; el campo que se edita sí queda visible.
- Evidencia: `base/1920x1200_es/hor_claro_e_cambio_clave_teclado.png`, zona 800,480,1600,700.
- Origen: detector `solape` y visual.
- QML: `Componentes/PanelTeclado.qml:184` (`_altoMaximo`), `Pantallas/CambioClave.qml`, `Pantallas/NuevoUsuario.qml:318`.
- Categoría 2 (cambia cómo se desplaza el formulario con el teclado; el valor se entrega con Confirmar del teclado, así que no bloquea la tarea).

### RV-12. Preciclo con muchas alarmas: la última fila se corta sin pista de que hay más
- Escenario `b_preciclo_muchas_alarmas`; los dos tamaños.
- Se ve: la fila 9 (vertical) o 6 (horizontal) queda cortada en el borde de la tarjeta.
- Evidencia: `base/1920x1200_es/hor_claro_b_preciclo_muchas_alarmas.png`, zona 740,590,1180,640.
- Origen: visual.
- QML: `Componentes/SeccionEstadoSeguro.qml`, `Pantallas/PantallaPreciclo.qml` (lista de alarmas).
- Categoría 2 (agregar un indicador de desplazamiento en la lista de alarmas).

### RV-13. Ciclo en curso sin conexión: los avisos cubren la gráfica
- Escenario `b_ciclo_sin_conexion`; los dos tamaños.
- Se ve: el aviso gris y el NO ABRIR se dibujan sobre las curvas; en horizontal ocupan casi todo el alto superior de la gráfica.
- Evidencia: `base/1920x1200_es/hor_claro_b_ciclo_sin_conexion.png`, zona 900,270,1390,450.
- Origen: visual.
- QML: `Pantallas/PantallaCicloEnCurso.qml` (`avisoSinConexionCiclo`).
- Categoría 2 (posiblemente intencional: sin datos vigentes la curva no sirve; mover el aviso cambia el diseño).

## BAJA

### RV-14. Teclado en horizontal: el título del campo se parte en una columna estrecha
- Escenarios `login_teclado*`, `inst_teclado_*`, `cambio_clave_teclado`, `nuevo_usuario_teclado`, `teclado_alfa`; 1920x1200.
- Evidencia: `base/1920x1200_es/hor_claro_inst_teclado_clave.png`, zona 0,640,400,740.
- QML: `Componentes/TecladoAlfanumerico.qml:71-82`, `Componentes/PanelTeclado.qml:194`, :256.
- Categoría 1.

### RV-15. Nuevo usuario: el interruptor «Activo» no se alinea con «Estado» ni con los campos
- Escenarios `nuevo_usuario*`; los dos tamaños.
- Evidencia: `base/1200x1920_es/hor_claro_nuevo_usuario.png`, zona 60,1030,1140,1230.
- QML: `Pantallas/NuevoUsuario.qml:494-515`.
- Categoría 1.

### RV-16. Asistente, modo automatizado: la ayuda queda pegada a «Serie original del equipo»
- Escenario `inst_activacion_auto`; los dos tamaños.
- Evidencia: `base/1200x1920_es/hor_claro_inst_activacion_auto.png`, zona 50,780,1150,1000.
- QML: `Pantallas/Instalacion.qml:542-552`.
- Categoría 1.

### RV-17. Fin de ciclo en horizontal: hora sola en la segunda línea del título
- Escenarios `fin_fallido`, `b_fin_observaciones_panel`, `b_fin_estado_seguro_modal`; 1920x1200.
- Se ve: «Ciclo 03 terminó en FALLO a las / 13:21», con el título pegado a «Ver gráfica».
- Evidencia: `base/1920x1200_es/hor_claro_b_fin_observaciones_panel.png`, zona 930,160,1400,260.
- QML: `Componentes/PanelFinCiclo.qml`.
- Categoría 2 (el corte depende del texto; evitarlo pide reformular o un ancho distinto del título).

### RV-18. Panel de equipo en vertical: las filas del módulo E/S quedan fuera de vista
- Escenarios `e_equipo`, `e_equipo_apagar`; 1200x1920.
- Evidencia: `base/1200x1920_es/hor_claro_e_equipo.png`, zona 48,1480,1152,1900.
- QML: `Componentes/PanelEquipo.qml:79-84`.
- Categoría 2 (pide un indicador de desplazamiento o reacomodar la lista).

### RV-19. Diálogo «Apagar equipo»: el velo no cubre el título ni CERRAR
- Escenario `e_equipo_apagar`. No accionado (control prohibido en la etapa E).
- Evidencia: `base/1200x1920_es/hor_oscuro_e_equipo_apagar.png`, zona 48,280,1152,1700.
- QML: `Componentes/PanelEquipo.qml:127-175`.
- Categoría 2 (el diálogo de apagado es un control de seguridad; no se toca sin decisión).

### RV-20. Modal de operador en oscuro: filas no elegidas con poco contraste
- Escenario `e_modal_operador`; los dos tamaños; oscuro.
- Evidencia: `base/1200x1920_es/hor_oscuro_e_modal_operador.png`, zona 70,630,1060,1450.
- QML: `Componentes/ModalOperador.qml:137`.
- Categoría 2: el par `fondoSutil`/texto ya pasa la prueba de contraste de la paleta (`tests/test_tema_oscuro.py`); subirlo cambia un valor oscuro compartido por muchas pantallas. A confirmar en la pantalla real.

### RV-21. Reportes, vista Año: tarjetas de mes de altura distinta
- Escenario `reportes_anio`.
- Evidencia: `base/1200x1920_es/hor_claro_reportes_anio.png`, zona 30,400,860,700.
- QML: `Componentes/MesMiniatura.qml`.
- Categoría 2 (estético; fijar 6 filas a todos los meses cambia la composición).

### RV-22. Programa en naranja sobre blanco en Historial y Reportes (claro)
- Escenarios `menu_historial*`, `menu_ciclos_hoy`, `reportes_fallo`, `reportes_dia`; claro.
- Evidencia: `base/1200x1920_es/hor_claro_menu_historial.png`, zona 430,590,650,640.
- Categoría 2 (sería cambiar un valor claro de `Colores.qml`).

### RV-23. Modal «Alarmas del periodo»: ocho filas por página con espacio vacío
- Escenario `reportes_alarmas`. Evidencia: `base/1200x1920_es/hor_claro_reportes_alarmas.png`, zona 70,820,830,1100.
- Categoría 2 (cambia la paginación).

### RV-24. Ajuste de parámetro del equipo: el velo no cubre la franja de botones
- Escenario `d_equipo_ajuste`; los dos tamaños.
- Evidencia: `base/1200x1920_es/hor_oscuro_d_equipo_ajuste.png`, zona 200,440,1200,480.
- QML: `Pantallas/OpcionesParametrosEquipo.qml:921-935`, :1120-1160.
- Categoría 1 (a confirmar al ampliar en la etapa D).

### RV-25. Entradas/Salidas en vertical: nombres de salida de tamaños distintos
- Escenarios `d_es_salidas`, `d_entradas_salidas`; 1200x1920.
- Se ve: con HorizontalFit solo algunos nombres se encogen («Descompresión chaqueta», «Aire comprimido cámara») y «Desbloqueo puerta 1/2» queda a ~5 px de «APAGADA».
- Evidencia: `base/1200x1920_es/hor_claro_d_es_salidas.png`, zona 180,1020,1200,1250.
- QML: `Pantallas/OpcionesEntradasSalidas.qml:155-163`.
- Categoría 1 (ajuste a dos líneas como en horizontal).

### RV-26. Parámetros del ciclo: la flecha «‹» no se alinea con el título de la subvista
- Escenarios `d_parametros_ciclo_fase`, `d_ciclo_sensores`.
- Evidencia: `base/1200x1920_es/hor_claro_d_parametros_ciclo_fase.png`, zona 200,310,700,400.
- QML: `Pantallas/OpcionesParametrosCiclo.qml:466-495`.
- Categoría 1.

### RV-27. Usuarios: la nota de «usuario eliminado» aparece también en la pestaña Operadores
- Escenario `d_usuarios_operadores`. QML: `Pantallas/OpcionesUsuarios.qml:231-238`.
- Categoría 2 (visibilidad por pestaña).

### RV-28. Usuarios: rol «operador» sin traducir en inglés
- Escenarios `d_usuarios*`, `f_usuarios_*`; en. QML: `Pantallas/OpcionesUsuarios.qml:283` (`etiquetaRol`).
- Categoría 2 (a confirmar con la etapa E: puede ser el dato de ejemplo).

### RV-29. Calibración de sensor: «ADC undefined»
- Escenario `d_calibracion_sensor`. QML: `Pantallas/OpcionesCalibracionSensor.qml:252-253` (compara `=== null` y no cubre `undefined`).
- Categoría 2 (lógica mínima; con el backend real el dato llega).

### RV-30. Información del sistema en horizontal: dos secciones quedan bajo el borde sin pista de desplazamiento
- Escenario `d_info_sistema`; 1920x1200. QML: `Pantallas/OpcionesInfoSistema.qml`.
- Categoría 2 (indicador de desplazamiento).

### RV-31. Texto de «sin conexión» distinto entre idiomas
- es dice «módulo E/S», en dice «the controller» (`i18n/es.json:866` y `en.json:866`).
- Categoría 2 (texto).

### RV-32. Selector de programa en inglés: «secado 15 min» en español
- Escenario `b_preciclo_selector`, en. Evidencia: `base/1200x1920_en/hor_claro_b_preciclo_selector.png`, zona 60,420,780,620.
- Categoría 2 (texto; el literal se arma fuera del QML).

### RV-33. Intro en inglés con el eslogan en español
- Escenario `intro_final`, en. QML: `Pantallas/IntroArranque.qml:284-285` (literal sin I18n).
- Categoría 2 (puede ser intencional, como marca).

### RV-34. Intro en claro: la línea de modelo y versión tiene poco contraste
- Escenario `intro_final`; claro. Evidencia: `base/1920x1200_es/hor_claro_intro_final.png`, zona 500,1050,1500,1150.
- Categoría 2 (valor claro de color).

### RV-35. Rótulos pequeños y pegados en la tira de valores de Ciclo en curso
- «Tiempo transcurrido», «Progreso de la fase» y los rótulos de la tira, de 14 a 16 px y pegados al valor.
- Categoría 2 (estético; cambia la tipografía fijada por el mockup).

### RV-36. Pantalla de prueba de teclados: la caja del valor es blanca en oscuro
- Escenarios `teclado_alfa`, `teclado_num` (arnés `Pruebas/PruebaTeclado*.qml`, no es una pantalla del equipo).
- Categoría 1 (solo arnés de prueba).

## Falsos positivos

- **FP-01.** Botones de acción de Preciclo y Ciclo en curso (Abrir puerta, Reconocer falla, CONFIRMAR) sin cuerpo en claro (grupo 2, H2): en ventana real se dibujan bien (`base_windows/1200x1920_es/hor_claro_b_preciclo_falla.png`); el cuerpo usa `MultiEffect`, que offscreen no dibuja.
- **FP-02.** Reportes: la dona y los círculos del calendario se salen del área desplazable y tapan la cabecera y la barra inferior (grupo 3, H1): en ventana real el recorte del `Flickable` se respeta (`base_windows/1200x1920_es/hor_claro_reportes_medio.png`); es el renderizador por software de offscreen, que no recorta `Shape`. Se agrega a las limitaciones conocidas.
- **FP-03.** `b_ciclo_espera_entrega_ingeniero` sin «Confirmar sin condiciones seguras» (grupo 2, H10): ese botón se retiró en la beta.3 («barra Terminando sin confirmación forzada»); el escenario era anterior y además no cargaba (propiedad `forzable` inexistente, corregido en la etapa B).
- **FP-04.** Panel de notificaciones y detalle de alarma con textos en español en inglés (grupo 3, H9): los textos vienen del doble del escenario (`ALARMA` de `hor_capturas.py`), no de la aplicación.
- **FP-05.** Resumen del asistente sin filas de automatización y barras inferiores vacías en login, cambio de clave y nuevo usuario: datos del doble.
- **FP-06.** Detectores: `cruza_divisor` de «Cancelar»/«Confirmar» y de las teclas del teclado en pantalla (líneas de la propia rejilla); solapes de la intro (fotograma inicial animado); solapes de la lista desplegable de roles (se dibuja encima a propósito); solapes de las filas bajo el selector de destino opaco; `fuera` de `cuerpoReportes`, `seccion*`, `grupoInfo_*` y `navegacionOpciones` (contenido dentro de un `Flickable` con recorte); `sale_del_cuadro` de ejes, leyendas y números de la gráfica y del chevron de las filas de fin de ciclo; `cruza_divisor` de la rejilla de la gráfica; `encogido` de salidas que se leen completas salvo RV-25; íconos monocromos vacíos y deslizadores o círculos de fase (MultiEffect y animación).
