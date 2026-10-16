# Planeación: pantallas QML de Opciones (marco y flujo de Parámetros del ciclo)

> **Adenda 2026-10-14 (tanda, T12):** Fases 2 a 4 implementadas de forma PROVISIONAL (sin diseño final) dentro de la zona de contenido de OPCIONES (`Pantallas/OpcionesParametrosCiclo.qml`, `controllers/parametros_ciclo_controller.py`), no como pantallas apiladas: vista de programa (selector, secciones con "No se ejecuta", fila de sensores), vista de sección (asterisco por defecto, descompresión solo con el modo activo) con ventana de ajuste (actual, por defecto, mínimo, máximo, teclado numérico; interruptor/opciones para booleanos y enumerados) y vista de sensores (roles de §1.1 de la tanda, sin advertencia de sonda fría). Backend: `GET /programas`, `GET /programas/{n}/seccion/{s}`; edición por `PATCH /cycle/parameter` con `valor_anterior_esperado`; roles por `PUT /cycle/sensor-roles`. Permisos y estados según §1.6 de la tanda (técnico fuera de CICLO, ingeniero siempre). Etiquetas de parámetros: provisionales (la clave legible) hasta tener el catálogo de etiquetas. La última modificación muestra el login, no el nombre (audit_log no guarda el nombre). Fase 5 NO.

Estado: BORRADOR, revisión 3.1 (sin acceso provisional a PySide; navegación en cajón lateral con botón hamburguesa; nombres de sección en una sola línea). Para revisión de Cristian. No hay código escrito ni se debe escribir hasta que este documento sea aprobado. La Fase 1 (marco) no depende de las otras especificaciones y puede iniciarse en cuanto se apruebe este documento.
Ubicación prevista: `docs\mis_plans\planeacion_opciones_parametros_ciclo.md`
Depende de: `planeacion_endurecimiento_backend_parametros.md` (rev. 4) y `planeacion_sensores_ciclo.md` (rev. 3), ambas pendientes de aprobación.
Referencias visuales: `opciones_cajon_comparativo.png`, `opciones_flujo_comparativo.png`, `opciones_ajuste_comparativo.png` y `opciones_sensor_comparativo.png`. La imagen `opciones_parametros_ciclo_referencia.png` quedó OBSOLETA (mostraba la navegación lateral permanente). Los datos que muestran son ILUSTRATIVOS.
Fuente de los hechos: los tres informes de Claude Code (2026-10-02, rama `dev`) y las respuestas de Cristian. Las referencias `archivo:línea` provienen de esos informes y deben verificarse al implementar.
Norma de referencia: IEC 62304 Clase C, ISO 14971.

---

## 1. Propósito y alcance

Esta especificación define la pantalla OPCIONES en QML, que se abre después de iniciar sesión, y el flujo de configuración de Parámetros del ciclo y de los sensores de temperatura. Es la tercera de tres especificaciones; las dos anteriores definen el backend sobre el que esta se apoya.

Dentro del alcance: marco de OPCIONES (encabezado, título con botón hamburguesa, cajón de navegación lateral, contenido, barra inferior), control de acceso por sección, paneles "Próximamente" para lo no migrado, las pantallas de Parámetros del ciclo (programa y fase, parámetros de la fase, ventana de ajuste, sensores), textos, pruebas y plan por fases.

Fuera de alcance (pendiente o aplazado): el contenido de Parámetros del sistema, Entradas/Salidas, Mantenimiento y Opciones avanzadas (quedan como "Próximamente" hasta migrarlos), el panel General del mockup (idioma, unidad, brillo, espera de pantalla, tema de color: fuera de V1.0), la creación y el borrado de programas, el cableado del Menú Principal, y la corrección de seguridad de puertas y alarmas (OPC-24 y OPC-25).

---

## 2. Decisiones adoptadas

