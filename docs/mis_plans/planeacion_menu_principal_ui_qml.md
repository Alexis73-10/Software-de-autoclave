# Planeación — Menú Principal (UI QML) — réplica funcional del mockup v3

Versión: 1.4 (resultados de la Fase 2: curva del último ciclo disponible, operador no registrado)
Ubicación prevista: `docs\mis_plans\planeacion_menu_principal_ui_qml.md`
Rama de trabajo: `dev`
Ejecuta: Claude Code (terminal). Este documento no contiene código.
Estado: Fase 0 completada. Autorizadas las Fases 1 a 3. Fase 4 diferida (ver sección 8).

---

## 1. Propósito y alcance

Implementar en QML la pantalla "Menú Principal" según el mockup `menu_principal_v3.png`, conectada a datos reales del backend, dentro de la migración total de tkinter a QML.

Dentro de alcance:
- Pantalla Menú Principal completa: encabezado, título, cuatro tarjetas de acción, campo de tiempo adicional de secado, Resumen del Sistema y barra inferior.
- Componentes QML reutilizables (tarjeta de menú, tarjeta de resumen) y, si ya existen en otras pantallas, reutilización del encabezado y de la barra inferior.
- ViewModel Python y proveedor de datos de solo lectura para el Resumen del Sistema y el campo de secado.
- Endpoint de solo lectura `GET /cycle/summary` en el backend (autorizado) para el Resumen del Sistema.
- Pantalla validada en un arnés de pruebas (`Pruebas/PruebaMenuPrincipal.qml`), sin conectarla a `Main.qml`.
- Pruebas automáticas y verificación visual contra el mockup.

Fuera de alcance (no tocar):
- Cableado del menú a `Main.qml` y a la navegación real (Fase 4, diferida).
- Refactor de `Ciclo.qml`, `PantallaCicloEnCurso.qml`, `BarraSuperior.qml` y `BarraInferior.qml` (tienen cambios sin commit; la duplicación de encabezado y barra inferior queda como deuda técnica anotada).
- Cambios en la app PySide (login y configuración).
- Pantallas Historial, Reportes e Información (no existen todavía).
- Login QML (pospuesto; se usa el login de PySide).
- Reubicación de Programas, Mantenimiento, Conectividad e Impresión (Cristian las ubicará en login y Reportes en planes propios).
- Lógica de control, sensores, actuadores, HAL, firmware.
- Cualquier escritura en base de datos o parámetros desde esta pantalla.
- Ejecución en equipos de campo: por ahora solo PC de desarrollo.

## 2. Referencias

- Mockup de referencia: `menu_principal_v3.png` (1188 × 1906 px). Cristian lo copia a `docs\mockups\menu_principal_v3.png` (el informe de Fase 0 confirmó que aún no está en el repo; sin él no se inicia la Fase 3). Es referencia visual, no fuente de assets: los iconos nuevos del mockup (usuario, ciclos totales, secado) están dibujados solo ahí.
- Mockup original del diseñador: `mockup-01` (pantallas espera, menú principal, login, nuevo usuario, opciones, ciclo).
- Plan vigente previo: `docs\mis_plans\planeacion_menu_principal.md` (roles, numeración de programas, operadores). Claude Code debe leerlo antes de nada y reportar contradicciones con este documento, sin corregirlas en silencio.
- Plan de teclados: `docs\mis_plans\planeacion_teclados_qml.md` (solo como referencia de estilo de plan; esta pantalla no usa teclados).
- Plan de pantalla de ciclo en curso: `planeacion_pantalla_ciclo_en_curso.md` (convenciones de responsividad y de formato de presión).

## 3. Decisiones ya tomadas por Cristian

