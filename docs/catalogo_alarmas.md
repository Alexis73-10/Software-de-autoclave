# Catálogo de alarmas

Inventario de las alarmas (`Alarm`, `state_machine/alarms/`) que el código genera hoy, obtenido por
búsqueda directa en `src/` (rama `dev`). No existe un registro central de `alarm_id`: cada
`Alarm(...)` se instancia donde ocurre la condición. Actualizado 2026-10-14 (E6: §2.2 y fila de §4.1); antes 2026-10-11 (versión anterior:
2026-09-18, respaldada en `catalogo_alarmas.2026-09-18.bak.md`).

Cambios respecto a la versión del 18-sep: se agrega `CONFIGURACION_INVALIDA`; se elimina PURGA de
`FALLO_<FASE>` (fase retirada el 2026-10-01); `FALLO_CONEXION` figura como recuperable (así está en
el código, la versión anterior decía "no"); se agregan causas, umbrales y acción del operador; se
agrega la sección de alarmas propuestas (§8).

## 1. Cómo leer esto

- **Tipo** (`AlarmType`): `ALERTA`, `FALLA`, `EMERGENCIA`.
- **Prioridad UI (IEC 60601-1-8)**: derivada del tipo en `ui_qml/bridge/ui_bridge.py`
  (`_PRIORIDAD_POR_NIVEL`), decisión de Cristian 2026-09-29: EMERGENCIA → alta, FALLA → media,
  ALERTA → baja. No hay mapeo por `alarm_id`.
- **Bloqueante**: `blocks_operation` (default `True`). **Recuperable**: `recoverable`.
- Autolimpieza (`Alarm.is_auto_clearable`): solo `ALERTA` + `recoverable`. Las FALLA y EMERGENCIA se
  liberan con el reconocimiento (`RESET_FALLA`) y, en el caso de `PARO_EMERGENCIA`, solo con el paro
  liberado.
- `AlarmManager.report()` deduplica por `id`.
- IDs con `<...>` son dinámicos.
- **Acción del operador**: recomendación derivada de la lógica del código; no es texto aprobado del
  manual de usuario (pendiente de validar).

## 2. Arranque / sistema

Fuente: `backend/context.py`, `services/domain/loop/control_loop.py`.

| ID | Tipo | Bloq. | Recup. | Condición | Acción del operador |
|---|---|---|---|---|---|
| `CONFIGURACION_INVALIDA` | FALLA | sí | no | `errores_config_arranque()` devolvió errores en la etapa de arranque `cargando_configuracion`. Desde la fase B (2026-10-12) es fallo bloqueante de esa etapa: la secuencia se detiene sin abrir el serial ni construir el control loop, y `/arranque` lo publica con este mismo código. Descripción: `Configuración inválida: <errores>`. | Corregir la configuración y reiniciar. Llamar a servicio técnico. |
| `OPERANDO_SIN_BD` | FALLA | sí | no | Etapa `abriendo_base_datos` agotó sus 3 intentos (degradada, `ARR_SIN_BD`). PROVISIONAL hasta el modo sin BD (§7 de `planeacion_arranque_y_modo_sin_bd.md`): `/cycle/start` rechaza con 409 `sin_base_de_datos` y las consultas a la BD responden 503. | Revisar el disco / `data/`. Reiniciar. Llamar a servicio técnico. |
| `NO_HAY_CONEXION` | FALLA | sí | sí | Enlace serial con la tarjeta ESP32 caído (fuera de ciclo). | Revisar cable USB/alimentación de la tarjeta. Se limpia al reconectar. |

### 2.1 Códigos de etapa de arranque (`GET /arranque`)

Fuente: `backend/arranque/secuencia.py`. No son alarmas del `AlarmManager`: son el campo `codigo` de una etapa en `/arranque` (contrato de `planeacion_barra_arranque_real.md` §5).

