# Tanda 26 — ARQ: el backend no actúa hasta que la UI termina el arranque

Rama `tanda26`. Commits: `3980032e` (backend) y `dbb758f5` (UI). Sin push.
Riesgos (HAZ-ARQ-01/02), trazabilidad, `CLAUDE.md` y merge quedan para el director.

## 1. Qué se hizo por decisión

### ARQ-D1 — el backend abre el puerto y espera
- `backend/main.py`: con la espera activa ya no lanza `arrancar_cuando_escuche`; solo el latido. Sin espera (D7) se comporta como antes.
- Ruta nueva `POST /arranque/iniciar` en `backend/rutas/arranque.py` (router propio; `rutas/sistema.py` no se tocó porque ALD trabajaba en él). Sin token, en `server._RUTAS_SIN_COMPUERTA`, idempotente (`server.iniciar_arranque` con lock: 8 peticiones concurrentes lanzan un solo hilo). Responde `{"ok": true, "instancia": …}`.
- `GET /arranque` publica además `instancia` (uuid del proceso), `esperandoIniciar` y `liberado` (`RegistroArranque.instantanea`).
- UI: `IntroArranque._iniciar()` (primer cuadro dibujado) llama `progreso.introIniciada()`; `ProgresoArranqueBackend` manda `iniciar` solo con la intro empezada, mientras el backend diga `esperandoIniciar`, y solo en la puerta 1 (`app.py`).
- OpenAPI base actualizada de forma justificada: `docs/informes/tanda15/base/rutas.json` y `openapi.json` solo añaden `POST /arranque/iniciar` (comprobado: ninguna otra ruta difería); nota en el docstring de `tests/test_t15_rutas_equivalentes.py`.

### ARQ-D2 — control retenido desde la etapa 7
- `BackendContext.arranque_liberado` (`threading.Event`) se pasa a `ControlLoop(arranque_liberado=…)` en `construir_control`.
- **Punto único de retención:** `ControlLoop._tick`, paso 2f, justo después de la configuración inválida (2d) y antes de los pasos 2c–5 (puertas, máquina de estados), 6 (registro) y 7 (buzzer):
  ```python
  if not self.arranque_liberado.is_set():
      self._tick_retenido()
      return
  ```
  Ya corrieron: lectura y publicación (paso 1), paro de emergencia con su ALL_OFF en el flanco (paso 2), módulo E/S y eventos, suministro eléctrico (solo apaga). `_tick_retenido` manda un ALL_OFF por conexión (solo apaga; cubre salidas que dejara encendidas un backend anterior), evalúa las alarmas de lectura de sensores (`preparacion.verificar_sensores()`, solo activa/resuelve alarmas) y no acredita F0. El tick se completa, así que el latido de MOD-08 (`marcar_tick_control`) sigue igual; MOD-08 no se tocó.
- El evento no depende de la UI ni de temporizadores: solo lo fija la secuencia (abajo). Sin evento (pruebas, uso aislado) el lazo nace liberado, como antes.
- Rutas: con la compuerta activa, el contexto operable y el control retenido, el middleware de `server.py` responde **409 `arranque_retenido`** a `POST /cycle/start`, `/io/test/enter`, `/safe-state/confirm`, `/fault/reset`, `/doors/*` y `PATCH /io/test/output/*` (`retencion.RUTAS_ACTUADORAS`), en vez de dejarlas como orden diferida que se ejecutaría al liberar. Lecturas, sesión, configuración, `/outputs/reset`, `/cycle/abort` y `/system/shutdown` siguen disponibles. Falla cerrada: solo `is_set() is True` cuenta como liberado.

