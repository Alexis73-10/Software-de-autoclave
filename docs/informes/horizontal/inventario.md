# Tanda horizontal: inventario de pantallas y componentes

Medidas verticales (lienzo 1200x1920 de dev) y disposición horizontal aplicada (lienzo 1920x1200) de cada pantalla y componente con medidas verticales. Las medidas van en px de diseño (las pantallas con `m()` usan px del mockup de 1196, ≈ px de lienzo). El inventario se armó grupo por grupo antes de editar cada grupo y se completó con lo aplicado.

## Base (común a todo)

| Elemento | Vertical (dev) | Horizontal |
|---|---|---|
| `Tema/Escala.qml` | `anchoDiseno` 1200, `altoDiseno` 1920 | `horizontal` (bool), `anchoVertical/altoVertical` 1200/1920, `anchoHorizontal/altoHorizontal` 1920/1200, `anchoDiseno/altoDiseno` según `horizontal`; `esHorizontal(ancho, alto)` = ancho >= alto. `factor = min(ancho/anchoDiseno, alto/altoDiseno)` y `altoLienzo = max(altoDiseno, alto/factor)` sin cambio de fórmula |
| Main, InstalacionVentana, ReposoInstalacionVentana, NuevoUsuarioHost | Ventana 600x960 por defecto; app.py la pone a pantalla completa en el monitor elegido | Igual; cada una fija `Escala.horizontal` con `esHorizontal` sobre su tamaño real (el de su monitor). Un proceso por pantalla: cada una decide la suya y sigue el giro del monitor |
| `Componentes/AreaFija.qml` | Área de ancho del lienzo x 1920 centrada | En horizontal, área de 1920x1200 centrada |
| `Componentes/BarraSuperior.qml` (Login, CambioClave, NuevoUsuario, Instalación) | 1200 de ancho; campana en x 888 y engranaje en x 1043 | 1920 de ancho; campana y engranaje con su mismo margen derecho (+720) |
| `Componentes/EncabezadoMenu.qml` (Menú, Opciones, Reportes) | Marco 1196: logo x 73, hora y fecha centradas en 597,5, campana 888, engranaje 1043 | Marco 1913,6: logo igual, hora y fecha al centro (`dxCentro`), campana y engranaje con su margen derecho (`dxDerecha`) |
| Encabezados inline de Preciclo y Ciclo en curso | Igual que EncabezadoMenu | Mismo criterio (`dxCentro`, `dxDerecha`), ver grupo B |
| Barras inferiores (`BarraInferiorMenu` y las de Preciclo/Ciclo) | 139 de alto, 171 desde el borde inferior, ancho de la tarjeta de encima | Mismo alto y margen; a lo ancho (x 19 o 54 hasta el margen derecho igual) |
| Pantallas con `escala = ancho / 1196` (MenuPrincipal, Opciones, Reportes, PantallaPreciclo, PantallaCicloEnCurso, barras de Login, CambioClave, NuevoUsuario) | Escala ligada al ancho | Escala del lienzo vertical, `Escala.px(1200) / 1196`, para conservar los px de diseño (si no, todo crecía 1,6 veces) |
| Arneses `qml/Pruebas/*.qml` | — | La misma regla de orientación sobre su tamaño |

## Grupos

## Grupo A: intro, arranque, asistente de instalación y sesión

Corrección común (Login, CambioClave, NuevoUsuario): usaban `raiz.width / 1196` para la escala de la barra flotante y el alto de la tarjeta (en horizontal la barra crecía 1,6 veces); ahora `escalaBarra = Escala.px(Escala.anchoVertical) / 1196` en horizontal: barra de 139 de alto, de x 24 a 1896, mismo margen inferior.

Diferencias de estructura en vertical sin efecto visual (posiciones iguales, comprobado con las capturas): en Login y CambioClave el encabezado y el formulario van en un GridLayout de 1 columna con rowSpacing 60 (antes, un espaciador de 60); en Instalación la página va en un Item contenedor con un Translate de 0 y tres Column pasaron a Grid de 1 columna (tipos de equipo, filas del resumen, clases).

