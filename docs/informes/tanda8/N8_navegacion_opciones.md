# N8 — Navegación de Opciones y cierre de sesión (tanda 8)

Rama: `tanda-8-n8` (desde `tanda-8`, 23704cb). Fuente: `decisiones_tanda_8.md` D8-4.1 y D8-4.2, e instrucción §2 N8.

## Resumen
- **D8-4.1 hecho:** Opciones tiene su propio historial. Los cambios están concentrados en `Pantallas/Opciones.qml`, el contenedor. Ningún archivo de sección se tocó, para facilitar la unión con V8a, R8 y M8.
- **D8-4.2 hecho:** Cerrar sesión invalida el token y lleva al LOGIN. Es una sola línea en `Main.qml`.
- **Reglas de navegación del 19-oct:** se verificaron las 6 y las 6 cumplen. No se cambió código por ellas.
- Hay 5 pruebas QML nuevas y 17 capturas en `docs/informes/tanda8/capturas/n8/`.

## D8-4.1 — Atrás con historial (`Opciones.qml`)

**La pila.** `historial` guarda entradas `{seccion, estado}`, y la pantalla expone `profundidadHistorial` (solo lectura).
- Elegir otra sección en el cajón apila la sección que se deja. Pasa igual si se elige directamente o después de confirmar el descarte de cambios en `dialogoCambiarSeccion`.
- El `estado` que se guarda incluye:
  - Parámetros del ciclo: el programa (`controlador.numero`), la fase (`controlador.seccion`) y la vista (`programa`, `seccion`, `sensores` o `entradas`);
  - Parámetros del equipo: el submenú (`controlador.grupo`);
  - Usuarios: la pestaña (`pestana`);
  - Entradas/Salidas: el segmento (`segmento`) y la calibración de un sensor (`sensorEnCalibracion`, `segmentoOrigen`);
  - Mantenimiento: la vista (`vista`, `calibracion_atm`);
  - en todas las secciones: el **desplazamiento** de cada `Flickable`/`ListView`. Se recorre el árbol de la sección y cada lista se identifica por su orden y su `objectName`.
- Al restaurar, se repiten las llamadas de carga del controlador: `elegirPrograma`, `abrirSeccion`, `cargarSensores` y `cargarEntradas`, y `abrirGrupo` en Parámetros del equipo. El desplazamiento se aplica en el ciclo de eventos siguiente (`Timer` de 0 ms), cuando las listas ya tienen su contenido.

**Orden de Atrás:**
1. La sección activa cierra su ventana de ajuste. Si hay un valor editado, pregunta Guardar o Descartar (`dialogoGuardarAjuste`, que ya existía).
2. Si no hay ventana abierta, la sección sube un subnivel: de la fase a la lista de programas, del submenú a la entrada, o de la calibración a la sección. Es la lógica que ya existía.
3. Arriba de la sección, Atrás vuelve al nivel anterior de la pila y lo restaura.
4. Con la pila vacía, Atrás sale de Opciones (`atrasPulsado`) y `Main.atras()` vuelve a la pantalla desde la que se entró: Menú principal, Preciclo o Ciclo.

**Home** no cambió: sale de todo, a Preciclo o Ciclo.

**Pruebas** (`tests/test_n8_historial_opciones_qml.py`, banco offscreen con backend doble):
- recorrido de ida y vuelta Parámetros del ciclo › 02 › Calentamiento (desplazada 600 px) → Mantenimiento → Información del sistema, regresando con el mismo programa, la misma fase y el mismo desplazamiento;
- ventana de ajuste abierta, sin cambios y con un valor editado; cambio de sección con un valor editado;
- Parámetros del equipo (submenú Chaqueta) → Usuarios (pestaña Operadores) → Entradas/Salidas (segmento Presión) → Fecha y hora, de ida y vuelta;
- pila vacía y Home.

`tests/opciones_qml_banco.py`: `correr()` acepta ahora `dir_capturas`, con valor por defecto, así que es compatible con lo que ya lo usaba.

## D8-4.2 — Cerrar sesión (`Main.qml`)
- `onCerrarSesionPulsado` llama a `sesionVentana.cerrarSesion()` (cierre local más `POST /auth/logout` con el token) y luego a `ventana.irALogin()`. `irALogin()` vacía la pila, pone la principal que corresponde al estado y apila el LOGIN encima.
- Desde ese Login, Atrás vuelve a Preciclo o Ciclo, con la pila en reposo + principal. Home hace lo mismo.
- Un login correcto sigue el flujo normal: `irAOpciones(true)`, o el cambio de contraseña si es obligatorio.
- Con cambios sin guardar, se pide confirmación antes de cerrar. Es el `_salirCon` que ya existía (`dialogoSalirOpciones`). Cancelar conserva la sesión y se queda en Opciones.
- El cierre por inactividad (5 min) no se tocó.

**Prueba:** `tests/test_n8_cerrar_sesion_qml.py`, con `Main.qml` real, parametrizada en PREPARADO y en CICLO. Comprueba que el logout llega al backend con el token correcto.

## Verificación de las reglas de navegación del 19-oct (instrucción de la tanda 2, U1–U3)

