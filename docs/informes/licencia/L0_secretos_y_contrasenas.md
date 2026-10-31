# Licencia L0 — secretos fuera del código y contraseñas al instalar

Fecha: 24-oct-2026. Rama `licencia-l0` (desde `dev`, 029feb7). Fuente: `docs/mis_plans/planeacion_licencia_pago.md` v3, §1 y §4; instrucción `docs/mis_plans/instruccion_claude_code_licencia_l0.md`.

Estado: **TERMINADA** — ver «Cierre» al final (suite, unión y push).

Ningún valor de secreto real aparece en este informe, en el código, en los logs ni en la salida de las pruebas. El archivo de secretos real no se leyó: las pruebas usan secretos de prueba fijos (`tests/conftest.py`) y `ESPECIFIKA_SECRETOS` apunta a una ruta inexistente durante toda la suite.

---

## 1. LIC-01 — secretos fuera del código

### Qué se hizo

| Archivo | Cambio |
|---|---|
| `src/autoclave/installation/secretos.py` (nuevo) | Ruta del archivo (`%USERPROFILE%\Documents\especifika_secretos\activacion.json` o `ESPECIFIKA_SECRETOS`), lectura y validación del formato `{"version": 1, "instalacion": <64 hex>, "fabrica": <64 hex>}`, huella corta (8 hex de SHA-256) y `entrada_compilacion()` para los `.spec`. Los mensajes de error nunca incluyen el valor. |
| `src/autoclave/installation/activation.py` | Sin `_SECRET_INSTALL` ni `_SECRET_FACTORY`. Carga, en orden: recurso empaquetado `config/activacion_secretos.json` (solo con `sys._MEIPASS`, vía `resource_path`) → archivo de §1.1. Sin secretos: `validate_*` devuelve `False` y se advierte **una sola vez** («compilación sin secretos de activación»); `generate_*` lanza `SecretosNoDisponibles`. No hay secreto por defecto. API pública intacta; nuevas `configurar_secretos()` (solo pruebas), `secretos_disponibles()`, `huella_instalacion()`. |
| `tools/secretos/generar_secretos.py` (nuevo) | Crea el archivo con `secrets.token_bytes(32)` ×2; se niega si ya existe (y abre con modo `x` para no pisar uno creado a la vez); imprime solo la ruta y las dos huellas. **No se ejecutó.** |
| `Autoclave.spec`, `AutoclaveBackend.spec` | Agregan `entrada_compilacion()` a `a.datas` como `config/activacion_secretos.json`. Sin archivo válido la compilación se detiene con `SystemExit` y el motivo. Imprimen la huella al compilar. |
| `GeneradorCodigos.spec` | No empaqueta el archivo; comentario de la línea 15 actualizado. |
| `tools/generador/app.py`, `lanzador.py` | Sin secretos el generador no arranca: lo registra en el log (y en la consola si la hay) y el servidor sirve solo una página 503 con el motivo en todas las rutas. La página **Usuarios** (administración) muestra la huella del secreto de instalación. |
| `.gitignore` | `especifika_secretos/` y `activacion.json`. |
| `docs/superpowers/plans/2026-05-24-temporal-codes.md` | Tenía los dos secretos antiguos en claro: reemplazados por un marcador (se comprobó sin imprimirlos que ningún otro archivo versionado los contiene). |

### Historial (§1.4)
No se reescribió el historial. Los dos secretos antiguos siguen en commits viejos (activation.py y el plan de mayo) y en cualquier copia o bifurcación del repositorio público: se consideran **comprometidos para siempre**. La rotación (archivo nuevo de Cristian) los invalida para todo lo que se compile después. Los equipos ya instalados no se ven afectados: el código de instalación solo se valida en el asistente. Explicado también en el aviso «Licencia L0» al inicio de `docs/instalacion/LEEME_INSTALACION.md`.

### Riesgo aceptado hasta L1
El ejecutable del autoclave sigue conteniendo el secreto (uno solo para todos los equipos). Además, `Autoclave.spec` es *onedir*: el recurso queda como archivo plano en `<instalación>\_internal\config\activacion_secretos.json`, legible por cualquiera con acceso al PC del equipo. Quien lo copie puede generar códigos de instalación y claves de fábrica válidos para cualquier serie. Se cierra en L1 (secreto por equipo).

---

