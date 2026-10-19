# Instrucción maestra para Claude Code — Tanda 2 (19-oct-2026)

Objetivo: con la entrega del equipo de pruebas aplazada al lunes 26-oct-2026, cerrar ajustes de interfaz pedidos por Cristian, los pendientes de seguridad de la tanda anterior, retirar el código tkinter, y preparar la hoja de pruebas de banco. Cristian puede no estar presente: ante ambigüedad aplica la regla 6.

## 0. Reglas generales
Aplican TODAS las reglas de la sección 0 de `docs/mis_plans/instruccion_claude_code_tanda_noche.md` (informes en español, pruebas primero, sin `git add -A`, sin push, revisores `safety-reviewer` y `timing-auditor` en etapas de seguridad, `time.monotonic()`, textos en i18n es/en, estado e informes por etapa), con estos cambios:
- Rama: `dev-noche` YA fue unida a `dev` por Cristian (19-oct). Crea `tanda-2` desde `dev` (verifica con `git merge-base --is-ancestor dev-noche dev`; si no lo está, avisa en el informe y parte de `dev-noche`). No unas nada a `dev`.
- Estado: `docs/informes/tanda2/estado.md`; informe de etapa `docs/informes/tanda2/<id>_<nombre>.md`; índice final `docs/informes/informe_tanda_2026-10-19.md`.
- Línea base: 3358 pruebas esperadas; regístrala al inicio.
- Si existe `docs/informes/tanda2/estado.md`, REANUDA desde la primera etapa no terminada.

## 1. Decisiones de Cristian (19-oct) — fuente de verdad
1. El equipo de pruebas NO lleva DO1 ni DO2 (generador): el generador interno tiene sus propios controles y el software no los enciende ni los lee.
2. Cambiar de ciclo (`POST /cycle/select`) sin sesión y estando en FALLA es el comportamiento deseado (ningún fallo exige técnico). Se conserva; se documenta como decisión y se prueba (ver S2).
3. Retirar el código tkinter y la ruta antigua del asistente (`wizard.py`).
4. Preparar la hoja de pruebas de banco.
5. El plan de la estación Windows (quiosco) queda para el final y es opcional.
6. UI (observaciones de Cristian, ver U1–U3). El mockup de U1 (`mockup_estado_seguro.png`, 3 estados) quedó APROBADO.
7. El cierre de sesión es SOLO por tiempo de inactividad (SAF-01). No habrá botón manual de cerrar sesión en ninguna pantalla.

## 2. Etapas (en este orden; lo último cae primero)

**U1. Alarmas y fallas fuera de la barra superior.** Hoy `AvisosSeguridad.qml` (montado en `Main.qml`, z 50, arriba de todas las pantallas) muestra franjas de paro, estado seguro y modo prueba. Las fallas, alarmas y avisos NO deben aparecer en una barra superior: el lugar es el espacio de alarmas/fallas/notificaciones (campana y panel de notificaciones; `PanelNotificaciones.qml`, `FilaAlarma.qml`). Muévelos allí conservando su función: el paro activo debe seguir siendo inequívoco y accesible, y la acción "Confirmar y llevar a estado seguro" debe seguir disponible para cualquier operador sin rol (el paro liberado no puede quedar sin salida). Revisa también que ninguna otra pantalla (Preciclo, Ciclo en curso, Login, Opciones, Instalación) dibuje alarmas en una franja superior. Diseño aprobado de la confirmación (ver `docs/mis_plans/mockup_estado_seguro.png`): dentro del panel de la campana, en tres estados — (1) paro activo: fila de alarma alta "PARO DE EMERGENCIA — NO ABRIR", sin botón; (2) paro liberado: fila de alarma, aviso naranja "Paro liberado. Verifique que no hay fuga antes de continuar." y botón azul `accionPrimario` "Confirmar y llevar a estado seguro" (sin sesión, cualquier operador); (3) en curso: botón deshabilitado con indicador "En curso…" y nota "NO ABRIR hasta que la cámara esté segura". Mientras haya una confirmación pendiente, la campana muestra un punto/insignia rojo parpadeante para que se vea sin abrir el panel. Para el resto de avisos, decide lo más seguro y anótalo como DECISIÓN SIN CONFIRMAR. Si el MODO PRUEBA necesita un indicador permanente, déjalo como insignia en el espacio de notificaciones, no como barra. Revisores obligatorios.