- U-1. Opciones usa el FORMATO VISUAL del mockup pero el CONTENIDO de lo que existe en PySide. Las 8 secciones del mockup no cuentan. `pantalla_05_opciones_1080x1920.png` y el PDF del diseñador son referencia de formato (colores, tamaños, estilo de componentes), no de contenido. Donde difieran, prevalecen las imágenes de referencia de este documento.
- U-2 (revisada). La navegación es un CAJÓN LATERAL (drawer) que se abre con un botón hamburguesa; no hay navegación lateral permanente. El cajón lleva cinco entradas técnicas, tomadas de `AdminMenuView._OPTIONS`, en este orden y con estos nombres: Parámetros del ciclo, Parámetros del sistema, Entradas / Salidas, Mantenimiento, Opciones avanzadas. Cada nombre se muestra en UNA sola línea, como en las imágenes del cajón; si un texto no cupiera, la fila crece lo necesario y pasa a dos líneas sin cambiar el resto del diseño.
- U-3. Opciones y el login se implementan en QML puro. La escala sigue la convención `m()` y la base ya adoptada en las demás pantallas QML.
- U-4 (revisada). La interfaz QML ya no abre las vistas PySide de configuración. Cada entrada aún no migrada muestra un panel del mismo estilo con el texto "Próximamente". No hay traspaso de sesión entre procesos ni segundo login. Se acepta perder temporalmente funciones (calibración de sensores, diagnóstico de entradas y salidas, edición de parámetros, creación de usuarios) porque el software no está instalado en ningún equipo. Las vistas PySide siguen en el repositorio y pueden ejecutarse por separado en el PC de desarrollo, con su propio login, hasta retirarlas en la Fase 5.
- U-19. Comportamiento del cajón: modal, de aproximadamente la mitad del ancho de la pantalla, con el encabezado "OPCIONES" y las entradas filtradas por `puedeVer`; la entrada activa va resaltada (fondo azul claro y barra azul). Se abre con el botón hamburguesa y se cierra al tocar fuera, al elegir una entrada o al tocar de nuevo el botón. Elegir una entrada cierra el cajón y muestra su panel; con cambios sin guardar pide confirmación antes de cambiar de sección. El fondo se atenúa mientras está abierto. El contenido ocupa todo el ancho de la zona blanca.
- U-18 (propuesta, pregunta Q-6). El engranaje de la pantalla de ciclo en curso, que hoy abre la configuración PySide con `lanzador_ajustes`, pasa a abrir el login QML y, tras iniciar sesión, OPCIONES. `lanzador_ajustes` queda sin uso desde QML.
- U-5. Barra inferior con solo dos botones: salir a la izquierda e inicio a la derecha, con la celda central vacía (como `BarraInferiorMenu.qml`). Salir cierra la sesión, con confirmación si hay cambios sin guardar. Inicio sale de OPCIONES conservando la sesión y vuelve a la pantalla de ciclo previa; cuando se cablee el Menú Principal, Inicio irá ahí. En el nivel superior el título lleva el botón hamburguesa (abre el cajón) en lugar del chevron y muestra el nombre de la sección activa; en las pantallas de segundo nivel y en las ventanas, el chevron vuelve un nivel.
- U-6. Encabezado: logo, hora, campana y engranaje, por consistencia visual. La campana se comporta como en las demás pantallas QML; el engranaje no hace nada en OPCIONES.
- U-7. Control de acceso por una sola función, `puedeVer(seccion)`, parametrizable. Política inicial: las cinco secciones técnicas, para biomédico, técnico e ingeniero; admin no. Dos entradas adicionales, "Usuarios" (Nuevo usuario) y "Conectividad", visibles solo para admin. Nuevo usuario mantiene su restricción a administradores. La matriz fina por rol sigue pendiente en el plan de roles.
- U-8. Con un ciclo en curso OPCIONES se puede abrir, en solo lectura. La edición solo se permite con el estado global PREPARACION o PREPARADO (especificación 1, D-1). El backend impone el bloqueo; la interfaz solo lo refleja.
- U-9. Parámetros del ciclo se organiza en cuatro pantallas: (1) programa y fase, con la entrada a sensores; (2) parámetros de la fase; (3) ventana flotante de ajuste con valor actual, valor por defecto, mínimo, máximo, última modificación y campo de nuevo valor, con teclado solo al tocar el campo; (4) sensores con roles Principal, Referencia y No en uso.
- U-10. La tarjeta "Por defecto" de la ventana de ajuste es el botón para usar el valor por defecto; rellena el campo sin guardar. Se deshabilita si el valor actual ya es el valor por defecto o si este no se puede determinar.
- U-11. Los parámetros distintos del valor por defecto se marcan con asterisco solo en la pantalla de configuración, no en Inicio.
- U-12. Guardado por parámetro (y por conjunto de roles en sensores), vía backend, con auditoría escrita por el backend (especificación 1). No hay "Restablecer valores" por pantalla.
- U-13. Cambios sin guardar: en la pantalla de sensores se marcan "Sin guardar"; al salir con cambios pendientes se pide confirmación; Cancelar descarta.
- U-14. Controles de proceso y de edición con área táctil mínima de 64 px (el equipo puede operarse con guantes).
- U-15. El teclado numérico reutiliza el existente (`PanelTeclado` / `teclado_numerico.py`), embebido en la ventana; sin tecla de signo salvo que un parámetro tenga mínimo negativo.
- U-16. El fondo atenuado no cierra la ventana de ajuste: solo Cancelar o Guardar.
- U-17. Para los parámetros que no son numéricos libres, el control de la ventana de ajuste cambia: booleano con interruptor y enumerado (por ejemplo `descompresion.modo` de 0 a 5, `secado.modo`) con lista de opciones; el teclado solo se usa en numéricos.

