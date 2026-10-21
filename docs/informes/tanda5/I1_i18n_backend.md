# I1 — i18n F2: backend y datos ★

## Hecho
- **Alarmas por código y parámetros.** Las 49 alarmas del catálogo tienen entrada en `es.json` y `en.json` bajo `alarmas.<codigo>.{titulo, plantilla, accion}`. La plantilla usa formato de Python (`{pres:.0f}`) y tiene los mismos campos que la del catálogo de seguridad (lo comprueba una prueba, en los dos idiomas).
  - `core/runtime/alarmas_i18n.py` arma los textos por idioma. Si falta un texto, usa el español del catálogo, así que una alarma nunca queda sin texto y los registros históricos se siguen mostrando.
  - `GET /status` publica en cada alarma `valores` (parámetros serializables) y `textos` (`{"es": {...}, "en": {...}}`). `description` sigue en español, por compatibilidad.
  - El nivel, el bloqueo, el despeje y la descripción registrada no cambian: siguen saliendo de `state_machine/alarms/catalogo.py`.
- **Parámetro `idioma`.** Se guarda en `data/idioma.json` (`core/runtime/config_idioma.py`; si no existe, español).
  - `GET /language` lo devuelve. `PUT /language` lo cambia: cualquier rol con sesión, permitido también en ciclo, con auditoría `idioma_configurado`.
  - **R-06 se mantiene:** no se agregó ningún selector de idioma para el operador.
- Textos en inglés nuevos: "sin revisar" (revisión de traducciones, F5).

## PENDIENTE (no hecho en esta tanda)
- **Motivos de puerta con código + parámetros.** Hoy el rechazo ya viaja como `RechazoApi` con código (`puerta_rechazada`, `puerta_ajena`, `modo_prueba_activo`, `sin_conexion_tarjeta`…), pero el motivo detallado de `ServicioPuertas` sigue siendo texto en español. Pasarlo a código toca la lógica de puertas (seguridad) y se deja para una etapa propia.
- **`motivo_fallo` como código + parámetros.** El código ya existe (`codigo_fallo`, en la BD y el ticket). Faltan los parámetros (columna o JSON en la BD), para renderizar el ticket en inglés.
- **`nombre_clave` en los ciclos de fábrica.** No se hizo: `cycles/factory/bowe_dick.json` tiene cambios sin commit de otra sesión (árbol compartido).
- **Etiquetas de roles y enums por catálogo** y **unificación de familias de códigos** (COM-03 frente a TARJETA_*): no se hicieron.
- `audit_log.detalle` ya se guarda como JSON (dict). No se reestructuró.
- `sensor-role-auditor` no se ejecutó: I1 no toca sensores.

## Revisión (safety-reviewer, con una mirada de temporización)
Sin Críticos ni Altos. El nivel, el bloqueo, el despeje y la descripción registrada no cambian. Las acciones de seguridad conservan su sentido en inglés ("Do not open the door", "The load is NOT sterile", el paro).
- **Medio M-1:** un catálogo de idioma ilegible tumbaba `/status`. **Corregido:** `textos` atrapa el error y usa el español.
- **Medio M-2:** un NaN o un inf en los parámetros rompía la serialización JSON. **Corregido:** se publican como `null`.
- **Bajo B-1:** el log de una plantilla rota se repetía en cada petición. **Corregido:** se registra una sola vez.
- **Bajo B-2:** una definición ausente hacía lanzar a `por_idioma`. **Corregido:** devuelve `{}`.
- **Bajo B-3:** `GET /language` va sin sesión. **DECISIÓN SIN CONFIRMAR I1-1:** se deja así porque la pantalla de login y la de espera lo necesitan. `PUT` no cambia el idioma en vivo, solo lo guarda; la UI lo aplica al leerlo (I2).
- Temporización: es despreciable (microsegundos por alarma, sin E/S después de la primera carga, sin locks compartidos con el ControlLoop).

## Pruebas
`tests/test_i1_i18n_backend.py` (157): cada código en es y en con sus parámetros, renderizado en los dos idiomas, respaldo sin valores, DTO de `/status`, registro histórico sin entrada, idioma (configuración, permisos por rol, en ciclo, 401/422).
