# Inventario de cadenas — F0 del plan de idiomas (i18n)

Software de Autoclave — Especifika S.A.S.
Fecha: 2026-10-08 · Rama `dev`, commit `30ed280` (con cambios locales sin commit en `server.py` y `serial_link.py`, que no se tocaron)
Plan de referencia: `docs/mis_plans/planeacion_i18n.md` v2
Tarea de solo lectura: no se modificó código, configuración ni datos.
Detalle fila por fila: `docs/mis_plans/inventario_cadenas_i18n.csv` (separador `;`, UTF-8 con BOM).

---

## 0. Cómo se hizo

- **QML:** extracción de literales de los 52 `.qml` de `src/autoclave/ui_qml/qml/` y cruce de cada llamada `tx("seccion","clave")` / `txRuta("seccion.clave")` contra `es.json`.
- **Python:** análisis con `ast` de los 199 `.py` de `src/autoclave/`. Se excluyen docstrings y comentarios, se separan los mensajes de log, las excepciones y el texto visible, y se descartan identificadores, rutas, SQL y colores.
- **Alarmas, persistencia, voz, fechas:** lectura dirigida del código. La voz se leyó en el worktree `.claude/worktrees/anuncios-voz`, rama `worktree-anuncios-voz`.
- **Límites del método:**
  - Las palabras sueltas en minúscula (`"listo"`, `"activa"`) se trataron como identificadores. Se revisaron a mano en QML; solo los meses de `BarraSuperior.qml` resultaron visibles.
  - En Python puede quedar alguna palabra suelta en minúscula sin detectar.
  - El CSV cuenta **cadenas literales**, no apariciones en pantalla.

---

## 1. Totales por superficie

| Superficie (D-01) | Filas CSV | Alarma-seguridad | Notas |
|---|---:|---:|---|
| A. UI QML — catálogo `es.json` | 229 | 20 | 277 entradas en total; 43 son de reportes/correo (fila D) y 9 de pantallas de prueba |
| A. UI QML — literales fijos en `.qml` (producción) | 18 | 0 | 8 en `Login.qml`, 8 en `NuevoUsuario.qml`, meses en `BarraSuperior.qml` |
| A. UI QML — texto que arma Python y entrega a QML | 25 + 4 | 0 | 4 de módulos en `ui_pyside/` que usa QML (roles, validación) |
| A. UI QML — pantallas y herramientas de prueba | 9 + 34 + 8 | 0 | `qml/Pruebas/`, `prueba_*.py`, `historial_ejemplo.py`, `lanzar.py` |
| B. Alarmas, fallas y eventos (dominio) | 49 | 41 | descripciones de `Alarm`, `motivo_fallo`, motivos de puerta |
| B. Mensajes del backend (API, campo `detail`) | 55 | 47 | rechazos 4xx/5xx en texto español |
| C. Persistencia (perfiles de ciclo, semillas, configuración) | 12 | 0 | ver §4 |
| D. Reportes PDF y correo | 43 + 2 | 0 | casi todo ya sale de `es.json` (`exportacion.*`) |
| D. Ticket térmico (ciclo, resumen, arranque, conectividad) | 45 | 7 | todo fijo en código Python |
| E. Logs técnicos | 300 | 0 | `logger.*` en los paquetes dentro del alcance |
| E. Consola (`print`, ayuda de argparse, `getpass`) | 45 | 0 | no es UI de operador |
| F. Voz | 32 | 23 | rama sin unir a `dev`; WAV de tono provisional |
| G. Formatos de fecha/hora/número | 27 | 0 | sitios de formateo, no cadenas traducibles |
| Otros (configuración, protocolos, excepciones internas) | 83 | 0 | |
| Otros — asistente de instalación (tkinter) | 52 | 0 | `installation/wizard.py`, `factory_dialog.py` |
| **Total CSV** | **1072** | **138** | |
| I. Fuera de alcance (D-02): `ui_pyside/views/*` y `ui/*` (tkinter, incluida `service_ui`) | 562 | — | solo conteo (§9), no van al CSV |

---

## 2. A — UI QML

### 2.1 Mecanismo actual

- Ya existe un catálogo: `src/autoclave/ui_qml/assets/textos/es.json` (348 líneas, 277 entradas de texto).
  - Lo carga `ui_qml/app.py:63` y `:89-91` (`cargar_textos`).
  - Se entrega a QML como propiedad inicial `textosJson` (`app.py:173`).
- No hay `en.json` ni un singleton de idioma. El JSON se pasa una sola vez al arrancar (`setInitialProperties`).
- **Formato de claves:** `seccion.clave` con dos niveles. Hay dos excepciones:
  - Listas: `fecha.meses`, que es un array, y `sensores[]`, una lista de objetos `{clave, etiqueta, unidad}`.
  - Un tercer nivel: `opciones.secciones.*`.
- Los placeholders ya tienen nombre (`{minimo}`, `{n}`, `{destino}`, `{tiempo}`…).
- **Cada archivo QML define su propia función `tx(seccion, clave)`.** Hay unas 17 copias, por ejemplo `MenuPrincipal.qml:50-53`, `Main.qml:44-51`, `Login.qml:33-45`.
  - **Si la clave no existe, devuelven `""`, sin aviso.**
- Python usa el mismo `es.json` para los PDF y el correo: `AccionesCiclos._tx`, en `bridge/acciones_ciclos.py:96-98`.
  - **Si falta la clave, devuelve la clave cruda.**
- Login, cambio de clave y nuevo usuario ya trabajan con **códigos → clave de `es.json`**: `sesion_backend.py:53-70`, `login_controller.py:69`, `validacion_usuario.py:92-105`.

### 2.2 Cobertura

- Las 143 claves que el QML cita literalmente existen todas en `es.json`; no falta ninguna.
- 134 claves no aparecen literalmente en QML. Se usan de tres formas:
  - con clave dinámica: `textoDeResultado`, `estados.*`, `fases.*`, `opciones.secciones.*`, `ResumenPeriodo.tx(modelData.clave)`;
  - desde Python: `exportacion.*`, `sesion.*`, `validacion.*`, `usuarios.*`;
  - o nunca se usan (no se verificó cuáles quedan muertas).