## 2. LIC-02 — contraseñas de Admin e Ingeniero en la instalación

| Archivo | Cambio |
|---|---|
| `Pantallas/Instalacion.qml` | Paso nuevo **Contraseñas** entre Datos y Resumen, siempre presente (también en reinstalación): contraseña y confirmación de Admin e Ingeniero, ocultas en pantalla y en el teclado. «Siguiente» valida con el puente; el resumen muestra «Fijadas (se guardan al instalar)». Las contraseñas viajan a `instalar()` dentro del perfil (`contrasenas`). |
| `bridge/puente_instalacion.py` | `errores_contrasenas()`: reglas de contraseña nueva del backend (`codigo_clave`/`codigo_confirmacion` de `validacion_usuario`, sin duplicarlas) + `semilla` (de cualquiera de las dos cuentas) + `iguales` (Ingeniero = Admin). Slot `validarContrasenas` (errores i18n por campo). `instalar()` vuelve a validar, guarda las contraseñas **antes** de escribir el perfil y, si el guardado falla, devuelve error y no escribe el perfil (el asistente no termina). Nunca registra las contraseñas. |
| `db_manager.py` | Sin los comentarios con la contraseña semilla. `es_clave_semilla()` verifica contra los hashes semilla (PBKDF2), sin la contraseña en claro. `fijar_claves_instalacion()`: hash nuevo + `debe_cambiar_clave=0` + fila `contrasena_fijada_instalacion` (usuario `sistema`, entidad = cuenta, detalle con rol/origen/fecha, sin la contraseña) en **una transacción**; si un rol no tiene exactamente una cuenta del sistema, no cambia nada. `cuentas_con_clave_semilla()` para el aviso. |
| `catalogo.py`, `context.py`, `server.py`, `ui_bridge.py` | Aviso **SIS-07** «Contraseña de fábrica vigente» (AVISO, no bloquea, despeje automático). El backend lo activa al abrir la base si Admin o Ingeniero conservan el hash semilla, y lo revisa tras cada cambio o restablecimiento de contraseña. El DTO de `/status` lleva `roles_visibles`; `UiBridge` filtra por el rol de la sesión de esa pantalla, así que en la bandeja de Preciclo y en la campana solo lo ven **técnico e ingeniero**. |
| `bitacora.py`, `es.json`, `en.json` | Evento `contrasena_fijada_instalacion`, textos del paso, códigos `validacion.semilla`/`validacion.iguales` y SIS-07, en es y en. |

---

## 3. LIC-03 — `parametros_software.accdb` (solo revisión, sin cambios)

Leído en modo solo lectura con el proveedor ACE de Windows (no se instaló nada). Sin valores en este informe.

- 2 tablas de usuario: **`Calentando`** (13 filas) y **`Esterilizacion`** (15 filas). Mismas columnas: `Id` (entero), `Parametro`, `Unidad`, `Descripcion` (texto), `Valor_defecto` (entero en Calentando, real en Esterilizacion), `Valor_min`, `Valor_max` (enteros). Además 7 tablas internas de Access y 5 de sistema (`MSysObjects` no es legible sin permisos; no se pudo comprobar si hay tablas vinculadas).
- Búsqueda de patrones en los textos (correo, URL, ruta de archivo, palabras de contraseña/secreto, hexadecimal largo, teléfono): **0 coincidencias**. Texto más largo: 324 caracteres.
- Ningún código, `.spec` ni instalador lo usa (solo un commit, 1302c00, 28-jul).

**Conclusión:** es un catálogo de definición de parámetros de ciclo (nombre, unidad, rangos, descripción), el antecedente de los perfiles JSON. No se vio información personal, credenciales ni secretos. No es sensible por sí mismo, pero sí es conocimiento de proceso de Especifika en un repositorio que fue público. Queda la pregunta a Cristian (sección 6). No se borró ni se sacó del índice.

---

## 4. LIC-04 — clave de fábrica (solo revisión, sin cambios)

Confirmado: `validate_factory_key` **no se llama en ningún lugar** del software del autoclave (`src/` ni QML). Solo existe en `activation.py` y en las pruebas. El asistente no tiene diálogo de clave de fabricante (decisión 1.7, comentario en `puente_instalacion.py`).

