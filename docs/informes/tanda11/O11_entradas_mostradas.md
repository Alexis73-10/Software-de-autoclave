# O11 — Entradas mostradas: solo sensores en uso y selector por fila (D11-7)

Rama `tanda-11-o11`, desde `tanda-11` en d0397cd (S11 ya unida). Fuente: D11-7 completo de
`docs/mis_plans/decisiones_tanda_11.md` y la etapa O11 de `instruccion_claude_code_tanda_11.md`.
No se configuraron roles de sensor en ningún programa (D11-7, contexto). No se tocaron las
funciones de S11 en `sensores_ciclo.py` (ni ese archivo).

## Qué se hizo, por punto

| Punto | Estado | Dónde |
|---|---|---|
| D11-7.1 Un sensor No en uso no se puede mostrar | Hecho | backend y pantallas (abajo) |
| D11-7.2 Selector por fila (Entrada 1/2/3) | Hecho | `parametros_ciclo_controller.py`, `OpcionesParametrosCiclo.qml` |
| D11-7.3 Cambio de rol a No en uso | Hecho | `server.put_sensor_roles` |
| D11-7.4 Omisión y JSON viejo | Hecho | `gestion_programas.entradas_de` / `entradas_por_omision` |
| D11-7.5 Programas de fábrica: filtro de presentación, siguen sin editarse | Hecho | mismo `entradas_de`; `editable` sin cambios |

### Backend (`src/autoclave/core/managers/gestion_programas.py`, `src/autoclave/backend/server.py`)

- `gestion_programas` (funciones nuevas; usa `sensores_ciclo` sin modificarlo):
  - `AI_DE_SENSOR` (se movió aquí desde `server._AI_DE_SENSOR`, que se quitó) y `entradas_no_en_uso(c)`:
    AI de los sensores que no son Principal ni Referencia (vía `sc.sensores_en_uso`).
  - `entradas_por_omision(c, habilitadas)`: [AI del Principal, primera Referencia (orden del
    catálogo) si la hay, `pres_camara`], hasta 3, entre las habilitadas; si ninguna está habilitada,
    la primera habilitada en uso.
  - `entradas_de(c, habilitadas)`: la selección propia sin los No en uso (sirve para JSON viejos y
    programas de fábrica); si no queda ninguna o no hay selección propia, la omisión.
  - `entradas_disponibles(c, habilitadas)`: lo que ofrece el selector (habilitadas − No en uso).
  - `entradas_tras_cambio_de_rol(propias, asignacion)`: la selección tras el cambio de rol (None si
    no hay selección propia o no cambia; vacía → AI del Principal).
  - `fijar_entradas`: además de 1 a 3 / sin repetir / habilitadas, rechaza un sensor No en uso con
    `ErrorPrograma("SENSOR_NO_EN_USO", ..., 422)` (el JSON no se toca).
- `server.py`:
  - `GET /cycle`: `entradas_mostradas` ya filtrada; `entradas_no_en_uso` igual que antes. Si
    `io_enabled` falla, la omisión del programa (antes, las tres fijas con la Referencia).
  - `GET /cycle/display-inputs`: agrega `disponibles` y `no_en_uso` (conserva `habilitadas`).
  - `PUT /cycle/display-inputs`: 422 `SENSOR_NO_EN_USO` (vía `_gestion`, como los demás rechazos).
  - `PUT /cycle/sensor-roles`: si el programa tiene selección propia y un sensor de ella queda No en
    uso, `entradas_mostradas` se escribe en la MISMA escritura atómica que
    `cycle_temperature_sensors` (`_escribir_sensores_json(..., entradas)`), se aplica en memoria junto
    con `cycle.sensores` bajo el mismo `bloqueo_maquina`, se revierte junto con los roles si el
    cambio se rechaza por ciclo en curso, y se audita: `ROLES_SENSOR` lleva `entradas_mostradas` en
    el detalle y además se registra el evento `entradas_mostradas` (misma entidad que el PUT,
    `/cycle/display-inputs/<n>`) con anterior/nuevo y `detalle.motivo = "sensor_no_en_uso"`.

### Pantallas

- `ui_qml/domain/entradas_mostradas.py`: `visibles(lista, no_en_uso)`; `construir` y
  `series_grafica` ya no incluyen las No en uso (desaparece la fila "—" en Preciclo, Ciclo y la
  leyenda/serie de la gráfica). `enUso` se conserva (siempre `True`) por compatibilidad con QML.
  `POR_OMISION` (sin `/cycle` todavía) pasa a `temp_camara`, `pres_camara`.
