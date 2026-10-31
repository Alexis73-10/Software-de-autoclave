# Adenda a E0/E1 — correcciones tras la revisión (safety-reviewer y timing-auditor)

Base: sección 7 de `docs/informes/informe_e0_e1.md` y `instruccion_claude_code_e0_e1.md` (mismas reglas: informes en español, sin commit, pruebas primero, línea base `python -m pytest -q -p no:cacheprovider` = 2440, sin hardware, sin cambiar ids de alarma, `time.monotonic`, no tocar cambios ajenos).
Decisiones de Cristian (2026-10-12): corregir ahora SAF-01, TMG-02, TMG-01, SAF-02 y los menores baratos; TMG-05 entra; TMG-04 y TMG-03 van a E3.

## Datos del equipo (confirmados por Cristian)
- Sondas de temperatura cableadas: **cámara 1, cámara 2, referencia y drenaje**. Ninguna otra.
- Agua de la bomba de vacío: protección solo por hardware (flotador en la bobina del contactor); no hay DI para el software.
- Los programas del 19-oct **usan prevacío y SECADO modo 1/2**.
- Hay válvulas de alivio mecánicas en chaqueta y cámara.

## Correcciones

**A-1 (SAF-01)** `VacuumPump.puede_activar()` (`devices/pump/pump.py:21`) respeta `supply_inputs`: con `agua_bomba` en False no exige el DI. Pruebas: bomba arranca con `agua_bomba` False y DI en 0; con True y DI en 0 no arranca (comportamiento actual).
Además, **solo reporta** (no cambies aún): qué hace SECADO modo 1/2 hoy si el vacío no se alcanza o la bomba no opera (¿timeout → COMPLETADO?). Cita archivo y línea. La corrección va a E3.

**A-2 (TMG-02, SAF-04)** Dos partes.
1. Canales vigilados por perfil: los que no están instalados no se vigilan ni bloquean. Primero busca si ya existe una configuración por equipo de sensores instalados (revisa `docs/informes/inventario_sensores_y_base_de_datos.md` y el código de sensores) y **reutilízala**. Si no existe, campo `temperature_probes` en el perfil con el mismo patrón que `supply_inputs` (por defecto todas presentes = fail-closed; valida; asistente; `tools/` análogo). Mapea los cuatro nombres de arriba a los canales reales; **si algún nombre no corresponde sin duda a un canal (por ejemplo `temp_drenaje` frente a `temp_drenaje_cam`), no supongas: pregúntalo en el informe antes de declarar el procedimiento.**
2. Si una sonda vigilada tiene lectura inválida y `supervisor()` falla, `ejecutor()` no puede dejar las salidas congeladas: llevar a OFF las salidas que aportan energía (vapor de chaqueta y de cámara) y aplicar A-4 a las que evacuan o enfrían. Deja que sigan los lazos que no dependen del sensor caído.

**A-3 (TMG-01, SAF-06)** "Sin datos de las entradas = paro":
- Sello monotónico de la última trama `DI:` en el enlace; vence a **1,5 s** (tres periodos de 500 ms) → `EmergencyStop.update(None)` = paro.
- `_connect()` pone `di` en 0 (con la lógica invertida, 0 = paro) y el paro se publica también mientras el enlace está desconectado.
- No cambies la estructura de `ControlLoop.run()`. E6 reutilizará el sello.

**A-4 (SAF-02)** Con `temp_drenaje` sin lectura válida, **forzar `agua_intercambiador_on()`** en PREPARACION, PREPARADO **y CICLO** (`_mantener_drenaje`). Esto reemplaza lo pedido en E0-2; deja una nota en el informe. Actualiza las pruebas de E0-2 que fijaban "no hace nada".

**A-5 (SAF-03)** `pres_chaqueta` sin dato → `vapor_chaqueta_off()` y alarma `ERROR_AI_PRES_*` también con `None` (hay válvula de alivio mecánica, pero no se confía solo en ella).

**A-6 (SAF-05, SAF-07)** `tools/declarar_entradas_suministro.py`: rechaza `--cableadas` vacío salvo con flag explícito, pide confirmación y registra el cambio (auditoría). Aviso si llega `puerta_2_cerrada`=1 con `door_count=1`.

**A-7 (TMG-09)** Con el paro activo, `ALL_OFF` como máximo una vez por segundo o mientras el último `DO:` reportado tenga una salida activa (nunca esperar el ACK bajo el lock del lazo más de lo necesario). El buzzer pasa a `time.monotonic()`.

**A-8 (TMG-05)** `/io/test/enter` y `/io/test/output` rechazan si el enlace con la tarjeta está caído o los datos son viejos. Usa el código de rechazo existente de mayor afinidad y repórtalo.

**A-9 (TMG-11)** CICLO usa `lectura_valida` en vez de `is None`; el suministro eléctrico no usa `get(..., 1)` como valor por defecto.

## No incluir
TMG-04, TMG-03 (E3), TMG-06, TMG-07, TMG-10 (deuda anotada), corrección de SECADO sin vacío real (E3).

## Entregable
Actualiza `docs/informes/informe_e0_e1.md` con una sección "8. Adenda": archivos cambiados, conteos antes/después, la respuesta de A-1 sobre SECADO, el mapeo de sondas, y preguntas abiertas. Sin commit.