Dónde se genera: `tools/generador/app.py`, ruta `POST /generar` (`generar_post`): para toda serie se calcula `generate_factory_key(serial)`; si la serie ya fue instalada se muestra solo la clave de fábrica (y se registra como `fabrica`); si es nueva se muestran el código de instalación y la clave de fábrica.

---

## 5. Pruebas

**Nuevas**
- `tests/test_l0_secretos_activacion.py` (28): generar→validar; otro serial, otro día u otro secreto rechazados; sin secretos `False` con una sola advertencia y `generate_*` lanza; archivo inválido = sin secretos; archivo de la variable; ruta por defecto; el ejecutable prefiere el recurso empaquetado y, sin él, usa el archivo; ningún secreto en `activation.py`; `.spec` se detiene sin archivo o con archivo inválido; la entrada empaquetada no imprime el secreto; los dos `.spec` del autoclave la usan y el del generador no; `.gitignore`; `generar_secretos.py` crea, no imprime valores, se niega si existe y da valores distintos; generador sin archivo no arranca (503 con el motivo, también desde `lanzador.main`); la página Usuarios muestra la huella.
- `tests/test_l0_contrasenas_instalacion.py` (27): reglas (obligatoria, corta, larga, confirmación distinta, iguales); semillas rechazadas con verificación real; errores para la pantalla; textos es/en; no termina sin las contraseñas; guarda el hash, apaga `debe_cambiar_clave` y audita sin la contraseña; si el guardado falla no termina; `fijar_claves_instalacion` es todo o nada; reinstalación también exige y fija; el paso está en el QML antes del resumen; `db_manager.py` sin la semilla en claro; SIS-07 con semilla y se despeja al cambiar; sin aviso tras la instalación; nunca lanza sin base; no bloqueante y solo técnico/ingeniero; DTO con `roles_visibles`; filtro por rol en bandeja/campana.

**Ajustadas** (dependían de los secretos fijos o del asistente sin contraseñas)
- `tests/conftest.py`: fixture automático con secretos de prueba y `ESPECIFIKA_SECRETOS` a una ruta inexistente.
- `tests/test_g10_codigo_activacion.py`: el «caso real» `FR4QAXQ3O43N` salía del secreto antiguo; ahora usa el código del secreto de prueba para la misma serie y día (`UOZ3P26VOUE5`, también con letras O) y sus variantes con 0, espacios y guiones.
- `tests/test_t9_instalacion.py::test_puente_instala_con_el_codigo_validado` y `tests/test_m1_puente_instalacion.py::test_puente_instalar_mesa_devuelve_error`: mandan las contraseñas y usan una base temporal.
- `tests/test_alarmas_catalogo.py`: ejemplo de SIS-07.

No se compiló con PyInstaller: la función que lee el archivo para los `.spec` se prueba sin compilar.

---

## 6. Decisiones sin confirmar y preguntas para Cristian

