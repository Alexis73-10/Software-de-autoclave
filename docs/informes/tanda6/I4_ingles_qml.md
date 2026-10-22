# I4 — Terminar el inglés: parte QML (Bloque 2) ★

Rama `tanda-6`. Sigue a `I4_ingles_backend.md`. R-06 se mantiene: no se agregó ningún selector de idioma para el operador.

## Hecho

### El idioma vigente en las dos ventanas
- O2a dejó anotado que nadie leía `GET /language`: cada proceso QML arrancaba en español y solo la ventana que hacía el cambio lo aplicaba.
- `ui_qml/bridge/i18n_qml.py`: el singleton `I18n` sigue `GET /language` cada 3 s, igual que `Unidades` sigue `GET /units`. La consulta va en un hilo y la respuesta se aplica en el hilo de la GUI (`i18n.fijar_idioma`).
  - El sondeo arranca cuando un motor QML pide el singleton, no al importar el módulo.
  - Sin respuesta o con un valor inválido, se conserva el idioma vigente.
  - Si el idioma cambió en esta ventana mientras la consulta estaba en vuelo, la respuesta se descarta. Así una respuesta vieja no revierte el cambio recién hecho.

### Textos que Python entrega a QML
- **Nombre del programa** (`ui_qml/domain/nombres_ciclo.py`):
  - pantalla de ciclo y selector: se usa `nombres[idioma]` de `GET /cycle` y `/programas`;
  - Historial, Menú y último ciclo: la BD guarda el nombre que tenía el programa. Si coincide con el nombre en español de un ciclo de fábrica, se muestra el de ese ciclo en el idioma vigente.
  - Un programa renombrado se ve igual en los dos idiomas (§3.7).
- **Selector de ciclo:** la temperatura de cada programa sale en la unidad vigente (antes era "°C" fijo).
- **NO ABRIR:** el motivo (`noAbrirMotivo`) usa `camara_segura_motivo_textos[idioma]`. Si no viene, se usa el texto en español de siempre. La decisión de NO ABRIR no cambia: sigue saliendo de `no_abrir`, con falla cerrada.
- Ya estaban del catálogo, y se verificó:
  - los motivos de puerta (`motivo_textos`, DoorCommandService);
  - el resultado del ciclo (`estados.<resultado>`);
  - las alarmas (I1);
  - el rótulo del periodo (I4 backend);
  - la gráfica en vivo en la unidad vigente (O3).

### Literales QML
- `NuevoUsuario.qml`: "Seguir editando" → `usuarios.seguir_editando` ("Keep editing").
- `PanelEquipo.qml`: una cadena con saltos de línea crudos dentro de las comillas pasa a `"\n\n"`. El texto que se ve es el mismo.
- Nueva prueba, más estricta que la de I2: revisa TODA cadena entre comillas de cada `.qml`, no solo ciertas propiedades. Lista blanca, con su justificación en la prueba:
  - eslóganes de marca (D-06);
  - "Software v";
  - motivos de auditoría que se envían a `/io/test/exit` y no se muestran;
  - " kPa" de E/S (exenta de U1, regla 0.5);
  - el patrón de `Qt.formatDate`;
  - los endónimos "Español"/"English";
  - escapes y marcado HTML.
- Otra prueba exige que toda clave `I18n.t("…")` usada en QML exista en es y en.

### Truncado a 1024 px
- `tests/i4_truncado_banco.py` carga cada pantalla offscreen en 1024×1638 (`Escala.factor` = 1024/1200), sin backend. Lista los textos visibles que Qt truncó (`truncated`) o que desbordan su caja (sin elide ni ajuste de línea).
- Son 22 pantallas: las 9 principales, Reposo y las 12 secciones de Opciones.
- **Hallazgo:** en inglés, en el Menú principal, la descripción de Historial ("Review the completed / cycles") ocupaba 3 líneas y se truncaba. Cambiada a "Review completed / cycles".
- Ningún otro truncado en es ni en en.
- `tests/test_i4_truncado_qml.py` lo verifica en inglés en las 22 pantallas.
- Capturas: `docs/informes/tanda6/capturas/I4_es_<Pantalla>.png` y `I4_en_<Pantalla>.png` (44). Se regeneran con `python tests/i4_truncado_banco.py`.
- **Limitación:** sin backend, cada pantalla muestra su estado vacío (sin ciclo, sin datos, NO ABRIR). Los textos que solo aparecen con datos (ventanas flotantes, diálogos, filas) no se recorrieron en esta revisión automática. Quedan para el recorrido en inglés de la hoja de banco (H1).

## DECISIONES SIN CONFIRMAR
- **I4Q-1:** en el Historial, el nombre de un ciclo de fábrica guardado en español se traduce por coincidencia exacta con el catálogo. Un programa de usuario que se llame igual que uno de fábrica también se traduce.
- **I4Q-2:** `estadoSeguroBloqueadoMotivo` (S4) sigue en español. `SeccionEstadoSeguro.qml` decide el botón "asignar sonda" buscando "Principal" en ese texto, y traducirlo exige antes un código en el backend.
- **I4Q-3:** `resultado_detalle` del Historial (p. ej. `FALLO_CALENTAMIENTO`) se muestra como código, igual en los dos idiomas.
- **I4Q-4:** el `detail` con que el backend rechaza un cambio de programa (selector) sigue en español: no trae código.

## Pruebas
- `tests/test_i4_ingles_qml.py` (17):
  - literales;
  - lista blanca viva;
  - claves es/en;
  - nombres de programa;
  - selector en °F;
  - motivo NO ABRIR;
  - sondeo de idioma (aplica, conserva, descarta respuesta vieja).
- `tests/test_i4_truncado_qml.py` (22).

## Revisión (safety-reviewer y timing-auditor)
Ningún hallazgo Crítico ni Alto. La bandera NO ABRIR sigue con falla cerrada: solo cambia el texto del motivo.
- **SAF-01 (Medio), mitigado con prueba:** `bloqueoPorSonda` depende de "Principal" en el texto en español. Una prueba fija que ese motivo no se traduce. Pendiente: que el backend exponga un código (I4Q-2).
- **SAF-02 (Bajo), corregido:** si `Thread.start()` falla, `_ocupado` vuelve a False.
- **TMG M-01 (Medio), corregido:** la señal se emite en un `finally`, así que el sondeo nunca queda trabado. `unidades_qml.py` tiene el mismo patrón y no se tocó: queda abierto.
- **Abiertos (Bajo):**
  - SAF-03: un PUT local fallido descuadra el idioma hasta el siguiente sondeo, 3 s después.
  - B-02: el descarte compara el idioma, no una generación.
  - B-03: `noAbrirMotivo` no se notifica al cambiar el idioma. Hoy su único binding lee `I18n.lang`.
  - B-04: `_oyentes` de i18n sin lock ni baja.
  - B-05: estilo.
