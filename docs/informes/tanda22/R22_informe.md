# R22 — Tanda 22: teclado en pantalla que disparaba acciones con cada tecla

Fecha: 29-oct-2026. Rama `tanda-22` (desde `dev` 14f62f34), unida a `dev` en `45966035`. Entrega **1.0.0-alpha.11** (`25e48bb8`, etiqueta `v1.0.0-alpha.11`). Spec: `docs/mis_plans/prompt_claude_code_tanda22.md` (TEC-ACC-01 a TEC-ACC-07). Estado paso a paso: `estado.md`.

## 1. Informe de problema PRB-T22-01 (NTC-IEC 62304 §9)

- **Síntoma** (equipo de pruebas, 1.0.0-alpha.10, 29-oct): en Opciones › Reasignación, al pedir la contraseña de confirmación, el ingeniero no alcanzaba a escribirla. La pantalla lo sacaba con «Sesión no válida o vencida» y, al volver a entrar, el login decía «usuario bloqueado».
- **Evidencia:** `evidencia/logs_autoclave_20261029_1047.zip` (`backend.log`, `ui_puerta1.log`) y `evidencia/recoger_logs_salida.txt`. El backend no se reinició. A las 10:36:50 recibió 4 POST `/io/assignment` con `reautenticacion_fallida`, uno cada ~0,44 s (lo que tarda PBKDF2). El 5.º, a las 10:36:53, activó `ControlIntentos` (5 intentos, 300 s), que invalida el token. El envío siguiente recibió 401 `sesion_invalida`. Todo se repitió igual a las 10:42:19.
- **Causa:** `Componentes/PanelTeclado.qml` entrega lo escrito «en vivo»: con cada tecla, al abrir otro campo y, al cancelar, con `""`. Eso sirve para campos que solo guardan el texto, pero `OpcionesReasignacion._pedirClave` hacía un POST, así que cada tecla enviaba una contraseña parcial y sumaba un intento fallido. Además, el cliente no reconocía `reautenticacion_fallida` («Respuesta no reconocida del backend») y no cerraba la sesión ante el 429 de bloqueo.
- **Clasificación:** defecto de la interfaz (Clase C por el sistema). No afecta el control del proceso ni las protecciones del backend, que contó y bloqueó como estaba diseñado. Su efecto fue que la reasignación de E/S quedaba inutilizable y se bloqueaba el usuario.
- **Corrección:** ver §2. El backend no se tocó (`git diff dev...tanda-22 -- src/autoclave/backend` vacío).
- **Verificación:** pruebas nuevas (§3). Las pruebas por pantalla fallan con las pantallas anteriores (7 de 8, comprobado) y pasan con las nuevas. La suite completa está en §3. Falta verificarlo en el equipo (§5).
- **Otros puntos con el mismo defecto:** en A0 se revisaron con grep las 26 llamadas a `abrirAlfanumerico(`/`abrirNumerico(`. Se confirmaron los 7 puntos de la lista del prompt y no apareció ninguno más (detalle en `estado.md`).

## 2. Qué cambió (TEC-ACC)

| Decisión | Cambio | Archivos |
|---|---|---|
| TEC-ACC-01 | Modo acción `abrirAlfanumericoAccion(titulo, valorInicial, longitudMaxima, ocultar, alConfirmar)`. Una propiedad `_enVivo` decide el modo. En modo acción `alConfirmar` se llama una sola vez y solo al Confirmar: nunca al escribir, al cancelar, al ocultar o cerrar, ni al abrir otro campo (lo escrito se descarta). El modo en vivo no cambia. | `Componentes/PanelTeclado.qml` |
| TEC-ACC-02 | Confirmar vacío no llama al callback y deja el teclado abierto. Tras la revisión R, lo mismo con texto de solo espacios. | `PanelTeclado.qml` |
| TEC-ACC-03 | `_entregarAccion` toma el callback, anula `_alConfirmar`/`_siguiente`, emite `confirmado`/`terminado` y cierra el panel **antes** de llamarlo. Un doble toque o un Confirmar reentrante durante el POST síncrono no envía nada. | `PanelTeclado.qml` |
| TEC-ACC-04 | Los 7 puntos pasan al modo acción: Reasignación (`_pedirClave` para Aplicar, Restaurar fábrica y Verificar; nombre reforzado; nombre reforzado de Verificar), Conectividad (nombre → correo del destinatario) y Manejo de ciclos (crear, duplicar). Las cadenas avanzan solo al Confirmar el primer paso; Cancelar en cualquier paso aborta sin enviar. | `Pantallas/OpcionesReasignacion.qml`, `OpcionesConectividad.qml`, `OpcionesManejoCiclos.qml` |
| TEC-ACC-05 | El cliente reconoce `reautenticacion_fallida` y `reautenticacion_requerida` (403 del backend) con `reasignacion.err_clave` y `reasignacion.err_clave_requerida`; ya no cierran la sesión y la pantalla muestra «Contraseña incorrecta». Ante un 429 `usuario_bloqueado` en `enviar`, la sesión local se cierra al instante, sin logout por red (el backend ya invalidó el token), con el aviso `sesion.usuario_bloqueado`, los segundos y el usuario. Al abrirse, el login muestra el aviso con cuenta regresiva (comprobado en prueba, sin tocar QML). | `ui_qml/sesion_backend.py` |
| TEC-ACC-06 | Regla en la cabecera de `PanelTeclado.qml` y una línea en `CLAUDE.md` (sección Interfaz). | `PanelTeclado.qml`, `CLAUDE.md` |
| TEC-ACC-07 | Prueba de regla: recorre los `.qml`, toma el callback de cada llamada en vivo (sigue también los callbacks pasados por parámetro, como `editar(..., alConfirmar)`) y falla si contiene una acción (`control.`, `controlador.`, `.abrir(`, `.open(`, `abrirAlfanumerico`, `abrirNumerico`, `Qt.callLater`, `_pedirClave`, `.enviar(`, `.push(`, `visible = true`) o si es un identificador que no se puede revisar. Lista blanca vacía: no hubo falsos positivos. | `tests/test_t22_regla_teclado_accion.py` |

