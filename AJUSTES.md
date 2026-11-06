# AJUSTES (tanda «llenado de fases», rama llenado-fases)

## 2026-10-31 · Paso 2 backend / revisión · Endurecer el LLF de progreso_ciclo (hallazgo 1, BAJA)
- Se pidió: que el bloque LLF de `armar_progreso`/`fraccion_fase` no pueda tumbar el endpoint (un int gigante como 10**400 pasa `_segundos_validos` y `float()` lanza OverflowError).
- Decidió: revisor (Opus); director.
- Cambio: nuevo `_segundos_llf` (conversión a float finito o None) usado solo por el LLF; `fraccion_fase` lo usa y el cálculo por fase de `armar_progreso` va en try/except (fraccion=None, referencia_s=None ante error). `_segundos_validos`, `restante_s`, `resultado`, `fase_terminacion` y `terminacion` no cambian. Invariante: ningún estado distinto de «completada» da fraccion > 0.90.
- Archivos: `src/autoclave/core/runtime/progreso_ciclo.py`.

## 2026-10-31 · Paso 2 backend / revisión · Pruebas faltantes del revisor
- Se pidió: (a) entradas extremas del conteo propio, (b) barrido de estados y caso esterilización 0/420, (d) normalizar_progreso con fallida/interrumpida/activa y 1.0, (e) endpoint con `context.estado` MagicMock real.
- Decidió: revisor (Opus); director.
- Archivos: `tests/test_llf_fraccion_fases.py`, `tests/test_llf_dominio_fraccion.py`, `tests/test_backend_ciclo_en_curso_endpoints.py` (la prueba (e) vive allí por usar su fixture `entorno`).

## 2026-10-31 · Hallazgos aceptados / no corregidos
- Hallazgo 3: `float(_tiempo_seg)` antes de escribir el restante de exposición; despreciable. Aceptado.
- Hallazgo 4: el simulador no pasa `total_exposicion_s`, así que allí la esterilización activa muestra 0.0; fuera del alcance de la tanda. Aceptado.
- Hallazgo 5: los atributos de exposición quedan con valor viejo tras cierres de `CicloState` hasta el reset de la siguiente esterilización; sin efecto (el conteo propio exige estado «activa»). Aceptado.

## Ajuste: tope efectivo en QML (revisión, hallazgo 2)
- Qué: `CirculoFaseLiquido.qml` usa `_topeEfectivo = Math.min(tope, 0.90)`; el enlace ya no puede subir el tope (HAZ-LLF-01).
- Decidió: revisor; aplicó: director.

## Hallazgo fuera de alcance (no corregido)
- `tiempo_restante` (restante_s) lanza OverflowError con un entero gigante en `exposicion_restante_s` y TypeError con referencias None. Preexistente, ajeno a esta tanda; queda para otra.

## 2026-10-30 — Instalación por automatización (rama automatizacion-instalacion)

- **Revisión A+B+C (M2, B1, B2, B4, B5):** decidió el director tras el informe del revisor; cambios en `activacion_v2.py`, `profile.py`, `tests/helpers/codigo_doble.py`, `backend/rutas/historial.py`. B3 (`machine_id` fuera del sello) y B6 (intentos) se dejaron documentados.
- **Revisión D+E (7 arreglos):** decidió el director; implementó un implementador (PDF, pantallas, `puente_instalacion.py`, i18n).
- **Rotulado del PDF en automatización:** Cristian delegó la redacción al director («cambialo a tu criterio»); queda «Automatizado por Especifika S.A.S.», pendiente de confirmación regulatoria.
- **Fallo de `test_v8b_textos`:** `elide` en 3 QML contradecía la regla D8-5.4; el director los cambió por `HorizontalFit`/`Escala.fuenteMinima`.
- **Cuelgue atribuido a la migración v12:** descartado (la prueba pasa sola; fue contención al correr en paralelo).

## 2026-11-02 · Dashboard de Reportes, etapa H (revisión de seguridad)

- **Ajuste H-1 (MEDIA):** un ciclo ya cerrado (con `resultado`) que espera CONFIRMAR se tomaba como «activo»; el día salía «En curso» o «Sin operación» y ocultaba el fallo. Plan: REP-07 (activo = sin resultado Y ciclo activo del equipo). Decidió: revisor H / director. Cambio: `_ciclo_activo` devuelve el id solo si la fila no tiene resultado (`backend/rutas/reportes.py`); el ciclo cerrado cuenta como intento real y entra en N(D).
- **Ajuste H-2 (MEDIA):** con total 0 la tarjeta Éxito decía «0%» / «0 de 0» y una comparación «−100 pp» en rojo. Plan: REP-03. Decidió: revisor H / director. Cambio: con total 0 (actual o anterior) valor «—» y sin comparación; la minigráfica omite los días sin ciclos (`ui_qml/domain/reporte_dashboard.py`).
- **Ajuste H-3 (MEDIA):** «Enviar consolidado» en Año daba 422 (`/cycle/list` no aceptaba `anio`) y el umbral de confirmación (300) superaba el máximo del envío (200). Plan: REP-12. Decidió: revisor H / director. Cambio: `/cycle/list` acepta `anio` (`backend/rutas/historial.py`); en `Pantallas/Reportes.qml` el umbral de confirmación pasa a 100 y por encima de `maxConsolidado` (200 = `MAX_CICLOS_CONSOLIDADO`) se muestra el aviso «demasiados ciclos» sin pedir confirmación. DECISIÓN SIN CONFIRMAR (100 y 200 por medir en el banco).
- **Ajuste H-4 (BAJA):** `fecha` sin tope (9999-12-31 / 0001-01-01) daba 500. Plan: §8 validación. Decidió: revisor H / director. Cambio: `fecha` acotada a 2000-01-01..2100-12-31 con 422 en `/report/dashboard|calendar|day-cycles|summary|failures`, `POST /report/summary/print` y `/cycle/list` (`utils/periodos.py` FECHA_MINIMA/FECHA_MAXIMA, `rutas/reportes.py`, `rutas/historial.py`).
- Pruebas: `tests/test_rep_correcciones_revision.py`.

## 2026-11-02 · Lag de la UI: sondeos síncronos de Entradas/Salidas y Calibración atmosférica

