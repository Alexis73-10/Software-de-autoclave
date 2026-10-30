# Tanda 23 — informe: «módulo E/S» y numeración RTD / AI

Fecha: 29-oct-2026. Spec: `docs/mis_plans/decisiones_tanda_23.md` (MES-01..04, AIN-01..05, AIN-R1..R3). Prompt: `docs/mis_plans/prompt_claude_code_tanda23.md`. Estado paso a paso: `estado.md`. Inventario: `inventario.md`. Revisión: `R_revision.md`.

**La entrega no se compiló.** Para compilarla, desde `dev` limpio (el mismo comando de la última entrega, alpha.11):

```
python tools/entrega/compilar_entrega.py --con-generador
```

## Resultado

- Rama `tanda-23` (desde `dev` acd17d36), unida a `dev` en el merge `c65c2c2b` (sin fast-forward). Sin push.
- Suite (`pytest tests -n auto`): sobre `dev` tras el merge, **9237 passed, 11 skipped, 7 xfailed, 1 failed**: `test_home_view.py::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`, la caída conocida de trabajador xdist (ya anotada en la tanda 22), que pasa en serie (1 passed). Corridas previas en `tanda-23` (`suite_raw_1.txt`, `suite_raw_2.txt`) encontraron dos rojas propias de la tanda, corregidas: el bloque T23 de la hoja del banco que `test_f1_registro_pruebas` no esperaba (18e2a436) y estado compartido de los filtros de `converters` en `test_t23_ain_grupos` con `-n auto`. Salida completa en `suite_raw.txt`.

## AIN — numeración de entradas analógicas (subagente B, worktree `tanda-23-ain`; revisión R)

- **AIN-03 lectura:** `protocols/modbus_link.py` lee fc04 0x0000 ×16 (`N_PRES = 16`, `N_AI = 24`): `ai[0..5]` RTD 1–6, `ai[6..7]` None, `ai[8..23]` AI 1–16. Vigilancia del lazo (MOD-08), `all_off`, ADB-01..05 y la configuración de seguridad no cambiaron (verificado por la revisión R). `hal/measures/units.py` y `converters.py` con presión ×16; dobles `tests/helpers/enlace_doble.py` (24) y `m31_simulado.py` (16 AI).
- **AIN-01/02 numeración:** `core/runtime/asignacion_io.py`: grupos `AI_TEMP` 1–6 («RTD 0n») y `AI_PRES` 1–16 («AI nn»), tipo `"AI"`; `_OFFSET_PRES` ya no suma al número de puerto; `map_pres[f] = i` sigue siendo el canal crudo 8+i y `map_temp` no cambia. `FORMATO = 2`. Ids de Entradas/Salidas y Calibración de sensor en `io_names.py`.
- **AIN-R1:** duplicados (`validar`, `ocupados` por `(grupo, puerto)`), búsquedas, evidencias, `responde`, `puertos_sin_calibracion`, textos de error, `/io/assignment` (`ocupados` por grupo `DI`/`DO`/`AI_TEMP`/`AI_PRES`, filas con `grupo` e `id_guardado`), controlador y pantalla de Reasignación (`objectName` de chips sin duplicados) trabajan por grupo. RTD 01 y AI 01 a la vez: sin conflicto ni cruce.
- **AIN-04 calibración:** `config/calibration_modbus.yaml` con 16 entradas de presión nominales (4000–20000 µA → 0–400 kPa abs). Una copia de `data/` o un respaldo con exactamente 8 entradas de presión se completa al cargar (`config/completar_presion.py`) sin tocar 0–7, con log; al calibrar, el escritor deja 16. Un respaldo Modbus de 8 se acepta; uno con otra fábrica se sigue rechazando. `tools/verificar_calibracion_neutra.py` exige 16.
- **AIN-05 migración:** un `asignacion_io.json` FORMATO 1 se migra al cargar (presión p → p−8; DI, DO, temperatura y pendientes sin cambio), con `.bak`, copia única `asignacion_io.json.formato1.bak` (SAF-03) y fila `asignacion_io_migrada` (categoría «configuracion»). Idempotente. Un puerto de presión FORMATO 1 fuera de 09–16 deja el archivo intacto y da CONFIGURACION_INVALIDA. Si el archivo no se puede reescribir se lee migrado en memoria (nunca con la numeración vieja) y la anotación se conserva en la siguiente escritura (SAF-02). Respaldos FORMATO 1: migrados al restaurar. Registros de calibración: los nuevos llevan `"formato": 2`; uno sin marca resta 8 en presión; una marca desconocida no se interpreta (SAF-04). YAML de instancia: clave nueva `io_ports_formato: 2` en `ACV-2026-001.yaml` (presión 1–4); un YAML sin la marca (copia persistente sin refrescar o instancia propia del sitio) se lee migrado con aviso en el log (SAF-01, MEDIA).
- **Pruebas nuevas:** `test_t23_ain_lectura.py` (16 AI contra `m31_simulado`, AI 16 nominal), `test_t23_ain_migracion.py` (migración, `.bak`, bitácora, idempotencia, respaldo; **equivalencia AIN-R2** en fábrica, ejemplo y las 1680 asignaciones válidas de presión 9–16), `test_t23_ain_grupos.py` (RTD 01 + AI 01, `puerto_inexistente` para RTD 07 / AI 17 / AI 00, controlador y `/io/assignment`), `test_t23_ain_calibracion.py` (8 → 16), `test_t23_ain_revision.py` (SAF-01..05).