| Pantalla / componente | Vertical (dev) | Horizontal |
|---|---|---|
| Login | Tarjeta de 1152; pila: margen 60, título, avatar 336, subtítulo, margen 60, formulario de 756 | Título, avatar y subtítulo centrados en la mitad izquierda; formulario de 756 en la mitad derecha, alineado arriba; margen superior 40 y espaciado del formulario 20 (cabe con la ayuda de contraseña y el aviso sin base de datos); campos hasta y ≈ 460, sobre el teclado |
| CambioClave | Igual que Login | Igual que Login (margen 60, espaciado 20); campos hasta y ≈ 590 |
| NuevoUsuario | Posiciones absolutas: campos de 707 en x 381 (y 184, 351, 518, 685), Rol de 1027, Estado y botones en y 1177 | Alto útil ≈655: 3 columnas de 449 (x 381, 878, 1375) y 2 filas (y 184 y 351): Nombre / Usuario / Rol y Contraseña / Confirmación / Estado; botones en y 520 a la derecha; error general en y 630; la lista de roles abre hacia abajo y cabe |
| Instalacion (asistente) | Título, «Paso n de N», indicador de pasos y página desde y 276, todo en columna | Título en y 48, «Paso n de N» a la derecha en su línea, indicador en y 124, página desde y 208 (≈607 útiles). Activación: serie y código en una fila, interruptor y ayuda, serie y modelo originales. Tipo de equipo: rejilla de 2. Puertas: cantidad y «puerta de este PC» a la izquierda, tipos a la derecha. Cámara: capacidad y carga a la izquierda, vista previa a la derecha. Datos: suministros / sondas. Contraseñas: Admin / Ingeniero (2 x 2). Resumen: columna de 520 (título, modelo, aviso, error) y filas en 2 columnas a la derecha (etiqueta en varias líneas, valor 55 %). Resultado: sello en y 60. Enfriamiento y vapor sin cambio. Solo en horizontal, la página sube para dejar el campo activo sobre `teclado.alturaOcupada` (como NuevoUsuario), con recorte bajo la barra superior |
| IntroArranque | Geometría en fracciones de ancho x alto | Línea, riel y volutas con el ancho vertical (riel de 864); logo en alto/2 − 270 y eslogan y barra a las distancias verticales desde el logo; pie en 0,935 del alto; fondo PreserveAspectCrop dentro de AreaFija |
| Reposo | PNG 1200x1920 con PreserveAspectCrop, contenido centrado | Sin cambios |
| BarraReinicioBackend | 80 % del ancho | Ancho del vertical (960), centrada |
| IndicadorPasos, CampoFormulario, BotonFormulario, OpcionTarjeta, FilaInterruptor, TarjetaContenido, FondoApp, FondoGradiente | — | Sin cambios |

Escenarios (`hor_escenarios_a.py`): intro_final, barra_reinicio, reposo_aviso, inst_activacion_auto, inst_equipo, inst_puertas, inst_puertas_una, inst_camara, inst_enfriamiento, inst_vapor, inst_datos, inst_contrasenas, inst_resumen, inst_resumen_auto, inst_listo, inst_teclado_codigo, inst_teclado_clave, login_teclado_clave, login_sin_bd, cambio_clave_teclado, nuevo_usuario_roles, nuevo_usuario_teclado; más intro, reposo, instalacion, login, cambio_clave, nuevo_usuario. Claro y oscuro: nada fuera del lienzo ni recortado o encogido; único aviso, falso positivo «Confirmar cruza divisor 1352» (divisor de la barra flotante bajo el teclado).

Vertical: `hor_vertical_igual` igual en todos salvo intro (animación; intro_final, congelado, igual), reposo y reposo_aviso (solo el reloj grande; Reposo.qml no se tocó). 33 archivos de pruebas existentes: 775 pasan sin modificarlos. `test_hor_a_sesion_instalacion.py`: 9 pasan.

DECISIÓN SIN CONFIRMAR: NuevoUsuario en 3 columnas (campos de 449 en lugar de 707); serie y código en la misma fila en la activación; la página del asistente sube sobre el teclado (en vertical no); márgenes 40 y 20 en Login; resumen en 2 columnas.

Sin verificar: resumen del asistente en modo automatización con las 16 filas (estimado ≈576 de ≈607): el puente de Pruebas/PruebaInstalacion.qml no tiene `calcularModelo` ni `normalizarOriginal`, las filas salen «—».