- **Se pidió:** quitar el lag intermitente de la UI causado por dos controladores que hacían `SesionVentana.enviar` (HTTP síncrono con join de hasta 5 s) cada 1 s en el hilo de la GUI, duplicando el `/status` que ya mantiene `UIServiceBackend`; emitir las señales solo si los datos cambian (los Repeater recreaban todos los delegados cada segundo). Escrituras sin cambios.
- **Decidió:** el usuario aprobó; encargo del director.
- **Cambio:**
  - `EntradasSalidasController.actualizar()` ya no llama a `GET /status`: lee el caché de `UIServiceBackend` con el nuevo lector `status_vigente()` (sin red). Sin servicio, sin conexión, caché vacío, error al leer o `/status` con más de 3 s (`ANTIGUEDAD_MAX_S`) = mismo trato que el fallo de `/status` de antes («Sin datos», sin presión ni avisos de corte). `cambioDatos` se emite solo si cambia algo visible (listas, presión de cámara, avisos, enlace, estado de máquina, rol).
  - `CalibracionAtmController`: el estado de la ventana no está en `/status`, así que el `GET /maintenance/atm-calibration` sigue, pero en un hilo de trabajo (resultado por señal; un solo GET en vuelo). `datosChanged` solo si el estado cambió. Una respuesta de sondeo que llega después de una orden se descarta (contador de generación) para no pisar el estado confirmado por la orden (`midiendo` bloquea la navegación).
  - `UIServiceBackend`: registra la instancia del proceso (`servicio_activo()`, `instalar_servicio()` para pruebas), guarda el instante del último `/status` y expone `status_vigente()` → `(status, conectado, edad_s)`.
  - Salidas del modo prueba, entrar/salir/keepalive del modo prueba, calibración de sensores y órdenes de la calibración atmosférica: sin cambios (síncronas, confirmadas por el backend).
- **Archivos:** `src/autoclave/ui_qml/controllers/entradas_salidas_controller.py`, `src/autoclave/ui_qml/controllers/calibracion_atm_controller.py`, `src/autoclave/cliente/ui_service_backend.py`; pruebas `tests/test_es_controlador.py`, `tests/test_calibracion_atm_controller_sondeo.py` (nueva), `tests/test_p1_salidas_momentaneas_qml.py`, `tests/test_t17_s4_opciones_qml.py`, `tests/banco/p9_capturas_banco.py` (doble del caché de `/status`).

## 2026-11-02 · Corrección tras revisión: sondeos de Entradas/Salidas y Calibración atmosférica

- **Qué falló (revisión):** (1, MEDIA) `UIServiceBackend` guardaba cuándo LLEGÓ el `/status`, no cuándo salió la petición: un `/status` pedido antes de entrar/salir del modo prueba o de accionar una salida seguía «vigente» y la pantalla mostraba un tick viejo (parpadeo del modo prueba, salidas libres al salir). (2, MEDIA) el hilo del sondeo de Calibración atmosférica llamaba `SesionVentana.enviar`, que ante 401 / 429 `usuario_bloqueado` cerraba la sesión (temporizadores, `SessionManager.logout`, señales) fuera del hilo de la GUI; además `_llamar_con_plazo` registraba «Espera lenta en la GUI» para ese hilo. (3, BAJA) emisión desde el hilo sobre un controlador ya destruido. (4, BAJA) el pedido pendiente relanzaba `cargar()` después de `desactivar()`. (5, BAJA) `stop()` no quitaba el servicio del registro del proceso.
- **Decidió:** encargo del director.
- **Cambio:**
  - `UIServiceBackend._fetch_status` guarda el instante monotonic de envío (`_t_envio_status`); `status_vigente()` → `(status, conectado, edad_s, t_envio)`. `stop()` quita el servicio del registro si es el activo.
  - `EntradasSalidasController`: tras la respuesta del backend a `POST /io/test/enter|exit` y `PATCH /io/test/output/*` fija `_t_orden` (monotonic, al volver la respuesta y no al enviarla, para cubrir también un `/status` pedido mientras la orden estaba en curso); un `/status` del caché con envío `<= _t_orden` se trata como «aún sin dato nuevo» (se conserva lo ya mostrado). Caché vencido o desconectado sigue dando «Sin datos». Una fuente que no da el instante de envío (3 valores) se acepta como antes.
  - `CalibracionAtmController`: el token y la comprobación de conexión se toman en el hilo de la GUI; en el hilo de trabajo solo va la petición HTTP (`SesionVentana._peticion`); el 401 / 429 se trata en el slot (hilo de la GUI) con el nuevo `SesionVentana.tratar_rechazo_sesion()`, extraído de `enviar` (misma lógica). El hilo retiene el controlador solo por `weakref` y comprueba `shiboken6.isValid` antes de emitir. El pendiente solo se relanza con el temporizador activo.
  - `SesionVentana._llamar_con_plazo`: «Espera lenta en la GUI» solo en el hilo principal.
  - Escrituras (salidas, modo prueba, calibración): sin cambios, síncronas y confirmadas por el backend.
- **Archivos:** `src/autoclave/cliente/ui_service_backend.py`, `src/autoclave/ui_qml/controllers/entradas_salidas_controller.py`, `src/autoclave/ui_qml/controllers/calibracion_atm_controller.py`, `src/autoclave/ui_qml/sesion_backend.py`; pruebas `tests/test_es_controlador.py`, `tests/test_calibracion_atm_controller_sondeo.py` y el doble de `tests/banco/opciones_qml_banco.py` (`_peticion`; `esperar()` en tramos de 10 ms porque `QTest.qWait` no suelta el GIL y la respuesta del hilo llegaba tarde: `test_o2f_calibracion_atm_qml` fallaba de forma intermitente).

## 2026-11-02 · Paso 2, fase 1: envíos asíncronos y cambio optimista (piloto Usuarios)

- **Se pidió:** que la UI no se congele por HTTP síncrono en el hilo de la GUI y que ciertos cambios de configuración se vean al instante y se reviertan si el backend falla. Fase 1 del paso 2, piloto en OPCIONES › Usuarios.
- **Decidió:** el usuario aprobó el diseño; encargo del director. Decisiones adoptadas: plazo asíncrono 5 s (`PLAZO_S`); los textos de reversión van arriba (banda de error de la pantalla); bloquear «Atrás» con cambios pendientes no aplica aún.
- **Cambio:**
  - `SesionVentana.enviar_async(...)` con `_DespachadorEnvios`: el hilo de trabajo solo hace la petición y deja el resultado en una `SimpleQueue`; un QTimer de 20 ms la vacía en la GUI, vigila el plazo (reloj monotónico) y entrega: trato de 401 / 429 (`tratar_rechazo_sesion`), dueño vivo (`weakref` + `shiboken6.isValid`) y `al_terminar`. Plazo vencido → `backend_no_responde`; la respuesta tardía va a `al_tardio` o al log. Hasta 8 peticiones en vuelo (la novena se rechaza con `error_generico` y log). `cerrar_local()` sube `_gen_sesion`: lo lanzado antes entrega `sesion_invalida` sin volver a cerrar. `cancelar_envios(dueno)`. Sin conexión, sin token o tope: entrega diferida (nunca dentro de la llamada). `enviar` síncrono sin cambios. Funciones de módulo `enviar_async(sesion, ...)` (con dobles de solo `enviar`, resultado en el acto) y `cancelar_envios(sesion, dueno)`.
  - Nuevo `ui_qml/cambio_optimista.py` (`CambioOptimista`, Python puro).
  - `UsuariosController`: activo/desactivado de usuarios y operadores optimista con reversión; restablecer contraseña y agregar operador asíncronos con «Guardando…» y la acción bloqueada mientras está pendiente; carga asíncrona con `cargando`. Interfaz aditiva: `pendientes`, `cargando`, `cambioResuelto(clave, ok, mensaje)`, `mensajeRevertido`. Cancela sus envíos al destruirse.
  - `OpcionesUsuarios.qml`: teclados de contraseña temporal y de operador en modo acción (`abrirAlfanumericoAccion`); se quitan los dos `Connections` a `terminado`.
  - i18n es/en: `opciones.cambio_revertido`, `opciones.cambio_sin_confirmar`, `opciones.guardando`, `opciones.cargando`.
