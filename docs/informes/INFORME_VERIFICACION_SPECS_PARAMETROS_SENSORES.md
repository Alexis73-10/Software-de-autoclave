# Informe de verificación: especificaciones de parámetros del ciclo y sensores de temperatura

Fecha: 2026-10-02. Autor: Claude Code (análisis de solo lectura).
Especificaciones verificadas (borradores, sin trackear): `docs/mis_plans/planeacion_endurecimiento_backend_parametros.md` (en adelante "especificación 1") y `docs/mis_plans/planeacion_sensores_ciclo.md` ("especificación 2").
Complementa, sin repetirlos, a `INFORME_OPCIONES_POST_LOGIN.md` e `INFORME_OPCIONES_PARAMETROS_SENSORES.md` (hallazgos OPC-01 a OPC-18; OPC-19 a OPC-21 están definidos en las especificaciones). Los hallazgos nuevos continúan desde OPC-22.

Método: lectura del árbol de trabajo en disco. Los únicos comandos ejecutados fueron de consulta (git status/diff/log, grep, lectura de JSON y YAML, `python -c` para imprimir la versión de SQLite del intérprete). No se ejecutaron pruebas, no se abrió la base de datos, no se tocó hardware. Las afirmaciones marcadas como "inferencia de lectura" se deducen del código sin haberlas ejecutado.

---

## 0. Estado del repositorio

- Rama `dev`, HEAD `960647f` (feat(ui_qml): lanzador con el simulador o con el backend real).
- Modificados sin commit relevantes para este informe: `src/autoclave/backend/server.py`, `src/autoclave/services/domain/logging/db_manager.py`, `src/autoclave/ui_qml/app.py`, `src/autoclave/ui_qml/bridge/ui_bridge.py`, `src/autoclave/ui_qml/assets/textos/es.json`, `src/autoclave/ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml`, `src/autoclave/ui_pyside/main_window.py`, `src/autoclave/ui_pyside/views/admin_menu.py`.
- Nuevos sin trackear relevantes: `src/autoclave/ui_qml/controllers/login_controller.py`, `src/autoclave/ui_pyside/services/roles.py`, `src/autoclave/ui_pyside/services/validacion_usuario.py`, `docs/informes/` (incluye `inventario_sensores_y_base_de_datos.md`), las dos especificaciones y los dos informes previos.
- Ignorados por git (existen en disco): `installation_profile.json`, `data/` (base de datos, PID, `last_shutdown.json`), `build/`, `dist/*.exe`. Los `dist/*.bat` sí están trackeados.
- Desplazamiento de líneas en `server.py` [MODIFICADO SIN COMMIT]: el diff contra HEAD solo agrega imports (líneas 1-8) e inserta 93 líneas en 330-422 (`/cycle/summary`, `/cycle/list`, `/cycle/history/{id}/graph`). Las rutas de parámetros no cambian de contenido, pero hoy están en otras líneas que las citadas en la especificación 1: `PATCH /cycle/parameters` en `server.py:622-663` (en HEAD, 527-568), `PATCH /cycle/parameter` en `server.py:673-696` (HEAD 578-601), `_save_cycle_json` en `server.py:699-710` (HEAD 604-615). Las líneas 591-639 y 642-665 que cita la especificación 1 §3 no corresponden a ninguna de las dos versiones.

---

## A. Anexo A: sustitución de 0 por constante

### A.0 Semántica de `get_param` (base de todo el anexo)

`Cycle.get_param(*keys, default=None)` (`core/managers/cycle_manager.py:27-33`) [COMMITEADO] navega con `data.get(key, {})` y devuelve `data.get("value", default)`. Consecuencias verificadas:

- `default=` solo actúa si falta la clave o la hoja. Si la hoja existe con `value: 0`, devuelve 0 (el 0 llega a la lógica). Si la hoja existe con `value: null`, devuelve `None` y tampoco aplica el `default`.
- La forma `get_param(...) or <constante>` sustituye por la constante todo valor falso: 0, 0.0, `None` y `False`.
- `Cycle.set_param` (`cycle_manager.py:35-71`) es la única vía de escritura por HTTP y valida contra `min`/`max` del propio JSON. Un parámetro con `min` mayor que 0 en el JSON no puede recibir 0 por `PATCH /cycle/parameter`, pero sí por edición manual del archivo o por `PATCH /cycle/parameters` (tabla propia, ver B.2).

Rangos: los cinco perfiles (`cycles/factory/{bowe_dick,instrumental_134}.json`, `cycles/user/{bowe_dick,instrumental_121,instrumental_134}.json`) [COMMITEADO] tienen el mismo `min`/`max` para cada parámetro; se indica un solo rango salvo que se diga otra cosa.

### A.1 Lecturas con `or <constante distinta de 0>` (sustitución efectiva)

Estas son las que pide RB-05.4. Para cada una: archivo:línea, constante, rango JSON, efecto de 0, documentación.

1. `precalentamiento.timeout_precalentamiento`: `precalentamiento.py:40`, `or 10` (min). Rango JSON 0 a 3600 min. Con 0 aplica 10 min. Comentario del módulo (`precalentamiento.py:13`): "timeout global; si expira antes → FALLO", no dice nada sobre 0. Nota: la fase solo corre si `tiempo_precalentamiento` es distinto de 0 (`:43-45`); hoy los cinco perfiles tienen `tiempo_precalentamiento = 0`, así que la fase se salta.
2. `prevacio.timeout_bajo`: `prevacio.py:128`, `or 10` (min). Rango 0 a 3600. Con 0 aplica 10 min.
3. `prevacio.timeout_alto`: `prevacio.py:176`, `or 10` (min). Rango 0 a 3600. Con 0 aplica 10 min.
4. `prevacio.presion_baja_pulso_{a,b,c,d}`: `prevacio.py:147`, `or 15` (kPa). Rango 0 a 1000; sin `type` en el JSON (`set_param` lo trata como `int`, `cycle_manager.py:54`). Con 0 aplica 15 kPa. Se lee solo si el tipo tiene `conteo_pulso_x` mayor que 0; hoy solo el tipo `a` tiene conteo (4).
5. `prevacio.presion_alta_pulso_{a,b,c,d}`: `prevacio.py:196`, `or 180` (kPa). Rango 0 a 1000, sin `type`. Con 0 aplica 180 kPa (valor actual del tipo `a`: 80 a 160 según perfil).
6. `calentamiento.temperatura_calentamiento`: `calentamiento.py:203`, `or 134.0`. Rango 100 a 140 (0 no pasa `set_param`). Con 0 en el archivo aplica 134 °C; en `instrumental_121.json` el valor es 121.0.
7. `calentamiento.timeout_calentamiento`: `calentamiento.py:205`, `or 60` (min). Rango 1 a 999.
8. `calentamiento.rango_temp_estabilizacion`: `calentamiento.py:216`, `or 1.0` (°C). Rango 0 a 10. Con 0 aplica 1.0 °C (la banda superior de ESTABLE_PREESTERILIZACION, `:381`).
9. `calentamiento.timeout_recuperacion_estabilizacion`: `calentamiento.py:217`, `or 5` (min). Rango 1 a 60.
10. `esterilizacion.temperatura_esterilizacion`: `esterilizacion.py:155`, `or 134.0`. Rango 100 a 140.
11. `esterilizacion.tiempo_esterilizacion`: `esterilizacion.py:156`, `or 3.5` (min). Rango 0 a 9999. Con 0 aplica 3.5 min. Además, el registro y la pantalla usan el valor crudo: `cycle_logger.py:210-211` lo guarda en `ciclos.tiempo_esterilizacion` y en el encabezado del ticket, y `ui_qml/domain/pantalla_ciclo.py:70-72` [COMMITEADO] lo muestra; con 0 quedaría registrado 0 y se ejecutarían 3.5 min (inferencia de lectura).
12. `secado.modo`: `secado.py:32`, `int(... or 1)`. Rango 1 a 3.
13. `secado.timeout_pulso`: `secado.py:37, 119, 135`, `or 10` (seg). Rango 1 a 600.
14. `secado.presion_chaqueta_secado`: `secado.py:60`, `or 200` (kPa). Rango 0 a 500. Con 0 aplica 200.
15. `secado.rango_chaqueta_secado`: `secado.py:61`, `or 30` (kPa). Rango 0 a 100. Con 0 aplica 30.
16. `secado.presion_baja_secado`: `secado.py:107`, `or 20` (kPa). Rango 0 a 200. Con 0 aplica 20.
17. `secado.presion_alta_secado`: `secado.py:125`, `or 80` (kPa). Rango 0 a 300. Con 0 aplica 80.
18. `globals.presion_chaqueta` en CICLO: `states/ciclo.py:175-176`, `or config.get("presion_chaqueta") or 320`. Rango 0 a 400. `global_params.json` no tiene la clave `presion_chaqueta`, así que con 0 aplica 320 kPa. En PREPARACION y PREPARADO se lee SIN respaldo (`preparacion.py:173`, `preparado.py:95`): con 0 el objetivo es 0 kPa (ver OPC-28).
19. `globals.rango_presion_chaqueta` en CICLO: `ciclo.py:177-178`, `or config... or 50`. Rango 0 a 100. Con 0 aplica 50 en CICLO; en PREPARACION/PREPARADO se usa 0 literal (`preparacion.py:174`, `preparado.py:96`): banda de ancho cero.
20. `descompresion.modo_N.timeout` (N = 1 a 5): doble respaldo, `get_param(..., default=60)` y luego `(timeout_min or 60)` en `descompresion.py:47-48` y `protocolo_fallo.py:112-113`. Rango 1 a 3600 min. Con 0 aplica 60 min. No existe `modo_0` en los JSON; `protocolo_fallo.py:111` usa la clave `modo_2` cuando el modo es 0.

