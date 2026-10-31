# U1 — Alarmas y fallas fuera de la barra superior

Instrucción: `instruccion_claude_code_tanda_2.md` §2 U1. Mockup aprobado: `docs/mis_plans/mockup_estado_seguro.png` (3 estados).

## Antecedentes

Al empezar la tanda había cambios sin commitear en `dev` (sesión anterior del 2026-10-19):
- barra de tareas de Windows oculta mientras corren las pantallas (`ui_qml/barra_tareas.py`, `doble_pantalla.py`, `lanzar.py`);
- historial del simulador;
- la franja "NO ABRIR" retirada de `AvisosSeguridad.qml`.

Los dos primeros, con sus pruebas en verde, van en su propio commit (`49c7efa`). La retirada de NO ABRIR queda absorbida por U1, que borra `AvisosSeguridad.qml`. **DECISIÓN SIN CONFIRMAR D-U1-0:** se commitearon en `tanda-2` en vez de dejarlos sueltos. Alternativa: revertir `49c7efa` si no debían entrar.

## Qué se hizo

- **Retirada la franja superior** `Componentes/AvisosSeguridad.qml` (`git rm`) y su montaje en `Main.qml` (z 50, sobre todas las pantallas).
- **Nuevo `Componentes/SeccionEstadoSeguro.qml`** dentro de `PanelNotificaciones.qml` (panel de la campana), por encima de la categoría "Alertas y avisos". Muestra los 3 estados del mockup:
  1. **Paro activo:** fila alta "PARO DE EMERGENCIA — NO ABRIR" y la nota "Suelte el botón de paro…". Sin botón.
  2. **Paro liberado:** fila alta "Paro de emergencia liberado — estado seguro pendiente", aviso naranja (`advertencia*`) y botón azul `accionPrimario` "Confirmar y llevar a estado seguro". Debajo, la nota "Disponible para cualquier operador, sin iniciar sesión". Si el backend rechaza, se muestra el motivo.
  3. **En curso:** fila media, botón deshabilitado con indicador "En curso…" y la nota "NO ABRIR hasta que la cámara esté segura". También mientras la petición de confirmar está en vuelo, para evitar el doble toque.
- **Nuevo `Componentes/InsigniaCampana.qml`**, usado en las cuatro campanas: preciclo, ciclo en curso, Menú Principal y OPCIONES.
  - Cuenta las alarmas más los avisos de seguridad.
  - Roja con el paro o con la confirmación pendiente; **parpadea** mientras la confirmación espera.
  - Amarilla con el estado seguro en curso.
- **Apertura y bloqueo del panel:** el panel se abre solo con el paro o con la confirmación pendiente, y **no se puede cerrar** mientras duren (`PanelModal.bloqueado`). Va por encima de los demás diálogos de la pantalla (z 200).
- **`Main.qml`:**
  - Con el paro o la confirmación pendiente, una pantalla sin campana (login, cambio de clave, nuevo usuario) vuelve a la principal. La sesión no se toca.
  - No se abren el login ni Nuevo usuario mientras dure.
  - Se cierra el teclado y se descarta la intro de arranque.
- **`bridge/standby.py`:** nunca entra en reposo con el paro o el estado seguro activo/pendiente. La aparición y el fin de esos estados cuentan como actividad: despiertan las dos pantallas y reinician el conteo.
- `FilaAlarma.qml` admite texto en varias líneas (`multilinea`).
- `Opciones.qml` recibe `comandosSistema`.
- Textos nuevos en `es.json`/`en.json` (`sistema.estado_seguro_pendiente`, `paro_suelte`, `confirmar_sin_sesion`, `estado_seguro_en_curso_boton`, `no_abrir_hasta_segura`, `seguridad_desconocida`), anotados en `revision_traducciones.md` como sin revisar.

## Revisión del resto de pantallas

Ninguna otra pantalla dibuja alarmas en una franja superior:
- `PantallaPreciclo`, `PantallaCicloEnCurso`, `Login`, `Opciones`, `CambioClave`, `NuevoUsuario` e `Instalacion` solo tienen avisos contextuales dentro de su contenido: sin conexión en el texto de puerta, sin BD en el formulario del login, edición bloqueada, bloqueo del asistente.
- Quedan dos avisos que no son alarmas del equipo; ver D-U1-5:
  - `avisoSinConexion` del Menú Principal: píldora bajo el encabezado;
  - `avisoSinConexionSesion` de `Main.qml`: tarjeta con cuenta regresiva en pantallas con token.

## Pruebas

| Momento | Resultado |
|---|---|
| Antes (línea base en `dev`) | 3358 |
| Después | 3375 |

- `tests/test_t7_avisos_qml.py`, reescrita: cubre los 3 estados, el botón (habilitado, en vuelo, rechazo), la insignia (conteo, rojo, parpadeo, amarillo), la apertura automática, que el panel no se cierre con paro, sin conexión, NO ABRIR, el modo prueba y que no quede ninguna franja `AvisosSeguridad`.
- `tests/test_u1_seguridad_navegacion_qml.py`, nueva, sobre `Main.qml` real:
  - el paro en el login vuelve a la principal con el panel abierto;
  - el avatar no abre el login con paro;
  - la confirmación queda a la vista;
  - sin paro, el login abre. Se comprobó que falla sin la navegación nueva.