---

## 3. Estado actual relevante (verificado en los informes)

- No existe pantalla Opciones en QML. El engranaje de la pantalla de ciclo en curso abre la configuración PySide.
- `LoginController` (`ui_qml/controllers/login_controller.py`, sin trackear) expone `nombreSesion` y `mensajeError` y emite `sesionIniciada(usuario, rol)`; no expone `usuario` ni `rol` como propiedades. `SessionManager` guarda `id`, `nombre`, `usuario` y `rol` por proceso y a nivel de clase.
- Roles definidos en `ui_pyside/services/roles.py` (sin trackear): `admin`, `tecnico`, `biomedico`, `ingeniero`; `operador` es el valor por defecto de la tabla `usuarios` y no figura en esa lista.
- Hoy un proceso QML por ventana (`--door`, `--screen`), todos hablan con `http://127.0.0.1:8000`; `UiBridge` entrega el estado por polling.
- `BackendClient` tiene `timeout=0.8` s para todas las operaciones. La especificación 1 (D-15) lo sube a 5 s para escrituras.
- Existe un simulador (`simulador/__main__.py`, `127.0.0.1:8001`) y un arnés de pruebas usado para el Menú Principal.
- Vistas PySide de configuración vigentes: `params_ciclo.py`, `secado.py`, `calibracion_sensor.py`, `io_*.py`, `impresion_menu.py`, `admin_menu.py`. Cuáles de las cinco entradas de `AdminMenuView` están implementadas y cuáles son provisionales debe listarlo Claude Code (NO DETERMINADO en este documento).
- Nuevo usuario existe como vista PySide alojada en `QQuickWidget`; su traslado a QML es aparte.
- Si existe una vista de Conectividad en PySide es NO DETERMINADO.
- El backend aún no soporta lo que esta especificación consume: catálogo de parámetros, valor por defecto, última modificación, roles de sensor, estado `edicion_permitida` y códigos de error normalizados. Todo eso proviene de las especificaciones 1 y 2.

---

## 4. Arquitectura de la interfaz

### 4.1 Navegación

Pila de navegación (`StackView`) dentro del proceso QML. Niveles: OPCIONES (marco con cajón de navegación lateral) → pantalla 2 (parámetros de la fase, pantalla completa estilo Nuevo Usuario) → ventana flotante de ajuste. La pantalla de sensores es de pantalla completa, al mismo nivel que la pantalla 2.

### 4.2 Controladores (proponer nombres; los puentes Python/QML los diseña Claude Code)

- `OpcionesController`: sección activa, entradas visibles (`puedeVer`), identidad de sesión, cierre de sesión, `edicionPermitida` derivada del estado global que ya llega por polling.
- `ParametrosCicloController`: programas, fases, parámetros de una fase, lectura y escritura por parámetro, manejo de códigos de error.
- `SensoresCicloController`: sensores del programa, roles, validación local y guardado del conjunto.
- Los controladores no calculan reglas de seguridad: la validación final es siempre del backend. La interfaz solo anticipa para dar mejor respuesta.

### 4.3 `puedeVer(seccion)`

Un único módulo de permisos con la lista de roles compartida con el backend (especificación 1, RB-02.2). Devuelve verdadero o falso por (sección, rol). La política inicial de U-7 vive solo ahí. Las pantallas nunca comparan roles directamente. El caso de qué ve el admin y qué ve el ingeniero en Conectividad y Usuarios es la pregunta Q-1.

### 4.4 Identidad en las escrituras

