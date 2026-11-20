# Revisión visual (RV): informe

19-nov. Rama `revision-visual` desde `dev` (75189880). Prompt: `docs/mis_plans/prompt_claude_code_revision_visual.md`. Sin merge a `dev` y sin compilar la entrega: Cristian confirma visualmente antes. La `data/` del repositorio principal quedó igual (sha256 de todos sus archivos antes y después, salvo logs y los -wal/-shm de SQLite); los worktrees de la etapa E se retiraron. El detalle de cada hallazgo está en `hallazgos.md` y la prueba de interacción en `R_interaccion.md`.

## Resumen

- **Escenarios:** 137 (132 que ya existían y 5 nuevos del grupo F), cada uno en 1200x1920 y 1920x1200, claro y oscuro, es y en (8 combinaciones, 1096 capturas offscreen), más la revisión I4 a 1024 × 1638 en es y en (22 pantallas). La pasada en ventana real (B2) repitió 1200x1920 y 1920x1200, claro y oscuro, en español (548 capturas), solo para íconos.
- **Detectores:** el nuevo detector de solapes (`tests/helpers/solapes_qml.py`) más los que ya había (textos que no caben y «fuera del lienzo"). La I4 no dio truncados ni solapes.
- **Hallazgos:** 38. Por severidad, 4 ALTA, 11 MEDIA y 23 BAJA. Por categoría, 9 de categoría 1 (corregidos) y 29 de categoría 2 (para decisión de Cristian), más 6 grupos de falsos positivos. La interacción agregó RVI-01 a RVI-05 (RVI-04 informativo).
- **Lo más importante corregido:** cuatro recuadros de campo que en tema oscuro quedaban blancos con el texto claro encima, de modo que lo tecleado no se veía: Nuevo usuario (incluida la lista de roles y «Cancelar»), Cambio de contraseña y el nuevo valor al ajustar un parámetro del ciclo o del equipo. También el nombre de programa largo, que tapaba el número de ciclo y el estado en Preciclo vertical.

## Corregidos (categoría 1)

Antes en `base/`, después en `final/` (y en `despues_d/` los escenarios recapturados durante la etapa D). Los valores claros de color no cambiaron: todos los cambios usan tokens cuyo valor claro es el que ya se veía.

- **RV-01. Nuevo usuario.** En `Pantallas/NuevoUsuario.qml`, los recuadros de campo, Rol, la lista de roles y «Cancelar» toman `Colores.fondoCampo` o `Colores.fondoTarjeta` (#FFFFFF en claro) en las dos orientaciones; antes, en vertical, un `Binding ... when: raiz.hz` los dejaba blancos también en oscuro. El código los marcaba «preexistente, pendiente de decisión»: se corrigió porque el texto tecleado no se veía (si Cristian prefería otra cosa, el cambio es de una línea por recuadro). Antes y después: `base/1200x1920_es/hor_oscuro_nuevo_usuario_roles.png` y `final/1200x1920_es/hor_oscuro_nuevo_usuario_roles.png`.
- **RV-02. Cambio de contraseña.** Lo mismo en `Pantallas/CambioClave.qml`: `hor_oscuro_cambio_clave.png`.
- **RV-38. Ajuste de un parámetro.** `campoNuevoValor` (`Pantallas/OpcionesParametrosCiclo.qml`) y `campoNuevoValorEquipo` (`Pantallas/OpcionesParametrosEquipo.qml`) sin color propio; ahora `Colores.fondoCampo`: `hor_oscuro_d_equipo_ajuste.png`, `hor_oscuro_d_ciclo_ajuste.png`.
- **RV-36. Arnés de teclados.** Lo mismo en `Pruebas/PruebaTecladoAlfanumerico.qml` y `PruebaTecladoNumerico.qml` (no es pantalla del equipo).
- **RV-03. Preciclo, nombre de programa largo en vertical.** En `Pantallas/PantallaPreciclo.qml`, un `TextMetrics` decide si el nombre cabe en una línea entre los divisores; si no, toma la misma caja de dos líneas con ajuste de letra que ya tenía el horizontal. Un nombre que cabe queda igual que antes. `hor_claro_b_preciclo_programa_largo.png` (el detector `cruza_divisor` desaparece).
- **RV-04. Teclado numérico.** En `Componentes/TecladoNumerico.qml`, el valor vacío muestra un espacio también en vertical, para que la unidad no se monte sobre «Rango» (también lo marcaba «pendiente de decisión»). `hor_oscuro_teclado_num.png` (desaparece el solape).
- **RV-05. Conectividad en horizontal.** En `Pantallas/OpcionesConectividad.qml`, el texto de los botones baja la letra para caber (`HorizontalFit`, mínimo `Escala.fuenteMinima`, sin elide). `1920x1200_es/hor_claro_d_conectividad.png`. El detector marca ahora `encogido`, que es el efecto buscado.
- **RV-16. Asistente, modo automatizado.** En `Pantallas/Instalacion.qml`, 16 px entre la ayuda y «Serie original del equipo», con el mismo desplazamiento para los campos de abajo: `hor_claro_inst_activacion_auto.png`.
- **RV-37. Reportes, Inicio y Salir en vertical oscuro.** En `Pantallas/Reportes.qml`, `IconoColor` también en vertical, con `Colores.iconoBarraMenu` y `Colores.textoNegro`, cuyos valores claros son exactamente los del SVG (#231F20 y #000). Verificado en ventana real: `despues_d/rv37_windows/hor_oscuro_reportes.png` y `hor_claro_reportes.png`. En offscreen esos íconos ya no se ven (MultiEffect), igual que los demás `IconoColor`.

## Pendientes de decisión de Cristian (categoría 2)

1. **RV-07, «RECONOCER FALLA» encogido en vertical (MEDIA).** Recomendación: rótulo en dos líneas con la letra del horizontal, sin cambiar el tamaño del botón.
2. **RV-08, clave cruda `estados.completado` en Ciclo en curso (MEDIA).** El puente publica «completado» y el i18n no tiene la clave. Recomendación: agregar `estados.completado` en es y en con el mismo texto que «exitoso».
3. **RV-09, códigos `FALLO_ESTERILIZACION` y similares en Reportes (MEDIA).** Recomendación: traducir la causa a un texto i18n en `reporte_dashboard.py` y usar la misma etiqueta en el título y el detalle.
4. **RV-10, aviso «Sin conexión» encima de la cabecera y la campana (MEDIA).** Recomendación: bajarlo bajo la cabecera (no tapar la campana, que da acceso a las alarmas).
5. **RV-11, el teclado tapa el botón de acción del formulario (MEDIA).** Recomendación: desplazar el formulario según `alturaOcupada` del teclado en Cambio de contraseña, Nuevo usuario y el asistente.
6. **RV-12, la lista de alarmas de Preciclo corta la última fila sin pista (MEDIA).** Recomendación: indicador de desplazamiento (degradado al pie o contador «N más»).
7. **RV-13, avisos de sin conexión sobre la gráfica (MEDIA).** Recomendación: dejarlo así si se quiere tapar a propósito una curva no vigente; si no, moverlos a la franja del título.
8. **RV-06, la última fila de Parámetros del ciclo pegada a la leyenda (MEDIA).** Se probó un margen y se revirtió, porque quita la fila asomada que avisa que hay más. Recomendación: indicador de desplazamiento y luego el margen.
9. **RV-14, título del teclado en horizontal partido en una columna estrecha (BAJA).** Recomendación: ensanchar la columna del encabezado del teclado.
10. **RV-15, interruptor «Activo» de Nuevo usuario desalineado (BAJA).** Recomendación: alinearlo a la etiqueta «Estado» y a los campos.
11. **RV-17, hora sola en la segunda línea del fin de ciclo en horizontal (BAJA).** Recomendación: unir «a las HH:MM» con espacio duro en la plantilla.
12. **RV-18, panel de equipo en vertical con filas fuera de vista (BAJA).** Recomendación: indicador de desplazamiento.
13. **RV-19, velo del diálogo «Apagar equipo» (BAJA).** Recomendación: velo sobre todo el panel; no se tocó por ser el diálogo de apagado.
14. **RV-20, filas no elegidas del modal de operador con poco contraste en oscuro (BAJA).** Recomendación: confirmar en la pantalla real antes de tocar `fondoSutil`.
15. **RV-21, tarjetas de mes de altura distinta en Reportes Año (BAJA).** Recomendación: seis filas fijas por mes.
16. **RV-22, programa en naranja sobre blanco en Historial y Reportes (BAJA).** Recomendación: usar el naranja de texto (`advertenciaTexto` o equivalente) en lugar del de relleno.
17. **RV-23, modal «Alarmas del periodo» con espacio vacío (BAJA).** Recomendación: más filas por página.
18. **RV-24, renglón que asoma bajo la franja de botones del ajuste de parámetro (BAJA).** Recomendación: bajar la tarjeta modal o extender el velo.
19. **RV-25, nombres de salida de tamaños distintos en vertical (BAJA).** Recomendación: dos líneas como en horizontal, si el alto de la tarjeta lo permite.
20. **RV-26, flecha «‹» de Parámetros del ciclo desalineada (BAJA).** Recomendación: reemplazar el glifo de 96 px por un ícono de flecha.
21. **RV-27, nota de «usuario eliminado» en la pestaña Operadores (BAJA).** Recomendación: mostrarla solo en la pestaña Usuarios.
22. **RV-28, rol «operador» sin traducir en inglés (BAJA).** Recomendación: mapear «operador» en `etiquetaRol`.
23. **RV-29, «ADC undefined» en Calibración de sensor (BAJA).** Recomendación: comparar con `== null`.
24. **RV-30, secciones de Información del sistema bajo el borde (BAJA).** Recomendación: indicador de desplazamiento.
25. **RV-31, «módulo E/S» frente a «the controller» (BAJA).** Recomendación: «the I/O module» (MES-01).
26. **RV-32, «secado» en español en el selector en inglés (BAJA).** Recomendación: pasar el texto por i18n.
27. **RV-33, eslogan de la intro en español en inglés (BAJA).** Recomendación: confirmar si es marca; si no, i18n.
28. **RV-34, línea de versión de la intro con poco contraste en claro (BAJA).** Recomendación: subir el contraste de ese texto.
29. **RV-35, rótulos pequeños y pegados en la tira de Ciclo en curso (BAJA).** Recomendación: dejarlo como el mockup salvo que en la estación cueste leerlos.
30. **RVI-01, la lista de Usuarios no muestra el usuario recién creado (MEDIA).** Recomendación: llamar a `control.cargar()` al volver de Nuevo usuario (`StackView.onActivated` o la señal de éxito de `puenteNuevoUsuario`).
31. **RVI-02, «Seleccione un rol» sigue en rojo tras elegir (BAJA).** Recomendación: limpiar el error del rol al elegir.
32. **RVI-03, `tiempo_esterilizacion` admite hasta 9999 min (BAJA).** Recomendación: revisar el máximo en el catálogo de parámetros.
33. **RVI-05, unidad «seg» sin traducir en inglés (BAJA).** Recomendación: pasar la unidad del catálogo por `Unidades`/i18n.
34. **Aviso «abrir la puerta de descarga».** CLAUDE.md lo describe en los ajustes del 9-nov, pero no está en el QML de `dev`: el `git stash` de la rama `ciclo-prion` («ajuste abrir_puerta_descarga (siguiente version)») parece tenerlo guardado. ¿Debe entrar?

## Falsos positivos

Detalle en `hallazgos.md`, «Falsos positivos»:
- Botones de acción de Preciclo sin cuerpo y formas de Reportes fuera de su recorte: son artefactos de offscreen; en ventana real se ven bien.
- Botón forzado del ingeniero: retirado en la beta.3.
- Textos en español en el panel de notificaciones: vienen del doble de prueba.
- Varias detecciones de los detectores: teclas del teclado, rejilla y ejes de la gráfica, contenido desplazable, íconos y animaciones.

Como el renderizador offscreen tampoco recorta los `Shape`, conviene agregarlo a las limitaciones conocidas de la skill `revision-visual-pantallas` (hoy solo dice MultiEffect y animaciones).

## Pruebas

- **Pruebas nuevas:** `tests/test_rv_solapes_qml.py`, con 6 casos que pasan: dos textos encimados dan un solape; un texto sobre su rectángulo no; lo tapado por un modal no; lo separado por un clip no; un texto bajo un botón sí; y no cuenta el interlineado de la hora grande.
- **Relacionadas:** las del prompt y las de las pantallas tocadas pasan. Hay dos fallas previas a la rama, que fallan igual en el árbol sin cambios:
  - `test_v8b_textos.py::test_descripciones_citan_nombres_visibles_de_parametros`: una descripción cita «Margen de recuperación por presión», rótulo renombrado en CRI-04.
  - `test_hor_b_textos_contraste_qml.py`: su QML asigna `forzable`, propiedad retirada en la beta.3.
- **Suite completa** (una vez, offscreen, 1 h 40 min): 12531 pasan, 32 fallan, 6 errores, 11 omitidas y 15 xfail.
  - De las 38, 11 pasan al repetirlas con el backend y el simulador de la etapa E detenidos: eran choques con los puertos 8000 y 8001, que estaban ocupados durante la suite (sesión, Nuevo usuario y similares).
  - De las 27 restantes, 24 fallan igual en un worktree limpio de `dev` (75189880), así que son previas a la rama. Entre ellas: `test_q1_r1p3_rango_calentamiento` y `test_t12_c07_c13_json` (esperan 10 programas y ya hay 12 con Prion), `test_t29_descompresion_fin_modo_solido` con los programas de fábrica, `test_s9_planta_simulada`, `test_t12_v12_ventana_referencia_en_cero`, `test_t17_copia_programa`, `test_s1_sen01_fuera_de_ciclo`, `test_v8b_textos` (rótulo renombrado en CRI-04) y los 6 errores de `test_hor_b_textos_contraste_qml` (propiedad `forzable` retirada).
  - Las otras 3 fallaban solo en este repositorio, no por la rama: la suite reescribió durante la corrida los seis programas de `src/autoclave/cycles/user/*.json` (migraciones T28-M3 y CRI con sus marcas), que estaban limpios al empezar. Se restauraron con `git checkout`. Luego `test_t28_a14_m3_brecha` pasa, y `test_c2_programas_persistentes::test_usuario_con_valores_fuera_de_catalogo_no_es_ejecutable` depende de los `*.json.bak` ignorados del 13-nov de `cycles/user` (en un worktree limpio pasa).
  - **Para Cristian:** alguna prueba escribe en los programas de usuario del repositorio. Conviene encontrarla y aislarla en un directorio temporal.
  - La rama no cambia código Python: el diff de `src/` son 11 archivos QML.
- **Revisor independiente (etapa F):** sin hallazgos ALTA ni MEDIA. Revisó el diff de `src/` y las capturas antes y después con diferencias por píxel. Sus tres BAJA se atendieron:
  - RV-06 revertido.
  - El detector de solapes ya no aborta la tanda si falla.
  - RV-37 ya no se ve en offscreen, anotado arriba.
- **Verificación (etapa F):** recaptura completa en `final/`. Frente a `base/`, solo desaparecen las detecciones de RV-03 y RV-04 y aparecen los `encogido` buscados de RV-05; ningún problema nuevo. Las diferencias de solapes en `e_main_sin_conexion` son la hora, que cambió entre capturas.

## Herramientas nuevas o cambiadas

- **`tests/helpers/solapes_qml.py`:** detector de solapes. Sus resultados van en la clave `solapes` de `resumen_<tema>.json`, sin tocar `problemas`, que comparan `resp_capturas.py` y `test_resp_sin_barras.py`.
- **`tests/banco/hor_capturas.py`:** `--listar` y el detector de solapes.
- **`tests/banco/hor_escenarios_f.py`:** escenarios nuevos del grupo F.
- **`tests/banco/hor_escenarios_b.py`:** sin la propiedad retirada `forzable`.
- **`tests/banco/i4_truncado_banco.py`:** solapes, más `--destino` e `--idiomas`.
- **`tests/banco/rv_interaccion.py`, `rv_flujos*.py` y `rv_backend_simulado.py`:** arnés y flujos de interacción.

## Limitaciones

Lo que debe verse en la pantalla real de la estación:
- Los toques con el dedo: tamaño de las manijas y arrastres.
- El zoom de dos dedos.
- El escalado y el brillo de los paneles: contraste de los grises en oscuro (RV-20, RV-34).
- Los íconos y sombras dibujados con MultiEffect en todas las pantallas. La pasada B2 los cubrió en español, sin encontrar otros defectos que RV-37.
- El carácter de máscara de las contraseñas, que offscreen dibuja como cuadros.

Otras limitaciones:
- La interacción corrió en offscreen porque la sesión de Windows estaba bloqueada; con la sesión abierta, el arnés abre las ventanas en primer plano.
- No se probaron la pantalla 2 en paralelo ni la pérdida del backend a mitad de una pantalla.
