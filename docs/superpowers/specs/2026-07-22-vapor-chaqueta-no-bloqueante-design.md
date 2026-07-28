# Vapor de chaqueta no bloqueante en PREPARACION/PREPARADO

## Contexto

Hoy `vapor_suministro` (DI de presencia de vapor en la línea de suministro) se
trata como un suministro "duro" idéntico a `agua_bomba`, `agua_generador` y
`aire_comprimido`:

- En **PREPARACION** (`preparacion.py`), `verificar_suministros()` lo incluye
  en la lista de suministros obligatorios dentro de `supervisor()`. Si falta,
  `supervisor()` retorna `False` y `run()` resetea `self.step = 0`
  (`preparacion.py:61-63`). Como PREPARACION no tiene timeout, el equipo queda
  reiniciando la secuencia de pasos indefinidamente mientras no vuelva el vapor.
- En **PREPARADO** (`preparado.py`), el mismo `verificar_suministros()` hace
  que `supervisor()` retorne `False` y `run()` retorne `False` antes de
  siquiera llegar a `esta_preparado()` (`preparado.py:49-51`). Esto bloquea
  `LISTO_PARA_CICLO` aunque puertas, presión de cámara y drenaje estén
  perfectamente listos.
- En **CICLO** (`ciclo.py::_mantener_chaqueta`, líneas 143-146) el
  comportamiento **ya es el deseado**: si falta vapor, solo se cierra la
  válvula (`vapor_chaqueta_off()`) y se continúa sin alarma ni cancelación;
  el ciclo eventualmente puede fallar por los timeouts propios de cada fase
  (p. ej. `calentamiento.py`, `precalentamiento.py`) si la falta de vapor se
  prolonga. No requiere cambios de lógica, solo se le añade una alarma
  informativa (ver Cambio 4).

Razón de negocio (dada por el usuario): pedir vapor cuando no hay suministro
—o cuando la presión de línea está baja— produce vapor demasiado húmedo,
generando condensación excesiva en la chaqueta. Por eso el sistema no debe
insistir en abrir la válvula cuando no hay suministro, pero tampoco debe
tratar esa ausencia como un fallo bloqueante de todo el equipo: debe permitir
que el resto de la preparación avance, dejando el acondicionamiento de la
chaqueta "pendiente" hasta que el vapor regrese.

## Mecanismo ya existente para alarmas no bloqueantes

La clase `Alarm` (`state_machine/alarms/alarm.py`) ya soporta
`blocks_operation: bool = True`. Este flag no tiene lectores dentro de la
máquina de estados hoy (`AlarmManager.has_blocking_alarm()` no se consume en
ningún otro punto del código), pero es el mecanismo ya establecido en el
proyecto para alarmas puramente informativas — usado en
`devices/puertas/advanced_door.py:376-383` para el caso
"abriendo en modo seguro". Se reutiliza el mismo patrón aquí: alarmas de
vapor pendiente se reportan con `blocks_operation=False`.

## Cambios

### 1. `verificar_suministros()` — sacar `vapor_suministro` de la lista dura

En `preparacion.py:156-174` y `preparado.py:239-249`, remover
`"vapor_suministro"` de la lista de suministros verificados por
`verificar_suministros()`. Los demás (`agua_bomba`, `agua_generador`,
`aire_comprimido`, y en PREPARADO también `suministro_electrico`) **no
cambian** — siguen siendo bloqueantes duros como hoy.

Esto evita que `supervisor()` resetee el step (PREPARACION) o bloquee la
ejecución de `ejecutor()`/`esta_preparado()` (PREPARADO) únicamente por falta
de vapor. El manejo de vapor pasa a vivir exclusivamente en la lógica de
chaqueta (cambios 2 y 3).

### 2. `preparacion.py` — paso de chaqueta pasa a ser no bloqueante y continuo

Hoy el paso 2 del secuenciador (`ejecutor()`, líneas 97-99) llama a
`suministrar_vapor_chaqueta()`, que retorna `False` (y por tanto detiene el
avance del step) tanto si falta vapor como si la presión está fuera de banda.

Cambios:

- `suministrar_vapor_chaqueta()` pasa a llamarse **en cada tick de
  `ejecutor()`, sin importar el valor de `self.step`** (igual patrón que
  `ciclo.py::_mantener_chaqueta`, que corre en cada tick del ciclo
  independientemente de la fase activa). Esto asegura que si el vapor vuelve
  después de que el step ya avanzó más allá de 2, el acondicionamiento de la
  chaqueta se retoma automáticamente en segundo plano.
- Dentro de la función: si `vapor_suministro` es falso →
  `vapor_chaqueta_off()`, reporta `SUMINISTRO_VAPOR`
  (`AlarmType.ALERTA`, `blocks_operation=False`), limpia
  `CHAQUETA_FRIA`/`CHAQUETA_SOBRECALENTADA` (no aplican sin vapor), y
  retorna `True` (no bloqueante — "pendiente").