### A.2 Lecturas con `default=` (el 0 SÍ llega a la lógica)

21. `descompresion.modo`: `descompresion.py:14` (`default=0`, leído una sola vez en `reset()`); `protocolo_fallo.py:78` y `ciclo.py:237` (`default=0) or 0`). Rango 0 a 5. Con 0: `DescompresionFase` ejecuta `_tick_modo_0` (`:98-101`), que no abre ninguna válvula y solo espera presión atmosférica, y no arma timeout porque el timeout exige `modo > 0` (`:46-48, 58`). En cambio `valvula_reposo.py:10` y `protocolo_fallo.py:121` tratan 0 como modo 2 (comentario `valvula_reposo.py:4-5`: "0 se trata como 2"). Ver OPC-36.
22. `descompresion.tiempo_pre_despresurizacion`: `descompresion.py:26, 36`, `default=0`. Rango 0 a 3600 seg. Con 0 no hay espera previa (`:27`). 0 es el valor actual de los cinco perfiles.
23. `descompresion.modo_3.presion_cambio`: `descompresion.py:117`, `protocolo_fallo.py:129-131`, `default=150`. Rango 0 a 500. Con 0: la condición `p <= 0` (`descompresion.py:120`) no se cumple con presión absoluta positiva, la fase queda en la subetapa lenta hasta el timeout del modo y termina en FALLO (inferencia de lectura).
24. `descompresion.modo_{4,5}.presion_camara_enfriamiento`: `descompresion.py:143`, `default=200`. Rango 0 a 500. Con 0 nunca se abre aire comprimido (`:145`).
25. `descompresion.modo_{4,5}.tiempo_apertura_chaqueta`: `descompresion.py:155`, `default=5`. Rango 1 a 3600. Con 0 (solo por edición manual) la válvula abre un tick y cierra al siguiente; este temporizador no sigue el patrón estándar de dos estados ("`t_on<=0` → enclavada cerrada").
26. `descompresion.modo_{4,5}.tiempo_cierre_chaqueta`: `descompresion.py:156, 158-159`, `default=10`. Rango 0 a 3600. Con 0: chaqueta enclavada abierta (comprobación explícita `t_off == 0`).
27. `descompresion.modo_{4,5}.temperatura_enfriamiento`: `descompresion.py:179`, `default=80.0`. Rango 0 a 150. Con 0 la subetapa de enfriamiento no termina (`t <= 0`, `:181`); FALLO al vencer el timeout del modo (inferencia de lectura).
28. `finalizacion.apertura_automatica`: `ciclo.py:256`, `default=False`. Tipo bool.
29. `finalizacion.tiempo_espera_apertura`: `ciclo.py:262-264`, `default=60` y respaldo explícito solo para `None`. Rango 0 a 3600 seg. Con 0 no hay espera.
30. `finalizacion.temp_max_apertura`: `ciclo.py:273-277`, `default=80.0`, respaldo solo para `None`, recortado al global `temp_max_apertura` (120 en `global_params.json`). Rango 0 a 150. Con 0 la puerta nunca se abre automáticamente y, pasado el timeout, se emite `TIMEOUT_APERTURA_AUTOMATICA` (`:279-294`).
31. `finalizacion.timeout_temperatura`: `ciclo.py:280-283`, `default=30`. Rango 1 a 120. Con 0 la alarma de timeout se emite en cuanto termina la espera fija.

### A.3 Lecturas con `or 0` / `or 0.0` (constante 0: no hay sustitución)

Para completar el inventario; con 0 el comportamiento es el indicado:

- `precalentamiento.tiempo_precalentamiento` (`precalentamiento.py:38`): 0 salta la fase (comentario `:12`: "si == 0, fase saltada"). `presion_precalentamiento` (`:39`): con 0 el objetivo se alcanza de inmediato.
- `prevacio.conteo_pulso_x` (`prevacio.py:95, 244`): 0 salta el tipo (comentario `:21`: "0 = saltar"). `tiempo_adicional_{bajo,alto}_x` (`:162, 211`): 0 sin sostenimiento.
- `calentamiento.presion_add_calentamiento` (`calentamiento.py:204`, rango 0 a 100): con 0, `p_techo = p_obj` (`:311`) y la ventana de estabilidad exige `pres == p_obj` exacto (`:381`); la fase no completaría y terminaría por `timeout_recuperacion_estabilizacion` (inferencia de lectura). `factor_calentamiento` (`:206`): 0 da `duty_estable = 1`. `rango_calentamiento` (`:207`): 0 vuelve binarios los términos de proximidad y sobrepaso (`:97-98, 111-112`). `tasa_calentamiento`/`tasa_presion` (`:208-209`): 0 = sin límite (comentario `:17-18`). `tiempo_estable_preesterilizacion` (`:210`): 0 completa en el primer tick dentro de banda. `intervalo_segmentos_calor` (`:211`): 0 activa una rama especial que aplica el duty en binario (comentario `:338-343`: "la UI permite intervalo_segmentos_calor=0"). Escapes (`:212-215`): patrón de dos estados (CLAUDE.md: "`t_off<=0` → enclavada abierta, `t_on<=0` → enclavada cerrada").
- `esterilizacion.*` restantes (`esterilizacion.py:157-169`): `factor_esterilizacion` 0 = vapor enclavado abierto dentro de banda; `presion_add_esterilizacion` 0 = techo de control igual a `P_sat(t_est)`; `intervalo_segmentos_ester` 0 = vapor enclavado abierto en PWM_ACTIVO (a diferencia de calentamiento, no hay rama especial); `rango_temperatura_ester`, `rango_presion_ester`, `brecha_error_*` en 0 = el umbral de falla coincide con el setpoint; `brecha_segura_*` en 0 = el umbral de RECUPERACION coincide con el setpoint; escapes con el patrón estándar. CLAUDE.md documenta `escape_lento_off_ester = 0` como "enclavada abierta" y `escape_rapido_on_ester = 0` como "enclavada cerrada".
- `globals.F0_objetivo` (`esterilizacion.py:171`, rango 0 a 60): con 0 el criterio F0 se cumple siempre.
- `secado.tiempo_secado` (`secado.py:27-30`): 0 salta la fase.

### A.4 Lecturas por vías distintas de `get_param`

- `ConfigManager.get` (`core/managers/config_manager.py:16-25`) sobre `config/global_params.json` (sin `min`/`max` en la mayoría de claves): `presion_admosferica` `or 101.3` y `rango_presion_atm` `or 20.0` (`base_fase.py:43-47`, `protocolo_fallo.py:70-71, 166-167`, `ciclo.py:229-230, 299-300`); valores actuales 75 y 5. `temp_max_apertura` `or 120.0` (`protocolo_fallo.py:168`), sin respaldo en `ciclo.py:276` y `ser_puertas.py:42`. `presion_empaque` `or 300` (`ciclo.py:136`). `temp_segura_drenaje` sin respaldo (`ciclo.py:196`, `preparado.py:170`, `preparacion.py:263`), `rango_temp_drenaje` sin respaldo (`preparado.py:171`, `preparacion.py:264`). `tiempo_estable_alarma` sin respaldo (`preparado.py:18`). Intervalos de impresión `or` valor por defecto (`cycle_logger.py:362`).
- Lecturas del JSON crudo (sin respaldo): `progreso_ciclo.py:65-71` (decide qué fases muestra la UI), `cycle_logger.py:210-211` (registro y ticket), `ui_qml/domain/pantalla_ciclo.py:66-73` (pantalla), `ui_pyside/views/secado.py:113-121` (vista de secado PySide, desde `GET /cycle`).
- `cycle_temperature_sensors`: presente en los JSON (`cycles/user/bowe_dick.json:6-9`), sin lector en el código.
- Parámetros de `globals` sin respaldo: `F0` (`esterilizacion.py:170`, `control_loop.py:209`, `cycle_logger.py:276`) con `bool(...)`.