D-01. Del Menú Principal se eliminan las tarjetas Iniciar ciclo, Programas, Conectividad, Impresión y Mantenimiento. Las reubica él: Mantenimiento dentro de iniciar sesión; Impresión dentro de Reportes; el resto en login o Reportes.
D-02. La tarjeta Iniciar ciclo se reemplaza por Iniciar sesión, con la misma forma (ancha, borde verde).
D-03. Tarjetas que permanecen: Historial, Reportes, Información.
D-04. "Tiempo adicional de secado" es un parámetro de cada programa. El campo del menú muestra el del programa seleccionado. Va en el menú, no en el Resumen del Sistema.
D-05. En el Resumen del Sistema, "Reportes" se reemplaza por "Ciclos totales del equipo". Se mantienen Próximo mantenimiento, Ciclos hoy y Último ciclo.
D-06. Barra inferior: se quita el icono de usuarios; Salir queda a la izquierda y Home a la derecha. Los dos separadores verticales se conservan (a confirmar, ver MP-03).
D-07. Migración a QML total y sin coexistencia con tkinter; canal backend→UI por polling; login PySide por ahora; engranaje abre la configuración PySide por ahora.
D-08. Decimal con punto, nunca coma, en toda la interfaz.
D-09. Pantalla responsiva ajustable a 9:16 (la convención de escala concreta quedó fijada en D-18).
D-10. Commits solo después de que Cristian confirme visualmente el resultado. Git es respaldo; no se hace `git pull` en el PC del autoclave.
D-11. El menú se construye y valida en un arnés de pruebas; su cableado a la navegación espera a que `PantallaCicloEnCurso` esté integrada en `Main.qml` y exista cancelación de ciclo desde QML (plan aparte).
D-12. Iniciar sesión no muestra usuario ni rol (la sesión vive en el subproceso PySide). Salir queda deshabilitado con `TODO(MP-03)`. Home inactivo.
D-13. Historial, Reportes e Información: visibles, atenuadas y deshabilitadas.
D-14. Ciclos totales = último `numero_ciclo` (`TODO(MP-06a)`); Próximo mantenimiento = "—"; Ciclos hoy y Último ciclo salen de un endpoint nuevo de solo lectura `GET /cycle/summary`.
D-15. Rótulo "Realizados" (no "Completados") en Ciclos totales y Ciclos hoy mientras no se definan estados terminales.
D-16. Sin selección o sin conexión, los campos muestran "—". Se agrega un aviso provisional "Sin conexión con el equipo" cuando el backend no responde.
D-17. La campana muestra el contador de alarmas con la fuente existente; sin fuente, sin contador. Sin acción al tocar.
D-18. Escala: convención `m()` de `Ciclo.qml`, no `Escala.px`. Las secciones de `planeacion_menu_principal.md` (v0.3) contradichas por este plan quedan marcadas como reemplazadas, sin borrarlas.
D-20. Las cuatro tarjetas del Resumen del Sistema también son botones: emiten su propia señal y tienen estado presionado y deshabilitado; sin flecha (el mockup no la tiene). Cada una abre una ventana flotante de solo visualización (D-21); si todavía no hay datos que mostrar, queda deshabilitada o muestra "—".
D-21. Las tarjetas del Resumen del Sistema abren una ventana flotante (superpuesta, dentro de la misma pantalla), solo de visualización y sin escritura. Próximo mantenimiento: fecha del último mantenimiento y cuántos ciclos faltan para el próximo. Último ciclo: gráfica del ciclo, datos del ciclo y quién lo envió. Contenido de Ciclos totales y Ciclos hoy: por definir (MP-14).
D-22. Archivos compartidos con otros trabajos (`db_manager.py`, `server.py`, `es.json`): se edita sobre el estado actual y en el commit se incluyen solo los bloques de este trabajo (`git add -p`). Propuesta de Claude Code aceptada por defecto; Cristian puede cambiarla.
D-23. Fase 2 hecha: `GET /cycle/summary` (total, ciclos de hoy, último ciclo con fecha de inicio, programa, resultado y operador) y `GET /cycle/history/{id}/graph` (curva del ciclo, un punto por segundo, mismo formato que la gráfica del ciclo en curso; se pide solo al abrir la ventana flotante de Último ciclo). La fecha mostrada de Último ciclo es la de inicio (Claude Code la dio por confirmada por Cristian; confirmar).
D-24. El operador que inició el ciclo no se guarda hoy: la ventana de Último ciclo muestra "—" con `TODO(MP-14b)`. Guardarlo exige identificar al operador al iniciar el ciclo y cambiar el esquema de `ciclos`; va en un plan aparte.
D-19. No se tocan ni se incluyen en commits los cambios sin commit existentes; el commit contiene solo archivos de este trabajo.

