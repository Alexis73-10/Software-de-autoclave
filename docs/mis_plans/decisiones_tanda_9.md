# Decisiones para la tanda 9 (aprobadas, 22-oct-2026 23:30)

Fuente: hallazgos de Cristian tras instalar la compilación B en el equipo de pruebas **sin sensores conectados** (22-oct), evaluados contra la rama `tanda-8`. La tanda 8 NO se instala; la tanda 9 parte de `tanda-8` unida a `dev`. Las respuestas de Cristian (23:26) están al final (§Q) y ya están incorporadas en cada punto.

Ya resueltos en `tanda-8`, solo se verifican en banco (agregar a la hoja de banco): H4 presión ausente muestra "—" (S1, D8-1.1); H13 motivo del modo no válido con líquido (D8-5.7/5.8); H16 E/S solo con los canales del perfil (D8-3.17).

## Causa común de H1, H2, H5, H6 y H8
En cada arranque (`context.py` → `recuperar_ciclo_interrumpido`, decisión E4/D-08) la cámara se evalúa con el primer dato vigente. Sin presión de cámara la cámara cuenta como no segura → `ProtocoloEstadoSeguro.iniciar(..., requiere_confirmacion=True)` con el texto "El paro de emergencia se liberó" aunque nunca se pulsó. Tras confirmar, el protocolo nunca termina (sin presión no hay 3 ticks seguros) y bloquea modo prueba (`enter_test_mode`, SAF-03 de T6), cambio de programa (`select_cycle` + `motivoNoTocable`) y apagado (`_estado_seguro_en_marcha` en `/system/shutdown`). `Main.qml` (`seguridadUrgente`) además saca al usuario del login. En campo, un transductor de presión dañado produciría el mismo bloqueo.

## D9-1. Estado seguro al arrancar y bloqueos ★ (H1, H2, H5, H6, H7, H8)
- **D9-1.1 (revierte en parte E4/D-08):** al arrancar con la cámara no segura, el protocolo corre SOLO, sin confirmación, con el programa conservador actual (`_programa_para_arranque`): con presión sobre la atmosférica + brecha, solo la descompresión lenta; con vacío bajo la atmosférica − brecha, aire atmosférico (ya existe en `ProtocoloFallo`, ramas `pres < atm - rango`; agregar prueba explícita del caso de arranque en vacío). "NO ABRIR" sigue hasta cámara segura.
- **D9-1.2:** la confirmación "Confirmar y llevar a estado seguro" se exige SOLO si hubo un paro real (`PARO_REAL`) visto durante este encendido. El texto de la confirmación y de la tarjeta de alarmas distingue: paro liberado / arranque con cámara no segura / fallo de ciclo. Nunca dice "paro liberado" si no hubo paro.
- **D9-1.3 (revierte SAF-03 de T6):** con el estado seguro activo se permiten: modo prueba (el protocolo se pausa al entrar y se reanuda al salir, con el ALL_OFF de salida de siempre), apagado del equipo y cambio de programa. El inicio de ciclo sigue bloqueado. La evaluación de seguridad sigue usando la copia del programa del protocolo y la del último ciclo, no solo el seleccionado (verificar `programas_para_seguridad` con una prueba que cambie el programa durante el protocolo).
- **D9-1.4:** sin lectura de presión de cámara el protocolo no queda corriendo indefinidamente: se detiene con CIC-10 ("Estado seguro detenido") + SEN-06, con NO ABRIR, y sin bloquear lo de D9-1.3.
- **D9-1.5:** el login se permite siempre, también con el paro activo o con una confirmación pendiente (puede hacer falta una corrección antes de liberar el paro). Se quita la vuelta forzada del login en `Main.qml`; la confirmación sigue visible en la tarjeta de alarmas de Preciclo y en la campana.
- **D9-1.6 (nuevo) coherencia puerta-presión:** fuera de ciclo, con la puerta detectada ABIERTA y la presión de cámara fuera de [atm − brecha, atm + brecha] durante 3 lecturas, alarma nueva (código siguiente libre, p. ej. SEN-10) "Presión de cámara incoherente con la puerta abierta": causas posibles en el texto de acción: calibración del sensor de presión, presión atmosférica de referencia o sensor de puerta. Nivel ALARMA, bloquea el inicio de ciclo, solo fuera de ciclo, despeje automático con 3 lecturas coherentes; solo presión (la temperatura con puerta abierta no se evalúa).
- Registro de riesgos: HAZ nuevos por D9-1.1, 1.3 y 1.6. Revisores ★ (safety, timing).