- 8 llamadas usan una clave calculada en ejecución (`txRuta(sesion.mensajeClave)`, etc.); se listan en el CSV.

### 2.3 Cadenas por archivo QML (producción)

Primera columna: llamadas `tx`/`txRuta` con clave literal. Segunda: literales fijos visibles.

| Archivo | `tx` con clave | Literales fijos |
|---|---:|---:|
| `Pantallas/MenuPrincipal.qml` | 61 | 1 (símbolo `‹`) |
| `Pantallas/PantallaCicloEnCurso.qml` | 37 | 0 |
| `Pantallas/PantallaPreciclo.qml` | 29 | 0 |
| `Pantallas/Opciones.qml` | 17 | 0 |
| `Componentes/GraficaCiclo.qml` | 16 | 0 |
| `Pantallas/NuevoUsuario.qml` | 14 | 8 |
| `Componentes/ResumenPeriodo.qml` | 12 | 0 |
| `Pantallas/CambioClave.qml` | 8 | 0 |
| `Componentes/TecladoAlfanumerico.qml` | 6 | 0 |
| `Componentes/DetalleCiclo.qml` | 5 | 0 |
| `Componentes/SelectorDestino.qml` | 4 | 0 |
| `Main.qml` | 2 | 0 |
| `Componentes/TecladoNumerico.qml` | 2 | 0 |
| `Pantallas/Login.qml` | 1 | 8 |
| `Componentes/BarraSuperior.qml` | 0 | 1 (meses `ene…dic` fijos) |
| Resto de `Componentes/` (`FilaAlarma`, `PanelNotificaciones`, `TarjetaMenu`, …) | 0 | 0 — reciben el texto por propiedades |
| `Tema/*.qml` | 0 | 0 — solo nombres de fuente (`Montserrat`, `Tahoma`, `Arial`) |

Pantallas de prueba (`qml/Pruebas/`): `GaleriaMenuPrincipal` tiene 28 literales; `PruebaCicloEnCurso` 3; `PruebaMenuPrincipal` 3; `PruebaTecladoAlfanumerico` 7 claves; `PruebaTecladoNumerico` 8 claves.

**Literales fijos en producción:**
- `Login.qml`: líneas 141, 166, 215, 279, 323, 364, 398, 414.
- `NuevoUsuario.qml`: líneas 312, 340, 363, 416, 658, 659, 679, 691. Varios marcados `// PLACEHOLDER`.

### 2.4 Texto que Python entrega a QML

- **Nombres de día y mes en español** (`ui_qml/domain/resumen_sistema.py:135-154`): rótulo del periodo del Historial, p. ej. "Lunes 6 oct 2026" u "Octubre 2026".
- **Etiquetas de rol** `Admin` / `Técnico` / `Ingeniero` (`ui_pyside/services/roles.py:17-21`), que llegan por `NuevoUsuarioBridge.roles` a `NuevoUsuario.qml:416,570`.
- **Valores crudos del perfil** en el panel de Información del equipo (`bridge/info_equipo.py:79-92`): `clase` (`piso`, `mesa_b`…, en español) y `tipo_puerta` (`advanced`, `simple`…, en inglés).
- **Códigos crudos de resultado** como "detalle": `resumen_sistema.py:73-77` (`resultado_detalle`, p. ej. `FALLO_CALENTAMIENTO`), que se muestra en `MenuPrincipal.qml:524,741`.
- **Descripciones de alarma y motivos de puerta:** ver §3.
- **Distribución del teclado** `FILAS_QWERTY_ES` con `ñ` (`domain/teclado_alfanumerico.py:16-19`).

---

## 3. B — Alarmas, fallas y eventos (responde I18N-01)

### 3.1 Modelo de alarma

- `Alarm(alarm_id, alarm_type, source_state, description, recoverable, blocks_operation)` (`state_machine/alarms/alarm.py:5-20`).
- `description` es **texto libre en español** y se arma donde se dispara la alarma.
- No existe catálogo de alarmas, ni en `es.json` ni en ningún otro lugar.

### 3.2 Códigos de alarma (completo según el código)

Abreviaturas de la columna Tipo: E = EMERGENCIA, F = FALLA, A = ALERTA.

