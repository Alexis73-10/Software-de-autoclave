# Informe — Estado del backend para la UI de Opciones

**Fecha:** 2026-10-07
**Rama:** `dev` (HEAD `dd8f107`). Árbol de trabajo con cambios sin commit en `server.py` y `serial_link.py` (enlace serial A1/A2, pausado a propósito); el `server.py` leído incluye esos hunks, que solo tocan `/status` (`card_connected`, `comunicacion`) y no afectan a Opciones.
**Modo:** solo lectura. No se modificó código. El único archivo escrito es este informe.

---

## 0. Fuentes y versiones

| Documento pedido | Versión encontrada | Nota |
|---|---|---|
| `planeacion_opciones.md` "v2" | **v4** (borrador), `planeacion_opciones.md:5` | No hay v2 en el repo. Este informe usa la v4. |
| `planeacion_backend_autenticacion.md` v6 | v6, cerrada (`:4`) | Coincide. |
| `planeacion_backend_parametros.md` | borrador **v1** (`:4`) | Coincide. |

Otros documentos relevantes que también existen y se solapan (no pedidos, pero afectan al diagnóstico):
- `planeacion_opciones_parametros_ciclo.md` rev. 3.1: es el plan con el que se construyó la Fase 1 de Opciones QML (`permisos_opciones.py:3`).
- `planeacion_endurecimiento_backend_parametros.md` rev. 3 y `planeacion_sensores_ciclo.md` rev. 2, ambos BORRADOR.
- Rama sin unir `feature/roles-sensor-temperatura` (último commit `87fca2f`, 2026-09-08; base `3a2e51c` del 2026-09-02): roles de sensor y entradas exhibidas en PySide, con endpoints propios (ver D).

---

## 1. Tabla de estado

Estados: **Listo / Parcial / Falta / No determinado**.

### A. Autenticación e identidad

| # | Funcionalidad | Backend | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|---|---|
| A1 | Token en memoria, validado en escrituras | `AlmacenTokens` (`backend/autenticacion.py`), `requiere_rol` (`server.py:134-150`), `POST /auth/login` (`server.py:227`) | **Parcial** | El backend emite y valida el token (`server.py:253-262`, `:141-149`). Pero el login QML **no** usa el backend: valida PBKDF2 leyendo SQLite y no obtiene token (`ui_qml/controllers/login_controller.py:5-7,76-86`). Ningún archivo de `ui_qml` envía `Authorization` (grep sin resultados). | **Sí** — sin token, ninguna escritura de Opciones puede hacerse desde QML. |
| A2 | Bind a 127.0.0.1 (H-03) | `backend/main.py:9,33` | **Listo** | `HOST = "127.0.0.1"`; prueba `test_backend_autenticacion.py:518-521`. | No |
| A3 | Roles admin/técnico/ingeniero, sin `biomedico` | `ui_pyside/services/roles.py:13-23` | **Listo** | En código de producción solo queda un comentario (`roles.py:10`). En pruebas aparece únicamente como caso de rechazo (`test_nuevo_usuario_puente.py:65,171`, `test_permisos_opciones.py:21`, `test_backend_autenticacion.py:466`). Rastro menor: la columna `usuarios.rol` tiene `DEFAULT 'operador'` (`db_manager.py:105`). | No |
| A4 | Semillas `admin` e `ingeniero` con cambio obligatorio | `_USUARIOS_SEMILLA` y `seed_admin_if_empty` (`db_manager.py:119-126,618-633`) | **Parcial** | En el backend: listo (bandera `debe_cambiar_clave=1`, y `requiere_rol` devuelve 403 mientras esté activa, `server.py:145-146`). Pero el login QML ignora la bandera (`login_controller.py:76-86`): `admin/admin1234` entra a Opciones QML sin cambiar la contraseña. Las semillas solo se crean con la tabla vacía (`db_manager.py:623-625`). | Sí (parte de A1) |
| A5 | `POST /usuarios` con matriz de creación | `server.py:321-348`, `ROLES_CREABLES` (`roles.py:28-31`) | **Listo** en backend | Ingeniero → {admin, técnico, ingeniero}; admin → {admin, técnico}; técnico sin entrada → 403. El puente de Nuevo usuario ya llama al endpoint (`ui_pyside/views/nuevo_usuario/puente.py:114-122`), pero toma el token de `SessionManager`, que el login QML nunca llena → no funciona desde QML hoy. | Sí para la pantalla Usuarios (por A1) |
| A6 | Guard "distinto de CICLO" y excepción del ingeniero | `guard_estado` (`server.py:153-175`), `DISTINTO_DE_CICLO` (`:76`) | **Parcial** | Aplicado en `PATCH /calibration` (`:418-419`) y `PATCH /cycle/parameter` (`:1087-1088`) con `excepcion_ingeniero=True`. La regla de 5.8 está **provisional**: editar el programa en curso devuelve 409 (`:1091-1094`, pendiente T-17); `aplica` siempre vale `"siguiente"` (`:1106`). No hay copia profunda de parámetros (T-17). | No para construir pantallas; sí para el comportamiento final en CICLO. |
| A7 | `audit_log` (migración v1) y eventos | `_migracion_v1` (`db_manager.py:134-151`), `_migrar_versiones` (`:224-240`), `registrar_auditoria` (`:250`) | **Parcial** | Tabla y `PRAGMA user_version` listos. Eventos registrados hoy: `login_ok`, `login_fallido`, `login_bloqueado`, `logout`, `cambio_clave`, `rechazo_401/403/409`, `usuario_creado`, `calibracion_cambio`, `param_ciclo_cambio`, `modo_prueba_entra`, `modo_prueba_sale`, `salida_prueba` (llamadas a `_auditar` en `server.py`). Falta `falla_reconocida` (T-16) y todos los de la spec de parámetros (`param_sistema_cambio`, `calibracion_atm_*`, `suspension_*`). La auditoría es "best effort": un fallo se registra en el log pero no deshace la acción (`server.py:88-104`). No hay endpoint de lectura (`GET /audit_log` no existe). | Sí para Bitácora |

