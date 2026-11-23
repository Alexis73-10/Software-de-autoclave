# Modo fábrica, Etapa 2: programas de fábrica y numeración

Fecha: 22-nov-2026. Rama `modo-fabrica`. Base: spec `docs/mis_plans/planeacion_modo_fabrica.md` (§5.3, D-02, D-05..D-07, FAB-09, FAB-13, P-02), revisión `R_revision_plan.md` (R-03, «Numeración», «Marca fabrica_equipo», «Defecto por número») y decisiones `decisiones.md` (DF-04, DF-06, PA-07).

## Qué se hizo

### Reglas puras (`core/managers/gestion_programas.py`)

No leen la base: el backend les pasa el estado con `modo_fabrica`.

- `numero_fabrica_libre(cm)`: primer número del 1 al 10 que no ocupa ningún programa cargado (de usuario o genérico de `factory/`, también uno que cedió su número por PRI-06/PRI-07, vía `numero_json`), ningún genérico de `cm.fabrica` ni ningún defecto. No consulta `numeros_usados.json`. Con los 10 ocupados, 409 `maximo_programas_fabrica`.
- `numero_usuario_nuevo(cm)` = `max(11, numero_nuevo(cm))` (PA-07).
- `duplicar(cm, numero, nombre, *, modo_fabrica=False)`:
  - en FÁBRICA, número libre del 1 al 10, `"fabrica_equipo": true`, sin `personalizado`, sin registrar el número en `numeros_usados.json`;
  - en ENTREGADO, número `max(11, …)`, `personalizado`, sin `fabrica_equipo` (también al duplicar un programa del equipo), y el número se registra como antes;
  - el defecto en `cycles/defecto/` se escribe igual que antes, en los dos estados.
- `borrar_fabrica(cm, cycle_id, activo_id)`, con `confirmar_borrado` y `deshacer_borrado_fabrica`:
  - acepta un programa no personalizado: genérico sembrado en `cycles/user`, del equipo, o genérico cargado de `factory/` sin copia de usuario;
  - rechaza un personalizado (422 `no_es_programa_de_fabrica`), el seleccionado (409 `programa_activo`) y uno inexistente (404);
  - primero escribe las listas (`fabrica_borrados.lst` y `fabrica_vistos.lst`), luego aparta el JSON, su `.bak` y sus defectos (buscados por `cycle_number` o `cycle_id`, no por el nombre del archivo) con el sufijo `.borrado`; los elimina tras auditar;
  - no registra el número en `numeros_usados.json`;
  - si la auditoría falla, restaura los archivos, las dos listas (o las quita si no existían), `cm.cycles`, `cm.defectos` y `cm.fabrica`;
  - un error de escritura da 503 `error_archivo` sin cambiar nada.

### Carga y siembra

- `utils/resources.py`: `MARCA_FABRICA_BORRADOS = "fabrica_borrados.lst"`, `leer_lista_ids`, `escribir_lista_ids` (atómica, ordenada, un id por línea; `fabrica_vistos.lst` la usa ahora también) y `fabrica_borrados()`. `sembrar_faltantes_usuario` no siembra un id de la lista.
- `cycle_manager._load_from_folder`: con `source == "factory"` salta los ids de `fabrica_borrados.lst`, incluidos los 5 heredados (R-03). Marca `cycle.fabrica_equipo` (solo en `cycles/user`) y `cycle.numero_json`. `Cycle.copia()` conserva `fabrica_equipo`.
- Sin el archivo, la carga no cambia.

### Backend (`backend/rutas/programas.py`)

- `POST /programas/{n}/duplicar`: en FÁBRICA (`_equipo_en_modo_fabrica()`), solo ingeniero (403 `rol_sin_permiso` para el técnico) y `modo_fabrica=True`; la auditoría agrega `fabrica_equipo: true` al valor nuevo.
- **Ruta nueva** `DELETE /fabrica/programas/{cycle_id}` con `requiere_modo_fabrica()`:
  - en ENTREGADO, 409 `solo_modo_fabrica` para todos;
  - en FÁBRICA, ingeniero, fuera de ciclo (`excepcion_ingeniero=False`) y bajo el mismo `_gestion` que el borrado normal;
  - respuesta `{"ok", "cycle_id", "numero"}`.