| Código (`alarm_id`) | Tipo | Dónde se dispara | Texto (`description`) |
|---|---|---|---|
| `CONFIGURACION_INVALIDA` | F | `backend/context.py:115` | `f"Configuración inválida: {motivo}"` (:119) |
| `NO_HAY_CONEXION` | F | `services/domain/loop/control_loop.py:111` | "No hay comunicación con el hardware." (:115) |
| `ABRIENDO_MODO_SEGURO_{Puerta N}` | A | `devices/puertas/advanced_door.py:376` | `f"Puerta {name}: abriendo en modo seguro (sin bomba de vacío)."` (:380) |
| `CERRANDO_MODO_SEGURO_{Puerta N}` | A | `advanced_door.py:465` | `f"Puerta {name}: cerrando en modo seguro (sin bomba de vacío)."` (:469) |
| `PARO_EMERGENCIA` | E | `preparacion.py:65`, `preparado.py:48`, `ciclo.py:395`, `falla.py:23`, `hibernacion.py:18` | **5 textos distintos** según el estado (ver I18N-14) |
| `SUMINISTRO_VAPOR` | A | `preparacion.py:182`, `preparado.py:103`, `ciclo.py:163` | genérico en PREPARACION/PREPARADO; en CICLO: "Sin suministro de vapor: chaqueta pendiente hasta que regrese." (:167) |
| `TEMP_DRENAJE_ALTA` | A | `preparacion.py:280-281`, `preparado.py:187`, `ciclo.py:209` | genérico; en CICLO: "Temperatura de drenaje alta: enfriando." (:213) |
| `CHAQUETA_FRIA`, `CHAQUETA_SOBRECALENTADA` | A | `preparacion.py:200,206`, `preparado.py:121,126` | genérico |
| `PRESION_CAMARA_BAJA`, `PRESION_CAMARA_ALTA` | A | `preparacion.py:236,243`, `preparado.py:155,161` | genérico |
| `AGUA_RESIDUAL_CAMARA` | A | `preparacion.py:257` | genérico |
| `ERROR_AI_{SENSOR}` (10 en PREPARACION: `PRES_CAMARA`, `PRES_CHAQUETA`, `PRES_EMPAQUE_1`, `PRES_EMPAQUE_2`, `TEMP_CAMARA`, `TEMP_2_CAMARA`, `TEMP_REF`, `TEMP_CHAQUETA`, `TEMP_DRENAJE_CAM`, `TEMP_DRENAJE`) | A | `preparacion.py:124,134`, `preparado.py:251,258` | genérico. En PREPARADO el conjunto sale de las claves presentes en `estado.sensores_pres/temp`, no de una lista fija |
| `SUMINISTRO_AGUA_BOMBA`, `SUMINISTRO_AGUA_GENERADOR`, `SUMINISTRO_AIRE_COMPRIMIDO` | A | `preparacion.py:153`, `preparado.py:271` | genérico |
| `SUMINISTRO_ELECTRICO` | A | `preparado.py:278` | genérico |
| `PUERTA_1_ABIERTA`, `PUERTA_2_ABIERTA` | A | `preparado.py:212,217` | genérico |
| `TIMEOUT_APERTURA_AUTOMATICA` | A | `ciclo.py:286` | "Apertura automática: la cámara tarda más de lo esperado en enfriar." (:290) |
| `APERTURA_AUTOMATICA_DENEGADA` | A | `ciclo.py:328` | `f"Apertura automática: no se pudo abrir {puerta} — {motivo or 'sin motivo reportado'}."` (:332); `{motivo}` es a su vez texto libre de `ser_puertas` |
| `FALLO_SUMINISTRO_ELECTRICO` | E | `ciclo.py:411` | `motivo_fallo` = "Pérdida de suministro eléctrico durante el ciclo." (:410) |
| `FALLO_PUERTA_{1,2}_ABIERTA`, `FALLO_PUERTA_{1,2}_EMPAQUE` | F | `ciclo.py:144,148` → `:428` | `f"Fallo de seguridad: {codigo.replace('_',' ').lower()}."` (:427) |
| `SENSOR_AUSENTE` | E | `ciclo.py:451` | `f"Sensor crítico ausente: {', '.join(ausentes)}"` (:450), con claves técnicas de sensor (`temp_camara`…) |
| `FALLO_{fase}` (`PRECALENTAMIENTO`, `PRE_VACIO`, `CALENTAMIENTO`, `ESTERILIZACION`, `DESCOMPRESION`, `SECADO`) | F | `ciclo.py:505` | el `motivo_fallo` que dejó la fase o `f"Fallo en la fase {fase.name.replace('_',' ').lower()}."` (:504) |
| `FALLO_CONEXION` | E | `ciclo.py:537` | "Se perdió la comunicación con el hardware durante el ciclo." (:536) |

"Genérico" quiere decir:
- en PREPARACION: `f"{nivel}: {alarm_id} en PREPARACION."` (`preparacion.py:56`), con `nivel` ∈ {"Alerta", "Fallo", "Emergencia"} (`_NIVEL_TXT`, `:13-17`);
- en PREPARADO: `f"Error {alarm_id} en estado PREPARADO"` (`preparado.py:36`).

**Motivos de fallo de fase** (`self._fallo(...)` → `estado.motivo_fallo`). Llevan los valores medidos incrustados en el texto:
- `calentamiento.py:235`: "Timeout de calentamiento: …"
- `calentamiento.py:402-403`: "No se logró sostener condición estable en …"
- `esterilizacion.py:203-231`: temperatura alta/baja y presión alta/baja, con `{temp:.1f}°C`, `{pres:.1f} kPa`.
- `esterilizacion.py:287-288`: `ESTERILIZACION_TIMEOUT_F0: …`. Ese código **solo existe como prefijo del texto**; la alarma real es `FALLO_ESTERILIZACION`.
- Las fases `precalentamiento`, `prevacio`, `descompresion` y `secado` devuelven `FALLO` sin escribir motivo (`precalentamiento.py:64`, `prevacio.py:145,194`, `descompresion.py:61`, `secado.py:114,131`). En ese caso queda el genérico de `ciclo.py:504`.

### 3.3 Otros códigos y eventos

- **`estado.fase_ciclo` al cerrar un ciclo**, que se guarda como `ciclos.resultado`:
  - `COMPLETADO`, `CANCELADO`
  - `EMERGENCIA` (no `PARO_EMERGENCIA`)
  - `FALLO_SUMINISTRO` (no `FALLO_SUMINISTRO_ELECTRICO`)
  - `FALLO_PUERTA_*`, `SENSOR_AUSENTE`, `FALLO_<fase>`, `FALLO_CONEXION`
  - `DESCONOCIDO` (`cycle_logger.py:162`)
- **Eventos de `audit_log.evento`**, todos códigos:
  - `login_ok`, `login_fallido`, `login_bloqueado`, `logout`, `cambio_clave`, `usuario_creado`
  - `calibracion_cambio`, `param_ciclo_cambio`
  - `modo_prueba_entra`, `modo_prueba_sale`, `salida_prueba`
  - `rechazo_{status}`
  - (`backend/server.py:136-1372`)
- **Tickets de conectividad:** `TARJETA`/`BACKEND` × conectado/desconectado, con texto fijo (`devices/printer/connectivity_ticket.py:9-14`).
- **Rechazos del backend:** clase `RechazoApi` con cuerpo `{"detail": <texto español>, "codigo": <código>}` (`server.py:111-128`). Lleva código estable. En cambio, `HTTPException(detail="…")` (~25 sitios) solo lleva texto.