## 4. Hallazgos y estado

Estado tras la respuesta de Cristian al informe de Fase 0.

MP-01 — Posición del Menú Principal en el flujo. Alta. DIFERIDO (D-11). Recomendación vigente: espera → Menú Principal; la pantalla de ciclo previa se alcanza tras identificación. Se implementa en la Fase 4.

MP-02 — Menú con ciclo en curso. Alta. DIFERIDO (D-11). Vigente: con ciclo en curso la UI permanece en la pantalla en curso y Home lleva a ella. No se puede probar hasta que `PantallaCicloEnCurso` esté integrada y exista cancelación desde QML.

MP-03 — Sesión y Salir. Media. RESUELTO (D-12). Requiere login QML o un canal de sesión para mejorar; fuera de alcance.

MP-04 — Destinos inexistentes. Media. RESUELTO (D-13).

MP-05 — Secado sin programa seleccionado. Media. RESUELTO para el caso sin selección o sin conexión (D-16). En el backend el programa seleccionado es siempre `bowe_dick` al arrancar, por lo que "sin selección" solo ocurre sin conexión. Ver MP-11.

MP-06 — Datos del resumen. Media. RESUELTO (D-14, D-15). Antes de definir "hoy", verificar cómo se guarda la fecha en la tabla `ciclos` (UTC o local) y documentarlo en el informe de la Fase 2.

MP-07 — Login QML pospuesto. Baja. Sin cambio. La tarjeta Iniciar sesión solo emite una señal en el arnés; el lanzamiento del login PySide se conecta en la Fase 4 (la app PySide no acepta argumentos para abrir directo en login; no se modifica).

MP-08 — Assets y tipografía. Baja. RESUELTO por la Fase 0: Montserrat (con OFL) y 47 SVG Tiny 1.2 ya están en el repo. Falta solo el icono de ciclos totales, que se crea provisional en SVG Tiny 1.2 y se lista para el diseñador. Iconos existentes a reutilizar: usuario, historial, reportes, informacion, casa, salir_sesion, sensor_tiempo_secado, mantenimiento, reloj, campana, engranaje.

MP-09 — Campana y engranaje. Baja. RESUELTO (D-17). Engranaje: señal en el arnés; el lanzamiento (`LanzadorAjustes`) se conecta en la Fase 4.

MP-10 — Dos procesos de UI. Baja. RESUELTO por la Fase 0: la tabla `ciclos` no tiene columna de puerta; los datos son del equipo y ambas UI mostrarán lo mismo.

MP-11 — "Tiempo adicional de secado". Media. RESUELTO: es un parámetro nuevo por programa (distinto de `secado.tiempo_secado`). Crearlo afecta parámetros de programa, validación, interfaz de configuración y ejecución del ciclo (control, Clase C), por lo que va en un plan aparte; no se implementa aquí. Hasta que exista, el campo del menú muestra "—" y no lee ningún parámetro (`TODO(MP-11)`).

MP-14 — Contenido de las ventanas flotantes del resumen. Media. PARCIALMENTE RESUELTO. Verificado en la Fase 2: (a) la curva del ciclo existe y se lee por `GET /cycle/history/{id}/graph`; (b) el operador no se guarda (D-24); (c) no hay datos de mantenimiento, la ventana de Próximo mantenimiento muestra "—" (plan aparte de mantenimiento por ciclos). Pendiente de Cristian: contenido de las ventanas de Ciclos totales y Ciclos hoy. Hasta que lo defina, esas dos tarjetas quedan deshabilitadas.

