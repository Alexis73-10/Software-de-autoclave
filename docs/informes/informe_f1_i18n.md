# Informe F1 — Infraestructura de idiomas (i18n)

Plan: `docs/mis_plans/planeacion_i18n.md` (v3), instrucción `docs/mis_plans/instruccion_claude_code_f1_i18n.md`.
Fecha: 14/10/2026. Rama `dev` (HEAD `2fcd5ab`). **Sin commit**: todo queda en el árbol de trabajo hasta la verificación visual de Cristian.

## 1. `git status` inicial

Cambios locales previos a F1 (ajenos a esta tarea, de otras sesiones):

- Modificados: `docs/catalogo_alarmas.md`, `backend/context.py`, `backend/server.py`, `devices/factory/factory.py`, `installation/profile.py`, `installation/storage.py`, `protocols/serial_link.py`, `services/domain/loop/control_loop.py`, `state_machine/states/ciclo.py`, `ui_qml/assets/textos/es.json` (+100 líneas: sección `instalacion`), `ui_qml/bridge/info_equipo.py`, `ui_qml/qml/Componentes/PanelEquipo.qml`, `tests/serial_doble.py`, `tests/test_arranque_sin_tarjeta.py`, `tests/test_info_equipo.py`, `tests/test_secuencia_arranque.py`, `tests/test_serial_link_v2_lector.py`.
- Sin seguimiento: `.claude/`, `Hardware/Comunicacion_esclava_ESP32_V3/`, varios documentos en `docs/` (alarmas, fin de ciclo, firmware 1.5, menú de instalación, E6), `docs/mockups/instalacion/`, `src/autoclave/images/icono autoclave.jpg`, el asistente de instalación QML (`ui_qml/prueba_instalacion.py`, `Pantallas/Instalacion.qml`, `Pruebas/PruebaInstalacion.qml` y 6 componentes nuevos), `tests/test_e6_*.py` (3) y `tools/emparejar_tarjeta.py`.

`backend/server.py` y `protocols/serial_link.py` no se tocaron.

## 2. Archivos

**Creados**
- `src/autoclave/i18n/__init__.py` — módulo de idiomas.
- `src/autoclave/i18n/en.json` — borrador en inglés.
- `src/autoclave/ui_qml/bridge/i18n_qml.py` — singleton QML `I18n`.
- `tests/test_i18n_linea_base.py` — línea base (paso 1) y equivalencia exhaustiva con las funciones viejas.
- `tests/test_i18n.py` — paridad, referencias, familias dinámicas, respaldo y binding.
- `tools/claves_sin_uso_i18n.py` — listado de claves sin uso (D-19).
- `docs/mis_plans/revision_traducciones.md` — registro de revisión (§6).
- `docs/mis_plans/claves_sin_uso_i18n.md` — resultado del script.
- Este informe.

**Movido** (con `git mv`; el renombre queda en el índice, sin commit)
- `src/autoclave/ui_qml/assets/textos/es.json` → `src/autoclave/i18n/es.json`. Contenido idéntico byte a byte (SHA-256 `95f9a193…04a6`), **incluidas las 100 líneas sin commit de la sección `instalacion`** de la otra sesión. La carpeta `assets/textos/` quedó vacía y se eliminó.

**Modificados — Python**
- `ui_qml/app.py`: se eliminan `TEXTOS_ES` y `cargar_textos()`; `main()` llama a `i18n.cargar()` antes de crear la app (sin catálogos no arranca); importa `bridge/i18n_qml` (registra el singleton); ya no pasa `textosJson`.
- `ui_qml/bridge/acciones_ciclos.py`: sin `_tx` ni parámetro `textos`; usa `i18n.t(...)`, y `i18n.catalogo()` / `i18n.valor("reportes")` donde los PDF reciben el diccionario entero.
- `ui_pyside/views/nuevo_usuario/vista.py`, `ui_qml/prueba_ciclo_en_curso.py`, `prueba_menu_principal.py`, `prueba_teclado_numerico.py`, `prueba_instalacion.py` (sin seguimiento): ya no cargan ni pasan `textosJson`.
- `ui_qml/bridge/progreso_arranque.py`: solo un comentario (ruta del catálogo).