### B. Parámetros del sistema

| # | Funcionalidad | Backend | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|---|---|
| B1 | Tabla en BD con JSON como fábrica | — | **Falta** | No existe `system_params` (solo `ciclos`, `lecturas`, `lecturas_grafica`, `ciclo_fases`, `usuarios`, `audit_log`: `db_manager.py:35-138`). La migración v2 está reservada sin implementar (`db_manager.py:131-132`). `ConfigManager` sigue leyendo el JSON una vez, sin lock ni `set` (`core/managers/config_manager.py:6-25`). | **Sí** |
| B2 | Endpoints lectura/escritura | `GET /global_params` (`server.py:550-552`) | **Parcial** | Solo lectura: sin token, devuelve el JSON tal cual (`{clave: {value, type, unit, min?, max?}}`). No existen `PATCH /global_params/{clave}` ni `POST /global_params/{clave}/reset`. | **Sí** (edición) |
| B3 | Metadatos: actual, defecto, mín, máx, usuario, fecha | — | **Falta** | El JSON solo trae `value/type/unit` y a veces `min/max` (`config/global_params.json:2-15`); 7 de 14 claves sin rango. Sin defecto, sin usuario ni fecha. | **Sí** |
| B4 | "Usar valor por defecto" | — | **Falta** | Sin endpoint de reset. | Sí |
| B5 | Aplicar sin reiniciar, solo en reposo | — | **Falta** | Sin escritura. Además, `ServicioPuertas` copia `temp_max_apertura`, `presion_admosferica` y `rango_presion_atm` en `__init__` (`services/domain/puertas/ser_puertas.py:41-44`, OPC-11 sin resolver). | Sí |
| B6 | Eliminar `temp_max` y `tipo_puerta` | — | **Falta** | Siguen en `global_params.json:2,9`. | No |
| B7 | Rangos aprobados | — | **Falta** | Divergencias del JSON con la v4: `tiempo_standby` defecto 5, rango 1–60 (v4: 10, 0–60) `:15`; `temp_max_apertura` 120 (v4: defecto 80) `:5`; `presion_empaque`/`vacio_empaque` sin rango (`:6-7`); `timeout_chaqueta`, `ciclos_servicio`, `dias_servicio` no existen (grep sin resultados); `timeout_puerta` e intervalos de impresión con mín 0 (v4: 0 no permitido) `:8,12-13`. Erratas `presion_admosferica` e `intervalo_imprecion_esterilizacion` sin corregir. Además el puente de suspensión convierte 0 en 5 (`ui_qml/bridge/standby.py:34,44-45`), así que "0 = desactivada" no es posible. | Sí (defectos y rangos que mostrará la ventana de ajuste) |
| B8 | Eliminar `PATCH /cycle/parameters` | — | **Listo** en backend | No hay ruta en `server.py`; prueba `test_backend_autenticacion.py:325-327`. Residuo: PySide `ui_pyside/views/secado.py:135` y `tests/test_patch_cycle_parameters.py` (prueba del cliente con mock) aún lo usan. | No |

