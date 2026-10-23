# S11 — SEN-03 según los sensores en uso (tanda 11, D11-3)

Rama: `tanda-11-s11` (parte de `tanda-11`, 1b3ec0d). Commit de código: `1331a63`.

## Qué se hizo, por punto de D11-3

1. **Solo sensores en uso, unión de los programas.** En `sensores_ciclo.py` se agregaron tres funciones nuevas (no se reescribió ninguna existente; `vigilar_fuera_de_ciclo` queda igual y se reutiliza):
   - `sensores_vigilados_fuera_de_ciclo(programas)`: unión de Principal + Referencias (`sensores_en_uso`) de los programas.
   - `programas_para_sen03(programas_seguridad, cycle)`: la lista `programas_seguridad()` (la misma que ya usa PREPARACION para drenaje/venteo de líquidos, y PREPARADO para cámara segura); sin proveedor, `[cycle]`.
   - `vigilar_en_uso_fuera_de_ciclo(alarm_manager, profile, estado, programas)`: llama a `vigilar_fuera_de_ciclo` para los sensores vigilados y resuelve SEN-03 de los demás.
   - `preparacion.py` y `preparado.py` (`verificar_sensores`) llaman a esta función una vez por tick, en lugar de llamar a `vigilar_fuera_de_ciclo` sensor por sensor.
2. **"No en uso" en todos los programas:** se llama `resolver(SEN_03, origen=<nombre legible>)` en cada tick (no hace nada si no estaba activa) y el sensor no se vigila.
3. **Vuelve a evaluarse en el siguiente tick:** la lista se pide en cada tick, sin caché. `verificar_inicio` (RS-06) no se tocó.
4. **Sin programa:** si la lista queda vacía (o solo trae `None`), se usa `sensores_en_uso(None)` = asignación de fábrica (Principal = Cámara 1). El "último ciclo ejecutado" ya está dentro de `programas_seguridad()` (`_programa_ultimo_ciclo` mientras cuente para la seguridad), y en el `ControlLoop` siempre hay un programa seleccionado (`cycle_manager.get_selected_cycle()` lanza una excepción si no hay ninguno).
5. `temp_drenaje` y los transductores de presión no cambian: siguen con su código y su alarma (SEN-01 / SEN-06/07).

## Decisiones sin confirmar

- **DECISIÓN SIN CONFIRMAR — "dos pantallas":** el backend tiene una sola selección de programa (`cycle_manager.selected_cycle`), que comparten las dos pantallas. Por eso la "unión de los programas de ambas" es la lista `programas_seguridad()`: el seleccionado, más el del último ciclo mientras la cámara no haya quedado segura, la copia del estado seguro y la del ciclo en recuperación. Así se vigila **de más** mientras esas copias sigan contando, lo cual es lo más seguro. La prueba "2 pantallas" simula esa lista con dos programas.
- **DECISIÓN SIN CONFIRMAR — falla segura:** si `programas_seguridad()` lanza una excepción, se vigilan los tres sensores (es el comportamiento de antes de S11) y queda en el log.
- **DECISIÓN SIN CONFIRMAR — asignación inválida:** con un programa de roles inválidos, `sensor_principal` devuelve Cámara 1 y ninguna Referencia. Para SEN-03 se vigila además todo sensor que esa asignación marque como principal o referencia, para no esconder una sonda caída. Ese programa no puede iniciar de todos modos: `verificar_inicio` lo bloquea.
- Un sensor en uso pero no declarado por la instalación sigue sin vigilarse y sin resolverse, igual que antes (`vigilar_fuera_de_ciclo` sin cambios).

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a9c4c9b4d52f681b7\src\autoclave\__init__.py`

Nueva: `tests/test_s11_sen03_sensores_en_uso.py` (25 casos, PREPARACION y PREPARADO con un `AlarmManager` real):
- un sensor "No en uso" desconectado no da SEN-03 (Cámara 2 y Referencia);
- al pasar a un programa que lo usa aparece en el siguiente tick, y al volver se resuelve;
- un Principal que pasa a "No en uso" en todos los programas tampoco se vigila;
- con 2 programas (las 2 pantallas) se vigila la unión de ambos;
- sin programas, regla de fábrica; si el proveedor falla, se vigilan todos; sin proveedor, el programa del estado;
- SEN-03 sigue sin bloquear;
- `verificar_inicio` sigue bloqueando el programa que usa la sonda caída y deja pasar el que no la usa.

Ajustada: `tests/test_t3_sensores_ciclo.py::test_sensor_del_ciclo_sin_lectura_alerta_sin_bloquear`. Esperaba SEN-03 de Cámara 2 y Referencia con la asignación de fábrica, que es justo lo que D11-3 cambia. Ahora el programa de la prueba usa los tres sensores.

Resultados:
- Las dos pruebas anteriores: **104 passed in 10.20s**.
- Las pruebas de los módulos que importan `sensores_ciclo`, `preparacion`, `preparado`, `StateMachine` o `control_loop` (107 archivos, `-n auto`), antes del ajuste: **12 failed, 2322 passed, 4 skipped in 220.27s**. Los 12 fallos eran todos de la prueba ajustada; tras el ajuste esa prueba pasa (incluida en las 104 de arriba).

## Preguntas para Cristian

- ¿La "unión de las dos pantallas" debe incluir también el programa del último ciclo mientras la cámara no sea segura, como hace hoy `programas_seguridad()`? Se dejó así porque D11-3.1 dice "la misma lista `programas()` que ya usa PREPARACION".

## Pendientes / coordinación

- O11 tocará `sensores_ciclo.py`. Lo de S11 está en un bloque al final del archivo, antes de `canonica` (`# ── S11 (tanda 11, D11-3) ...`), con funciones nuevas.
- No se tocaron i18n, QML, `app.py`, `server.py` ni `doble_pantalla.py`.