---

## B. Backend: escucha y clientes

### B.1 Dirección, puerto y lanzamiento

- `backend/main.py:27-32` [COMMITEADO]: `uvicorn.run("autoclave.backend.server:app", host="0.0.0.0", port=8000)`, con el comentario `# CRÍTICO: escucha en red`. No hay variable de entorno ni archivo de configuración para el host o el puerto. Hoy escucha en 0.0.0.0.
- Lanzamiento desde la UI tkinter (`main.py`) [COMMITEADO]: solo la ventana primaria con `profile.door_id == 1` lanza el backend como subproceso (`main.py:215-230`); en desarrollo `python -m autoclave.backend.main`, en el EXE `AutoclaveBackend.exe` junto al ejecutable (`main.py:72-83`). Una ventana secundaria (`--door` distinto de la puerta del perfil) solo espera (`main.py:211-214`).
- `dist/Iniciar_Puerta1.bat`, `Iniciar_Puerta2.bat`, `Iniciar_Doble_Pantalla.bat` [COMMITEADO] lanzan `AutoclaveUI.exe --door 1/2`; no lanzan el backend directamente.
- La UI QML (`ui_qml/app.py:6-10`) [MODIFICADO SIN COMMIT] no lanza el backend; `ui_qml/lanzar.py` levanta el simulador en `127.0.0.1:8001` (`simulador/__main__.py:60`) o espera al backend real.
- Servicios de Windows: NO IMPLEMENTADO. No se encontró configuración de servicio ni tarea programada; solo una mención hipotética en `docs/mis_plans/planeacion_anuncios_voz.md:507`.
- `tools/generador/app.py:33` escucha en 0.0.0.0:8080 por defecto (herramienta aparte, no del equipo).

### B.2 Clientes de `PATCH /cycle/parameter` y `PATCH /cycle/parameters`

`PATCH /cycle/parameter`:
- `ui_pyside/views/params_ciclo/params_ciclo.py:316-321` [COMMITEADO], `_ParamEditDialog._on_save`: cuerpo `{"cycle_id", "fase", "path", "value"}`. Con error HTTP muestra el `detail` y no guarda (`:322-327`); con error de red muestra "el cambio no se guardó" (`:328-333`). Con éxito actualiza su copia local e inserta la auditoría con el nombre completo del usuario (`:336-357`). No usa el `value` coercionado que devuelve el backend: guarda en local y audita su propio `new_val`.
- Pruebas: `tests/test_backend_cycle_parameter_endpoint.py` (siete casos: persistencia, autocommit, ruta anidada, 404, 422 por fase y por rango, no persistencia de fábrica).
- No hay clientes en QML, tkinter (`src/autoclave/ui/`), simulador ni firmware.

`PATCH /cycle/parameters`:
- `ui_pyside/views/secado.py:126-135` [COMMITEADO], `SecadoView._save`: cuerpo `{"modo", "tiempo_secado", "presion_chaqueta_secado", "presion_baja_secado", "presion_alta_secado"}` sobre el programa seleccionado. Muestra éxito o el `detail` del error; no audita. Es alcanzable: tarjeta "secado" del inicio PySide (`views/home.py:19-23`) y `main_window.py:185` [MODIFICADO SIN COMMIT].
- Pruebas: `tests/test_patch_cycle_parameters.py:10-35` prueba solo `BackendClient.patch` con `requests` simulado; no hay prueba del endpoint.
- Documentación histórica: `docs/superpowers/specs/2026-06-16-menu-pyside6-design.md:110, 201-206`, `docs/superpowers/plans/2026-06-17-secado-fase.md`, `docs/mis_plans/planeacion_ui_dual_pantalla.md:280`.
- Conclusión para D-12: `PATCH /cycle/parameters` TIENE un cliente activo (OPC-27).

Cliente HTTP común: `ui/service_ui/backend_client.py:48-56` [COMMITEADO], `timeout=0.8` segundos para GET, POST y PATCH; acepta `**kwargs` que pasa a `requests` (permitiría cabeceras, hoy nadie las envía). Ver OPC-26.

### B.3 Identificación de clientes

NO IMPLEMENTADO. Ninguna ruta lee cabeceras, IP ni token (`grep` de `Request`, `headers`, `request.client` en `backend/` sin resultados). Los únicos datos de identidad viajan en el cuerpo y no se verifican: `usuario` en `PATCH /calibration` con valor por defecto "Desconocido" (`server.py:75`), `source_door` en `/doors/{name}/open|close`, que se devuelve sin usarse (`server.py:584-619`).

### B.4 Dos instancias de UI

- Mismo PC, procesos separados. Tkinter: un proceso por ventana (`--door 1` y `--door 2`), solo una posee el backend (`main.py:198-214`). QML: un proceso por ventana (`ui_qml/app.py:59-70`, argumentos `--door` y `--screen`); el comentario de `login_controller.py:6-8` lo confirma ("una por proceso, es decir, por ventana QML"). El backend mantiene `ActividadUI` compartida para el standby simultáneo (`server.py:30-31, 181-186`). La configuración PySide es otro proceso, lanzado desde tkinter (`ui/window/main_window.py:658-682`) o desde QML (`ui_qml/bridge/lanzador_ajustes.py`).
- PC distinto para la puerta 2: el código lo menciona ("PC puerta 2 — esperando backend en red...", `main.py:231-234`) pero todos los clientes usan `http://127.0.0.1:8000` fijo (`main.py:21`, `ui_qml/app.py:47`, `ciclo_controller.py:23`, `params_ciclo.py:32`, `secado.py:19`, `calibracion_sensor.py:19`, `impresion_menu.py:25`, `_io_base.py:16`, `io_do.py:20`). Con el código actual esa topología no puede conectarse (OPC-35).

---

## C. Directorio de datos persistente

### C.1 Resolución de rutas

- `utils/paths.app_root()` (`utils/paths.py:8-22`) [COMMITEADO]: en el EXE, la carpeta del ejecutable; en desarrollo, la raíz del repositorio. Su docstring advierte expresamente no usar `__file__` para datos persistentes.
- `data/autoclave.db`: `app_root()/data/autoclave.db` (`db_manager.py:26`, `cycle_params_audit.py:6`, `sensor_calibration_audit.py:6`). Persistente en ambos casos.
- `cycles/`: `CycleManager` usa `BASE_DIR` derivado de `__file__` (`cycle_manager.py:9, 102`): `src/autoclave/cycles` en desarrollo y la carpeta temporal de extracción en el EXE (los tres `.spec` empaquetan `src/autoclave/cycles`: `AutoclaveBackend.spec:18`, `AutoclaveUI.spec:10`, `AutoclaveSettings.spec:9`). Los tres son de un solo archivo (sin `COLLECT`).
- `config/global_params.json`: `resource_path("autoclave/config/global_params.json")` (`config_manager.py:11`). `resource_path` (`utils/resources.py:4-11`) usa `sys._MEIPASS` en el EXE y `os.path.abspath("src")` en desarrollo, es decir, depende del directorio de trabajo del proceso. Ningún código escribe este archivo.
- `calibration.yaml`: en desarrollo el del repositorio; en el EXE una copia en `app_root()/data/calibration.yaml`, sembrada desde el empaquetado la primera vez (`utils/paths.py:25-42`). Es el único mecanismo existente de "copia persistente sembrada desde el paquete".
- Logs: backend en EXE `app_root()/data/backend.log` (`backend/main.py:10-21`); UI en EXE `data/ui{sufijo}.log` (`main.py:24-38`). `utils/logging.py:5-9` crea `src/logs/autoclave.log` relativo a `__file__` (dentro de la extracción en el EXE); lo importa `installation/backend_guard.py:3`.
- `installation_profile.json`: `app_root()/installation_profile.json` (`installation/storage.py:11`).