- **Archivos:** `src/autoclave/ui_qml/sesion_backend.py`, `src/autoclave/ui_qml/cambio_optimista.py`, `src/autoclave/ui_qml/controllers/usuarios_controller.py`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesUsuarios.qml`, `src/autoclave/i18n/es.json`, `src/autoclave/i18n/en.json`; pruebas `tests/test_envio_async_sesion.py` y `tests/test_cambio_optimista.py` (nuevas).

## 2026-11-02 · Corrección tras revisión de la fase 1 (M1, M2, M3, B1)

- **Qué falló (revisión):** (M1, MEDIA) un PUT de activo que tardaba más del plazo pasaba a «verificando»; si el GET de relectura llegaba antes de que el backend aplicara el PUT, leía el valor viejo y el cambio se revertía mostrando desactivado a un usuario que sí quedó activo; la respuesta tardía solo iba al log. (M2, MEDIA) `_entregar`/`_tardio` convertían en `sesion_invalida` cualquier respuesta de una generación anterior de sesión, incluso un 200, y el cambio optimista revertía contra el estado real. (M3, MEDIA) el texto `opciones.cambio_sin_confirmar` decía que se mostraba el valor guardado en el equipo, y al revertir por SIN_CONFIRMAR no se había leído el equipo. (B1, BAJA) los 409 `ultimo_ingeniero`, `autodesactivacion`, `cuenta_sistema` y `operador_existe` caían en `error_generico` por no ser códigos conocidos.
- **Decidió:** encargo del director.
- **Cambio:**
  - M1: `UsuariosController._enviar` acepta `al_tardio` y `sesion_backend.enviar_async` (función de módulo) lo reenvía; `_lanzar_activo` pasa un `al_tardio` que llama a `cargar()` (la marca de `CambioOptimista` protege lo aún pendiente).
  - M2: con generación de sesión distinta, un resultado `ok` se entrega tal cual (sin `tratar_rechazo_sesion`) y solo los no-ok pasan a `sesion_invalida`; igual en la respuesta tardía.
  - M3: texto es «No se pudo confirmar el cambio; vuelva a cargar para ver el estado real.» y su equivalente en inglés; además `_al_revertir` por SIN_CONFIRMAR lanza `cargar()`.
  - B1: `_CODIGOS_USUARIOS` en `sesion_backend`, reconocidos solo en `/usuarios` y `/operadores` (como `_CODIGOS_REASIGNACION`, RSB-04); los textos ya estaban en `_MENSAJES` del controlador.
- **Archivos:** `src/autoclave/ui_qml/sesion_backend.py`, `src/autoclave/ui_qml/controllers/usuarios_controller.py`, `src/autoclave/i18n/es.json`, `src/autoclave/i18n/en.json`; pruebas en `tests/test_envio_async_sesion.py`.

## 2026-11-02 · Paso 2, fases 2 a 5 (UI sin HTTP síncrono en el hilo de la GUI)

- **Qué se pidió:** el usuario aprobó lanzar las fases 2 a 5 del paso 2 (lag de la UI por HTTP síncrono; la UI debe actualizarse primero y revertir si el backend no responde o responde otra cosa).
- **Decidió:** el director, sobre el diseño del arquitecto y con las reglas de seguridad fijadas desde el inicio; correcciones tras dos revisiones (revisor Opus).
- **Cambio:**
  - Fase 2 (parámetros del equipo): idioma, unidades e impresora optimistas con reversión (solo en el selector; el efecto global de idioma y unidades solo tras el 200). `PATCH /global_params` y reset asíncronos SIN optimismo: valor vigente con «Guardando…» y edición bloqueada hasta el 200 y la relectura (solo `/system_params`); relectura fallida → fila «sin confirmar». `fijarImpresoraYReiniciar` sigue síncrono.
  - Fase 3 (parámetros de ciclo, SAF-05): `PATCH /cycle/parameter` asíncrono sin optimismo, con la conciliación íntegra (modo leído antes del PATCH, arrastres, `valor_anterior_esperado`, DEU-01, `err_sin_respuesta`); entradas mostradas optimistas con reversión; lecturas asíncronas. `guardarSensores` (roles de sensores) sigue síncrono.
  - Fase 4: correo, intervalos de mantenimiento y programa habilitado optimistas con reversión; correo de prueba y registrar mantenimiento asíncronos «Guardando…»; `crear`/`duplicar`/`borrar` programas síncronos.
  - Fase 5: lecturas de bitácora, fecha y hora, información del sistema, respaldo y carga de reasignación asíncronas con `cargando`; `exportar` asíncrono; `restaurar` y todas las escrituras de reasignación de E/S síncronas. Un error de lectura de respaldo conserva la última lista de unidades.
  - Corrección de la revisión: `Opciones.qml` bloquea cajón, Inicio, Atrás, Cerrar sesión y engranaje mientras un parámetro de ciclo o de equipo se guarda (`guardandoParametro`; un valor ya enviado no cuenta como «cambio sin guardar»; Cancelar deshabilitado). El bloqueo puede durar hasta ~15-20 s en el peor caso de tipo de carga (lectura previa, PATCH, relectura, conciliación). Entradas mostradas conservan la lista si el GET falla con un cambio pendiente. `ajuste.param` se refresca con la relectura.
  - Códigos de rechazo por ruta en `sesion_backend._CODIGOS_POR_RUTA` (`/email`, `/maintenance`, `/programas`, `/global_params`, `/language`, `/units`, `/printer/config`) con prueba `tests/test_t25_codigos_rutas_async.py`; textos nuevos `conectividad.err_archivo`, `opciones.mant_err_calibracion_en_curso`, `opciones.equipo_err_calibracion_en_curso` (es/en).
- **Archivos:** controladores `parametros_equipo`, `parametros_ciclo`, `conectividad`, `mantenimiento`, `manejo_ciclos`, `bitacora`, `fecha_hora`, `info_sistema`, `respaldo`, `reasignacion`; QML `Opciones`, `OpcionesParametrosEquipo`, `OpcionesParametrosCiclo`, `OpcionesConectividad`, `OpcionesMantenimiento`, `OpcionesManejoCiclos`, `OpcionesBitacora`, `OpcionesFechaHora`, `OpcionesInfoSistema`, `OpcionesRespaldo`, `OpcionesReasignacion`; `sesion_backend.py`; i18n es/en; pruebas `tests/test_f2_*`, `test_f3_*`, `test_f4_*`, `test_f5_*`, `test_t25_codigos_rutas_async.py`.
- **Pendiente:** verificación visual en el equipo (fila «sin confirmar», bloqueo de navegación con backend lento, píldoras «Guardando…»); entrada de riesgo en `docs/riesgos/registro_riesgos.md` (presentar un valor no vigente, SAF-05) y trazabilidad; solicitud de cambio formal (IEC 62304 8.2.1).

## 2026-11-04 · Fase 6 – corrección tras revisión

- **Qué falló (revisor Opus, NO APROBABLE):** C1 (crítico) un 200 tardío de `GET /calibration` de un sensor A, llegado con la pantalla de otro sensor C abierta, cambiaba la calibración del controlador a A y los puntos de C se escribían en A. M1 (mayor) con la salida del modo prueba sin confirmar, el botón de una salida sostenida encendida quedaba deshabilitado (sin forma de apagarla desde la UI). m1 un 200 tardío tras una RECHAZADA de la conciliación (no del backend) no se notificaba; m2 el gancho de cierre de sesión se ponía solo al resolver la entrada; m3 una petición que no salió no pasaba por `al_rechazo` (un `sesion_invalida` en la salida no contaba como hecha); m6 la relectura activa puede ser de otra sesión.
- **Quién decidió:** revisor Opus + director. No se tocó el backend.
- **Qué se cambió:** C1 contador de generación del GET de calibración (solo el 200 del último pedido fija `_calibracion`); slot `calibracionEs(segmento, sensor)`; la pantalla no abre con `operacion.confirmada_tarde` ni si la calibración cargada no es la del sensor pedido; `aplicarPuntos`/`restaurar` reciben segmento y sensor de la pantalla y rechazan en local si no coinciden (mensaje `operacion.sin_confirmar`, sin clave i18n propia). M1 propiedad `pruebaSinConfirmar` (notify) y `puedeApagar` en la tarjeta: el apagado de una sostenida encendida se ofrece con modo prueba o con dudas; encender sigue exigiendo `salidasHabilitadas`. m1 `rechazo_conciliado` en `OperacionCritica` (afecta también a los demás controladores que la usan). m2 gancho puesto al iniciar la entrada, quitado ante rechazo o inactivo y no registrado si la sesión cambió en vuelo. m3 `no_salio` pasa por `al_rechazo`. m6 solo comentario (/status no publica el dueño).
- **Archivos:** `src/autoclave/ui_qml/operacion_critica.py`, `src/autoclave/ui_qml/controllers/entradas_salidas_controller.py`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesCalibracionSensor.qml`; pruebas `tests/test_f6_operacion_critica.py`, `tests/test_f6_modo_prueba_async.py`, `tests/test_f6_calibracion_sensor_async.py`.
- **Segunda revisión (MAYOR-1..3, MENOR-4..9):** MAYOR-1 cada `_Op` lleva un id único y un `grupo` (por defecto su clave); `ultimo_id`, `id_de`, `contexto_de` y, mientras corren `al_ok` o el desenlace, `id_resuelta`/`contexto_resuelta` (kwargs nuevos `grupo`, `al_ok_tardio`, `contexto`; firmas y señales anteriores sin cambio). Un 200 tardío con otra operación vigente del mismo grupo no ejecuta `al_ok` ni emite `confirmada_tarde`: solo log y relectura. Reasignación usa grupo único y guarda el cuerpo del 200 por id; Manejo de ciclos lleva su contexto por operación; las órdenes de calibración atmosférica, grupo común. MAYOR-2 `conciliar_fabrica(leido, antes)`: con el archivo dañado, reinicio pendiente o fábrica ya guardada al pedir, sin confirmar; exige `error_archivo` vacío. MAYOR-3 relectura que no coincide tras no-respuesta = SIN_CONFIRMAR (aplicar, verificar, fábrica, roles de sensores), así el 200 tardío se procesa. MENOR-4 alta de usuario: GET /usuarios antes del POST (5 s) y relectura que confirma solo si el usuario (nombre, rol, activo) no estaba; sin lista previa, sin confirmar (el 401 de esa lectura deja el alta rechazada por sesión inválida). MENOR-5 duplicar sin lista cargada (o cargando) no concilia. MENOR-6 `habilitado:<n>` excluido con el borrado de <n> en vuelo y al revés; `impresora` ↔ `impresora_reinicio`; restaurar ↔ exportar (también en `OpcionesRespaldo.qml`). MENOR-7 el 200 tardío de una orden atm ya no aplica su cuerpo: relee. MENOR-8 las impresiones de Mantenimiento bloquean la navegación (como mucho 15 + 5 s). MENOR-9 cada puerta es un proceso propio (`ui_qml/app.py`), así que `Operaciones.bloqueaNavegacion` no bloquea la otra pantalla; sin cambio. Archivos: `operacion_critica.py`, controladores de reasignación, parámetros del ciclo, manejo de ciclos, parámetros del equipo, respaldo y calibración atmosférica, `nuevo_usuario/puente.py`, `OpcionesRespaldo.qml`, `OpcionesMantenimiento.qml`, `OpcionesManejoCiclos.qml`; pruebas `tests/test_f6_*` correspondientes y `tests/test_nuevo_usuario_puente.py`.
- **Tercer ciclo (H1–H5, último permitido):** H1 el alta de usuario lleva su contexto por operación (`contexto` de `iniciar`; desenlace con `contexto_resuelta`, conciliación por el cierre); un desenlace o un `confirmada_tarde` de un alta que no es la actual (otra en lectura previa, vigente o enviada después) solo va al log: ni `usuarioCreado` ni `guardadoResuelto`. `guardadoResuelto(estado, errores, mensaje, alta)` y propiedad `altaActual`; `NuevoUsuario.qml` ignora un `confirmada_tarde` con alta en curso o de otro número. H2 un fallo al pedir la lista previa devuelve rechazo local y no deja el alta en curso. H3 slot `abandonarPreparacion` (llamado en `Component.onDestruction` de `NuevoUsuario.qml`): cerrada la pantalla durante la lectura previa, el POST no sale. H4 `OpcionesCalibracionSensor.qml` no borra los puntos con `confirmada_tarde` de `cal_puntos` (no hay manejador de `cal_restaurar`). H5 contador `_gen_tardia` en la calibración atmosférica: solo se aplica la última relectura tras un 200 tardío (una orden nueva también la invalida); `_fase_esperada` sin estado «antes» queda igual. Prueba nueva que vigila la forma completa de `aplicarPuntos`/`restaurar` (Python por AST, QML por texto). `operacion_critica.py` sin cambios. Archivos: `nuevo_usuario/puente.py`, `NuevoUsuario.qml`, `OpcionesCalibracionSensor.qml`, `calibracion_atm_controller.py`; pruebas `tests/test_f6_nuevo_usuario_async.py`, `tests/test_nuevo_usuario_puente.py`, `tests/test_nuevo_usuario_qml.py`, `tests/test_f6_calibracion_atm_async.py`, `tests/test_f6_calibracion_sensor_async.py`, `tests/test_f6_sin_enviar_sincrono.py`.
- **Pendientes de decisión de Cristian tras la fase 6:** M2 backend (generación en `PATCH /io/test/output` ON, ver HAZ-UIA-06); P1/P2/O2 de los `comandos_*` (ver registro de riesgos, Fase 6); menores de la tercera revisión: `NuevoUsuario.qml` (un tardío de la alta anterior puede navegar una pantalla recién abierta; propuesta `altaEnviada` en el QML), lectura previa del alta sin revisar la generación de sesión, `OpcionesCalibracionAtm.qml:47-49` (`atm_confirm` confirmado tarde cierra `dialogoConfirmar` reabierto) y hueco `n != 3` en `test_f6_sin_enviar_sincrono` para restaurar de 2 argumentos; solicitud de cambio formal IEC 62304 (8.2.1); verificación visual y de banco en el equipo (modo prueba con salida sin confirmar o backend caído, restaurar con backend lento, alta con backend lento).

