# B3 — Mantenimiento: valores definitivos y robustez

## Hecho
- **Valores definitivos (aprobados por Cristian el 2026-10-20): 365 días y 1000 ciclos** (`core/runtime/mantenimiento.py`: `INTERVALO_DIAS_DEFECTO`, `INTERVALO_CICLOS_DEFECTO`). Se quitaron las notas "provisional / DECISIÓN SIN CONFIRMAR" del código, de la pantalla y del docstring del endpoint. (No existe otro "catálogo" con estos valores: solo `data/mantenimiento.json` y esas constantes.)
- **Primer vencimiento** = `installed_at` + 365 días, o 1000 ciclos contados desde la instalación (contador actual − contador al instalar), lo que ocurra primero. El contador al instalar se fija una sola vez en `data/mantenimiento_base.json` (`ciclos_instalacion`; 0 en un equipo nuevo). Tras `registrar`, la base pasa a la fecha y al contador de ese momento.
- **Migración** (`migrar_valores_provisionales`, se ejecuta al arrancar la vigilancia): si `data/mantenimiento.json` está en 180 / 0 y la bitácora no tiene `mantenimiento_configurado` ni `mantenimiento_migrado`, pasa a 365 / 1000 y audita `mantenimiento_migrado` (usuario `sistema`). Si alguien lo editó por la API → no se toca. Sin archivo → ya rige el defecto nuevo. Sin base de datos (no se puede comprobar la auditoría) → no se toca. Se ejecuta una sola vez.
- **M1-01 (reloj):** además del reloj anterior a la instalación / al último mantenimiento (ya existía), ahora se detecta un reloj de pared ADELANTADO: si la pared avanzó más de 1 día respecto del tiempo monotónico desde que arrancó el proceso (ajuste manual hacia adelante), el estado es `sin_dato` ("—" en las tarjetas), no se activa el aviso de vencido y `POST /maintenance/records` se rechaza con 409 `reloj_adelantado` (el atrasado sigue siendo `reloj_invalido`). Al corregir el reloj se recupera solo. Limitación aceptada: tras un reinicio con el reloj ya adelantado no hay referencia independiente para detectarlo.
- **Pantalla de intervalos** en OPCIONES › Mantenimiento: dos campos (por fecha, en días; por ciclos; 0 = no aplica) con el teclado numérico (`teclado.abrirNumerico`), botón "Guardar intervalos" solo si hay cambios, solo con `edicionPermitida` (técnico/ingeniero, estado distinto de CICLO), límites 0–3650 días y 0–1 000 000 ciclos; el backend valida otra vez, exige técnico/ingeniero y audita `mantenimiento_configurado`. Rechazos con su motivo (rol, sesión, estado, validación, sin respuesta).
- i18n es/en nuevas (`opciones.mant_*`).

## Pruebas
`tests/test_b3_mantenimiento.py` (27: defecto, vence por fecha / ciclos / lo primero, ciclos desde la instalación, base tras registrar, migración en 5 casos, reloj atrasado / adelantado / corregido / deriva tolerada, endpoint 409, permisos) y `tests/test_b3_mantenimiento_ui.py` (15). Se actualizó `test_m1_mantenimiento_backend.py` a 365 / 1000.

## DECISIONES SIN CONFIRMAR
1. Equipos ya instalados con ciclos previos: el "contador al instalar" es el valor que tenga el contador la primera vez que se evalúa con esta versión (los ciclos anteriores no cuentan para el vencimiento). Alternativa: contar desde 0 (vencería de inmediato un equipo con >1000 ciclos).
2. Umbral de reloj adelantado: 1 día de deriva entre pared y monotónico. Alternativa: otra tolerancia.
3. La migración compara contra auditoría de la base: un archivo editado a mano a 180/0 sin auditoría se migra.

## Revisor (safety-reviewer): sin Críticos ni Altos; no bloquea ciclos
Confirmado: `MANTENIMIENTO_VENCIDO` es AVISO con `bloquea_inicio=False`; nada corre en el hilo del ControlLoop; todo el servicio contiene sus excepciones; permisos técnico/ingeniero con auditoría.
- SAF-M1 (Medio): la referencia pared/monotónico se fija al arrancar; una corrección legítima HACIA ADELANTE de más de 1 día (RTC desfasado) deja el estado "adelantado" hasta reiniciar. Mitigado: el mensaje `mant_err_reloj_adelantado` ahora dice "corrija la fecha y hora y reinicie el programa". Corregir hacia atrás se recupera solo.
- SAF-M2/M3 (Medio): la auditoría de éxito se escribe después de la acción y `_auditar` no propaga errores (patrón del resto del backend); si la base falla justo entonces, un 180/0 fijado a propósito podría migrarse en el siguiente arranque. Aceptado (poco probable, solo afecta un aviso informativo).
- Bajos: edición manual del archivo a 180/0 se migra (documentado); umbral 1 día; `time.monotonic` y suspensión (no aplica en Windows); base de ciclos errónea si el contador se lee 0 transitoriamente; `OSError`/SQLite en PUT/POST salen como 500.
- Por orden de Cristian (20-oct) NO se ejecutan más revisiones con agentes `safety-reviewer`/`timing-auditor` en esta sesión: las etapas B5, B7, B8 y B9a quedan SIN revisión de agentes y deben revisarse aparte.