### C.2 Archivos escritos en ejecución

Persistentes junto al ejecutable o en la raíz: `data/autoclave.db` (+ `-wal`, `-shm`), `data/tickets/ciclo_NNNNN.txt` (`server.py:22, 481-483`), `data/backend.pid` (`backend_guard.py:6-12`), `data/last_shutdown.json` (`heartbeat.py:10-15`), `data/calibration.yaml` (solo EXE), `data/*.log` (solo EXE), `installation_profile.json` (`storage.py:43`).
Volátiles en el EXE (se pierden al cerrar): `cycles/user/*.json` reescritos por `_save_cycle_json` (`server.py:699-710`), `src/logs/autoclave.log`.

### C.3 Mecanismos de ruta existentes

- Variables de entorno: solo `AUTOCLAVE_BACKEND_URL` (URL del backend para la UI QML, `ui_qml/app.py:50-52`). No hay variable para el directorio de datos.
- ProgramData, AppData o LOCALAPPDATA: NO IMPLEMENTADO (sin referencias en `src/`).
- Carpeta junto al ejecutable: sí, `app_root()` (C.1).

### C.4 Datos a migrar

`cycles/user/bowe_dick.json`, `instrumental_121.json`, `instrumental_134.json`. Los dos perfiles de `cycles/factory/` (`bowe_dick.json`, `instrumental_134.json`) son de solo lectura. Además, en el EXE, `config/global_params.json` vive solo dentro del paquete. Hecho relevante para D-10: la vista PySide de parámetros carga los programas de disco en su propio proceso (`params_ciclo.py:430-435`), así que en el EXE leería la copia empaquetada en `AutoclaveSettings.exe`, no la del backend (OPC-34).

---

## D. Orden del tick y falla de sensor

### D.1 Orden dentro de un tick

`ControlLoop._tick` (`services/domain/loop/control_loop.py:92-196`) [COMMITEADO]: comprobación del enlace (`:93-141`; sin conexión retorna sin ejecutar la máquina de estados y aborta el ciclo tras 5 s, `:123-126`), `estado.update(units.get_all())` con las lecturas nuevas (`:144`), paro de emergencia y suministro eléctrico (`:147-154`), puertas (`:171-173`), servicio de puertas (`:176`), `state_machine.update()` bajo `_sm_lock` (`:179-181`), F0 (`:185`), `cycle_logger.update()` (`:188-189`), buzzer (`:195-196`).

`CicloState.run()` (`states/ciclo.py:341-517`) [COMMITEADO], en este orden: (0) resultado pendiente de confirmación (`:355-379`); (1) cancelación (`:382-388`); (2) paro de emergencia (`:391-404`); (2b) suministro eléctrico (`:407-420`); (3) puertas y empaque (`:423-437`); (4) sensores críticos, `SENSOR_AUSENTE` (`:440-460`); (5) chaqueta y drenaje (`:463-464`); (6) fin del pipeline (`:467-471`); (7) `fase.update()` de la fase actual (`:474-475`).

Conclusión para RS-05.2: la vigilancia de `SENSOR_AUSENTE` se ejecuta antes de `fase.update()` en el mismo tick y después de refrescar las lecturas en ese tick. La especificación habla de `run()` de la fase; el método real es `update()`. No hay prueba que verifique el orden: `tests/test_ciclo_sensores.py:26-52` comprueba que se reporta `SENSOR_AUSENTE`, pero no que la fase no se ejecute.

### D.2 Comportamiento de cada fase ante `None`

Mientras `SENSOR_AUSENTE` vigile `temp_camara` y `pres_camara`, las ramas `None` de esos dos sensores dentro de las fases no se alcanzan en CICLO. Comportamiento intrínseco de cada fase (relevante si se vigila otro sensor como Principal):

- CALENTAMIENTO: antes de inicializar, `temp_camara` `None` devuelve EN_CURSO sin armar el timeout (`calentamiento.py:222-225`): EN_CURSO indefinido mientras dure. Ya inicializada, el timeout global se evalúa antes de leer sensores (`:234-240`): termina en FALLO.
- ESTERILIZACION: `None` en temperatura o presión devuelve EN_CURSO (`esterilizacion.py:190-193`) antes de la finalización y del timeout de F0 (`:268-290`): EN_CURSO indefinido (riesgo aceptado, `esterilizacion.py:36-38` y CLAUDE.md).
- DESCOMPRESION: los modos 0 a 3 esperan `_en_presion_atm()`, que es falso con `None` (`descompresion.py:77-79`); los modos 4 y 5 no salen del enfriamiento con temperatura `None` (`:180-181`). Los modos 1 a 5 tienen timeout (`:46-48, 58-61`). El modo 0 no tiene timeout: EN_CURSO indefinido (OPC-36).
- SECADO: los modos 1 y 2 terminan por temporizador (`secado.py:76-95`); el modo 3 termina en FALLO por `timeout_pulso` (`:111-114, 128-131`). La presión de chaqueta `None` solo omite el control (`:56-59`).
- PRECALENTAMIENTO (usa `pres_chaqueta`, no vigilada): el timeout se evalúa antes del sensor (`precalentamiento.py:57-70`), termina en FALLO.
- Supervisores de CICLO: `_mantener_chaqueta` y `_mantener_drenaje` omiten el tick con `None` (`ciclo.py:156-158, 193-195`).
- Lectura obsoleta: `EstadoAutoclave.update` conserva el valor anterior si falta un índice (`core/runtime/status.py:125-129`). Para temperaturas no ocurre en la práctica porque `convert_temperatures` siempre entrega 8 valores, con `None` para ADC 0 o mayor o igual a 4095 (`hal/measures/converters.py:166-174`).

### D.3 Debounce y tolerancias

- `SENSOR_AUSENTE`: sin debounce; una sola lectura `None` dispara (`ciclo.py:440-460`).
- Fallas de ESTERILIZACION: debounce de 3 lecturas (`esterilizacion.py:47, 198-232`).
- Drenaje en CICLO: debounce simétrico de 3 (`ciclo.py:34, 186-219`).
- Desconexión serial: tolerancia de 5 s (`control_loop.py:37, 123-126`).
- PREPARADO: alarmas temporizadas con `tiempo_estable_alarma` (5 s), con un único temporizador compartido por todas (`preparado.py:196-201`). PREPARACION: sin temporización.
- `ERROR_AI_<SENSOR>` en PREPARACION/PREPARADO: solo con lectura exactamente 0, sin debounce (OPC-09). Hecho adicional: con lectura `None`, `evaluar_banda` lanza excepción (OPC-29).

### D.4 Sensores vigilados y protocolo de fallo

- `_SENSORES_TEMP_CRITICOS = ["temp_camara"]`, `_SENSORES_PRES_CRITICOS = ["pres_camara"]` (`ciclo.py:32-33`).
- Tratamiento real de `SENSOR_AUSENTE`: alarma de tipo EMERGENCIA con `recoverable=False` (`ciclo.py:451-457`), pero el resultado es `FALLO` y el estado global pasa a FALLA tras la confirmación (`state_machine.py:106-108`). FALLA vuelve a PREPARACION con `RESET_FALLA` y vacía todas las alarmas (`falla.py:33-36`, `state_machine.py:119-124`). Ningún código lleva el estado global a EMERGENCIA ni a HIBERNACION (solo aparecen en `state_machine.py:129, 136`). `/cycle/acknowledge` prearma `RESET_FALLA` solo si `fase_ciclo` empieza por `FALLO_` o es `EMERGENCIA` (`server.py:577-579`): con `SENSOR_AUSENTE` hace falta `/fault/reset`. Ver OPC-24.
- `ProtocoloFallo` usa `pres_camara` y `temp_camara` (`protocolo_fallo.py:69, 164-165`) y la temperatura segura del global `temp_max_apertura` (120 °C, `:168`), no la del programa.
- Interlock de puertas (`ser_puertas.py:49-53, 130-165`): usa `pres_camara` y `temp_camara`; si alguna es `None`, omite esa verificación y permite abrir (OPC-25).

---

## E. F0

