# Planeación — Pantalla Nuevo Usuario (QML)

Versión: 1.1 (enmiendas de la compuerta G0, 2026-10-01)
Destino en el repositorio: `docs/mis_plans/planeacion_nuevo_usuario.md`
Rama de trabajo: `dev`
Ejecuta: Claude Code (terminal). Redacta y aprueba: Cristian.
Referencia visual: mockup-01, pantalla "Nuevo usuario". Contenido final: `src/autoclave/images/nuevo_usuario_sin_codigo.png`. Medidas y espaciados: `docs/diseno/referencias/pantallas_1080x1920/pantalla_04_nuevo_usuario_1080x1920.png`. Todo con anclas y `Escala.px()` sobre el lienzo de 1200 × 1920.
Clasificación del software: IEC 62304 Clase C. Todo cambio debe ser trazable y tener pruebas.


## 1. Objetivo

Construir la pantalla Nuevo Usuario del mockup-01 en QML, funcional de extremo a extremo: el administrador captura los datos, se validan, se guardan en la tabla `usuarios` de SQLite y el nuevo usuario puede iniciar sesión con el login existente.

Alcance incluido:

- Pantalla QML Nuevo Usuario (encabezado, tarjeta, formulario, barra inferior).
- Validaciones y mensajes de error.
- Capa de datos: columnas de auditoría, verificación de duplicados, inserción.
- Puente Python (QObject) entre QML y `DbManager`.
- Opción nueva en el menú de administración PySide (`admin_menu.py`) para abrir la pantalla.
- Cambio mínimo y aditivo en `src/autoclave/ui_pyside/main_window.py` para alojar la pantalla (G0): registro de la vista y una bandera genérica por vista para ocultar encabezado y pie de PySide (no un caso especial para esta pantalla).
- Propiedad opcional en `BarraSuperior.qml` para mostrar campana y engranaje, `false` por defecto, sin afectar pantallas existentes (P-07).
- Conexión con los teclados QML existentes.
- Pruebas automatizadas.


## 2. Fuera de alcance

- Lista, edición, desactivación o eliminación de usuarios.
- Foto de perfil: el avatar es estático. No se implementa el botón "+". Los avatares predefinidos en código se tratarán en un plan posterior.
- Campo "Nivel de acceso": se elimina; el nivel se infiere del rol.
- Definir cómo se genera y descifra el código de creación (D-12); hoy solo se valida su formato (NU-11).
- Matriz de permisos por rol (plan aparte).
- Migración del hash de contraseñas a un esquema con sal (ver hallazgo NU-01).
- Login QML: destino de la sesión. (Enmienda 2026-10-01: Cristian pidió habilitar en `Login.qml` una validación provisional contra la tabla `usuarios` —`LoginController`, mismo hash D-03, acceso directo D-04— que emite `sesionIniciada(usuario, rol)`; a qué pantalla lleva se define después. El login PySide sigue vigente.)
- Cualquier endpoint nuevo en FastAPI.
- Cualquier cambio en tkinter.
- Operadores: no se crean desde esta pantalla. La tabla `operadores` no existe todavía; su creación es una decisión futura.


## 3. Decisiones

### 3.1 Decisiones firmes (confirmadas por Cristian)