| Regla | Resultado | Evidencia |
|---|---|---|
| Atrás regresa a la pantalla anterior | **Cumple** | `Main.qml::atras()` (`pila.pop()`, o la principal si solo quedan reposo + principal) en Login, Menú principal, Cambio de clave y Nuevo usuario. Opciones, ahora con historial propio. `test_u2_navegacion_qml.py` y las pruebas N8. |
| Home lleva a Preciclo o Ciclo | **Cumple** | `volverAPrincipal()` → `irAPrincipal()` según `machineState` en Menú, Login, Cambio de clave, Opciones y Nuevo usuario. `test_opciones_qml.py::inicio_desde_menu` y `test_u2`. |
| En Preciclo el login va en el lugar de Home | **Cumple** | `PantallaPreciclo.qml` no tiene `casa.svg` ni `inicioPulsado`; el avatar está en la celda derecha `x: raiz.m(800)` con `personalizada: true` (`test_u2::test_preciclo_sin_home_y_con_el_avatar_en_su_lugar`). |
| Fallas y alarmas en el espacio de alarmas, no en una barra superior | **Cumple** | `AvisosSeguridad.qml` ya no existe ni se monta. El paro, el estado seguro, NO ABRIR y el modo prueba están en `PanelNotificaciones` › `SeccionEstadoSeguro` y en la tarjeta de alarmas de Preciclo y Ciclo. Ver la observación 1. |
| El panel de la campana no se abre solo | **Cumple** | `panelNotificaciones.abrir()` solo se llama desde `onCampanaPulsada` u `onClicked` de la campana, en Preciclo, Ciclo en curso, Menú y Opciones. `PanelNotificaciones.qml` no tiene apertura automática (comentario U4). |
| El Menú principal no tiene el botón de agregar tiempo de secado | **Cumple** | `MenuPrincipal.qml` no tiene la tarjeta (comentario U5 de la tanda 3): Reportes e Información ocupan esa fila. `test_menu_principal_pantalla_qml.py` lo cubre. |

**Observaciones (sin cambio):**
1. `Main.qml` tiene dos superposiciones que no son alarmas en barra superior:
   - `avisoSinConexionSesion`, anclado arriba: es el aviso de sesión sin conexión con su cuenta regresiva (plan T-8 §3.7), no una falla del equipo;
   - `alarmaArranque`, centrado: es la falla bloqueante de arranque sobre la intro, marcada PROVISIONAL.

   Las dejo como están.
2. En el banco, `OpcionesBitacora.qml:111` avisa de un ciclo de enlace en `height` cuando el controlador tiene un mensaje de error (backend doble vacío). Por eso las pruebas N8 usan Información del sistema en lugar de Bitácora. Es preexistente y ajeno a N8.

## DECISIONES SIN CONFIRMAR
1. **Navegación dentro de una sección:**
   - **Qué hace:** dentro de una misma sección, Atrás sube por la jerarquía (fase → lista de programas, submenú → entrada) antes de consultar la pila, y solo el cambio de sección agrega un nivel a la pila. Elegir otro programa o abrir otra fase dentro de Parámetros del ciclo no se apila.
   - **Ejemplo:** Parámetros del ciclo › 02 › Calentamiento → Mantenimiento. Atrás lleva a Parámetros del ciclo › 02 › Calentamiento; otro Atrás, a la lista de programas de 02; otro, sale.
2. **Lo que no se restaura:**
   - la ventana de ajuste abierta (vuelve cerrada);
   - los valores tecleados sin guardar: se descartaron con confirmación al cambiar de sección;
   - los campos de formularios y los filtros: el tipo y los intervalos en Mantenimiento, los filtros de la Bitácora, la fila seleccionada en Usuarios.
3. **Límites de la pila:**
   - elegir la sección activa no agrega nivel;
   - la pila guarda como máximo 50 niveles;
   - una sección que ya no es visible para el rol se salta.
4. **Navegación bloqueada:** con la calibración atmosférica midiendo, Atrás no hace nada (igual que antes).
5. **Modo prueba:** volver por Atrás a Entradas/Salidas › Salidas NO reactiva el modo prueba. Salir de la sección lo cierra, como ya se hacía (D-ES-08).
6. **Cerrar sesión con paro o confirmación de estado seguro pendiente:** `irALogin()` no apila el LOGIN y deja la principal (regla U1/TMG-02 que ya existía). La sesión igual se cierra.

## PREGUNTAS PARA CRISTIAN
- ¿Debe apilarse también el cambio de programa o de fase dentro de Parámetros del ciclo (historial estricto), o basta con la jerarquía dentro de la sección (la decisión 1 de arriba)?

## Commits
- `8d200fa` feat(tanda8-n8): historial propio de Opciones (D8-4.1)
- `ec64a10` feat(tanda8-n8): cerrar sesion lleva al login (D8-4.2)
- `1917d02` docs(tanda8-n8): capturas de los recorridos de navegacion
- (este informe y el log de la suite)

## Archivos que pueden chocar al unir
- `src/autoclave/ui_qml/qml/Pantallas/Opciones.qml`: bloque nuevo después de `elegirSeccion`, la función `atras()` y el `onConfirmado` de `dialogoCambiarSeccion`. V8a (barra flotante) y R8 (Opciones avanzadas) tocan este archivo. **Si R8 agrega un `Loader` para `opciones_avanzadas`, debe sumarse a `_cargadorDe()`** para que su estado se conserve; sin eso, la sección igual entra en la pila, pero vuelve a su estado inicial.
- `src/autoclave/ui_qml/qml/Main.qml`: una línea (`onCerrarSesionPulsado`).
- `tests/opciones_qml_banco.py`: parámetro opcional `dir_capturas`.
- No se tocó i18n: no hay textos nuevos. No se tocó `db_manager.py`.

## Suite completa
Corrida en el worktree antes del corte por límite de uso (log `tanda8/suites/n8.log`), con `PYTHONPATH=<worktree>/src`:
**5387 passed, 3 skipped, 3 xfailed** en 27 min 21 s (= línea base 5382 + 5 pruebas N8). Informe y log commiteados por la sesión principal al reanudar.