## D9-2. Niveles de alarma (H3)
SEN-01, SEN-03, SEN-06, SEN-07 y CIC-10 pasan de AVISO a ALARMA. Se conserva su `bloquea` actual. Textos y pruebas del catálogo actualizados.

## D9-3. Equipos con puertas simples (H10, H11)
Según el perfil de instalación (tipo de puerta):
- Parámetros del ciclo › Finalización: se ocultan `tiempo_espera_apertura` y `apertura_automatica`; el backend rechaza `apertura_automatica=true` en ese equipo. `temp_max_apertura` sigue visible.
- Parámetros del equipo: se ocultan los grupos Empaque y Puerta (`timeout_puerta`).
- Grupo nuevo **"Cámara segura"** (es/en) con `temp_max_apertura` y `rango_presion_atm` (sale del grupo puerta en `global_params.json`), visible en todo equipo.
- La lista de grupos deja de estar fija en `OpcionesParametrosEquipo.qml` (hoy `["puerta","impresion","drenaje","empaque","chaqueta","sistema"]`): la entrega el backend ya filtrada por perfil.

## D9-4. Parámetros del equipo no se refrescan al guardar (H12)
`model: control.delGrupo(control.grupo)` no se reevalúa con `datosChanged` (es una función, no una propiedad). Pasar a una propiedad notificable (p. ej. `parametrosGrupo`) o forzar la dependencia. Prueba QML: guardar y leer el valor nuevo en la lista sin salir. Revisar el mismo patrón (llamadas a `@Slot` como `model:`) en todas las pantallas de Opciones, incluido Parámetros del ciclo.

## D9-5. Entradas NC interpretadas (H15)
Hoy E/S muestra el nivel crudo (ES-11). Para TODAS las entradas de contacto NC se muestra el estado interpretado (Activo/Inactivo: 1 = inactivo, 0 o abierto = activo) y el nivel crudo en pequeño al lado. Hoy no existe un atributo de polaridad por entrada (solo el paro lo maneja en `devices/paro_emergencia`): se agrega `nc: true|false` por DI en el YAML de la instancia (máximo físico) con esta lista de NC: el paro de emergencia y el seguro de atrapamiento de cada puerta (solo cuando el perfil tiene puertas con atrapamiento). Las demás entradas, NO NC.

## D9-6. Bitácora solo con lo necesario (H18)
Se conservan: eventos de seguridad (paro, estado seguro, ciclo interrumpido, falla reconocida, apagado, modo prueba y salidas de prueba, aire atmosférico cortado, salidas sin confirmar), cambios de configuración con quién/qué/antes/después (parámetros de ciclo y equipo, roles de sensor, calibraciones, reasignación, unidades, idioma, impresora, correo, mantenimiento, usuarios y operadores, respaldo/restauración) e inicio/cierre de sesión, login fallido/bloqueado.
Se retiran: `rechazo_401/403/409` (y todo `rechazo_*` de `_rechazar`), `suspension_entra/sale`, `puerta_orden`, `puerta_orden_rechazada`, `PROGRAMA_SELECCIONADO`, `PROGRAMA_SELECCION_RECHAZADA`, `correo_prueba`, `impresora_prueba`, `impresion_ganancias`. Siguen en el log de desarrollo (`logger`). Actualizar `core/runtime/bitacora.py::EVENTOS` y las pruebas.

## D9-7. Entrega sin datos precargados (H17, N-1)
- `config/correo.json` de la entrega: sin remitente ni destinatarios (plantilla neutra).
- Solo `cycles/factory/` va al ejecutable; `cycles/user/` y `cycles/defecto/` no (hoy va toda la carpeta `cycles` en `Autoclave.spec`/`AutoclaveBackend.spec`; `cycles/user/bowe_dick.json` tiene descompresión modo 4, residuo del banco).
- La compilación verifica las dos cosas y falla si no se cumplen (igual que D8-3.18 con la calibración).

