# U11 — Cuentas Admin e Ingeniero (tanda 11, D11-6)

- Rama: `tanda-11-u11` (desde `tanda-11`, 1b3ec0d). Sin push.
- Fuente: `docs/mis_plans/decisiones_tanda_11.md` §D11-6 e `instruccion_claude_code_tanda_11.md` etapa U11.
- Toca la autenticación: falta el revisor `safety-reviewer` que pasa la sesión principal sobre esta rama.

## Qué se hizo, por punto de D11-6

**6.1 Nombres.** Las semillas pasan a `Admin` / `Admin` e `Ingeniero` / `Ingeniero` (usuario / nombre mostrado). El rol sigue siendo `admin` / `ingeniero` (minúsculas, sin cambio). Están en `_USUARIOS_SEMILLA` de `db_manager.py`.

**6.2 Marca persistente.** Se agrega la columna `usuarios.cuenta_sistema INTEGER NOT NULL DEFAULT 0` con la migración numerada **v11** (`_migracion_v11`, dentro del mecanismo existente de `PRAGMA user_version`/`_MIGRACIONES`). La protección se basa en la marca, no en el texto del usuario. Tiene dos capas:
- **Base de datos (triggers, defensa en profundidad):**
  - `usuarios_cuenta_sistema_protegida`: una fila marcada no cambia de `usuario`, `nombre` ni `rol`, y no pasa de activa a inactiva.
  - `usuarios_marca_sistema_inmutable`: la marca no se pone ni se quita con UPDATE.
  - `usuarios_marca_sistema_solo_semilla`: un INSERT con la marca solo se acepta si `creado_por='semilla'`.
  - Borrar ya estaba prohibido para todos desde la v9 (`usuarios_sin_delete`).
  - `hash_pw` y `debe_cambiar_clave` sí cambian: cambiar y restablecer la contraseña siguen funcionando.
- **Backend:** `DbManager.fijar_activo_usuario` devuelve `"cuenta_sistema"` al desactivar una cuenta marcada. Reactivar sí se permite: sirve para una base antigua que traiga la semilla inactiva.

**6.3 Rechazo 409 con auditoría, y UI.**
- En `server.py`, `_rechazar_cuenta_sistema()` responde 409 con `codigo="cuenta_sistema"` y escribe en la bitácora el evento nuevo `cuenta_sistema_rechazada`, con `detalle.accion` = `desactivar` / `borrar` / `cambiar_rol` / `renombrar`. Hace falta escribirlo aparte porque `_rechazar` ya no audita desde D9-6.
- `PUT /usuarios/{u}/activo` con `activo=false` sobre una cuenta marcada: 409 `cuenta_sistema`. Se comprueba antes del 403 por rol objetivo y se repite tras la escritura (resultado `"cuenta_sistema"` de la BD).
- Rutas nuevas, solo de rechazo: **`DELETE /usuarios/{u}`** y **`PATCH /usuarios/{u}`**. El cuerpo admite `nombre`, `usuario` y `rol`; cualquier otro campo da 422. Las dos exigen sesión de admin o ingeniero, devuelven 404 si el usuario no existe y 409 `cuenta_sistema` (auditado) si es Admin o Ingeniero. Para cualquier otro usuario responden 409 `usuario_no_se_borra` o `modificacion_no_disponible`. **Nunca modifican nada.** Ver DECISIÓN SIN CONFIRMAR 1.
- `GET /usuarios` expone `cuenta_sistema` (bool) en cada fila.
- UI QML (`OpcionesUsuarios.qml` + `usuarios_controller.py`):
  - cada fila trae `cuentaSistema`;
  - con una cuenta del sistema seleccionada (y activa), el botón «Desactivar» queda deshabilitado y aparece el aviso `motivoCuentaSistema`;
  - «Restablecer contraseña» sigue habilitado;
  - el código `cuenta_sistema` se muestra con `gestion_usuarios.err_cuenta_sistema`.