### Desde cuándo rige la numeración nueva

Desde la primera arrancada de una compilación con esta tanda (la siguiente entrega después de alpha.11). En la bitácora: las filas de reasignación, verificación y calibración anteriores a la fila `asignacion_io_migrada` de cada equipo (o, si el equipo nunca tuvo `asignacion_io.json`, anteriores a la instalación de esa compilación) usan la numeración vieja (presión «AI 09–16» = AI 01–08 de ahora, mismo canal físico). Las filas viejas no se reescriben.

## MES — «módulo E/S» (subagentes C1–C4)

- **MES-01/02 textos:** «tarjeta», «tarjeta de E/S», «tarjeta de control», «targeta» → «módulo E/S» (singular, masculino), en inglés «I/O module», en QML, `ui_pyside`, i18n es/en, catálogo de alarmas (títulos, descripciones y acciones), ticket de conectividad («MODULO E/S: DESCONECTADO», sin tilde porque cp437 no tiene «Ó»), ticket de arranque, PDF, correo, bitácora (texto propio para el evento `tarjeta_conectada`: «Conexión del módulo E/S»), mensajes de log, comentarios y docstrings, Setup (página «Red del módulo E/S», `autoclave.iss`, LEEME, textos del paso 08), `tools/registro_pruebas`, documentación vigente.
- **Identificadores** (`tarjeta` → `modulo_es`/`ModuloEs`/`moduloEs`): `EventoTarjeta` → `EventoModuloEs`; `EnlaceES.tarjeta()` → `modulo_es()` (y `MIEMBROS_ENLACE`); `tarjeta_emparejada()` → `modulo_es_emparejado()`; `estado.sin_datos_tarjeta_s` → `sin_datos_modulo_es_s`; `PLAZO_TARJETA_S` → `PLAZO_MODULO_ES_S`; `UiBridge.estadoTarjeta` → `estadoModuloEs`; campos publicados `/status.tarjeta` → `modulo_es`, `/status.estado_tarjeta` → `estado_modulo_es`, `/system/info` `software.id_tarjeta` → `id_modulo_es`, 409 `sin_conexion_tarjeta` → `sin_conexion_modulo_es`, diagnóstico `tarjeta_st` → `modulo_es_st` (lectores del cliente y la UI actualizados a la vez; las rutas no cambian; base t15: solo el docstring de POST `/system/shutdown` en `openapi.json`). Claves i18n `*_tarjeta*` → `*_modulo_es*`. Archivos: `tools/emparejar_tarjeta.py` → `tools/emparejar_modulo_es.py`; pruebas `test_arranque_sin_modulo_es.py`, `test_e6_control_loop_modulo_es.py`, `test_e6_emparejamiento_modulo_es.py`, `test_u4_puente_modulo_es.py`, `test_u4_modulo_es_desconectado.py`.
- **MES-04:** `state_machine/alarms/catalogo.codigo_visible()` muestra `TARJETA_<x>` como `MODULO_ES_<x>` en la campana, filas de alarma, ventana de detalle (campo «Código»), Preciclo, fin de ciclo, motivo del PDF/correo, ticket (historial y en vivo), ticket de alarmas activas de `ui_pyside`; campo nuevo `codigo_visible` en los DTO de alarmas/eventos de `/status` y roles `idVisible`/`codigoVisible` en `AlarmListModel`. El código guardado (`codigo`, `id` = `CODIGO|origen`, historial) no cambia.
- **Prueba de regla D:** `tests/test_t23_sin_tarjeta.py` (valores de i18n, «board» en en.json, literales e identificadores QML, plantillas de ticket/PDF/correo, `autoclave.iss`, textos `configurar_modulo.*`, mensajes de log, identificadores de `src/` con lista blanca comentada, títulos del catálogo, `codigo_visible()`). Más `test_t23_mes04_codigo_visible_ui.py` y `test_t23_mes04_codigo_visible_nucleo.py`.

### Lo que NO se renombró (MES-03) y por qué