- Fórmula (`core/runtime/letalidad.py:4-11`) [COMMITEADO]: `10 ** ((T_ref − 121.1) / 10) * dt_min`; z = 10 y 121.1 °C fijos en código.
- Acumulación (`control_loop.py:198-231`): requiere estado CICLO, `fase_ciclo` en `{"CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION"}` (`:23`) y `globals.F0` verdadero; si no se cumple, el sello se pone en `None` (`:211-213`). El primer tick solo inicializa (`:215-218`); `dt_min` es el tiempo real entre ticks (`:230`). Con `temp_camara` `None` no suma, pero avanza el sello, así que ese intervalo se pierde (`:216, 220-222`). `T_ref` es `min(temp_camara, temp_2_camara)` solo si `cap.has_liquid_sensor` y hay lectura del segundo sensor; si no, `temp_camara` (`:224-228`). Se ejecuta fuera de `_sm_lock`.
- Uso en el ciclo (`esterilizacion.py:170-171, 181-182, 268-290`): con F0 activo, la finalización exige tiempo cumplido Y `f0_acumulado >= F0_objetivo`; el timeout de seguridad es 2 × `tiempo_esterilizacion` y produce FALLO con texto `ESTERILIZACION_TIMEOUT_F0`. F0 no termina la fase por sí solo antes del tiempo. El timeout de F0 queda detrás de la comprobación de sensores (`:192-193`).
- Qué se imprime: `F0 total: {:.1f} min` en el pie del ticket si el programa tenía F0 activo (`cycle_logger.py:273-283`, `ticket_formatter.py:65, 80-81`). Se registra en el log al completar (`esterilizacion.py:279-282`).
- Qué se guarda: NO IMPLEMENTADO. `f0_acumulado` no está en ninguna tabla (`db_manager.py:28-109`) ni en `/status` (`server.py:104-179`); solo vive en memoria (`status.py:115-118`) y se pone a 0 en `CicloState.reset()` (`ciclo.py:110`). Ver OPC-33.
- Pruebas: `tests/test_letalidad.py` (cinco casos de la fórmula), `tests/test_control_loop_f0.py:45-125` (nueve casos: inicialización, dt real, fuera de ciclo, fase que no acumula, F0 desactivado, `temp_camara` `None`, mínimo con sensor de líquido, degradación sin segundo sensor, transición CALENTAMIENTO→ESTERILIZACION), `tests/test_esterilizacion_fase.py:457-525` (seis casos de finalización y timeout), `tests/test_ciclo_reset_f0.py`, `tests/test_estado_autoclave_f0.py`, `tests/test_ciclos_f0_objetivo.py` (presencia de `F0_objetivo` en los JSON), `tests/test_cycle_logger_printer.py:215-228` y `tests/test_ticket_formatter.py:97-102` (pie del ticket). No hay prueba de activar F0 a mitad de la fase (OPC-30).
- `has_liquid_sensor`: atributo de `EquipmentCapabilities` derivado de la clase de equipo (`installation/equipment.py:13-55`): verdadero solo en `mesa_b_lab` y `piso_lab`. La clase sale de `installation_profile.json` (`installation/storage.py:11, 28`), cargado por `BackendContext` (`backend/context.py:39-43`). No sale de ningún YAML. El perfil presente en este repositorio es `"equipment_class": "piso"`, es decir `has_liquid_sensor = False`.

---

## F. Sensores: configuración, nombres y posiciones

### F.1 YAML de instancia y de modelo [COMMITEADO]

- `config/instances/ACV-2026-001.yaml:17-26`, `io_enabled.AI`: `temp_camara`, `temp_referencia`, `temp_drenaje_camara`, `temp_drenaje`, `pres_camara`, `pres_chaqueta`, `pres_empaque_1`, `pres_empaque_2`. Sin canales, etiquetas ni comentarios de posición. Declara `model_name: SOLIDS` (`:7`).
- `config/models/solids.yaml`: `sensors.temperature.chamber.supported_count: [1]`, `reference: true`, `drain_chamber`, `drain_general` (`:8-14`); `io_contract.AI` igual a la instancia (`:72-81`); límites de presión de 1 a 400 kPa y de temperatura de 0 a 200 °C (`:64-70`).
- `config/models/solids_liquids.yaml`: `io_contract.AI` agrega `temp_camara_2` (`:76-85`). En `:10-11`, `chamber:` queda vacío y `supported_count: [1, 2]` cuelga al mismo nivel por la indentación.
- Ningún código Python lee `instances/` ni `models/` (búsqueda de `io_enabled`, `io_contract`, `solids`, `instances/` en `src/` sin resultados).

### F.2 Mapeo frente a `EstadoAutoclave.map_temp` (`status.py:12-19`)

`map_temp`: `temp_camara` (0), `temp_2_camara` (1), `temp_ref` (2), `temp_chaqueta` (3), `temp_drenaje_cam` (4), `temp_drenaje` (5). Discrepancias:

- `temp_referencia` (YAML) frente a `temp_ref`; `temp_drenaje_camara` frente a `temp_drenaje_cam`; `temp_camara_2` (solo `solids_liquids.yaml`) frente a `temp_2_camara`.
- `temp_chaqueta` no figura en ningún YAML, pero `verificar_sensores` de PREPARACION la revisa (`preparacion.py:112-119`).
- El orden del YAML no sigue los canales (ya en `docs/informes/inventario_sensores_y_base_de_datos.md:56` [NUEVO SIN TRACKEAR]).
- Fuera de AI: la instancia omite `descompresion_lenta` y `vapor_caldera` (DO) aunque las fases usan `descompresion_lenta`; el YAML escribe `aire_atmosferico_camara` y el código `aire_admosferico_camara` (`status.py:60`); `buzzer_alarma` (YAML) frente a `buzer_alarma` (`status.py:69`); `suministro_electrico` (DI 13, `status.py:42`) no figura en ningún YAML.

### F.3 Posición física o función de cada sonda

- Firmware (`Hardware/.../Comunicacion_esclava_ESP32_V2.ino:16-21, 156-180`) [COMMITEADO]: 16 canales analógicos por multiplexor, sin nombres ni funciones.
- `Documentacion/DOC_Capa_Interfaz_Hardware.docx` [COMMITEADO]: `temp_2_camara` = "Segunda sonda de temperatura de la cámara"; `temp_ref` = "Temperatura de referencia". `DOC_Conversion_ADC_Valores_Fisicos.docx`: "AI1 (temp_2_camara)", "AI2 (temp_ref)". Sin posición física.
- `calibration.yaml`: comentarios por índice ("Sensor 0 — recalibrado..."), sin posición.
- UI: `es.json:82-83` [MODIFICADO SIN COMMIT] "Temp cámara" y "Temp referencia"; `:70-71` "Temp Cámara" y "Temp Ref" en la gráfica; el puente QML lee `temp_ref` (`ui_qml/bridge/ui_bridge.py:156-161, 191, 259-260`). `io_temp.py:64-69` (PySide) usa los alias `camara`, `camara_2`, `ref`, `chaqueta`, `drenaje_camara`, `drenaje`, iguales a las claves de `/status` (`server.py:129-136`).
- Docs: `planeacion_f0.md:88-91` (mínimo de las dos sondas de cámara); `docs/handoff/handoff-2026-07-22-margen-entrada-esterilizacion.md:46` y `docs/superpowers/plans/2026-06-02-equipment-profiles-impl.md:1226` describen un diseño anterior en el que CALENTAMIENTO exigía ambas sondas con sensor de líquido (hoy no está en el código).
- NO DETERMINADO: la posición física de las tres sondas. Ningún archivo del repositorio la indica.

### F.4 Qué hace hoy `temp_ref`

Se publica en `/status` (`server.py:132`), se guarda en `lecturas_grafica` (`cycle_logger.py:316-321`, `db_manager.py:71-79`), se grafica y se muestra como "Temp referencia". Se revisa en `verificar_sensores` de PREPARACION (`preparacion.py:112-119`) y, por iteración del diccionario completo, en PREPARADO (`preparado.py:256-261`). No participa en control, fallas, F0, puertas ni ticket.

### F.5 Lectura de `has_liquid_sensor` y efecto del modelo

Solo se lee en `control_loop.py:224`. La lista de sensores no cambia entre `solids` y `solids_liquids` en ejecución: los YAML de modelo no se leen, `map_temp` es fijo y `has_liquid_sensor` depende del perfil de instalación, no del YAML. Son dos fuentes independientes que pueden discrepar (OPC-31).

---

## G. Registro del ciclo y ticket

### G.1 Esquema (`db_manager.py:28-109`) [MODIFICADO SIN COMMIT; las tablas de ciclo no cambian respecto a HEAD]