Preexistente en dev (no tocado para no cambiar el vertical): en NuevoUsuario, oscuro, los recuadros de los campos y el botón Cancelar no tienen `color` y salen blancos; el texto escrito y «Cancelar» casi no se ven.

Pendiente de banco: táctil real del teclado sobre los campos en horizontal; la intro en el monitor girado.
## Grupo B: Preciclo (dos puertas) y Ciclo en curso

Regla común: en horizontal `m()` usa `Escala.px(1200)/1196` (no el ancho); marco de 1913,6 px del mockup; `dxCentro`/`dxDerecha` llevan reloj y fecha al centro y campana/engranaje a la derecha, como EncabezadoMenu; tarjeta principal y barra inferior de x 19 a 1894,6. En vertical los desplazamientos valen 0.

| Pantalla / componente | Vertical (dev) | Horizontal |
|---|---|---|
| PantallaPreciclo | Tarjeta 1159 de ancho de y 177 a la barra; ciclo 219–404, parámetros 425–633, alarmas 655–1599 (944 de alto), botones en y 1615 (110), barra 139 a 171 del borde | Columna izquierda: ciclo, parámetros y botones con la geometría vertical; los botones (ABRIR/CERRAR PUERTA o indicador, deslizador INICIAR, RECONOCER FALLA) bajan con `dyAcciones` hasta quedar sobre la barra. Columna derecha: alarmas y avisos a todo el alto (x 1178, ≈702 x 808), lista desplazable como antes |
| PantallaCicloEnCurso (alto flexible, `yb()`) | Ciclo 219–404, BarraFases centrada en y 480, parámetros 576–784, gráfica x 33–1162 y 804–yb(1598), relojes y pista abajo | Columna izquierda (1159, igual que en vertical): ciclo, BarraFases, parámetros, relojes y pista; píldora de fin de ciclo centrada entre parámetros y relojes. Columna derecha: gráfica de x 1192 al borde (≈687) y de y 192 a yb(1722) (≈810); PanelFinCiclo y la capa de avisos en el mismo rectángulo (avisos de hasta ancho − 140). Barra inferior a lo ancho; en la celda derecha, deslizador de cancelar y CONFIRMAR centrados, indicador de espera y «Confirmar sin condiciones seguras» con margen de 12 px. Pantalla completa de la gráfica a lo ancho (1847,6) |
| GraficaCiclo | Tarjeta 1129 de ancho, botones y eje derecho en x fijas | Propiedad `dw` (ancho real − 1129, 0 en vertical) corre a la derecha todo lo anclado al borde derecho (Tiempos, pantalla completa, CERRAR, separador, eje y rótulos derechos, cuadrícula, `xDato1`, área táctil, lupa, globo, título del eje X); con cabecera angosta (`dw < 0`) la leyenda baja a su propia fila (y 108). DetalleCiclo le da 1129: `dw` 0 |
| BarraFases, CirculoFaseLiquido, ConectorFase, PanelFinCiclo, DeslizadorInicio, IndicadorPuerta, PildoraFinCiclo, RegresoPanel, SeccionEstadoSeguro, FilaAlarma, FilaAcordeon, SelectorPrograma, InsigniaCampana | Sin cambio | Se adaptan al tamaño de su contenedor; sin cambios |

Escenarios: preciclo_preparado, preciclo_alarma, ciclo_grafica, ciclo_completo, fin_fallido, ciclo_demo y los de `hor_escenarios_b.py` (b_preciclo_puerta2, b_preciclo_puerta2_manual, b_preciclo_modo_prueba, b_preciclo_falla, b_preciclo_sin_conexion, b_preciclo_muchas_alarmas, b_preciclo_programa_largo, b_preciclo_selector, b_ciclo_pantalla_completa, b_ciclo_tiempos, b_ciclo_zoom_lupa, b_ciclo_sin_conexion, b_fin_fallido_grafica, b_fin_observaciones_pildora, b_fin_observaciones_panel, b_fin_estado_seguro_modal, b_ciclo_espera_entrega_ingeniero, b_ciclo_espera_entrega), en claro y oscuro y también a 1600x1200. Ningún ítem fuera del lienzo. Avisos restantes, iguales en vertical: `chevronFila` de FilaAcordeon (chevrón girado), «RECONOCER FALLA» encogido, programa largo que cruza el divisor; en pantalla completa y en el modal, textos tapados por la capa superpuesta. `ciclo_zoom` de hor_capturas no amplía (el objectName `botonPantallaCompleta` no existe): lo cubren b_ciclo_pantalla_completa y b_ciclo_zoom_lupa.

