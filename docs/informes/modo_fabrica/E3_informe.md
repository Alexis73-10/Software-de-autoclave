# Modo fábrica, Etapa 3: base de fábrica del equipo

Fecha: 22-nov-2026. Rama `modo-fabrica`. Base: spec `docs/mis_plans/planeacion_modo_fabrica.md` (D-08, FAB-06, FAB-08, §6.2 paso 3, P-03), revisión `R_revision_plan.md` (R-05, «Restaurar parámetros», «Defecto por número») y decisiones `decisiones.md` (DF-07).

La Etapa 3 deja las piezas que usará el cierre de la Etapa 5. No implementa el cierre ni cablea las funciones de escritura a ninguna ruta.

## Qué se hizo

### Módulo nuevo `core/runtime/fabrica_equipo.py`

Es el único módulo que nombra los dos archivos. Constantes: `NOMBRE_PARAMETROS = "parametros_fabrica_equipo.json"`, `NOMBRE_CALIBRACION = "calibracion_fabrica_equipo.yaml"`, `FORMATO_CALIBRACION = 1`, `CARPETA_EN_RESPALDO = "fabrica_equipo"`, `SUFIJO_TEMPORAL_DEFECTO = ".fab_nuevo"`.

Rutas: `carpeta_datos()` = `utils/paths.app_root() / "data"` (la carpeta de `tema.json` y `ciclo_contador.json`; en el compilado, `X:\Especifika\Autoclave\datos\data`), `ruta_parametros()`, `ruta_calibracion()`.

API para el cierre (Etapa 5):

| Función | Qué hace |
|---|---|
| `escribir_parametros_fabrica_equipo(config_manager, destino=None) -> dict` | Escribe `{clave: valor vigente}` de todos los parámetros del equipo (`config_manager.describir()`, también los de solo lectura) en `destino` (por omisión `ruta_parametros()`), atómico con `utils/archivos.escribir_texto_atomico`. Devuelve lo escrito; lanza si no puede escribir. |
| `escribir_calibracion_fabrica_equipo(destino=None, origen=None, mapas=None) -> dict` | Lee la sección `user` del archivo activo (`origen`, por omisión `calibration_path()`) y guarda, por función de sensor (`EstadoAutoclave.map_temp` / `map_pres` vigentes, o `mapas`), `{canal, puerto, formato: 2, gain, offset, poly}`. Formato: `{"formato": 1, "temperature": {sensor: {...}}, "pressure": {...}}`. Atómico. Un canal fuera del archivo no se guarda (aviso). |
| `consolidar_defectos_programas(cycle_manager, carpeta_defecto) -> dict` | Deja en la carpeta un `<cycle_id>.json` por programa con número de `cycle_manager.cycles` (`cycle_id`, `cycle_number`, `display_name`, `parameters` vigentes) y borra todo otro `.json` de la carpeta. Primero escribe todos los temporales `*.fab_nuevo` (con fsync), luego los reemplaza, luego borra los sobrantes. Idempotente. Un programa dañado no se escribe y su defecto previo se conserva. No toca `cycle_manager.defectos` (el cierre reinicia). Devuelve `{"escritos", "borrados", "omitidos"}`. Ante un fallo de escritura borra los temporales y lanza, sin cambiar los archivos. |

Lectura (uso en campo):

- `leer_parametros_crudos(ruta) -> dict | None`: el JSON sin validar; None sin archivo; lanza si es ilegible o no es un objeto.
- `entrada_calibracion_equipo(tipo, sensor, canal, ruta=None) -> dict | None`: `{"gain", "offset", "poly"}` o None si no hay archivo, el formato no es 1, falta el sensor, la entrada no es válida (no finita, `poly` mal formado, plausibilidad «rechazo» de `evaluar_desviacion_acumulada`) o su canal no es el que la función usa hoy. Nunca lanza.
- `contenido_respaldo(perfil_calibracion, parametros) -> dict`: `{ruta en el ZIP: bytes}` de los archivos que existan.

### Parámetros del equipo (`core/managers/config_manager.py`)