- `ui_bridge.py`: pasa `entradas_no_en_uso` también a `series_grafica`.
- `parametros_ciclo_controller.py`: funciones puras `filas_de`, `opciones_fila`,
  `entradas_de_filas`; propiedades `entradasDisponibles`, `filasEntradas`; slots
  `opcionesFila(fila, filas)` y `guardarFilas(filas)` (Entrada 1 obligatoria, sin repetir, y guarda
  con el mismo `PUT`); mensaje para `SENSOR_NO_EN_USO`. Con un backend sin `disponibles`, usa
  `habilitadas`.
- `OpcionesParametrosCiclo.qml` (vista "entradas"): tres filas «Entrada 1:», «Entrada 2:»,
  «Entrada 3:» (componente `Fila`, 92 px de diseño ≥ 64 px); al tocar una se despliega debajo su
  lista (Ninguna en las filas 2 y 3 + las disponibles menos las elegidas en las otras filas; la
  elegida, resaltada); se guarda con el botón existente. `cambiosPendientes` también cuenta las
  entradas sin guardar (Opciones confirma antes de salir, como con los roles).
- **Hallazgo corregido**: los botones Guardar de las vistas de entradas y de roles de sensor no
  tenían `width` y `BotonFormulario` no tiene ancho implícito: quedaban en 0 px y no se veían (se ve
  en `O11_antes_*_opciones_1_entradas.png`: solo asoma una letra a la derecha). Se les puso
  `width: Escala.px(320)`. Ver DECISIONES SIN CONFIRMAR.
- Textos nuevos es/en (`opciones.`): `entrada_fila` («Entrada {n}:» / «Input {n}:»),
  `entrada_ninguna` («Ninguna» / «None»), `err_entrada_1_obligatoria`, `err_entradas_repetidas`,
  `err_sensor_no_en_uso`; `entradas_nota` reescrita. Sin comillas « » alrededor de «No en uso»
  (la prueba de V8b exige que lo citado así sea un nombre de parámetro).

## Commits

- `6195b8c` feat(tanda11-o11): entradas mostradas solo con sensores en uso en el backend
- `8fac7ce` feat(tanda11-o11): selector por fila de entradas y pantallas sin filas No en uso
- (este informe, el script de capturas y las capturas, en el commit siguiente)

## Pruebas

`autoclave.__file__` en todas las corridas:
`C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-adce3217b26664c1f\src\autoclave\__init__.py`

Nuevas, `tests/test_o11_entradas_mostradas.py` (escritas antes del código; 24 de 28 fallaban):
omisión con 5 asignaciones distintas y respetando las habilitadas; `entradas_no_en_uso`; JSON viejo
filtrado (función y `GET /cycle`); programa de fábrica filtrado; `disponibles` sin No en uso; `PUT`
con un No en uso → 422 `SENSOR_NO_EN_USO` sin tocar el JSON (y aceptado si está en uso); cambio de
rol que quita la entrada (JSON, memoria y auditoría `entradas_mostradas`), que repone el Principal si
queda vacía, que no toca una selección no afectada, y que no cambia nada si se rechaza en CICLO;
función pura del cambio de rol; `construir`/`series_grafica`/`UiBridge` sin la fila No en uso;
controlador: el selector no ofrece el No en uso, filas iniciales, opciones sin repetidas entre filas,
Entrada 1 obligatoria y sin repetir (sin `PUT`), guardado compactando «Ninguna»; textos es/en; QML
con 3 filas, títulos, «Ninguna», alto ≥ 64, botón Guardar con ancho > 0, desplegable de la fila 2 con
Ninguna + disponibles menos la de la fila 1, sin avisos del motor QML.

Actualizadas (el comportamiento cambió a propósito, D11-7.4): en `test_o1_gestion_programas.py` y
`test_o3_entradas_mostradas.py` la omisión de fábrica pasa de [cámara, referencia, presión] a
[cámara, presión]; la prueba del «—» por No en uso pasa a «no se muestra».

Resultados:
- `tests/test_o11_entradas_mostradas.py`: **28 passed**.
- Módulos tocados y los que los importan (51 archivos, `-n auto`, sin
  `test_o3_entradas_mostradas_qml.py`): **1070 passed** en 218 s.
