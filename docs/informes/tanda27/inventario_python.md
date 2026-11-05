# Inventario de código Python sin uso en `src/autoclave` (tanda 27, solo análisis)

Rama `tanda27`. No se borró ni editó nada; este es el único archivo escrito. Alcance: sin `ui_pyside` (otro agente) y sin lo del ESP32/serial.

## Método

1. **Grafo de importación** (script AST propio fuera del repo, `ast.walk` sobre los 298 `.py` de `src/autoclave`; cuenta importaciones dentro de funciones, relativas, `from pkg import submódulo` y cadenas literales `autoclave.x.y`). Raíces: `exe_unico` (y todos sus `--rol`: backend, ui, ajustes, instalar, asociar-tactiles, configurar-modulo), `backend.main`, `backend.server`, `backend.server_reasignacion`, `simulador.__main__`, `ui_qml.app`, `ui_qml.lanzar`, `ui_pyside.app`, `instalador_exe`, los `hiddenimports` de `packaging/Autoclave.spec` (`_build_info`, `protocols.modbus_link(_config)`, `estacion.asociar_tactiles/_ventanas/instancia_unica`) y la única carga dinámica (`importlib` en `backend/rutas/_comun.py`, que carga `server`/`server_reasignacion`, ya raíces). Los 4 `.spec` tienen como script `exe_unico.py`, `backend/main.py`, `ui_pyside/app.py` y `tools/generador/lanzador.py`; `[project.scripts]` apunta a `ui_qml.lanzar:main`.
2. Resultado: **293 de 298 módulos alcanzables**. Se comprobó además qué módulos solo son alcanzables vía `ui_pyside` (1) y vía `simulador` (el simulador mismo, ver abajo) y cuáles solo los importa un `__init__.py`.
3. **vulture 2.16** (`--min-confidence 80` y `60`) para símbolos muertos en módulos vivos. Cada símbolo se cruzó con un contador de palabras sobre `src` (incluye QML/JSON/YAML), `tests`, `tools` y `packaging` (comando: contador `\w+` por carpeta; «src_otros» = apariciones fuera de la definición), y luego con `docs/`, `CLAUDE.md` y los marcadores `req(`.
4. Los ~170 «unused function» de `backend/rutas/*`, `server_reasignacion.py`, `server.py` y `simulador/servidor.py` son **falsos positivos** (rutas FastAPI decoradas); no se listan. Idem `@Slot`/`@Property` de QML que sí se usan desde `.qml`.

Conteos vulture: confianza 80 = 6 hallazgos (4 son `checked` en `ui_pyside`, 1 `full_scale` en `converters.py:136`, 1 import `parametros_globales` en `preparacion.py:2`); confianza 60 = 728 líneas (577 fuera de rutas/simulador/ui_pyside).

---

## 1. Módulos completos

Ningún módulo cumple los 5 criterios. Cinco no tienen importador desde un punto de entrada vivo:

| Módulo | Evidencia | a | b | c | d | e | Veredicto |
|---|---|---|---|---|---|---|---|
| `ui_qml/domain/alarmas.py` | Grafo: sin importadores en `src`; solo `tests/test_alarmas_domain.py`. `rg -w alarmas.py docs` | sí | sí | sí | NO: `docs/mis_plans/planeacion_ui_dual_pantalla.md` (F8) y `analisis_sistema_alarmas.md` lo citan como base de las partes B/C de alarmas; D2_depuracion (tanda 7, P3) recomendó conservar | sin `req` | DUDOSO (decisión de Cristian: plan de alarmas B/C pausado) |
| `ui_qml/domain/reconexion.py` | Igual; solo `tests/test_reconexion.py`; planeación F3 (WebSocket) | sí | sí | sí | NO (F3) | sin `req` | DUDOSO (mismo motivo) |
| `ui_qml/domain/telemetria.py` | Igual; solo `tests/test_telemetria_validacion.py` | sí | sí | sí | NO (F3) | sin `req` | DUDOSO (mismo motivo) |
| `ui_qml/historial_ejemplo.py` | Sin importadores en `src`; lo usan `tests/helpers/reportes_ejemplo.py`, `tests/helpers/textos_caben_qml.py`, `tests/test_v8b_textos.py`, `tests/banco/rep_capturas_reportes.py`, `tools/demos_qml/prueba_menu_principal.py` y el comentario de `Pruebas/PruebaMenuPrincipal.qml` | sí | sí | NO (nombre en pruebas/banco/QML de prueba) | NO (banco de capturas) | sin `req` | DUDOSO (es apoyo de pruebas y demos; no es código de producto pero se usa) |
| `installation/cambio_perfil.py` | Sin importadores en `src`; lo usan `tools/declarar_entradas_suministro.py`, `declarar_sondas_temperatura.py`, `emparejar_modulo_es.py` (este nombrado en CLAUDE.md) y `tests/test_automatizacion_perfil.py`, `test_m1_modelo.py`; CLAUDE.md cita `cambio_perfil.CAMPOS_DE_IDENTIDAD`; `docs/riesgos/registro_riesgos.md` | sí | sí | NO | NO | citado en riesgos (AUT) | DUDOSO (herramienta vigente + riesgos) |