Vertical: `hor_vertical_igual` 13 de 25 idénticos; los 12 distintos tienen animación o reloj (brillo del deslizador, engranaje animado, vapor de la barra de fases, segundos de la píldora). Además, volcado de geometría (x, y, ancho, alto, texto, letra) de todos los ítems visibles a 1200x1920 con dev y con la rama en PruebaFinDeCiclo (en curso, fallo, gráfica, pantalla completa, preciclo con y sin actuador) y PruebaCicloEnCurso con zoom: ninguna diferencia. 47 archivos de pruebas existentes: 926 pasan; fallan 2 de test_t23_sin_tarjeta (identificadores de otros grupos, corregidos) y la de v8b que ya falla en dev.

DECISIÓN SIN CONFIRMAR:
- Gráfica angosta en Ciclo en curso: las dos columnas a su ancho natural (1159 + 1129) no caben; la gráfica queda en ≈687 px de ancho (trazado ≈496) y más alta que en vertical; para verla grande, la pantalla completa (a todo el ancho). Opción: gráfica a 1129 rehaciendo la columna izquierda en ≈700 px (ciclo en dos filas, parámetros 3x2...), que daría ≈1060 de alto y no cabe en 848.
- Píldora de fin de ciclo en la columna izquierda (junto a «Tiempos» no hay lugar con la cabecera angosta).
- Hueco en Preciclo entre parámetros (y 633) y botones (y 894), por dejar los botones sobre la barra como en vertical; opción: subirlos bajo los parámetros.

Pendiente de banco: gesto de dos dedos y cursor sobre la gráfica angosta con los táctiles reales; legibilidad de la leyenda (baja a ≈16 px con nombres largos).
## Grupo C: Menú principal y sus ventanas, Historial y Detalle de ciclo, Reportes

| Pantalla / componente | Vertical (dev) | Horizontal |
|---|---|---|
| MenuPrincipal | escala = ancho/1196; título con casa en y 262–390; tarjetas de menú en dos filas (499–819 y 843–1163, de x 54 a 1139); «Resumen del sistema» en y 1244 y 4 tarjetas de resumen en una fila (1295–1625); barra inferior de x 54 a 1139 | Escala del lienzo vertical; títulos «Menú principal» (con la casa a su izquierda) y «Resumen del sistema» en la misma línea (base y 238); columna izquierda: las 4 tarjetas de menú con sus anchos verticales (filas en y 290 y 644); columna derecha (x 1158 al margen 54): Resumen en 2 x 2 (filas en 290 y 634, 330 de alto); barra inferior a lo ancho (54 a 54) |
| VentanaFlotante | Tarjeta de x 34 a ancho − 34, alto mín(altoTarjeta, alto − 160) (Último ciclo, Ciclos hoy e Historial piden 1500) | Mismo cálculo: ≈1845 x 1036 px del mockup; propiedad `anchoRecuadroHz` (0 = todo el ancho) para centrarla con ancho fijo (Mantenimiento: 1128, su ancho vertical) |
| DetalleCiclo | Fila de 4 datos (0,25 / 0,37 / 0,2 / 0,18) y debajo la gráfica a todo el ancho, escala = ancho/1129 (1032 px del mockup en la ventana) | Datos en una columna a la izquierda (≈700) y la gráfica a la derecha a todo el alto; escala de la gráfica mín(m(1032)/1129, alto/794) (la letra nunca crece). La fila de datos es un Grid (4 columnas en vertical, 1 en horizontal) con las mismas posiciones; `reservaSuperiorHz` deja sitio arriba para los botones |
| Ciclos hoy, Historial y ciclo abierto de Reportes | Botones arriba (Volver a la izquierda; Enviar e Imprimir a la derecha) y el detalle debajo | Volver y, debajo, Enviar e Imprimir en la columna de datos (State + AnchorChanges); gráfica a todo el alto; en Historial el aviso de la acción baja a la izquierda. En Reportes la gráfica queda a 0,90 en vez de 0,914 (≈1,5 % más chica) |
| Reportes | escala ancho/1196; Flickable `contenidoReportes` de x 54 a 1139 (1085) desde y 262 hasta la barra; todo en una columna | Escala del lienzo vertical; Flickable y barra de 54 al margen 54 (≈1805); Periodo a lo ancho; Grid de dos columnas: izquierda Indicadores (2 x 2), Resultado, Ciclos por día y Por programa; derecha Calendario con su panel del día y Causas de fallo (una causa por fila); debajo a lo ancho Mantenimiento / Alarmas / Operadores y Acciones. En vertical el mismo Grid tiene una columna y apila con el mismo espaciado (posiciones idénticas). Sigue desplazándose |
| TarjetaMenu, TarjetaResumen, BarraInferiorMenu, Calendario, CalendarioEjecucion, MesMiniatura, PanelDiaCalendario, GraficaArea, GraficaDona, listas, TarjetaIndicador, SelectorPeriodo, SelectorDestino, AvisoAccion, BotonPildora, AnilloProgreso, SelectorSegmentos, ResumenPeriodo | — | Sin cambios: toman el ancho de su contenedor |