- `load_config(ruta_fabrica_equipo=None)` llama a `_aplicar_fabrica_equipo`, que superpone el archivo a los genéricos de `global_params.json`:
  - cada clave conocida (se aceptan los alias de errata) con tipo y rango del catálogo válidos reemplaza al genérico en `_fabrica` y en el valor inicial;
  - una clave desconocida o un valor inválido se ignora con aviso en el log;
  - si el conjunto resultante incumple la coherencia de límites (suministro < alivio ≤ fondo, corte de chaqueta ≤ alivio − 10) o la de empaque, se ignora el archivo entero con aviso;
  - archivo ilegible: aviso y genéricos. Sin archivo: idéntico a antes.
- `restablecer` no cambió: usa `_fabrica`, que ahora es el valor del equipo.
- Las reglas de coherencia pasaron a funciones puras `regla_limites(v)` y `regla_empaque(v)`; `_incoherencia_detalle` las usa (mismas reglas, mismos códigos y detalle).

### Calibración (`backend/rutas/io.py`, `config/calibration_writer.py`)

- `POST /calibration/{tipo}/{sensor}/restaurar` con `"defecto"`: usa `fabrica_equipo.entrada_calibracion_equipo(tipo, sensor, index)` (`index` = canal vigente de la función). Si hay entrada, restaura gain, offset y `poly`; si no, el neutro de siempre.
  - Auditoría `calibracion_cambio` igual que antes, con `detalle["origen"]` = `"fabrica_equipo"` | `"neutro"` (y `valor_nuevo.poly` si lo hay).
  - La respuesta agrega `origen`.
  - «ultimo» no cambia.
  - El docstring de la ruta se dejó igual porque es la descripción en la base OpenAPI de la tanda 15; la explicación va en un comentario.
- `write_user_calibration(..., poly=None)`: parámetro opcional que conserva el polinomio junto a gain/offset; sin él, igual que antes.

### Respaldo USB (`backend/rutas/respaldo.py`)

`/backup/export` agrega, si existen, `fabrica_equipo/calibracion_fabrica_equipo.yaml` (con «perfil y calibración») y `fabrica_equipo/parametros_fabrica_equipo.json` (con «parámetros y programas»). Van en el manifiesto con su hash, sin cambiar `FORMATO`. La restauración no los lee: solo procesa nombres conocidos, así que no los restaura. Un respaldo nuevo leído por una versión anterior pasa igual, porque `leer` no rechaza nombres desconocidos.

### FAB-06

Ninguna ruta llama a las tres funciones de escritura. Lo vigila `tests/test_fab_e3_solo_lectura.py` por AST:

1. solo `fabrica_equipo.py` nombra los dos archivos;
2. las tres funciones de escritura solo aparecen en `fabrica_equipo.py` y en el conjunto `CIERRE` (vacío: **la Etapa 5 debe agregar ahí su módulo**);
3. ningún `backend/rutas/*` las nombra;
4. el literal `cycles/defecto` solo aparece en `cycle_manager.py`, `gestion_programas.py` y `fabrica_equipo.py`.

## Archivos

- Código: `src/autoclave/core/runtime/fabrica_equipo.py` (nuevo), `core/managers/config_manager.py`, `backend/rutas/io.py`, `backend/rutas/respaldo.py`, `config/calibration_writer.py`.
- Pruebas nuevas (56): `tests/test_fab_e3_parametros.py` (16), `test_fab_e3_calibracion.py` (22), `test_fab_e3_defectos.py` (7), `test_fab_e3_solo_lectura.py` (7), `test_fab_e3_respaldo.py` (3, reutiliza la fixture `api` de `test_o2h_respaldo.py`).
- Las pruebas usan carpetas temporales (`monkeypatch` de `fabrica_equipo.carpeta_datos`). No escriben en `data/` ni en `src/autoclave/cycles`.

## Pruebas

- P-03:
  - parámetros: `escribir_parametros_fabrica_equipo` tras fijar valores; en un arranque nuevo, `restablecer` da el valor del equipo y no el genérico;
  - calibración: `escribir_calibracion_fabrica_equipo` y luego «defecto» dan los valores del equipo, no el neutro.