### 3.4 Recorrido del texto: dónde viaja y dónde se guarda

| Dato | Forma | Dónde queda |
|---|---|---|
| Alarma activa | **código + texto libre** | Solo en memoria (`estado.Alarmas_activas`); **no hay tabla de alarmas**. Viaja en `GET /status` como `{"id","level","description","source_state"}` (`server.py:606-614`) → `UiBridge.AlarmListModel` (`ui_bridge.py:56-66`) → QML: `PanelNotificaciones.qml:92-93` muestra `description`; `PantallaPreciclo.qml:497` muestra `description` o, si viene vacía, el `id` |
| Alarma en log | texto | `alarm_manager.py:24-32`, en `data/backend.log` o `logs/autoclave.log` |
| Resultado del ciclo | **código** | `ciclos.resultado` (`db_manager.py:42`, `:351-356`) |
| Motivo de fallo | **texto libre español, con parámetros incrustados** | `ciclos.motivo_fallo` (`db_manager.py:49`; se escribe en `cycle_logger.py:269-270`) |
| Ticket de ciclo | código + texto | `Estado: {resultado}` y `Motivo: {motivo_fallo}` (`ticket_formatter.py:76-79`); se imprime en vivo y se reimprime; va dentro del PDF (`acciones_ciclos.py:380`) |
| PDF / Historial | código crudo como detalle | `acciones_ciclos.py:393-394` y `resumen_sistema.py:73-77` |
| Reporte "Causas de fallo" | código crudo | `resumen_periodo.py:40-41,93-96` y PDF de resumen |
| Motivo de denegación de puerta | **solo texto libre, sin código** | `ser_puertas.py:64-192` → `server.py:1113-1118` (`HTTPException.detail`) → `door_command_service.py:22` → `comandos_puerta.py:63-76` → `PantallaPreciclo.qml:59` |
| Fases por tramo | código | `ciclo_fases.fase`, `lecturas_grafica.fase` |
| Bitácora | evento = código; `detalle` = JSON que puede llevar texto español | `audit_log.detalle` (`server.py:136`, `:264`, `:336`, `:359`, `:1284`) |

### 3.5 Respuesta a I18N-01

**Se confirma, en parte: hoy las alarmas y los fallos se emiten y se guardan como texto libre en español.**

- **Alarmas activas.** Cada una lleva un código estable (`id`) y un texto libre (`description`), y los dos viajan juntos a la UI (`server.py:606-614`).
  - El texto se arma en español en el punto de disparo y no sale de ningún catálogo (`ciclo.py:163-537`, `preparacion.py:52-58`, `preparado.py:31-38`, `advanced_door.py:376-469`, `control_loop.py:111-115`).
  - La UI muestra el texto, no el código (`PanelNotificaciones.qml:93`).
  - Como el código ya viaja, el texto **puede** resolverse en la UI sin tocar el transporte. Pero hay códigos dinámicos (`ERROR_AI_*`, `SUMINISTRO_*`, `FALLO_<fase>`, `*_MODO_SEGURO_Puerta N`), y algunos textos llevan parámetros que **no viajan aparte** (`APERTURA_AUTOMATICA_DENEGADA`, `CONFIGURACION_INVALIDA`).
- **Persistencia.** `ciclos.resultado` guarda un código. `ciclos.motivo_fallo` guarda **texto libre en español** con los valores medidos incrustados (p. ej. "Temperatura baja: 133.8°C < 133.9°C", `esterilizacion.py:213`).
  - Los parámetros no se guardan por separado. Ese campo no se puede mostrar en otro idioma (D-05) sin un cambio de diseño.
  - I18N-09 dice que no hay históricos que conservar.
- **Motivos de denegación de puerta.** Viajan **solo como texto**, sin código, y la UI QML los muestra tal cual (ver I18N-12).
- **La parte de sesión y login ya cumple R-03:** código del backend → clave de `es.json` (`sesion_backend.py:53-70`).

Conclusión para el plan: hace falta el cambio previsto en F2, y además cubrir los motivos de puerta y los rechazos del backend, que hoy no tienen código.

---

## 4. C — Persistencia

### 4.1 SQLite (`services/domain/logging/db_manager.py` y auditorías)

| Tabla.columna | Contenido | ¿Texto visible? |
|---|---|---|
| `ciclos.nombre_ciclo` | copia del `display_name` del perfil al iniciar el ciclo | **Sí, texto libre** (se congela en el idioma del momento) |
| `ciclos.tipo_ciclo` | `cycle_id` | código |
| `ciclos.resultado` | `fase_ciclo` final | código (se muestra crudo como detalle) |
| `ciclos.motivo_fallo` | `estado.motivo_fallo` | **Sí, texto libre español** |
| `ciclos.modelo`, `serie`, `version_sw` | datos del equipo | dato, no se traduce |
| `ciclos.operador` | no se llena hoy (`resumen_sistema.py:96`) | — |
| `lecturas.fase_codigo` | `PH`, `PV`, `H`, `S`, `E`, `F` (`cycle_logger.py:47-56`) | letra impresa en el ticket |
| `lecturas_grafica.fase`, `ciclo_fases.fase` | `fase_ciclo` | código |
| `usuarios.nombre` | nombre propio; semillas "Administrador" e "Ingeniero" (`db_manager.py:120,123`) | nombre propio, no catálogo |
| `usuarios.rol` | `admin` / `tecnico` / `ingeniero` | código; la etiqueta sale de `roles.py` |
| `audit_log.evento` / `entidad` / `detalle` | código / clave / JSON | `detalle` puede llevar texto español |
| `cycle_params_audit.fase`, `.param` | claves técnicas | código |
| `sensor_calibration_audit.tipo`, `.sensor` | claves técnicas | código |

### 4.2 Perfiles de ciclo (`src/autoclave/cycles/`)