MP-12 — Acciones que desaparecen de Home (puerta, reinicio de falla, reconocer alarma). Alta (Clase C). SEPARADO por decisión de Cristian: se trata en un plan aparte de alarmas y fallas y no forma parte de esta pantalla. Hallazgos de la Fase 1 para ese plan: la puerta existe solo en `Ciclo.qml`; el reinicio de falla no existe en QML ni en PySide; "reconocer alarma" no existe en ninguna capa (`/cycle/acknowledge` confirma el resultado del ciclo, no reconoce alarmas).

MP-13 — Visibilidad de estado, alarmas y conexión. Alta. RESUELTO parcialmente (D-16, D-17): el menú nuevo no tiene tarjetas de estado de máquina, puertas, alimentación ni versiones, y esas se perderían de la vista del menú. Se aceptan como ausentes por decisión de Cristian; se cubren solo alarmas (campana) y conexión (aviso).

## 5. Especificación visual (referencia: mockup v3, 1188 × 1906)

Las medidas están en unidades del mockup v3 (1188 × 1906). La implementación usa la convención `m()` de `Ciclo.qml` sobre el marco de 1196 de ancho del diseñador (D-18). Según la verificación de Fase 1, el marco real mide 1196 × 1917 (no 1914). El v3 mide 1188 × 1906, por lo que el desplazamiento es de unos 4 px por lado en x y de unos 5 a 6 px en y; son valores aproximados porque el recorte del v3 se hizo a ojo. Las medidas de esta sección son de referencia: la pantalla se valida por comparación visual con el v3 y se ajusta ahí, no por conversión exacta de coordenadas. Donde el proyecto ya tenga tokens de tema (colores, tipografía, radios), se usan esos tokens y se reporta cualquier diferencia con los valores de abajo.

Estructura vertical:
- Encabezado: logo a la izquierda, hora y fecha centradas, campana con contador y engranaje a la derecha. Igual que en las demás pantallas; reutilizar el componente existente.
- Título: icono de casa centrado y texto "MENÚ PRINCIPAL" (blanco, semibold).
- Fila 1 (y 500–820, alto 320): Iniciar sesión (ancho 716, x 59–775) e Historial (ancho 350, x 794–1144).
- Fila 2 (y 844–1164, alto 320): Reportes (x 59, ancho 349), Información (x 427, ancho 349), Tiempo adicional de secado (x 795, ancho 349).
- Márgenes laterales del contenido: 59; ancho útil 1085. Separación horizontal entre tarjetas 19; vertical 24.
- Anclaje: el encabezado va anclado arriba y la barra inferior anclada al borde inferior de la pantalla (margen inferior de unos 20 del mockup, no fluye detrás del contenido). El espacio sobrante en pantallas más altas se reparte en el área de contenido entre los títulos y la barra.
- Título "MENÚ PRINCIPAL" con icono de casa centrado y título "RESUMEN DEL SISTEMA": ambos son parte de la pantalla (Fase 3). La galería de la Fase 1 solo muestra componentes y no los incluye.
- Título "RESUMEN DEL SISTEMA": centrado, semibold 39, centro en y 1245.
- Tarjetas de resumen (y 1296–1626, alto 330): Ciclos totales (ancho 230), Próximo mantenimiento (293), Ciclos hoy (206), Último ciclo (308); separación 16.
- Barra inferior: x 39–1167, y 1747–1886, fondo blanco redondeado, con "V: 1.0" abajo a la derecha. Salir a la izquierda, Home a la derecha, separadores verticales gris claro en x 352 y x 839.

Tarjetas de menú:
- Fondo blanco, radio 26. Iniciar sesión con borde verde de 4.
- Icono con aro de 122 de diámetro arriba a la izquierda (fila 1) o 106 (fila 2), título en negrita, descripción en regular, flecha a la derecha abajo.
- Fila 1: título Montserrat Bold 28.75, descripción Regular 24. Fila 2: título Bold 25, descripción Regular 21.
- Tiempo adicional de secado: sin flecha; valor en negrita 46 arriba a la derecha (por ejemplo "10 min"), título en dos líneas ("TIEMPO ADICIONAL" / "DE SECADO") y debajo "Programa seleccionado".
- Estado presionado: atenuación ligera (provisional). Estado deshabilitado: opacidad reducida y sin respuesta táctil.