### C. Parámetros del ciclo

| # | Funcionalidad | Backend | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|---|---|
| C1 | Listar programas, fases y parámetros con metadatos | `GET /cycles` (`server.py:570-575`), `GET /cycle` (`:555-567`) | **Parcial** | `/cycles` devuelve solo `id`, `name`, `source`. Los parámetros solo se obtienen del **programa seleccionado** (`GET /cycle`); no hay ruta para leer los de otro programa ni una lista de fases. Cada hoja trae `value/type/unit/min/max` (p. ej. `cycles/user/*.json`, `esterilizacion.escape_lento_on_ester`), pero no defecto ni usuario/fecha del último cambio (ese dato está en `audit_log` como `param_ciclo_cambio`, sin endpoint de lectura). | **Sí** |
| C2 | Escritura con auditoría en backend | `PATCH /cycle/parameter` (`server.py:1072-1121`) | **Listo (provisional en CICLO)** | Solo ingeniero; usuario del token; `audit_log` con valor anterior/nuevo y `detalle` (`:1119-1120`). Sin `git_autocommit`. Coerción laxa: `bool("false")` es `True` y acepta NaN (`core/managers/cycle_manager.py:55-60`). Escritura del JSON no atómica (`server.py:1124-1134`). | No (sí se puede construir la ventana de ajuste) |
| C3 | Cambio de fases solo ingeniero | `requiere_rol(ROL_INGENIERO)` (`server.py:1074`) | **Listo** en backend | Admin y técnico reciben 403. Divergencia en la UI: ver OPC-05. | No |
| C4 | Gestión de programas para técnico (habilitar, duplicar, borrar) | — | **Falta** | `CycleManager` no tiene métodos para ello (`cycle_manager.py:75-141`: cargar, descartar repetidos, seleccionar). Sin endpoints. Los perfiles no tienen campo "habilitado". | **Sí** |

### D. Sensores

| # | Funcionalidad | Backend | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|---|---|
| D1 | Listar sensores realmente conectados | — | **Falta** | `/status` devuelve un juego fijo (6 temperaturas, 4 presiones, `server.py:486-502`, mapas fijos en `core/runtime/status.py:12-26`). Nada en Python lee `io_enabled` (solo existe en `config/instances/ACV-2026-001.yaml:17`). | **Sí** |
| D2 | Roles Principal/Referencia/No en uso por programa | — en `dev` | **Falta en `dev`** / Parcial en rama sin unir | Los perfiles traen `cycle_temperature_sensors` (`{"1":"temp_camara","2":"temp_ref"}`) pero ningún código de `dev` lo lee (grep sin resultados). La rama `feature/roles-sensor-temperatura` tiene `PATCH /cycle/sensor-roles` y `PATCH /cycle/display-slots`, **sin token ni guard de estado y con `git_autocommit`** (anteriores a la etapa 1). | **Sí** |
| D3 | Validación 1 Principal, 0–2 Referencias | — | **Falta** | En la rama sin unir, el commit `02dbf86` exige **un único** sensor Referencia, lo que contradice "0 a 2". | Sí |
| D4 | Permisos técnico e ingeniero, admin no | — | **Falta** | No hay endpoint en `dev`. | Sí |
| D5 | Entradas mostradas 1–3 por programa | — | **Falta** | No existen `ciclo_entradas_mostradas` ni `ciclo_entradas_seleccion`; las 3 series de la gráfica están fijas (`lecturas_grafica`, `db_manager.py:74`). | Sí |
| D6 | Calibración de sensores (método actual) | `GET/PATCH /calibration/{tipo}/{sensor}` (`server.py:360-450`) | **Listo (método actual)** | Ver sección 4.1. | No para la pantalla de calibración "V1 método actual". |

