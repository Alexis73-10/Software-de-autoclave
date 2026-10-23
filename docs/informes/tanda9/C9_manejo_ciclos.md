# C9 — Manejo de ciclos en Opciones avanzadas (tanda 9, D9-10)

Rama `tanda-9-c9` (worktree `agent-a3bb314591f7dfc9e`, desde `tanda-9` c7b8744). Sin push. Etapa no ★: no se lanzaron revisores (la regla 9 solo los pide en etapas ★).

## Qué se hizo (D9-10 y Q2)

| Punto de D9-10 | Estado | Dónde |
|---|---|---|
| Sección nueva «Manejo de ciclos» en Opciones avanzadas | Hecho. Opciones avanzadas es ahora un contenedor con dos partes: Manejo de ciclos y Reasignación de entradas y salidas | `Pantallas/OpcionesAvanzadas.qml`, `Pantallas/OpcionesManejoCiclos.qml`, `controllers/manejo_ciclos_controller.py` |
| Visible para técnico e ingeniero; la reasignación de E/S sigue solo para el ingeniero | Hecho. `opciones_avanzadas` pasa a `_TECNICOS`. Funciones nuevas `puede_reasignar_io` (solo ingeniero) y `puede_manejar_ciclos` (técnico e ingeniero). El técnico no ve el selector y el `Loader` de la reasignación no se activa para él. El backend de la reasignación no cambió: sigue con `requiere_rol(ingeniero)` | `domain/permisos_opciones.py`, `OpcionesController.puedeReasignarIo` |
| Crear = duplicar un programa existente con nombre nuevo (Q2) | Hecho. «Crear programa» abre una ventana para elegir el programa base y luego pide el nombre. Llama a `POST /programas/{base}/duplicar` con `{"nombre", "crear": true}`. `crear` es opcional (`StrictBool`, por defecto `false`) y solo cambia el evento de la bitácora a `programa_creado` | `server.py::_DuplicarBody` |
| Duplicar, habilitar/deshabilitar, borrar | Hecho, con los endpoints existentes: `/duplicar`, `PUT /habilitado` y `DELETE`. Cada tarjeta de programa muestra Duplicar, Habilitar o Deshabilitar y, solo en los personalizados, Borrar (con confirmación) | `OpcionesManejoCiclos.qml` |
| Nunca borrar los de fábrica | Hecho en dos capas. La interfaz no muestra Borrar en los programas no personalizados. El backend ya respondía 422 `programa_de_fabrica`, y hay una prueba nueva para técnico e ingeniero | `gestion_programas.borrar` (sin cambios) |
| Solo fuera de ciclo | Hecho. Se retira la excepción del ingeniero en los tres endpoints (`_gestion(..., excepcion_ingeniero=False)`): ahora responden 409 en CICLO a todos los roles. La interfaz deshabilita todo y muestra un aviso en CICLO, también al ingeniero (`motivo_manejo_ciclos`). Las entradas mostradas (`PUT /cycle/display-inputs`, que sigue en Parámetros del ciclo) conservan la excepción, y hay una prueba que lo fija | `server.py::_gestion` |
| Bitácora: crear, borrar, habilitar/deshabilitar | Ya se registraban `programa_duplicado`, `programa_habilitado` y `programa_borrado`, con reversión si la bitácora falla (O1, SAF-01). Se agregaron: el evento `programa_creado`; los textos `bitacora.ev.*` y `bitacora.tipo.*` en es y en (antes salían con el texto genérico); y un texto propio para deshabilitar, para no mostrar `True`/`False` | `core/runtime/bitacora.py`, i18n |
| Retirar los botones de Parámetros del ciclo | Hecho. Se quitaron el título «Gestión del programa», los tres botones y el diálogo de borrar. En su lugar hay una línea que indica dónde está ahora la función (`opciones.gestion_movida`). Se mantiene el aviso «Programa deshabilitado». Se quitaron del controlador los slots `fijarHabilitado`, `duplicar` y `borrar`. No se tocó nada más de Parámetros del ciclo (P9 trabaja en Finalización) | `OpcionesParametrosCiclo.qml`, `parametros_ciclo_controller.py` |
| Textos es/en | Hecho. Bloque nuevo `manejo_ciclos.*`, `opciones.gestion_movida` y los textos de la bitácora | `i18n/es.json`, `i18n/en.json` |
| Pruebas backend y QML | Hecho (ver «Pruebas») | |
| Capturas es y en | Hecho: 16 en `docs/informes/tanda9/capturas/c9/` (8 por idioma) | ver abajo |

Historial de Opciones (N8): `opciones_avanzadas` se sumó a `_cargadorDe()`, como pedía el informe N8. Así la parte elegida (`segmento`, que ya está en `_propiedadesSubnivel`) se conserva al volver con Atrás.