**Modificados — QML (31 archivos)**
- Producción: `Main.qml`, `NuevoUsuarioHost.qml`, `Componentes/` `BarraFases`, `DetalleCiclo`, `EncabezadoMenu`, `GraficaCiclo`, `ListaCiclos`, `PanelEquipo` (ya tenía cambios locales), `PanelTeclado`, `ResumenPeriodo`, `SelectorDestino`, `SelectorPeriodo`, `TecladoAlfanumerico`, `TecladoNumerico`; `Pantallas/` `CambioClave`, `Instalacion` (sin seguimiento), `IntroArranque`, `Login`, `MenuPrincipal`, `NuevoUsuario`, `Opciones`, `PantallaCicloEnCurso`, `PantallaPreciclo`, `Reposo`.
- Pruebas: `Pruebas/` `GaleriaMenuPrincipal`, `PruebaCicloEnCurso`, `PruebaCicloEnCursoBackend`, `PruebaInstalacion` (sin seguimiento), `PruebaMenuPrincipal`, `PruebaTecladoAlfanumerico`, `PruebaTecladoNumerico`.

**Modificados — pruebas existentes (21)**: `test_acciones_ciclos_puente`, `test_cancelacion_ciclo_en_curso_qml`, `test_e6_emparejamiento_tarjeta` (sin seguimiento), `test_intro_arranque_qml`, `test_login_qml_autenticacion`, `test_main_menu_principal_qml`, `test_menu_principal_componentes_qml`, `test_menu_principal_pantalla_qml`, `test_navegacion_ciclo_en_curso`, `test_navegacion_sesion_qml`, `test_opciones_qml`, `test_panel_teclado_login`, `test_pantalla_ciclo_en_curso_qml`, `test_pdf_consolidado`, `test_pdf_resumen`, `test_progreso_arranque`, `test_reconocer_falla`, `test_teclado_alfanumerico_qml`, `test_teclado_numerico_qml`, `test_ui_qml_app`. Cambios: ruta nueva de `es.json`, sin `textosJson`/`cargar_textos`, registro del singleton en los scripts de subproceso, y las expresiones regulares que buscaban `tx("sec", "clave")` ahora buscan `I18n.t("sec.clave", I18n.lang`.

**Módulos fuera de alcance que leían `es.json`:** ninguno. Las vistas PySide de configuración y la UI tkinter no lo leen; la única vista PySide que lo usaba es `nuevo_usuario/vista.py` (dentro del alcance, D-02).

## 3. Diferencias entre las copias de `tx()`

Accesos al catálogo con lógica propia que había antes de F1 (un archivo puede tener varios):

| Variante | Dónde | Comportamiento |
|---|---|---|
| `tx(seccion, clave)` | 15 archivos (DetalleCiclo, GraficaCiclo, ListaCiclos, SelectorDestino, SelectorPeriodo, CambioClave, Instalacion, Login, MenuPrincipal, NuevoUsuario, Opciones, PantallaCicloEnCurso, PantallaPreciclo, PruebaTecladoAlfanumerico, PruebaTecladoNumerico) | Idénticas. Devuelve `""` si falta. Devuelve el valor tal cual, aunque sea lista u objeto |
| `_tx(seccion, clave)` | TecladoAlfanumerico, TecladoNumerico | Igual a `tx` |
| `txRuta(ruta, valores)` | Login, CambioClave, NuevoUsuario (vía `tx`) y Main (búsqueda en línea) | Equivalentes. Parten en el **primer** punto (un tercer nivel como `opciones.secciones.x` no se resolvía) y reemplazan solo la **primera** aparición de cada `{marcador}`, convirtiendo el valor con `String()` de JS |
| `tx(clave)` | ResumenPeriodo | Sección fija `reportes` |
| `_tx(clave)` | IntroArranque | Sección fija `arranque`; solo devuelve texto (`typeof === "string"`) |
| `ti(clave, valores)` | Instalacion | Sección fija `instalacion` + marcadores, como `txRuta` |
| `nombre(clave)` / `_nombreFase(clave)` | BarraFases, GraficaCiclo | Lectura directa de `textosJson.fases`; `""` si falta |
| `nombreSeccion(clave)` | Opciones | Lectura directa de `opciones.secciones`; si falta, **la clave**; cambia `\n` por espacio |
| `textosEquipo[clave] ?? clave` | PanelEquipo (sección pasada por MenuPrincipal, Preciclo y CicloEnCurso) | Si falta, **la clave** |
| `textosJson.fecha.meses` | EncabezadoMenu, PantallaPreciclo, PantallaCicloEnCurso, Reposo | Lista o `[]` |
| `AccionesCiclos._tx` (Python) | bridge/acciones_ciclos.py | Si falta, la **clave corta** (sin sección); marcadores con `str.format` |