### ARQ-D3 — liberación por dos condiciones
- `secuencia.esperar_interfaz_y_liberar`: corre después de la etapa 8. (a) se cumple por construcción (un fallo bloqueante en 1–7 hace `return` antes; además se revisa `registro.fallo_bloqueante` al liberar) y (b) es `registro.interfaz_lista` (POST `/arranque/interfaz-lista`, enclavado: un aviso que llegue antes del fin de las etapas libera al terminar).
- UI: `avisarInterfazLista()` (fin de la intro) ya no manda el aviso directamente. El aviso sale solo con la respuesta del backend `terminado` de verdad (no el «sin módulo E/S» que deja terminar la intro), la vista al día (`_vista >= _cumplidas_reales()`) y la etapa `preparando_interfaz` aún pendiente; una vez por instancia del backend.
- Verificación de que la barra no se adelanta: `_publicar` ya limitaba la vista a `min(_vista, _cumplidas_reales())`; se probó con el objeto real (`test_la_barra_nunca_se_adelanta_al_backend`) y con `Main.qml` real offscreen (`test_main_qml_inicia_avisa_y_muestra_el_reinicio`, muestreo de `fraccionMostrada` cada 20 ms contra la fracción real: sin adelanto). Se encontró y corrigió ARQ-01 y ARQ-02 (abajo).

### ARQ-D4 — sin aviso, se espera sin tope
- A los `PLAZO_SIN_INTERFAZ_S` = 60 s (**DECISIÓN SIN CONFIRMAR**) se anota `ARR_SIN_INTERFAZ` en `preparando_interfaz` (`anotar_si_en_curso`, atómico frente a un aviso simultáneo) y en el log; el control sigue retenido con todo apagado; un aviso tardío libera. El tope de 75 s del ticket de arranque no cambió. `docs/catalogo_alarmas.md` lista `ARR_SIN_INTERFAZ` y `ARR_SENSORES`.

### ARQ-D5 — reinicio del backend con la UI abierta (DECISIÓN SIN CONFIRMAR)
- `ProgresoArranqueBackend(vigilar_reinicio=True)` (las dos puertas): al terminar el arranque pasa a «vigilancia» (GET `/arranque` cada 1 s). Un backend que espera `iniciar`, o una instancia nueva con la interfaz pendiente, pone `reiniciandoBackend = True`, vuelve al sondeo de 0,3 s sin la animación, la puerta 1 reenvía `iniciar` y, con las etapas terminadas, `interfaz-lista`. Un backend sin responder en vigilancia no cambia nada (se sigue mirando).
- `Main.qml` (**cambio mínimo, avisado**): un `Loader` `reinicioBackend` que muestra `Componentes/BarraReinicioBackend.qml` (título, detalle, barra real y etapa; solo `Colores`, sin `elide`, texto de etapa con `HorizontalFit`) mientras `introTerminada && reiniciandoBackend`. Bloquea los toques. Textos `arranque.reinicio_titulo`/`reinicio_detalle` en es/en.

### ARQ-D6 — sin perfil y asistente
- Sin cambios: sin perfil o con perfil inválido el lanzador (`exe_unico`) no arranca el backend y el asistente escribe la base directamente (`puente_instalacion`), así que no usa rutas detrás de la espera. `ProgresoArranqueSinPerfil` no tiene `introIniciada` (la intro lo comprueba con `typeof`). REI-01 sin cambios. `test_t18_arranque_instalacion.py` pasa.

### ARQ-D7 — `AUTOCLAVE_ESPERA_INTERFAZ=0` (DECISIÓN SIN CONFIRMAR)
- `retencion.espera_interfaz_activa()`: `=0` desactiva las dos esperas solo si `sys.frozen` es falso; en el compilado se ignora con aviso en el log. Sin espera, el evento se fija antes de construir el control (comportamiento anterior) y `main.py` arranca al escuchar.
- Pruebas existentes que arrancan el backend, ahora con la variable explícita: `test_secuencia_arranque.py` (fixture autouse), `test_endpoint_arranque.py::test_main_activa_la_compuerta…`, `test_arranque_sin_modulo_es.py`, `test_t19_integracion_modbus.py`, `test_t20_integracion.py`. Ninguna aserción se relajó; dos cambian por diseño: `verificando_sensores` deja de ser `ok` incondicional (ahora `degradado`/`ARR_SENSORES` con un doble sin lecturas) y el aviso de interfaz lista exige el backend terminado (`test_progreso_avisar_en_hilo_y_una_vez`).