Alcanzable solo por `ui_pyside`: `services/domain/logging/cycle_params_audit.py` (se evalúa con el otro agente; se pierde su uso si `ui_pyside` se retira).
Alcanzables solo por el simulador (no está en el .exe, `excludes=['autoclave.simulador']`): `simulador/{__init__,__main__,autenticacion_simulada,repeticion,reportes_sim,servidor}.py`. `simulador/__main__.py` es punto de entrada declarado en el encargo: se tratan como vivos.
Módulos importados solo por un `__init__.py` (`ui_qml/controllers/*_controller.py`, `ui_qml/bridge/detalle_aviso_qml.py`): son registros QML en el `__init__`, VIVOS (no es uso muerto).

**Quién importa `ui_pyside` desde fuera de él** (para el otro agente): `exe_unico.py` (`ui_pyside.app` en `--rol ajustes`), `ui_qml/app.py` (`ui_pyside.views.nuevo_usuario.puente`), `ui_qml/bridge/lanzador_ajustes.py` (`ui_pyside.app`); `packaging/Autoclave.spec` lo fija como `hiddenimport` y `AutoclaveSettings.spec` lo compila como script.

---

## 2. Funciones, clases, métodos y constantes sin ninguna referencia (src/tests/tools = 0, docs sin proceso vigente)

BORRABLE significa: criterios a–e cumplidos según lo buscado; beneficio por ítem es pequeño. Todas verificadas con vulture 60 + contador de palabras (`src_otros=0`, `tests=0`, `tools=0`) + `rg -w` en `docs/` y `CLAUDE.md` (sin menciones, salvo donde se indica).

| Símbolo | Evidencia | a–e | Veredicto |
|---|---|---|---|
| `cliente/ui_service_backend.py`: `_snapshot` (127), `get_sensores_di` (161), `get_estado_puertas` (191), `get_fase_ciclo` (239), `get_fase_en_sostenimiento` (244), `get_prevacio_progreso` (249), `get_temp_camara_2` (258) | 0 referencias en src/tests/tools; sin `getattr` dinámico sobre el servicio. `docs/` solo en planes de mayo (`suministro-electrico`, `responsive-orientacion`), históricos | a–e sí | BORRABLE (7 métodos; el resto de la clase tiene uso) |
| `core/managers/catalogo_parametros.py`: `CERO_VALIDO` (187) | 0 referencias | sí | BORRABLE |
| `core/managers/limites_equipo.py`: `CLAVES_LIMITES` (36) | 0 referencias | sí | BORRABLE |
| `core/managers/gestion_programas.py`: atributo `_entradas_previas` (328) | solo se escribe, nadie lo lee | sí | BORRABLE |
| `core/runtime/asignacion_io.py`: método `guardar_texto` (714) | 0 referencias (existen `guardar_bytes` y el atómico) | sí (datos persistidos: se borra el método, no el dato) | BORRABLE |
| `core/runtime/status.py`: `reset_flags` (288) | 0 referencias | sí | BORRABLE |
| `devices/buzer/buzer.py`: `BEEP_AVISO` (74) | 0 referencias (`BEEP_ALARMA` sí lo tiene en pruebas) | sí | BORRABLE |
| `estacion/_ventanas.py`: `cambiar_texto` (97), `reafirmar` (102) | 0 referencias; módulo en hiddenimports pero esos métodos no | sí | BORRABLE (bajo valor) |
| `estacion/_win32.py`: constantes `WS_VISIBLE, WAIT_OBJECT_0, WAIT_TIMEOUT, WM_DESTROY, WM_ERASEBKGND, DT_VCENTER, EVENT_MODIFY_STATE, SYNCHRONIZE, RID_INPUT` | 0 referencias | sí | BORRABLE, pero valor ≈ 0 (tabla de constantes de la API de Windows): recomendado dejarlas |
| `hal/measures/units.py`: `get_temperature` (150), `get_last_update` (256) | 0 referencias (`get_pressure` tiene 5 en pruebas) | sí | BORRABLE |
| `ui_qml/bridge/progreso_ciclo.py`: `faseCiclo` (135, Property) | sin lectura desde QML ni Python | sí | BORRABLE |
| `ui_qml/bridge/unidades_qml.py`: `simboloTemp` (103), `simboloPres` (107) | sin lectura desde QML ni Python | sí | BORRABLE |
| `ui_qml/controllers/calibracion_atm_controller.py`: `referenciaUsuario` (374); `conectividad_controller.py`: `redConectada` (319) | sin lectura desde QML ni Python | sí | BORRABLE |
| `ui_qml/controllers/entradas_salidas_controller.py`: `INACTIVIDAD_UI_S` (93) | 0 referencias | sí | BORRABLE |
| `state_machine/states/preparacion.py:2` import `parametros_globales` (vulture 90 %) | import sin uso en el módulo | sí (state_machine: solo import) | BORRABLE (limpieza de una línea; ver nota abajo sobre `parametros_globales.py`) |
| `hal/measures/converters.py:136` variable `full_scale` (vulture 100 %) | asignada y no leída | sí | BORRABLE (variable local) |