- `ciclos`: `id` PK autoincremental, `numero_ciclo` NOT NULL, `fecha_inicio` NOT NULL, `fecha_fin`, `tipo_ciclo` (id del programa), `nombre_ciclo`, `resultado`, `temp_esterilizacion`, `tiempo_esterilizacion`, `modelo`, `serie`, `version_sw`, `operador` (hoy siempre vacío, `server.py:366-368`), `motivo_fallo`. Índices `idx_ciclos_fecha (fecha_inicio)` e `idx_ciclos_numero (numero_ciclo)`. No guarda el número de programa (`server.py:353-355`).
- `lecturas`: `id`, `ciclo_id` FK a `ciclos`, `timestamp_rel`, `timestamp_abs`, `fase_codigo`, `temp_camara`, `pres_camara`, `para_imprimir`. Índice `idx_lecturas_ciclo`. No tiene `temp_ref` ni otras temperaturas.
- `lecturas_grafica`: `id`, `ciclo_id`, `t_s`, `fase`, `temp_camara`, `temp_ref`, `pres_camara`. Índice `(ciclo_id, id)`.
- `ciclo_fases`: `id`, `ciclo_id`, `fase`, `inicio_s`, `fin_s`, `duracion_s`. Índice `(ciclo_id)`.
- `usuarios`: ver K.
- Tablas creadas fuera de `_SCHEMA`, por su propia clase: `cycle_params_audit` (`cycle_params_audit.py:8-19`) y `sensor_calibration_audit` (`sensor_calibration_audit.py:8-24`).

### G.2 Versionado y migraciones

- Sin versionado: no hay `PRAGMA user_version` ni tabla de versión.
- Cada instancia de `DbManager` ejecuta `_SCHEMA` con `CREATE ... IF NOT EXISTS` (`db_manager.py:140-144`) y `_migrate()` (`:146-164`), que intenta `ALTER TABLE ... ADD COLUMN` y descarta `OperationalError` (`ciclos.motivo_fallo` [COMMITEADO]; `usuarios.creado_por`, `creado_en`, `codigo_creacion` [MODIFICADO SIN COMMIT]). Se ejecuta en cada proceso que crea un `DbManager` (H.2).

### G.3 Ticket

- Encabezado (`cycle_logger.py:198-254`): número, serie, modelo, versión, nombre e id del programa, `temperatura_esterilizacion` y `tiempo_esterilizacion` crudos del JSON, fecha.
- Filas: `temp_camara` y `pres_camara` en todas las fases (`cycle_logger.py:371-403`). Códigos (`:47-56`): PRECALENTAMIENTO `PH`, PRE_VACIO `PV`, CALENTAMIENTO `H`, ESTERILIZACION `S`, cierre `E`/`F`. DESCOMPRESION y SECADO no tienen código (se registran como `" "`). Solo `H` y `S` tienen intervalo periódico (`:66-71, 357-361`); en las demás fases solo hay filas al cambiar de fase o de paso interno (`:351-353`).
- Pie: temperatura final (última `temp_camara`), motivo y F0 si aplica (`cycle_logger.py:273-283`).
- Texto del ticket guardado: `format_ticket(ciclo, rows)` a partir de la fila de `ciclos` y de `lecturas` con `para_imprimir` (`server.py:471-485`).

### G.4 Dónde vive hoy el metadato por ciclo

Los metadatos de cada ciclo están como columnas de `ciclos`, escritas una vez en `crear_ciclo` (`cycle_logger.py:219-228`) y completadas en `cerrar_ciclo` (`db_manager.py:216-223`). Las rutas de reporte devuelven la fila completa: `/cycle/history/{id}/readings` y `/cycle/history/{id}/ticket` usan `dict(ciclo)` (`server.py:443-468`), así que cualquier columna nueva aparecería en esas respuestas; `_ciclo_json` (`server.py:352-369`) y `/cycle/history` (`:426-440`) eligen campos por nombre. Los datos por fase van en la tabla hija `ciclo_fases`.

---

## H. Base de datos y concurrencia

### H.1 Apertura

- `DbManager` (`db_manager.py:123-134`): una conexión por instancia, `check_same_thread=False`, protegida por un `threading.Lock` interno (válido solo dentro del proceso). Sin argumento `timeout`, así que rige el valor por defecto de `sqlite3.connect` (5 s de espera ante bloqueo). `PRAGMA journal_mode = WAL` y `foreign_keys = ON` dentro de `_SCHEMA` (`:29-30`).
- `CycleParamsAuditDB` y `SensorCalibrationAuditDB`: abren una conexión nueva por operación con `with sqlite3.connect(...)` (`cycle_params_audit.py:25, 38, 47`; `sensor_calibration_audit.py:30, 48, 59`). El gestor de contexto confirma o revierte, pero no cierra la conexión.
- En el backend, las escrituras de `CycleLogger` ocurren en el hilo del lazo de control (`control_loop.py:188-189`), fuera de `_sm_lock`. Las de calibración, en hilos del servidor HTTP.

### H.2 Procesos que escriben

- Backend: `ciclos`, `lecturas`, `lecturas_grafica`, `ciclo_fases` (`CycleLogger`), `sensor_calibration_audit` (`server.py:96-99`), DDL de arranque (`context.py:74-75`).
- Proceso PySide (AutoclaveSettings): `cycle_params_audit` (`params_ciclo.py:355-357, 366`); DDL, `seed_admin_if_empty` y `crear_usuario` a través de `DbManager()` (`views/login.py:235`, `views/nuevo_usuario/puente.py:31`, `views/ciclos.py:234`).
- Proceso QML: `DbManager()` en `login_controller.py:26-28, 43-46` [NUEVO SIN TRACKEAR], que al crearse ejecuta DDL y `seed_admin_if_empty` (`db_manager.py:132-133, 455-470`).
- Respuesta para RB-03: hay más de un proceso escribiendo, y `cycle_params_audit` se escribe hoy desde el proceso PySide, no desde el backend.

### H.3 Transacciones y bloqueo

- No hay transacciones explícitas (`BEGIN`, `BEGIN IMMEDIATE`) en ningún lugar; se usa la transacción implícita del módulo `sqlite3` y `commit()` por operación.
- "database is locked": sin manejo específico. Las únicas capturas de `OperationalError` son las de `_migrate`. En el backend, `CycleLogger._guardar` captura errores solo para gráfica y fases (`cycle_logger.py:326-331`); `crear_ciclo`, `insertar_lectura` y `cerrar_ciclo` no están protegidos y propagarían la excepción hasta `ControlLoop.run` (`control_loop.py:86-90`), tras esperar hasta 5 s en el hilo de control (inferencia de lectura).

### H.4 Triggers y `ALTER TABLE ADD COLUMN`

- Versión: el intérprete del que se tomó `sqlite3.dll` para el build (`build/AutoclaveBackend/Analysis-00.toc` referencia `...\Python314\DLLs\sqlite3.dll`) reporta hoy SQLite 3.50.4 (Python 3.14.3). Esa versión admite triggers y `ALTER TABLE ... ADD COLUMN`. NO DETERMINADO si el EXE del 22-09 contiene exactamente esa DLL; no se inspeccionó el ejecutable.
- Uso actual: `ADD COLUMN` sí (`db_manager.py:150-161`); triggers no (sin `CREATE TRIGGER` en el código).

---

## I. Bloqueo `_sm_lock`

- Definición: `threading.Lock()` (no reentrante), `control_loop.py:50`.
- Adquisiciones (las únicas en `src/`):
  1. `control_loop.py:180-181`, hilo `ControlLoop`, en cada tick fuera del modo prueba: envuelve `state_machine.update()` completo.
  2. `control_loop.py:301-311`, `set_active_cycle`, llamado desde el hilo HTTP por `POST /cycle/select` (`server.py:229`): comprueba que no esté en CICLO y reconstruye la `StateMachine`.