Tarjetas de resumen:
- Son botones (D-20): señal propia, estado presionado (atenuación ligera) y deshabilitado, sin flecha.
- Fondo blanco, radio 24. Icono con aro de 106 centrado arriba; rótulo en negrita 20 (una o dos líneas); valor en negrita hasta 46; subrótulo regular 19.
- El valor se reduce automáticamente para caber en la tarjeta (tamaño mínimo definido) sin recortar.
- Último ciclo: rótulo, fecha y hora en negrita 19, "Programa:" y "Resultado:" en regular 17 con el valor en negrita; resultado exitoso en verde, programa en naranja (según el mockup).

Colores de referencia del mockup (usar tokens existentes si los hay): verde `#009535` (borde e icono), texto verde `#0D8C2C`, azul `#0361EC`, naranja `#FF9720`, texto naranja `#F26500`, morado `#9827D1`, texto negro.

## 6. Especificación funcional

6.1 Encabezado
- Hora en formato 24 h `HH:MM`, fecha `D mmm - AAAA` con mes abreviado en español y en minúscula (ene, feb, mar, abr, may, jun, jul, ago, sep, oct, nov, dic), mediante tabla propia, sin depender de la configuración regional del sistema operativo.
- Hora de reloj solo para visualización; nunca se usa para temporización de control (regla C-01 se aplica a temporizadores del proceso, no a esta pantalla).
- Engranaje: abre la configuración PySide. Campana: ver MP-09.

6.2 Tarjetas de acción
- Iniciar sesión: abre el login PySide (MP-07). Estados según MP-03.
- Historial, Reportes, Información: según MP-04.
- Tiempo adicional de secado: según MP-05 y MP-11. Hasta que Cristian responda MP-11 muestra "—" con `TODO(MP-11)`.

6.3 Resumen del Sistema
- Ciclos totales del equipo: último `numero_ciclo`, entero sin separador de miles; rótulo del subtexto "Realizados"; ver D-14 y MP-06a.
- Próximo mantenimiento: días restantes enteros, redondeando hacia arriba; si el plazo venció se muestra "Vencido"; sin fuente se muestra "—". Ver MP-06b.
- Ciclos hoy: ciclos terminados desde las 00:00 hora local del equipo, tomados de `GET /cycle/summary`. Subtexto "Realizados". Ver D-14 y MP-06c.
- Último ciclo: fecha `DD/MM/AAAA` y hora `HH:MM`, número de programa y resultado; sin ciclos previos se muestra "—" en cada campo. Ver MP-06d.
- Todo dato ausente o con error de lectura se muestra "—"; nunca se muestra un valor inventado ni un valor anterior desactualizado sin marcarlo.
- Sin respuesta del backend se muestra el aviso "Sin conexión con el equipo" y los datos pasan a "—" (D-16). El resultado de un ciclo se presenta con los estados reales: COMPLETADO, FALLO, CANCELADO; si `resultado` es nulo (proceso interrumpido) se muestra "—".

6.4 Barra inferior
- Salir y Home según MP-02 y MP-03. Home en esta pantalla está inactivo o resaltado, ya que es la pantalla actual (a definir con el diseñador; provisionalmente inactivo).

6.5 Actualización de datos
- El ViewModel consulta al activarse la pantalla y luego por polling cada 10 s (provisional; ajustable). Las consultas son de solo lectura y baratas. Si el backend no responde, se conservan los últimos valores y se marca el error en el estado interno, sin bloquear la UI.

## 7. Diseño técnico propuesto

Los nombres y rutas son propuestas; Fase 0 los ajusta a la estructura real del repositorio.