| Código | Etapa | Resultado | Condición |
|---|---|---|---|
| `ARR_PERFIL` | verificando_instalacion | fallo | Perfil de instalación ausente o inválido. |
| `ARR_RELOJ` | verificando_instalacion | fallo | Reloj del sistema anterior a la fecha de instalación. |
| `ARR_CONFIG_ILEGIBLE` | cargando_configuracion | fallo | `global_params.json` ausente o ilegible. |
| `ARR_CICLO_DEFECTO` | cargando_configuracion | fallo | No existe el ciclo por defecto (`bowe_dick`). |
| `CONFIGURACION_INVALIDA` | cargando_configuracion | fallo | Valores fuera de rango (ver la alarma del mismo nombre). |
| `ARR_CICLO_CORRUPTO` | cargando_configuracion | degradado | Un JSON de ciclo no se pudo cargar; se omite. |
| `ARR_CALIBRACION` | verificando_calibracion | fallo | Calibración ausente, vacía, ilegible o que no valida. |
| `ARR_SIN_BD` | abriendo_base_datos | degradado | BD no disponible tras 3 intentos (alarma `OPERANDO_SIN_BD`). |
| `ARR_SIN_ES` | conectando_modulos_es | en_curso | 15 s sin E/S conectadas; sigue reintentando (D-E). |
| `ARR_ERROR_INTERNO` | cualquiera | fallo | Excepción no prevista en la etapa (queda la traza en el log). |

### 2.2 Tarjeta de E/S (E6, 2026-10-14)

Fuente: `protocols/serial_link.py` (detección, `EventoTarjeta`) y `services/domain/loop/control_loop.py`
(`_procesar_eventos_tarjeta`). Ids aprobados en `planeacion_protocolo_serial_esp32.md` §11.6. Fuera de ciclo
el `ControlLoop` las reporta como FALLA bloqueante y recuperable (`source_state="CONTROL_LOOP"`) y las despeja
al completarse el siguiente handshake. En ciclo, las de operación abortan el ciclo (ver §4.1). La descripción
lleva el motivo concreto (texto en español generado en `serial_link.py`). Mientras el handshake no se completa,
`is_connected()` es False, así que además aparece `NO_HAY_CONEXION`.

**U4 (tanda 2, 19-oct):** ya no. COM-01 (antes `NO_HAY_CONEXION`) sale solo con la tarjeta **desconectada**
(ningún puerto de la tarjeta, o puerto perdido por error de lectura/escritura); con el puerto presente y sin
datos válidos (sin handshake, CRC malo, firmware incompatible, DI vencida) aparece `TARJETA_SIN_TRAMA_VALIDA`
u otra de esta tabla. Las dos son excluyentes: al pasar de una a otra se resuelve la anterior. Además, el
`ControlLoop` activa `TARJETA_SIN_TRAMA_VALIDA` (motivo "no envía la trama de entradas (DI)") si, con el
handshake hecho, la trama DI vence (> 1,5 s) fuera de la ventana de la primera DI; se resuelve al volver.
SIS-01 (paro) ya no sale por falta de datos: solo con la entrada del paro leída en 0. Ver
`docs/informes/tanda2/U4_tarjeta_desconectada.md`.

