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