- `GET /programas`: campo nuevo `fabrica_equipo` (bool); los demás campos no cambian. `editable` sigue siendo `source == "user"`, así que un programa del equipo es editable.
- El borrado normal (`DELETE /programas/{n}`) sigue exigiendo `personalizado`: un programa del equipo da 422 `programa_de_fabrica` en los dos estados.
- Bitácora: evento `programa_fabrica_borrado` (categoría configuración, `valor_anterior` = id, número y nombre), con textos `bitacora.ev`/`bitacora.tipo` en es y en.
- Base de la tanda 15: la ruta se insertó en `rutas.json` tras `DELETE /programas/{numero}` y `openapi.json` se regeneró con `openapi_ordenado` (solo ese path). Anotado en el docstring de `test_t15_rutas_equivalentes.py`.

### Cliente y pantalla

- `ui_qml/sesion_backend.py`: `solo_modo_fabrica` global (`fabrica.err_solo_modo_fabrica`); `maximo_programas_fabrica` en `/programas`; tabla nueva `_CODIGOS_FABRICA_PROGRAMAS` para `/fabrica/programas`.
- `ManejoCiclosController`: filas con `fabrica_equipo` y `borrableFabrica` (no personalizado); slot `borrarFabrica(numero)` (operación crítica, por `cycle_id`); textos para `maximo_programas_fabrica`, `solo_modo_fabrica`, `no_es_programa_de_fabrica` y `error_archivo`.
- `OpcionesManejoCiclos.qml`: propiedad `borrarFabrica`, botón `botonBorrarFabrica_N` «Borrar (modo fábrica)» y diálogo `dialogoBorrarFabricaManejo` (el mismo `DialogoConfirmacion` de la pantalla). El estado del programa dice «De fábrica del equipo». `Opciones.qml` la calcula como `control.puedeReasignarIo && puente.modoFabrica === true` (ingeniero y FÁBRICA) y la pasa por `OpcionesAvanzadas.qml`. En ENTREGADO, o para el técnico, no se muestra. Sin colores nuevos ni `elide`.
- `.gitignore`: `src/autoclave/cycles/user/fabrica_borrados.lst`.

## Archivos

- Código: `core/managers/gestion_programas.py`, `core/managers/cycle_manager.py`, `utils/resources.py`, `backend/rutas/programas.py`, `core/runtime/bitacora.py`, `i18n/es.json`, `i18n/en.json`, `ui_qml/sesion_backend.py`, `ui_qml/controllers/manejo_ciclos_controller.py`, `ui_qml/qml/Pantallas/OpcionesManejoCiclos.qml`, `OpcionesAvanzadas.qml`, `Opciones.qml`, `.gitignore`.
- Base de rutas: `docs/informes/tanda15/base/rutas.json` y `openapi.json`.
- Pruebas nuevas: `tests/test_fab_e2_programas.py` (18: P-02, R-03, actualización simulada, `numeros_usados.json` sin cambios, defecto por número, deshacer, ENTREGADO con 11, rutas en los dos estados, auditoría fallida) y `tests/test_fab_e2_ui.py` (15: códigos, textos, controlador y pantalla offscreen en FÁBRICA/ENTREGADO, ingeniero/técnico).
- Pruebas modificadas:
  - `test_t15_rutas_equivalentes.py`: solo el docstring, que documenta el cambio de la base;
  - `test_t25_codigos_rutas_async.py`: se agrega `maximo_programas_fabrica` en `/programas` y la ruta `/fabrica/programas`, que es la tabla que fija el test, no se relaja;
  - `tests/banco/opciones_qml_banco.py`: parámetro opcional `modo_fabrica` para el puente falso.

## Pruebas

