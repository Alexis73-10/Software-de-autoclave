# P9 — Opciones: puertas simples, refresco al guardar y entradas NC (tanda 9)

Rama `tanda-9-p9` (desde `tanda-9`, c7b8744). Fuente: `decisiones_tanda_9.md` D9-3, D9-4, D9-5 y Q5.
Etapa no ★: no se lanzaron revisores (regla 9 solo para ★). No se crearon códigos de alarma.

## D9-3. Equipos con puertas simples

"Puertas simples" = `door_type == simple` en el perfil de instalación (`installation/profile.py::puertas_simples`, nueva). Sin perfil: se muestra todo, como antes.

- **Parámetros del ciclo › Finalización:** el backend (`GET /programas/{n}/seccion/finalizacion`, en `_hojas_seccion`) ya no entrega `tiempo_espera_apertura` ni `apertura_automatica` en un equipo de puertas simples. `temp_max_apertura` y `timeout_temperatura` siguen visibles. La pantalla QML no cambió: muestra lo que entrega el backend.
- **Rechazo en backend:** `PATCH /cycle/parameter` con `finalizacion/apertura_automatica = true` en un equipo de puertas simples → 422 `apertura_automatica_no_disponible`, auditado igual que `f0_no_disponible`. Desactivarla siempre se permite. Mensaje en la pantalla: `opciones.err_apertura_puertas_simples` (es/en), mapeado en `sesion_backend.py` y `parametros_ciclo_controller.py`.
- **Grupo nuevo "Cámara segura"** (`camara_segura`; es "Cámara segura", en "Safe chamber"): `temp_max_apertura` y `rango_presion_atm` pasan del grupo `puerta` a este en `config/global_params.json`. El grupo `puerta` queda solo con `timeout_puerta` (su descripción cambió a "Tiempo límite de movimiento de la puerta"). El grupo sale de la descripción del archivo, no de la base: no hace falta migrar `system_params`.
- **Lista de grupos del backend:** `GET /system_params` devuelve ahora `grupos` (`config_manager.grupos_visibles`), ya filtrada por perfil: sin `puerta` ni `empaque` con puertas simples; y solo los parámetros de esos grupos. `OpcionesParametrosEquipo.qml` toma las tarjetas de `control.grupos` (antes, lista fija). Si el backend no trae `grupos` (versión anterior), el controlador muestra todos.

## D9-4. Refresco al guardar

- `ParametrosEquipoController.parametrosGrupo`: propiedad notificable (`parametrosGrupoChanged`, emitida en `cargar()` —que corre tras cada guardar/restablecer— y al cambiar de submenú). La lista usa `model: control.parametrosGrupo` en vez de `control.delGrupo(control.grupo)`. Comprobado que la prueba nueva falla con el enlace viejo ("80.0 °C" tras guardar 75) y pasa con el nuevo.
- Barrido de todas las pantallas `Opciones*.qml` (`model:` y enlaces que llaman a un `@Slot` con resultado):
  - `OpcionesParametrosEquipo.qml`: el caso de H12 (corregido).
  - `OpcionesUsuarios.qml` `motivoSeleccionado`: `motivoSobre()` solo dependía de `usuarios`; ahora lee también `control.motivo` (señal `permisosChanged`) para reevaluar al cambiar el rol o el usuario de la sesión.
  - `OpcionesCalibracionSensor.qml` `resultado`: `calcular()` usa la calibración vigente del controlador; ahora lee `controlador.calibracion` para recalcular al guardarla.
  - `OpcionesParametrosCiclo.qml`: todos sus `model:` ya son propiedades notificables (`parametros`, `secciones`, `programas`, `sensores`, `entradasHabilitadas`); se agregó prueba QML de refresco tras guardar.
  - El resto (`Bitacora`, `CalibracionAtm`, `Conectividad`, `EntradasSalidas`, `InfoSistema`, `Mantenimiento`, `Reasignacion`, `Respaldo`, `FechaHora`): los `model:` son propiedades o listas literales; las llamadas restantes están en manejadores (`onClicked`, funciones), no en enlaces.

## D9-5. Entradas NC interpretadas (revierte ES-11 solo para las NC)

- YAML de la instancia (`config/instances/ACV-2026-001.yaml`): sección nueva `di_contacto`, con `nc: true|false` para cada DI del máximo físico. NC: `paro_emergencia`, `atrapamiento_puerta_1`, `atrapamiento_puerta_2` (Q5). El atrapamiento solo aparece en E/S si el perfil tiene puertas con atrapamiento (filtro de D8-3.17, sin cambios: hoy solo `advanced`).
- `io_names.leer_nc()`; si falta la sección o una entrada, rige `NC_POR_OMISION` (la misma lista). `canales_digitales("DI")` agrega `nc` a cada canal (`GET /io/channels`).
- `domain/entradas_salidas.presentar_entradas`: agrega `nc` y `nivel` (crudo). `activo` es el nivel crudo, o su inverso si es NC (1 = inactiva; 0 = activa).
- `OpcionesEntradasSalidas.qml`: en las NC, junto a ACTIVO/INACTIVO, el nivel crudo en pequeño (`io.ui.nivel_crudo`: "Nivel {nivel}" / "Level {nivel}").
- Solo presentación: la lógica del paro (`devices/paro_emergencia`) y del atrapamiento sigue tratando esas entradas como NC en el código. No lee el YAML.