- `tests/test_o3_entradas_mostradas_qml.py` en serie: **9 passed**. Con `-n auto` junto a otros dio 5
  errores de montaje (fixtures en paralelo); en serie pasa entero — temporización/paralelismo ajeno.
- Tras el último ajuste de QML (resaltado y ancho del botón): 11 archivos de Opciones/i18n/textos,
  `-n auto`: **459 passed**.

## Capturas (banco CAP9)

Script `tests/o11_capturas_banco.py` (no lo recoge pytest): Opciones con
`tests/opciones_qml_banco.py` (1200x1920, técnico); Preciclo y Ciclo cargando la pantalla sola con un
`UiBridge` real sobre un `UIServiceBackend` simulado (como la parte `preciclo` de
`tests/cap9_capturas_banco.py`). Caso: asignación de fábrica y un JSON viejo con
`[temp_camara, temp_referencia, pres_camara]`. «antes» = lo que mandaba el backend anterior (la
lista sin filtrar) con el código de antes; «despues» = la lista calculada por el
`gestion_programas` nuevo.

```
PYTHONPATH=<worktree>/src python -X utf8 tests/o11_capturas_banco.py antes
PYTHONPATH=<worktree>/src python -X utf8 tests/o11_capturas_banco.py despues
```

Carpeta `docs/informes/tanda11/capturas/o11/`, cada una en `es` y `en`:
- `O11_antes_<i>_opciones_1_entradas.png` (lista con casillas y sin botón visible),
  `O11_antes_<i>_preciclo.png`, `O11_antes_<i>_ciclo.png` (columna «Temp. referencia» con «—»);
- `O11_despues_<i>_opciones_1_entradas.png`, `O11_despues_<i>_opciones_2_desplegable.png`,
  `O11_despues_<i>_preciclo.png`, `O11_despues_<i>_ciclo.png` (sin la columna de la Referencia;
  la gráfica sin su serie).

Sin avisos del motor QML en ninguna. Total 14 PNG.

## DECISIONES SIN CONFIRMAR

1. **Asignación inválida**: «en uso» = `sc.sensores_en_uso` (con una asignación inválida solo el
   Principal de respaldo, Cámara 1). Antes, «No en uso» se leía del rol literal. Para asignaciones
   válidas es lo mismo.
2. **Omisión sin `/cycle` todavía** (pantalla recién abierta): Cámara 1 y presión de cámara (la
   omisión de la asignación de fábrica), en lugar de las tres de siempre con la Referencia.
3. **Primera Referencia** = la primera en el orden del catálogo (`temp_camara`, `temp_2_camara`,
   `temp_ref`).
4. **Omisión filtrada por las habilitadas**; si ninguna de las tres está habilitada, la primera
   habilitada en uso (como antes, `habilitadas[:1]`, pero sin un No en uso).
5. **Auditoría del cambio de rol**: además del detalle en `ROLES_SENSOR`, un registro
   `entradas_mostradas` aparte. Como `ROLES_SENSOR`, se escribe con `_auditar` (un fallo de la
   bitácora queda en el log y no deshace el cambio), no con la semántica de `_gestion` (revertir si
   no hay auditoría). Se mantuvo la semántica existente del endpoint de roles.
6. **Botón Guardar de roles de sensor** (vista vecina, mismo defecto de ancho 0): también se le
   puso ancho. Sin él no se podían guardar roles desde la pantalla. Reversible.
7. Al cambiar las filas, «Ninguna» en la fila 2 con algo en la fila 3 se guarda compactado (la de la
   fila 3 pasa a ser la segunda).

## PREGUNTAS PARA CRISTIAN

1. ¿La omisión [Principal, primera Referencia, presión] queda así (D11-7.4 la marca como propuesta)?
2. Otros `BotonFormulario` sin ancho en la misma pantalla: «Cerrar» del aviso de cambio automático
   (`cerrarAvisoParametros`) y los botones de unidad de ingreso psig/inHg de la ventana de ajuste.
   No se tocaron (fuera de D11-7); probablemente tampoco se ven. ¿Se corrigen en otra etapa?

## Pendientes

- La UI no muestra un aviso cuando el backend quitó entradas por un cambio de rol (la vista de
  entradas se recarga al abrirla y ya sale la selección nueva).
- No se corrió la suite completa (regla 8 del brief).