- Ninguna otra ruta HTTP lo toma. `POST /cycle/start`, `/cycle/abort`, `/cycle/acknowledge`, `/fault/reset` y las de parámetros leen el estado o escriben indicadores sin el bloqueo (`server.py:488-581, 622-696`). Esto contradice la especificación 1 §3 (OPC-22).
- Trabajo dentro de la sección crítica (toda la máquina de estados): lógica de fases y supervisores; salidas por serial (cada `set_output` escribe una línea con `serial.write`, `serial_link.py:262-277`; el puerto se abre sin `write_timeout`, `:113`); `reset_all_outputs()` → `all_off()`, que espera hasta 1.0 s el ACK (`serial_link.py:279-291`). Se llama en cada tick de PREPARACION, PREPARADO o FALLA con paro de emergencia (`preparacion.py:63-65`, `preparado.py:46-47`, `falla.py:21-22`), una vez en `ProtocoloFallo.ejecutar` y en cada tick de `ProtocoloFallo.update` mientras no se confirme (`protocolo_fallo.py:66, 159-160`). También alarmas en memoria, logging (en el EXE a archivo; PREPARACION registra en INFO en cada tick, `preparacion.py:88`) y `door_service.request_open` en la apertura automática (`ciclo.py:323`). No hay acceso a BD ni a red dentro del bloqueo.
- Frecuencia: `run()` duerme `interval = 0.5` s después de cada tick (`control_loop.py:41, 84-90`); el periodo es la duración del tick más 0.5 s, es decir, como máximo unos 2 ticks por segundo.
- Duración típica de la sección crítica: NO DETERMINADO. No hay instrumentación y no se ejecutó nada; el límite superior conocido es de al menos 1 s por tick cuando `all_off` no recibe ACK.
- Hilos HTTP: las rutas son funciones `def` síncronas, que FastAPI ejecuta en su grupo de hilos; uvicorn se lanza con un solo proceso (`backend/main.py:27-32`). Comparten el mismo bloqueo solo a través de `set_active_cycle`.

---

## J. Lecturas de parámetros en PREPARACION y PREPARADO

- `PreparacionState` lee del programa activo solo `globals.presion_chaqueta` y `globals.rango_presion_chaqueta` (`preparacion.py:173-174`), sin respaldo. `PreparadoState`, los mismos (`preparado.py:95-96`); `mantener_chaqueta` se ejecuta dos veces por tick (en `ejecutor`, `:86`, y en `esta_preparado`, `:230`). El resto viene de `global_params.json`.
- Efecto en caliente: el `Cycle` editado por `PATCH /cycle/parameter` es el mismo objeto que usa la máquina de estados (`context.py:31-36`, `control_loop.py:51, 59-63`; `set_param` muta la hoja en sitio, `cycle_manager.py:70`). El cambio actúa en el tick siguiente: cambia el umbral de la válvula de chaqueta, la banda de alarma y la condición de listo (`control_banda.py:12-26`). Con 0 en `rango_presion_chaqueta` la banda tiene ancho cero (OPC-28).
- Servicios que corren en esos estados: `ServicioPuertas` y las puertas (solo `global_params.json`), `CycleLogger` (inactivo fuera de CICLO, `cycle_logger.py:160-168`), `_acumular_f0` (corta en la primera condición, `control_loop.py:206-213`). No leen el programa.
- Lectores fuera de la máquina de estados que muestran el programa en esos estados: la pantalla de preciclo QML vía `GET /cycle` (`ui_qml/domain/pantalla_ciclo.py:66-73`).
- `POST /cycle/select` en PREPARADO reconstruye la máquina de estados (`control_loop.py:305-310`): al reentrar a PREPARADO se borra `START_CICLO` (`state_machine.py:48-51`) y se reinician los confirmadores y el temporizador de alarmas (constructor de `preparado_state`).

---

## K. Identidad y roles

- Tabla `usuarios` (`db_manager.py:98-108`): `id`, `nombre` (nombre completo), `usuario` (login, UNIQUE), `hash_pw`, `rol` (`DEFAULT 'operador'`), `activo` (`DEFAULT 1`), `creado_por`, `creado_en`, `codigo_creacion` (las tres últimas [MODIFICADO SIN COMMIT]). No existe columna `nivel`.
- Valores de rol: `ui_pyside/services/roles.py:10-19` [NUEVO SIN TRACKEAR] define `admin`, `tecnico`, `biomedico`, `ingeniero`. `operador`, el valor por defecto de la tabla, no está en la lista. Usuario sembrado: `admin` con rol `admin` (`db_manager.py:455-470`).
- `LoginController` (`ui_qml/controllers/login_controller.py`) [NUEVO SIN TRACKEAR]: expone la propiedad `nombreSesion` (el `nombre`, `:57-60`) y `mensajeError`; emite `sesionIniciada(usuario, rol)` (`:34, 84`). No hay propiedad para `usuario` ni para `rol`. La sesión se guarda en `SessionManager`, a nivel de clase y por proceso (`session_manager.py:8-34`), con `id`, `nombre`, `usuario` y `rol`.
- Cómo podría adjuntarse hoy: dentro del mismo proceso, un controlador puede leer `SessionManager.current_user()`; `BackendClient.patch(path, body, **kwargs)` reenvía `kwargs` a `requests` (`backend_client.py:48-56`), así que el cuerpo o las cabeceras podrían llevarlo. Ningún controlador QML lo hace hoy.
- Identificador usado hoy en PySide: el nombre completo. `params_ciclo.py:342-349` y `calibracion_sensor.py:225-226` usan `current_user().get("nombre", "Desconocido")`, no el login. La auditoría histórica de `cycle_params_audit.usuario` contiene nombres completos o "Desconocido" (OPC-37).

---

## Cierre

### (1) Hallazgos nuevos