Escenarios: menu, menu_ultimo_ciclo, menu_mantenimiento, menu_ciclos_hoy, menu_historial, menu_historial_detalle, reportes, reportes_abajo y los de `hor_escenarios_c.py` (menu_historial_ciclo, menu_ciclos_hoy_ciclo, menu_historial_destino, reportes_dia, reportes_panel, reportes_medio, reportes_selector, reportes_anio, reportes_alarmas, reportes_correo, reportes_ciclo, reportes_fallo), en claro y oscuro (y en inglés los principales). Falsos positivos que quedan, iguales en los dos temas: título de Mantenimiento «sale_del_cuadro» (medido contra la tarjeta del fondo; ya salía antes) y CERRAR de «Ver todas» «cruza_divisor» (divisor bajo el velo). Las entradas «fuera» son contenido desplazable que sobresale, también en vertical. `menu_historial_detalle` de hor_capturas no abre el ciclo (findChildren no ve los delegados de ListView): lo cubre menu_historial_ciclo.

Vertical: `hor_vertical_igual` igual en los 20 escenarios del grupo. 33 archivos de pruebas existentes: 745 pasan; 2 de t23_sin_tarjeta fallaban por identificadores (renombrados; el archivo pasa completo después).

DECISIÓN SIN CONFIRMAR: reparto de columnas de Reportes; Mantenimiento centrada a 1128 de ancho; Historial y Ciclos hoy siguen cambiando el listado por el detalle (no lado a lado).

Aviso: el ícono de Inicio de Reportes en oscuro casi no se ve (usa Image en lugar de IconoColor); sin comprobar si pasa igual en vertical; no se tocó.

Pendiente de banco: tacto real de la gráfica y de los botones en la columna de datos.
## Grupo D: Opciones y todas sus secciones

En horizontal `escala = Escala.px(1200)/1196` y el marco mide 1913,6 x 1196 px del mockup. Donde había una Column larga se partió en bloques dentro de `Grid { columns: Escala.horizontal ? 2 : 1 }` con el mismo espaciado (en vertical, mismas posiciones). Cambios de tipo en vertical sin efecto visible (a revisar): riel Column → Grid de 1 columna; lista de parámetros del ciclo ListView → GridView con celda del mismo alto (`contentY` y la restauración del historial siguen, test_n8 pasa); temperatura y presión de E/S Column → Flow; ventanas de ajuste de Parámetros del ciclo y del equipo dentro de un Flickable (en vertical no desplaza ni recorta). Identificadores: `recuadroMaquinaVertical` (en vertical el objectName sigue siendo «tarjeta_» + grupo), `anchoSensor`.