- Componentes QML reutilizables: tarjeta de menú (propiedades: título, descripción, icono, color de acento, borde, valor opcional, flecha visible, habilitada) y tarjeta de resumen (icono, rótulo, valor, subrótulo, o contenido propio para Último ciclo). Genéricos, sin datos ni lógica de negocio.
- Pantalla `MenuPrincipal.qml`: solo composición y enlace a propiedades del ViewModel; sin lógica de datos.
- `MenuPrincipalViewModel` (Python, QObject): expone propiedades de solo lectura (hora y fecha formateadas, estado de sesión, datos del resumen, programa seleccionado y su tiempo adicional de secado, estados de habilitación de tarjetas) y señales de navegación. Sin acceso directo a hardware.
- Proveedor de datos de solo lectura: funciones puras para ciclos totales, ciclos de hoy, último ciclo y próximo mantenimiento, que consultan la persistencia existente. No introduce tablas ni escrituras; si hiciera falta un contador persistente nuevo, se documenta como cambio aparte (MP-06a).
- Formateadores (fecha, hora, número, "—") en un módulo aparte con pruebas unitarias.
- Encabezado y barra inferior: componentes nuevos, solo para el menú. Los actuales están duplicados inline en `Ciclo.qml` y `PantallaCicloEnCurso.qml` y `BarraSuperior.qml` / `BarraInferior.qml` no coinciden con el mockup; no se refactorizan (D-19). Se anota la deuda técnica en el informe.
- Tema: se agregan los tokens de color del mockup (`#009535`, `#0361EC`, `#FF9720`, `#9827D1`) a `Colores.qml`, y se reutilizan `Tipografia` (`tarjeta_titulo`, `tarjeta_descripcion`, `kpi_valor`) y `TarjetaContenido` cuando coincidan; las diferencias se reportan.
- Navegación: en esta etapa las tarjetas solo emiten señales dentro del arnés. El cableado al `StackView` de `Main.qml` es la Fase 4.
- Backend: único cambio autorizado, `GET /cycle/summary` de solo lectura (total, ciclos de hoy, último ciclo con fecha, número de programa y resultado), con pruebas. No se modifica control, HAL ni parámetros.
- Sin dependencias nuevas (SOUP). Si algo lo exigiera, se detiene y se reporta.

## 8. Plan de ejecución por fases

Fase 0 — Reconocimiento. COMPLETADA. Informe F0-01 a F0-12 recibido. Hallazgos relevantes ya incorporados arriba. Queda una verificación complementaria, de solo lectura, que se ejecuta al inicio de la Fase 1:
1. MP-12: dónde existen hoy, en la UI QML, las acciones de puerta, reinicio de falla y reconocer alarma, y si hay forma de realizarlas fuera de Home.
2. Fuente existente del contador de alarmas para la campana.
3. Cómo se guarda la fecha en `ciclos` (UTC o local).
4. Alto del marco del diseñador en `Ciclo.qml` y confirmación del desplazamiento de 4 px.

Fase 1 — Tema y componentes. Tarjeta de menú y tarjeta de resumen genéricas; tokens de color; icono provisional de ciclos totales (SVG Tiny 1.2); encabezado y barra inferior nuevos. Verificación: galería de componentes en un archivo de `Pruebas/`, con estados normal, presionado, deshabilitado y valor largo.

Fase 2 — Backend y datos. Empieza con la verificación de solo lectura de MP-14 (a, b, c) y la reporta antes de implementar. Endpoint `GET /cycle/summary` de solo lectura con pruebas; ViewModel o puente siguiendo el patrón ya usado por `InfoEquipo` y `ui_bridge`; formateadores con pruebas unitarias (sin datos, un ciclo, cambio de día, FALLO, CANCELADO, resultado nulo, valor largo, backend sin respuesta).