### ARQ-D8 — etapa 8, verificación de sensores
- La §6 de `planeacion_arranque_y_modo_sin_bd.md` **no** tiene los criterios cerrados (umbrales «pendientes de medición», prueba de banco diferida, criterios de la trama serial). Se implementó lo mínimo, **DECISIÓN SIN CONFIRMAR**: `BackendContext.sensores_arranque_sin_lectura()` exige `presion_vigente` del lazo y lectura válida y distinta de 0 en el Principal del programa seleccionado, `pres_camara` y `pres_chaqueta` si el equipo la tiene (`presion_sin_lectura.canales_vigilados`). Plazo 10 s (§4.8). Degradable: `ARR_SENSORES` y log; nunca bloquea ni deja el equipo retenido (un error interno también degrada). Las alarmas propias de cada sensor (SEN-01, SEN-06/07) se evalúan durante la retención y las sigue dando PREPARACION. La etapa ya existía en la barra (peso 2) y ahora refleja una verificación real.

## 2. Hallazgos

| Id | Sev. | Hallazgo | Estado |
|---|---|---|---|
| ARQ-01 | Media | Con «sin módulo E/S» la intro salía con la barra llena (`enSalida ? 1`) aunque el backend no había terminado: la barra se adelantaba al backend. | Corregido: `IntroArranque` solo llena si `progreso.completo`. |
| ARQ-02 | Media | Con E/S que llegan después de que la repetición visible se detuvo, `_vista` quedaba atrás para siempre (publicado `terminado` volvía a False y el aviso nunca habría salido con D3). | Corregido: el temporizador de la vista se rearma con etapas nuevas; al terminar la intro la vista se descarta. |
| ARQ-03 | Alta | Antes de la tanda, desde la etapa 7 las rutas de puertas, modo prueba e inicio actuaban con la UI aún sin mostrarse. | Corregido: 409 `arranque_retenido` mientras dura la retención. |
| ARQ-04 | Media | El estado seguro de arranque (ciclo interrumpido con la cámara a presión) ya no ventea durante la retención: se procesa en el primer tick liberado. Con la UI que nunca avisa (D4) la cámara queda cerrada y presurizada, con todo apagado. | **DECISIÓN SIN CONFIRMAR**; probado que al liberar entra el protocolo (solo la lenta). Pregunta 1. |
| ARQ-05 | Baja | La liberación se observa por sondeo cada 0,1 s del evento de interfaz: hasta ~70 ms entre el aviso y la liberación (medido). | Aceptable; se puede pasar a `Event.wait`. |
| ARQ-06 | Baja | Si la UI nunca pide `iniciar`, el latido de `last_shutdown.json` arranca a los 120 s sin perfil (`latido_y_ticket`, plazo existente) y el ticket sale tras su tope sin perfil. | Sin cambio (comportamiento previo de un arranque no operable). Pregunta 3. |
| ARQ-07 | Baja | En «sin módulo E/S» el menú se ve con el control retenido: INICIAR, puertas y modo prueba responden 409 `arranque_retenido`, que la UI muestra como error genérico (el código no está en `sesion_backend.codigos_conocidos`). | Pendiente de texto propio si Cristian lo quiere. |
| ARQ-08 | Baja | La intro tiene un respaldo que arranca a los 1,5 s sin cuadro dibujado (pruebas sin pantalla); en ese caso `iniciar` sale sin ventana visible. | En el PC real el primer cuadro llega antes; se deja. |
| ARQ-09 | Info | `tests/test_i18n_linea_base.py::test_qml_i18n_igual_a_referencia_para_toda_clave` falla por `aviso_detalle.sin_conexion.titulo` (claves de ALD), no por las de ARQ. | Para el director/ALD. |

## 3. Mediciones con el simulador M31