- D-01. "Nivel de acceso" no existe en la pantalla ni en la base de datos.
- D-02. Avatar estático, sin botón "+" por ahora.
- D-03. Hash de contraseña: reutilizar `hash_password` de `SessionManager` (SHA-256 hex) para mantener compatibilidad con el login actual.
- D-04. Ruta de escritura: el QML llama a un puente Python que usa `DbManager` directamente, igual que el login PySide. Prohibido crear un endpoint FastAPI para esto.
- D-05. Punto de entrada: nueva opción en el menú de administración (post-login) de PySide, visible solo para rol admin.
- D-06. Los teclados QML ya existen y su plan está terminado (`planeacion_teclados_qml.md`). Se reutilizan sin modificarlos, salvo lo indicado en NU-02.
- D-07. Validaciones: nombre, usuario y contraseña obligatorios; contraseña de mínimo 8 caracteres; confirmación igual a la contraseña; usuario único; Rol obligatorio.
- D-08. Auditoría: se registran `creado_por` y `creado_en`, siguiendo el patrón de auditoría de calibración.
- D-09. Cancelar y "<" piden confirmación solo si hay datos capturados.
- D-10. Barra inferior: solo salir (izquierda), inicio (derecha) y versión "V: 1.0". Sin iconos centrales; se conservan los dos divisores verticales.
- D-11. Estado: interruptor "Activo", por defecto encendido; se guarda en `activo`.
- D-12. (Post-G0) Campo "Código" obligatorio, como en `src/autoclave/images/nuevo_usuario.png` pero sin "(Opcional)". Nivel de acceso y botón "+" siguen fuera. Es un identificador (no secreto): se muestra sin enmascarar y se guarda en texto plano en la columna nueva `codigo_creacion`. Contiene información que el software sabrá descifrar; mientras eso no se defina, se valida solo el formato (4 a 20 caracteres, letras y números, sin espacios, teclado alfanumérico) en una única función del puente. Se suma a la sesión admin (NU-05), no la reemplaza. `creado_por` guarda el usuario de la sesión.

### 3.2 Decisiones provisionales (Cristian debe confirmar antes de la fase F1)

Estado en G0 (2026-10-01): P-01 a P-06 confirmadas (P-03 confirmada después de G0). Código de creación: reintroducido por Cristian (ver referencia `src/autoclave/images/nuevo_usuario.png`), obligatorio; definición pendiente. P-07 modificada. P-08 resuelta: opción (a).

- P-01. Salir = cerrar sesión (`SessionManager.logout()`) y navegar a `login`. Inicio = navegar a `home`.
- P-02. El desplegable Rol ocupa el ancho completo de la fila (al quitar Nivel de acceso). Estado queda debajo.
- P-03. Los roles se guardan sin acento y en minúscula: `admin`, `tecnico`, `biomedico`, `ingeniero`. Las etiquetas visibles llevan acento (Admin, Técnico, Biomédico, Ingeniero). Los nombres de rol siguen siendo provisionales: se definen en una única constante, en un solo módulo, para poder cambiarlos sin tocar la pantalla.
- P-04. Longitudes: Nombre Completo máximo 50; Nombre Usuario de 3 a 30 caracteres, sin espacios; Contraseña de 8 a 64.
- P-05. Se rechaza un usuario si ya existe otro igual sin distinguir mayúsculas (evita "Juan" y "juan" a la vez). El login sigue comparando exacto.
- P-06. Errores de validación en línea, debajo del campo, en rojo. Éxito: mensaje de confirmación y regreso al menú de administración. La confirmación de descartar datos aplica también a Salir e Inicio, porque ambos abandonan la pantalla.
- P-07. (Modificada en G0) Campana y engranaje se agregan como propiedad opcional de `BarraSuperior`, con valor `false` por defecto, sin afectar pantallas existentes. En esta pantalla se muestran pero son inertes. El reloj y la fecha se actualizan en vivo.
- P-08. (Resuelta en G0) Alojamiento: opción (a), `QQuickWidget` dentro de la pila de vistas PySide. Se autoriza un cambio mínimo y aditivo en `main_window.py`; ocultar encabezado y pie de PySide es una bandera genérica por vista.


## 4. Hallazgos

