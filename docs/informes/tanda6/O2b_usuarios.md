# O2b — Usuarios y operadores

## Qué se hizo
### Backend
- **Migración v9:** tabla `operadores` (nombre único sin distinguir mayúsculas, sin contraseña, `activo`, quién y cuándo la creó). Triggers que impiden borrar filas de `usuarios` y de `operadores` (trazabilidad).
- **Endpoints:**
  - `GET /usuarios`: admin, técnico e ingeniero. Lista sin hashes, con el último ingreso (`login_ok` de la bitácora) y `gestionables` (roles que la sesión puede modificar).
  - `PUT /usuarios/{usuario}/activo` `{activo}`: admin e ingeniero.
  - `POST /usuarios/{usuario}/restablecer_clave` `{clave, confirmacion}`: admin e ingeniero. Deja `debe_cambiar_clave=1`.
  - `GET /operadores` (lectura libre; solo `id`, `nombre`, `activo`), `POST /operadores`, `PUT /operadores/{id}/activo`: admin e ingeniero.
- **Reglas:**
  - técnico y otros roles: 403 en toda escritura;
  - el usuario objetivo debe tener un rol de `ROLES_CREABLES[rol de la sesión]` (el admin no toca a un ingeniero): 403 `rol_no_gestionable`;
  - nadie se desactiva a sí mismo (409 `autodesactivacion`); la propia contraseña va por Cambiar contraseña (409 `usar_cambio_clave`);
  - nunca queda el equipo sin un ingeniero activo (409 `ultimo_ingeniero`; comprobación y escritura bajo el mismo candado de la base);
  - desactivar o restablecer cierra las sesiones abiertas del usuario (y su modo prueba, si lo tenía).
- **Auditoría:** `usuario_desactivado`, `usuario_reactivado`, `clave_restablecida` (sin la clave), `operador_creado`, `operador_desactivado`, `operador_reactivado`.

### UI (QML)
- `OpcionesUsuarios.qml` (mockup 6): pestañas Usuarios / Operadores; filas con nombre, usuario, rol, último ingreso y chip Activo/Desactivado; para el seleccionado, "Restablecer contraseña" (contraseña temporal y su confirmación con el teclado, ocultas, y confirmación) y "Desactivar"/"Reactivar"; "+ Nuevo usuario" abre la pantalla existente. Operadores: lista, "+ Agregar operador" y desactivar/reactivar. Nota visible de no borrado.
- **Permisos (decisión 1.9):** el técnico ve la sección con todos los controles deshabilitados y el motivo. Sobre uno mismo o sobre un rol no gestionable, el motivo se muestra en la fila de acciones.
- Textos en `gestion_usuarios.*` (es/en).

## Pruebas
`tests/test_o2b_usuarios.py` (56): migración y no borrado; listado sin hash; matriz completa por rol (4 roles × objetivos admin/técnico/ingeniero) para desactivar y restablecer; 401 sin token; autodesactivación; último ingeniero; cierre de sesiones; validación 422; operadores (matriz, duplicado con Ñ, longitud); controlador; textos; pantalla por rol (admin, ingeniero, técnico). Arnés compartido `tests/opciones_qml_doble.py`. Se ajustaron las pruebas que fijaban que el técnico no ve Usuarios.

Suite completa antes del commit: 4801 passed / 2 skipped / 3 xfailed.

## Capturas
`O2b_1_usuarios_admin.png`, `O2b_1_usuarios_tecnico.png`, `O2b_2_seleccionado_admin.png`, `O2b_3_operadores_admin.png`, `O2b_3_operadores_tecnico.png`.

## Revisión (safety-reviewer): sin Críticos ni Altos
- H-01 (Medio, carrera login/restablecer): **corregido**, el login relee la fila tras verificar y no emite token si cambió.
- H-02 (Medio): las sesiones no revalidan `activo` en cada petición; la revocación depende del cierre explícito. **Abierto** (propuesta: "generación" del usuario en la sesión).
- H-03 (Bajo, usuario sin codificar en la URL): **corregido** (`quote`).
- H-04 (Bajo, bloqueo de intentos tras restablecer): **corregido**.
- H-05 (Bajo, metadatos públicos de operadores): **corregido** (solo id, nombre, activo).
- H-06 (Bajo): el inicio de ciclo aún no elige operador de la tabla (ver decisiones). H-07 (Bajo): HTTP síncrono en el hilo de la UI, como el resto de OPCIONES.