Ningún texto de `es.json` repite un marcador ni usa `{{ }}`, así que "reemplazar solo la primera aparición" y `format` dan lo mismo que el reemplazo completo del módulo nuevo. Lo comprueba `test_i18n_linea_base.py` con cada clave.

## 4. API final

**Python — `autoclave.i18n`** (`src/autoclave/i18n/__init__.py`)
- `IDIOMAS = ("es", "en")`, `IDIOMA_BASE = "es"`.
- `cargar()`: carga o recarga los dos catálogos; `FileNotFoundError` si falta alguno. Si no se llama antes, se carga solo en el primer uso.
- `t(clave, idioma=None, **params) -> str`: texto de `clave` en `idioma` (o el vigente) con `{marcador}` sustituido. Respaldo R-05: falta en `en` → español + aviso; falta en ambos → la clave + aviso; una sola advertencia por (clave, idioma); nunca `""` (salvo con clave vacía).
- `traducir(clave, idioma, params: dict, a_texto=str)`: como `t`, con los parámetros en un dict y la conversión de valores elegible (la usa el singleton).
- `valor(clave, idioma=None)`: valor crudo (texto, lista u objeto) con respaldo al español; `None` con aviso si no existe.
- `existe(clave, idioma=None) -> bool`: hay texto en el idioma o en español; no avisa.
- `catalogo(idioma=None) -> dict`: copia profunda del catálogo completo (para los PDF).
- `idioma()`, `fijar_idioma(idioma)` (`ValueError` si no es `es`/`en`) y `al_cambiar_idioma(oyente)`. En F1 el idioma vigente es estado del módulo; no se lee ni se guarda en BD.

**QML — singleton `I18n`, módulo `Autoclave.I18n` 1.0** (`ui_qml/bridge/i18n_qml.py`)
- Nombre elegido coherente con `Autoclave.Controllers`; se registra al importar el módulo (lo importa `ui_qml/app.py`). Uso: `import Autoclave.I18n`.
- `lang` (propiedad de solo lectura con señal `langChanged`, conectada a `al_cambiar_idioma`).
- `t(clave, lang)` y `t(clave, lang, params)`: `params` es un objeto JS opcional; los números se convierten como `String()` de JS (`5.0` → `"5"`, `true` → `"true"`).
- `valor(clave, lang)`: listas y objetos (`fecha.meses`).
- `existe(clave, lang)`: para los respaldos propios de cada pantalla.
- Patrón usado en todo el QML: `I18n.t("seccion.clave", I18n.lang)`.
- Una sola instancia compartida por todos los motores QML del proceso (las pruebas crean varios), con propiedad C++, para que ningún motor la destruya al cerrarse.

## 5. Resultado de las pruebas

| Prueba | Resultado |
|---|---|
| Línea base (paso 1), contra el código anterior y antes de migrar | 2/2 pasan |
| Equivalencia: las 408 claves de texto, cada una con parámetros enteros, reales y de texto, `I18n.t` igual a `txRuta`/`tx` viejas; listas y objetos iguales; sin avisos QML | Pasa |
| Python: `i18n.t` igual a `AccionesCiclos._tx` viejo en todas las claves de dos niveles | Pasa |
| Paridad es/en: mismas claves, estructura (listas de igual longitud, objetos con iguales claves) y marcadores; ningún texto vacío | Pasa |
| Claves literales en QML (todos los `.qml`) y en Python de alcance D-02 existen en `es` y `en` | Pasa (más de 150 en QML y más de 40 en Python) |
| Familias dinámicas: 21 prefijos enumerados desde el código; todos los sufijos existen en ambos idiomas; ningún prefijo del código queda sin enumerar | Pasa |
| Respaldo: falta en `en` → español + 1 aviso; falta en ambos → clave + 1 aviso por idioma; nunca vacío; `catalogo()` es copia; `cargar()` falla sin archivo | Pasa |
| Binding QML (offscreen): `I18n.t(..., I18n.lang)`, con parámetro, y `I18n.valor("fecha.meses", I18n.lang)` cambian a inglés y vuelven a español sin recargar; sin avisos | Pasa |
| Suite completa antes de F1 | 2765 pasan, 0 fallan |
| Suite completa después de F1 | **2808 pasan, 0 fallan** (las 2765 anteriores más 43 nuevas de i18n) |

