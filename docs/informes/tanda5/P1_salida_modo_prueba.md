# P1 — El modo prueba termina al cerrar su ventana ★

## Qué se hizo
La otra sesión ya cubría estos caminos: Atrás, otra entrada del cajón, Inicio y Cerrar sesión desde Opciones (`_salirCon`), además del cambio de segmento y la destrucción de la pantalla (`Component.onDestruction`). Faltaban dos:
1. **Otra pantalla encima** (engranaje → Menú principal, o cualquier `pila.push` sobre Opciones). Opciones seguía viva, el modo prueba seguía activo y el keepalive estaba detenido. Ahora `OpcionesEntradasSalidas.qml` sale del modo prueba en `onVisibleChanged` cuando `!visible`.
2. **Cierre de sesión fuera de Opciones** (standby, suspensión, inactividad de la sesión, salida de la aplicación). El logout llegaba antes que la salida, con el token ya inválido. Ahora `SesionVentana` tiene avisos previos al cierre (`al_cerrar_sesion`), que corren en `cerrar_sesion` y `cerrar_al_salir` con el token todavía válido. `EntradasSalidasController` se registra al entrar y sale con `/io/test/exit`, con el motivo "cierre de sesión" (agregado a la lista cerrada del backend).

Respaldo si la UI se cae o la llamada falla: el vigilante SAF-01 (2 s) y el plazo de inactividad de 90 s, ya probados en `test_io_momentaneas_keepalive.py` y `test_revision_tanda4.py`.

Se conserva el botón "Salir del modo prueba". El endpoint `/io/test/force-exit` se queda, sin botón.

## Revisores
**safety-reviewer:** sin Altos ni Críticos.
- Medio SAF-01: los avisos sobrevivían a `cerrar_local` y podían dispararse luego con la sesión de otro usuario. **Corregido:** `cerrar_local` los descarta y lo registra en el log.
- Bajo SAF-02: si la salida devuelve `sesion_invalida`, el controlador baja su estado local.
- Bajo SAF-04: el token se leía fuera del candado en `_caducar_momentanea`. **Corregido.**

**timing-auditor:**
- **Alto TMG-01:** el aviso usaba el plazo de 5 s de `enviar` y bloqueaba la salida de la aplicación. **Corregido** con `enviar_al_cerrar` y `PLAZO_AVISO_CIERRE_S = 0,5 s`. Ante un 401 no llama a `cerrar_local` ni navega.
- Medio TMG-02 (bloqueo de la UI en el logout): queda acotado por el mismo plazo.
- Medio TMG-03 / TMG-07: un temporizador viejo podía sacar a una sesión nueva. **Corregido** con `_generacion_prueba`. La generación no cambia cuando la misma sesión vuelve a entrar, para no dejar una momentánea sin caducidad.
- Medio TMG-04 (estado local incoherente tras un 401): el aviso limpia siempre el estado local.
- Bajo TMG-05 (causa no auditada): corregido.
- Bajo TMG-06: cubierto por `enviar_al_cerrar`.

## Pruebas
`tests/test_p1_salida_modo_prueba.py` cubre: botón, standby y salida de la aplicación; sin modo prueba; después de una salida normal; fallo de la salida; aviso que lanza una excepción; avisos descartados sin token; plazo corto ante un 401; pantalla QML tapada o destruida; `_salirCon`. También `test_temporizador_de_otra_generacion_no_saca_a_la_sesion_nueva`.

## Comprobación manual (Cristian)
En el equipo, activar una salida en modo prueba y salir por cuatro caminos: Menú principal, Inicio, inactividad de la sesión y cierre de la aplicación. En todos, la salida debe apagarse en 1 s o menos, o en 2 s o menos si actúa el vigilante.