- La UI no tiene acciones de borrar, renombrar ni cambiar rol para ningún usuario, así que no hay nada más que ocultar.

**6.4 Sin distinguir mayúsculas.**
- `get_usuario_by_username` (inicio de sesión, cambio de contraseña, reasignación) compara con `casefold()` en Python, igual que `existe_usuario`.
- Si en una base antigua hay dos usuarios que solo difieren en mayúsculas, decide la coincidencia exacta; sin ella **no se elige ninguno** y el inicio de sesión falla.
- El contador de bloqueo ya era insensible a mayúsculas (`ControlIntentos._clave`).
- `crear_usuario` (BD) rechaza un nombre que solo difiera en mayúsculas con la comprobación dentro del candado, en el mismo bloque que el INSERT; así cierra la carrera que el UNIQUE exacto no cubría. El backend ya devolvía 409 `usuario_existe` vía `existe_usuario`.
- La regla del «último ingeniero activo» se conserva sin cambios. Ojo: con la cuenta `Ingeniero` activa (y ya no desactivable) esa regla no se alcanza en uso normal; solo actúa si una base antigua trae la semilla inactiva (cubierto por prueba).

**6.5 Migración al arrancar.** `_marcar_cuentas_sistema()` corre dentro de la v11, en la transacción `BEGIN IMMEDIATE` de `_migrar_versiones`:
- Renombra `admin`→`Admin` e `ingeniero`→`Ingeniero` (usuario y nombre) **solo** en filas con `creado_por='semilla'`, y les pone la marca.
- Conserva id, `hash_pw`, `debe_cambiar_clave`, `activo` y `rol`.
- No reescribe la auditoría ni los ciclos: `audit_log` además es de solo anexar.
- Agrega una fila `usuario_renombrado` por cuenta, con `usuario="sistema"`, `entidad`=nombre nuevo, anterior y nuevo `{usuario, nombre}` y `detalle.origen="migracion_v11"`.
- **Idempotente:** `user_version` evita que se repita, y además la función, llamada a mano otra vez, no cambia nada ni audita (probado).
- **Choque:** si otro usuario coincide sin distinguir mayúsculas con el nombre nuevo, la semilla **no se renombra**, se registra un WARNING en el log («… choca sin distinguir mayúsculas … (pregunta para Cristian)») y queda como PREGUNTA 1. Aun así la semilla se marca.
- Los triggers se crean después del renombre.
- **Sesiones:** los tokens viven solo en memoria (`AlmacenTokens`), y la migración corre al abrir la BD, en el arranque, cuando no hay sesiones. No hay nada que conservar ni que romper.

**6.6 BD nuevas.** `seed_admin_if_empty` inserta `Admin`/`Ingeniero` con `cuenta_sistema=1`, `debe_cambiar_clave=1` y las mismas contraseñas iniciales (`admin1234` / `ingeniero1234`, mismos hashes precalculados).

**Simulador** (`simulador/autenticacion_simulada.py`): semillas renombradas a `Admin`/`Ingeniero` y login sin distinguir mayúsculas, igual que el backend real, para que la batería de contrato siga valiendo en los dos.

**Bitácora:** eventos nuevos `usuario_renombrado` y `cuenta_sistema_rechazada` en `core/runtime/bitacora.py:EVENTOS`, con textos `bitacora.ev.*` y `bitacora.tipo.*` en es y en.

**Documentos:**
- `docs/instalacion/LEEME_INSTALACION.md` §5:
  - credenciales `Ingeniero`/`ingeniero1234` y `Admin`/`admin1234`;
  - aviso de que el usuario no distingue mayúsculas y de la migración automática;
  - las dos cuentas no se desactivan, borran, renombran ni cambian de rol.
  - `entrega/` no se tocó.