### E. Calibración de presión atmosférica

| Funcionalidad | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|
| Endpoints `start`/`cancel`, ventana de 120 s con 24 muestras, precondiciones, aborto, cancelación, flag `calibracion_en_curso` en `/status` | **Falta** | Ninguna ruta `/maintenance/*` en `server.py` (lista de rutas: `server.py:227-1248`); `/status` no expone `calibracion_en_curso` (`:526-540`). | **Sí** |
| Rango de aceptación del promedio | **Definido en el plan, no implementado** | La v4 ya lo propone: 60–106 kPa absolutos y máx − mín ≤ 1.0 kPa (`planeacion_opciones.md:155-160`), como "propuesta". Hay que confirmar que deja de ser propuesta (pregunta 3). | — |

### F. Otras secciones

| Sección | Backend | Estado | Evidencia | ¿Bloquea UI? |
|---|---|---|---|---|
| Suspensión | — | **Falta** | La suspensión vive en el puente QML (`ui_qml/bridge/standby.py:1-25`); HIBERNACION nunca se alcanza (solo se declara, `state_machine/state_machine.py:134`); sin apagado de salidas en backend (OPC-25). El valor solo se edita como parámetro del sistema (B). | Sí (para el comportamiento de la v4 §6) |
| Usuarios | `POST /usuarios` | **Parcial** | Solo crear. No hay listar, desactivar ni restablecer contraseña. Tabla `operadores` no existe. | Sí, salvo "crear" (y crear depende de A1) |
| Conectividad (wifi, IP, correo) | — | **Falta** | Solo `ui_qml/exportacion/config_correo.py` (JSON + keyring, "PROVISIONAL", sin endpoint). Wifi/IP: nada. | **Sí** |
| Bitácora (lectura) | — | **Falta** | `get_auditoria` existe en `db_manager.py:278-292`, pero no hay `GET /audit_log` ni unión con `cycle_params_audit`/`sensor_calibration_audit`. | **Sí** |
| Fecha y hora | — | **Falta** | Sin endpoint ni código de ajuste de reloj (grep sin resultados). | **Sí** |
| Información del sistema | Lectura parcial | **Parcial** | `ui_qml/bridge/info_equipo.py` lee perfil de instalación, versión del paquete y `GET /cycle/history`; "versión de la tarjeta" y "último mantenimiento" sin fuente (`info_equipo.py:11-12`). `/status` da `card_connected` y `comunicacion`. | No (se puede construir con lo que hay y "No disponible") |
| Respaldo / restauración | — | **Falta** | Nada. | **Sí** |
| Entradas/Salidas con modo prueba | `POST /io/test/enter` `/exit`, `PATCH /io/test/output/{name}`, `GET /status` | **Listo** | Token técnico/ingeniero (`server.py:1143`), sesión dueña (`:1164-1170,1184,1264`), guard CICLO/HIBERNACION/EMERGENCIA (`:1156,1256`), paro (`:1259`), R-02 al encender: presión atmosférica y puertas cerradas leídas en vivo (`:1205-1245`); `/status` da DI, DO y lecturas (`:486-507`). Depende de A1 para el token. | No (salvo A1) |
| Mantenimiento y contadores | — | **Falta** | `ciclos_servicio`/`dias_servicio` no existen; `resumen_sistema.py:210` "no existe fuente de mantenimiento". Sin impresión de página de prueba ni de ganancias. | **Sí** |

### G. UI QML