| ID | Tipo | Bloq. | Recup. | Condición | Acción del operador |
|---|---|---|---|---|---|
| `TARJETA_SIN_TRAMA_VALIDA` | FALLA | sí | sí | Handshake: ninguna línea de CRC válido dentro del presupuesto (15 s), o ninguna ST tras el ALL_OFF. Reintento cada 3 s. | Revisar cable USB y alimentación de la tarjeta. Llamar a servicio técnico. |
| `TARJETA_VERSION_INCOMPATIBLE` | FALLA | sí | sí | Handshake: `VER` sin respuesta, protocolo distinto de 2, o tramas sin CRC (firmware V2 cargado, HAZ-FC-11). | Cargar el firmware 1.0.0 (servicio técnico). |
| `TARJETA_SIN_ACK` | FALLA | sí | sí | Handshake: `HB` sin `ACK` en 3 intentos de 1 s. | Servicio técnico. |
| `TARJETA_ALL_OFF_SIN_CONFIRMAR` | FALLA | sí | sí | Handshake: `ALL_OFF` sin `OK ALL_OFF` en 3 intentos de 1 s, o la tarjeta sigue con `sync=0` en 2 ST seguidas tras confirmarlo. | Servicio técnico. |
| `TARJETA_SALIDAS_NO_APAGADAS` | FALLA | sí | sí | Handshake: `DO:` con alguna salida en 1 en 2 tramas seguidas tras el `ALL_OFF`. | No operar. Servicio técnico (etapa de potencia o expansor). |
| `TARJETA_CONFIG_SEGURIDAD` | FALLA | sí | sí | Tanda 19 (MOD-07, MOD-12), solo enlace Modbus: la configuración de seguridad de los módulos M31-U (tiempo y modo de desconexión, estado de falla, estado al encender y modo de cada DO, rango y filtro de AI, unidad, compensación, filtro y habilitación de PT100) no quedó igual a lo escrito tras `intentos_escritura_config` escrituras y lecturas de vuelta. En ciclo, COM-03 (origen `operacion`). | Revisar la red de los módulos de E/S. Servicio técnico. |
| `TARJETA_MODULOS_ORDEN` | FALLA | sí | sí | Tanda 19 (MOD-06, MOD-10, MOD-12), solo enlace Modbus: código de error del principal (0x7587) = 2 (orden de expansiones incorrecto) o negociación pendiente (0x758A = 1), al conectar o en operación (invalida la conexión). En ciclo, COM-03 (origen `operacion`). | Sin energía, revisar el orden de los módulos y negociar (doble pulsación de Reload). |
| `TARJETA_EXPANSOR_FUERA_DE_LINEA` | FALLA (EMERGENCIA en ciclo) | sí | sí | `pcf_ok` distinto de `3F` en 2 ST seguidas: en el handshake, o en operación (fuera de ciclo pide nuevo handshake). | Servicio técnico (bus I2C / expansor PCF8575). |
| `TARJETA_WATCHDOG` | FALLA (EMERGENCIA en ciclo) | sí | sí | Con handshake hecho: `WD: ALL_OFF`, o ST con `wd=1` o `sync=0`. El enlace repite el handshake solo. | Revisar si el PC o el lazo de control se congelaron (FW-D6). |
| `TARJETA_REINICIO` | FALLA (EMERGENCIA en ciclo) | sí | sí | Con handshake hecho: `BOOT` inesperado o `uptime_s` que retrocede. El enlace repite el handshake solo. No aplica al enlace Modbus (tanda 19): los módulos M31-U no informan un contador de vida; un reinicio corta el TCP y la reconexión rehace la conexión verificada. | Revisar alimentación de la tarjeta. |
| `DISCREPANCIA_SALIDAS` | FALLA (EMERGENCIA en ciclo) | sí | sí | `DO:` reportado distinto de lo comandado (canales comandados desde el handshake y hace ≥ 1 s) en 2 tramas, tras un reenvío único. Fuera de ciclo pide nuevo handshake. Independiente de `disc_do`, que es solo diagnóstico (D-05). | Servicio técnico. |

## 3. PREPARADO y PREPARACION

Fuente: `states/preparado.py`, `states/preparacion.py`. Separación válvula/alarma/gate: ver
`CLAUDE.md` y `control_banda.py`. "Temporizada" = se dispara tras `tiempo_estable_alarma`.

