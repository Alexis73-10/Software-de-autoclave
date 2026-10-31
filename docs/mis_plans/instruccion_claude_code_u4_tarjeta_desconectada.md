# Instrucción para Claude Code — Etapa U4 (19-oct-2026): tarjeta desconectada vs. paro de emergencia, alarmas sin bloqueo

Se inserta en la tanda 2 ANTES de S3 (S3a sin commitear: termínala y commitéala primero, o déjala en stash con nota en `estado.md`). Aplican las reglas generales de `instruccion_claude_code_tanda_2.md` §0 (informes en español, pruebas primero, sin `git add -A`, sin push, `time.monotonic()`, textos i18n es/en, revisores `safety-reviewer` y `timing-auditor` obligatorios). Informe: `docs/informes/tanda2/U4_tarjeta_desconectada.md`; actualiza `estado.md`.

## Problema (observado por Cristian con la tarjeta desconectada)
1. La UI dice "Paro de emergencia activado" y queda bloqueada, aunque el botón no está pulsado.
2. El panel de la campana se abre solo y no se puede cerrar (`PanelNotificaciones.qml`: `bloqueado: seguridad.urgente`, `onBloqueadoChanged: abrir()`), bloqueando la UI.
3. El paro no aparece clasificado dentro de la lista desplegable (las filas de `SeccionEstadoSeguro` están fuera de "Alertas y avisos" y no cuentan en su contador).
4. Aparece "No llegan datos válidos de la tarjeta de control" (COM-01) / "La tarjeta de E/S no envía datos válidos" (`TARJETA_SIN_TRAMA_VALIDA`) cuando la tarjeta simplemente no está conectada.

Causa raíz: `control_loop.py` (~L485) hace `paro_emergencia.update(None)` sin enlace; `EmergencyStop` trata `None` como paro (D-16/A-3). Un solo flag `PARO_EMERGENCIA` mezcla "botón pulsado" y "sin datos". Las dos causas deben distinguirse.

## Decisiones de Cristian (19-oct) — fuente de verdad
- D1. Se distingue tarjeta desconectada de datos inválidos y de paro real. El botón "Confirmar y llevar a estado seguro" va DENTRO de la tarjeta de alarmas de Preciclo (además de seguir en el panel si el diseño lo conserva).
- D2. Al reconectar la tarjeta fuera de ciclo NO se exige confirmación de estado seguro si nunca hubo un paro real (DI vigente leyendo 0). Solo un paro real exige confirmación.
- D3. El panel agrupa por nivel del catálogo (emergencia/fallas, alarmas, avisos); el paro queda dentro de su grupo y cuenta en el contador.
- El panel de la campana NO se abre solo ni es no cerrable. Las alarmas y el paro se ven en la tarjeta de alarmas de Preciclo (y de Ciclo en curso) y en la insignia roja parpadeante de la campana.

## Requisitos
**A. Estado de la tarjeta (backend).** Publica un estado `tarjeta` con tres valores: `desconectada` (`_scan_ports()` sin puerto, o puerto cerrado/perdido), `sin_tramas_validas` (puerto abierto, sin trama con CRC válido, versión incompatible, handshake fallido, DI vencida con enlace) y `ok`. Exponlo en `/status` y en `UiBridge` (propiedad para QML). Falla cerrada: sin dato = `desconectada`.

**B. Seguridad intacta.** Con tarjeta desconectada o sin datos el equipo sigue en estado seguro: salidas apagadas, sin inicio de ciclo, sin apertura permitida, `NO ABRIR` activo. NO cambies la lógica que apaga salidas ni D-16/A-3 para la máquina de estados; solo separa la CAUSA publicada: `paro_real` = enlace conectado + DI vigente + entrada = 0. La máquina de estados puede seguir usando el flag combinado para bloquear, pero la alarma SIS-01, la fila "PARO DE EMERGENCIA" y el requisito de confirmación de estado seguro dependen solo de `paro_real`. Cuida el arranque: la DI inicial en 0 antes de la primera trama NO es paro real.

**C. Alarmas y textos (catálogo + i18n es/en).**
- COM-01: "Tarjeta de E/S desconectada" / "No se detecta la tarjeta de control." / acción: "Conecte la tarjeta (cable USB) y verifique su alimentación." Solo para `desconectada`.
- `TARJETA_SIN_TRAMA_VALIDA`: conserva "no envía datos válidos", solo con puerto abierto.
- SIS-01: solo con `paro_real`.
- Revisa que COM-01 y `TARJETA_SIN_TRAMA_VALIDA` no se activen a la vez por la misma causa; al pasar de una a otra, resuelve la anterior.
- Aviso `sistema.seguridad_desconocida` (fila SIN_CONEXION): reescríbelo para decir "Tarjeta desconectada: no se puede verificar el paro ni la cámara", sin afirmar paro.

**D. Estado seguro y reconexión.** Un paro solo por falta de datos no marca "requiere confirmación". Un paro real sí (flujo actual). Si la tarjeta se perdió DURANTE un ciclo, conserva COM-02/COM-03 y el protocolo de fallo actual sin cambios; al reconectar, lo que ya exigía hoy ese camino se mantiene. Documenta la tabla de casos (desconexión fuera de ciclo / en ciclo / paro real / paro real + desconexión / arranque sin tarjeta) con el resultado esperado de cada uno.

**E. UI.**
- Quita `bloqueado` y la apertura automática de `PanelNotificaciones.qml` (y su uso de `urgente`); el panel se abre solo con la campana y se cierra con normalidad.
- La tarjeta de alarmas de Preciclo (`zonaAlarmas`) y la de Ciclo en curso muestran, arriba y en prioridad alta: tarjeta desconectada / sin datos, paro real, estado seguro pendiente (con el botón "Confirmar y llevar a estado seguro" inline, sin sesión), estado seguro en curso, NO ABRIR y modo prueba; debajo, el modelo de alarmas. Reutiliza `FilaAlarma` y la lógica de `SeccionEstadoSeguro` (extrae el componente compartido en vez de duplicar).
- El texto "sin conexión" actual de `avisoSinConexion` debe decir "tarjeta desconectada" cuando corresponda.
- Insignia de la campana: roja y parpadeante con paro real o confirmación pendiente; roja fija con tarjeta desconectada.
- Panel: agrupa por nivel (D3), con cabecera y contador por grupo; el paro y el estado seguro dentro de "Emergencia/Fallas".
- Nada de lo anterior debe bloquear la navegación ni los iconos de la barra inferior.

**F. Pruebas.** Estado de la tarjeta en cada caso (puerto ausente, puerto abierto sin tramas, CRC malo, firmware incompatible, DI vencida, ok); no hay SIS-01 con tarjeta desconectada; sí lo hay con DI vigente = 0; COM-01 y `TARJETA_SIN_TRAMA_VALIDA` excluyentes; reconexión sin paro real no pide confirmación; con paro real sí; la DI inicial en 0 al conectar no cuenta como paro; las salidas siguen apagadas en todos los casos; controlador/QML: el panel no se abre solo ni queda bloqueado, el botón de confirmación inline funciona, los grupos cuentan bien. Suite completa en verde.

## Fuera de alcance
Firmware, protocolo serial (formato de tramas), módulos M31-U, cambios al flujo de estado seguro aparte de la condición `paro_real`.
