# B5 — Aviso de impresora desconectada al arrancar

## Hallazgos previos
- **No existía la bandera "impresora habilitada"** (ni en el perfil, ni en `global_params`, ni en `impresion_menu.py`/`context.py`). **Hoy la impresión no tiene modo "deshabilitada"**: el backend siempre encola e imprime (una impresión fallida solo se registra). No se suponía nada: se creó la bandera con valor por defecto **habilitada** (comportamiento actual).
- Ya existía `win32_printer.estado_impresora()` (lista / no_instalada / desconectada / sin_papel / error), usada para avisar antes de reimprimir tickets. No se tocó; se añadió `conexion_impresora()` con el vocabulario pedido.

## Hecho
- `devices/printer/win32_printer.py`: `conexion_impresora()` → `conectada` / `desconectada` / `desconocida`. Enumera impresoras (`EnumPrinters`) y lee atributos de la cola (`GetPrinter`); no imprime ni gasta papel. Ausente de la lista o cola sin conexión → desconectada; sin papel/error → conectada (está presente); sin `win32print`, error del spooler o al abrir/consultar → desconocida. También `registrar_observador_exito()` (se invoca cuando `print_raw`/`print_startup` imprimen bien).
- `core/runtime/vigilancia_impresora.py`: `ConfigImpresora` (`data/impresora.json`, `{"habilitada": bool}`; ausente/ilegible/inválido → habilitada) y `VigilanciaImpresora`: al arrancar (llamada desde `BackendContext` tras `iniciar_vigilancia_mantenimiento`, con el backend operable) lanza un hilo que consulta con **plazo de 5 s**; no responde a tiempo, error o desconocida → NO hay aviso, y `iniciar()` vuelve de inmediato (no retrasa el arranque). Deshabilitada → no consulta ni avisa. Desconectada → activa **SIS-05 `IMPRESORA_DESCONECTADA`**; se limpia sola cuando una impresión tiene éxito o al reiniciar con la impresora presente (la alarma vive en memoria).
- Catálogo: **SIS-05 "Impresora no conectada"**, AVISO (nivel de baja prioridad), `bloquea_inicio=False`, despeje automático; texto es/en en `alarmas.SIS-05` (i18n) y fila en `docs/catalogo_alarmas.md`.
- Visibilidad: al ser un AVISO del `AlarmManager` entra en `/status.alarms` con nivel `ALERTA`, que es lo que ya muestran la tarjeta de alarmas y avisos de Preciclo y el grupo "Avisos" del panel de la campana (`PanelNotificaciones`); NO va en la barra superior (no se tocó QML).
- API: `GET /printer/config` (abierto, solo lectura) y `PUT /printer/config` (técnico/ingeniero, audita `impresora_configurada`).

## Pruebas (`tests/test_b5_aviso_impresora.py`, 26)
conexión (conectada, sin papel, ausente, cola offline ×3, no consultable ×3, sin win32print); bandera; habilitada+conectada (sin aviso); habilitada+desconectada (aviso en `/status` como ALERTA, no bloquea); sin duplicar; deshabilitada (no consulta); desconocida; consulta lenta (no avisa ni retrasa); consulta con error; `iniciar` no bloquea; impresión exitosa limpia el aviso y una fallida no; el cierre del ciclo (`RealtimePrinter.enqueue`) degrada sin bloquear; el servicio no referencia el control del ciclo; permisos y auditoría del PUT.

## PENDIENTES / DECISIONES SIN CONFIRMAR
1. **No hay pantalla** para cambiar `impresora.habilitada`: "Parámetros del equipo" aún no existe en QML (OPCIONES muestra "Próximamente"); queda editable por API (técnico/ingeniero, auditada). PENDIENTE: control en esa pantalla cuando se construya.
2. **No se añadió al asistente de instalación** (el perfil está bloqueado y el asistente no tiene el campo; añadirlo exige tocar perfil, validación y QML). PENDIENTE; mientras tanto el valor por defecto (habilitada) coincide con el comportamiento actual de los equipos instalados.
3. La bandera solo gobierna la verificación y el aviso; no desactiva la impresión (hoy no hay modo deshabilitado). Alternativa: que deshabilitada también suprima los intentos de impresión.
4. `desconocida` (no se pudo consultar) no avisa, por instrucción.

## Revisión
Por orden de Cristian (20-oct) no se ejecutó el agente `safety-reviewer` en esta sesión. Comprobación propia: nada del módulo importa ni llama al `ControlLoop`; el aviso es AVISO sin bloqueo; toda excepción se contiene en el hilo de verificación; revisar aparte.