1. **DECISIÓN SIN CONFIRMAR — recurso en `config/` de la raíz del paquete**, no en `autoclave/config/`: esa carpeta se siembra en disco escribible (`%ProgramData%\...\programa\`) y el secreto quedaría copiado ahí. En *onedir* igual queda como archivo plano en `_internal\config\` (riesgo de §1, hasta L1).
2. **DECISIÓN SIN CONFIRMAR — generador sin secretos:** como el ejecutable no tiene consola, el servidor arranca pero solo muestra la página con el motivo (503); el generador no genera nada. `/salud` responde `sin_secretos: true`.
3. **DECISIÓN SIN CONFIRMAR — archivo mal formado** (versión ≠ 1, longitud, no hexadecimal, o los dos secretos iguales) = sin secretos: falla cerrada en el autoclave y detiene la compilación.
4. **DECISIÓN SIN CONFIRMAR — SIS-07 detecta «conserva la semilla» por hash idéntico** (nunca cambiada). Si alguien la cambia y luego vuelve a poner la de fábrica (nueva sal), no se detecta; para cerrarlo, `/auth/change_password` y el restablecimiento también deberían rechazar la semilla (fuera de este alcance). ¿Se agrega?
5. **DECISIÓN SIN CONFIRMAR — quién ve SIS-07:** técnico e ingeniero, según la instrucción; **Admin no** lo ve (y es una de las dos cuentas afectadas). Sin sesión no se ve. El historial de alarmas sí lo registra. ¿Admin también?
6. **DECISIÓN SIN CONFIRMAR — orden contraseñas → perfil.** Si las contraseñas se guardan y luego falla la escritura del perfil, quedan fijadas y auditadas aunque el asistente no termine; al reintentar se vuelven a fijar.
7. **DECISIÓN SIN CONFIRMAR — el asistente escribe la base directamente** (corre sin backend). Con la marca BD_BLOQUEADA o una base sin exactamente una cuenta del sistema por rol, la instalación no termina y muestra el error.
8. La verificación de la semilla usa PBKDF2 (4 verificaciones): al pulsar «Siguiente» en el paso Contraseñas la pantalla queda ocupada un momento (medido en el PC de desarrollo, con la suite corriendo: 1.5 s para las dos contraseñas; luego se suma el hash de las dos al instalar). **[verificar en sitio]** en el PC del equipo.
9. El simulador (`src/autoclave/simulador/autenticacion_simulada.py`, no va en el ejecutable), el LEEME (sección 5) y pruebas/informes antiguos siguen diciendo las contraseñas semilla: son públicas igual y solo se pidió limpiar `db_manager.py`. ¿Se limpian también?
10. **LIC-03:** ¿`parametros_software.accdb` debe seguir en el repositorio? No tiene credenciales, pero es conocimiento de proceso.
11. **LIC-04:** la clave de fábrica se genera y se registra, pero el autoclave no la pide nunca. ¿Se retira del generador, o se define para qué sirve (DL-21 dice que la emite cualquier técnico)?

---

## 7. Pasos para Cristian

1. Ejecutar `python tools\secretos\generar_secretos.py` (desde la raíz del repositorio). Anotar las dos huellas que imprime.
2. Guardar una copia del archivo `%USERPROFILE%\Documents\especifika_secretos\activacion.json` fuera del PC (USB que no quede conectada) hasta que exista la custodia definitiva.
3. Comprobar que la huella del generador coincide con la de la compilación: al compilar `Autoclave.spec` se imprime «LIC-01: secretos de activación … (huella instalación XXXXXXXX, …)»; en el generador, la página **Usuarios** muestra «Huella del secreto de instalación».
4. La siguiente compilación del autoclave y la del generador deben usar ese mismo archivo. **Los códigos del generador anterior dejan de servir**, y sin el archivo ni el autoclave se compila ni el generador arranca.

---

## Cierre

**Suite** (`pytest tests -n auto`, 24-oct ~23:10): 7586 passed, 10 skipped, 3 xfailed, 7 failed en 6 min 30 s. Los 7 fallos repetidos en serie: 5 pasan (`test_ciclos_print` ×2, `test_main_window_navigate_payload`, `test_calibracion_sensor_view`, `test_home_view`: las rojas intermitentes en paralelo de siempre). Quedan **2 rojas ajenas**: `test_config_correo.py::test_carga_el_archivo_del_repo` y `::test_descarta_destinos_invalidos`. Dependen de `data/correo_equipo.json` del PC de desarrollo (sin versionar, creado hoy 17:59): con `RUTA_EQUIPO` apuntando a un archivo inexistente pasan las 14 del módulo, y fallan igual con el código de la tanda 12, porque el paquete `autoclave` instalado apunta a este repositorio. No se tocó `data/`.

**Por qué la primera corrida se colgó:** `pytest -n auto` sin ruta, desde la raíz, recorre también `_suites_t11/` (worktree de la tanda 11, sin versionar, dentro del repositorio) y la recolección no termina. Con `pytest tests` recolecta 7605 pruebas en 7 s. Recomendación: agregar `testpaths = ["tests"]` en `pyproject.toml` o sacar `_suites_t11/` del repositorio (no se hizo: fuera de alcance).

**Pruebas que se ajustaron además de las de §5** (al recorrer la suite): `tests/m1_asistente_banco.py` y `tests/test_m1_asistente_qml.py` (el asistente tiene 9 pasos; recorrido con el paso Contraseñas y una base falsa; prueba nueva de que sin contraseñas no se pasa al resumen), `tests/test_status_endpoint_alarms.py` (`roles_visibles` en el DTO), y el mensaje de error del guardado de contraseñas pasó al catálogo i18n (`instalacion.error_guardar_contrasenas`) por `test_v8b_textos`.

Unión a `dev` con `--no-ff` y push de `dev` y `licencia-l0`: ver el registro de git.
