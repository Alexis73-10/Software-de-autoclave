# Hallazgos NRM — NTC-IEC 62304:2019 (IEC 62304:2006) — Software de Autoclave

Estado: v0.1 — 2026-10-07. Fuentes: declaración de Cristian (P-02) y paquete 3.1 (rama `dev`, commit `e7bccf2`).
**Baseline de auditoría desde 2026-10-08:** rama `audit/62304-snapshot` (hash `8d1884c`) = `dev` e7bccf2 + cambios sin commit del directorio de trabajo. Los informes de los paquetes 3.2 en adelante citan esa rama. El paquete 3.1 se ejecutó antes: sus tablas B y C reflejan el directorio de trabajo (incluyen módulos sin versionar, p. ej. `crc16.py`), y sus datos de git (commits, tags, ramas) reflejan `dev` e7bccf2.
Severidad = propuesta; la valida el responsable técnico. Solo planeación: ninguna acción se implementa durante la auditoría.

---

## NRM-01 — Clase C declarada sin fichero de gestión de riesgos
- **Severidad:** Crítica
- **Cláusulas:** 4.2, 4.3 c, 7.1.4, 7.1.5, 7.2.1, 7.3.3 (y, por dependencia, 7.1.1–7.1.3, 7.2.2, 7.3.1–7.3.2, 7.4)
- **Evidencia:** declaración de Cristian, 2026-10-07: no existe fichero ISO 14971.
- **Descripción:** no hay peligros, causas, secuencias de eventos ni medidas de control documentados. Sin ellos no es posible demostrar la clasificación ni trazar medidas de control a sus verificaciones.
- **Relacionados:** C-01, H-03, LIQ-01 y demás hallazgos previos son candidatos a entradas del fichero (causas potenciales).
- **Candidatos añadidos el 2026-10-08 (etapa 4 de autenticación, `plan_t8_login_qml.md`):**
  - **Token huérfano sin expiración** (riesgo residual aceptado, spec de autenticación §6.3): un login cuya respuesta no llega a la UI, o un cierre sin logout, deja un token válido hasta el reinicio del backend. Tokens de 256 bits (`secrets.token_urlsafe(32)`), solo en memoria, backend en 127.0.0.1.
  - **H-T8-01** (Alto): `POST /auth/change_password` no contaba los fallos de la clave actual (`server.py:288-294`); con una sesión ajena abierta se podían probar contraseñas sin límite. Control aprobado: contador compartido con el login, 429 al 5.º fallo e invalidación del token.
  - **Bloqueo de un usuario legítimo por terceros** (riesgo residual aceptado, spec de autenticación §6.4): 5 intentos fallidos bloquean 5 min a un usuario real. Afecta al acceso a Opciones, no a los ciclos (endpoints operativos sin token).
- **Acción propuesta:** construir el fichero desde cero (Fase 4), empezando por las funciones de seguridad ya identificadas en el código (ver sección "Insumos" más abajo).
- **Estado:** Abierto

## NRM-02 — Cambios sin trazabilidad a solicitud de cambio
- **Severidad:** Alta
- **Cláusulas:** 8.2.4 (también 8.2.1, 6.2.4)
- **Evidencia:** paquete 3.1-D: 1 de 519 commits en `dev` cita un identificador de cambio o hallazgo (`aa900f1`, 2026-09-29); búsqueda ampliada a NRM-, NU-, G- sin resultados adicionales. Varios commits citan planes por nombre (p. ej. `a01dfc5` → `planeacion_teclados_qml`).
- **Descripción:** existen planes y specs por subsistema, pero no hay enlace verificable commit ↔ solicitud de cambio ↔ aprobación. Calificado a nivel de commits; falta revisar si hay registros de aprobación en otro lugar.
- **Relacionados:** NRM-03.
- **Acción propuesta:** definir PRO-03 (solicitud de cambio) y convención de ID en el mensaje de commit.
- **Estado:** Abierto

## NRM-03 — Identificación de versión y liberación no formalizada
- **Severidad:** Media
- **Cláusulas:** 8.1.1, 8.3, 5.8.4 (relacionadas: 5.8.5, 5.8.7, 5.8.8)
- **Evidencia:** paquete 3.1-D/E: sin tags (`git tag -l` vacío); versión `0.5.0` única en `pyproject.toml:7`; sin `__version__` ni `VERSION`; 7 ramas locales y 3 worktrees paralelos; correspondencia entre `0.5.0` y lo compilado en `dist/` NO VERIFICADO.
- **Descripción:** hay versión declarada y registrada en el ciclo (`cycle_logger.py:37-44`), pero no esquema documentado de identificación de elementos de configuración (incluidos SOUP y documentos) ni registro de liberación.
- **Acción propuesta:** PRO-07 (liberación y archivo) y esquema de identificación (PRO-02).
- **Estado:** Abierto