- NU-01 (Alta). El hash es SHA-256 sin sal (`hash_password`, `_hash_pw`, seed del admin). Es débil frente a ataque offline sobre `autoclave.db`. No se corrige aquí por compatibilidad con el login (D-03). Registrar como hallazgo abierto y crear plan de migración a PBKDF2 con sal y marca de versión de hash.
- NU-02 (Media). El encabezado del teclado alfanumérico muestra el valor tecleado. En los campos de contraseña debe mostrarse enmascarado (puntos), respetando el interruptor del ojo. Resolución (G0): el parámetro ya existe (`ocultar` de `PanelTeclado.abrirAlfanumerico` → `TecladoAlfanumerico.ocultarTexto`); se pasa el estado del ojo sin modificar los teclados. Si el ojo se apaga con el teclado abierto, se reabre el teclado con el valor actual y `ocultar: true`. Limitación restante: NU-10.
- NU-03 (Alta). El seed crea `admin` con contraseña conocida (`admin1234`) cuando la tabla está vacía. Fuera de alcance, pero queda documentado: un equipo en campo no debe conservar esa contraseña. Proponer en el plan de login el cambio obligatorio en el primer ingreso.
- NU-04 (Media). `get_usuario_by_username` filtra `activo=1`. La columna `usuario` es `UNIQUE` incluso para inactivos. Usar esa función para detectar duplicados dejaría pasar un usuario inactivo y la inserción fallaría con `IntegrityError`. Se requiere una función nueva que incluya inactivos y capturar `IntegrityError` como defensa final.
- NU-05 (Alta). Control de acceso: ocultar la opción en el menú no basta. El puente debe verificar `SessionManager.current_role() == "admin"` en cada operación de escritura, y la pantalla debe regresar al menú si se abre sin sesión admin.
- NU-06 (Informativa). H-03 sigue vigente: el backend FastAPI no tiene autenticación en endpoints y escucha en todas las interfaces. Esta pantalla no debe introducir nada nuevo en esa superficie (D-04).
- NU-07 (Media). `DbManager` ejecuta esquema y seed en cada instanciación. El puente conserva su propia instancia de `DbManager`, igual que `ciclos.py`, sin multiplicar conexiones innecesarias.
- NU-08 (Media). `AdminMenuView.showEvent` (`admin_menu.py`) llama a `SessionManager.is_logged_in()`, que no existe (el método es `is_authenticated()`), y usa `SessionManager.current_user["nombre"]` indexando el método de clase en vez de llamarlo (`current_user()`). El `try/except Exception: pass` oculta el error: la etiqueta siempre muestra "Administrador". Se corrige con el cambio mínimo en `admin_menu.py`, que ya se modifica en F4.
- NU-09 (Alta). El login PySide (`login.py`, `_do_login`) navega a `admin_menu` a cualquier usuario autenticado, sin verificar su rol. Queda abierto: se resuelve en el plan de login y permisos.
- NU-10 (Baja). `ocultar` solo se lee al abrir el teclado. Si el ojo se enciende (mostrar) con el teclado abierto, el encabezado del teclado sigue enmascarado hasta que se vuelva a abrir. Es el sentido seguro (nunca expone la contraseña); se acepta.
- NU-11 (Alta). El código de creación no se verifica contra nada: solo se valida su formato, así que todavía no prueba quién creó el usuario. Queda abierto hasta definir su generación y descifrado (D-12); la verificación se concentra en una sola función del puente.
- NU-12 (Baja). `PanelTeclado.cerrar()` no vacía el texto del controlador del teclado alfanumérico: la última contraseña tecleada queda en memoria (no visible) hasta la siguiente apertura del teclado. La pantalla limpia sus propios campos al salir, pero limpiar el controlador exige tocar los teclados (D-06). Queda abierto; proponer en el plan de teclados un vaciado al cerrar.


## 5. Especificación de la pantalla

Referencia: imagen del mockup, con las diferencias autorizadas de las secciones 2 y 3.

Encabezado (zona de degradado azul):
- Logo "especifika" a la izquierda, reloj grande centrado con fecha debajo (formato "12 oct - 2026"), campana con insignia numérica y engranaje a la derecha.
- Si ya existe un componente de encabezado en las pantallas QML actuales, reutilizarlo. Si no, crearlo como componente reutilizable.