Los controladores leen `usuario`, `nombre` y `rol` de `SessionManager` y los incluyen en cada petición de escritura (especificación 1, RB-02). Si faltan, la interfaz no envía la petición y pide iniciar sesión de nuevo. `LoginController` o un controlador de sesión nuevo debe exponer esos datos a QML (hoy solo `nombreSesion`).

### 4.5 Estado de la máquina y solo lectura

`edicionPermitida` = estado global en {PREPARACION, PREPARADO}. Se usa solo para mostrar o deshabilitar controles y mostrar el mensaje; el backend impone el bloqueo (especificación 1, RB-01). Si el estado cambia con la ventana de ajuste abierta, el intento de guardar recibirá `EDICION_BLOQUEADA_ESTADO` y se maneja como en 5.4.

---

## 5. Pantallas

### 5.0 Marco de OPCIONES

Encabezado del mockup (logo, hora y fecha, campana con indicador, engranaje). Fila de título con botón hamburguesa a la izquierda y el nombre de la sección activa (por ejemplo "PARÁMETROS DEL CICLO"). Contenido a todo el ancho de la zona blanca con esquinas redondeadas, y barra inferior con salir e inicio. Imágenes 1a (cajón cerrado), 1b (cajón abierto, técnico) y 1c (cajón abierto, admin).

Cajón (U-19): encabezado "OPCIONES" con línea divisoria y una fila por entrada, con icono y nombre en una sola línea. Estilo de la entrada seleccionada: fondo azul claro con barra azul a la izquierda, texto azul en negrita. Icono por entrada: reloj para Parámetros del ciclo, engranaje para Parámetros del sistema, flechas de entrada y salida para Entradas / Salidas, llave para Mantenimiento, controles deslizantes para Opciones avanzadas (los de Entradas/Salidas y Opciones avanzadas dibujados en las referencias; los iconos definitivos los entrega el diseñador).

Entradas solo para admin (U-7): "Usuarios" y "Conectividad"; el admin ve solo estas dos en el cajón y los roles técnicos ven solo las cinco técnicas. Iconos tomados del mockup (usuarios y red). Ambas muestran "Próximamente" hasta migrarlas (Nuevo usuario y Conectividad). El admin aterriza en la primera entrada que le corresponde (Usuarios).

Panel por entrada no migrada: título de la sección y el texto "Próximamente". Sin tarjeta de acceso a PySide.

Estados: sin sesión (OPCIONES no se abre), con ciclo en curso (solo lectura), rol sin ninguna sección visible (mensaje "Su perfil no tiene secciones disponibles").

### 5.1 Pantalla 1: programa y fase

- Título "PARÁMETROS DEL CICLO" con el botón hamburguesa (nivel superior). El contenido ocupa todo el ancho de la zona blanca (imagen 1a).
- Selector de programa (lista desplegable): número y nombre del programa, por ejemplo "03 · Botellones vacíos". Los programas vienen del backend; no se lee disco.
- Lista de fases como filas con chevron: Precalentamiento, Vacío, Calentamiento, Esterilización, Descompresión y Secado, más dos filas adicionales para las secciones Generales y Finalización (P13). No se muestran secciones sin lector en el código (OPC-15). Las fases se muestran todas siempre; la que no se ejecuta por tener su parámetro de activación en 0 (precalentamiento, secado, tipos de pulso de vacío) lleva la etiqueta pequeña "No se ejecuta" para que se pueda activar editándola (pregunta Q-2).
- Debajo, tras una línea divisoria, "Sensores de temperatura" con una fila resumen del programa seleccionado (por ejemplo "Principal: Cámara 1 · 1 referencia") que abre la pantalla de sensores.
- Cambiar de programa actualiza la lista de fases y la fila de sensores. En solo lectura las filas siguen siendo tocables (se consultan, no se editan).

### 5.2 Pantalla 2: parámetros de la fase

- Pantalla completa, estilo Nuevo Usuario: chevron, nombre de la fase como título y, debajo, la ruta en gris ("Parámetros del ciclo · 03 Botellones vacíos").
- Una fila por parámetro: etiqueta, valor actual en negrita, unidad en gris y chevron. Asterisco azul junto a la etiqueta si el valor difiere del valor por defecto (U-11). Pie con la leyenda "* Valor distinto del valor por defecto" y la nota de auditoría.
- Etiquetas, unidades, decimales y paso salen del catálogo de parámetros en código (especificación 1, RB-05.1), no de los JSON, que no traen etiqueta, paso ni valor por defecto.
- Parámetros huérfanos (sin lector en el código) no se muestran. Fases con muchos parámetros se agrupan con subtítulos y desplazamiento; la agrupación la propone Claude Code a partir del catálogo y la aprueba Cristian. Para Descompresión se muestra primero el selector de modo y a continuación solo los parámetros del modo activo (pregunta Q-3).
- En solo lectura: filas visibles, sin chevron de edición, con un aviso fijo "Edición bloqueada: ciclo en curso".