## 2026-11-04 · Modo prueba: sin cierre de sesión por inactividad y corte de 5 min solo sin salidas ON

- **Qué se pidió:** (1) en modo prueba (`/status.test_mode_active`) la UI no cierra la sesión por inactividad y renueva el token con el keepalive existente; al salir el plazo se reinicia. (2) El corte de 5 min de Entradas/Salidas «solo aplica si no hay salidas ON. Estado desconocido: si no se puede leer el estado de las salidas, el corte aplica igual (falla cerrada). No toca: el corte de 90 s del backend (`backend/rutas/io.py`), el keepalive de 30 s ni los cierres por abandonar o cambiar de sección.»
- **Decidió:** el usuario.
- **Cambio:** `SesionVentana.modoPrueba` (propiedad con setter, enlazada desde `Main.qml` a `puente.modoPrueba`); `_revisar_inactividad` no cierra y renueva por `_renovar_en_servidor` mientras sea True; al pasar a False reinicia `_ultima_actividad`. En `OpcionesEntradasSalidas.qml`, `hayAlgunaSalidaOn(salidas)` (solo `encendida === true` cuenta) y `plazoInactividadMs`: con salida ON el temporizador se rearma, si no (todas OFF, null o sin lista) corta.
- **Archivos:** `src/autoclave/ui_qml/sesion_backend.py`, `src/autoclave/ui_qml/qml/Main.qml`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml`; pruebas `tests/test_modo_prueba_sin_cierre_sesion.py`.
- **Pendiente:** riesgo residual (equipo en modo prueba con salidas ON sin operador: lo acota el corte de 90 s del backend); prueba de banco.

## 2026-11-04 · PREPARACION/PREPARADO: la chaqueta ya no se corta por sensores ajenos (revierte A-2.2/P4)

- **Qué se pidió:** que un sensor ajeno caído (drenaje, empaque, cámara, Referencia) o un suministro ajeno (agua, aire) ya no apague `vapor_chaqueta` en PREPARACION/PREPARADO: la chaqueta tarda en calentar y, fría, el drenaje no se enfría y puede sobrecalentarse. La chaqueta solo se corta por causas propias: `pres_chaqueta` sin lectura o en 0, paro, estado seguro, vaciado de chaqueta, suministro eléctrico caído y suministro de vapor (SUM-06). `vapor_camara` sigue OFF con el supervisor en falla; el gate de listo/inicio y PREPARACION→PREPARADO siguen exigiendo el supervisor. Además: (a) en estado seguro activo corre el lazo de drenaje (`agua_intercambiador` ya no queda con la última orden), sin chaqueta ni venteo; (b) corte único D-CHQ (`presion_max_chaqueta_control`) también en PREPARACION/PREPARADO; (c) el ConfirmadorApagado de la chaqueta ya no se reinicia en las salidas seguras del supervisor.
- **Decidió:** el usuario. FALLA (`falla.py`) queda fuera.
- **Archivos:** `src/autoclave/state_machine/states/preparacion.py`, `src/autoclave/state_machine/states/preparado.py`; pruebas `tests/test_adenda_estados.py`, `tests/test_adenda_decisiones.py`, `tests/test_preparacion_chaqueta_independiente.py` (nueva).
- **Pendiente:** actualizar `tests/test_e0_lecturas_invalidas.py` (afirma el comportamiento anterior) y `tests/test_preparado_chaqueta.py` (su config doble devuelve 5 para todo, con lo que el corte D-CHQ queda en 300 kPa); riesgo y trazabilidad; prueba de banco.

## 2026-11-04 — Pruebas y riesgo de la chaqueta independiente (PREPARACION/PREPARADO)

- **Qué:** `tests/test_e0_lecturas_invalidas.py` (con `temp_drenaje` caído la chaqueta ya no se apaga: `vapor_chaqueta_off` no se llama) y `tests/test_preparado_chaqueta.py` (el doble de config devuelve 375 para `presion_max_chaqueta_control`, 5 para el resto); entrada HAZ-PRE-01 en `docs/riesgos/registro_riesgos.md`. Sin cambios en `src/`.
- **Decidió:** el usuario. Prueba de banco pendiente.
- **Archivos:** los cuatro citados.

## 2026-11-04 - Ticket de arranque tras la animación y apertura del .exe

- **Pedido y decisión (usuario):** (3.1) el ticket de arranque a veces imprimía antes de que la UI arrancara; la impresión sale ahora solo al terminar la animación de arranque (opción B). (3.2) apertura lenta del .exe: solo cambios seguros.
- **3.1:** `POST /arranque/interfaz-lista` (sin token, idempotente, pasa la compuerta 503) completa la etapa `preparando_interfaz` y activa `RegistroArranque.interfaz_lista`; `latido_y_ticket` arranca el latido al quedar operable y el ticket espera ese evento con tope de 75 s (`TOPE_INTERFAZ_S`), pasado el cual imprime igual. La pantalla de la puerta 1 avisa con `progresoArranque.avisarInterfazLista()` (hilo, reintentos).
- **3.2:** `exe_unico.py` ya no importa `autoclave.ui_qml.app` (constante `BACKEND_URL` propia); el backend (limpieza + Popen + vigilancia) se prepara en un hilo en paralelo con el lanzamiento de las pantallas; `lanzador.log` registra la hora de cada lanzamiento.
- **Archivos:** `backend/main.py`, `backend/server.py`, `backend/rutas/sistema.py`, `backend/arranque/registro.py`, `devices/printer/arranque_equipo.py`, `ui_qml/bridge/progreso_arranque.py`, `ui_qml/app.py`, `exe_unico.py`, `docs/informes/tanda15/base/{rutas,openapi}.json`, `tests/test_arranque_interfaz_lista.py`, `tests/test_r1_arranque_equipo.py`, `tests/test_t15_rutas_equivalentes.py` (docstring).

## 2026-11-04 — Correcciones del revisor: suministro eléctrico de la chaqueta (PREPARACION/PREPARADO)

- **Qué:** `_sin_suministro_electrico` falla cerrado como A-9: sin la DI `suministro_electrico` (o en 0) = sin suministro, además del flag `FALLO_SUMINISTRO_ELECTRICO`. `_vapor_vaciado_permitido` exige suministro eléctrico: el vaciado EN_CURSO ya no vuelve a encender `vapor_chaqueta` sin él. Pruebas nuevas: DI ausente, vaciado con flag/DI eléctrica caída, vaciado con supervisor en falla, alternancia estado seguro → normal → supervisor con el `ConfirmadorApagado`.
- **Decidió:** el usuario (a pedido del revisor). Sin cambios de alarmas ni de `ConfigManager`.
- **Archivos:** `src/autoclave/state_machine/states/preparacion.py`, `src/autoclave/state_machine/states/preparado.py`, `tests/test_preparacion_chaqueta_independiente.py`.
- **Pendiente:** `tests/test_vaciado_chaqueta.py` (9 pruebas) necesita `"suministro_electrico": 1` en sus dobles (`_preparado` y `_maquina`).
## 2026-11-04 · Modo prueba: sin cierre de sesión por inactividad y corte de 5 min solo sin salidas ON

- **Qué se pidió:** (1) en modo prueba (`/status.test_mode_active`) la UI no cierra la sesión por inactividad y renueva el token con el keepalive existente; al salir el plazo se reinicia. (2) El corte de 5 min de Entradas/Salidas «solo aplica si no hay salidas ON. Estado desconocido: si no se puede leer el estado de las salidas, el corte aplica igual (falla cerrada). No toca: el corte de 90 s del backend (`backend/rutas/io.py`), el keepalive de 30 s ni los cierres por abandonar o cambiar de sección.»
- **Decidió:** el usuario.
- **Cambio:** `SesionVentana.modoPrueba` (propiedad con setter, enlazada desde `Main.qml` a `puente.modoPrueba`); `_revisar_inactividad` no cierra y renueva por `_renovar_en_servidor` mientras sea True; al pasar a False reinicia `_ultima_actividad`. En `OpcionesEntradasSalidas.qml`, `hayAlgunaSalidaOn(salidas)` (solo `encendida === true` cuenta) y `plazoInactividadMs`: con salida ON el temporizador se rearma, si no (todas OFF, null o sin lista) corta.
- **Archivos:** `src/autoclave/ui_qml/sesion_backend.py`, `src/autoclave/ui_qml/qml/Main.qml`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml`; pruebas `tests/test_modo_prueba_sin_cierre_sesion.py`.
- **Pendiente:** riesgo residual (equipo en modo prueba con salidas ON sin operador: lo acota el corte de 90 s del backend); prueba de banco.