- OPC-22 (Media). Especificación 1 §3 (último punto) y RB-01.3. La especificación afirma que el patrón `get_machine_state()` bajo `_sm_lock` "ya se usa" en `POST /cycle/abort`, `/cycle/acknowledge` y `/fault/reset`. Es falso: solo lo toman `ControlLoop._tick` y `set_active_cycle` (`control_loop.py:180, 301`); esas rutas leen el estado y escriben indicadores sin bloqueo (`server.py:508-581`). Además el bloqueo es `threading.Lock`, no reentrante: el servicio de RB-08 no podrá llamar a `set_active_cycle` mientras lo sostenga.
- OPC-23 (Alta). Especificación 1 RB-01.3 ("no retrasar el lazo más de un tick"). Dentro de `_sm_lock` el lazo hace E/S serial bloqueante y `all_off()` con espera de hasta 1.0 s por ACK, repetible en cada tick (I). Una petición HTTP que espere el bloqueo puede esperar un segundo o más, y una sección crítica HTTP larga retrasaría escrituras de salidas. La duración real es NO DETERMINADO; RB-01.3 pide medirla.
- OPC-24 (Alta). Especificación 2 RS-05.1, C-3 y criterio de aceptación 3; especificación 1 D-1. "SENSOR_AUSENTE como EMERGENCIA no recuperable, con el mismo tratamiento actual" no describe el comportamiento actual: el estado global pasa a FALLA y se sale con `RESET_FALLA`, que borra todas las alarmas, incluidas las de `recoverable=False` (`state_machine.py:106-124`, `falla.py:33-36`). Ningún código pone el estado global en EMERGENCIA ni en HIBERNACION, aunque D-1 y las pruebas de RB-01 los enumeran.
- OPC-25 (Alta). Especificación 2 S-8 y RS-07. El interlock de puertas no bloquea si `temp_camara` o `pres_camara` es `None`: omite la verificación y permite abrir (`ser_puertas.py:139-157`). S-8 da por hecho que mantener `temp_camara` asegura la cámara; con sensor ausente fuera de CICLO no hay protección por temperatura ni presión.
- OPC-26 (Media). Especificación 1 RB-03.5 y RB-04.3. `BackendClient` usa `timeout=0.8` s (`backend_client.py:48-56`), mientras el backend ejecuta `git add` y `git commit` dentro de la petición (`server.py:699-710`). Si la respuesta tarda más, PySide informa "el cambio no se guardó" (`params_ciclo.py:328-333`) aunque el backend ya lo aplicó en memoria y en disco, y no se escribe auditoría. Tiempo real de git: NO DETERMINADO.
- OPC-27 (Alta). Especificación 1 D-12, RB-03.1 y criterio 6. `PATCH /cycle/parameters` tiene un cliente activo, `SecadoView` (`ui_pyside/views/secado.py:126-135`), alcanzable desde el inicio PySide. Edita cinco parámetros del programa seleccionado sin ninguna auditoría y con la tabla de rangos propia, que admite 0 en presiones (`server.py:630-638`). La especificación solo prevé que la UI PySide "deje de escribir auditoría" en `params_ciclo.py`.
- OPC-28 (Alta). Especificación 1 RB-05.4, Anexo A y D-11. `globals.presion_chaqueta` y `globals.rango_presion_chaqueta` tienen dos semánticas para el mismo valor: en CICLO, 0 se sustituye por 320/50 (`ciclo.py:175-178`); en PREPARACION y PREPARADO, 0 se usa literalmente (`preparacion.py:173-174`, `preparado.py:95-96`), con objetivo de 0 kPa o banda de ancho cero. El rango JSON admite 0 en ambos.
- OPC-29 (Media). Especificación 2 RS-09 (y OPC-09). En PREPARACION y PREPARADO, una lectura `None` de `pres_chaqueta`, `pres_camara` o `temp_drenaje` (o un parámetro `None`) llega a comparaciones con `None` (`control_banda.py:18-25`, `preparado.py:143`, `preparacion.py:223`) y lanza `TypeError` en cada tick; `ControlLoop.run` lo captura y solo registra un aviso (`control_loop.py:86-90`). No hay alarma y el tick se corta (F0, registro y buzzer no corren en ese tick). Inferencia de lectura; no ejecutado.
- OPC-30 (Alta). Especificación 1 RB-01 (respaldo de la necesidad). Si `globals.F0` pasa de falso a verdadero durante ESTERILIZACION, `_timer_timeout_max` queda en `None` (solo se arma al inicializar, `esterilizacion.py:181-182`) y la comparación de `:286` lanza `TypeError` en cada tick: la fase no completa ni falla y las salidas quedan como estaban. Cancelación, emergencia y `SENSOR_AUSENTE` siguen funcionando porque se evalúan antes. Inferencia de lectura; no ejecutado.
- OPC-31 (Media). Especificación 2 RS-01.4, S-9 y §4.1. La "declaración de la instalación" no existe como fuente única: los YAML no se leen, `has_liquid_sensor` sale de `installation_profile.json` (`equipment.py`, `storage.py`), e `io_enabled` omite sensores y salidas que el código usa (`temp_chaqueta`, `temp_2_camara`, `descompresion_lenta`, `suministro_electrico`). Además, en el EXE los YAML viajan dentro del paquete.
- OPC-32 (Media). Especificación 2 RS-08.2. La premisa "`lecturas` registra `temp_camara` y `temp_ref`" no es exacta: `lecturas` solo tiene `temp_camara` y `pres_camara` (`db_manager.py:49-58`); `temp_ref` está solo en `lecturas_grafica`. DESCOMPRESION y SECADO no tienen código de fase ni filas periódicas en el ticket (`cycle_logger.py:47-71`).
- OPC-33 (Media). Especificación 2 RS-04 y RS-08. El F0 acumulado no se persiste ni se expone (sin columna, sin campo en `/status`); solo se imprime en el pie y se registra en el log. Un ciclo que termina por el criterio F0 no deja el valor en la base.
- OPC-34 (Media). Especificación 1 D-10 y RB-04.5. Los tres ejecutables de un solo archivo empaquetan cada uno su propia copia de `cycles/` y `config/`; la vista PySide carga los programas de disco en su propio proceso (`params_ciclo.py:430-435`), así que en el EXE mostraría y tomaría el `valor_anterior` de la copia empaquetada de Settings, no de la del backend. `resource_path` depende del directorio de trabajo en desarrollo (`resources.py:9-11`) y `utils/logging.py` escribe bajo `__file__`.
- OPC-35 (Baja). Especificación 1 D-9. El comentario `# CRÍTICO: escucha en red` (`backend/main.py:29`) y el mensaje "PC puerta 2 — esperando backend en red" (`main.py:232`) describen una topología de dos PC que el código no soporta: todos los clientes usan `127.0.0.1` fijo. Pasar a `127.0.0.1` no rompe ningún cliente existente, pero contradice esos comentarios.
- OPC-36 (Media). Especificación 2 RS-05.2 y especificación 1 Anexo A. En DESCOMPRESION con `modo = 0` (permitido, mínimo JSON 0) no se abre ninguna válvula y no hay timeout (`descompresion.py:46-48, 58, 98-101`): la fase puede quedar en EN_CURSO indefinidamente; en otros puntos el modo 0 se trata como 2 (`valvula_reposo.py:10`, `protocolo_fallo.py:121`). Con `default=` (A.2), un 0 en `presion_cambio` o en `temperatura_enfriamiento` lleva a FALLO por timeout; D-5 solo cubre la forma `or`.
- OPC-37 (Media). Especificación 1 RB-03, §5 (migración) y D-3. La columna `cycle_params_audit.usuario` contiene hoy nombres completos o "Desconocido" (`params_ciclo.py:342-349`), no el login. Si las filas nuevas guardan el login, la misma columna mezclará dos identificadores y la consulta de última modificación (RB-03.7) los comparará. La calibración hace lo mismo (`calibracion_sensor.py:225-226`, `server.py:75`).

### (2) Preguntas abiertas

1. ¿El despliegue real usa los EXE de un solo archivo de `dist/`? Sigue NO DETERMINADO y condiciona D-10, OPC-34 y la ubicación de `global_params.json`.
2. ¿Se descarta la topología de dos PC (puerta 2 en otro equipo)? Si se descarta, ¿se corrigen los comentarios de OPC-35 en el mismo cambio que D-9?
3. Para RS-05 y C-3: ¿"no recuperable" debe significar llevar el estado global a EMERGENCIA (hoy inexistente) o se mantiene el flujo actual de FALLA con reinicio (OPC-24)?
4. ¿El interlock de puertas con sensor `None` (OPC-25) entra en la especificación 2 o se trata aparte?
5. ¿El Anexo A debe incluir también los parámetros con `default=` en los que 0 produce bloqueo o FALLO (`modo`, `presion_cambio`, `temperatura_enfriamiento`, `tiempo_apertura_chaqueta`, `temp_max_apertura`), además de los de la forma `or`?
6. Para `globals.presion_chaqueta` y `rango_presion_chaqueta` en 0 (OPC-28): ¿cuál de las dos semánticas es la correcta, o se prohíbe el 0?
7. ¿`SecadoView` y `PATCH /cycle/parameters` se conservan (D-12 dice que sí si hay clientes), se retiran junto con la vista, o la vista pasa a usar el servicio único?
8. Auditoría histórica (OPC-37): ¿se migran las filas con nombre completo tal como están, o se agrega una columna nueva para el login?
9. ¿RS-08 debe guardar F0 (OPC-33) y la asignación de sensores en `ciclos`?
10. ¿Qué fuente es "la declaración de la instalación" para RS-01: `io_enabled` del YAML, el perfil de instalación (clase de equipo) o una nueva?
11. C-4 sigue abierta: el repositorio solo dice "Segunda sonda de temperatura de la cámara" (`temp_2_camara`) y "Temperatura de referencia" (`temp_ref`); no hay posiciones físicas.
12. ¿La excepción con sensor `None` en PREPARACION/PREPARADO (OPC-29) se corrige dentro de RS-09?

### (3) Archivos para revisión directa

- `src/autoclave/services/domain/loop/control_loop.py` (tick, `_sm_lock`, F0).
- `src/autoclave/state_machine/states/ciclo.py` (orden de `run()`, `SENSOR_AUSENTE`, chaqueta con respaldo).
- `src/autoclave/state_machine/states/preparacion.py` y `preparado.py` (chaqueta sin respaldo, `None`).
- `src/autoclave/state_machine/cycle_phases/esterilizacion.py`, `calentamiento.py`, `descompresion.py`, `secado.py`, `prevacio.py`, `precalentamiento.py`, `protocolo_fallo.py`, `valvula_reposo.py`.
- `src/autoclave/backend/server.py` (rutas de parámetros, `_save_cycle_json`, rutas sin bloqueo) y `src/autoclave/backend/main.py` (host).
- `src/autoclave/protocols/serial_link.py` (`all_off`, escritura bloqueante).
- `src/autoclave/services/domain/puertas/ser_puertas.py` (interlock con `None`).
- `src/autoclave/ui_pyside/views/secado.py` y `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`.
- `src/autoclave/ui/service_ui/backend_client.py` (timeout 0.8 s).
- `src/autoclave/services/domain/logging/db_manager.py`, `cycle_params_audit.py`, `cycle_logger.py`.
- `src/autoclave/core/managers/cycle_manager.py`, `config_manager.py`, `src/autoclave/utils/paths.py`, `utils/resources.py`.
- `src/autoclave/installation/equipment.py` e `installation_profile.json`.
- `src/autoclave/config/instances/ACV-2026-001.yaml`, `config/models/solids.yaml`, `solids_liquids.yaml`.
- `AutoclaveBackend.spec`, `AutoclaveUI.spec`, `AutoclaveSettings.spec`.
- `Documentacion/DOC_Capa_Interfaz_Hardware.docx` (única descripción de función de las sondas).
