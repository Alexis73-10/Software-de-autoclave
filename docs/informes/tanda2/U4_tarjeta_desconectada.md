# U4 — Tarjeta desconectada vs. paro de emergencia, alarmas sin bloqueo (19-oct-2026)

Instrucción: `docs/mis_plans/instruccion_claude_code_u4_tarjeta_desconectada.md` (insertada en la tanda 2 antes de S3).
Rama `tanda-2`, sin push.

**Antes de empezar:** S3a (plausibilidad de calibración) estaba implementada sin commit. Se apartó en
`git stash` (`stash@{0}`, "S3a tanda 2: plausibilidad de calibración (sin commit, apartada para U4)") con nota
en `estado.md`. La otra sesión de Claude que lleva S3 lo sabe y retoma con `git stash pop` al cerrar U4.

## 1. Causa raíz

`control_loop.py` publicaba un solo flag, `PARO_EMERGENCIA`, que es verdadero tanto con el botón pulsado
(entrada NC en 0) como sin datos de la tarjeta (sin enlace o trama DI vencida: D-16/A-3). La UI, SIS-01 y el
estado seguro leían ese mismo flag, así que con la tarjeta desconectada la pantalla decía "Paro de emergencia
activado", el panel de la campana se abría solo sin poder cerrarse (corrección SAF-01 de U1) y, al volver la
tarjeta, se pedía "Confirmar y llevar a estado seguro" sin que hubiera existido un paro. COM-01 ("No llegan datos
válidos…") y `TARJETA_SIN_TRAMA_VALIDA` podían salir juntas por la misma causa.

## 2. Qué cambió

### A. Estado de la tarjeta (backend)
- `SerialLink.puerto_presente()` (nuevo): True si el último escaneo encontró el puerto de la tarjeta y se pudo
  abrir. Se apaga si no hay puerto, si no abre, por error de lectura/escritura (cable quitado) o con `stop()`.
  **No** se apaga cuando el propio enlace cierra el puerto para reintentar (timeout de datos de 3 s o 10 líneas
  inválidas): la tarjeta sigue enchufada y es "sin tramas válidas". False antes del primer escaneo.
- `ControlLoop.estado_tarjeta` (nuevo), calculado en cada tick: `desconectada` (sin puerto presente),
  `ok` (enlace con handshake + DI vigente) o `sin_tramas_validas` (el resto: puerto abierto sin handshake, CRC
  malo, firmware incompatible, handshake fallido, DI vencida con enlace, primera DI pendiente). Falla cerrada:
  vale `desconectada` hasta el primer tick. Un enlace que no informa el puerto (dobles de prueba viejos) se
  deduce de la conexión.
- Publicado en `/status` como `estado_tarjeta` (valor desconocido → `desconectada`) y en `UiBridge.estadoTarjeta`
  (sin conexión con el backend o sin dato → `desconectada`).

### B. Seguridad intacta, causa separada
- Nuevo flag `PARO_REAL` (`EstadoAutoclave._flags_map`), lo fija `EmergencyStop.update()`: True solo si llega
  un valor leído y vale 0. `ControlLoop` pasa `None` sin enlace o con la DI no vigente, así que la DI inicial en 0
  que deja `_connect()` antes de la primera trama **no** es paro real.
- Carrera valor/edad de la DI (TMG-04 / SAF-01): el enlace fija la edad de la DI antes de notificar a `Units`, así
  que en el primer tick vigente de una conexión el valor podía ser aún el 0 de `_connect()`. Un 0 en ese primer
  tick cuenta como sin datos (bloquea igual, sin paro real); desde el segundo tick es dato. Además `_connect()`
  ahora notifica a `Units` la DI en cero, para que no conserve la DI de la conexión anterior (paro=1).
- `_disconnect` desde un error de escritura ya no marca el puerto como perdido (un `write_timeout` no prueba que
  se quitó el cable; el error de lectura sí) (TMG-06). `serial` y `_puerto_presente` se asignan juntos bajo
  `serial_lock` (SAF-06). Un fallo al evaluar el estado de la tarjeta no impide publicar el paro (SAF-05).
- `PARO_EMERGENCIA` (combinado) no cambia: los estados siguen con `apagar_por_paro()`, el inicio de ciclo, la
  apertura, el modo prueba, el cambio de ciclo y los endpoints siguen bloqueados igual. `camara_segura` y
  "NO ABRIR" no se tocaron (sin datos vigentes = no segura).
- SIS-01 solo con `PARO_REAL` en PREPARACION, PREPARADO, FALLA e HIBERNACION. En PREPARACION/PREPARADO, sin
  datos se resuelve SIS-01 (como cuando no hay paro). En FALLA/HIBERNACION nunca se resolvía solo (se libera al
  reconocer); ahí solo se evita activarlo sin datos.
- En CICLO, el aborto por el flag combinado mantiene el mismo protocolo (sin válvulas, `_paro_en_espera`,
  confirmación), pero si no es paro real se registra **COM-03** con causa `TARJETA_SIN_TRAMA_VALIDA`
  ("Sin datos vigentes de las entradas de la tarjeta.") en vez de SIS-01.
- Textos de rechazo del backend con el flag combinado (`/fault/reset`, `/safe-state/confirm`,
  `/cycle/acknowledge`, `/io/test/output`) y de `set_active_cycle`/`enter_test_mode`: sin paro real dicen
  "Sin datos válidos de la tarjeta de control…". Los códigos de rechazo no cambian.

### C. Alarmas y textos
- COM-01 (catálogo + `alarmas.COM-01` en es/en): "Tarjeta de E/S desconectada" / "No se detecta la tarjeta de
  control." / "Conecte la tarjeta (cable USB) y verifique su alimentación.". Solo con `desconectada`: en el
  flanco tras una conexión real; en el arranque, pasados 5 s seguidos (el arranque normal no la deja en el
  historial). Se resuelve al salir de `desconectada`.
- `TARJETA_SIN_TRAMA_VALIDA` conserva su texto. La del handshake la sigue reportando el enlace (solo corre con
  el puerto abierto). Nueva activación propia del `ControlLoop` por DI vencida con el handshake hecho, fuera de
  la ventana de 1,5 s de la primera DI; se resuelve al volver la DI (salvo que el handshake la haya reportado
  entretanto: entonces la resuelve el siguiente handshake).
- Con el puerto presente y sin conexión (handshake en curso, o reintentando tras el cierre por timeout de datos),
  pasados 5 s también se activa la propia, sin esperar a que falle el handshake (revisión SAF-07). La propia por
  DI vencida pide 3 ticks seguidos (TMG-03) y solo se resuelve al volver a `ok` (o al pasar a `desconectada`), no
  porque el enlace cierre el puerto para reintentar (TMG-01).
- Un evento de handshake fallido que llega con la tarjeta ya `desconectada` (handshake cortado por quitar el
  cable) se descarta con registro en el log: la causa es la desconexión, que ya da COM-01 (TMG-02).
- Exclusión: al pasar a `desconectada` se resuelve `TARJETA_SIN_TRAMA_VALIDA` (y se quita de las alarmas de
  tarjeta pendientes); al dejar `desconectada` se resuelve COM-01. Probado con el `AlarmManager` real.
- SIS-01: "La entrada del paro está en 0. Si el botón no está pulsado, revisar… (NC)." (ya no dice "o sin datos").
- `sistema.seguridad_desconocida` (fila SIN_CONEXION, que es la caída del **backend**, no de la tarjeta):
  "Sin conexión con el equipo: no se puede verificar el paro ni la cámara. NO ABRIR.". El texto pedido para la
  tarjeta va en la fila nueva `sistema.tarjeta_desconectada`: "Tarjeta desconectada: no se puede verificar el
  paro ni la cámara. NO ABRIR." (y `tarjeta_sin_datos` para el puerto presente sin datos). **DECISIÓN SIN
  CONFIRMAR U4-1:** la instrucción pedía reescribir `seguridad_desconocida`, pero esa fila sale cuando la UI no
  llega al backend; se dejaron dos filas distintas para no decir "tarjeta" cuando lo caído es el backend.

### D. Estado seguro y reconexión
- `ProtocoloEstadoSeguro.update()`: con el flag combinado siempre pausa (sin avanzar, ticks seguros a 0), pero
  solo con `PARO_REAL` marca `requiere_confirmacion` y registra `paro_activado`. Al volver los datos sin paro
  real, el protocolo sigue solo.
- Si ya se marcó la confirmación por un paro real, perderse la tarjeta después no la borra.
- La recuperación de arranque con cámara no segura sigue pidiendo confirmación (no depende del paro).

### E. UI
- `PanelNotificaciones.qml`: sin `bloqueado`, sin apertura automática; se abre con la campana y se cierra con
  normalidad. Agrupado por nivel del catálogo (D3) con cabecera y contador: **Emergencia / Fallas** (sin
  conexión, tarjeta desconectada o sin datos, paro real, estado seguro pendiente con el botón, en curso, y las
  alarmas EMERGENCIA; desplegado), **Alarmas** (NO ABRIR y las FALLA) y **Avisos** (modo prueba, ALERTA e
  INFORMATIVO); estos dos plegados por defecto y al cerrar. Nivel desconocido → Emergencia.
- `PanelModal.qml`: se quitó `bloqueado` (ya no lo usa nadie).
- `SeccionEstadoSeguro.qml` es el componente compartido (propiedad `grupo`: `emergencia`/`alarma`/`aviso`/todos),
  con filas nuevas `filaTarjetaDesconectada` y `filaTarjetaSinDatos`. `paroActivo` del puente = paro real.
  NO ABRIR no se repite si ya hay una fila de sin datos (todas dicen NO ABRIR).
- Preciclo, `zonaAlarmas`: la sección va fija arriba, fuera de la lista (no se desplaza con ella; revisión SAF-04) (todas las filas, con el botón "Confirmar y
  llevar a estado seguro" inline, sin sesión); debajo, el modelo de alarmas. El aviso superior dice "Tarjeta de
  control desconectada. Los valores mostrados no están actualizados." (o "no envía datos válidos") cuando
  corresponde; "Sin conexión con el controlador…" sigue siendo la caída del backend. La lista atenuada sin
  conexión ya no atenúa las filas de seguridad.
- Ciclo en curso: no tiene tarjeta de alarmas en su diseño. **DECISIÓN SIN CONFIRMAR U4-2:** las filas del grupo
  Emergencia (sin conexión, tarjeta, paro real, estado seguro) se superponen a la gráfica mientras duren
  (`tarjetaSeguridadCiclo`, PROVISIONAL sin diseño). NO ABRIR (permanente durante el ciclo) y el modo prueba (no
  existe en ciclo) quedan en el panel. El aviso de la gráfica también avisa la tarjeta desconectada/sin datos.
  Un aviso crítico cierra la gráfica a pantalla completa, que tapaba la tarjeta y la campana (revisión SAF-02).
- Insignia de la campana: roja y parpadeante con paro real o confirmación pendiente; roja fija con tarjeta
  desconectada, sin datos o sin conexión con el backend; amarilla con el estado seguro en curso.
- `Main.qml`: la vuelta a la pantalla principal desde una pantalla sin campana (login, cambio de clave, nuevo
  usuario) sigue con el paro **real** o la confirmación pendiente; la tarjeta desconectada ya no la provoca.
- Nada de lo anterior toma toques fuera de su botón: no bloquea la navegación ni la barra inferior.
  **DECISIÓN SIN CONFIRMAR U4-3:** se conserva el freno de U1 (TMG-02) en `abrirConfiguracion`/`abrirNuevoUsuario`
  con el paro **real** o la confirmación pendiente: el avatar no lleva a una pantalla sin campana mientras dure
  (desde ahí no se vería el paro). Con la tarjeta desconectada ya no frena nada.

**Sustitución de la corrección SAF-01 (Alto) de U1.** El panel bloqueado era la garantía de que el paro y la
confirmación se vieran sin tocar la campana. La instrucción U4 lo retira; la garantía pasa a ser: (1) la tarjeta de
alarmas de Preciclo con las filas y el botón inline, (2) la superposición en Ciclo en curso, (3) la insignia roja
parpadeante y (4) la vuelta automática a la principal desde pantallas sin campana con paro real o confirmación
pendiente. Aviso de la otra sesión (revisor de S3a) recogido aquí.

## 3. Tabla de casos

| Caso | Salidas | Inicio / apertura | Alarmas | Fila UI | Confirmación de estado seguro |
|---|---|---|---|---|---|
| Arranque sin tarjeta | apagadas (la máquina no corre sin enlace) | bloqueados, NO ABRIR | COM-01 a los 5 s, una vez | Tarjeta desconectada (roja fija) | no |
| Desconexión fuera de ciclo | apagadas | bloqueados | COM-01 en el flanco | Tarjeta desconectada | no; al reconectar, sin paro real, el estado seguro (si lo había) sigue solo |
| Puerto presente sin tramas / CRC malo / firmware incompatible | apagadas | bloqueados | `TARJETA_SIN_TRAMA_VALIDA` u otra del handshake; nunca COM-01 | Tarjeta sin datos | no |
| DI vencida con enlace, fuera de ciclo | ALL_OFF por el flag combinado | bloqueados | `TARJETA_SIN_TRAMA_VALIDA` (propia); sin SIS-01 | Tarjeta sin datos | no |
| Desconexión en ciclo | protocolo de fallo actual (sin válvulas con el flag combinado) | — | COM-01 + COM-02 tras 5 s (sin cambios) | Tarjeta desconectada | sí, igual que hoy (`_paro_en_espera` del ciclo) |
| DI vencida en ciclo (enlace hecho) | mismo protocolo | — | COM-03 causa `TARJETA_SIN_TRAMA_VALIDA` (antes SIS-01) + `TARJETA_SIN_TRAMA_VALIDA` propia | Tarjeta sin datos | sí, igual que hoy |
| Paro real (DI vigente = 0) | ALL_OFF | bloqueados | SIS-01 | PARO DE EMERGENCIA (roja parpadeante) | sí, al soltarlo |
| Paro real + desconexión (o DI vencida) | apagadas | bloqueados | SIS-01 queda activa (no se resuelve por perder datos); COM-01 o sin tramas | Tarjeta desconectada | sí, se conserva la que dejó el paro |

## 4. Pruebas

Primero en rojo: `tests/test_u4_tarjeta_desconectada.py` (71) y `tests/test_u4_puente_tarjeta.py` (7):
`EmergencyStop` (combinado vs. real), `puerto_presente` (sin escanear, sin puerto, abre, no abre, timeout de
datos, líneas inválidas, error de lectura, error de escritura, `stop`), `estado_tarjeta` en cada caso, firmware
incompatible, DI inicial 0 al conectar sin paro real, paro real + desconexión, COM-01 de arranque una vez,
puerto presente nunca da COM-01, COM-01/`TARJETA_SIN_TRAMA_VALIDA` excluyentes (doble y `AlarmManager` real),
DI vencida con enlace, salidas apagadas sin SIS-01 en los 4 estados, SIS-01 con paro real, COM-03 en ciclo,
estado seguro sin confirmación por falta de datos y con confirmación por paro real, textos de rechazo,
`/status`, y el puente.

QML: `tests/test_t7_avisos_qml.py` reescrita (el panel no se abre solo, se cierra con el paro, grupos y
contadores con alarmas de cada nivel, filas de tarjeta, insignia, pliegue al cerrar, botón inline con clic real
en la sección compartida, sin `bloqueado`), `tests/test_u1_seguridad_navegacion_qml.py` (la tarjeta
desconectada no saca del login; el paro real vuelve a Preciclo con la fila del paro en su tarjeta de alarmas,
panel cerrado; la confirmación pendiente con el botón en Preciclo).

Pruebas existentes ajustadas a la nueva semántica (donde simulaban "paro" con solo `PARO_EMERGENCIA`, ahora
también `PARO_REAL`): `test_alarmas_falla_hibernacion`, `test_ciclo_alarmas_fallo`, `test_e1_paro_emergencia_nc`,
`test_preparacion_alarm_wording`, `test_io_endpoints`, `test_s2_cycle_select`, `test_t5_estado_seguro`,
`test_historial_alarmas` (título nuevo de COM-01) y los dobles de UI que daban `True` a todo flag salvo
`PARO_EMERGENCIA` (`test_main_menu_principal_qml`, `test_navegacion_ciclo_en_curso`,
`test_navegacion_sesion_qml`, `test_opciones_qml`, `test_ui_qml_app`, `test_u2_navegacion_qml`).

Suite completa (`python -m pytest -q -p no:cacheprovider`): 3497 en verde y 1 fallo
(`test_t7_ui_seguridad.py::test_modo_prueba_paro_y_estado_seguro`, otro doble que simulaba el paro solo con
`PARO_EMERGENCIA`); corregido y vuelto a correr ese archivo: 11/11. Total 3498 en verde, 7 min 12 s.
Ojo: la suite corrió sobre el árbol compartido, que tenía R1 (retiro de tkinter) de la otra sesión **sin
commit** y S3a apartada en stash; el número no es comparable directamente con el 3413 de S2.

## 5. Revisores

**safety-reviewer** — sin hallazgos Altos. Confirmó que sin datos no se habilitan salidas, inicio, apertura ni
salida del estado seguro (todo sigue en el flag combinado) y que un paro real seguido de desconexión conserva la
confirmación. Hallazgos y qué se hizo:
- SAF-01 (Media), carrera valor/edad de la DI → corregido (primer 0 enmascarado + notificación en `_connect`).
- SAF-02 (Media), la gráfica a pantalla completa tapaba los avisos → corregido (se cierra con un aviso crítico).
- SAF-03 (Baja), SIS-01 se resolvía al perder datos tras un paro real → corregido (no se resuelve por eso).
  Queda: con la tarjeta perdida la fila de la UI pasa a "Tarjeta desconectada" (no se puede afirmar paro); SIS-01
  sigue en la lista de alarmas.
- SAF-04 (Baja), las filas se desplazaban con la lista → corregido (fijas arriba).
- SAF-05 (Baja), excepción antes de publicar el paro → corregido (try/except).
- SAF-06 (Baja), asignación fuera de lock → corregido.
- SAF-07 (Baja), puerto presente sin alarma hasta que falle el handshake → corregido (alarma a los 5 s).
- Pregunta sobre los frenos de `Main.qml` → DECISIÓN SIN CONFIRMAR U4-3.

**timing-auditor** — todo con `time.monotonic()`. Hallazgos:
- TMG-01 (Media), alarma propia resuelta al cerrar el puerto por timeout → corregido.
- TMG-02 (Media), alarmas falsas de un handshake cortado por desconexión → corregido (se descartan).
- TMG-03 (Media), oscilación de la alarma con la vigencia de la DI → corregido (debounce de 3 ticks para la
  alarma; la vigencia del paro sigue fallando cerrada al instante).
- TMG-04 (Media) = SAF-01 → corregido.
- TMG-05 (Baja), reconexión completa entre dos ticks sin que el lazo la vea: **pendiente**. El caso requiere
  que caída + escaneo + handshake ocurran en < 0,5 s; su efecto sería una alarma de sin tramas inmediata. Se
  resolvería con un contador de conexión en `SerialLink`.
- TMG-06 (Baja), `write_timeout` tomado como cable quitado → corregido. El puerto ocupado por otro programa sigue
  dando `desconectada` (la instrucción define "puerto cerrado" como desconectada).
- TMG-07 (Baja), `_di_vigente()` se evalúa varias veces por tick y los dos flags se escriben por separado:
  **pendiente**, solo visual y dura un tick.
- TMG-08 (Baja), `_puerto_presente` sin lock respecto de `port_open`: cubierto en parte por SAF-06; el resto es
  una lectura incoherente de un tick, sin efecto en la seguridad.

## 6. Pendiente de verificación en banco

- Quitar y poner el cable USB con el equipo en PREPARADO: COM-01 sola, fila "Tarjeta desconectada", insignia roja
  fija, sin "Paro de emergencia"; al reconectar, sin pedir confirmación.
- ESP32 alimentado por USB con la tarjeta de E/S sin 24 V (si el firmware no habla): `TARJETA_SIN_TRAMA_VALIDA`
  sin COM-01.
- Pulsar el paro: SIS-01, fila del paro, insignia parpadeante; soltarlo: botón en la tarjeta de alarmas de
  Preciclo.