### 5.3 Pantalla 3: ventana flotante de ajuste

Contenido, de arriba abajo: título (nombre del parámetro), subtítulo "Fase · Programa", cuatro tarjetas (valor actual resaltado, por defecto, mínimo y máximo), línea "Última modificación: usuario · fecha y hora", etiqueta "Nuevo valor" con el campo (con unidad), línea "Rango permitido: mín – máx unidad", y los botones Cancelar y Guardar.

Estados (imágenes 3a, 3b y 3c):
- Al abrir: campo vacío con el texto "Toque para ingresar el nuevo valor"; Guardar deshabilitado.
- Al tocar el campo: foco azul y aparece el teclado numérico dentro de la misma ventana, que crece.
- Tras tocar la tarjeta Por defecto: el campo se rellena con el valor por defecto sin abrir el teclado; Guardar habilitado.

Reglas:
- El campo valida contra el rango efectivo (intersección del catálogo y el JSON del programa, especificación 1, RB-05.2), el tipo y los decimales. Fuera de rango o con formato inválido: campo en rojo, mensaje con el rango y Guardar deshabilitado.
- La tarjeta Por defecto está deshabilitada (gris, sin borde azul) cuando el valor actual ya es el valor por defecto o cuando este no está disponible (se muestra "—").
- "Última modificación" sale de la consulta de auditoría (especificación 1, RB-03.8); sin registros se muestra "Sin cambios registrados". Se identifica al usuario por su nombre y no por el login.
- Guardar envía la petición con `valor_anterior_esperado` (especificación 1, RB-06) y la identidad de sesión. Con una respuesta correcta, cierra la ventana, actualiza la fila de la pantalla 2 y la marca del asterisco.
- Parámetros booleanos y enumerados usan interruptor o lista de opciones, no teclado (U-17).
- En solo lectura la ventana puede abrirse para consultar, con el campo y Guardar deshabilitados.
- Tamaño táctil mínimo de 64 px en teclas y botones (U-14).

### 5.4 Manejo de errores al guardar

Códigos de la especificación 1 (RB-07) y mensajes propuestos:

- `EDICION_BLOQUEADA_ESTADO` (409): "Edición bloqueada: el equipo no está en preparación. Finalice o cancele el ciclo para modificar parámetros." Cierra la ventana y pasa la pantalla a solo lectura.
- `VALOR_CAMBIO` (409): "El valor cambió en el equipo (ahora {valor}). Revíselo e intente de nuevo." Recarga y muestra el valor actual.
- `ROL_NO_PERMITIDO` (403): "Su usuario no tiene permiso para modificar este parámetro."
- `IDENTIDAD_FALTANTE` (422): "No se pudo identificar la sesión. Cierre sesión e ingrese de nuevo."
- `VALOR_INVALIDO` (422): "Valor fuera de rango o con formato inválido ({mín} a {máx} {unidad})."
- `PROGRAMA_NO_ENCONTRADO` (404) y `PROGRAMA_NO_EDITABLE` (409): "El programa no está disponible para edición."
- `BASE_OCUPADA` (503): "El registro está ocupado. Intente de nuevo en unos segundos."
- `PERSISTENCIA_FALLIDA` (500): "No se pudo guardar el cambio. El valor no se modificó."
- Tiempo de espera agotado o error de red: el resultado es INCIERTO. Mostrar "Sin respuesta del equipo. Verificando el valor actual…", recargar el valor desde el backend y solo entonces informar el resultado real (especificación 1, D-15). Nunca decir "no se guardó" sin verificar.
- Códigos de sensores (especificación 2): `ASIGNACION_INVALIDA` ("La asignación no cumple las reglas: {regla}."), `SENSOR_NO_DISPONIBLE` ("El sensor {nombre} no está disponible."), `ASIGNACION_SENSORES_INVALIDA` (aviso al iniciar ciclo, fuera de esta pantalla).

