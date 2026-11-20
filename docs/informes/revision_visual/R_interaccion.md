# Revisión visual (RV): informe de la prueba de interacción (etapa E)

19-nov. Rama `revision-visual`. Arnés: `tests/banco/rv_interaccion.py` (UI completa de una puerta, `autoclave.ui_qml.app.main`, operada con eventos reales de ratón y teclado de QTest en el centro visible de cada control), flujos en `tests/banco/rv_flujos_base.py`, `rv_flujos_ciclo.py` y `rv_flujos_opciones.py`, y backend real con el módulo E/S simulado en `tests/banco/rv_backend_simulado.py`. Capturas y registros en `interaccion/backend_real/`, `interaccion/backend_real_en/` (la misma interfaz cambiada a inglés desde la UI) e `interaccion/simulador/`: una carpeta por flujo con `NN_<paso>.png` y un `registro_<flujo>.json` con lo esperado, si se cumplió (`ok`), las notas y las advertencias del motor QML. El campo `ok` lo calcula el arnés; donde dice false por una comprobación del arnés y no de la aplicación, se aclara abajo.

## Entorno

- **Hardware real:** `Test-NetConnection 192.168.3.7 -Port 502` no respondió (ni ping ni TCP) antes de empezar; nada se conectó al módulo E/S real.
- **Simulador de la UI** (`python -m autoclave.simulador`, 127.0.0.1:8001, velocidad 20): arranque, sesión, menú, Preciclo, ciclo completo y cancelado, Historial y Reportes. Responde solo las rutas de esos flujos (no tiene Opciones, `/language`, usuarios reales ni E/S).
- **Backend real con Modbus simulado:** worktree aislado `..\codigo_autoclave_rv` (desprendido en la rama) con su propia copia de `data/` y de `installation_profile.json`. `rv_backend_simulado.py` se niega a correr fuera de un worktree, levanta `tests/helpers/m31_simulado.py` en 127.0.0.1:15020 con el equipo en reposo (paro liberado, atrapamientos libres, puertas cerradas y presiones a la atmosférica), reescribe solo el `modbus_link.json` del worktree con 127.0.0.1 (y lo comprueba) y arranca `autoclave.backend.main` en 127.0.0.1:8000 con `AUTOCLAVE_REINICIO_PC=0`. En la copia del worktree: `correo.json` con servidor inválido y sin destinatarios, `correo_equipo.json` sin envío ni destinatarios, impresora ya deshabilitada, y dos cuentas de prueba creadas solo en su base (`ingrv`, ingeniero, y `oprv1`, operador). La `data/` del repositorio principal no se tocó (ver «Cierre» del informe principal).
- **Plataforma:** el prompt autorizaba ventanas visibles y Cristian pidió verlas en primer plano, pero la sesión de Windows estaba bloqueada (la captura del escritorio mostraba la pantalla de bloqueo) y una ventana visible no se dibuja así: las capturas salían en blanco y los toques no llegaban. Toda la etapa E corrió con `RV_PLATAFORMA=offscreen`: los eventos de QTest y `grabWindow` funcionan igual y las capturas salen a 1200x1920 sin escalar. Con la sesión abierta, el mismo arnés abre la ventana en primer plano (`--escala` 0,42 para que quepa en el monitor del PC).
- **Idioma:** los flujos corrieron en español; luego la propia UI cambió el idioma a inglés (Parámetros del equipo › Configuración de la máquina, con su diálogo de confirmación) y se repitieron sesión, Opciones, Parámetros y Bitácora en inglés (`backend_real_en/`), y se volvió a español.

## Flujos y resultado

(F = funciona, X = falla de la aplicación, A = falla del arnés corregida y repetida, N = no probado, S = no accionado por seguridad)

