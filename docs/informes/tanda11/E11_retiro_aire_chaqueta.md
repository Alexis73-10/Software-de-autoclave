# E11 — Retiro de la salida `aire_comprimido_chaqueta` (tanda 11)

- Rama: `tanda-11-e11` (desde `tanda-11`, 1b3ec0d). Commit de código: `ae883e4`.
- Fuente de verdad: D11-2 de `docs/mis_plans/decisiones_tanda_11.md`.

## Lo que se hizo, punto por punto (D11-2)

**D11-2.2: la función se retira por completo.** Con `grep -rn aire_comprimido_chaqueta` (incluido `funcion_`) en `src/`, `tests/`, `tools/`, la configuración y `docs/` aparecían:

| Lugar | Cambio |
|---|---|
| `core/runtime/status.py` `map_do` | Se quita la clave (índice 12). Queda un comentario que dice que el 12 (DO 13) está libre. |
| `devices/io/set_io.py` | Se quitan `aire_comprimido_chaqueta_on/off`. |
| `backend/context.py` `_SALIDAS_ENERGIA` | Se quita de la tupla. Queda `aire_comprimido_camara`. |
| `config/instances/ACV-2026-001.yaml` | Se quita de `io_enabled.DO` y de `io_ports.DO` (`: 13`). |
| `config/models/solids_liquids.yaml` | Se quita de `actuators` y de `io_contract.DO`. |
| `i18n/es.json` y `en.json` | Se quitan `io.do.aire_comprimido_chaqueta` y `funcion_aire_comprimido_chaqueta`. |
| Catálogo de asignación de E/S y Entradas/Salidas (modo prueba) | Ambos salen de `map_do`, así que la salida desaparece sola. `/io/channels` ya no la lista, y `PATCH /io/test/output/aire_comprimido_chaqueta` responde 404. |
| `docs/instalacion/LEEME_INSTALACION.md` l. 259 | Se quita de la lista del rodeo "canales que no aparecen en E/S", para que nadie la agregue a mano. La l. 365 es historia de la entrega B→C y no se tocó. |
| Hoja de pruebas de banco (B-13: `pruebas.py`, `.md`, `.html`) | Antes decía "DO13/DO14 aire comprimido de chaqueta/cámara". Ahora dice "DO13 libre (sin función desde la tanda 11; debe seguir siempre apagada), DO14 aire comprimido de cámara". El `.md` y el `.html` se editaron a mano con la misma frase y **no se regeneraron**: `generar.py` borraba unas 300 líneas que se agregaron al `.md` a mano en otras tandas (ver Pendientes). |
| Pruebas existentes | En `test_io_names.py` y `test_io_test_mode_endpoints.py` el total de DO pasa de 24 a 23. En `test_r8_salidas_puertas.py` y `test_t8_e1_io_enabled_perfil.py` se quita la salida de las listas esperadas. |

En `tools/` no había ninguna aparición.

**D11-2.3: la numeración física no cambia.** Ninguna otra salida cambia de índice. `aire_comprimido_camara` sigue en DO 14, y así hasta el buzzer en DO 24. La trama con la ESP32 y el firmware no cambian. Nadie puede mandar DO 13: no tiene nombre en `map_do`, y el modo prueba lo rechaza con 404. Así que la tarjeta lo deja en 0, y el ALL_OFF también lo apaga. Si el ALL_OFF no se confirma, el apagado de respaldo canal por canal (`_CANALES_APAGADO_BASE = 1..24`) sigue mandando DO 13 en 0. Hay una prueba que lo comprueba.

**D11-2.4: `aire_comprimido_camara` no se tocó.** Siguen en verde las pruebas de descompresión modo 4 y del protocolo de fallo (`test_descompresion_fase`, `test_protocolo_fallo_modo_descompresion`, `test_t5_protocolo_liquidos`, `test_t8_s2a_*`, los ensayos simulados), más una prueba nueva de que manda por DO 14.

**D11-2.5: los datos antiguos se aceptan y se ignoran con una advertencia.** La lista de salidas retiradas está en un solo sitio: `io_names.SALIDAS_RETIRADAS`. `asignacion_io.RETIRADAS` es la misma lista, y `quitar_retiradas(cambios, origen)` deja la advertencia en el log. Se ignora la salida en estos casos:
- `io_ports` del YAML de instancia (`fabrica_desde_yaml`). Antes, una función desconocida ahí bloqueaba el arranque con `CONFIGURACION_INVALIDA`, y eso habría pasado en los equipos que conservan su YAML de la compilación anterior.
- `data/asignacion_io.json` guardado (`vigente`). Antes, el equipo quedaba bloqueado con la alarma CONFIGURACION_INVALIDA. Si la salida estaba en `verificacion_pendiente`, ya se filtraba antes con `funciones()`.
- Restaurar un respaldo de la asignación (`server_reasignacion.validar_respaldo`). Lo que se guarda ya no la incluye.
- `io_enabled` del YAML (`io_names.canales_digitales`). Se omite con una advertencia propia.