## 2026-11-04 - Ticket de arranque tras la animación y apertura del .exe

- **Pedido y decisión (usuario):** (3.1) el ticket de arranque a veces imprimía antes de que la UI arrancara; la impresión sale ahora solo al terminar la animación de arranque (opción B). (3.2) apertura lenta del .exe: solo cambios seguros.
- **3.1:** `POST /arranque/interfaz-lista` (sin token, idempotente, pasa la compuerta 503) completa la etapa `preparando_interfaz` y activa `RegistroArranque.interfaz_lista`; `latido_y_ticket` arranca el latido al quedar operable y el ticket espera ese evento con tope de 75 s (`TOPE_INTERFAZ_S`), pasado el cual imprime igual. La pantalla de la puerta 1 avisa con `progresoArranque.avisarInterfazLista()` (hilo, reintentos).
- **3.2:** `exe_unico.py` ya no importa `autoclave.ui_qml.app` (constante `BACKEND_URL` propia); el backend (limpieza + Popen + vigilancia) se prepara en un hilo en paralelo con el lanzamiento de las pantallas; `lanzador.log` registra la hora de cada lanzamiento.
- **Archivos:** `backend/main.py`, `backend/server.py`, `backend/rutas/sistema.py`, `backend/arranque/registro.py`, `devices/printer/arranque_equipo.py`, `ui_qml/bridge/progreso_arranque.py`, `ui_qml/app.py`, `exe_unico.py`, `docs/informes/tanda15/base/{rutas,openapi}.json`, `tests/test_arranque_interfaz_lista.py`, `tests/test_r1_arranque_equipo.py`, `tests/test_t15_rutas_equivalentes.py` (docstring).