**U2. Navegación inferior uniforme.** Reglas de Cristian, para TODAS las pantallas:
- Preciclo: eliminar el icono de Home; el icono de login (avatar) se desplaza a la derecha, a la posición donde estaba Home.
- Icono Atrás (back): regresa a la pantalla ANTERIOR. Ya no cierra sesión.
- Icono Home: sale de todas las pantallas y regresa a Preciclo o a Ciclo en curso, según corresponda al estado del equipo.
- Revisa `BarraInferior.qml`, `BarraInferiorMenu.qml`, `PantallaPreciclo.qml`, `Login.qml`, `MenuPrincipal.qml`, `Opciones.qml`, `CambioClave.qml`, `NuevoUsuario.qml`, `Instalacion.qml` y la navegación de `Main.qml`/`app.py`. Haz primero un inventario (pantalla → qué iconos tiene hoy → qué hacen) en el informe, y luego la tabla objetivo.
- Cierre de sesión: solo por inactividad (decisión 7). Retira el icono/acción "Salir" de la barra del Menú Principal (`BarraInferiorMenu.qml`, `salirPulsado`, `salirHabilitado`, TODO(MP-03)) y su código muerto; la celda queda libre o se reacomoda según el inventario. No agregues cierre manual a ninguna pantalla. La inactividad (SAF-01) no cambia: al vencer, cierra sesión y regresa a Preciclo o Ciclo en curso según corresponda; verifica y prueba que Home/Atrás no dejan una sesión abierta sin pantalla. Pantalla de ciclo en curso: la sesión sigue las mismas reglas.
- Atrás no debe poder salir de un flujo de seguridad (asistente de instalación, confirmación de estado seguro) hacia una pantalla inválida; anota cómo lo resolviste.
- Pruebas QML/de controlador de cada transición. Revisores obligatorios (navegación durante ciclo).

**U3. Menú Principal: retirar el botón de agregar tiempo de secado.** Elimina el botón (la tarjeta de tiempo de secado queda informativa, sin acción). Búscalo en `MenuPrincipal.qml`, `TarjetaMenu.qml`/`TarjetaResumen.qml` y `bridge/resumen_sistema.py`; hay un `TODO(MP-11)` sobre "tiempo adicional de secado" en `MenuPrincipal.qml` (~línea 238). Si no encuentras el botón, repórtalo con captura de dónde buscaste, no inventes uno. Quita también el código muerto asociado, sin tocar el valor mostrado de tiempo de secado.

**S1. DO1/DO2 en el equipo de pruebas.** Este equipo no lleva DO1 ni DO2. Verifica y deja por escrito: (a) que ningún código del perfil `vapor_source=generator` los enciende ni espera su estado; (b) que no hay validación, alarma, diagnóstico de E/S, prueba del modo prueba ni simulador que los requiera para el equipo de pruebas; (c) que el perfil de instalación y el asistente lo reflejan sin dejar salidas "huérfanas". Documenta que para otros equipos (caldera externa o mixto) la asignación queda abierta. Cierra el pendiente T2 con esa nota. Si encuentras salidas de generador mapeadas a otras DO, repórtalas sin cambiar el cableado asumido.

**S2. `/cycle/select`.** Conserva el cambio de programa sin sesión y en FALLA (decisión 2). Pero verifica y prueba que `set_active_cycle` rechaza el cambio mientras hay un ciclo EN CURSO (incluye estado seguro en curso y paro activo), que un programa dañado sigue rechazado (RB-04.4) y que el cambio queda en la bitácora con el origen. Si hoy no se rechaza algún caso de ciclo en curso, corrígelo. Revisores obligatorios.