Falsos positivos descartados de la lista: `config/calibration_writer.py:132 preserve_quotes` (atributo de ruamel), `estacion/digimon.py:174 nuevo_nombre` (variable de bucle sin uso, inofensiva).

---

## 3. DUDOSOS (sin uso en producción, pero algún criterio falla o es zona protegida)

| Símbolo | Evidencia | Motivo del DUDOSO |
|---|---|---|
| `devices/io/set_io.py`: 16 métodos `abrir/cerrar/bloqueo/desbloqueo_puerta_{1,2}_on/_off` (230–332) | 0 referencias (src/tests/tools); las puertas usan canales vía `factory._build_door_cfg` | Código de puertas (interlock): requiere `auditor-iec62304` y revisión; no borrar sin ella |
| `services/domain/puertas/ser_puertas.py`: `can_open`, `can_close` | 0 referencias | `docs/informes/tanda8/D8_depuracion.md` y `tanda7/D2_depuracion.md` los conservan expresamente (barrera de permisos por rol pendiente); puertas |
| `state_machine/machine/parametros_globales.py` (constantes `PRESION_ATMOSFERICA, RANGO_PRES_ATMOSFERICA, TEMP_DRENAJE, MARGEN_MINIMO_ENTRADA_ESTERILIZACION`) | nadie lee los valores; `ser_puertas.py:33` importa la clase y `preparacion.py:2` la instancia sin usarla | Zona state_machine/seguridad; el handoff 2026-07-22 documenta `MARGEN_MINIMO...`; comprobar a mano que ya vive en otro sitio |
| `state_machine/cycle_phases/base_fase.py`: `_temp_camara_2` (89) | 0 referencias | CLAUDE.md: «Pendiente: sensor de líquido secundario»; fases |
| `protocols/modbus_link.py`: `REG_NEGOCIACION` (126) | 0 referencias | Mapa de registros del módulo E/S (documentación en código) |
| `devices/paro_emergencia/paro_emergencia.py`: `rising_edge`, `falling_edge`, `AVISO_CABLEADO_NC` | solo pruebas | Paro de emergencia; solo pruebas |
| `state_machine/alarms/alarm_manager.py`: `has_emergency`, `has_active_alarms` | solo pruebas | Alarmas; `D2_depuracion` los conserva |
| `hal/measures/converters.py`: `presion_en_falla`, `reiniciar_presiones` | solo pruebas, varias con `req` (`test_t19_s2_conversion`, `test_t23_ain_*`) | Criterio e (req) |
| `core/runtime/asignacion_io.py`: `canal_crudo`, `restablecer_memoria_fabrica_codigo` (29 usos en pruebas), `limpiar_pendiente` | solo pruebas, con `req` en varias | Criterio e |
| `core/managers/catalogo_parametros.py`: `errores_recuperacion` | solo `tests/test_t16_s4_programas.py` (con `req`) | Criterio e |
| `_version.py`: `semver_a_pep440`, `pep440_a_semver` | solo `tests/test_ver_version.py` (con `req`) | Criterio e; CLAUDE.md fija `_version` como fuente única |
| `core/runtime/aire_atmosferico_prueba.py`: `es_salida`; `core/runtime/respaldo.py`: `programas_del_respaldo`; `devices/factory/factory.py`: `build_hardware` (7 en pruebas); `installation/activacion_v2.py`: `transporte_disponible`; `ui_qml/domain/detalle_aviso.py`: `sufijos_i18n`; `ui_qml/domain/entradas_salidas.py`: `origen_de`; `ui_qml/domain/pantalla_ciclo.py`: `lecturas_de_status` (7); `ui_qml/controllers/*` y `bridge/*`: `hayCiclo, faseTerminacion, cerrarDia, actualizarIdioma, periodosValidos, puedeSiguiente, intervaloMs, roleNames, siguienteUsuario, siguienteTipo, hastaEsHoy, ordenPendiente, programaPersonalizado, entradasHabilitadas, entradasDisponibles, digitos, simbolos, teclaSigno, teclaPunto, permiteNegativo`; `backend/arranque/registro.py`: `etapa_actual`, `estado_de`; `services/.../db_manager.py`: `ESQUEMA_VERSION`, `get_version_esquema`, `indice_numero_unico`; `state_machine/alarms/catalogo.py`: `CODIGOS_CONSERVADOS`; `protocols/enlace.py` constantes; `utils/resources.py`: `SUBCARPETA_PROGRAMA/DATOS`; `core/runtime/mantenimiento.py`: `TIPOS_HISTORICOS`; `ui_qml/controllers/info_sistema_controller.py`: `CLAVES_FILA` | Solo los usan pruebas (sin llamador de producto, o los llama QML por nombre con otro patrón); borrarlos obliga a editar pruebas | DUDOSO en bloque: si Cristian quiere, se borran junto con sus pruebas, una a una; no se hizo por riesgo/beneficio |
| `installation/activation.py`: `configurar_secretos` (usado por `tests/conftest.py`), `huella_instalacion`, `validate_factory_key`; `installation/secretos.py`: `entrada_compilacion*` | pruebas y/o `.spec` (los `.spec` llaman `entrada_compilacion*`, así que son VIVOS) | Licencia/activación; criterio b para `secretos`; `validate_factory_key` solo `tests/test_activation.py` |
| `installation/cambio_perfil.py: escribir_campo` | usado por 3 `tools/` | Vivo vía herramientas |
| Módulos §1 (`alarmas`, `reconexion`, `telemetria`, `historial_ejemplo`, `cambio_perfil`) | ver §1 | ver §1 |