| # | Pregunta | Respuesta | Evidencia |
|---|---|---|---|
| G1 | ¿Login QML y contenedor de Opciones? | **Sí.** Login QML y `Opciones.qml` con cajón lateral modal, botón hamburguesa y `BarraInferiorMenu` con Salir (confirmación si hay cambios) e Inicio. | `qml/Pantallas/Login.qml`, `Opciones.qml:16,126-146,217-227,232-244,352-354`; `Main.qml:77,212,232` |
| G2 | ¿Qué pantallas existen? | El marco y 7 entradas: Parámetros del ciclo, Parámetros del sistema, Entradas/Salidas, Mantenimiento, Opciones avanzadas (técnico e ingeniero) y Usuarios, Conectividad (admin). **Todas** muestran "Próximamente". No hay entradas de Fecha y hora, Bitácora ni Información del sistema. | `domain/permisos_opciones.py:35-43`, `Opciones.qml:10,191-194` |
| G3 | ¿Cómo pasa la identidad/token? | `LoginController` abre la sesión en `SessionManager` (clase, una por proceso/ventana) con la fila de `usuarios`; `OpcionesController` lee usuario, nombre y rol de ahí. **No hay token.** | `login_controller.py:82-86`, `opciones_controller.py:28,35-57` |
| G4 | ¿Claves i18n es/en? | Claves estables solo en **español** (`assets/textos/es.json:6-23`, bloque `opciones`). No existe `en.json` (la carpeta solo tiene `es.json`). | `ui_qml/assets/textos/` |

---

## 2. Veredicto por pantalla de Opciones

| Pantalla | Veredicto |
|---|---|
| Marco (login, cajón, barra inferior) | **Ya construido.** |
| Parámetros del ciclo → fases → parámetros → ventana de ajuste | **Bloqueada por:** A1 (token en QML); C1 (leer parámetros de cualquier programa, lista de fases, defecto y último cambio). La escritura (`PATCH /cycle/parameter`) sí existe. |
| Parámetros del ciclo → programas (técnico) | **Bloqueada por:** C4 (no hay backend). |
| Parámetros del ciclo → sensores de temperatura | **Bloqueada por:** D1, D2, D3, D4 (nada en `dev`; la rama sin unir no cumple la regla 0–2 ni la etapa 1). Además P-2 de la v4 y la spec de sensores siguen en borrador. |
| Parámetros del ciclo → entradas mostradas | **Bloqueada por:** D5 y P-9 (`io_enabled` sin lector). |
| Parámetros del sistema | **Bloqueada por:** A1; B1–B5 (tabla, escritura, metadatos, reset, aplicación en vivo); B7 (rangos). Solo se podría construir una vista de solo lectura con `GET /global_params`. |
| Entradas y salidas (DI, DO, lecturas, modo prueba) | **Se puede construir la UI ya**, salvo que encender/salir del modo prueba exige token → **bloqueada por A1** para la parte de escritura. La lectura en tiempo real sí se puede ya. |
| Entradas y salidas → calibración de sensores (ingeniero) | **Se puede construir la UI ya** con el método actual (2 puntos), **pero** su escritura depende de A1. |
| Mantenimiento (contadores, atmosférica, impresora) | **Bloqueada por:** E (calibración atmosférica), contadores de servicio (B7/F), página de prueba. |
| Opciones avanzadas (máquina, E/S, respaldo) | **Bloqueada por:** todo el backend (no existe nada; R-03 y R-04 sin implementar). |
| Usuarios | **Bloqueada por:** A1 (para crear) y endpoints de listar/desactivar/restablecer y `operadores`. |
| Conectividad | **Bloqueada por:** backend inexistente (y OPC-01 de la v4). |
| Fecha y hora | **Bloqueada por:** backend inexistente; además falta la entrada en `permisos_opciones.py`. |
| Bitácora de auditoría | **Bloqueada por:** `GET /audit_log` y la unión con las tablas históricas; falta la entrada en `permisos_opciones.py`. |
| Información del sistema | **Se puede construir la UI ya** (con "No disponible" donde no hay fuente); falta la entrada en `permisos_opciones.py`. |

## 3. Veredicto global

**No se puede continuar con la UI de Opciones más allá de pantallas de solo lectura** (Información del sistema, lectura de E/S, vista de parámetros sin editar). Toda pantalla que escribe depende de que QML tenga un token, y la mayoría de las secciones no tienen backend.

Mínimo de backend que falta, en orden de dependencia:

1. **T-8** (spec de autenticación, etapa 4): login QML contra `POST /auth/login`, token por ventana, manejo de 401/403/409 y cambio de contraseña obligatorio. Sin esto ninguna escritura funciona y las semillas entran sin cambiar la clave.
2. **T-17** (etapa 3): copia profunda de parámetros del ciclo y regla de fases pendientes, para que la edición del ingeniero en CICLO deje de ser provisional (409).
3. **Spec de parámetros, fases 1–2:** migración v2 (`system_params`), `ConfigManager` con `RLock` y `set()` transaccional con `audit_log`, `PATCH`/`reset` de `/global_params` con metadatos, lectura en vivo en `ServicioPuertas`/`preparado_state`, y corrección de rangos/defectos del JSON (B7).
4. **Lectura para Parámetros del ciclo:** parámetros de cualquier programa, lista de fases, defecto (del perfil de fábrica) y último cambio desde `audit_log`.
5. **`GET /audit_log`** con filtros, paginación y unión con las tablas históricas.
6. **Sensores y entradas mostradas:** decidir si se rescata la rama `feature/roles-sensor-temperatura` o se reimplementa; ajustar a 0–2 Referencias, token, guard y `audit_log`; lector de `io_enabled` (P-9) y tablas de entradas mostradas (spec de parámetros §9).
7. **Calibración atmosférica** (spec de parámetros §8 y fase 4).
8. **Gestión de programas** (habilitar, duplicar, borrar) — no tiene spec de backend.
9. **Suspensión en backend** (HIBERNACION real, apagado de salidas, OPC-25) y el valor 0.
10. **Usuarios (listar, desactivar, restablecer, operadores), Fecha y hora, Mantenimiento, Respaldo/restauración, Conectividad, Opciones avanzadas** — sin spec de backend todavía.

---

## 4. Calibración de sensores — método actual (D6)

1. `PATCH /calibration/{tipo}/{sensor}` (solo ingeniero, `server.py:397-399`) recibe `shown_low`, `real_low`, `shown_high`, `real_high` (`:405-406`).
2. Invierte la calibración de usuario vigente (lineal o polinomial) para obtener el valor de fábrica en cada punto (`invert_user_calibration`, `hal/measures/calibration_tools.py:12`).
3. Ajusta una recta por dos puntos (`fit_two_point`, `calibration_tools.py:60-66`) y obtiene la nueva ganancia y compensación.
4. Escribe el YAML de calibración (`write_user_calibration`) y recarga `Units` (`server.py:436-440`).
5. Registra `calibracion_cambio` en `audit_log` con ganancia/compensación anterior y nueva y los puntos (`:441-448`).
6. Lectura: `GET /calibration/{tipo}/{sensor}` devuelve `is_poly`, `gain`, `offset`, `poly` y el último cambio (`audit_log`, o la tabla histórica) (`:360-394`).

Observaciones: dos puntos sin verificación de linealidad (OPC-04 de la v4, aceptado temporalmente); con coeficientes polinomiales la ganancia y compensación no se aplican; la conversión de fábrica también aplica un `gain/offset` propio del bloque de fábrica (`hal/measures/converters.py:109-127`). No hay defecto, "último guardado" ni fecha de vencimiento expuestos (los pide la v4 §8). Queda pendiente de revisión, como indica el pedido.

---

## 5. Hallazgos