## Commits

| Commit | Contenido |
|---|---|
| 9c56291 | Backend: gestión solo fuera de ciclo, `crear` → `programa_creado`, textos de bitácora (es/en), pruebas API |
| cbc2c53 | Permisos, controlador y pantallas (Opciones avanzadas, Manejo de ciclos), retiro de los botones de Parámetros del ciclo, pruebas actualizadas |
| 7a1db5b | Capturas es/en |
| (este) | Informe |

## Pruebas

Todas con `PYTHONPATH=<worktree>/src`. `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a3bb314591f7dfc9e\src\autoclave\__init__.py`.

**Pruebas nuevas:**
- `tests/test_c9_manejo_ciclos_api.py` (backend). Cubre:
  - `crear` registra `programa_creado` y duplicar sigue registrando `programa_duplicado`;
  - `crear` solo acepta un booleano (422);
  - en CICLO, el técnico y el ingeniero reciben 409 en crear, habilitar y borrar, y nada cambia;
  - el técnico opera en PREPARACION, PREPARADO y FALLA;
  - nunca se borra un programa de fábrica;
  - las entradas mostradas conservan la excepción del ingeniero;
  - los textos de la bitácora existen en es y en, y deshabilitar tiene texto propio.
- `tests/test_c9_manejo_ciclos_ui.py` (controlador). Cubre:
  - la lista, sin los programas de `cycles/factory`;
  - crear con la marca `crear`;
  - duplicar, habilitar y borrar;
  - un nombre vacío no llega al backend;
  - 11 códigos de rechazo, cada uno con su mensaje, y la lista se relee siempre;
  - sin respuesta del backend;
  - el catálogo es/en completo;
  - los botones ya no están en Parámetros del ciclo;
  - el cableado en `Opciones.qml`.
- `tests/test_c9_manejo_ciclos_banco_qml.py` (banco QML en es y en). Cubre:
  - el técnico ve solo Manejo de ciclos, crea y borra;
  - el técnico y el ingeniero en CICLO tienen todo deshabilitado y no se envía nada;
  - el ingeniero cambia a la reasignación.

  Con `C9_CAPTURAS=1` genera las capturas.

**Pruebas actualizadas** (por la nueva política):
- `test_permisos_opciones.py`: el técnico ve Opciones avanzadas. Casos nuevos de `puede_reasignar_io`, `puede_manejar_ciclos` y `motivo_manejo_ciclos`.
- `test_opciones_controller.py` y `test_opciones_qml.py`: el técnico ve Opciones avanzadas.
- `test_o1_gestion_programas.py`: el ingeniero ya no duplica en CICLO (409).
- `test_o1_parametros_ciclo_ui.py`: sin botones de gestión.
- `test_r8_reasignacion_ui.py`: la reasignación está dentro del contenedor y solo se activa para el ingeniero.
- `test_r8_reasignacion_banco_qml.py`: elige la parte de reasignación antes del recorrido.

**Resultados exactos:**
- Corrida 1, módulos tocados y los que los importan (capturas activas): **310 passed in 112.92s**. Incluye `test_c9_manejo_ciclos_banco_qml.py`, `test_c9_manejo_ciclos_ui.py`, `test_c9_manejo_ciclos_api.py`, `test_o1_gestion_programas.py`, `test_o1_parametros_ciclo_ui.py`, `test_r8_reasignacion_ui.py`, `test_r8_reasignacion_banco_qml.py`, `test_permisos_opciones.py`, `test_opciones_controller.py`, `test_c1b_admin_parametros_equipo.py`, `test_opciones_qml.py`, `test_o2e_bitacora.py`, `test_i18n.py` y `test_i18n_linea_base.py`.
- Corrida 2, pruebas QML que cargan `Opciones.qml`: **89 passed in 63.05s**. Incluye `test_i4_ingles_qml.py`, `test_n8_historial_opciones_qml.py`, `test_t12_opciones_parametros.py`, `test_u2_navegacion_qml.py`, `test_t7_avisos_qml.py`, `test_v8a_tipo_carga_modos.py` y `test_n8_cerrar_sesion_qml.py`.
- Corrida 3, backend antes de la parte de interfaz: **197 passed**. Incluye `test_c9_manejo_ciclos_api.py`, `test_o1_gestion_programas.py`, `test_o2e_bitacora.py`, `test_i18n*.py` y `test_backend_autenticacion.py`.

**Suite completa: no corrida** (regla 8; la corre la sesión principal al unir).

## Capturas (`docs/informes/tanda9/capturas/c9/`, 1200x1920)