**S3. Resto de pendientes de seguridad (T3, T5, T8, T9).**
- Calibración sin límites de plausibilidad (T3): agrega límites de plausibilidad por canal al catálogo y rechaza/avisa fuera de ellos (decide valores conservadores, anótalos).
- CIC-10 (T5): salida autorizada cuando el estado seguro no puede terminar. Diseña el camino más seguro; si requiere decisión de producto, déjalo PENDIENTE con la propuesta.
- SAF-03 (T8): una BD que falla en caliente debe activar OPERANDO_SIN_BD (con el respaldo JSONL), sin detener el ciclo en curso.
- fsync del respaldo dentro del tick (T8): sácalo del lazo de control (hilo/cola) sin perder la garantía de escritura; `timing-auditor` obligatorio.
- `door_id` con dos pantallas en un solo PC y `source_door` (T9 SAF-03): defínelo y prueba.
- Validar en simulador que SECADO alcanza atm − rango con la bomba y válvulas cerradas (T5), si el simulador lo permite; si no, déjalo para banco en la hoja de pruebas (P1).
Revisores obligatorios en cada subpunto de seguridad.

**R1. Retiro de tkinter y punto de entrada de producción.**
- Inventario primero (informe): módulos tkinter, `wizard.py`, el .exe viejo y sus .spec, referencias en pruebas, scripts y documentación. Nada se borra sin estar en el inventario.
- Retira `wizard.py` y la ruta antigua del asistente (el asistente QML de T9 es el único). Retira el código tkinter muerto y sus pruebas. Los archivos retirados van con `git rm` en commit propio (reversible).
- NO retires las vistas PySide (Fase 5 de Opciones sigue fuera de alcance).
- Define y documenta el punto de entrada único de producción: el lanzador que arranca backend como subproceso supervisado y las 2 UI QML. Prepara el `.spec` (PyInstaller u otro ya usado en el repo) pero NO compiles ni distribuyas el ejecutable; la compilación la hace Cristian en el PC industrial. Lista en el informe cómo compilarlo y cómo probarlo.
- Suite completa en verde; `grep` final de `tkinter` sin resultados fuera de documentación histórica.

**P1. Hoja de pruebas de banco (E7) para el equipo de pruebas.** Entregable: `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (y una versión imprimible en `.xlsx` o tabla que se pueda marcar). Para cada prueba: objetivo, precondiciones, pasos, resultado esperado, criterio de aprobado/fallo, campo para valor observado y firma. Debe cubrir como mínimo: las 11 comprobaciones manuales de `informe_tanda_2026-10-14.md` §5; Instrumental 134 y 121 completos; Líquidos con la sonda dentro del líquido (HAZ-LIQ-01, enfriamiento con contrapresión a 80 °C antes de la rápida, aire residual sin prevacío); paro de emergencia NC (soltar, confirmar, estado seguro); "NO ABRIR" y apertura solo con cámara segura; puertas manuales (un sensor de cerrada por puerta, puerta abierta en ciclo = FALLO); pérdida de comunicación y de energía en ciclo; roles de sensor (Principal/Referencias/No en uso); modo sin BD; firmware 1.0.0 (versión e ID únicos solo en Información del sistema); SECADO con bomba y válvulas cerradas; vigilancia del corte por calidad de vapor del calentamiento. Marca qué pruebas pueden hacerse sin vapor (en seco) y cuáles requieren equipo en operación. Incluye el orden seguro de ejecución y una lista de registros que se deben conservar (para el expediente 62304).

**W1 (OPCIONAL, solo si todo lo anterior quedó commiteado). Plan de la estación Windows.** Documento `docs/mis_plans/planeacion_estacion_windows.md`: quiosco, arranque sin logo ni login, control de actualizaciones, AnyDesk, apagado desde el software, tareas programadas, cuenta restringida, y qué se prueba en el PC industrial. Solo documento; no ejecutes cambios de sistema.

## 3. Fuera de alcance
Compilar/cargar firmware, pruebas en banco, Fase 5 de Opciones, USB de recuperación, licencia/activación, voz, quinto programa, creación/borrado de programas, cualquier `git push` o unión a `dev`.