1. **Códigos de alarma** `TARJETA_SIN_TRAMA_VALIDA`, `TARJETA_VERSION_INCOMPATIBLE`, `TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_SALIDAS_NO_APAGADAS`, `TARJETA_EXPANSOR_FUERA_DE_LINEA`, `TARJETA_WATCHDOG`, `TARJETA_REINICIO`, `TARJETA_CONFIG_SEGURIDAD`, `TARJETA_MODULOS_ORDEN`, la tupla `CODIGOS_TARJETA`, las claves i18n `alarmas.TARJETA_*` y los ids sintéticos `TARJETA_DESCONECTADA`/`TARJETA_SIN_DATOS` de `SeccionEstadoSeguro.qml`: se guardan en el historial y los citan catálogo, riesgos y trazabilidad (MES-03.1). Se muestran como `MODULO_ES_*`.
2. **Nombres persistidos** (MES-03.2): evento `tarjeta_conectada`, entidad `tarjeta_es` y clave de detalle `tarjeta_conectada` del evento `apagar_equipo` (`audit_log`); `board_id` del perfil; campo `id_tarjeta` de la cabecera de `tools/registro_pruebas` (va en su BD); el nombre `emparejar_tarjeta` en las filas viejas de `installation_profile_cambios.log` (las nuevas dicen `emparejar_modulo_es`). Los valores enumerados de `estado_modulo_es` (`"desconectada"`, `"sin_tramas_validas"`) siguen en femenino porque la UI los compara.
3. **Recuadros de interfaz** (MES-03.3): `TarjetaMenu`, `TarjetaContenido`, `TarjetaResumen`, `OpcionTarjeta`, `TarjetaCanal`, `TarjetaGrupo`, `TarjetaSensor`, `fondoTarjeta`, `tarjeta_titulo`… (lista completa en `inventario.md` (b) y en la lista blanca de la prueba de regla), la clase CSS `.tarjeta` de `registro_pruebas`, y las tarjetas de widget de `ui_pyside`.
4. **Otro sentido de la palabra:** «tarjeta de red» y «lector de tarjetas» en el Setup; la tarjeta KinCony/ESP32 retirada en documentos históricos.
5. **Documentos históricos:** `docs/informes/`, decisiones, planes y prompts de tandas cerradas, filas viejas de la bitácora, tickets impresos, `docs/superpowers/`.

## Decisiones sin confirmar

1. **YAML de instancia sin `io_ports_formato` = FORMATO 1 y se lee migrado** (SAF-01): en vez de rechazarlo; la marca desconocida sí se rechaza (`fabrica_invalida`).
2. **Anotación de la migración en el propio `asignacion_io.json`** (`"migracion": {…, "registrada": false}`) hasta que la fila entra en la bitácora (la BD puede no estar lista o la instalación sin terminar). Si el proceso se corta entre escribir la fila y marcarla, la fila se repite una vez.
3. **La calibración se completa solo con exactamente 8 entradas de presión**; otro largo decide la validación de siempre.
4. **Columna Tipo de Reasignación sigue en «AI» para RTD**; la etiqueta del puerto dice «RTD 0n».
5. **`motivo_fallo` (texto libre guardado) se guarda ya con el código visible**; `codigo_fallo` conserva el guardado. El parámetro `causa` de COM-03 se guarda visible; el `origen` sigue `TARJETA_*`.
6. **Claves i18n renombradas mecánicamente** (`modulo_es_desconectada`, `…_emparejada` conservan la terminación femenina aunque el texto sea masculino).
7. «Tarjeta del equipo» → «Módulo E/S del equipo» («Equipment I/O module»).
8. En el Setup, «la red de los módulos» pasó a singular («del módulo E/S»); los mensajes sobre la composición física (principal + expansiones) siguen en plural.
9. Hoja de banco: D-R8-04 (rechazo por puerto sin calibración) queda condicionado: con 16 AI nominales ya no se puede provocar.

## Preguntas abiertas (revisión R)

1. Confirmar en el banco que el principal responde fc04 0x0000 ×16: si diera excepción en 0x0008–0x000F se perdería toda la trama AI (temperaturas incluidas): falla cerrada, pero el equipo quedaría inutilizable.
2. ¿Hay equipos con YAML de instancia propio o con la copia persistente editada a mano? (SAF-01 ya corregido; afecta solo al aviso).
3. ¿Hay transmisores cableados hoy en AI 09–16? (quedan con calibración nominal, AIN-R3).

## Verificación en el equipo (después de instalar)

1. Entradas/Salidas: presiones en AI 01–04 con las mismas lecturas que antes; temperaturas en RTD 01–06.
2. Reasignación: etiquetas RTD/AI, AI 09–16 disponibles; asignar RTD 01 y AI 01 a la vez no da conflicto.
3. Desconectar el cable de red de los módulos: mensajes con «módulo E/S», ninguno con «tarjeta».
4. Ticket, PDF, Información del equipo y del sistema, Setup: sin «tarjeta»; en inglés sin «board».
5. (Adicional) Bitácora: una fila «asignacion_io_migrada» solo si el equipo tenía `asignacion_io.json`; la presión de cámara lee lo mismo que antes de actualizar. Pasos en la hoja de banco, bloque T23 (T23-01..04).

## Riesgos

AIN-R1 (ALTA), AIN-R2 (ALTA) y AIN-R3 (MEDIA) en `docs/riesgos/registro_riesgos.md`; trazabilidad REQ-33..35 en `docs/riesgos/matriz_trazabilidad.md`.