## 6. Claves dinámicas que no se pudieron enumerar del todo

- **`arranque.*` del backend real:** la prueba enumera las etapas de `ETAPAS_EJEMPLO` (simulador que usa hoy la UI). Las de `backend/arranque/registro.py` no tienen texto (ver I18N-27).
- **`estados.*` del estado de máquina:** se enumera llamando a `estado_equipo()` con una lista fija de estados (`CICLO`, `FALLA`, `PREPARADO`, `PREPARACION`, vacío); la función solo tiene 4 salidas posibles.
- **Claves que llegan completas desde Python** (`sesion.mensajeClave`, errores `{clave, valores}` de validación y de usuarios): se cubren con el escaneo de literales del Python de alcance más la familia `f"validacion.{codigo}"` (constantes `COD_*`). Una clave armada fuera de esos archivos no quedaría cubierta.
- **Lecturas por nombre corto en los PDF** (`exportacion/textos.py`, `pdf_resumen.py`, `pdf_consolidado.py`, `pdf_ciclo.py`, que reciben el diccionario entero y hacen `textos.get("eje_tiempo", "")`): no las cubre la prueba de referencias (la instrucción pide `t`/`_tx`); el script de claves sin uso sí las considera. Ver I18N-32.

## 7. Traducciones dudosas

Detalle en `docs/mis_plans/revision_traducciones.md` (T-01 a T-14). Las principales:
- "Avisos" → *Notices* (IEC 60601-1-8 no usa *notice*); "Reconocer falla" → *Acknowledge fault*; "Fallo" como resultado → *Failed*.
- "Descompresión" → *Exhaust*; "Vacío" → *Vacuum* (la fase es prevacío); abreviaturas *Ster. Temp.*, *Ster. Time*, *Dry. Time*.
- "Realizados" → *Performed* (no *Completed*, que ya es "Completado"); "Consigna" → *Setpoint*; "Mesa/Piso" → *Tabletop/Floor-standing*; "Con bloqueo" → *With lock*.

## 8. Decisiones tomadas por ambigüedad

1. **Nombre del módulo:** `autoclave.i18n` (el propio paquete).
2. **Respaldo R-05 frente al comportamiento anterior.** Con una clave inexistente, el texto ahora es la clave (antes `""`). En los sitios donde el código contaba con `""` o con la clave como respaldo, se mantuvo exactamente el comportamiento anterior usando `I18n.existe()`: nombres de fase (BarraFases, GraficaCiclo), secciones de Opciones, filas del panel de equipo, proceso de la intro de arranque, descripción opcional de tipo de puerta/vapor en Instalación y estado de un ciclo terminado sin resultado. En los demás sitios dinámicos (p. ej. `menu.resultado_` + código desconocido, `estados.` + valor desconocido) se aplica R-05: se vería la clave y queda aviso en el log.
3. **`textosJson` eliminado por completo.** Ya ningún componente lo usa, así que se quitó la propiedad de todos los componentes, de `Main.qml`, de los arneses `prueba_*.py`, de la vista de Nuevo usuario y de las pruebas. También se eliminó `cargar_textos()` y el parámetro `textos` de `AccionesCiclos` (cambio de firma: `AccionesCiclos(backend, ...)`).
4. **Archivos de la otra sesión.** `es.json` se movió con las 100 líneas sin commit de la sección `instalacion`, y se migraron `Instalacion.qml`, `PruebaInstalacion.qml`, `prueba_instalacion.py` y la ruta de `test_e6_emparejamiento_tarjeta.py`, que no tienen seguimiento. Sin esto, el asistente de instalación habría quedado sin textos. Al hacer commit hay que decidir si estos archivos entran en el mismo commit o en el de su trabajo.
5. **Índice de git:** `git mv` dejó el renombre de `es.json` preparado en el índice (no es commit). Las 100 líneas locales siguen sin preparar sobre la ruta nueva.
6. **Escaneo de literales Python:** alcance = `ui_qml/**` + `ui_pyside/views/nuevo_usuario/{puente,vista}.py` + `ui_pyside/services/{roles,validacion_usuario}.py`.
7. **Borrador en inglés:** se ajustó "Realizados" a *Performed* antes de entregar (ver T-11).
8. **Avisos en el log del asistente de instalación:** el resumen calcula `instalacion.puerta_` + tipo y `instalacion.vapor_` + fuente aún sin selección, lo que registra un aviso por clave inexistente (una sola vez). Antes daba `""` en silencio; no es visible porque el resumen solo se muestra con la selección hecha.