## 2026-11-04 — SUM-02 (suministro eléctrico) también en PREPARACION

- **Qué:** `preparacion.verificar_suministros` emite SUM-02 con el mismo patrón que PREPARADO (A-9: DI `suministro_electrico` ausente o en 0 = sin suministro; se omite si el perfil no tiene la entrada); el supervisor falla y bloquea PREPARACION→PREPARADO. Chaqueta sin cambio (sigue OFF con el eléctrico caído). Misma clave sin origen: no hay doble alarma entre PREPARACION y PREPARADO.
- **Decidió:** el usuario.
- **Archivos:** `src/autoclave/state_machine/states/preparacion.py`, `tests/test_preparacion_sum02_electrico.py`, `docs/riesgos/registro_riesgos.md` (HAZ-PRE-01).
- **Pendiente:** `tests/test_preparacion_suministro.py` y `tests/test_e1_supply_inputs.py` (3 pruebas) suponen que PREPARACION no vigila el eléctrico; hay que ajustar sus dobles.
## 2026-11-04 — SUM-02 también con el flag FALLO_SUMINISTRO_ELECTRICO (PREPARACION/PREPARADO)

- **Qué:** `verificar_suministros` de PREPARACION y PREPARADO activa SUM-02 con `_sin_suministro_electrico()` (flag `FALLO_SUMINISTRO_ELECTRICO` o DI ausente/0), la misma condición que corta la chaqueta; antes, con el flag en True y la DI en 1, la chaqueta se apagaba sin alarma. Sin entrada en el perfil sigue sin vigilarse; misma clave SUM-02 sin duplicados; despeje automático con ambos restablecidos. Supervisor y gate sin otro cambio.
- **Decidió:** el usuario.
- **Archivos:** `src/autoclave/state_machine/states/preparacion.py`, `src/autoclave/state_machine/states/preparado.py`, `tests/test_preparacion_sum02_electrico.py`, `docs/riesgos/registro_riesgos.md` (HAZ-PRE-01).
## 2026-11-04 — Prueba roja de la suite antes de compilar alpha.15 (`test_t12_c05_chaqueta`)

- **Qué:** `test_preparado_sigue_usando_presion_chaqueta` fallaba tras el ajuste de la chaqueta: el doble de `config` (`get.return_value = 5`) recortaba `presion_max_chaqueta_control` a 300 kPa (340 kPa disparaba el corte D-CHQ) y faltaba la DI `suministro_electrico` (ahora falla cerrada). Solo cambió el doble de la prueba, no el código de control.
- **Decidió:** el director (dentro del alcance aprobado, mismo defecto de doble ya corregido en `test_preparado_chaqueta`).
- **Archivos:** `tests/test_t12_c05_chaqueta.py`.

## 2026-11-05 · Paso 4. ARQ · Correcciones del revisor de seguridad (H3 a H7, tanda 26)