1. **Arranque** (simulador y backend real): F. La intro sigue las etapas, termina en el Reposo y un toque lleva a Preciclo. Con el backend real la intro dura más de 60 s (espera de sensores y de la interfaz, ARQ-D3), sin error.
2. **Sesión:** F. Teclado alfanumérico (escribir, borrar, cancelar), usuario o contraseña incorrectos con su mensaje, bloqueo por intentos, login correcto que lleva a Opciones y cerrar sesión. Cambio de contraseña voluntario: N.
3. **Menú Principal:** F. Último ciclo, Mantenimiento, Ciclos hoy, Historial e Información abren su ventana y se cierran; Reportes abre su pantalla; Inicio regresa.
4. **Preciclo:** F. Selector desplegable de programa (abre y elige), campana con el panel de notificaciones, deslizador de inicio incompleto (regresa y no inicia) y completo (inicia el ciclo). En el simulador la puerta no tiene actuador (sin botón). Modal de operador con operadores activos: N (el simulador no los tiene). Deslizador oculto en modo prueba: cubierto por la captura `b_preciclo_modo_prueba` de la etapa B, no por interacción.
5. **Ciclo en curso:** F. Barra de fases y gráfica, cursor con un toque (aparece el globo), campana, deslizador de cancelar incompleto (no cancela) y completo (cancela sin modal), panel de fin de ciclo con «Ver gráfica», CONFIRMAR con su modal y regreso a Preciclo, tanto tras cancelar como tras un ciclo COMPLETADO. Zoom con dos dedos y lupa: N (el arnés no genera toques multitáctiles; cubierto por `tests/test_zom_grafica_zoom_qml.py`).
6. **Opciones** (backend real): F en las 11 secciones (se abren desde el menú de Opciones). Detalle:
   - Parámetros del ciclo: abrir Esterilización, abrir un parámetro, teclado numérico; 999 °C se rechaza (rango 100–140 °C) y 135 °C se guarda con su confirmación.
   - Usuarios: crear (formulario con teclado y lista de roles): F en el backend, con RVI-01 y RVI-02 en la pantalla. Cambiar rol, desactivar y eliminar: N, porque el flujo dependía de la fila del usuario nuevo (RVI-01); los modales están capturados en la etapa B (`f_usuarios_*`).
   - Bitácora: filas, calendario táctil del filtro Desde y «Hoy».
   - Reasignación: tabla visible; Aplicar y Restaurar fábrica: S.
   - Entradas/Salidas (backend real con el módulo simulado): F. Entradas y Salidas, diálogo de precaución del modo prueba («Continuar»), modo prueba activo con su barra, una salida encendida y apagada (orden pendiente y estado), y salida del modo prueba. La orden sale solo hacia el módulo simulado en 127.0.0.1.
   - Idioma, tema y unidades: F. Tema oscuro e idioma inglés con sus diálogos de confirmación (la interfaz cambia en el acto) y vuelta a español y claro.
   - Respaldo y Fecha y hora: S (no se tocó ningún control; Respaldo ni siquiera se abrió, por la lista de prohibidos del arnés). Conectividad: abierta sin enviar el correo de prueba (S).
7. **Historial y Reportes** (simulador): F. Historial con detalle del ciclo; Reportes con las vistas Día, Semana, Mes y Año. Calendario por programa y selector de destino: abiertos en las capturas de la etapa B; el envío: S.
8. **Standby** (simulador): no concluyente. En 7 minutos sin tocar, la pantalla no pasó al Reposo; con el simulador el tiempo de standby depende de su configuración, que no se revisó. Tocar el Reposo sí lleva a la pantalla principal (flujo 1).
9. **Pantalla 2 y sin conexión:** N. El arnés tiene el modo `--espejo` para la pantalla 2, pero no se llegó a correr las dos puertas a la vez, ni a detener el backend a mitad de una pantalla (el estado sin conexión está en las capturas `*_sin_conexion` de la etapa B).

No accionados por seguridad: Apagar equipo, Reiniciar PC, instalación, Respaldo/restaurar, configurar módulo, Red del módulo E/S, Fecha y hora, envío de correo, impresión, Aplicar y Restaurar fábrica de Reasignación.

## Hallazgos de interacción

### RVI-01. Usuarios: el usuario recién creado no aparece en la lista al volver
- Flujo 6 (Usuarios), pasos `nuevo_usuario` → `usuario_creado`. Reproducido dos veces (`interaccion/backend_real/usuarios_1/` y `usuarios_2/`).
- Qué se hizo: Nuevo usuario → nombre, usuario, contraseña y confirmación con el teclado → Rol Técnico → Guardar usuario.
- Esperado: volver a Usuarios con el usuario nuevo en la lista.
- Pasó: el backend lo creó (`POST /usuarios` 200, fila `usuario_creado` en la bitácora y en la base), pero la lista mostrada al volver no lo incluye aunque se esperó 8 s; sí aparece al entrar de nuevo a la sección.
- Causa probable: `Pantallas/OpcionesUsuarios.qml:41` carga la lista solo en `Component.onCompleted`; Nuevo usuario se apila encima y al volver (`Main.qml:206`, `ventana.atras()`) la página de Opciones sigue viva y no recarga.
- Severidad MEDIA (impide seguir la tarea: cambiar rol, desactivar o eliminar al usuario recién creado sin salir y volver). Categoría 2.