| ID | Tipo | Bloq. | Recup. | Estados | Condición / parámetro | Acción del operador |
|---|---|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí | no | PREPARADO, PREPARACION | Flag `PARO_EMERGENCIA` activo. | Resolver causa, liberar el paro, reconocer. |
| `SUMINISTRO_VAPOR` | ALERTA | **no** | sí | PREPARADO, PREPARACION | DI `vapor_suministro` = 0. Cierra `vapor_chaqueta`; chaqueta queda pendiente. Limpia `CHAQUETA_FRIA/SOBRECALENTADA`. | Restablecer suministro de vapor. |
| `CHAQUETA_FRIA` | ALERTA | sí | sí | PREPARADO (temporizada), PREPARACION (inmediata) | `pres_chaqueta` < `presion_chaqueta − rango_presion_chaqueta`. | Esperar calentamiento de chaqueta; si persiste, revisar vapor/trampas. |
| `CHAQUETA_SOBRECALENTADA` | ALERTA | sí | sí | PREPARADO (temporizada), PREPARACION (inmediata) | `pres_chaqueta` > `presion_chaqueta + rango_presion_chaqueta`. | Esperar descenso; si persiste, revisar válvula/regulador. |
| `TEMP_DRENAJE_ALTA` | ALERTA | sí | sí | PREPARADO (temporizada), PREPARACION (inmediata) | `temp_drenaje` > `temp_segura_drenaje + rango_temp_drenaje`. Solo lado alto; sin alarma de lado bajo. Activa `agua_intercambiador`. | Esperar enfriamiento; verificar agua del intercambiador. |
| `PRESION_CAMARA_BAJA` | ALERTA | sí | sí | PREPARADO, PREPARACION | `pres_camara` < `presion_admosferica − rango_presion_atm`. Abre aire atmosférico a cámara. | Esperar igualación; si persiste, revisar aire/sensor. |
| `PRESION_CAMARA_ALTA` | ALERTA | sí | sí | PREPARADO, PREPARACION | `pres_camara` > `presion_admosferica + rango_presion_atm`. Pide descompresión. | Esperar venteo; si persiste, revisar válvula de descompresión. |
| `PUERTA_1_ABIERTA` | ALERTA | sí | sí | PREPARADO | DI `puerta_1_cerrada` = 0. | Cerrar puerta 1. |
| `PUERTA_2_ABIERTA` | ALERTA | sí | sí | PREPARADO | DI `puerta_2_cerrada` = 0. | Cerrar puerta 2. |
| `AGUA_RESIDUAL_CAMARA` | ALERTA | sí | sí | PREPARACION | DI `agua_camara` activo. Pide descompresión rápida/drenaje. | Esperar drenaje; revisar drenaje obstruido. |
| `SUMINISTRO_ELECTRICO` | ALERTA | sí | sí | PREPARADO | DI `suministro_electrico` = 0. | Revisar alimentación eléctrica. |
| `SUMINISTRO_AGUA_BOMBA` | ALERTA | sí | sí | PREPARADO, PREPARACION | DI `agua_bomba` = 0. | Restablecer agua a la bomba de vacío. |
| `SUMINISTRO_AGUA_GENERADOR` | ALERTA | sí | sí | PREPARADO, PREPARACION | DI `agua_generador` = 0. | Restablecer agua al generador. |
| `SUMINISTRO_AIRE_COMPRIMIDO` | ALERTA | sí | sí | PREPARADO, PREPARACION | DI `aire_comprimido` = 0. | Restablecer aire comprimido. |
| `ERROR_AI_<SENSOR>` | FALLA (SEN-01; ALERTA hasta D9-2, tanda 9) | sí | sí | PREPARADO, PREPARACION | Lectura analógica == 0 (fallo de sensor). `<SENSOR>` = clave en mayúsculas. PREPARACION chequea lista fija: `pres_camara`, `pres_chaqueta`, `pres_empaque_1`, `pres_empaque_2`, `temp_camara`, `temp_2_camara`, `temp_ref`, `temp_chaqueta`, `temp_drenaje_cam`, `temp_drenaje`. PREPARADO recorre todos los configurados. | Revisar cableado/sensor; servicio técnico. |

## 4. CICLO

Fuente: `states/ciclo.py`. Al entrar en cualquier FALLA/EMERGENCIA de ciclo se ejecuta
`ProtocoloFallo` y el ciclo queda esperando confirmación con resultado FALLO.

### 4.1 Abortan el ciclo

| ID | Tipo | Bloq. | Recup. | Condición | Acción del operador |
|---|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí | no | Flag de paro durante el ciclo. `motivo_fallo`: "Paro de emergencia activado durante el ciclo." | Ver §3. |
| `FALLO_SUMINISTRO_ELECTRICO` | EMERGENCIA | sí | no | Flag `FALLO_SUMINISTRO_ELECTRICO` durante el ciclo. | Restablecer energía; revisar el ciclo antes de reutilizar la carga. |
| `FALLO_PUERTA_1_ABIERTA` | FALLA | sí | sí | DI `puerta_1_cerrada` = 0 en ciclo. | No abrir bajo presión; esperar protocolo de fallo. |
| `FALLO_PUERTA_2_ABIERTA` | FALLA | sí | sí | DI `puerta_2_cerrada` = 0 en ciclo. | Ídem. |
| `FALLO_PUERTA_1_EMPAQUE` | FALLA | sí | sí | `pres_empaque_1` < 0.6 × `presion_empaque` (default 300). | Revisar sello/empaque y presión de aire de la puerta 1. |
| `FALLO_PUERTA_2_EMPAQUE` | FALLA | sí | sí | `pres_empaque_2` < 0.6 × `presion_empaque`. | Ídem puerta 2. |
| `SENSOR_AUSENTE` | EMERGENCIA | sí | no | Sin lectura (`None`) de `temp_camara` o `pres_camara` (únicos críticos hoy). | Revisar sensor/comunicación; servicio técnico. |
| `FALLO_CONEXION` | EMERGENCIA | sí | **sí** | Enlace serial caído más de `_TOLERANCIA_DESCONEXION_SEG` (5 s) en ciclo; lo dispara `ControlLoop` vía `abortar_por_desconexion()`. | Revisar enlace con la tarjeta. |
| `TARJETA_WATCHDOG` / `TARJETA_REINICIO` / `TARJETA_EXPANSOR_FUERA_DE_LINEA` / `DISCREPANCIA_SALIDAS` / `TARJETA_CONFIG_SEGURIDAD` / `TARJETA_MODULOS_ORDEN` (tanda 19) | EMERGENCIA | sí | sí | Falla de la tarjeta de E/S en ciclo (ver §2.2); lo dispara `ControlLoop` vía `abortar_por_falla_io(alarm_id, motivo)`. `fase_ciclo = "FALLO_IO"`. | Ver §2.2. |
| `FALLO_<FASE>` | FALLA | sí | sí | Una fase devolvió `FaseResult.FALLO`. Ver §4.3. | Según motivo (`estado.motivo_fallo`). |