## Capturas

`docs/informes/tanda9/capturas/p9/` (16): `P9_{simples|automaticas}_{es|en}_{1_ciclo_finalizacion|2_equipo_entrada|3_equipo_camara_segura|4_entradas_salidas}.png`. Las genera `tests/p9_capturas_banco.py` (offscreen, con un doble del backend; los datos salen de los mismos módulos que usa el backend). Puertas simples: Finalización con 2 parámetros y 6 tarjetas sin Puerta ni Empaque. E/S: paro en "INACTIVO · Nivel 1". Puertas automáticas: Finalización con 4 parámetros y 8 tarjetas. E/S: atrapamiento 1 en "INACTIVO · Nivel 1" y atrapamiento 2 en "ACTIVO · Nivel 0".

## Commits

- `cc3c616` feat(tanda9-p9): entradas NC interpretadas en Entradas/Salidas (D9-5)
- `9b9e3f4` feat(tanda9-p9): puertas simples, grupo Camara segura y refresco al guardar (D9-3, D9-4)
- (este informe y las capturas en el commit siguiente)

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-ad265c7339bc98e37\src\autoclave\__init__.py`

- Nueva: `tests/test_p9_opciones_puertas_nc.py`: **33 passed**. Cubre perfil, grupos, backend (422, sección Finalización, `/system_params`), controlador, refresco QML de Parámetros del equipo y del ciclo, NC (YAML, omisión, canales, interpretación, sin enlace).
- Actualizadas: `tests/test_o2a_parametros_equipo.py` (grupo `camara_segura`, 8 tarjetas) y `tests/test_i18n.py` (sufijos de `equipo_grupos`).
- Pruebas de los módulos tocados y de los que los importan (97 archivos, `grep -rl` en `tests/`): **2280 passed, 2 skipped, 6 failed**. Los 6 fallos eran todos de `test_o2a_parametros_equipo.py`, esperados por el cambio de grupo. Tras actualizarla: `test_o2a_parametros_equipo.py` + `test_p9`: **116 passed**.

## DECISIONES SIN CONFIRMAR

1. Puertas simples = solo `door_type: simple`. `motorized`, `locking` y `motorized_locking` conservan la apertura automática y los grupos Puerta y Empaque.
2. `timeout_temperatura` (Finalización) sigue visible con puertas simples, aunque solo lo usa la apertura automática. La decisión solo nombra los otros dos.
3. Una entrada NC con el enlace vivo pero sin lectura se muestra "Sin datos" (D-ES-04: no se inventa un valor), no "Activo". La lógica del paro sí trata la falta de dato como paro.
4. Los parámetros ocultos (`timeout_puerta`, `presion_empaque`, `vacio_empaque`, `tiempo_espera_apertura`) siguen siendo modificables por la API. Solo se rechaza activar `apertura_automatica`.
5. Sin perfil cargado se muestra todo (como antes).

## PREGUNTAS PARA CRISTIAN

1. Un programa que ya tenga `apertura_automatica = true` en un equipo de puertas simples (copiado, restaurado o editado antes de este cambio) no se corrige. Al terminar el ciclo, `CicloState._mantener_apertura_automatica` esperaría sin fin a que la puerta se mueva (avisa con `APERTURA_AUTOMATICA_DENEGADA`). ¿Se fuerza a `false` al cargar el programa, o se bloquea el inicio del ciclo? (Es una transición de ciclo/puerta: no se tocó.)
2. Lo mismo al duplicar o importar un programa: hoy no se revisa la apertura automática según el perfil.
3. `revisa_empaque()` vale True para `motorized`/`locking`, pero esos tipos no tienen sensor de empaque (solo `advanced`). ¿El grupo Empaque se oculta también para ellos?

## Pendientes

- La interfaz PySide antigua (`ui_pyside/views/params_ciclo`) no se tocó.
- Archivos de choque tocados: `i18n/es.json` y `i18n/en.json` (claves nuevas `opciones.equipo_grupos.camara_segura`, `opciones.equipo_grupos_desc.camara_segura`, `opciones.err_apertura_puertas_simples`, `io.ui.nivel_crudo`; cambiada `opciones.equipo_grupos_desc.puerta`), `backend/server.py` (`/system_params`, `_hojas_seccion`, `/cycle/parameter`), `sesion_backend.py`. Sin cambios en `db_manager.py` (sin migración), `control_loop.py`, `set_io.py` ni el catálogo de alarmas.