| Id | Severidad | Hallazgo | Impacto normativo |
|---|---|---|---|
| **OPC-27** | **Alto** | El login QML valida contra SQLite sin pasar por `/auth/login` (`login_controller.py:76-86`): no aplica el bloqueo de 5 intentos, no registra `login_*` en `audit_log` e ignora `debe_cambiar_clave`, de modo que `admin/admin1234` e `ingeniero/ingeniero1234` abren Opciones QML sin cambiar la contraseña. Es provisional hasta T-8, pero hoy es el único login que usará Opciones. | IEC 62304 §5.2/§7 (requisitos de seguridad sin implementar en el camino real del usuario); ISO 14971: control de riesgo de acceso no efectivo. Mitigado mientras QML no escriba nada. |
| **OPC-28** | **Alto** | Contradicción de permisos entre documentos y código. (a) La v4 (§2) da al técnico E en sensores, entradas mostradas y programas, y L en fases; la spec de autenticación (decisión 25) y el backend limitan parámetros de ciclo a ingeniero. (b) `permisos_opciones.py` sigue la rev. 3.1 de otro plan: admin no ve Parámetros del sistema (v4: L) y faltan Fecha y hora, Bitácora e Información del sistema. (c) `edicion_permitida` deja al ingeniero editar **cualquier sección en cualquier estado** (`permisos_opciones.py:61-72`), mientras la spec limita la excepción a parámetros de ciclo y calibración; y para los demás roles usa {PREPARACION, PREPARADO}, cuando el backend permite "distinto de CICLO" (incluye FALLA) y la v4 §10.2 dice "solo en PREPARADO". | IEC 62304 §5.2.6/§5.7 (requisitos inconsistentes, verificación imposible). Con el backend como autoridad no hay riesgo físico, pero la UI mostraría controles que el backend rechaza. |
| **OPC-29** | **Alto** | Los valores de fábrica del JSON no coinciden con la v4: `temp_max_apertura` 120 °C (v4: 80), `tiempo_standby` 5 (v4: 10) y rango 1–60 (v4: 0–60), `timeout_puerta` e intervalos de impresión con mínimo 0 (v4: 0 no permitido), empaque sin rango (`global_params.json:5-15`). Con 120 °C por defecto, la puerta se puede abrir con la cámara hasta 120 °C. | ISO 14971: control de riesgo de quemadura/apertura (temperatura segura) con valor por defecto más permisivo que el aprobado. |
| **OPC-30** | Medio | La auditoría es "best effort": si falla la escritura en `audit_log`, la calibración o el parámetro de ciclo quedan cambiados sin registro (`server.py:88-104`, `:445`, `:1119`). La spec de parámetros exige cambio y registro en una sola transacción para el sistema (§3.1, criterio 2), pero no lo dice para ciclo ni calibración. | IEC 62304 §8 (trazabilidad de configuración); R-05 de la v4. |
| **OPC-31** | Medio | La rama `feature/roles-sensor-temperatura` (sin unir, 2026-09-08) implementa roles de sensor con **un único** sensor Referencia (commit `02dbf86`), sin token, sin guard de estado y con `git_autocommit`. Unirla tal cual reintroduciría endpoints de configuración abiertos y contradiría la v4 (0–2 Referencias). | IEC 62304 §5.1/§6 (gestión de configuración de ramas); OPC-02/H-03. |
| **OPC-32** | Medio | `cycle_temperature_sensors` existe en los 5 perfiles pero nadie en `dev` lo lee: el control usa siempre `temp_camara` (y F0 `min(temp_camara, temp_2_camara)` si hay sensor de líquido, `control_loop.py:255`). Configurar sensores en la UI no tendría efecto hoy. | ISO 14971: el operador creería configurado un sensor Principal que el control no usa. |
| **OPC-33** | Medio | Coerción laxa en `Cycle.set_param`: `bool("false")` es `True` y se acepta NaN (`cycle_manager.py:55-60`). Afecta a parámetros como `globals.F0` desde `PATCH /cycle/parameter`. | IEC 62304 §5.5.3 (validación de entradas); un "false" textual activaría F0. |
| **OPC-34** | Medio | Suspensión: 0 no desactiva (se convierte en 5, `standby.py:34,44-45`), contra la v4 §6. Y HIBERNACION sigue sin alcanzarse (OPC-25). | ISO 14971 (v4 §6 exige apagar salidas en suspensión). |
| **OPC-35** | Bajo | `GET /cycles` no permite leer parámetros de un programa no seleccionado; `GET /cycle` depende de la selección actual. La UI no puede recorrer programa → fase → parámetro sin cambiar la selección. | — |
| **OPC-36** | Bajo | Sin `en.json`: la v4 §1.5 pide inglés seleccionable "requisito normativo"; hoy solo hay claves en español. | Etiquetado/usabilidad (IEC 62366-1), no 62304. |
| **OPC-37** | Bajo | Residuos de `PATCH /cycle/parameters`: `ui_pyside/views/secado.py:135` y `tests/test_patch_cycle_parameters.py` (cliente con mock). PySide obtendría 404/405. | Ninguno si PySide se retira. |
| **OPC-38** | Bajo | Las semillas solo se crean con la tabla `usuarios` vacía (`db_manager.py:623-625`); una base de desarrollo previa conserva hashes SHA-256 que nunca validan (decisión 27). Requiere recrear la base. | — |