- Nuevas: 33 en verde.
- Subconjunto relacionado (programas, gestión, siembra, Prion, C9, F4/F6, T17, T22, T24, T25, U10b, V8b, i18n, rutas de la tanda 15, arquitectura de capas): en verde, salvo los fallos preexistentes de la base.
- Suite completa: ver la sección siguiente.

Suite completa (`python -m pytest tests -q -p no:cacheprovider -n auto`): 20 fallos, 12851 en verde, 11 omitidas, 15 xfail y 6 errores. Es exactamente la lista de `suite_base.txt` (20 fallos y 6 errores preexistentes): ningún fallo nuevo y ninguno desaparecido. La suite reescribió `src/autoclave/cycles/user/*.json`, que se descartó con `git checkout` antes de commitear.

En corridas parciales en paralelo aparecieron dos intermitentes ajenos al cambio, que pasan aislados: `test_t17_s3_bitacora::test_evento_sin_clasificar_cae_en_sistema` y un timeout de `test_rep_calendario_qml::test_sin_programas`. Los fallos de `test_t29_descompresion_fin_modo_solido[user/*]` en corridas parciales también aparecen sin este cambio (los JSON de usuario del repo sin migrar).

## Decisiones tomadas en esta etapa (todas `DECISIÓN SIN CONFIRMAR`)

- **E2-D1. El id de un programa borrado no se reutiliza.** En FÁBRICA un número sí se reutiliza: si `programa_N` ya está en `fabrica_borrados.lst`, el programa nuevo se llama `programa_N_2` (y así), para que la bitácora y la «última modificación» no mezclen dos programas.
- **E2-D2. «Programa de fábrica» para el borrado de fábrica = todo programa no personalizado**: genérico sembrado, del equipo o genérico de `factory/` sin copia de usuario (este último solo se anota en las listas, porque `factory/` es del paquete). Los personalizados se borran por la ruta normal.
- **E2-D3. Las listas se escriben antes de apartar los archivos.** Si el proceso se corta a mitad, el programa no reaparece desde `factory/` ni por la siembra; en el peor caso queda un `.borrado` sin eliminar.
- **E2-D4. En FÁBRICA, el técnico recibe 403 `rol_sin_permiso` al crear o duplicar.** La pantalla no le oculta «Crear» ni «Duplicar»; el backend es la autoridad y el texto es el de rol.
- **E2-D5. Los defectos se buscan por `cycle_number` o por `cycle_id`.**
- **E2-D6. Duplicar en FÁBRICA escribe el defecto en `cycles/defecto/` como antes** (valores del origen al duplicar). La base de fábrica del equipo es de la Etapa 3.
- **E2-D7. El número libre cuenta** el número del JSON de un genérico que lo cedió (PRI-06/PRI-07) y los números de los defectos.
- **E2-D8. En ENTREGADO, duplicar un programa del equipo da un personalizado sin la marca.**
- **E2-D9. `fabrica_borrados.lst` ilegible:** el cargador y la siembra lo ignoran con aviso (comportamiento anterior a la lista); `borrar_fabrica` responde 503 `error_archivo` sin cambiar nada.
- **E2-D10. Se usó `DialogoConfirmacion`**, el mismo de la pantalla para el borrado normal, en lugar de `ModalConfirmacion`.

## Observaciones

- El texto `manejo_ciclos.explicacion` sigue diciendo «Los programas de fábrica no se borran». Es cierto en ENTREGADO; en FÁBRICA el botón propio lo contradice. No se cambió (pendiente de Cristian).
- El respaldo USB lleva solo `programas/*.json` de `cycles/user`, sin `fabrica_vistos.lst` ni `fabrica_borrados.lst`. Restaurar un respaldo en un equipo con programas borrados en FÁBRICA no los recrea (las listas siguen en el equipo), pero en un equipo nuevo sí lo haría. Revisar en la Etapa 4/5 si el paquete y el cierre deben llevar las listas.
- La limpieza del 1 al 10 en `numeros_usados.json` (DF-10) es del cierre (Etapa 5); aquí no se toca.
- No se tocaron `docs/riesgos` ni `CLAUDE.md` (Etapa 6).