Decidió en todos: el director con el revisor de seguridad (aprobado con condiciones). H1 (ARQ-04) y H2 (dependencia de la puerta 1) quedan para Cristian, sin tocar. Sin cambios de parámetros de proceso, fases, umbrales, periodo del lazo, MOD-08 ni de la liberación por las dos condiciones. Pruebas nuevas en `tests/test_t26_arq_revision.py`.

- **H3 (MEDIA) · ControlLoop fallaba abierto por defecto.** Pidió: que el punto 2f evalúe `is_set() is True` (como el middleware) y que el lazo sin `arranque_liberado` no nazca liberado. Cambio: sin argumento el lazo nace RETENIDO (evento sin fijar); 2f usa `is_set() is not True`. Hacerlo obligatorio rompía ~20 archivos de prueba igual que el defecto retenido, así que se eligió el defecto retenido y las pruebas que necesitan el lazo actuando pasan `arranque_liberado=evento_liberado()` (nuevo `tests/helpers/arranque_doble.py`). El único constructor de `src` (`BackendContext.construir_control`) ya pasa su evento sin fijar. Archivos: `src/autoclave/services/domain/loop/control_loop.py`, `tests/helpers/arranque_doble.py` y los 22 archivos de prueba que construyen `ControlLoop(` (solo el argumento y su import).
- **H4 (BAJA/MEDIA) · ALL_OFF de la retención marcado antes de enviarse.** Pidió: marcarlo solo con éxito y reintentar mientras siga retenido. Cambio: `_retencion_apagado` pasa a True solo si `reset_all_outputs()` no lanza y devuelve exactamente True; si no, se reintenta cada `_REINTENTO_ALL_OFF_RETENCION_S` = 1,0 s (monotonic); la reconexión del módulo reinicia la marca y el instante del último intento. Archivo: `control_loop.py`.
- **H5 (BAJA) · Vigilante del dueño del modo prueba fuera del lock.** Pidió: crearlo dentro de `_lock_hilo_arranque` y solo la primera vez. Cambio: la llamada se movió dentro del lock, tras lanzar el hilo de arranque (las llamadas siguientes salen antes); además `_iniciar_vigilancia_dueno_prueba` hace la comprobación y la creación bajo su propio lock. Archivos: `src/autoclave/backend/server.py`, `src/autoclave/backend/rutas/io.py`.
- **H6 (BAJA) · Sensores evaluados en la retención con la trama AI vencida.** Pidió: llamar `verificar_sensores` solo con la AI vigente. Cambio: `_tick_retenido` la llama solo con `_ai_vigente()` (mismo criterio de falla cerrada que el aire atmosférico y la coherencia puerta-presión); con la AI vencida no activa ni resuelve alarmas. Archivo: `control_loop.py`.
- **H7 (BAJA) · interfaz-lista aceptado antes de iniciar.** Pidió: rechazar si `iniciado` es False, sin impedir el aviso antes del fin de las etapas. Cambio: `POST /arranque/interfaz-lista` responde 409 `arranque_no_iniciado` sin enclavar si aún no llegó `POST /arranque/iniciar`; con el arranque iniciado se acepta aunque las etapas sigan (queda enclavado, como antes). La UI solo avisa con el backend terminado (y por tanto iniciado) y, tras un reinicio del backend (ARQ-D5), vuelve a pedir iniciar al ver la instancia nueva. Pruebas existentes actualizadas por el cambio de diseño (pedían 200 sin iniciar): `tests/test_t26_arq_retencion.py::test_lecturas_y_apagado_no_se_retienen` y `tests/test_arranque_interfaz_lista.py::test_ruta_pasa_la_compuerta_y_completa_la_etapa` (ahora marcan el arranque iniciado antes). Archivo: `src/autoclave/backend/rutas/sistema.py`.
- **Pruebas adicionales del revisor:** el latido (`marcar_tick_control`) se renueva en cada tick retenido aunque `verificar_sensores` lance; `/system/shutdown` estando retenido y un `interfaz-lista` posterior no reactivan nada (unitaria y con el simulador M31).

## 2026-11-05 · Paso 4. ARQ · contrato de GET /arranque
- Qué falló: `test_registro_arranque::test_instantanea_inicial_cumple_el_contrato` exigía el conjunto de claves anterior.
- Quién decidió: director. Qué cambió: la aserción incluye `instancia`, `esperandoIniciar` y `liberado` (ARQ-D1/D5); no se relajó ninguna otra. Archivo: `tests/test_registro_arranque.py`.

## 2026-11-05 · tanda26b · ARQ-04/H1 estado seguro de arranque
- Se pidió: aceptar que el venteo del estado seguro de arranque espere a la liberación, sin exceptuarlo de la retención.
- Decidió: Cristian (5-nov).
- Cambio: Sin cambio de código; se marca resuelto y aceptado.
- Archivos: `docs/informes/tanda26/R26_informe.md`, `docs/riesgos/registro_riesgos.md`, `CLAUDE.md`.

## 2026-11-05 · tanda26b · ARQ-07 texto del 409
- Se pidió: texto propio i18n es/en para `arranque_retenido` y `arranque_no_iniciado`.
- Decidió: Cristian (5-nov).
- Cambio: La UI muestra texto propio en lugar del error genérico, con prueba.
- Archivos: `sesion_backend.py`, `es.json`, `en.json`.

## 2026-11-05 · tanda26b · ARQ-06 latido de apagado
- Se pidió: que el latido arranque al quedar operable el contexto o al recibir `POST /arranque/iniciar`, lo primero que ocurra, sin esperar 120 s; sin actuar sobre salidas (tope de 75 s del ticket intacto).
- Decidió: Cristian (5-nov).
- Cambio: Cambia el momento de arranque del latido (`latido_y_ticket`).
- Archivos: `src/autoclave/backend/main.py` (`_esperar_primero`, `latido_y_ticket`), `src/autoclave/backend/arranque/registro.py` (`evento_iniciado`), `src/autoclave/devices/printer/arranque_equipo.py` (`iniciar_latido`); pruebas `tests/test_t26b_respuestas_cristian.py` y dobles de `iniciar_latido` en `test_r1_arranque_equipo.py` y `test_arranque_interfaz_lista.py` (sin tocar aserciones).
- Decisión del director, a confirmar por Cristian: se conserva un respaldo de 120 s si no llegan ni `iniciar` ni el contexto operable (el latido no toca salidas). También se cambió una palabra del docstring de `ControlLoop._tick_retenido` (sin cambio de lógica) al quitar la marca de ARQ-04.

## 2026-11-05 · tanda26b · H2 pantalla 2 sola
- Se pidió: confirmar que la pantalla 2 sola no pide iniciar y el equipo queda retenido.
- Decidió: Cristian (5-nov).
- Cambio: Sin cambio de código; dependencia de la puerta 1 aceptada.
- Archivos: `docs/informes/tanda26/R26_informe.md`, `docs/riesgos/registro_riesgos.md`.