---

## 4. Pruebas que solo prueban código BORRABLE

- Código BORRABLE de §2: **ninguna prueba lo ejercita** (`tests=0` en todos). No hay pruebas que borrar junto con ellos.
- Si Cristian decide además borrar los módulos DUDOSOS sin cablear de `ui_qml/domain`, se borrarían con ellos: `tests/test_alarmas_domain.py`, `tests/test_reconexion.py`, `tests/test_telemetria_validacion.py` (ninguna tiene `req`). Además habría que quitar `tests/__pycache__` y las menciones de `docs/mis_plans/planeacion_ui_dual_pantalla.md`. Pruebas indirectas de los QML `components/alarms/*` no se comprobaron.

---

## 5. Dependencias (`pyproject.toml`, `requirements*.txt`, lock)

Imports de terceros en `src/autoclave` (sin `ui_pyside` no cuenta): `PIL`, `PySide6`, `shiboken6`, `escpos`, `fastapi`, `keyring`, `psutil`, `pydantic`, `pymodbus`, `requests`, `ruamel`, `uvicorn`, `win32print`, `yaml`.

- Dependencias de `pyproject.toml` que nadie importa fuera de `ui_pyside` y del ESP32: **ninguna**. `PySide6-Fluent-Widgets[full]` (`qfluentwidgets`) solo lo importa `ui_pyside` (se queda mientras el engrane de ajustes exista; el `.spec` ya documenta que `scipy` lo necesita transitivamente).
- `pyserial` ya no está en el lock ni instalado (retirado en la tanda 20).
- En `requirements.lock.txt` los paquetes `numpy`, `scipy`, `colorthief`, `darkdetect`, `PySideSix-Frameless-Window` (de `qfluentwidgets`) y `python-barcode`, `qrcode`, `six`, `appdirs`, `argcomplete`, `pywin32-ctypes` (de `python-escpos`/`keyring`) son transitivas: nadie las importa directamente, no se deben quitar. `requirements-dev.txt`: `python-multipart` lo exige el generador (`tools/generador`); `httpx` las pruebas; `pyinstaller*` la compilación.
- Nada que borrar.

---

## 6. Resumen

- 298 módulos, 293 alcanzables; 5 sin importador de entrada viva, **los 5 DUDOSOS** (0 borrables).
- Símbolos BORRABLES (criterios a–e cumplidos): unos 33 (7 métodos del cliente, 11 constantes de `_win32`/otras, métodos/propiedades QML y utilidades sueltas, import y variable de vulture-80). Ninguno tiene pruebas.
- DUDOSOS: ~90 símbolos (puertas, paro, alarmas, licencia, `req`, solo-pruebas).
- Dependencias sobrantes: 0.
