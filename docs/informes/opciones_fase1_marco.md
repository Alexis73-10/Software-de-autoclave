# Informe: OPCIONES QML, Fase 1 (marco)

Fecha: 2026-10-07. Rama `dev`. Aprobada por Cristian el 2026-10-07 (ver §8).
Plan: `docs/mis_plans/planeacion_opciones_parametros_ciclo.md`, rev. 3 (cajón lateral con botón hamburguesa). La primera versión de esta fase se hizo sobre la rev. 2, con navegación lateral fija; esta entrega la reemplaza.
Referencia visual: `src/autoclave/images/opciones_cajon_comparativo.png` (1a, 1b, 1c).

## 1. Paso 0: verificación contra el código

- `LoginController` valida contra SQLite y emite `sesionIniciada`, pero no expone `usuario` ni `rol` a QML. Se exponen con `OpcionesController` (§4.4).
- `SessionManager` mantiene la sesión por proceso, es decir, por ventana, y no notifica cambios. Se resuelve con `refrescar()`.
- `BarraInferiorMenu.qml`, la convención `m()` sobre el marco de 1196 × 1917, el arnés de pruebas (subproceso offscreen) y `UiBridge.machineState` sirven tal como están.
- La rev. 3 reescribió las correcciones de hechos que se habían hecho a la rev. 2. U-18 sigue diciendo que el engranaje de ciclo en curso abre PySide, pero desde el 2026-10-02 abría el Menú Principal. No cambia lo que hay que hacer.
- No existen iconos de hamburguesa, de flechas de entrada y salida ni de controles deslizantes.

No hubo bloqueos.

## 2. Qué se hizo

- **Acceso.** El login QML, al validar, se reemplaza por OPCIONES. El engranaje de la pantalla de ciclo en curso abre el login, o va directo a OPCIONES si ya hay sesión (`Main.qml`, `abrirConfiguracion()`). El engranaje de preciclo sigue abriendo el Menú Principal (Q-6 ajustada por Cristian). El avatar y "Iniciar sesión" del menú también abren el login.
- **Marco (`qml/Pantallas/Opciones.qml`).** Tiene:
  - encabezado con campana (abre las notificaciones) y engranaje sin acción (U-6);
  - fila de título con la hamburguesa (tres trazos dibujados) y el nombre de la sección activa (Q-8);
  - contenido a todo el ancho con "Próximamente";
  - barra inferior con Salir e Inicio.
- **Cajón (U-19).**
  - Es modal, de unos 627 px de los 1196 del marco, con el encabezado "OPCIONES", una línea divisoria y una fila por entrada (icono y nombre en una línea).
  - La entrada activa va resaltada con fondo azul claro y barra azul.
  - Se abre con la hamburguesa. Se cierra al tocar fuera, al elegir una entrada o con `alternarCajon()`.
  - El fondo se atenúa y no deja tocar el contenido.
  - No se abre con gesto de deslizamiento (Q-7).
  - Con cambios sin guardar, cambiar de sección pide confirmación.
- **Permisos** (`ui_qml/domain/permisos_opciones.py`, única fuente):
  - técnico, biomédico e ingeniero ven las cinco secciones técnicas;
  - admin ve solo Usuarios y Conectividad, y aterriza en Usuarios;
  - cualquier otro rol ve "Su perfil no tiene secciones disponibles", con "OPCIONES" como título.
- **Sesión** (`OpcionesController`): expone `usuario`, `nombre`, `rol`, `secciones`, `cerrarSesion()` y `edicionPermitida` (solo PREPARACION y PREPARADO).
- **Solo lectura:** fuera de PREPARACION y PREPARADO aparece el aviso "Edición bloqueada: ciclo en curso". Excepción (§8): el ingeniero puede editar cualquier sección en cualquier estado.
- **Salida.** Salir cierra la sesión, con confirmación si hay cambios sin guardar. Inicio conserva la sesión. Los dos vuelven a preciclo o a ciclo en curso según el estado de la máquina, aunque se haya llegado por el Menú Principal.
- **`lanzador_ajustes`:** no se tocó. Ya no se usa desde QML.
- **Textos** en `es.json`, bajo `opciones.*`. Los nombres de sección quedan en una sola línea.