| Pantalla | Vertical (dev) | Horizontal |
|---|---|---|
| Opciones (marco) | Tarjeta x 19, y 177, ancho 1159; título con base en 282; riel en x 54, ancho 96, desde y 330; contenido x 180–1142 (962 x ≈1386); barra en H − 171 | Tarjeta y barra a lo ancho (19–1894,6); título con base en 250, hamburguesa en y 187; riel y contenido desde y 297; riel plegado en dos columnas de iconos (200 de ancho: las 11 secciones sin desplazar); con la hamburguesa se abre como en vertical (una columna con nombres, superpuesta, desplazable, con velo); contenido de x 284 al margen 54 (≈1576 x 698) |
| Parámetros del ciclo | Programa, fases, sensores y entradas mostradas en una columna | Fases del programa en 2 columnas (Sensores y Entradas mostradas a lo ancho); parámetros de la fase en 2 columnas (celda 92); sensores en 2 columnas; ventana de ajuste con alto máximo el disponible y desplazamiento |
| Parámetros del equipo | Entrada en rejilla + Configuración de la máquina aparte; submenú en una columna | Rejilla de 4 columnas con Configuración de la máquina como una celda más (2 filas, sin desplazar); submenú en 2 columnas; máquina igual (ya desplazable); ventana de ajuste como en ciclo |
| Usuarios | Lista y acciones apiladas | Lista a la izquierda a todo el alto, acciones en una columna a la derecha (50 %); Operadores igual |
| Fecha y hora | Separadores de 40, datos en una columna | Separadores de 10, los 4 datos en 2 columnas |
| Información del sistema | Grupos en una columna | Grupos en 2 columnas; sigue desplazándose (la segunda fila bajo el pliegue) |
| Mantenimiento | Una columna | Acciones y datos a la izquierda; tipo, Registrar e intervalos a la derecha |
| Calibración atmosférica | Una columna | Condiciones y progreso a la izquierda; datos, criterios y botones a la derecha |
| Calibración de sensor | Una columna | Lectura, ganancia y punto bajo a la izquierda; punto alto, resultado y acciones a la derecha |
| Conectividad | Una columna | Red y correo a la izquierda (60 %), destinatarios a la derecha (40 %; evita que se achique el detalle de FilaInterruptor) |
| Respaldo | Una columna | Estado de la USB a lo ancho; Exportar a la izquierda, Restaurar a la derecha |
| Entradas / Salidas | Entradas y salidas en 2 columnas; temperatura y presión en 1 | 3 columnas; temperatura y presión en 2 |
| Bitácora, Avanzadas, Manejo de ciclos, Reasignación | — | Sin cambios: su tabla o lista toma el ancho |

Escenarios (`hor_escenarios_d.py`, Opciones con una sesión doble con datos que solo rige mientras la ventana está abierta): d_usuarios, d_usuarios_seleccion, d_usuarios_operadores, d_parametros_ciclo, d_parametros_ciclo_fase, d_ciclo_sensores, d_ciclo_entradas, d_ciclo_ajuste, d_parametros_equipo, d_parametros_equipo_maquina, d_equipo_chaqueta, d_equipo_impresion, d_equipo_ajuste, d_fecha_hora, d_info_sistema, d_bitacora, d_bitacora_tipo, d_mantenimiento, d_calibracion_atm, d_conectividad, d_respaldo, d_entradas_salidas, d_es_salidas, d_es_temperatura, d_es_presion, d_calibracion_sensor, d_avanzadas, d_avanzadas_programa, d_reasignacion, d_cajon. Marcas que quedan: «encogido» en nombres de canal de E/S y en 2 títulos de fila de Chaqueta (menos del 15 %, nunca bajo `fuenteMinima`, permitido por D8-5.4; en E/S pasa igual en vertical); «fuera» en d_info_sistema y d_cajon (contenido desplazable); OpcionesCalibracionSensor suelto a pantalla completa con Aplicar bajo el pliegue (desplazable; dentro de Opciones cabe) y el TypeError previo de AVISOS_PREVIOS.

Vertical: `hor_vertical_igual` en 47 escenarios (17 existentes de Opciones y 30 d_*): 45 idénticos; los 2 distintos (OpcionesFechaHora, d_fecha_hora) solo en el reloj grande con segundos. 71 archivos de pruebas de Opciones: 1470 pasan y 1 falla (v8b, ya falla en dev).

DECISIÓN SIN CONFIRMAR: riel plegado en dos columnas de iconos en lugar de un panel fijo con nombres (11 entradas de 88 px con nombre no caben en 698 de alto); el ancho del contenido da prioridad a las dos columnas de las secciones.

No cupo sin desplazar: la segunda fila de grupos de Información del sistema (opción: columnas tipo mampostería).

Componente ajeno: FilaInterruptor muestra el detalle en una línea con la letra reducida; con ajuste de línea Conectividad podría volver a 50/50.