- **Fábrica** (`cycles/factory/`): `bowe_dick.json` ("Bowe & Dick") e `instrumental_134.json` ("instrumental 134", en minúscula).
- **Usuario** (`cycles/user/`): `bowe_dick.json`, `instrumental_134.json` (mismos `cycle_id` que los de fábrica) e `instrumental_121.json` ("Instrumental 121°C", sin equivalente de fábrica).
- **Único texto visible:** `display_name`. Los parámetros no tienen etiqueta.
  - La UI PySide (fuera de alcance) los muestra a partir de la clave: `_format_param_name`, que cambia `_` por espacio y pone mayúscula inicial (`params_ciclo.py:508-509`).
  - En QML, "Parámetros del ciclo" aún no muestra parámetros.
- **Unidades** que aparecen en los perfiles: `°C`, `°C/min`, `kPa`, `kPa/min`, `min`, `%`, `seg` **y** `sec` (ver I18N-20).
- **Carga:** `cycle_manager.py:79-84` lee primero fábrica y después usuario, en un diccionario por `cycle_id`. **Un perfil de usuario con el mismo `cycle_id` reemplaza al de fábrica.**
- No se encontró código que **cree** perfiles nuevos en `cycles/user/`. Solo `server.py:1209-1227` reescribe los existentes al cambiar un parámetro. Ver pregunta P-04.

### 4.3 Otros JSON y YAML

- **`config/correo.json`:** nombres de destino "Administrativo" y "Mantenimiento" (líneas 7-8). `SelectorDestino.qml` los muestra tal cual.
- **`config/global_params.json`:** solo valores y unidades (`seg`, `°C`, `kPa`, `min`). Sin etiquetas.
- **`config/calibration.yaml`:** `name: "Calibracion Sensores PRO"`. No se encontró uso visible.
- **`config/models/*.yaml`, `config/instances/*.yaml`, `active_instances.yaml`:** solo claves técnicas (`temp_camara`, `vapor_chaqueta`…) y `model_name: SOLIDS`. Sin texto para el operador.
- **`installation_profile.json`** (raíz del repo): `equipment_class: "piso"` (enum en español, `installation/equipment.py:5-10`) y `door_type: "advanced"` (enum en inglés, `devices/puertas/door_type.py:4-9`). Los dos se muestran crudos en el panel de Información del equipo.
- **Nombres de puerta `"Puerta 1"` / `"Puerta 2"`:**
  - se generan en `devices/factory/factory.py:15` y `core/runtime/status.py:72-75`;
  - son el **identificador** en la API (`/doors/{door_name}/open`) y en `estado_puertas`;
  - **y a la vez** aparecen en textos visibles: `f"{name} no está cerrada"` (`ser_puertas.py:164`) y la alarma `APERTURA_AUTOMATICA_DENEGADA`.

---

## 5. D — Reportes PDF, ticket y correo

| Salida | Módulo generador | Origen del texto |
|---|---|---|
| PDF de ciclo | `ui_qml/exportacion/pdf_ciclo.py` (+ `textos.py`) desde `bridge/acciones_ciclos.py:360-410` | `es.json` (`exportacion.*`, `ciclo.serie_*`, `fases.*`); el bloque "Registro del ciclo" es el **ticket en texto fijo** (`format_ticket`) |
| PDF de resumen | `ui_qml/exportacion/pdf_resumen.py` | `es.json` (`reportes.*`, `exportacion.*`); causas de fallo = códigos crudos |
| PDF consolidado | `ui_qml/exportacion/pdf_consolidado.py` | `es.json` (`menu.col_*`, `reportes.indice`, `reportes.col_pagina`) |
| Correo (asunto y cuerpo) | `acciones_ciclos.py` + `exportacion/correo.py` | `es.json` (`exportacion.asunto*`, `cuerpo*`, `enviado*`) |
| Ticket de ciclo (térmica) | `services/domain/logging/ticket_formatter.py` | **fijo en código**: "Fecha:", "Hora:", "Num serie:", "SoftW.:", "Ciclo No.:", "Temp. Ester.: … C", "Estado:", "Motivo:", "F0 total:", "Hora fin:", "Operador:"; meses `ENE…DIC` (`:15-18`) |
| Ticket de resumen (térmica) | `services/domain/reportes/resumen_periodo.py:64-97` | **fijo en código** ("RESUMEN DE CICLOS", "Desde:", "POR PROGRAMA", "CAUSAS DE FALLO"…) |
| Ticket de arranque | `devices/printer/startup_ticket.py` | **fijo en código**. **Solo lo invoca la UI tkinter** (`ui/window/main_window.py:165-212`); las etiquetas "Backend"/"Tarjeta" y los valores "OK"/"FALLO"/"Sin datos" vienen de ese archivo |
| Ticket de conectividad | `devices/printer/connectivity_ticket.py:9-14` | **fijo en código** |

Las cadenas de cada módulo están en el CSV (superficie D). La impresora térmica codifica en `cp437` (`win32_printer.py:61`).

---

## 6. E — Logs técnicos

- **Configuración:**
  - `backend/main.py:13-24`: solo en el build congelado, archivo `data/backend.log`.
  - `main.py:38-48`: UI tkinter, `data/ui{sufijo}.log`.
  - `utils/logging.py`: `logs/autoclave.log` + consola; lo importan `serial_link.py`, `serial_link_config.py`, `device_reset.py` y `backend_guard.py`.
  - `logging.basicConfig(level=INFO)` en `ui_qml/app.py:112`, `doble_pantalla.py:43`, `lanzar.py:91`, `ui/main.py:16` y `simulador/__main__.py:39`.
- **Formato común:** `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`. No hay rotación de archivos.
- **Mensajes:** 300 cadenas `logger.*` dentro del alcance, todas en español. Hay emojis en algunos (`cycle_manager.py:104`, `ui_service_backend.py:63`). El detalle está en el CSV.
  - `alarm_manager.py` registra `id - description` de cada alarma.
- **Bitácora visible** (`audit_log`): ver §3.4 y §4.1.

---