- Archivo inválido, incoherente (4 reglas) o ilegible: rigen los genéricos, con aviso.
- Calibración: sin archivo, sin el sensor, inválida o con el canal cambiado: rige el neutro. Con `poly`: se conserva. Si falla la auditoría, el archivo se revierte. «ultimo» sin cambios.
- `consolidar_defectos_programas`: escribe por número, borra los sobrantes, es idempotente, conserva el defecto de un programa dañado, no deja nada a medias si falla una escritura, y funciona con un `CycleManager` real sobre una copia temporal (al recargar, `defecto(n)` da el consolidado).
- Respaldo: exporta la copia y no la restaura; sin los archivos, el ZIP no cambia.
- Subconjunto relacionado (`-k "calibr or global_param or config_manager or respaldo or fab_ or parametros_equipo or arquitectura or o2f or t15_rutas or o2a or limites"`): 962 en verde.

Suite completa (`python -m pytest tests -q -p no:cacheprovider -n auto`): **no terminó**. Claude Code la detuvo al 17 % porque el sistema se quedó sin memoria (un worker de xdist cayó: «node down»). No se relanzó, por indicación del sistema. Hasta ese punto no hubo fallos atribuibles a la etapa. **Pendiente:** correrla completa y compararla con `suite_base.txt` (20 fallos y 6 errores preexistentes). La suite reescribió `src/autoclave/cycles/user/*.json`, y eso se descartó con `git checkout` antes de commitear.

## Decisiones tomadas en esta etapa (todas `DECISIÓN SIN CONFIRMAR`)

- **E3-D1.** El archivo de parámetros también acepta los parámetros de solo lectura, como `presion_atmosferica` calibrada en fábrica. Los valida con el rango del catálogo. La API sigue sin poder restablecer un parámetro de solo lectura (`fijar` lo rechaza), como hoy.
- **E3-D2.** La coherencia del conjunto incluye la regla de empaque, además de la de límites de presión: «y la que exista».
- **E3-D3.** El valor del equipo pasa a ser también el valor inicial. Sin base rige ese valor, y siembra las filas que falten en `system_params`. Una fila existente de la base sigue mandando como valor vigente.
- **E3-D4.** Calibración válida = gain y offset finitos, `poly` lista no vacía de números o nulo, y sin plausibilidad «rechazo» (con un «aviso» se restaura, porque ya se confirmó en fábrica). El `poly` no pasa por la plausibilidad (el respaldo lo trata como aviso).
- **E3-D5.** Canal estricto: la entrada solo vale si su `canal` es igual al canal vigente de la función. Si no, rige el neutro (mismo criterio que «ultimo»).
- **E3-D6.** `consolidar_defectos_programas` incluye todo programa con número de `cm.cycles`, también un genérico de `factory/` sin copia de usuario. Un defecto con número del 1 al 10 manda sobre el genérico de `factory/` en `CycleManager.defecto(n)` (D-08). La migración T29-05 (`_modo_solido_fabrica`) sigue leyendo el `factory/` original: no se tocó y queda para decidir.
- **E3-D7.** Los archivos que no son `.json` de `cycles/defecto` no se tocan. Un programa dañado conserva su defecto anterior.
- **E3-D8.** FAB-06 y `cycles/defecto`: siguen las escrituras de `gestion_programas` que ya existían: el defecto propio de un programa nuevo al duplicar (también en ENTREGADO, con número ≥ 11), su borrado con el programa personalizado, y el borrado de fábrica (solo en FÁBRICA). No cambian el defecto de otro programa. Si Cristian quiere que en ENTREGADO nada escriba en `cycles/defecto`, hay que tocar `gestion_programas.duplicar`.
- **E3-D9.** En el respaldo, la calibración del equipo va con «perfil y calibración» y los parámetros con «parámetros y programas», en la carpeta `fabrica_equipo/` del ZIP. Es solo una copia y nunca se restaura.
- **E3-D10.** El archivo de calibración del equipo guarda todas las funciones de `map_temp` / `map_pres`, no solo las instaladas.

## Para la Etapa 5

- Llamar a `escribir_parametros_fabrica_equipo(context.config_manager, destino)`, `escribir_calibracion_fabrica_equipo(destino)` y `consolidar_defectos_programas(cm, carpeta)`. Si el cierre consolida en temporales (`*.fab_nuevo`), pasarles el destino temporal.
- Agregar el módulo del cierre a `CIERRE` en `tests/test_fab_e3_solo_lectura.py`.
- Tras el reemplazo, el reinicio recarga `ConfigManager` y `CycleManager.defectos`.