- `tests/test_standby.py`: 5 pruebas nuevas (regla, despertar con paro o estado seguro, fin del paro, sin conexión).
- Arneses ajustados (`test_main_menu_principal_qml`, `test_navegacion_*`, `test_opciones_qml`, `test_ui_qml_app`): simulaban todas las banderas en `True`, con lo que el paro quedaba activo. Ahora `PARO_EMERGENCIA` está en falso salvo que la prueba lo pida.

## Revisores

**timing-auditor:** sin Críticos ni Altos.
- TMG-01 (Medio, el panel no se reabre al pasar de paro a confirmación): **corregido**, el panel queda abierto y bloqueado mientras dure cualquiera de los dos.
- TMG-02 (Medio, el login aparece y se expulsa durante el paro): **corregido**, ya no se hace el push. La expulsión queda solo cuando el paro aparece estando en una pantalla sin campana.
- TMG-04 (Bajo): **corregido**, el fin del paro cuenta como actividad.
- TMG-03, TMG-05 y TMG-06 (Bajos): anotados.
  - TMG-03: sin conexión la regla del standby no ve la seguridad.
  - TMG-05: el parpadeo sigue con el panel abierto.
  - TMG-06: el POST de actividad sin control de petición en vuelo; ya existía.

**safety-reviewer:** sin Críticos.
- SAF-01 (**Alto**, panel cerrado durante el paro y no reabierto al liberarlo): **corregido**, el panel se bloquea abierto mientras haya paro o confirmación pendiente. Tiene prueba.
- SAF-02 (Medio, otros diálogos o el teclado encima del panel): **corregido**, z 200 y cierre del teclado.
- SAF-03 (Medio, la intro de arranque tapa el panel): **corregido**, `introTerminada = true` con el paro o la confirmación pendiente. Sin prueba automática, porque el arnés no carga la intro: comprobación manual 3.
- SAF-04 (Medio, sin conexión el paro deja de verse): **corregido**, fila alta "Sin conexión: estado del paro de emergencia y del estado seguro desconocido. NO ABRIR.".
- SAF-05 (Bajo, `mensaje` compartido con Apagar y doble POST posible entre la aceptación y el siguiente `/status`): PENDIENTE de bajo impacto; el backend rechaza el segundo envío.
- SAF-06 (Bajo, la fila del paro tiene el mismo estilo que cualquier alarma): se ajusta al mockup aprobado; anotado.
- SAF-07 (Bajo): ver D-U1-5.
- Preguntas del revisor:
  - **Puerta con paro:** el backend ya rechaza la apertura con paro, estado seguro y cámara no segura (T4/T5, `camara_segura` en `/status`). La UI solo informa.
  - **Instalación:** el asistente (ventana aparte) no mostraba la franja tampoco antes. Ver comprobación manual 4.

## DECISIONES SIN CONFIRMAR

- **D-U1-1:** el panel no se puede cerrar mientras haya paro o confirmación pendiente. Durante ese tiempo la pantalla queda dedicada al aviso; la campana y su insignia siguen. Alternativa: dejar cerrarlo y reabrirlo a los N segundos.
- **D-U1-2:** "NO ABRIR" con la cámara no segura pasa a ser una fila media del panel, contada en la insignia. No abre el panel solo. Alternativa: mostrarlo también en la tarjeta de puerta de la preciclo.
- **D-U1-3:** MODO PRUEBA es una fila baja (cian) del panel, contada en la insignia mientras dure. Esa es su "insignia permanente".
- **D-U1-4:** con el paro o la confirmación pendiente no se abren el login ni Nuevo usuario. Un técnico sin sesión no entra hasta confirmar; con sesión, OPCIONES tampoco se abre desde el avatar.
- **D-U1-5:** los avisos de **conexión** se dejan donde están: la píldora del Menú Principal y la tarjeta de sesión con cuenta regresiva en las pantallas con token. No son alarmas del equipo y dependen de la pantalla. Alternativa: pasarlos al panel.

## Comprobaciones manuales (Cristian)

1. En el equipo, pulsar el paro con la preciclo a la vista: el panel se abre solo, en rojo, sin botón y sin poder cerrarse. La insignia está roja.
2. Soltar el paro: aparece el aviso naranja y el botón azul. La insignia parpadea. Confirmar sin sesión: "En curso…" y luego el panel se puede cerrar. Repetir desde el Menú Principal, OPCIONES, el login y el ciclo en curso, en las dos pantallas.
3. Reiniciar el equipo con el paro pulsado: tras el arranque se ve el panel del paro (la intro no lo tapa).
4. Con el asistente de instalación abierto (ventana aparte) no hay campana. Confirmar que el paro se ve en las ventanas normales.
5. Revisar el tamaño de los textos del panel y del botón en la pantalla real.