## 7. F — Voz

**Estado real:** el subsistema está implementado **solo en la rama `worktree-anuncios-voz`** (worktree `.claude/worktrees/anuncios-voz`).
- Son 17 commits, el último `786c735` del 2026-08-13. **No está unido a `dev`** (`git merge-base --is-ancestor` lo confirma).
- En `dev` no hay código de voz.

| Aspecto | Encontrado |
|---|---|
| Anuncios | **32**, no 33. `manifest.json` y `tools/generar_audio.py:17-50` tienen 32. Si se suman las tablas §4.1-4.7 de `planeacion_anuncios_voz.md` dan 5+4+4+10+4+3+2 = 32, aunque la línea 244 de ese plan dice "Total: 33" |
| Textos | En el CSV (superficie F). En el manifiesto **van sin tildes** ("Camara en condiciones seguras."), a diferencia del plan ("Cámara…") |
| Modelo Piper | **Ninguno.** `generar_audio.py:1-4` genera un **tono de 440 Hz de 0.4 s** para todos los eventos ("placeholder, NO locución real"). No hay modelo ni versión registrados |
| WAV | `src/autoclave/assets/audio/es/<event_id>.wav`, 32 archivos, PCM 16 bit, 22 050 Hz, mono |
| Manifiesto | `assets/audio/manifest.json`: `version`, `idioma_default: "es"`, y por evento `prioridad`, `cooldown_s`, `texto`, `archivos{idioma}`, `sha256{idioma}`. La estructura ya admite varios idiomas |
| Carga | `devices/audio/manifest.py:23` `load_manifest(path, idioma="es")`; `backend/context.py:125-128` lo llama sin idioma, o sea, siempre `es` |
| Reproducción | `sounddevice` (`sd.play` + `sd.wait`) en el hilo demonio `Announcer` (`devices/audio/announcer.py`); volumen con ganancia cuadrática |
| Cola | `heapq` por (prioridad, contador). Seis niveles P0-P5, menor = más urgente. Cooldown de 60 s en P0-P2 y 5 s en P3-P5. No duplica un evento ya en cola. Si llega uno más prioritario que el que suena, lo interrumpe (`sd.stop()`). Cola máxima de 10: si está llena, descarta el de menor prioridad o el entrante (`announcer.py:44-82`). Tras 3 fallos de reproducción seguidos llama a `on_fallo_persistente` |
| Configuración | Vista PySide `ui_pyside/views/audio_config.py` y endpoints `/audio/config`, `/audio/test`, `/audio/ui-ready`. El aviso `ui-ready` (anuncio `sys_bienvenida`) lo envía la ventana PySide/tkinter (commit `5df5875`), no la UI QML |

---

## 8. G — Fechas y números

No hay `QLocale`, `locale` ni `Qt.formatDate*` en el código; todo se formatea a mano. El detalle con archivo y línea está en el CSV (superficie G).

| Formato | Dónde |
|---|---|
| `dd/MM/yyyy` y `HH:mm` | `ui_qml/domain/resumen_sistema.py:48,54` (Menú, Historial, PDF); `resumen_periodo.py:52,74` (ticket de resumen) |
| `dd/MES/yyyy` con mes en español (`ENE…DIC`) + `HH:MM:SS` | `ticket_formatter.py:15-27,68` (ticket de ciclo) |
| `yyyy-MM-dd HH:mm:ss` (ISO) | `startup_ticket.py:17,33`; `connectivity_ticket.py:23` |
| `yyyy-MM-dd HH:mm` / `yyyy-MM-dd` | `info_equipo.py:50,87` (panel Información del equipo); `server.py:483`; auditorías (`cycle_params_audit.py:37`, `sensor_calibration_audit.py:47`) |
| `d mes  -  yyyy` con mes abreviado en español | relojes QML: `EncabezadoMenu.qml:83`, `Arranque.qml:58`, `PantallaCicloEnCurso.qml:261`, `PantallaPreciclo.qml:234` (meses de `es.json`); `BarraSuperior.qml:22,58` (meses fijos en el .qml) |
| Nombre de día o mes completo en español | rótulos de periodo del Historial, `resumen_sistema.py:135-154` |
| `HH:mm` | `reloj_splash.py:11` |
| Decimales | `formato_numerico.py:19` (`f"{valor:.{decimales}f}"`, punto fijo, único formateador de la UI); `GraficaCiclo.qml:514` (`toFixed(1)`); ticket `{:06.1f}` (`ticket_formatter.py:59-60`); motivos de fallo `{:.1f}` y `{:.0f}` incrustados en texto |

---

## 9. H — Mecanismos de traducción existentes

- **No hay** `qsTr`, `QTranslator`, `tr()`, `gettext` ni `babel` en `src/autoclave/`.
- El único mecanismo es el catálogo propio `es.json` con funciones `tx` locales en QML y `_tx` en `AccionesCiclos`. Ver §2.1 y el hallazgo I18N-13.
- `Login.qml:23` ya deja anotado que sus etiquetas quedan "para el plan de idiomas".

---

## 10. I — Vistas fuera de alcance (D-02): solo conteo

Cadenas detectadas por archivo (texto visible + logs).