Los textos viven en `ui_qml/assets/textos/es.json`, bajo un espacio de nombres propio para Opciones (propuesta: `opciones.*`).

### 5.5 Pantalla 4: sensores de temperatura

- Pantalla completa. Título "SENSORES DE TEMPERATURA", ruta "Parámetros del ciclo · Programa", instrucción "Asigne el rol de cada sensor para este ciclo".
- Una tarjeta por sensor, con nombre, tipo (por ejemplo "Sensor de cámara"), lectura actual y un control segmentado de tres opciones: Principal, Referencia y No en uso (colores: azul, verde azulado y gris). La lista sale del backend (especificación 2, RS-01), no de una lista fija.
- Reglas de interfaz (especificación 2, sección 6): el sensor Principal tiene deshabilitadas las otras dos opciones; para cambiarlo se asigna Principal a otro sensor y el anterior pasa a No en uso; la opción Referencia se deshabilita en los demás sensores cuando ya hay dos; un sensor sin señal solo admite No en uso.
- Contadores: Principal n / 1, Referencia n / 2, No en uso. Nota "Un nuevo Principal reemplaza al anterior, que pasa a No en uso". Última modificación.
- Las tarjetas modificadas se marcan "Sin guardar". Guardar se habilita solo con un conjunto válido y distinto del guardado; envía el conjunto completo (todo o nada) con `asignacion_anterior_esperada`.
- Si el programa tiene F0 activo y la asignación deja como No en uso una sonda de cámara que la familia declara, antes de guardar se muestra una advertencia sin bloqueo (especificación 2, RS-04.3).
- Un sensor con rol activo asignado pero no instalado se lista marcado como no disponible y obliga a reasignar.
- En solo lectura los controles se muestran deshabilitados con el aviso de edición bloqueada.
- Los nombres visibles son provisionales (Cámara 1, Cámara 2, Referencia) hasta resolver C-4 de la especificación 2.

---

## 6. Datos que consume la interfaz (a definir en el backend)

Las rutas y los campos son propuestas de esta especificación; Claude Code verifica contra las rutas existentes (`GET /cycle`, `GET /cycles`) y propone nombres definitivos en su plan.

- Lista de programas: número, nombre, origen (fábrica o usuario) y estado (disponible o dañado).
- Parámetros de una fase de un programa: ruta del parámetro, etiqueta, tipo, unidad, decimales, paso, valor actual, valor por defecto, mínimo, máximo efectivos, `modificado` (booleano) y última modificación (login, nombre, rol, fecha y hora).
- Sensores del programa: identificador, nombre, tipo, estado (`disponible`, `sin_senal`, `no_instalado`), lectura y rol (especificación 2, RS-01).
- Estado del equipo: el polling existente debe incluir el estado global (para `edicionPermitida`).

### 6.1 Valor por defecto (cierra OPC-10, OPC-14 en la parte de lectura)

- Para los programas de fábrica (1 a 10) el backend conserva en memoria un perfil de fábrica inmutable, indexado por NÚMERO de programa y no por nombre de archivo. El valor por defecto es el del perfil de fábrica.
- Para los programas de usuario (11 en adelante) no hay perfil de fábrica propio. Hoy no existe ninguno; la creación de programas es un plan aparte, que deberá congelar en el JSON una copia del programa base al crearlo. Hasta entonces, el valor por defecto se muestra como "—" y la tarjeta Por defecto queda deshabilitada (pregunta Q-4).
- `modificado` se calcula comparando el valor actual con el valor por defecto; sin valor por defecto no se marca asterisco.

---

## 7. Plan por fases y puertas de entrada