Pendiente de banco: gesto de desplazamiento en las ventanas de ajuste en horizontal; el teclado sobre la ventana de ajuste a 1200 de alto tapa más proporción que en vertical.
## Grupo E: modales, diálogos, paneles superpuestos, teclados y Main.qml

| Componente | Vertical (dev) | Horizontal |
|---|---|---|
| PanelModal | ancho = padre − 96; alto = mín(altoTarjeta, alto − 192) | ancho = mín(padre − 96, `anchoRecuadroHorizontal` (1500 por defecto)); alto = mín(altoTarjeta, alto − 96) = 1104 en 1200 |
| PanelNotificaciones (alto 1400) | Tarjeta de PanelModal | Hereda PanelModal: 1500 x 1104 centrada; grupos plegables y desplazamiento como en vertical (no hizo falta panel lateral) |
| PanelEquipo (alto 1500; ≈19 filas de 76 en ListView) | Una columna, rótulo 50 % | Tarjeta de 1824; filas en dos columnas (Grid en Flickable `columnasEquipo`, separación 64), rótulo 56 %; con «Apagar equipo» todo cabe sin desplazar. La fila pasó a un componente en línea `FilaEquipo` compartido; el ListView vertical igual |
| ModalConfirmacion | ancho − 160; alto con tope alto − 192 | ancho máx. 1300, tope alto − 96 |
| ModalOperador | ancho − 160, alto 1300 | ancho máx. 1300, alto mín(1300, alto − 96): ≈5,5 filas de 96 visibles, lista desplazable |
| DialogoConfirmacion | ancho − 160, alto según el contenido | ancho máx. 1300 |
| VentanaDetalleAlarma | ancho 1000, alto tope alto − 120 con Flickable | ancho 1400 (menos alto) |
| PanelTeclado + TecladoAlfanumerico/Numerico | A lo ancho, al pie, alto ≤ 45 % (TEC-D06), margen 24; alfanumérico ≈676, numérico ≈708 (en 1200 el tope es 540: la fila inferior quedaba fuera) | Encabezado (título, valor, unidad, rango) a la izquierda de la rejilla (`encabezadoLateral`, `anchoEncabezado`, `anchoRejilla`, `desplazamientoRejilla`); rejilla centrada en 1920; margen arriba/abajo 9 (4 x 120 + 3 x 14 = 522 ≤ 540); teclas idénticas 96/206 x 120. Ocupa de y 660 a 1200 |
| Main.qml | — | `alarmaArranque` centrada con el ancho vertical (1104); `avisoSinConexionSesion` igual (franja arriba); navegación sin cambio |
| Tecla, ElementoCompartido, Tema/Teclado, TecladoProvisional, Capas | — | Sin cambio |

Escenarios (`hor_escenarios_e.py`): e_notificaciones, e_detalle_alarma, e_equipo, e_equipo_apagar, e_modal_confirmacion, e_dialogo_confirmacion, e_modal_operador, e_main_sin_conexion, e_cambio_clave_teclado, e_nuevo_usuario_teclado; y login_teclado, login_teclado_num, teclado_alfa, teclado_num. 0 problemas y 0 fuera en los modales (claro y oscuro). «cruza_divisor · Confirmar» es un falso positivo (la tecla superpuesta cruza un divisor de la pantalla de abajo). Con valor vacío, en el numérico «°C» se monta sobre «Rango»: igual en vertical (preexistente, no se tocó).

Vertical: `hor_vertical_igual` en los 14 escenarios, todos idénticos. 59 archivos de pruebas existentes: 1028 pasan; falla la de v8b (también en dev) y las de t23_sin_tarjeta por un identificador de otro grupo (corregido).

DECISIÓN SIN CONFIRMAR:
- Teclado: margen arriba/abajo del panel de 24 a 9 en horizontal para cumplir TEC-D06 sin achicar teclas (la fila inferior queda a 9 px del borde). Alternativa: relajar el 45 % solo en horizontal (≈47,5 %).
- Encabezado del teclado pegado al margen izquierdo, lejos de la rejilla; opción: alinearlo junto a las teclas.
- ModalOperador en una sola columna con desplazamiento (dos columnas exigiría cambiar el ListView, que lee test_t30_01).
- PanelEquipo: valores muy largos (versión con hash) bajan de letra (HorizontalFit), columna ≈366 contra 552 en vertical.

Pendiente de banco: teclado y modales con los táctiles reales en horizontal.
