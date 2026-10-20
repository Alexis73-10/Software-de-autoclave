# B1 — Secado PySide guarda por la ruta vigente (SAF-04 de C1)

**Problema:** `ui_pyside/views/secado.py` hacía `PATCH /cycle/parameters` (ruta inexistente → 404 siempre).

**Cambio:** la vista guarda cada campo modificado por `PATCH /cycle/parameter` (`{cycle_id, fase:"secado", path:[campo], value}`) con el token de la sesión PySide (cliente con token de C1). Solo se envían los campos que cambiaron respecto a lo cargado (menos entradas de auditoría); los de pulso (`presion_baja/alta_secado`) solo con modo 3. Resultado:
- 200 → "Guardado"; sin cambios → "Sin cambios" (no llama al backend).
- 409/422/503 → "Error al guardar" con el `detail` del servidor por campo; nunca "éxito" ni "sin conexión".
- 401/403 → "Sin permiso" (sesión vencida o rol insuficiente).
- Backend caído → "Sin conexión". Si `_load_current` no pudo leer el programa, no guarda.

**Barrido de rutas:** la única discrepancia en `ui_pyside/` y `ui/service_ui/` era `/cycle/parameters`. Las demás (`/cycle/parameter`, `/io/test/*`, `/calibration/*`, `/auth/*`, `/status`, `/cycle`, `/cycles`, `/cycle/select`, `/cycle/start|abort|acknowledge`, `/system/shutdown`, `/cycle/current/readings`) existen. Prueba permanente `test_barrido_toda_ruta_http_de_ui_pyside_existe_en_el_backend`.

**Nota:** el secado también se edita en OPCIONES › Parámetros del ciclo (QML, sección `secado`). La vista PySide "Secado" (tarjeta en `home.py`) probablemente sobra, pero NO se retira (instrucción). Nota: `home.py` la ofrece como "Ajusta el tiempo de secado del ciclo activo".

**Pruebas:** `tests/test_b1_secado_pyside.py` (10): válido, sin cambios, fuera de rango, 409, 401/403, backend caído, sin programa cargado, ruta inexistente retirada, barrido. Suite: 3803 pasan, 1 omitida (línea base 3793).

**Decisiones sin confirmar:** ninguna.