`python tests/banco/t26_medicion_arranque.py --repeticiones 3` (backend real en proceso contra `M31Simulado`, UI de la puerta 1 simulada con el protocolo de `ProgresoArranqueBackend`: intro de 3,5 s, repetición a 0,35 s por etapa, salida de 1 s). Tiempos en s desde «UI visible» (`docs/informes/tanda26/arq_medicion.txt`):

| corrida | iniciar | etapas terminadas | interfaz-lista | liberado | PREPARACION | bobinas ON antes de liberar |
|---|---|---|---|---|---|---|
| 1 | 0,01 | 0,63 | 7,38 | 7,45 | 7,62 | 0 |
| 2 | 0,01 | 0,94 | 7,39 | 7,39 | 7,68 | 0 |
| 3 | 0,01 | 0,94 | 7,39 | 7,40 | 7,69 | 0 |

Etapas (corrida 1): instalación/procesos/servicios < 1 ms; configuración 0,026; calibración 0,024; base 0,041; módulos E/S 0,258; sensores 0,261; espera de la interfaz 6,75. Antes de liberar solo hubo 2 escrituras de bobinas, ambas de apagado (0F de la conexión y ALL_OFF de la retención). PREPARACION llega 0,2–0,3 s después de liberar (periodo del lazo 0,5 s, sin cambios). En el PC industrial hay que medir el arranque de las ventanas y el del .exe (pendiente de banco).

## 4. Pruebas

- Nuevas: `tests/test_t26_arq_retencion.py` (35: variable y `sys.frozen`, secuencia retenida, (a)+(b), fallo bloqueante sin liberación, `ARR_SIN_INTERFAZ` a los 60 s y 10 min sin liberar, `detener` corta la espera, etapa 8, rutas 409, falla cerrada, `ControlLoop` real con la planta simulada 10 s retenido sin ninguna salida ON con la cámara a presión y liberación con estado seguro, paro y SEN-06 publicados durante la retención, puertas/buzzer/máquina quietos, integración con el simulador M31) y `tests/test_t26_arq_ui.py` (8, incluida `Main.qml` real offscreen con el reinicio del backend).
- Corridas: las de arranque, ControlLoop, estado seguro, modo prueba, backend, integración Modbus, `test_t15_rutas_equivalentes` y `test_arquitectura_capas` (ver resumen de la entrega). No se corrió la suite completa.

## 5. Decisiones sin confirmar
1. 60 s para `ARR_SIN_INTERFAZ` (D4).
2. Reinicio del backend con la UI abierta: vigilancia cada 1 s, reenvío y capa de barra (D5).
3. `AUTOCLAVE_ESPERA_INTERFAZ=0` solo fuera del compilado (D7).
4. Etapa 8 mínima, plazo 10 s, degradable (D8).
5. Estado seguro de arranque diferido hasta la liberación (ARQ-04).
6. Rechazo 409 `arranque_retenido` de las rutas actuadoras (en vez de dejarlas pasar o diferirlas).

## 6. Preguntas para Cristian
1. ARQ-04: con un ciclo interrumpido y la cámara a presión, ¿se acepta que el venteo automático espere a que la UI termine el arranque (segundos en condiciones normales; sin tope si la UI no aparece)? La alternativa es exceptuar de la retención el protocolo de estado seguro de arranque (solo la lenta), lo que contradice «ninguna salida ON».
2. ¿Texto propio en la UI para `arranque_retenido` (ARQ-07) o basta el error genérico?
3. ARQ-06: ¿el latido de apagado debe arrancar aunque la UI nunca pida iniciar (hoy, a los 120 s)?
4. ¿Se confirma que la pantalla 2 sola (puerta 1 caída) no pida `iniciar`? Hoy el equipo queda retenido y la pantalla 2 muestra «Sin respuesta del sistema de control» a los 20 s y la barra de reinicio si el backend se reinicia.

## 7. Pendiente de banco (bloque T26)
Arranque real en el PC industrial con las dos pantallas (tiempos de ventana visible → `iniciar` → PREPARACION), reinicio por reasignación de E/S con las pantallas abiertas, y comprobar con el M31 real que ninguna bobina se enciende antes de la liberación.