## D9-8. Modo de descompresión 5 en la primera instalación (H14)
En B, al instalar por primera vez solo se ofrecía hasta el modo 4; después, en configuración, sí dejaba el 5. En `tanda-8` el asistente no tiene selector de modo y la lista de Parámetros del ciclo ofrece 0–5 (con líquido 4, 5, 0). Sin cambio de código: caso nuevo en la hoja de banco (instalación limpia → Parámetros del ciclo → modo 5 en los 4 programas). Si se reproduce, Code toma captura y lo investiga.

## D9-9. Buzzer y paro: salidas que se encienden un instante (H-nuevo 12) ★
Evidencia de banco (Cristian): con el paro de emergencia activo, cada vez que el buzzer reinicia su patrón se encienden un instante **las salidas que estaban activas en el momento en que se pulsó el paro**. Es decir, algo conserva el estado de salidas previo al paro y lo vuelve a escribir. Hipótesis a descartar en orden:
1. **Firmware:** el registro sombra (`estadoOut1/estadoOut2`) conserva los bits previos al paro; el `SET DO` del buzzer hace `write16(estadoOut)` con todos ellos hasta el siguiente ALL_OFF. Revisar si el ALL_OFF del paro llega y limpia la sombra, y si el firmware rechaza o acepta `SET` mientras tanto.
2. **PC, comandado:** la corrección de discrepancia comandado/reportado (`serial_link.py`, reenvío de `SET DO`) o `_comandado` reenvían estados previos al paro.
3. **PC, ALL_OFF espaciado:** con el paro, el ALL_OFF se repite a lo sumo cada 1 s (`_INTERVALO_ALL_OFF_PARO_SEG`, `set_io.py`) y el DO reportado ignora el buzzer (`_SALIDAS_IGNORADAS_PARO`), así que una salida reencendida no fuerza un ALL_OFF inmediato.
Requisitos: al detectar el paro, ALL_OFF inmediato con ACK; con el paro activo ninguna salida distinta del buzzer puede encenderse ni un instante (en el PC y en el firmware); el buzzer conmuta solo su canal; fuera del paro, el buzzer no altera otras salidas. Si la causa es el firmware: Code modifica el `.ino` de `Hardware/Comunicacion_esclava_ESP32_V3`, sube la versión de firmware y deja a Cristian las instrucciones para compilar y cargar (Code NO carga firmware). Prueba: registro de todos los `SET`/`ALL_OFF` enviados durante el paro con la planta simulada, con salidas encendidas antes del paro y el patrón del buzzer reiniciándose; caso de banco con la lista de salidas a observar.

## D9-10. Manejo de ciclos en Opciones avanzadas (H-nuevo 13)
Las funciones ya existen desde la tanda 5 (O1) dentro de Parámetros del ciclo (`/programas/{n}/habilitado`, `/duplicar`, `DELETE`; técnico e ingeniero). Se mueven a una sección "Manejo de ciclos" de Opciones avanzadas: crear, duplicar, habilitar/deshabilitar y borrar los personalizados (nunca los de fábrica). "Crear" = duplicar un programa existente con un nombre nuevo (no hay creación desde cero). Roles: la sección Manejo de ciclos es para técnico e ingeniero; la reasignación de E/S sigue solo para el ingeniero. Fuera de ciclo, con bitácora (crear, borrar, habilitar/deshabilitar). Se retiran los botones de Parámetros del ciclo para no duplicar la función.

## D9-11. Setup: "Configurar este PC como estación del autoclave" (H-nuevo 14)
Opción del Setup de Inno Setup, marcada por defecto, que ejecuta al final los scripts 01, 02, 04 y 05 de `tools/estacion/`:
- una página del asistente pide usuario y contraseña para el inicio automático;
- el desinstalador ejecuta los scripts de reversión;
- el Setup da permisos de escritura a `C:\ProgramData\Especifika\Autoclave` (resuelve la cuenta de operador sin privilegios).
Decisiones (Cristian, 23:26):
- inicio automático con la cuenta con la que se instala (no se crea cuenta "operador");
- Windows Update solo avisando y diferido (lo que hacen los scripts hoy), no desactivado;
- arranque sin logo (`bcdedit`, script 02) como casilla aparte, DESMARCADA por defecto;
- se valida primero en un PC de prueba: Code arma el Setup pero NO lo ejecuta ni corre ningún `.ps1`; deja a Cristian una lista de verificación para el PC de prueba (instalar, reiniciar, comprobar inicio automático, desinstalar y comprobar la reversión).