| Archivo | Cadenas |
|---|---:|
| `ui_pyside/views/params_ciclo/params_ciclo.py` | 57 |
| `ui_pyside/views/entrdas_salidas/io_do.py` | 52 |
| `ui_pyside/views/ciclos.py` | 40 |
| `ui_pyside/views/entrdas_salidas/calibracion_sensor.py` | 28 |
| `ui_pyside/views/login.py` | 27 |
| `ui_pyside/views/impresion_menu.py` | 25 |
| `ui_pyside/views/admin_menu.py` | 22 |
| `ui_pyside/views/_email_dialog.py` | 19 |
| `ui_pyside/views/entrdas_salidas/io_menu.py` | 16 |
| `ui_pyside/main_window.py` | 15 |
| `ui_pyside/views/secado.py` | 13 |
| `ui_pyside/views/entrdas_salidas/io_di.py` | 11 |
| `ui_pyside/views/entrdas_salidas/_io_base.py` | 10 |
| `ui_pyside/views/entrdas_salidas/io_pres.py` / `io_temp.py` | 9 / 9 |
| `ui_pyside/views/home.py` | 7 |
| `ui_pyside/views/nuevo_usuario/vista.py` / `puente.py` | 4 / 3 |
| **Subtotal `ui_pyside/`** | **367** |
| `ui/window/main_window.py` (tkinter) | 81 |
| `ui/cycle/cycle_window.py` | 48 |
| `ui/main.py` | 25 |
| `ui/components/components.py` | 16 |
| `ui/service_ui/ui_service_backend.py` | 13 |
| `ui/cycle/widgets/live_graph.py` / `phase_indicator.py` / `data/cycle_buffer.py` | 6 / 4 / 2 |
| **Subtotal `ui/`** | **195** |
| **Total fuera de alcance** | **562** |

Notas sobre ese límite:
- `ui/service_ui/` y dos módulos de `ui_pyside/` **sí los usa la UI QML** (ver I18N-23).
- `ui/` (tkinter) no es solo `service_ui`: incluye la ventana principal antigua. Ver P-01.

---

## 11. Preguntas abiertas (no se pueden resolver leyendo el código)

| # | Pregunta |
|---|---|
| P-01 | ¿Qué interfaz se entrega en V1.0? `AutoclaveUI.spec` empaqueta `src/autoclave/main.py` (UI **tkinter**) y no incluye `ui_qml/assets` (ni `es.json`); la UI QML se lanza con `ui_qml/app.py`, `doble_pantalla.py` o `lanzar.py`, y ninguno tiene spec. D-02 solo excluye las vistas PySide; la UI tkinter (`ui/window`, `ui/cycle`, `ui/components`) no está clasificada |
| P-02 | ¿Qué proceso imprime el ticket de arranque cuando el equipo arranca con la UI QML? Hoy solo lo hace `ui/window/main_window.py:165-212`. Lo mismo para el aviso `ui-ready` de la voz |
| P-03 | ¿Dónde vivirá el catálogo? Hoy está en `src/autoclave/ui_qml/assets/textos/es.json` y el backend no lo carga. F2/F4 (alarmas, ticket, logs) lo necesitan del lado del backend. `planeacion_i18n.md` §3.2 deja la ruta "a confirmar" |
| P-04 | ¿Cómo nacen los ciclos creados por el ingeniero (I18N-05)? No hay código que cree perfiles nuevos en `cycles/user/`. ¿`instrumental_121.json` es un ciclo de usuario o de fábrica que falta en `factory/`? |
| P-05 | ¿El "33" de los planes de voz y de i18n es un error de suma, o falta un anuncio en la implementación? |
| P-06 | ¿Qué modelo Piper (voz es_MX o es_ES) y qué versión se usará? No hay ninguno en el código (`planeacion_anuncios_voz.md` D-02 solo dice "Piper") |
| P-07 | ¿Los valores de `equipment_class` y `door_type` que muestra el panel de Información del equipo deben traducirse, o se reemplazan por etiquetas de catálogo? Hoy mezclan español (`piso`) e inglés (`advanced`) |
| P-08 | ¿El teclado alfanumérico (QWERTY-ES con `ñ`) y la tecla "espacio" cambian con el idioma? |
| P-09 | ¿Las 134 claves de `es.json` sin uso literal en QML siguen todas vivas? No se verificaron una por una las de uso dinámico |
| P-10 | ¿El nombre de puerta ("Puerta 1") seguirá siendo a la vez identificador de API y texto visible? |
| P-11 | ¿Los textos de la UI tkinter y de las vistas PySide que sí se imprimen (ticket de alarmas en `impresion_menu.py:65`, que imprime `description`) entran en el alcance de "ticket"? |

---

## 12. Hallazgos

Se sigue el formato de `planeacion_i18n.md` §4; la numeración continúa a partir de I18N-11. Lo verificado es solo lectura de código, sin ejecutar.