- Hoja de banco:
  - caso nuevo **D-26b** «Cuentas del sistema Admin e Ingeniero» y ajuste del paso 4 de D-26, que ya no puede desactivar «al único ingeniero» en banco;
  - editado en `pruebas.py`;
  - `.html` regenerado con `generar.py`, cuyo diff es solo D-26/D-26b;
  - el `.md` editado a mano (ver Pendiente 2).

## Commits

| Commit | Mensaje |
|---|---|
| bdf98f1 | feat(tanda11-u11): cuentas del sistema Admin e Ingeniero (D11-6) |
| 0dd5dda | test(tanda11-u11): ajusta pruebas y simulador a Admin/Ingeniero y esquema v11 |
| 52c1b99 | docs(tanda11-u11): credenciales Admin/Ingeniero en el LEEME y caso D-26b en la hoja de banco |
| (este) | docs(tanda11-u11): informe U11 |

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-ac703b4234b11450c\src\autoclave\__init__.py` (con `PYTHONPATH` del worktree).

**Nuevas** en `tests/test_u11_cuentas_sistema.py`, 42 casos (primero en rojo: `ESQUEMA_VERSION` 10 < 11):
- BD nueva con Admin/Ingeniero marcados y contraseñas iniciales válidas.
- Migración sobre una **copia** de una BD v10 con `admin`/`ingeniero`, construida con las migraciones 1-10 y la siembra antigua. Comprueba:
  - id, contraseña (incluida una ya cambiada), `debe_cambiar_clave` (0 y 1), activo y rol intactos;
  - auditoría previa idéntica, con las filas viejas aún con `admin`;
  - 2 filas `usuario_renombrado` con anterior y nuevo;
  - el original sin tocar.
- Segundo arranque y llamada manual repetida de `_migracion_v11`: usuarios y auditoría idénticos byte a byte.
- Choque (`ADMIN` no semilla): la semilla `admin` no se renombra, queda marcada, hay WARNING en el log y solo se audita `Ingeniero`.
- Fila no semilla (`creado_por=''`): no se renombra ni se marca.
- Triggers: 8 operaciones SQL directas rechazadas (renombrar usuario y nombre, cambiar rol, desactivar, quitar o poner la marca, DELETE, INSERT marcado no semilla).
- Contraseña de la cuenta del sistema: sí se cambia y se restablece; `fijar_activo_usuario` devuelve `cuenta_sistema`.
- Búsqueda: `admin`/`ADMIN`/`Admin`/`aDmIn` → `Admin`; inactivo → None; alta `ADMIN` → IntegrityError; coincidencia ambigua → None.
- API:
  - login con `admin`, `ADMIN` y `Admin` (200, `usuario="Admin"`, `login_ok` con `Admin`);
  - 409 `cuenta_sistema` y auditoría al desactivar Admin e Ingeniero (sesión ingeniero y admin);
  - 409 + auditoría con `DELETE` y con `PATCH` de rol, usuario y nombre;
  - otros usuarios: 409 genérico; además 404, 403, 401 y 422;
  - restablecer y cambiar la clave de Admin: 200;
  - alta de `admin`/`ADMIN`/`ingeniero`/`TOMAS_TEC`: 409 `usuario_existe`;
  - **último ingeniero activo** sobre una BD migrada con la semilla inactiva: 409 `ultimo_ingeniero`; reactivar `Ingeniero` da 200 y desactivarlo de nuevo da 409 `cuenta_sistema`.
- UI:
  - el controlador expone `cuentaSistema` y mapea el error;
  - pantalla QML offscreen: con `Admin` seleccionado, «Desactivar» deshabilitado, «Restablecer» habilitado y aviso visible; con un técnico, al revés.

**Ajustadas (efecto esperado de U11):**
- `test_db_audit_log`, `test_i4_ingles_backend`, `test_o1_operador_ciclo`, `test_s2b_d8_2_14_avisos_ticket_bd`: versión de esquema 10 → 11.
- `test_contrato_autenticacion`: «pendiente» = `Admin`; `/auth/sesion` devuelve `Admin`.
- `test_contrato_autenticacion_simulador`: semilla `Admin`.
- `test_login_qml_autenticacion`: se escribe `admin` y la sesión es `Admin`.
- `test_o2b_usuarios::test_no_deja_sin_ingeniero_activo`: Ingeniero da 409 `cuenta_sistema`; para la regla se apaga la semilla sin triggers.

**Resultados exactos:**
- Barrido de los 83 archivos de `tests/` que nombran usuarios, login, bitácora, versión de esquema o semillas (`-n auto`), antes de los ajustes: `8 failed, 2461 passed, 3 xfailed`. Las 8 son las ajustadas de arriba.
- Tras ajustarlas, los archivos afectados: `283 passed` + 1 fallo del simulador (corregido) + 3 errores de `test_login_qml_autenticacion` en paralelo. Esos 3 son del fixture que escribe un `.qml` temporal y se pisan entre workers, ajenos a U11. En serie: `8 passed`.
- Contrato, en paralelo: `39 passed`.
- Verificación final (`test_u11_cuentas_sistema`, `test_o2b_usuarios`, `test_usuarios_db`, `test_backend_autenticacion`, `test_contrato_autenticacion`, `test_contrato_autenticacion_simulador`, `test_o2e_bitacora`, `test_i18n`, `test_v8b_textos`): **`335 passed in 56.39s`**.
- No se corrió la suite completa (regla 8).

## DECISIONES SIN CONFIRMAR

1. **Rutas `DELETE /usuarios/{u}` y `PATCH /usuarios/{u}` solo de rechazo.** El backend no tenía borrar, renombrar ni cambiar rol para nadie. Para cumplir «el backend las rechaza igual (409, con auditoría del intento)» se agregaron estas dos rutas, que nunca modifican nada: 409 `cuenta_sistema` auditado para las 2 cuentas, 409 genérico (sin auditar) para el resto. La alternativa era no exponer rutas y confiar solo en los triggers. Reversible: se borran las dos funciones.
2. **Una semilla inactiva en una BD antigua sigue inactiva tras migrar.** No se reactiva sola; se puede reactivar desde la UI y desde ahí ya no se puede desactivar. Lo más conservador es no cambiar el estado en silencio.
3. **Ante un choque de nombres, la semilla se marca aunque no se renombre.** La protección va por la marca. Si Cristian prefiere que no quede protegida, basta con no marcarla en ese caso.
4. **Búsqueda ambigua sin coincidencia exacta → nadie inicia sesión.** Con dos usuarios que solo difieren en mayúsculas, solo es posible en bases anteriores a la unicidad.
5. **Las filas semilla de bases anteriores a la columna `creado_por` (`creado_por=''`) no se migran ni se marcan**, por la letra de D11-6.5. Quedan como `admin`/`ingeniero` sin protección, aunque el ingreso funciona igual porque no distingue mayúsculas.
6. **La fila `usuario_renombrado` va con `usuario="sistema"`**, como `ciclo_interrumpido`. La bitácora la muestra como «renombró la cuenta {anterior} → {nuevo}».

## PREGUNTAS PARA CRISTIAN

1. **Choque al migrar** (D11-6.5): si en una BD existe un usuario no semilla como `Admin`/`ADMIN` o `Ingeniero`, la semilla se queda con su nombre anterior (marcada) y el log lo avisa. ¿Qué hacer en ese caso: renombrar al otro usuario, o dejarlo así?
2. Con la cuenta `Ingeniero` no desactivable, la regla del «último ingeniero activo» prácticamente deja de actuar. ¿Se mantiene tal cual (así se dejó) o se replantea?

## Pendientes y notas

1. ~~«Último ingreso» de Admin/Ingeniero tras migrar~~: resuelto en la revisión de seguridad (ver abajo, «Opcional»).
2. **Hoja de banco: el `.md` está desincronizado del generador.** El `.md` tiene unas 300 líneas editadas a mano (tanda 10) que `generar.py` borraría al regenerar. Por eso el `.md` se editó a mano (D-26 y D-26b más la fila del índice) y solo el `.html` se regeneró. Alguien debería pasar esas ediciones a `pruebas.py`.
3. **Documentos que nombran `admin`/`ingeniero` y no se tocaron:**
   - informes históricos (`docs/informes/**`, `docs/handoff`, `docs/superpowers`);
   - planes de Cristian en `docs/mis_plans/planeacion_*.md` e instrucciones de tandas anteriores: los planes no se redactan, ver memoria;
   - el usuario `admin` del **Generador** (LEEME, línea del paso 2 de la sección del generador), que es otra aplicación con su propia BD, fuera de D11-6.
4. **Ensayo F → G** (instrucción, sección de entrega) sobre una copia de la BD real de la F: lo hace la etapa K11. La migración ya se probó sobre una BD v10 construida con el código anterior.

## Revisión de seguridad

Revisión de la sesión principal, sin hallazgos bloqueantes. Cada hallazgo se corrigió en esta misma rama y con TDD: primero las pruebas de `tests/test_u11_revision_seguridad.py`, en rojo (34 fallos), y luego el código. Commits `acd666e` y `56ee963`.

| Hallazgo | Qué se hizo |
|---|---|
| **SAF-01** `casefold()` no normaliza Unicode: se podían crear `Αdmin` (alfa griega), `Ａdmin` (ancho completo) o `Admin` + U+200B, que imitan a las cuentas del sistema. | Ver detalle debajo de la tabla. |
| **SAF-02** `INSERT/UPDATE OR REPLACE` borraría la fila de Admin sin disparar `usuarios_sin_delete`. | `DbManager.__init__` activa `PRAGMA recursive_triggers = ON` en su conexión. Las pruebas de `db_manager`/auditoría siguen verdes: ningún código usa REPLACE, y el `ON CONFLICT DO UPDATE` de `system_params` no tiene triggers. El trigger `usuarios_cuenta_sistema_protegida` cubre también `id` y `creado_por`. Probado con `INSERT OR REPLACE` por id, `REPLACE INTO` con el usuario `Admin`, `UPDATE OR REPLACE` que choca con `Admin`, `UPDATE id` y `UPDATE creado_por`: los 5 rechazados y la fila intacta. Límite documentado en el docstring de la v11: otra conexión a la BD sin ese PRAGMA (herramienta externa) no queda cubierta frente a REPLACE. |
| **SAF-03** La semilla se identificaba solo por `creado_por='semilla'` y el nombre. | La migración exige además el rol (`admin` para Admin, `ingeniero` para Ingeniero). Si no coincide, no renombra ni marca la fila y deja un WARNING en el log (PREGUNTA 3). En el choque de nombres se mantiene la marca (protege). Anotado en el docstring de `_marcar_cuentas_sistema`: una futura migración que renombre una cuenta ya marcada tendrá que soltar y volver a crear `usuarios_cuenta_sistema_protegida`. |
| **SAF-04** `PATCH /usuarios/{u}` no registraba qué se pidió y aceptaba un cuerpo vacío. | Cuerpo vacío o con todos los campos en null: 422 (`{"campo": "cuerpo", "codigo": "obligatorio"}`), antes de buscar el usuario y sin auditar. En el 409 de las cuentas del sistema, `detalle.campos` lleva la lista ordenada de campos pedidos. |
| **Opcional** «Último ingreso» de Admin/Ingeniero tras migrar. | Era trivial y se hizo. `listar_usuarios` agrupa los `login_ok` por nombre normalizado y toma el más reciente, así que Admin encuentra los ingresos registrados como `admin`, sin reescribir la auditoría. Efecto aceptado: en una BD antigua con dos usuarios que solo difieren en mayúsculas, ambos muestran el ingreso más reciente de los dos. |

**Detalle de SAF-01:**
- **Módulo nuevo** `core/runtime/nombre_usuario.py`, con la normalización compartida:
  - `normalizar_usuario` = NFKC y después casefold;
  - `formato_valido`: letras latinas por nombre Unicode `LATIN …` (con tildes y ñ), dígitos ASCII y `._-`;
  - `es_reservado`: `sistema` y `semilla`.
- **Dónde se usa:**
  - unicidad: `existe_usuario` y `crear_usuario` (BD);
  - búsqueda del inicio de sesión: `get_usuario_by_username`;
  - contador de bloqueo: `ControlIntentos._clave`;
  - simulador: login y alta;
  - comparaciones de la migración.
- **Validación al crear:** `codigos_nuevo_usuario` (`validacion_usuario.py`) rechaza con `formato` los caracteres de formato (Cf), de control (Cc), los de otros alfabetos, los de ancho completo y los espacios, y con `reservado` los nombres `sistema`/`semilla`. Es la única fuente de reglas: la usan el backend (`POST /usuarios`), el simulador y el puente de la UI (Nuevo usuario), así que la regla queda en los tres sin duplicarla.
- **Textos:** `validacion.formato` pasa a «Solo letras, números y . _ -, de {min} a {max} caracteres» (en: «Letters, digits and . _ - only, …»). Se agrega `validacion.reservado` en es y en.
- **Verificación previa:** antes de cambiar la regla, un barrido de los nombres de usuario de `tests/` y de las semillas no encontró ninguno válido que quede fuera; solo `a b`, que ya era un caso de rechazo.
- **Usuarios existentes:** uno con un nombre que ya no sería válido sigue entrando, porque solo se valida al crear (probado con `José Pérez` en una BD antigua).
- **Pruebas:** las 6 imitaciones se rechazan en la validación, en la API (422) y en el simulador. `ＡDMIN` comparte el contador de bloqueo y la cuenta con `admin`.

**Pruebas tras la revisión** (`autoclave.__file__` = el del worktree):
- `test_u11_revision_seguridad.py` + `test_u11_cuentas_sistema.py`: `85 passed`.
- Los 83 archivos relacionados de antes + `test_u11_revision_seguridad.py`: `2512 passed, 3 xfailed`.
- Los otros 17 archivos que importan `DbManager`, la validación, el contador o el simulador: `263 passed, 2 skipped`.
- Ajustada `test_nuevo_usuario_qml.py::test_errores_no_escriben_ni_navegan`, por el texto nuevo de `validacion.formato`.

**PREGUNTA PARA CRISTIAN 3 (SAF-03):** si una fila semilla `admin`/`ingeniero` tiene un rol distinto del esperado, la migración no la toca: queda sin renombrar y sin protección, con un WARNING en el log. ¿Qué hacer en ese caso?

## Puntos de choque tocados

- `src/autoclave/i18n/es.json` y `en.json`: `gestion_usuarios.motivo_cuenta_sistema`, `gestion_usuarios.err_cuenta_sistema`, `bitacora.ev/tipo.usuario_renombrado`, `bitacora.ev/tipo.cuenta_sistema_rechazada`; en la revisión de seguridad, `validacion.reservado` y el texto nuevo de `validacion.formato`.
- `src/autoclave/ui_pyside/services/validacion_usuario.py` (regla de alta compartida por el backend, el simulador y la UI) y `src/autoclave/backend/autenticacion.py` (`ControlIntentos._clave`).
- `src/autoclave/backend/server.py`: DTO, `_rechazar_cuenta_sistema`, `PUT activo`, rutas `DELETE`/`PATCH` nuevas.
- `src/autoclave/ui_qml/qml/Pantallas/OpcionesUsuarios.qml`.
- `docs/instalacion/LEEME_INSTALACION.md` §5.
- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (+ `.html` y `hoja_pruebas_banco/pruebas.py`).
- Esquema de BD: **v11** (`ESQUEMA_VERSION` = 11). Cualquier otra etapa que agregue una migración debe tomar la v12.