Fase 3 — Pantalla en arnés. Incluye un componente genérico de ventana flotante, la ventana de Último ciclo (con curva por `GraficaCiclo.qml`) y la de Próximo mantenimiento (con "—"); Ciclos totales y Ciclos hoy quedan deshabilitadas hasta definirlas. `MenuPrincipal.qml`, con las ventanas flotantes de solo visualización de D-21 (el contenido de Último ciclo y Próximo mantenimiento depende de lo que confirme la verificación de MP-14), compuesta con los estados de D-12 a D-17 y probada en `Pruebas/PruebaMenuPrincipal.qml`. Verificación visual por captura a la proporción del mockup y a 9:16, comparada con v3. Requiere el v3 copiado a `docs\mockups\`.

Fase 4 — Navegación e integración. DIFERIDA (D-11). Se planea aparte cuando `PantallaCicloEnCurso` esté integrada y exista cancelación de ciclo desde QML. Contenido previsto: transición desde espera (MP-01), comportamiento con ciclo en curso (MP-02), lanzamiento del login PySide y de la configuración, y regreso.

Fase 5 — Cierre de lo autorizado. Suite completa (`python -m pytest`), pruebas QML con `QT_QPA_PLATFORM=offscreen`, revisión de que solo se tocaron los archivos de este trabajo. Cristian valida visualmente; solo entonces se hace el commit en `dev`, únicamente con archivos de este trabajo (D-19).

Entre fases, Claude Code se detiene y reporta; no encadena fases sin confirmación de Cristian.

## 9. Criterios de aceptación

- La barra inferior queda pegada al borde inferior y los títulos MENÚ PRINCIPAL y RESUMEN DEL SISTEMA están presentes.
- Las tarjetas de resumen responden como botones (presionado y deshabilitado) y emiten su señal.
- La pantalla coincide con el mockup v3 (disposición, jerarquía, colores y textos) con diferencias menores de píxel; las diferencias intencionales están listadas.
- Con datos reales, el Resumen del Sistema muestra los valores correctos; con datos ausentes, "—".
- Con y sin programa seleccionado, el campo de secado se comporta según MP-05.
- Ninguna acción de esta pantalla escribe datos ni actúa sobre el equipo; el único cambio de backend es un endpoint de lectura.
- El menú se verifica en el arnés; el comportamiento con ciclo en curso (MP-02) queda para la Fase 4.
- Sin respuesta del backend, aparece el aviso "Sin conexión con el equipo" y los datos muestran "—".
- Sin dependencias nuevas, sin tkinter, y todas las pruebas pasan.
- Todos los `TODO(MP-xx)` restantes están listados en el informe final.

## 10. Riesgos

- Ciclos totales derivados de un historial depurable puede dar un total incorrecto (MP-06a).
- Mostrar un valor desactualizado como si fuera vigente en un dispositivo de Clase C; mitigado con "—" y marca de error.
- Navegación que oculte un ciclo en curso (MP-02); mitigado por diferir la integración.
- Pérdida de acceso a puerta, reinicio de falla y reconocer alarma al retirarlas de Home (MP-12).
- Pérdida de visibilidad de estado de máquina, puertas y alimentación en el menú (MP-13).
- Texto o iconos no conformes con Qt SVG Tiny 1.2 rompen el renderizado en silencio (MP-08).
- Endpoints del backend sin autenticación (hallazgo H-03): esta pantalla solo debe usar lecturas, y mientras no se resuelva H-03 no se habilita en equipos de campo.

## 11. Pendientes de Cristian y de diseñador

De Cristian:
- MP-14: qué muestran las ventanas de Ciclos totales y Ciclos hoy.
- D-23: confirmar que la fecha de Último ciclo es la de inicio.
- Copiar `menu_principal_v3.png` a `docs\mockups\` (bloquea la Fase 3).
- Confirmar D-22 si prefiere otra opción.

Planes aparte (fuera de esta pantalla):
- Parámetro nuevo "tiempo adicional de secado" (MP-11).
- Alarmas y fallas: reinicio de falla, reconocer alarma, puerta (MP-12).
- Datos de mantenimiento por ciclos (fuente de próximo mantenimiento).
- Identificación del operador al iniciar el ciclo y su registro en `ciclos` (D-24).

Del diseñador:

- SVG definitivos de usuario, ciclos totales y secado.
- Estados presionado y deshabilitado de las tarjetas.
- Aspecto de la celda central vacía en la barra inferior.
- Aspecto del aviso "Sin conexión con el equipo".
- Aspecto de las ventanas flotantes del resumen.
- Estado visual de Home cuando ya se está en el Menú Principal.