## 2026-11-05 · tanda26b · SMP plazo de 3 s y residual
- Se pidió: aceptar el plazo de 3 s y el residual del botón «Activar» deshabilitado hasta ≈3,2 s tras un OFF aceptado sin reflejo.
- Decidió: Cristian (5-nov).
- Cambio: Sin cambio de código; se quita `DECISIÓN SIN CONFIRMAR` de ese punto.
- Archivos: `docs/riesgos/registro_riesgos.md`, `CLAUDE.md`, `docs/informes/tanda26/R26_informe.md`.

## 2026-11-05 · tanda26b · temp_alta cosmético
- Se pidió: que la frase «el menor entre el del equipo y el del programa» salga solo cuando haya programa seleccionado.
- Decidió: Cristian (5-nov).
- Cambio: Ajuste del texto del detalle de la alarma.
- Archivos: `src/autoclave/ui_qml/domain/detalle_aviso.py`.

## 2026-11-05 — Tanda 27, Parte A, A4 (ciclo de corrección 1 de 3)
- Falló: el revisor (opus) rechazó A4: el seguro de atrapamiento D-ES-16 solo se evaluaba al recibir la orden (antes la renovación de 500 ms lo reevaluaba); el apagado de la salida opuesta del enclavamiento no se comprobaba; residual AJ27-01 subestimado.
- Decidió: director, dentro del alcance de A4 (solo añade protección). NO se añade tope de tiempo (contradice la decisión «interruptor sin tope» de Cristian): queda como pregunta a Cristian en el informe.
- Cambio: vigilancia en el lazo en modo prueba (apaga cerrar_puerta_N si aparece atrapamiento/DI vencidas), y rechazo 409 si el OFF de la opuesta no se confirma. Archivos: services/domain/loop/control_loop.py, core/runtime/salidas_prueba_seguridad.py, backend/rutas/io.py, pruebas, docs/riesgos/registro_riesgos.md.

## 2026-11-05 — Tanda 27, depuración (ciclo de corrección 1 de 3)
- Falló: revisor (opus) rechazó el diff de depuración: test_t16_s5 llamaba a /cycle/history/{id}/readings, ruta retirada.
- Decidió: director (dentro del alcance). Cambio: quitar "readings" de la prueba; precisar 3 comentarios (ciclo.py, prevacio.py, respaldo.py). Commit de correcciones tras la revisión.

## 2026-11-06 — Tanda 28c, revisión de seguridad A14-M3 / A12
- **Paso del plan:** A14-M2 (corte de chaqueta por consigna en ESTERILIZACION).
- **Qué falló:** el revisor (H1, MEDIA) halló que `_tick_dos_estados` solo evalúa `_corte_consigna_chaqueta()` al pasar a ON; durante `t_on` largo (p. ej. 29,7 s) `vapor_chaqueta` podía seguir ON sin corte por consigna ni por pérdida de lectura.
- **Quién decidió:** director (corrección dentro del alcance aprobado).
- **Qué se cambia:** reevaluar el corte en cada tick con el PWM abierto, en modo chaqueta; prueba con `t_on` largo. Archivo: `src/autoclave/state_machine/cycle_phases/esterilizacion.py` y pruebas `tests/test_t28_a14_*`.
- **Pendiente de Cristian:** H2/AJ28C-05 (escape lento subatmosférico en prevacío, confirmar antirretorno en el P&ID) y H3 (defecto 101,3 kPa de presión atmosférica).

## 2026-11-06 — Tanda 28: A7 no se une (decidió Cristian)
- **Paso del plan:** A7 (rama `tanda28`, c27b1ebb y 4bbea3c5).
- **Qué se pidió/falló:** `dev` ya traía su propio A7 (158290df, tanda 27, `test_t27_a7_incoherencia_parametros.py`) y `tanda28` una segunda implementación independiente. Las reglas de validación son idénticas; difieren la API del detalle, los textos, el rango efectivo con valor incoherente y el manejo de la calibración atmosférica, y sus pruebas se contradicen (8 archivos en conflicto).
- **Quién decidió:** Cristian.
- **Qué se hizo:** `tanda28` NO se une; A7 queda como está en `dev`. Se comprobó que `dev` no tiene el defecto H1 de `tanda28`: `rutas/mantenimiento.py` devuelve `incoherente` y existe `calibracion_atm.motivo_incoherente`. La rama `tanda28` se conserva sin borrar.

## 2026-11-06 — Tanda 28: A9 marca persistente (decidió Cristian)
- **Paso del plan:** A9 (tanda28b). **Qué falló:** el revisor rechazó A9 (A9-R1, alta): un apagado o reinicio durante el protocolo de estado seguro dejaba el siguiente encendido sin protocolo.
- **Quién decidió:** Cristian (marca persistente). **Qué se cambió:** `core/runtime/marca_estado_seguro.py` (`data/estado_seguro_en_curso.json`, falla cerrada), `control_loop.py` (paso 5a), `context.py` (`hubo_ciclo_interrumpido`), pruebas ESS-07 sobre el camino real y `test_t28b_a9r_marca_estado_seguro.py` (commit 08a4e9cf).

## 2026-11-06 — Tanda 28: A13 M3, M4 y M5 (decidió Cristian)
- **Paso del plan:** A13 (tanda28b). **Qué falló:** el revisor rechazó A13: M3 (no se verificaba el vacío), M4 (NO ABRIR durante el secado), M5 (programa incierto tras ciclo interrumpido). M1, M2, B1, B2 y B4 los corrigió el director dentro del alcance.
- **Quién decidió:** Cristian (verificar el vacío, cumplir NO ABRIR, secar solo con programa del propio ciclo). **Qué se cambió:** commits 8c12a72d, 05cdc3a6, 929ccbcb, 352a3a00; `protocolo_fallo.py`, `camara_segura.py`, `context.py`, `control_loop.py`, `marca_estado_seguro.py`, parámetro `secado_tras_fallo_vacio_s`.

## 2026-11-06 — Unión de ramas: CIC-20 duplicada, renumerada a CIC-21
- **Paso del plan:** unión de `tanda28b` a `dev`. **Qué falló:** A12 (`dev`) y A13-M3 (`tanda28b`) definieron cada una una alarma CIC-20 distinta.
- **Quién decidió:** director. **Qué se cambió:** CIC-20 queda para A12 (bloqueante, descompresión del prevacío); la de A13 (aviso, secado sin vacío) pasa a CIC-21 en `catalogo.py`, `protocolo_fallo.py`, i18n es/en, pruebas y documentos. REQ de la tanda 28b renumerados: REQ-64 (A9) y REQ-65 (A13), tras REQ-60..63.

## 2026-11-06 — AJ28B-10: test_p9 relajado a las claves que le importan
- **Qué falló:** `test_p9_opciones_puertas_nc::test_parametros_grupo_es_propiedad_que_cambia_al_guardar` fijaba la lista exacta de claves de Cámara segura; A13 añadió `secado_tras_fallo_s` y `secado_tras_fallo_vacio_s`.
- **Quién decidió:** director. **Qué se cambió:** el test exige las dos claves de puertas en primer lugar y la presencia de las dos nuevas (no se relajó ninguna comprobación de seguridad).