## 9. Preguntas abiertas y hallazgos

| Código | Sev. | Hallazgo | Propuesta |
|---|---|---|---|
| I18N-27 | Media | Las 6 etapas reales del backend sin texto en `arranque.*`: `verificando_instalacion`, `liberando_procesos`, `cargando_configuracion`, `verificando_calibracion`, `conectando_modulos_es`, `preparando_interfaz` (`backend/arranque/registro.py`). Hoy la intro usa el simulador, pero al conectarla a `GET /arranque` el rótulo de proceso quedaría vacío | Cristian define los textos en español; se agregan a `es.json` y `en.json` |
| I18N-28 | Media (usabilidad, IEC 62366) | `sistema.modo_prueba` ("MODO PRUEBA ACTIVO — los ciclos no son válidos para carga estéril") existe en el catálogo y está marcada como alarma-seguridad, pero ninguna pantalla QML la muestra, aunque el backend tiene modo de prueba (`server.py`, `control_loop.test_mode_active`) | Revisar si la UI QML debe mostrar el aviso de modo prueba; no es de idiomas |
| I18N-29 | Alta (para la liberación) | `AutoclaveUI.spec` no empaqueta `src/autoclave/i18n/*.json`. En el ejecutable, `i18n.cargar()` lanza error y la UI no arranca. Ya estaba desactualizado (D-11) | Incluirlo en la tarea de empaquetado |
| I18N-30 | Media | El worktree `alarmas-parte-a` (sin unir) sigue con `assets/textos/es.json`, `textosJson`, `cargar_textos` y `AccionesCiclos(backend, textos)`. Al unirla habrá conflictos y pruebas rotas | Rebasar sobre F1 antes de unir |
| I18N-31 | Baja | `resource_path` depende del directorio de trabajo (`os.path.abspath("src")`); `i18n.cargar()` falla si la UI se lanza desde otra carpeta. Ya pasaba con `cargar_textos()` | Revisarlo en la tarea de empaquetado o arranque |
| I18N-32 | Media | Los generadores de PDF reciben el diccionario completo y leen con `textos.get(k, "")`: con una clave faltante en `en` saldría vacío, sin respaldo al español ni aviso (incumple R-05 en PDF) | Pasar los PDF a `i18n.t` en F4 |

Preguntas para Cristian:
1. ¿Se acepta que, en los sitios dinámicos sin respaldo propio, una clave desconocida muestre la clave en vez de `""` (R-05), o prefieres mantener `""` en alguno?
2. ¿El commit de F1 incluye también los archivos sin seguimiento del asistente de instalación que se migraron (punto 8.4)?
3. Textos en español para las 6 etapas de I18N-27.

## Verificación visual pendiente (Cristian)

Con el idioma en español, recorrer las 9 pantallas de la instrucción (arranque y espera, login y cambio de clave, Menú Principal con Historial y detalle, Preciclo, Ciclo en curso con gráfica, Opciones, Nuevo usuario, teclados, exportación a PDF y correo) y confirmar que el texto no cambió. Si todo coincide, se hace el commit.