Fuera del alcance, pero necesario para que la suite quede verde: `tests/test_o3_entradas_mostradas_qml.py` escribe ahora un `.qml` temporal por proceso. Antes, con `-n auto`, Preciclo y Ciclo usaban el mismo archivo y uno lo borraba mientras el otro lo leía (carrera previa a esta tanda).

### Commits (rama `tanda-22`)
`c5ce9171` A0 · `182a6480` P2 (merge `ef295843`) · `e8bf32fc` P1 (merge `fbbdf6ee`) · `c5b8cf3a` TEC-ACC-04/06/07 · `ed938ad1` correcciones de R · `cb82f73d` carrera de o3 · merge a dev `45966035` · versión `25e48bb8`.

## 3. Pruebas

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `tests/test_t22_teclado_accion_qml.py` | 16 | Panel real en offscreen y teclas tocadas con el ratón. En modo acción: escribir no llama y Confirmar llama 1 vez con el texto completo; Cancelar, Ocultar (botón y `cerrar()`) y abrir otro campo (en vivo, acción o numérico) no llaman; Confirmar vacío, tras borrar o con solo espacios no llama y el panel sigue abierto; doble toque, doble llamada al controlador y Confirmar reentrante producen 1 sola llamada; la cadena abre el teclado siguiente. El modo en vivo queda intacto (cada tecla llega, Cancelar entrega `""`, numérico igual). |
| `tests/test_t22_pantallas_accion_qml.py` | 8 | Pantallas reales con una sesión doble que cuenta los envíos. Reasignación: la contraseña escrita letra a letra hace 0 POST y Confirmar hace 1 (aplicar, fábrica, verificar); Cancelar y Confirmar vacío hacen 0; el nombre reforzado no abre el diálogo de reinicio hasta Confirmar. Conectividad: el teclado del correo no se abre hasta Confirmar el nombre y hay 1 PUT al Confirmar el correo; Cancelar en el nombre o en el correo hace 0. Manejo de ciclos: crear y duplicar hacen 1 POST al Confirmar y Cancelar hace 0. Sin avisos QML. |
| `tests/test_t22_regla_teclado_accion.py` | 9 | La regla TEC-ACC-07 y la autoverificación del detector. |
| `tests/test_t22_sesion_bloqueo.py` | 18 | TEC-ACC-05 (400/401/403 con los dos códigos, 429 con y sin segundos, aviso en el login, casos anteriores sin cambio). |

**Suite** `pytest tests -n auto` sobre `tanda-22`: 9151 passed, 11 skipped, 7 xfailed. Hubo 1 fallo, `test_home_view::test_home_view_tarjeta_impresion_general_navega_a_impresion_menu`: es la caída conocida de un trabajador xdist (ya figura en R20 y en ajustes_28oct) y pasa en serie. También hubo 2 errores de `test_o3` por la carrera descrita arriba, ya corregida (9 passed con `-n 4`). La suite de la entrega (sobre `dev` tras el merge) dio 9153 passed y 1 failed, y esa roja pasó al repetirla en serie. Salidas en `suite_raw.txt` y `entrega_raw.txt`.

El primer intento de la suite se colgó al 43 % tras la caída de un trabajador xdist y lo detuvo el límite de tiempo; los dos siguientes terminaron con normalidad.

## 4. Revisión R (subagente, solo lectura)

No encontró hallazgos de gravedad alta ni media. Confirmó lo siguiente:
- El modo en vivo es idéntico al de `dev` en todas las rutas y no deja estado residual: `_enVivo` se fija en cada `abrir*`, después de `_guardarPendiente`.
- Ninguno de los 7 puntos puede enviar texto parcial ni `""`.
- El backend y `ControlIntentos` no se tocaron.
- El cierre por 429 no rompe el 429 del login ni el del cambio de contraseña, que van por otras funciones.