- Fase 1: marco. Puerta de entrada: aprobación de este documento. Contenido: login → OPCIONES, encabezado, título con botón hamburguesa, cajón de navegación lateral con las cinco entradas (y Usuarios y Conectividad para admin) filtradas por `puedeVer`, panel por sección con "Próximamente", barra inferior con salir e inicio, confirmación al salir con cambios pendientes (todavía sin edición), solo lectura con ciclo en curso. Exposición de `usuario`, `nombre` y `rol` de la sesión a QML. Sin edición de parámetros en QML.
- Fase 2: lectura de Parámetros del ciclo y de sensores. Puerta de entrada: catálogo de parámetros (especificación 1, RB-05.1 con etiqueta, unidad, decimales y paso), perfil de fábrica en memoria (6.1), consulta de última modificación (RB-03.8) y ruta de sensores (especificación 2, RS-01). Contenido: pantallas 1, 2, 3 y 4 en solo lectura.
- Fase 3: edición de parámetros. Puerta de entrada: especificación 1 implementada y verificada, al menos RB-01 (bloqueo por estado), RB-02, RB-03, RB-05, RB-06, RB-07 y RB-09. No debe liberarse antes: una interfaz de edición ampliaría un defecto conocido (OPC-01).
- Fase 4: roles de sensor. Puerta de entrada: especificación 2 implementada, al menos RS-01, RS-02, RS-03, RS-05 y RS-06, y resueltos C-4 (nombres y posiciones) y C-6 (familias).
- Fase 5: retiro de las vistas PySide equivalentes (`params_ciclo.py`, `secado.py`) y de sus rutas, tras verificar las fases 3 y 4.

Cada fase termina con aprobación explícita de Cristian tras revisión visual, como en el plan del Menú Principal.

---

## 8. Pruebas

- Arnés de pruebas QML y simulador: se extiende el simulador con las rutas nuevas y con inyección de fallos (cada código de error de 5.4, tiempo de espera agotado, sensor sin señal, programa dañado, estado distinto de PREPARACION y PREPARADO) para probar la interfaz sin backend real.
- `puedeVer`: una prueba por rol (admin, técnico, biomédico, ingeniero, operador) y por entrada.
- Marco y cajón: abrir y cerrar con el botón y tocando fuera, entradas según el rol (técnico, admin), la entrada activa resaltada, cambiar de sección con cambios pendientes pide confirmación, el fondo atenuado no deja tocar el contenido, navegación a cada entrada, salir con y sin cambios pendientes, inicio conserva la sesión, ciclo en curso en solo lectura.
- Ventana de ajuste: los tres estados, validación de rango y decimales, tarjeta Por defecto habilitada y deshabilitada, boolean y enumerados, teclado solo al tocar el campo, el fondo no cierra la ventana.
- Errores: cada código produce su mensaje; el tiempo de espera agotado recarga el valor antes de informar.
- Sensores: las cinco reglas de asignación (un solo Principal, hasta dos Referencias, reemplazo automático, deshabilitar Referencia con dos, sin señal solo No en uso), marca "Sin guardar", advertencia de F0.
- Tamaños: área táctil de 64 px en teclas y botones; escala con `m()` y base 1200×1920 ajustable a 9:16.
- Regresión: las demás pantallas QML siguen funcionando y no queda ningún acceso desde QML a las vistas PySide.

---

## 9. Riesgos

- R-1 (media). Una interfaz de edición liberada antes que la especificación 1 amplía OPC-01 (cambio en caliente); por eso la Fase 3 queda condicionada.
- R-2 (media). Mientras el backend no autentique, el control de acceso por rol es defensa en profundidad (especificación 1, D-8): el backend verifica el rol declarado por el cliente.
- R-3 (baja). Dos instancias de UI en el mismo equipo pueden editar el mismo parámetro; el control de concurrencia de la especificación 1 (RB-06) devuelve `VALOR_CAMBIO` y la interfaz recarga.
- R-5 (media). Sin acceso a PySide, mientras las secciones no se migren no hay interfaz en QML para crear usuarios, calibrar sensores, diagnosticar entradas y salidas ni editar parámetros. En el PC de desarrollo se usan las vistas PySide por separado o se opera la base de datos directamente; para probar `puedeVer` hacen falta usuarios con cada rol, y se crean con la vista PySide de Nuevo usuario ejecutada por separado.
- R-4 (baja). Los nombres de sensor (Cámara 1, Cámara 2, Referencia) son provisionales.

---

## 10. Preguntas abiertas (responder por número; sin respuesta se adopta la recomendación)