## D9-13. Pendientes de la tanda 8 (revisión del 22-oct 23:56)
Fuente: `docs/informes/informe_tanda_2026-10-23_t8.md` y `tanda8/DECISIONES_PARA_REVISAR.md`. La compilación C NO se instala: el equipo pasa de B a D.
- **D9-13.1 (SP-5) Actualizar sin copiar archivos a mano** (recomendación aceptada por defecto): al actualizar, el programa (o el Setup) refresca los archivos de configuración DE FÁBRICA de `programa\autoclave\config\`: `instances\*.yaml` (máximo físico y asignación de fábrica) y `global_params.json` (defectos y límites), igual que hoy `cycles\factory\`. NUNCA se reemplazan: `calibration.yaml` del equipo, `correo.json`, la asignación de E/S vigente (`ProgramData`, D8-5.12), el perfil, la BD ni `cycles\user\`/`cycles\defecto\`. Los valores vigentes de los parámetros siguen en la BD. Antes de reemplazar, copia de respaldo con fecha. Ensayo B → D sobre una copia con el perfil y la BD de la B (como el de K8): Cámara 2 y `descompresion_lenta` aparecen sin pasos manuales. La sección "Actualizar B → D" del LEEME no debe tener pasos de copia a mano.
- **D9-13.2 (SP-3) Calibración neutra:** se confirma lo de K8 (usuario 1/0, sección `factory` conservada).
- **D9-13.3 (V8a, Medios abiertos) ★:** TMG-01 (aplicar al ciclo en curso solo después de registrar la bitácora), SAF-01 (las filas de bitácora del cambio y del arrastre en una sola transacción: método por lote en `db_manager.py`) y SAF-02 (doble falla bitácora + JSON). Con revisores.
- **D9-13.4 (V8b) Ticket y motivos de fallo en inglés:** con la interfaz en inglés, el ticket, la reimpresión y los motivos de fallo de las fases salen en el idioma vigente (catálogo es/en; claves + parámetros, D-25). Ticket de 32 columnas: se permiten abreviaturas solo en el ticket (D8-5.4 no aplica al ticket) — DECISIÓN SIN CONFIRMAR.
- **D9-13.5 (V8b) Capturas:** regenerar el banco de capturas con el código final de la tanda 9, en es y en, incluida la pantalla de reasignación y las pantallas nuevas (Cámara segura, Manejo de ciclos). Prioridad baja: después de todo lo funcional.
- **No entran (necesitan respuesta o datos de Cristian):** D-38 (cuentas ADC de banco), válvula de seguridad mecánica tarada (el equipo tiene válvulas de alivio mecánicas en chaqueta y cámara; falta la presión de tara), preguntas de S1, S2a, S2b, R8 (incluida SAF-04: estado seguro con la asignación de E/S dañada), V8a, E1 y E2, y la limpieza de worktrees con `--force`. Quedan en el índice de la tanda 9 como PREGUNTAS arrastradas.

## D9-12. Diferido (al final, solo si sobra tiempo): H9 "Recordar usuario" y "¿Olvidó su contraseña?".

## Q. Respuestas de Cristian (22-oct 23:26)
- Q1 (D9-1.6): de acuerdo con la recomendación.
- Q2 (D9-10): de acuerdo: crear = duplicar; Manejo de ciclos para técnico e ingeniero.
- Q3 (D9-9): con el paro de emergencia, se encienden un instante las salidas que estaban activas cuando se activó el paro.
- Q4 (D9-11): (a) cuenta con la que se instala; (b) diferido; (c) arranque sin logo como opción aparte desmarcada; (d) sí, PC de prueba primero.
- Q5 (D9-5): NC = paro de emergencia y atrapamiento de las puertas cuando aplica.