## 3. Dudas de diseño (para Cristian; no se decidieron)

1. **Volver a tocar la hamburguesa (U-19).** En las referencias 1b y 1c el cajón tapa la hamburguesa, así que con el cajón abierto no se puede tocar de nuevo. Hoy se cierra tocando fuera o eligiendo una entrada. ¿Se mueve la hamburguesa por encima del cajón, se pone un botón de cerrar en el cajón, o se deja así?
2. **Nombres en una o dos líneas.** U-2 dice que los nombres largos van en dos líneas; §5.0 y las referencias del cajón los muestran en una. Se siguió §5.0. ¿Se corrige U-2?
3. **Iconos sin asset.** Entradas / Salidas usa `sensor_temperatura.svg` y Opciones avanzadas `programas.svg`, porque no existen los de flechas ni de controles deslizantes. La hamburguesa está dibujada con tres trazos. ¿Se los pedimos al diseñador?
4. **Tamaño de "Próximamente"** (42 px del marco, gris guía, centrado): se tomó a ojo de la referencia 1c. ¿Está bien?
5. **El standby cierra la sesión** (`Main.qml`, `cerrarSesionPorStandby`). Viene de la entrega anterior y sigue sin confirmar.
6. **Cambio de estado con OPCIONES abierta.** Si la máquina entra o sale de CICLO, OPCIONES se cierra y vuelve a la pantalla principal, igual que el Menú Principal. ¿Debe quedarse abierta y solo cambiar a solo lectura?
7. **El estado de la rev. 3 dice "BORRADOR".** Se ejecutó por su orden directa. ¿Lo marco como aprobado?

## 4. Pruebas (arnés)

- `tests/test_permisos_opciones.py`: orden de las secciones; `puede_ver` por cada rol (admin, técnico, biomédico, ingeniero, operador, vacío) y por cada entrada; `edicion_permitida` por estado.
- `tests/test_opciones_controller.py`: identidad de la sesión, secciones por rol, `refrescar`, `cerrarSesion`, `edicionPermitida`.
- `tests/test_opciones_qml.py`: navegación real de `Main.qml` (offscreen, base de usuarios temporal, toques reales en la ventana). Cubre técnico en CICLO y en PREPARADO, admin y operador:
  - el acceso abre el login, y el login validado abre OPCIONES;
  - el cajón está cerrado al entrar; la hamburguesa lo abre; tocar fuera lo cierra; `alternarCajon()` abre y cierra;
  - con el cajón abierto, el fondo no deja tocar la casa;
  - elegir una entrada cierra el cajón y cambia el título;
  - con cambios sin guardar, cambiar de sección pide confirmación y, al confirmar, cambia;
  - las entradas corresponden al rol y el admin aterriza en Usuarios;
  - el aviso de bloqueo aparece solo en CICLO;
  - Inicio conserva la sesión (el siguiente acceso va directo a OPCIONES); Salir la cierra (el siguiente acceso vuelve a pedir login);
  - entrando por el Menú Principal, Inicio vuelve a preciclo;
  - nada lanza PySide y no hay avisos QML.
- `tests/test_main_menu_principal_qml.py`: queda solo el caso de preciclo.
- **Suite completa: 1878 pruebas pasan, 6 advertencias ya existentes (2026-10-07, tras los ajustes de §8).**

## 5. Capturas

`docs/informes/opciones_fase1_capturas/`: `1a_cerrado_tecnico.png`, `1b_abierto_tecnico.png`, `1c_abierto_admin.png`, `ciclo_en_curso.png` (técnico, con el aviso de bloqueo), `ciclo_en_curso_ingeniero.png` (sin el aviso) y `sin_secciones.png`. Se tomaron con la plataforma real, a 598 × 958.

## 6. Otros cambios de esta sesión

- Usuarios de prueba en la base local de desarrollo (`data/autoclave.db`), uno por rol: `tecnico`, `biomedico`, `ingeniero` y `operador`. La contraseña de cada uno es su nombre de usuario seguido de `1234`.
- Bug del teclado anotado con un TODO en `Login.qml`, sin corregir: lo escrito sin tocar Confirmar se pierde.