- Q-1. Qué ve cada rol en las entradas de admin. Recomendación: Usuarios solo admin; Conectividad solo admin; el ingeniero no las ve hasta que la matriz de permisos diga lo contrario.
- Q-2. Fases con su parámetro de activación en 0 (precalentamiento, secado, pulsos de vacío): mostrarlas siempre con la etiqueta "No se ejecuta". Recomendación: sí, para poder activarlas.
- Q-3. Descompresión: mostrar solo los parámetros del modo activo. Recomendación: sí.
- Q-4. Programas de usuario sin perfil de fábrica: valor por defecto "—" y botón deshabilitado hasta definir la creación de programas. Recomendación: sí.
- Q-5. Mínimos de seguridad del Anexo B: revisar y aprobar parámetro por parámetro.
- Q-7. Cajón: abrirlo también con un deslizamiento desde el borde izquierdo. Recomendación: no; con guantes un deslizamiento puede dispararse sin querer, y basta el botón hamburguesa más tocar fuera para cerrar.
- Q-8. Título del nivel superior: el nombre de la sección activa y no "OPCIONES" (que queda como encabezado del cajón). Recomendación: sí.
- Q-6. Engranaje de la pantalla de ciclo en curso (U-18): que abra el login QML y luego OPCIONES, en lugar de la configuración PySide. Recomendación: sí.

---

## Anexo B. Límites del catálogo: propuesta de mínimos (pendiente de aprobación)

Criterio: esta propuesta solo EXCLUYE EL 0 (especificación 1, D-5) con el menor valor físicamente plausible, y toma como cota inferior y superior de presión los límites del modelo de equipo (1 a 400 kPa absolutos, `config/models/solids.yaml`). No toca los máximos ni los mínimos que el JSON ya fija por encima de 0. Los valores marcados con (P) requieren una decisión de proceso de Cristian porque el mínimo plausible depende del proceso y no del código.

### B.1 Parámetros con `or <constante>` cuyo mínimo JSON hoy es 0 (A.1 de la especificación 1)

- `precalentamiento.timeout_precalentamiento`: mínimo propuesto 1 min.
- `prevacio.timeout_bajo` y `prevacio.timeout_alto`: 1 min.
- `prevacio.presion_baja_pulso_a/b/c/d` y `presion_alta_pulso_a/b/c/d`: de 1 a 400 kPa.
- `calentamiento.rango_temp_estabilizacion`: 0.1 °C (P).
- `esterilizacion.tiempo_esterilizacion`: 1 min (P). Los programas actuales empiezan en 3.5 min.
- `secado.presion_chaqueta_secado`, `secado.rango_chaqueta_secado`, `secado.presion_baja_secado` y `secado.presion_alta_secado`: de 1 a 400 kPa.
- `globals.presion_chaqueta` y `globals.rango_presion_chaqueta`: de 1 a 400 kPa. Esto elimina la doble semántica del 0 entre CICLO y PREPARACION o PREPARADO (OPC-28).

### B.2 Parámetros con `default=` donde el 0 bloquea o desactiva una protección (A.2 de la especificación 1)

- `descompresion.modo_3.presion_cambio`: de 1 a 400 kPa.
- `descompresion.modo_{4,5}.presion_camara_enfriamiento`: de 1 a 400 kPa.
- `descompresion.modo_{4,5}.temperatura_enfriamiento`: 1 °C como mínimo técnico (P): con un valor por debajo de la temperatura ambiente el enfriamiento no termina; Cristian decide si el mínimo debe ser mayor.
- `finalizacion.temp_max_apertura`: 1 °C como mínimo técnico (P): con un valor demasiado bajo la puerta no se abre sola; Cristian decide el mínimo útil.
- `descompresion.modo`: EXCLUIDO, el 0 es válido (descompresión por gravedad).

### B.3 Parámetros con mínimo JSON ya mayor que 0 (sin cambio)

`calentamiento.temperatura_calentamiento` (100 a 140 °C), `esterilizacion.temperatura_esterilizacion` (100 a 140 °C), `calentamiento.timeout_calentamiento` (1 a 999 min), `calentamiento.timeout_recuperacion_estabilizacion` (1 a 60 min), `secado.modo` (1 a 3), `secado.timeout_pulso` (1 a 600 s), `descompresion.modo_N.timeout` (1 a 3600 min), `descompresion.modo_{4,5}.tiempo_apertura_chaqueta` (1 a 3600 s).

### B.4 Máximos y validaciones cruzadas (revisión aparte)

Los máximos actuales son muy amplios (por ejemplo `tiempo_esterilizacion` hasta 9999 min; presiones hasta 1000 kPa con un equipo de 400 kPa; temperaturas hasta 150 °C con límites de modelo de 0 a 200 °C). Claude Code debe entregar el listado de parámetros cuyo máximo excede el límite del modelo para que Cristian los revise. Las validaciones cruzadas (por ejemplo, presión baja menor que presión alta en un pulso de vacío) no existen hoy en el código; si se quieren, requieren una especificación propia.