Hay 8 capturas por idioma, en `C9_es_*` y `C9_en_*`:
1. `1_tecnico_lista`
2. `2_crear_base`
3. `3_creado`
4. `4_borrar`
5. `5_tecnico_en_ciclo`
6. `6_ingeniero_en_ciclo`
7. `7_ingeniero_manejo`
8. `8_ingeniero_reasignacion`

El banco no tiene teclado, así que no hay captura del paso del nombre: es el teclado alfanumérico de siempre, con el título «Nombre del programa nuevo».

## DECISIONES SIN CONFIRMAR

1. **Habilitar y deshabilitar valen para todos los programas operables**, también los 4 de fábrica que están en `cycles/user`, como desde O1. «Nunca los de fábrica» se aplicó solo a borrar. D9-10 se puede leer como «solo los personalizados» para todas las acciones, pero eso dejaría sin forma de ocultar un programa estándar en Preciclo. Duplicar también admite los de fábrica: es la base para crear.
2. **«Fuera de ciclo»** significa:
   - en el backend, cualquier estado distinto de CICLO: PREPARACION, PREPARADO y FALLA permitidos, como el resto de Opciones;
   - en la interfaz, solo PREPARACION, PREPARADO y FALLA (con un estado desconocido, deshabilitado);
   - se quitó la excepción que dejaba al ingeniero gestionar programas en CICLO (O1, tanda 5).
3. **Crear y duplicar son la misma operación**, con dos entradas en la pantalla:
   - Crear elige la base en una ventana;
   - Duplicar parte de la tarjeta del programa;
   - los dos piden el nombre con el campo vacío (el backend rechaza nombres repetidos).

   En la bitácora se distinguen: `programa_creado` y `programa_duplicado`.
4. **La lista no muestra los programas de `cycles/factory`** (origen `factory`): son la referencia de fábrica, no se ofrecen en Preciclo y el backend no los gestiona.
5. **Diseño PROVISIONAL sin mockup.** Opciones avanzadas abre siempre en Manejo de ciclos. El ingeniero cambia de parte con un selector propio de dos segmentos que admite texto en dos líneas. `SelectorSegmentos` no se tocó porque es compartido. Si la reasignación tiene cambios sin guardar, cambiar de parte pide confirmación.
6. **Valores en la bitácora:** crear, duplicar y borrar muestran los campos crudos (`numero=…, cycle_id=…, nombre=…`), como otros eventos con diccionario. Deshabilitar tiene texto propio para no mostrar `True`/`False`.
7. **Textos que quedan sin uso:** las claves `opciones.gestion_titulo`, `habilitar_programa`, `deshabilitar_programa`, `duplicar_programa`, `borrar_programa`, `borrar_programa_pregunta` y `nombre_programa` ya no se usan. Se dejaron en el catálogo para no chocar al unir con P9 y se pueden borrar en una limpieza.

## PREGUNTAS PARA CRISTIAN

Ninguna sobre transiciones de ciclo, estado seguro ni puertas: esta etapa no las toca.

## Pendientes

- Nada abierto de D9-10.
- D9-13.5 (regenerar el banco de capturas al final de la tanda) debe incluir esta pantalla; el recorrido ya está en `test_c9_manejo_ciclos_banco_qml.py`.

## Puntos de choque al unir

- `src/autoclave/i18n/es.json` y `en.json`: bloque nuevo `manejo_ciclos` (antes de `reasignacion`), `opciones.gestion_movida` y 5+4 claves al final de `bitacora.ev` y `bitacora.tipo`. Se unen por claves.
- `src/autoclave/backend/server.py`: `_DuplicarBody`, `_gestion` (parámetro `excepcion_ingeniero`) y los tres endpoints de programas.
- `src/autoclave/core/runtime/bitacora.py`: `EVENTOS` y `_clave_texto` (parámetro nuevo `nuevo`).
- `src/autoclave/ui_qml/qml/Pantallas/Opciones.qml` (QML compartido):
  - la línea de `cambiosPendientes` (`avanzadas.item`);
  - el mapa de `_cargadorDe`;
  - el `Loader` de Opciones avanzadas: id `avanzadas`, objectName `cargadorOpcionesAvanzadas`.

  P9 puede tocar este archivo por el refresco de modelos.
- `src/autoclave/ui_qml/qml/Pantallas/OpcionesParametrosCiclo.qml` y `controllers/parametros_ciclo_controller.py`: solo se quitó el bloque de gestión. P9 trabaja en Finalización en los mismos archivos.
- `src/autoclave/ui_qml/domain/permisos_opciones.py`, `controllers/opciones_controller.py` y `controllers/__init__.py`.
- No se tocaron `db_manager.py` (sin migración), `control_loop.py`, `set_io.py` ni el catálogo de alarmas. **No hay códigos de alarma nuevos.**