Divergencias de documentos (sin severidad, para su registro): el pedido cita `planeacion_opciones.md` v2, el repo tiene v4; la Fase 1 de QML siguió `planeacion_opciones_parametros_ciclo.md` rev. 3.1, no la v4.

---

## 6. Pruebas

### 6.1 Resultado

`python -m pytest -q` sobre el árbol de trabajo de `dev` (con los cambios sin commit de `server.py` y `serial_link.py`): **2022 pasan, 0 fallan**, 6 advertencias de deprecación (`QMouseEvent`, `datetime.utcnow`), 166 s. Excluidos por `pyproject.toml` (`addopts`): `Interfaz.py`, `ventana_emergente.py`, `test_flujo_unidades.py`, `test_rutas.py`, `test_config.py`.

### 6.2 Cobertura por área

| Área | Archivos de prueba | Cobertura |
|---|---|---|
| A. Autenticación | `test_backend_autenticacion.py` (43 pruebas), `test_backend_guard.py` (12), `test_db_audit_log.py` (6), `test_usuarios_db.py`, `test_login_controller.py`, `test_login_qml_autenticacion.py`, `test_nuevo_usuario_puente.py`, `test_nuevo_usuario_qml.py` | Buena en backend (token, roles, bloqueo, semillas, `POST /usuarios`, host, guard). Ninguna prueba de login QML contra backend (no existe). |
| B. Parámetros del sistema | — | Ninguna (no hay escritura). |
| C. Parámetros del ciclo | `test_backend_cycle_parameter_endpoint.py`, `test_cycle_set_param.py`, `test_cycle_params_audit.py`, `test_backend_cycle_select_endpoint.py` | Escritura, rol y guard. Sin gestión de programas. |
| D. Sensores | `test_backend_calibration_endpoints.py`, `test_calibration_tools.py`, `test_calibration_writer.py`, `test_sensor_calibration_audit.py`, `test_units_reload_calibration.py`, `test_ciclo_sensores.py` | Solo calibración. Roles y entradas mostradas: ninguna en `dev`. |
| E. Calibración atmosférica | — | Ninguna. |
| F. Otras | `test_io_test_mode_endpoints.py` (12), `test_standby.py`, `test_actividad_ui_backend.py`, `test_permisos_opciones.py` (7), `test_opciones_controller.py`, `test_opciones_qml.py` (4) | Modo prueba y marco de Opciones; resto sin backend. |

---

## 7. Preguntas pendientes

1. ¿Qué plan manda para la matriz de permisos de Opciones: la v4 (`planeacion_opciones.md` §2) o la rev. 3.1 de `planeacion_opciones_parametros_ciclo.md` que siguió la Fase 1? En particular, ¿el técnico edita sensores, entradas mostradas y programas (v4) aunque los parámetros de ciclo sean solo de ingeniero (spec de autenticación, decisión 25)?
2. ¿En qué estados se edita la configuración: "distinto de CICLO" (spec de autenticación decisión 13 y backend, incluye FALLA), "solo PREPARADO" (v4 §10.2) o {PREPARACION, PREPARADO} (UI actual)? ¿Y la excepción del ingeniero cubre solo parámetros de ciclo y calibración, o "cualquier sección en cualquier estado" como implementa `permisos_opciones.py`?
3. ¿Se confirma como definitivo el criterio de aceptación de la calibración atmosférica de la v4 §5 (promedio 60–106 kPa absolutos y máx − mín ≤ 1.0 kPa), o sigue siendo propuesta?
4. ¿La rama `feature/roles-sensor-temperatura` se rescata (y se corrige a 0–2 Referencias con token y auditoría) o se descarta y se reimplementa según `planeacion_sensores_ciclo.md`?
5. ¿Gestión de programas, Usuarios (listar, desactivar, restablecer, operadores), Fecha y hora, Mantenimiento, Respaldo, Conectividad y Opciones avanzadas tendrán spec de backend propia? Hoy ninguna planeación las especifica a nivel de endpoints.
6. ¿El "valor por defecto" de un parámetro de ciclo es el del perfil de `cycles/factory/` del mismo programa? Los programas de usuario sin equivalente de fábrica (`instrumental_121.json` no está en `factory/`) no tendrían defecto.
7. P-13 de la v4: ¿se confirma `timeout_chaqueta` en 10–180 min?