Tarjeta blanca con esquinas redondeadas:
- Fila de título: flecha "<" y texto "NUEVO USUARIO".
- Columna izquierda: avatar circular gris con silueta de usuario, estático.
- Columna derecha, de arriba abajo:
  - Nombre Completo (marcador "Nombres y apellidos").
  - Nombre Usuario.
  - Contraseña (marcador "Ingresar contraseña", icono de ojo).
  - Confirmar Contraseña (icono de ojo).
- Fila a ancho completo: Rol (marcador "Seleccione rol", flecha de desplegable).
- Fila a ancho completo: Código (D-12), obligatorio.
- Estado: etiqueta "Estado", interruptor y texto "Activo".
- Botones: "Cancelar" (blanco, borde tenue) a la izquierda y "Guardar usuario" (azul, icono de guardar) a la derecha.

Barra inferior: salir, divisor, zona central vacía, divisor, inicio y "V: 1.0".

Comportamiento:
- Al tocar un campo de texto se abre el teclado alfanumérico existente, con el nombre del campo en su encabezado.
- El ojo alterna mostrar/ocultar de forma independiente en cada campo de contraseña. Por defecto ocultos.
- El desplegable Rol abre una lista táctil con las cuatro opciones; no usa teclado.
- Guardar se valida completo. Los errores se muestran por campo, todos a la vez, y se enfoca el primero con error. No se escribe nada en la base de datos si hay un error.
- Mensajes sugeridos: "Campo obligatorio", "Mínimo 8 caracteres", "Las contraseñas no coinciden", "El usuario ya existe", "Seleccione un rol", "Sin espacios, de 3 a 30 caracteres", "Letras y números, de 4 a 20 caracteres".
- Éxito: limpiar la pantalla, mostrar confirmación ("Usuario creado") y navegar a `admin_menu`.
- Cancelar, "<", Salir e Inicio: si hay datos capturados, diálogo de confirmación para descartar; si no, actúan de inmediato.
- Datos capturados = cualquier campo no vacío, Rol elegido o Estado distinto del valor por defecto.
- La contraseña nunca se registra en logs ni se deja en variables más tiempo del necesario; limpiar los campos al salir de la pantalla.

Tamaño: el mockup es 1190 × 1920 px. Usar anclas y proporciones, y la misma convención de escala que ya usan las pantallas QML existentes (verificar en F0). No fijar píxeles absolutos que rompan en otra resolución.


## 6. Capa de datos

Archivo: `src/autoclave/services/domain/logging/db_manager.py`.

- Agregar a la tabla `usuarios` las columnas `creado_por TEXT DEFAULT ''` y `creado_en TEXT DEFAULT ''`.
  - Incluirlas en `_SCHEMA` para bases nuevas.
  - Agregar migración aditiva en `_migrate`, un `ALTER TABLE` por columna, cada uno con su propio `try/except sqlite3.OperationalError`, igual que `motivo_fallo`. No tocar datos existentes.
- Extender `crear_usuario` con el parámetro opcional `creado_por: str = ""`. `creado_en` se calcula dentro con el mismo formato de fecha que ya usa el módulo para `fecha_inicio`. La firma actual debe seguir funcionando; las pruebas existentes no deben cambiar.
- Agregar a `usuarios` la columna `codigo_creacion TEXT DEFAULT ''` (D-12), con el mismo tratamiento de esquema y migración. `crear_usuario` recibe el parámetro opcional `codigo_creacion: str = ""`.
- Agregar `existe_usuario(usuario: str) -> bool`, que cuente también usuarios inactivos y compare sin distinguir mayúsculas (P-05), usando el Lock interno.
- `crear_usuario` debe dejar propagar `sqlite3.IntegrityError`; el puente la traduce a "El usuario ya existe".


## 7. Puente Python

Ubicación sugerida: junto a los demás componentes de UI PySide/QML, en el módulo que Claude Code determine en F0 siguiendo la estructura actual. No ubicarlo en el backend.

Clase `NuevoUsuarioBridge(QObject)`, registrada en el contexto QML:

- Propiedades de solo lectura: `roles` (lista de pares valor/etiqueta desde la constante de P-03), `minLongitudPassword`, `usuarioActual`.
- Método `puedeCrear()`: verdadero solo si hay sesión y el rol es admin (NU-05).
- Método `validar(nombre, usuario, password, confirmacion, rol, codigo)`: devuelve un diccionario campo → mensaje de error. Es la única fuente de reglas; el QML no duplica la lógica, solo muestra.
- Método `guardar(nombre, usuario, password, confirmacion, rol, codigo, activo)`: repite la verificación de rol admin y la validación, calcula el hash con `hash_password`, llama a `crear_usuario(..., creado_por=<usuario de la sesión>, codigo_creacion=<código>)` y devuelve `{ok: bool, errores: {...}}`. Captura `IntegrityError` y cualquier excepción de SQLite sin exponer detalles internos a la UI.
- Señales: `usuarioCreado`, `solicitudNavegar(destino)` si el alojamiento (F0) lo requiere.
- Log: registrar solo el evento ("usuario creado: <usuario>, rol <rol>, por <admin>"). Nunca la contraseña ni su hash.


## 8. Integración y punto de entrada

- En `src/autoclave/ui_pyside/views/admin_menu.py` agregar a `_OPTIONS` una opción "Usuarios" (o "Nuevo usuario"; usar "Nuevo usuario" mientras no exista la lista) y su ruta en `_OPTION_ROUTES`.
- La opción solo se muestra, o queda deshabilitada, si el rol actual es admin. El menú ya conoce `SessionManager`.
- Alojamiento (decidido en G0): (a) `QQuickWidget` dentro de la pila de vistas PySide, registrado en `main_window.py` como una vista más de `navigate_to`. El ocultamiento de encabezado y pie de PySide es una bandera genérica por vista. Se descartó (b), ventana o proceso QML independiente, porque un proceso aparte no comparte la sesión en memoria de `SessionManager` (NU-05).
- No retirar ni reescribir otras vistas PySide.


## 9. Fases y compuertas

Regla general: Claude Code no avanza de una fase a la siguiente sin cumplir los criterios de salida. No hace commit hasta que Cristian confirme visualmente el resultado (compuerta G3).

### F0. Reconocimiento (solo lectura, sin cambios)

Revisar y reportar, sin modificar nada:
- Cómo están alojadas hoy las pantallas QML (espera, ciclo, login): archivos, registro de contexto, escala, componentes reutilizables (encabezado, barra inferior, botones, campos).
- Cómo navega PySide (`nav_callback`, pila de vistas) y cómo se registran las vistas.
- Estado real de los teclados QML: archivos, API pública, cómo se enlazan a un campo, si ya existe una opción de enmascarado.
- Qué assets existen (SVG de ojo, guardar, flecha, avatar, salir, inicio, campana, engranaje, logo) y su ubicación.
- Qué cadenas de rol se usan hoy en el código (por ejemplo `_ROLES_PERMITIDOS` en calibración) para no romper permisos existentes.
- Si el estado del repositorio coincide con lo descrito en este plan; marcar cualquier discrepancia como nota de consistencia, sin corregirla en silencio.

Compuerta G0: Claude Code entrega el reporte y propone el alojamiento (a) o (b) con justificación. Cristian decide y confirma las decisiones P-01 a P-08. No se escribe código antes.

### F1. Capa de datos

Implementar la sección 6 con pruebas primero o junto al código.
Salida: pruebas nuevas y existentes de `usuarios` en verde; migración probada sobre una base antigua sin las columnas.

### F2. Puente Python

Implementar la sección 7. Si NU-02 exige tocar los teclados, reportar el cambio propuesto y esperar aprobación.
Salida: pruebas del puente en verde (validaciones, rol no admin, duplicado inactivo, duplicado por mayúsculas, éxito, `IntegrityError`).

### F3. Pantalla QML