## NRM-04 — Sin política de control documental
- **Severidad:** Media
- **Cláusulas:** 8.1.3, 8.3, 5.1.8 d), 5.1.9, 5.1.11
- **Evidencia:** paquete 3.1-F: varios planes de `docs\mis_plans\` (autenticación, protocolo serial ESP32, opciones, migración QML, sensores, etc.) y 7 informes de `docs\informes\` figuran sin versionar `(u)`. Confirmación de Cristian (2026-10-07): **no existe política** sobre qué documentos se versionan ni cómo se aprueban.
- **Descripción:** documentos que especifican comportamiento de seguridad (autenticación, protocolo serial) están fuera de control de configuración. 5.1.8 d) exige procedimientos y responsabilidades de desarrollo, revisión, aprobación y modificación de documentos.
- **Acción propuesta:** definir en PRO-01/PRO-02 qué documentos son elementos de configuración, dónde viven, cómo se aprueban y cómo se versionan.
- **Estado:** Abierto

## NRM-05 — Código de seguridad en desarrollo sin control de configuración
- **Severidad:** Alta
- **Cláusulas:** 5.1.11, 8.2.1, 8.3 (relacionadas: 8.1.3, 7.4)
- **Evidencia:** `git status` (2026-10-08) sobre `dev` e7bccf2:
  - Modificados sin commit: `services/domain/loop/control_loop.py`, `protocols/serial_link.py`, `backend/server.py`, `backend/context.py`, `backend/main.py`, `services/domain/logging/db_manager.py`, además de los módulos de roles/sesión/login/permisos.
  - Nuevos sin versionar: `protocols/crc16.py`, `protocols/serial_link_config.py`, `config/serial_link.json`, `backend/autenticacion.py`, `backend/contrasenas.py`, `core/managers/validacion_config.py`, y sus pruebas (`test_crc16.py`, `test_serial_link_v2_lector.py`, `test_backend_autenticacion.py`, `test_db_audit_log.py`, `test_config_invalida_arranque.py`).
  - Eliminados sin commit: `utils/git_autocommit.py` y `tests/test_git_autocommit.py`.
- **Descripción:** las unidades de Clase C que implementan CRC del enlace, autenticación y validación de configuración, junto con sus pruebas y los planes que las especifican (NRM-04), existen solo en el directorio de trabajo. No hay historial ni aprobación enlazada a esos cambios. Puede ser estado transitorio de trabajo ya aprobado pendiente de commit; la fotografía `audit/62304-snapshot` evita que la auditoría pierda evidencia, pero no sustituye el control de configuración.
- **Relacionados:** NRM-02, NRM-03, NRM-04; H-03.
- **Acción propuesta:** cuando Cristian confirme visualmente cada bloque, commitearlo en `dev` en commits lógicos con el nombre del plan en el mensaje; definir PRO-03.
- **Estado:** Abierto

## NRM-06 — Planes de proceso y seguridad no sincronizados con el código
- **Severidad:** Alta (propuesta)
- **Cláusulas:** 5.2.6 (b, f), 5.4.4, 8.2.3, 7.4.1–7.4.2
- **Evidencia:** lote 1 (base `8d1884c`): de 148 afirmaciones verificables en 4 planes, 99 coinciden y 31 difieren; 15 comportamientos del código no están documentados. Los commits `cee1cc4`, `0477fd1`, `c4b64ab`, `2f59198`, `93b33dc` y `410109f` modificaron áreas cubiertas sin actualizar el plan. Los planes de esterilización y F0 se contradicen entre sí (DSC-L1-07).
- **Descripción:** los requisitos escritos de calentamiento, esterilización, F0 y alarmas no reflejan el código vigente, y entre dos de ellos hay contradicción. Sin saber cuál manda (plan o código) no se puede verificar el requisito ni analizar el impacto de los cambios.
- **Relacionados:** NRM-02, NRM-04.
- **Pendiente:** decisión de Cristian plan vs código (preguntas 1, 5, 7 del lote 1). Lotes 2–5 sin revisar.
- **Estado:** Abierto

## NRM-07 — Valores por defecto silenciosos en parámetros de seguridad
- **Severidad:** Alta (propuesta)
- **Cláusulas:** 5.2.2 b (valores por defecto, rangos), 5.5.4 h, 7.1.2 a
- **Evidencia:** lote 1: DSC-L1-02 (empaque de puertas con default 300, sin chequeo si el sensor es None), DSC-L1-03 (el patrón `or defecto` reemplaza 0 o ausencia), DSC-L1-13 (perfiles `user/` 9/2 frente a 11/3 del plan).
- **Descripción:** un parámetro ausente o con valor 0 puede sustituirse por un defecto sin aviso. Si 0 es un valor legítimo, el comportamiento cambia sin que el operador lo sepa.
- **Pendiente:** preguntas 3 y 4 del lote 1 (origen de 300/0.6, semántica de 0, rol de `validacion_config.py`).
- **Estado:** Abierto

## NRM-08 — Manejo de sensor None sin garantía a nivel de fase
- **Severidad:** Alta (propuesta; candidata a Crítica según salidas de los "escapes")
- **Cláusulas:** 5.5.4 d, 5.2.3, 7.1.2 b/d
- **Evidencia:** lote 1: DSC-L1-01 (sensor None sin timeout; escapes congelados), DSC-L1-02 (puertas sin chequeo de None), DSC-L1-08 (F0 integra huecos de enlace).
- **Descripción:** ante pérdida de lectura de temperatura o presión no hay garantía, por fase, de qué hacen las salidas ni de cuánto puede durar el estado. F0 puede acumular durante huecos de comunicación.
- **Pendiente:** pregunta 2 del lote 1 (estado de las salidas en los "escapes" y trazado de None); cruzar con paquetes 3.3a y 3.3c.
- **Estado:** Abierto

## NRM-09 — Catálogo de alarmas desalineado con las alarmas reales
- **Severidad:** Media (propuesta; Alta si DSC-L1-10 resulta insegura)
- **Cláusulas:** 5.2.2 d, 5.2.6
- **Evidencia:** lote 1: catálogo coincide en 24 de 34 afirmaciones; faltan `CHAQUETA_SOBRECALENTADA` (PREPARACION) y `CONFIGURACION_INVALIDA`; DSC-L1-09 (`TIMEOUT_F0` no existe), DSC-L1-10 (`PARO_EMERGENCIA` con `recoverable=True` en PREPARADO/PREPARACION), DSC-L1-11 (`FALLO_CONEXION`/`NO_HAY_CONEXION` distintas del catálogo).
- **Pendiente:** pregunta 7 del lote 1 (plan vs código y efecto de `recoverable`). Hay trabajo de alarmas adelantado en la rama `alarmas-parte-a`, aún no auditada.
- **Estado:** Abierto

---

## Observaciones del paquete 3.1 aún sin clasificar
Se anotan como candidatas; no son hallazgos hasta recolectar más evidencia.

| # | Observación | Evidencia | Cláusula posible |
|---|---|---|---|
| O-01 | `pyproject.toml:32` declara el punto de entrada `autoclave.app:main`, pero `src/autoclave/app.py` no existe | `ls`: «No such file or directory» | 8.1 / 5.8.5 |
| O-02 | `README.md` referenciado en `pyproject.toml:9` no existe | paquete 3.1-F | 5.1.8 / 5.8.5 |
| O-03 | Solo 4 módulos Python con docstring de módulo (de 196 archivos) | paquete 3.1-B | 5.4.2 (diseño detallado por unidad); revisar si los `.docx` de `Documentacion\` lo cubren |
| O-04 | UI tkinter heredada sigue en el árbol (`ui/`, `main_window.py` 1052 líneas con términos de seguridad) junto a QML y PySide6 | paquete 3.1-B/C | 5.3.1 (arquitectura), 5.1.10 |
| O-05 | Tres ramas viven en worktrees paralelos (`alarmas-parte-a`, `roles-sensor-temperatura`, `anuncios-voz`) | `git worktree list` | 8.2, 5.1.11 |
| O-07 | Se eliminan `utils/git_autocommit.py` y su prueba (sin commit). Pregunta abierta: ¿qué hacía y quién lo usaba? Si versionaba automáticamente en campo, es relevante para 8.3 | `git status` 2026-10-08 | 8.2, 8.3 |
| O-06 | Firmware ESP32 en un solo archivo `.ino` de 229 líneas | paquete 3.1-C | 5.4.x, 5.5.x |

## Insumos para los siguientes paquetes (nombres reales confirmados)
Unidades con lógica de seguridad según 3.1 (clasificación heurística, no análisis de riesgo):
- `services/domain/loop/control_loop.py` (383 l.) · `core/runtime/status.py` · `core/runtime/letalidad.py` · `core/runtime/steam.py`
- `state_machine/state_machine.py` · `states/{ciclo,preparacion,preparado,emergencia,falla,hibernacion,control_banda}.py` · `cycle_phases/{precalentamiento,prevacio,calentamiento,esterilizacion,descompresion,secado,protocolo_fallo,valvula_reposo}.py` · `alarms/{alarm,alarm_manager}.py`
- Puertas: `devices/puertas/{advanced_door,simple_door,base_puertas,door_factory}.py` · `services/domain/puertas/{ser_puertas,door_command_service,permissions}.py`
- Salidas/seguridad física: `devices/io/set_io.py` · `devices/paro_emergencia/paro_emergencia.py` · `devices/suministro_electrico/suministro_electrico.py` · `devices/pump/pump.py`
- Comunicación: `protocols/{crc16,serial_link,serial_link_config,device_reset}.py` · firmware `.ino`
- Conversión/calibración: `hal/measures/{converters,units,calibration_tools}.py` · `config/{calibration_writer,schema}.py`
- API y autenticación: `backend/server.py` (1275 l.) · `backend/{autenticacion,contrasenas,context}.py`

Pruebas: 168 archivos `.py` en `tests/` (a evaluar en el paquete 3.5).

---

## Registro de discrepancias plan–código (resumen; detalle en los informes de cada lote)

### Lote 1 — base `8d1884c` — 148 afirmaciones: 99 COINCIDE, 31 DIFIERE, 3 EN OTRA RAMA, 15 SIN DOCUMENTAR
| ID | Sev. propuesta | Resumen | Hallazgo |
|---|---|---|---|
| DSC-L1-01 | Alta (cand. Crítica) | Sensor None sin timeout; salidas «congeladas» en los escapes | NRM-08 |
| DSC-L1-02 | Alta | Empaque de puertas con default 300 y sin chequeo si el sensor es None | NRM-07, NRM-08 |
| DSC-L1-03 | Alta | `or defecto` reemplaza 0 o valor ausente | NRM-07 |
| DSC-L1-04 | Alta | Limitadores de vapor/presión sin documentar | NRM-06 |
| DSC-L1-05 | Alta | Algoritmo de calentamiento distinto del plan | NRM-06 |
| DSC-L1-06 | Alta | RECUPERACION también se activa por presión | NRM-06 |
| DSC-L1-07 | Alta | Planes de esterilización y F0 contradictorios (F0 exige f0 y timeout 2x) | NRM-06 |
| DSC-L1-08 | Alta | F0 integra huecos de enlace | NRM-08 |
| DSC-L1-09 | Alta | Alarma `TIMEOUT_F0` no existe | NRM-09 |
| DSC-L1-10 | Alta | `PARO_EMERGENCIA` con `recoverable=True` en PREPARADO/PREPARACION | NRM-09 |
| DSC-L1-11 | Alta | `FALLO_CONEXION`/`NO_HAY_CONEXION` distintas del catálogo | NRM-09 |
| DSC-L1-12 | Alta | Catálogo sin `CHAQUETA_SOBRECALENTADA` ni `CONFIGURACION_INVALIDA` | NRM-09 |
| DSC-L1-13 | Alta | Perfiles `user/` 9/2 frente a 11/3 del plan | NRM-07 |
| DSC-L1-14 | Alta | Banda ESTABLE asimétrica | NRM-06 |
| DSC-L1-15 | Media | `time.time` frente a `monotonic` en los planes | NRM-06 |

Observaciones: OBS-L1-01 `advanced_door.py:372,462` usa `time.time` (fuera del lote; verificar en 3.3b y 3.4-C) · OBS-L1-02 el sensor secundario existe solo en una rama · OBS-L1-03 los planes no tienen commits que los citen.

### Preguntas abiertas del lote 1 (decisiones de Cristian)
Sin responder: 1) plan vs código en DSC-05/06/07/15 y PURGA · 2) salidas de los escapes y trazado de None · 3) sensor y origen de 300/0.6 (empaque) · 4) semántica de 0 y rol de `validacion_config.py` · 5) banda ESTABLE · 6) reanudación tras FALLO_CONEXION y F0 en huecos · 7) DSC-09 a 12: plan vs código y efecto de `recoverable` · 8) origen de 9/2 y `git_autocommit.py` (O-07) · 9) integración de `feature/roles-sensor-temperatura`.