## 7. Pendiente

- Fase 2 según las puertas de entrada del plan.

## 8. Revisión de Cristian (2026-10-07)

Decisiones:
- Se adoptan las recomendaciones de la §10 del plan para Q-1, Q-2, Q-3, Q-4, Q-6, Q-7 y Q-8. Q-5 (Anexo B) queda pendiente y no afecta a la Fase 1. La Fase 1 ya cumplía Q-1, Q-6, Q-7 y Q-8. Q-2, Q-3 y Q-4 aplican desde la Fase 2.
- Con Q-7 ("basta el botón hamburguesa más tocar fuera para cerrar"), la duda 1 queda resuelta: se deja como está. La duda 7 no se tocó, porque el plan es de Cristian.
- Commit autorizado.

Ajustes hechos:
- **Recuadro azul del cajón.** Sobresalía 16 px del marco (604 frente a 588) del borde del cajón. Ahora la entrada mide el ancho del cajón menos 25 px a cada lado. La prueba QML comprueba que todas las entradas quedan dentro del borde. Se rehicieron las capturas 1b y 1c.
- **Edición del ingeniero durante el ciclo.** El ingeniero puede ajustar Parámetros del ciclo con un ciclo en curso; el técnico no. Está en `permisos_opciones.edicion_permitida(estado, rol, seccion)`. El controlador recibe la sección activa (`seccion`) y recalcula `edicionPermitida`. Por ahora solo cambia el aviso, porque en la Fase 1 no se edita nada.

Dudas nuevas (no decididas; se implementó lo más restrictivo):
8. **Biomédico.** Se trató como el técnico: no edita durante el ciclo. ¿Es correcto?
9. **Alcance de la excepción.** Se aplica solo en el estado CICLO y solo a Parámetros del ciclo. En FALLA, EMERGENCIA y demás estados el ingeniero sigue bloqueado, y también en las otras secciones.
10. **Choque con la especificación 1.** RB-01 y U-8 bloquean en el backend toda edición fuera de PREPARACION y PREPARADO. Antes de la Fase 3 hay que decidir si el backend acepta esta excepción, y qué parámetros del ciclo en curso se pueden cambiar en caliente y desde cuándo surten efecto: de inmediato en la fase activa o desde el siguiente ciclo. Esto toca el control de actuadores, así que conviene una revisión de seguridad (safety-reviewer) en esa fase.

### Respuestas a las dudas 8 a 10 (2026-10-07)

8. Sí: el biomédico se trata como el técnico.
9. El ingeniero puede modificar lo que sea en cualquier momento. Se implementó así: `edicion_permitida` devuelve verdadero para el ingeniero en cualquier sección y en cualquier estado, incluidos CICLO, FALLA y EMERGENCIA. Técnico, biomédico y admin solo editan en PREPARACION y PREPARADO.
10. Un cambio hecho con el ciclo en curso surte efecto desde la fase activa. Esto se aplica en el backend en la Fase 3. La especificación 1 (RB-01 y U-8) debe incluir la excepción del ingeniero antes de esa fase.

### Respuestas a las dudas 2 a 6 (2026-10-07)

2. Una sola línea por nombre (§5.0 manda). Cristian corrigió U-2 en la rev. 3.1: si un nombre no cupiera, la fila pasa a dos líneas y crece lo necesario. Implementado: antes se recortaba con "…"; ahora el texto se ajusta a un máximo de dos líneas y la fila crece si hace falta. La prueba QML lo comprueba con un nombre largo.
3. Se quedan los iconos provisionales hasta que llegue el oficial.
4. "Próximamente" se queda así; es temporal.
5. El standby cierra la sesión: confirmado. Se quitó la marca PROVISIONAL de `Main.qml`.
6. Si la máquina entra o sale de CICLO, OPCIONES se cierra: confirmado, sin cambios.

Suite completa tras estos ajustes: 1881 pruebas pasan, 6 advertencias ya existentes.