Implementar la sección 5 con el alojamiento aprobado en G0.
- Reutilizar componentes existentes antes de crear nuevos.
- Assets: usar los existentes. Para los que falten, crear marcadores temporales en SVG Tiny 1.2 (atributos de presentación en línea, texto convertido a trazos, sin estilos CSS, filtros, texto vivo ni degradados complejos), con prefijo `placeholder_`, y dejar una lista de pendientes para el diseñador (Illustrator/CorelDRAW).
- Probar con `QT_QPA_PLATFORM=offscreen` cuando aplique.
Salida: la pantalla arranca en la PC de desarrollo y todos los comportamientos de la sección 5 se pueden ejercitar.

Compuerta G3: Cristian revisa la pantalla funcionando y compara con el mockup. Solo con su aprobación se hace commit.

### F4. Punto de entrada

Implementar la sección 8 en `admin_menu.py`.
Salida: iniciar sesión como admin, ver la opción, crear un usuario, cerrar sesión e iniciar sesión con el usuario nuevo (flujo completo).

### F5. Cierre

- Ejecutar la suite completa de pruebas y reportar resultados.
- Actualizar `docs/mis_plans/` con este plan. Los hallazgos NU-01 a NU-10 quedan en la sección 4 de este plan; no hay registro central.
- Reportar archivos modificados, archivos nuevos y notas de consistencia.
- Commit en `dev` solo después de G3, con mensaje descriptivo que cite este plan.


## 10. Pruebas mínimas

Datos:
- Migración añade ambas columnas sin perder filas existentes.
- `crear_usuario` conserva su firma anterior y guarda `creado_por` y `creado_en`.
- `existe_usuario` detecta activos, inactivos y variantes de mayúsculas.

Puente:
- `puedeCrear` falso sin sesión y con rol distinto de admin.
- `guardar` rechaza si el rol no es admin, aunque la UI haya sido manipulada.
- Cada regla de validación (obligatorios, longitudes, sin espacios, confirmación, rol) devuelve el mensaje esperado.
- El hash guardado coincide con `hash_password(<contraseña>)` y permite el login existente.
- La contraseña no aparece en logs.

Pantalla:
- Con datos capturados, Cancelar, "<", Salir e Inicio piden confirmación; sin datos, no.
- Ojo alterna visibilidad por campo.
- Éxito limpia la pantalla y navega a `admin_menu`.

Integración:
- Flujo completo de F4.


## 11. Criterios de aceptación

- La pantalla se ve conforme al mockup, con las diferencias autorizadas de las secciones 2 y 3.
- No existe "Nivel de acceso" ni botón "+" en el avatar. El campo Código existe y es obligatorio (D-12).
- Un admin crea un usuario y ese usuario inicia sesión con el login PySide actual.
- Un usuario no admin no puede abrir la pantalla ni crear usuarios.
- Ningún error de validación escribe en la base de datos.
- La contraseña nunca se muestra en el encabezado del teclado cuando el ojo está oculto, y nunca se registra.
- Todas las pruebas, nuevas y existentes, pasan.
- No se agregó ningún endpoint FastAPI ni se modificó tkinter.


## 12. Reglas de ejecución para Claude Code

- No asumir. Ante cualquier ambigüedad o discrepancia con el repositorio, detenerse y preguntar a Cristian con preguntas numeradas.
- Leer antes de modificar. Señalar efectos colaterales que Cristian no haya mencionado.
- No tocar nada fuera del alcance de la sección 1.
- No cambiar el esquema de hash ni el login (D-03).
- Cambios mínimos y aditivos en `db_manager.py`; no refactorizar.
- Los hallazgos se numeran (NU-xx) con severidad; no se corrigen en silencio.
- Decimal con punto en toda la interfaz, si aplica.
- No hacer commit antes de la confirmación visual de Cristian.
- Antes de F3, Cristian hace commit de su trabajo previo sin commit o lo aparta. Si no lo hizo: `git add` con rutas explícitas y `git add -p` para `es.json`; nunca `git add -A` ni `commit -a`.
- Git es solo respaldo y control de versiones; no se despliega con `git pull` en el PC del autoclave.