Un cambio **nuevo** por la API de reasignación que traiga la salida se sigue rechazando como `funcion_desconocida` (`combinar` no cambió).

## ¿Cambia el comportamiento de alguna fase?
No. Ninguna fase, ni el protocolo de fallo, ni PREPARACION/PREPARADO, ni las puertas llamaban a `aire_comprimido_chaqueta_on/off`. El grep solo encontró las definiciones. El único uso real era su lugar en `_SALIDAS_ENERGIA`. Esa lista solo sirve para inhibir encendidos, y nadie encendía esta salida. Quitarla tiene un efecto secundario bueno: con la clave fuera de `map_do`, el setter `SetOutput.inhibidas` habría registrado una excepción por cada inhibición (no encontraba su canal). Ahora ya no la busca.

## Pruebas
Todas corridas con `PYTHONPATH=<worktree>/src`. `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-ad7b4bd54afb67488\src\autoclave\__init__.py`.

- Nuevas: `tests/test_e11_retiro_aire_chaqueta.py`, 16 pruebas. Primero se vio fallar 14 de ellas (las 2 restantes, sobre `aire_comprimido_camara` y el apagado de respaldo, describen lo que debe seguir igual y ya pasaban). Después de los cambios pasan las 16. Cubren:
  - mapa DO esperado completo y DO 13 libre;
  - la salida no aparece en `funciones()`, `fabrica_codigo()`, `fabrica()` ni `canales_digitales`;
  - `/io/channels` no la lista y `aire_comprimido_camara` sigue en DO 14;
  - `SetOutput` ya no tiene los métodos;
  - el apagado de respaldo incluye DO 13;
  - `_SALIDAS_ENERGIA`, i18n y el YAML de modelo ya no la tienen;
  - un YAML antiguo (`io_ports` e `io_enabled`), un `asignacion_io.json` antiguo y un respaldo antiguo se aceptan con advertencia;
  - el arranque (`cargar_asignacion_io`) con YAML y asignación antiguos no bloquea ni activa alarmas;
  - la API sigue rechazando un cambio nuevo con la salida.
- Módulos tocados y los que los importan (45 archivos, `-n auto`): **1311 passed, 8 skipped** en 148,6 s.
- QML y controlador de E/S (`test_r8_reasignacion_banco_qml`, `test_x1_una_instancia_opciones_qml`, `test_s2b_d8_2_15_textos_catalogo_qml`, `test_p1_salidas_momentaneas_qml`, `test_es_controlador`): **34 passed**.
- La suite completa no se corrió (regla 8).

## DECISIONES SIN CONFIRMAR
1. **DO 13 "libre", no bloqueado para reasignar.** D11-2.3 dice "libre/reservado". Se dejó como un puerto libre más, igual que DO 25-32: Opciones avanzadas puede asignarle otra función si se daña un puerto. No se agregó ningún bloqueo. Si Cristian prefiere reservarlo (rechazar asignaciones a DO 13), hay que agregar una regla en `asignacion_io.validar`.
2. La advertencia por los datos antiguos sale **en cada arranque** mientras el YAML instalado o el `asignacion_io.json` conserven la salida. El archivo no se reescribe solo. El JSON se limpia la próxima vez que el ingeniero guarde una reasignación, y el YAML al instalar esta compilación.

## PREGUNTAS PARA CRISTIAN
Ninguna. No cambió la lógica de ninguna fase.

## Pendientes / notas para la sesión principal
- `docs/mis_plans/hoja_pruebas_banco/generar.py` ya **no reproduce** el `.md` actual: al correrlo, el `.md` pierde unas 300 líneas que se agregaron a mano en otras tandas. Por eso aquí se editaron a mano las tres fuentes. Conviene que una tanda futura sincronice `pruebas.py` con el `.md`.
- Archivos de choque tocados: `i18n/es.json`, `i18n/en.json` (solo se borraron 2 claves en cada uno), `hoja_pruebas_banco_equipo_pruebas.md` (una línea de B-13) y `docs/instalacion/LEEME_INSTALACION.md` (una línea).