### 4.2 No abortan el ciclo

| ID | Tipo | Bloq. | Recup. | Condición | Acción del operador |
|---|---|---|---|---|---|
| `SUMINISTRO_VAPOR` | ALERTA | no | sí | DI `vapor_suministro` = 0; cierra `vapor_chaqueta`, chaqueta pendiente. | Restablecer vapor. |
| `TEMP_DRENAJE_ALTA` | ALERTA | no | sí | `temp_drenaje` > `temp_segura_drenaje` por 3 lecturas (sin `rango`, a diferencia de PREPARADO). Activa `agua_intercambiador`; se limpia tras 3 lecturas bajas. | Verificar agua del intercambiador. |
| `TIMEOUT_APERTURA_AUTOMATICA` | ALERTA | no | sí | Apertura automática: cámara no baja de `temp_max_apertura` en `timeout_temperatura` min. Una vez por ciclo. | Esperar enfriamiento y abrir manualmente. |
| `APERTURA_AUTOMATICA_DENEGADA` | ALERTA | no | sí | La puerta no se mueve tras `request_open()` por más de 60 s (bloqueo mecánico/interlock). Una vez; reintenta cada 5 s. | Revisar bloqueo de puerta; abrir manualmente. |

### 4.3 Causas internas de `FALLO_<FASE>`

El `alarm_id` solo identifica la fase; el motivo queda en `estado.motivo_fallo` (texto libre, y solo
`esterilizacion` y `calentamiento` lo rellenan con detalle). Fases con nombre `name`:
`PRECALENTAMIENTO`, `PRE_VACIO`, `CALENTAMIENTO`, `ESTERILIZACION`, `DESCOMPRESION`, `SECADO`
(verificar `name` exacto de cada clase).

| ID | Causas actuales (debounce de 3 lecturas donde se indica) |
|---|---|
| `FALLO_PRECALENTAMIENTO` | Timeout `timeout_precalentamiento` (default 10 min) sin alcanzar la presión objetivo. Sin `motivo_fallo` específico. |
| `FALLO_PRE_VACIO` | Timeout `timeout_bajo` (vacío no alcanzado) o `timeout_alto` (presión no alcanzada), default 10 min por pulso. Sin `motivo_fallo` específico. |
| `FALLO_CALENTAMIENTO` | Timeout global de calentamiento; no se logró sostener condición estable dentro del tiempo de recuperación. Con `motivo_fallo`. |
| `FALLO_ESTERILIZACION` | Temperatura alta (`T > t_est + rango`), temperatura baja, presión alta, presión baja (cada una con 3 lecturas) y `ESTERILIZACION_TIMEOUT_F0` (F0 no alcanzado en 2 × `tiempo_esterilizacion`; solo si `F0=true`). Con `motivo_fallo`. |
| `FALLO_DESCOMPRESION` | Timeout del modo (`descompresion.modo_N.timeout`, default 60 min). El modo 0 (gravedad) no tiene timeout por diseño. Sin `motivo_fallo` específico. |
| `FALLO_SECADO` | Timeout de pulso `timeout_pulso` (default 10 s) en VACIO_BAJO o AIRE_ALTO (modo 3). Sin `motivo_fallo` específico. |

## 5. Puertas

Fuente: `devices/puertas/advanced_door.py` (solo `AdvancedDoor`).