| Código | Severidad | Estado | Hallazgo | Recomendación |
|---|---|---|---|---|
| I18N-12 | Alta | Abierto | Los **motivos de denegación de apertura/cierre de puerta** viajan solo como texto libre en español, **sin código**: "Sobrepresión en cámara ({pres} kPa)", "Temperatura demasiado alta…", "Cámara presurizada…" (`ser_puertas.py:64-192` → `server.py:1113-1118,1133-1138` → `door_command_service.py:22` → `comandos_puerta.py:63-76` → `PantallaPreciclo.qml:59`). Es el interlock de puerta, una función de seguridad | Tratarlos igual que I18N-01 en F2 (código + parámetros) e incluirlos en la prueba de alarmas de F5 |
| I18N-13 | Media | Abierto | El mecanismo actual contradice R-05: las ~17 copias de `tx()` en QML devuelven `""` si falta la clave (p. ej. `MenuPrincipal.qml:50-53`) y `AccionesCiclos._tx` devuelve la clave cruda (`acciones_ciclos.py:96-98`); ninguna registra advertencia. `PantallaPreciclo.qml:497` muestra el `id` crudo si la descripción llega vacía | Registrar en F1 que las copias actuales se reemplazan; la prueba de paridad debe cubrir las claves dinámicas (§2.2) |
| I18N-14 | Media | Abierto | Una misma alarma tiene textos distintos según el estado, y en PREPARACION/PREPARADO el texto **incrusta el código**: "Alerta: CHAQUETA_FRIA en PREPARACION." / "Error CHAQUETA_FRIA en estado PREPARADO" (`preparacion.py:56`, `preparado.py:36`). `PARO_EMERGENCIA` tiene 5 textos (`preparacion`, `preparado`, `ciclo.py:394`, `falla.py:27`, `hibernacion.py:22`) | Definir un texto por código (no por estado) antes de redactar `en.json`; cambio de seguridad |
| I18N-15 | Media | Abierto | Los códigos de cierre (`fase_ciclo` / `ciclos.resultado`) no coinciden con los de alarma para el mismo evento: `EMERGENCIA` frente a `PARO_EMERGENCIA`, `FALLO_SUMINISTRO` frente a `FALLO_SUMINISTRO_ELECTRICO` (`ciclo.py:392-411`). `ESTERILIZACION_TIMEOUT_F0` solo existe dentro del texto (`esterilizacion.py:288`) | Decidir si el catálogo usa una sola familia de códigos o las dos |
| I18N-16 | Media | Abierto | Textos visibles derivados del código por transformación de cadena: `"Fallo de seguridad: fallo puerta 1 abierta."` (`ciclo.py:427`), `"Fallo en la fase pre vacio."` (`ciclo.py:504`), `"Sensor crítico ausente: temp_camara"` (`ciclo.py:450`). Además, la UI, el PDF y los tickets muestran códigos crudos como texto (`resultado_detalle`, "Causas de fallo", `Estado:` del ticket) | Incluir en F2/F4 la presentación de códigos de resultado; §3.2 del plan pide código **junto** al texto, no en lugar de él |
| I18N-17 | Media | Abierto | Los formatos de fecha no cumplen D-09 y varios dependen del idioma: ISO en los tickets de arranque y conectividad y en el panel de Información del equipo; mes abreviado en español en el ticket de ciclo y en los relojes QML (`BarraSuperior.qml:22` lo fija en el .qml, sin usar `es.json`); nombres de día y mes en el Historial (`resumen_sistema.py:135-154`) | Definir en el plan si los meses con nombre se mantienen (y van al catálogo) o pasan a `dd/MM/yyyy`; ver tabla §8 |
| I18N-18 | Media | Abierto | Ticket de arranque: la decisión "Sistema listo" / "** FALLO EN ARRANQUE **" **compara contra el texto mostrado** (`"FALLO"`, `"ERROR"`, `"Sin datos"`, `startup_ticket.py:21`), y esos valores los escribe `ui/window/main_window.py:178-196`. Si se traduce ese texto se rompe la lógica. Además, el ticket solo se imprime desde la UI tkinter (P-02) | Separar el estado (código) del rótulo antes de traducir; resolver P-02 |
| I18N-19 | Media | Abierto | Voz: la implementación está en una rama sin unir; los WAV son tonos provisionales; hay 32 anuncios y no 33; los textos del manifiesto van sin tildes; `load_manifest` siempre carga `es`; no hay modelo Piper registrado (§7). Afecta la premisa de §3.7 y de I18N-11 | Corregir el conteo en los dos planes; decidir si F6 parte de esa rama |
| I18N-20 | Baja | Abierto | Unidades inconsistentes: `sec` y `seg` en los perfiles de ciclo; `C` en lugar de `°C` en el ticket (`ticket_formatter.py:46,48,75`). §3.2 dice que las unidades no se traducen, pero `seg`/`sec`/`min` son palabras | Fijar en el plan la lista cerrada de unidades no traducibles |
| I18N-21 | Baja | Abierto | El panel de Información del equipo muestra valores crudos de enums en dos idiomas a la vez: `piso` (`installation/equipment.py:9`) y `advanced` (`door_type.py:9`), vía `info_equipo.py:82,84` | P-07 |
| I18N-22 | Baja | Abierto | Los nombres de ciclo de fábrica son texto libre (`display_name`) y se **copian** a `ciclos.nombre_ciclo` al iniciar, así que el histórico queda en el idioma de ese momento. Además, un perfil de usuario con el mismo `cycle_id` reemplaza al de fábrica (`cycle_manager.py:82-83`). Mayúsculas inconsistentes ("instrumental 134" / "Instrumental 121°C") | Considerarlo en §3.5 del plan (clave para fábrica) junto con I18N-05 |
| I18N-23 | Media | Abierto | El límite de D-02 no es limpio: la UI QML importa y muestra texto de paquetes "fuera de alcance": `ui/service_ui/` (`app.py:27-28`; `select_cycle` devuelve "No se pudo contactar al backend: …", `ui_service_backend.py:324-326`), `ui_pyside/views/nuevo_usuario/puente.py` (`app.py:30`) y `ui_pyside/services/roles.py` (etiquetas de rol visibles) | Precisar D-02 por archivo, no por paquete |
| I18N-24 | Baja | Abierto | `audit_log.detalle` guarda texto español libre ("paro de emergencia", "sesión cerrada", motivo de rechazo completo) (`server.py:136,264,336,359,1284`), en contra de R-03 y D-10 para la bitácora | Incluir en F2 |
| I18N-25 | Baja | Abierto | Literales fijos en pantallas de producción: `Login.qml` (8) y `NuevoUsuario.qml` (8, varios `PLACEHOLDER`); "V: 1.0" duplicado (`Login.qml:414` frente a `es.json` `app.version`) | Ya previsto en `planeacion_opciones.md` §11 |
| I18N-26 | Media | Abierto — **ajeno a i18n**, detectado durante el inventario | Impresión periódica del ticket: `_INTERVALO_PARAM` / `_INTERVALO_DEFAULT` usan las claves `W/H/S/E` (`cycle_logger.py:70-82`), pero `_FASE_A_CODIGO` produce `PH/PV/H/S/E/F` (`:47-56`), y SECADO/DESCOMPRESION dan `" "`. Para precalentamiento, prevacío, secado y descompresión no hay intervalo, así que solo se imprime fila al cambiar de fase o subestado (`:357-359`). El comentario del esquema dice `W / H / S / E` (`db_manager.py:57`). El intervalo se mide con `time.time()` (`cycle_logger.py:362`), contra la regla de `time.monotonic()` de CLAUDE.md. `format_row` alinea a 1 carácter códigos de 2 (`ticket_formatter.py:55`) | Verificar en ejecución y tratarlo aparte del plan de idiomas (registro de ciclo = evidencia de esterilización) |