### RVI-02. Nuevo usuario: «Seleccione un rol» sigue en rojo después de elegir el rol
- Flujo 6, paso `formulario_lleno` (`usuarios_2/04_formulario_lleno.png`): con «Técnico» ya elegido, el recuadro sigue rojo con el mensaje «Seleccione un rol» hasta guardar.
- Causa probable: el error de validación del rol no se limpia al elegir (`Pantallas/NuevoUsuario.qml`, campo Rol y `raiz.error("rol")`).
- Severidad BAJA. Categoría 2.

### RVI-03. `tiempo_esterilizacion` admite hasta 9999 min
- Flujo 6 (Parámetros), primera corrida: el teclado aceptó 999 min y se guardó (en la copia aislada), porque el rango publicado es 1,0–9999,0 min (`interaccion/backend_real/parametros_1/`).
- No es una falla de la pantalla, que respetó el rango; se informa porque un tope de casi 7 días para la exposición parece un valor por defecto sin revisar.
- Severidad BAJA. Categoría 2 (catálogo de parámetros).

### RVI-04. Al ingeniero la lista de roles de Nuevo usuario no le ofrece «Operador»
- Flujo 6: la lista muestra Admin, Técnico e Ingeniero; los operadores se gestionan en la pestaña Operadores (T30-03). Coincide con el diseño; se anota porque la pantalla Nuevo usuario de la etapa B (`nuevo_usuario_roles`) mostraba cuatro roles, incluido Supervisor, con el doble de prueba.
- Sin severidad: informativo.

### RVI-05. Inglés: la unidad «seg» sin traducir en Parámetros del ciclo y del equipo
- `backend_real_en/parametros/07_guardado.png`: «Steam pulse period during sterilization * 2 seg» y los tiempos en segundos de otras filas, con el resto en inglés. En la misma pasada se confirmó RV-28 (rol «operador» en minúscula y sin traducir en Users).
- Causa probable: la unidad viene del catálogo del programa (`"unit": "seg"` en los JSON de `cycles/`) y la pantalla la muestra sin pasarla por `Unidades`/i18n.
- Severidad BAJA. Categoría 2.

### Notas del arnés (no son hallazgos)
- `toque_desviado` con `detectorToques` en Ciclo en curso: es el detector de actividad a pantalla completa, que deja pasar el toque (el botón respondió en todos los casos).
- `ok=false` del arnés que no son de la aplicación: `tras_intro` (la intro dura más de 60 s con el backend real), `guardado` de Parámetros (el arnés no relee la fila; la captura muestra el valor guardado), `filtro_hoy` de Bitácora (el calendario sí se cierra con la fecha puesta) y `seccion_respaldo` (Respaldo no se abre a propósito).
- La primera corrida de cada flujo de Opciones se desviaba por fallas del arnés (diálogos que confirman con «Continuar» o «Confirmar», el toque que cierra el teclado, una sección que tarda en cargar); se corrigieron y se repitieron. Cada flujo corre ahora en su propio proceso de la UI (`_rv_correr.sh` en el worktree).
- `toque_desviado` en los `SelectorSegmentos` (idioma, tema, segmentos de Entradas/Salidas): el selector recibe el toque con una sola MouseArea y elige por posición; la opción respondió.
- Con el teclado abierto, el primer toque fuera de él lo cierra (por diseño) y hace falta un segundo toque para el control.
- Las contraseñas se ven como cuadros en las capturas offscreen: la letra empaquetada no tiene el carácter de máscara y offscreen no tiene letras de respaldo del sistema. A confirmar en la estación (Windows sí tiene respaldo).

## Advertencias QML y errores de log

- `This plugin does not support raise()` (offscreen): del arnés.
- `Mouse event at 1203..1239, 1677 occurs outside target window`: el arnés arrastra la manija de los deslizadores hasta 1,1 veces su ancho para completar el gesto; no es de la aplicación.
- Ninguna otra advertencia del motor QML en los flujos. El backend real no registró errores durante las corridas; solo los 503 de `/units` mientras el arranque estaba retenido, como corresponde.

## Para probar en la estación real con los táctiles

- Toques y arrastres con el dedo en los deslizadores de inicio y cancelar (tamaño de la manija, velocidad del arrastre).
- Zoom con dos dedos y la lupa de la gráfica.
- Pantalla 2 siguiendo a la 1 (idioma, tema, unidades) y la vuelta tras perder y recuperar el backend.
- Modal de operador con operadores activos y puerta con actuador.
- Que el carácter de máscara de las contraseñas se dibuje.
- Cambio de contraseña voluntario y standby por inactividad con el tiempo real del equipo.