| ID | Tipo | Bloq. | Recup. | Condición |
|---|---|---|---|---|
| `ABRIENDO_MODO_SEGURO_<nombre>` | ALERTA | no | sí | Puerta abriendo en modo seguro, sin bomba de vacío disponible. |
| `CERRANDO_MODO_SEGURO_<nombre>` | ALERTA | no | sí | Puerta cerrando en modo seguro, sin bomba de vacío disponible. |

## 6. FALLA / HIBERNACION

| ID | Tipo | Bloq. | Recup. | Condición |
|---|---|---|---|---|
| `PARO_EMERGENCIA` | EMERGENCIA | sí | no | Paro activo estando en FALLA (`falla.py`, apaga todas las salidas, buzzer de emergencia; descarta `RESET_FALLA`) o HIBERNACION (`hibernacion.py`). |

## 7. Notas de consistencia

1. **`PARO_EMERGENCIA`** se instancia desde 5 estados (PREPARADO, PREPARACION, CICLO, FALLA,
   HIBERNACION) con el mismo id; la deduplicación deja una sola activa y el `source_state` es el de
   quien la reportó primero.
2. **Umbrales de drenaje distintos**: PREPARADO/PREPARACION usan `temp_segura_drenaje + rango_temp_drenaje`;
   CICLO usa `temp_segura_drenaje` sin rango. Mismo id, distinto umbral y bloqueo (sí vs no).
3. **`ERROR_AI_*` solo detecta valor == 0**. Un sensor desconectado que devuelva `None` se atiende
   solo en ciclo (`SENSOR_AUSENTE`, únicamente `temp_camara` y `pres_camara`). `temp_2_camara`
   (sensor de líquidos) y los de empaque no tienen alarma de ausencia en ciclo.
4. **Sin alarmas por exceso en ciclo**: chaqueta fría/sobrecalentada y presión de cámara fuera de
   banda solo se alarman en PREPARADO/PREPARACION; en ciclo la chaqueta solo reporta
   `SUMINISTRO_VAPOR`.
5. **Motivo de falla en texto libre**: la UI, el ticket y los correos solo pueden distinguir la
   causa interna leyendo `motivo_fallo`; no es clasificable ni traducible por id (relevante para
   i18n).
6. **Sin registro central**: renombrar una alarma exige `grep` del literal en `src/` (instanciación,
   `clear()` y UI). `ui/window/main_window.py` (tkinter) deriva el texto legible del id con
   `replace("_", " ").title()`.
7. **Anuncios de voz**: la rama `anuncios-voz` (worktree) no está integrada en `dev`; este catálogo
   no incluye su mapeo alarma→audio.

## 8. Alarmas propuestas (NO IMPLEMENTADAS)

Propuestas para discutir; ninguna existe en el código. Varias coinciden con el alcance de la Parte B
del rediseño (`docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md` §1: cobertura
nueva y separación de los CIC por causa). Prioridad sugerida con la regla vigente
(tipo → prioridad).

| ID propuesto | Tipo sugerido | Motivo |
|---|---|---|
| `ESTERILIZACION_TEMP_ALTA` / `_TEMP_BAJA` / `_PRES_ALTA` / `_PRES_BAJA` | FALLA | Separar las 4 causas hoy en `motivo_fallo` para voz, i18n y estadística. |
| `ESTERILIZACION_TIMEOUT_F0` | FALLA | Ya existe como texto en `motivo_fallo`; elevarlo a id. |
| `CALENTAMIENTO_TIMEOUT` / `CALENTAMIENTO_NO_ESTABLE` | FALLA | Ídem. |
| `PRECALENTAMIENTO_TIMEOUT` | FALLA | Ídem. |
| `PREVACIO_TIMEOUT_VACIO` / `PREVACIO_TIMEOUT_PRESION` | FALLA | Ídem. |
| `DESCOMPRESION_TIMEOUT` | FALLA | Ídem. |
| `SECADO_TIMEOUT_VACIO` / `SECADO_TIMEOUT_AIRE` | FALLA | Ídem. |
| `SENSOR_AUSENTE_<SENSOR>` por sensor, incluyendo `temp_2_camara` en equipos con sensor de líquido | EMERGENCIA | Hoy una sola alarma para 2 sensores; falta cobertura del sensor de líquidos. |
| `SOBREPRESION_RECURRENTE_CAMARA` | FALLA | Prevista en el rediseño de admisión por chaqueta (`planeacion_alimentacion_camara_desde_chaqueta.md`); pendiente de implementar. |
| `CHAQUETA_FUERA_DE_BANDA` en ciclo | ALERTA | No hay supervisión de chaqueta durante el ciclo salvo suministro de vapor. |
| `IMPRESORA_DESCONECTADA` | ALERTA | Existen eventos de conectividad de impresora (spec 2026-07-07) que no pasan por `AlarmManager`; confirmar si deben hacerlo. |