- Si hay vapor: lógica de banda **sin cambios** (abre/cierra válvula según
  `presion_chaqueta ± rango_presion_chaqueta`, alarmas `CHAQUETA_FRIA` /
  `CHAQUETA_SOBRECALENTADA` igual que hoy, sigue bloqueando el avance del
  step 2 hasta estar en banda).
- El `elif self.step == 2:` del secuenciador usa el resultado de esa llamada
  (ya hecha al inicio de `ejecutor()`) para decidir si avanza a `step = 3`.

Efecto: si no hay vapor, el step 2 se salta de inmediato (avanza a
igualar presión de cámara, drenar, etc.), y la función de chaqueta sigue
intentando en segundo plano en cada tick — apenas vuelve el vapor, empieza a
acondicionar la chaqueta sin que el operador tenga que hacer nada ni
reiniciar PREPARACION.

### 3. `preparado.py` — `mantener_chaqueta()` no bloquea `esta_preparado()` por falta de vapor

En `mantener_chaqueta()` (líneas 86-118): cuando `vapor_suministro` es falso,
en vez de retornar `False` (que hoy bloquea `esta_preparado()` vía la cadena
`and` en línea 204), retorna `True` — válvula cerrada, alarma
`SUMINISTRO_VAPOR` informativa (`blocks_operation=False`). Si hay vapor pero
la presión está fuera de banda, el comportamiento **no cambia**: sigue
retornando `False` y bloqueando `esta_preparado()` (la chaqueta debe llegar a
su punto antes de permitir iniciar ciclo, cuando sí hay vapor disponible).

Efecto: con puertas cerradas, cámara igualada y drenaje OK, el equipo llega a
`LISTO_PARA_CICLO` aunque falte vapor — la chaqueta queda pendiente y se
retoma sola cuando vuelva el suministro (misma función, corre cada tick).

### 4. `ciclo.py` — alarma informativa durante el ciclo (sin cambio de lógica)

En `_mantener_chaqueta()` (líneas 143-146), agregar el mismo tipo de alarma
informativa no bloqueante (`SUMINISTRO_VAPOR`, `blocks_operation=False`)
cuando falta vapor, y `alarm_manager.clear("SUMINISTRO_VAPOR")` cuando vuelve.
No se toca el flujo de control: la válvula se sigue cerrando, el ciclo sigue
corriendo, y si la falta de vapor se prolonga lo suficiente, la fase activa
(`calentamiento`, `precalentamiento`, etc.) fallará por su propio timeout
existente — comportamiento ya presente hoy, sin cambios.

`CicloState` ya recibe `alarm_manager` en su constructor
(`ciclo.py:57,62`) y lo usa en otros puntos para reportar alarmas de fallo,
así que no requiere cambios de wiring.

## Fuera de alcance

- No se modifica el manejo de `agua_bomba`, `agua_generador`,
  `aire_comprimido` ni `suministro_electrico` — siguen siendo bloqueantes
  duros exactamente como hoy.
- No se agrega timeout nuevo a PREPARACION/PREPARADO — si falta vapor de
  forma indefinida, el equipo se queda en PREPARACION/PREPARADO con la
  chaqueta pendiente (o en CICLO hasta que una fase falle por su timeout
  propio), tal como describe el comportamiento pedido. No hay requisito de
  escalar a FALLA por vapor ausente fuera de un ciclo.
- No se introduce un flag nuevo en `EstadoAutoclave` (tipo
  `CHAQUETA_PENDIENTE`) — la alarma `SUMINISTRO_VAPOR` con
  `blocks_operation=False` ya es visible para el operador (aparece en
  `Alarmas_activas`) y es suficiente para este alcance. Si más adelante se
  quiere una bandera dedicada para la UI, es una extensión posterior.

## Pruebas

Tests existentes a revisar/actualizar:
`tests/test_ciclo_suministro.py`, `tests/test_preparado_suministro.py`,
`tests/test_ciclo_sensores.py`, `tests/test_preparacion_alarm_wording.py`.

Casos nuevos a cubrir:

- PREPARACION: sin `vapor_suministro`, el step avanza más allá de 2 (no se
  resetea a 0), y se reporta `SUMINISTRO_VAPOR` con `blocks_operation=False`.
- PREPARACION: vapor vuelve estando ya en step 4/5 → la válvula de chaqueta
  se activa/desactiva según banda sin necesidad de retroceder el step.
- PREPARACION: falta de `agua_bomba`/`agua_generador`/`aire_comprimido` sigue
  reseteando `self.step` a 0 (comportamiento no debe cambiar).
- PREPARADO: sin `vapor_suministro`, `esta_preparado()` puede retornar `True`
  si el resto de condiciones se cumplen (puertas, cámara, drenaje).
- PREPARADO: con vapor presente pero fuera de banda, `esta_preparado()` sigue
  retornando `False` (sin cambios).
- CICLO: sin `vapor_suministro`, se reporta la alarma informativa y se limpia
  al volver; el ciclo no falla ni se cancela por esto solo (ya cubierto por
  `test_ciclo_suministro.py`, extender para la alarma).