Hallazgos bajos corregidos en `ed938ad1`:
- En modo acción, el texto de solo espacios se trataba como texto.
- La regla tenía falsos negativos: le faltaban patrones, aceptaba callbacks pasados como identificador no verificables y elegía mal la función envolvente.
- La función que quita comentarios cortaba URLs.
- El conteo de usos del modo acción contaba también los comentarios.
- La prueba de pantallas filtraba avisos que contuvieran «sesion».
- Faltaban casos: Cancelar en el nombre del destinatario y Confirmar vacío en la contraseña.

Anotado y no cambiado:
- `_comprometerNumerico` no mira `_enVivo`; hoy no importa porque no existe un modo acción numérico.
- La regla no puede seguir una señal cuyo manejador ejecute una acción (p. ej. `campo.elegido(v)` en Mantenimiento, que hoy solo asigna).
- El correo de Conectividad empieza con mayúscula automática; ya pasaba en `dev`.

## 5. Decisiones sin confirmar

1. **TEC-ACC-02:** en modo acción, Confirmar vacío no hace nada y deja el teclado abierto (lo fija el prompt).
2. **Solo espacios = vacío** en modo acción (revisión R). Una contraseña formada solo por espacios no podría escribirse en estos 7 puntos; en Login, CambioClave y NuevoUsuario no cambia nada.
3. **El 429 `usuario_bloqueado` cierra la sesión en cualquier ruta que pase por `enviar`**, no solo en `/io/assignment*`. Hoy solo la reautenticación lo emite con token, y siempre con el token ya invalidado. `enviar_al_cerrar` no cambia.
4. **USB en exFAT** (por si el Setup supera 4 GB; hoy pesa 86 MB).

## 6. Qué verificar en la pantalla del equipo (alpha.11)

1. **Reasignar con contraseña:** cambiar un puerto, Aplicar y escribir la contraseña despacio. No debe pasar nada hasta Confirmar.
   - Con la contraseña errada debe aparecer «Contraseña incorrecta» sin sacar de la sesión.
   - Con 5 errores seguidos debe volver al login con «usuario bloqueado» y la cuenta regresiva.
   - Con la contraseña correcta debe aplicar.
2. **Reforzada:** cambiar una función de seguridad (p. ej. paro de emergencia). Al escribir su nombre no debe abrirse el diálogo «Se reiniciará el control» hasta Confirmar. Cancelar aborta.
3. **Verificar** una función reforzada: el nombre y luego la contraseña, cada uno solo al Confirmar.
4. **Restaurar fábrica:** la contraseña se envía solo al Confirmar.
5. **Agregar destinatario** (Conectividad): el teclado del correo se abre solo al Confirmar el nombre. Se agrega 1 destinatario, no uno por letra. Cancelar en cualquier paso no agrega nada.
6. **Crear y duplicar programa** (Manejo de ciclos): se crea 1 programa con el nombre completo al Confirmar.
7. Los formularios de siempre (Login, cambio de clave, nuevo usuario, usuarios, parámetros) deben comportarse igual que antes.

## 7. Entrega y USB

- **Versión:** 1.0.0-alpha.11 (AppVerNum 1.0.0.1011), commit `25e48bb8`, etiqueta anotada `v1.0.0-alpha.11`, carpeta `entrega/v1.0.0-alpha.11_2026-10-29/` (con `GeneradorCodigos.exe`, por `--con-generador`). Sin push (para publicarla: `git push origin dev v1.0.0-alpha.11`). No hizo falta tocar `.git/info/exclude`: los archivos sin seguimiento están fuera del producto y solo dieron aviso.
- **USB:** en la unidad E: estaba el disco 1, `Generic Flash Disk`, serie `1`, 14,65 GB, bus USB, sin arranque ni sistema. Es un disco distinto del de C: y del repositorio (disco 0) y en este PC no existe la clave de registro del autoclave.
  - **Antes:** etiqueta `CCCOMA_X64F`, FAT32, con la alpha.10, `LEEME`, `SHA256SUMS`, `drivers\`, `recoger_logs.bat` y `recoger_logs.ps1` (estos dos siguen en `tools\diagnostico\`).
  - **Formateo:** solo el volumen, exFAT, etiqueta `AUTOCLAVE`, formato rápido.
  - **Contenido copiado:** `Autoclave_Setup_1.0.0-alpha.11.exe` (89 758 445 B), `LEEME_INSTALACION.md`, `SHA256SUMS.txt` y `drivers\` (vacía, igual que en el origen).
  - **SHA-256 del Setup en E:** `8fdfa87c6b124d83b9d96cb254977adbc4a38beb32119d5b1956cf9cc5db0754`, coincide con `SHA256SUMS.txt`.
  - La unidad no se expulsó.
  - **Ojo:** la USB ya no trae `recoger_logs.*`. Si se necesitan en el equipo, cópielos desde `tools\diagnostico\`.

## 8. Recordatorio

Si quedó bloqueado en el equipo, el usuario se desbloquea solo a los 5 minutos o al reiniciar el control (`ControlIntentos` vive en memoria).