## 9. Correspondencia con el diseño Parte A (códigos `ÁREA-NN`)

Fuente: `docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md` §4.3 (diseño aprobado en
chat; `state_machine/alarms/catalogo.py` **aún no existe** en `src/`). Niveles nuevos: AVISO
(ALERTA), ALARMA (FALLA), FALLO_CRITICO (EMERGENCIA). Este catálogo describe el código actual; al
implementarse la Parte A, los ids de la columna izquierda dejan de usarse.

**D9-2 (tanda 9):** SEN-01, SEN-03, SEN-06, SEN-07 y CIC-10 pasan de AVISO a ALARMA (FALLA en `/status`)
conservando su bloqueo y su despeje automático. Al ser ALARMA requieren reconocimiento: si la condición
desaparece sin reconocerlas, quedan como "resuelta sin reconocer" (no bloquean el inicio) hasta que se reconozcan.

| ID actual | Código Parte A | Nivel nuevo |
|---|---|---|
| `PARO_EMERGENCIA` | SIS-01 (desde U4 solo con paro real: entrada leída en 0) | FALLO_CRITICO |
| `FALLO_SUMINISTRO_ELECTRICO` | SUM-01 | FALLO_CRITICO |
| `SUMINISTRO_ELECTRICO` | SUM-02 | AVISO |
| `SUMINISTRO_AGUA_BOMBA` / `_AGUA_GENERADOR` / `_AIRE_COMPRIMIDO` | SUM-03 / SUM-04 / SUM-05 | AVISO |
| `SUMINISTRO_VAPOR` | SUM-06 | AVISO |
| `CHAQUETA_FRIA` / `CHAQUETA_SOBRECALENTADA` | PRE-01 / PRE-02 | AVISO |
| `PRESION_CAMARA_BAJA` / `PRESION_CAMARA_ALTA` | PRE-03 / PRE-04 | AVISO |
| `AGUA_RESIDUAL_CAMARA` | PRE-05 | AVISO |
| `TEMP_DRENAJE_ALTA` | PRE-06 | AVISO |
| `PUERTA_1_ABIERTA` / `PUERTA_2_ABIERTA` | PUE-01 | AVISO |
| `FALLO_PUERTA_n_ABIERTA` | PUE-02 | ALARMA |
| `FALLO_PUERTA_n_EMPAQUE` | PUE-03 | ALARMA |
| `ABRIENDO_MODO_SEGURO_x` / `CERRANDO_MODO_SEGURO_x` | PUE-04 / PUE-05 | AVISO |
| `ERROR_AI_<SENSOR>` | SEN-01 | ALARMA (antes AVISO; D9-2, tanda 9), bloquea, despeje automático |
| `SENSOR_AUSENTE` | SEN-02 | FALLO_CRITICO |
| `FALLO_PRECALENTAMIENTO` / `_PRE_VACIO` / `_CALENTAMIENTO` / `_ESTERILIZACION` / `_DESCOMPRESION` / `_SECADO` | CIC-01 … CIC-06 | ALARMA |
| `TIMEOUT_APERTURA_AUTOMATICA` / `APERTURA_AUTOMATICA_DENEGADA` | CIC-07 / CIC-08 | AVISO |
| `NO_HAY_CONEXION` | COM-01 ("Tarjeta de E/S desconectada" desde U4; solo sin puerto) | ALARMA |
| `FALLO_CONEXION` | COM-02 | FALLO_CRITICO |
| `CONFIGURACION_INVALIDA` | `CONFIGURACION_INVALIDA` (id conservado, tanda 2026-10-14) | ALARMA, bloquea, despeje manual |
| `OPERANDO_SIN_BD` | `OPERANDO_SIN_BD` (id conservado) | ALARMA, **no bloquea** (D-03, T8), despeje manual |
| `TARJETA_*` (11 ids de §2.2: 9 de E6 y 2 del enlace Modbus de la tanda 19), fuera de ciclo | mismos ids (conservados) | ALARMA, bloquea, se resuelven al completar el handshake |
| `TARJETA_*` en ciclo (`abortar_por_falla_io`) | **COM-03** con origen = id de la tarjeta (`COM-03\|TARJETA_WATCHDOG`) | FALLO_CRITICO, despeje manual; `fase_ciclo = "FALLO_IO"` |
| (nueva) | SIS-02 Historial no disponible | AVISO |
| (nueva, T8) | SIS-03 Respaldo del ciclo no disponible | AVISO, no bloquea, despeje manual |
| (nueva, M1 tanda 3) | SIS-04 Mantenimiento vencido | AVISO (baja prioridad), NO bloquea nunca un ciclo, despeje automático al registrar el mantenimiento. Alias en código: `MANTENIMIENTO_VENCIDO` |
| (nueva, B5 tanda 4) | SIS-05 Impresora no conectada | AVISO (baja prioridad), NO bloquea nunca un ciclo, despeje automático cuando una impresión tiene éxito. Solo se activa al arrancar si la impresora está habilitada (`data/impresora.json`) y Windows la reporta desconectada. Alias en código: `IMPRESORA_DESCONECTADA` |
| (nueva, R8 tanda 8) | SEN-09 Reasignación de entradas y salidas sin verificar | AVISO, **bloquea el inicio de ciclo**, despeje automático cuando el ingeniero verifica en OPCIONES › Opciones avanzadas la última función reasignada. Además del aviso, una condición en `AlarmManager.condiciones_bloqueo` mantiene bloqueado el inicio aunque la alarma se resuelva al reconocer una FALLA (la vigilancia la reactiva). |
| (tanda §1.1) | SEN-03 Sensor de temperatura sin señal | ALARMA (antes AVISO; D9-2, tanda 9), no bloquea el equipo (bloquea al iniciar un programa que lo use), despeje automático |
| (S1, tanda 8) | SEN-06 / SEN-07 Sensor de presión de cámara / chaqueta sin lectura fuera de ciclo | ALARMA (antes AVISO; D9-2, tanda 9), bloquea el inicio, despeje automático |
| (T5/S4) | CIC-10 Estado seguro detenido | ALARMA (antes AVISO; D9-2, tanda 9), no bloquea, despeje automático Acción según la causa (T10, tanda 10, D10-3): con la presión de cámara sin lectura (D9-1.4), motivo y acción dicen que sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro y piden revisar su conexión o llamar a servicio técnico (`catalogo.CIC_10_ACCION_SIN_PRESION`, i18n `alarmas.CIC-10.accion_sin_presion`, elegida por `alarmas_i18n.accion()`); con cualquier otra causa, la acción de siempre (sonda Principal). |
| (nueva, S9 tanda 9) | SEN-10 Presión de cámara incoherente con la puerta abierta | ALARMA, **bloquea el inicio de ciclo**, solo fuera de ciclo: puerta detectada ABIERTA y presión de cámara fuera de [atm − `rango_presion_atm`, atm + `rango_presion_atm`] 3 lecturas seguidas (tramas AI distintas); despeje automático solo con 3 lecturas coherentes con una puerta ABIERTA (al cerrar la puerta SEN-10 se mantiene y sigue bloqueando el inicio; revisión ★ SAF-02). Acción: calibración del sensor de presión, presión atmosférica de referencia o sensor de puerta (D9-1.6). |

**Integración (tanda 2026-10-14, T1):** la Parte A está unida a `dev-noche`; esta tabla ya describe el código.
La regla de la tanda "ningún id existente se renombra" se aplicó a los ids que la rama no había migrado:
los 9 de la tarjeta (11 desde la tanda 19), `CONFIGURACION_INVALIDA` y `OPERANDO_SIN_BD` quedan con su nombre
(`CODIGOS_CONSERVADOS` en `catalogo.py`). Los textos `alarmas.<ID>.{titulo, accion}` de `es.json`/`en.json`
duplican los del catálogo para los 9 de la tarjeta; la UI todavía muestra `titulo`/`descripcion` de `/status`.

Observación (histórica): el diseño Parte A no contempla `CONFIGURACION_INVALIDA` (alarma agregada al backend el
mismo periodo). Hay que asignarle código (¿`SIS-03`?) antes de implementar el catálogo central.
