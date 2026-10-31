# U10b — Barrido de todas las pantallas y abreviaturas (D10-1.4 y D10-1.5)

Rama `tanda-10-u10b`, desde `tanda-10` (af5eaf5, con U10a unida). Sin push.
La empezó un subagente cuya sesión se cortó (todo sin commit); otro la continuó: revisó lo
hecho, corrigió 3 pruebas que había roto, agregó Opciones con datos a la prueba, commiteó por
partes, eligió las capturas y escribió este informe.

## Qué se hizo, por punto

| Punto | Estado |
|---|---|
| D10-1.4 barrido | Hecho en todas las pantallas cargadas solas, Main en Preciclo con alarmas y campana, Menú Principal y sus 7 ventanas con datos, Opciones (12 secciones, Reasignación y Manejo de ciclos con sus diálogos), en es y en, a 1024x1638 y 1200x1920 |
| D10-1.4 CIC-10 en la tarjeta de alarmas de Preciclo | Hecho: motivo completo en varias líneas (antes se achicaba con `HorizontalFit` y aun así se cortaba) |
| D10-1.4 filas de alarma en español con la interfaz en inglés | Hecho: se TRADUCEN (rol `descripciones` del modelo, desde los textos por idioma que el servidor ya manda en el DTO) — en la tarjeta de Preciclo y en el panel de la campana |
| D10-1.5 prueba extendida | Hecho: `tests/test_u10b_textos_caben_qml.py` (256 casos) |
| Capturas antes/después | 16 PNG (comprimidos a 256 colores) en `docs/informes/tanda10/capturas/u10b/` |

### D10-1.4 Hallazgos y cambios

Con la revisión ampliada (ver D10-1.5) solo aparecieron problemas en:

1. **Tarjeta de alarmas de Preciclo** (`PantallaPreciclo.qml`): fila CIC-10 con el motivo largo
   achicada a letra ilegible y cortada; y todas las filas en español con la interfaz en inglés.
   Ahora `wrapMode: Text.WordWrap` con alto de fila según el texto, y el texto es
   `descripciones[I18n.lang] || description || id`.
2. **Panel de la campana** (`PanelNotificaciones.qml`): mismas filas, recortadas con `elide` y
   en español. Ahora `multilinea: true` (propiedad ya existente de `FilaAlarma`) y la
   descripción del idioma vigente.
3. **Origen de la traducción** (`ui_bridge.py`): `AlarmListModel` gana el rol `descripciones`
   ({idioma: descripción}) leído de `textos` del DTO de /status (`alarmas_i18n.por_idioma`).
   Filas mal formadas → `{}` y la pantalla usa `description` (respaldo, igual que antes). No se
   tocó el servidor ni el catálogo de alarmas.
4. **Reportes, tabla «Por programa»** (`ResumenPeriodo.qml`): encabezados «Completados» y
   «Cancelados» (y en inglés «Completed») se achicaban (`HorizontalFit`). El encabezado pasa a
   `TextoAjustable` por clave (`claves: [...]`); las filas de datos (nombres de programa) siguen
   como estaban (se achican si no caben: son datos, no se abrevian).
5. **Historial / Ciclos de hoy** (`ListaCiclos.qml`): «NN · Programa» se achicaba. Se reparten
   distinto las proporciones de columna (Fecha 0.22→0.19, Hora 0.14→0.12, Programa 0.27→0.32);
   ningún texto nuevo.

Sin problemas encontrados: IntroArranque, Login, CambioClave, NuevoUsuario, MenuPrincipal,
CicloEnCurso, Instalación, Reposo, Opciones y sus 15 pantallas, Reasignación, Manejo de ciclos,
barra inferior, Último ciclo, Mantenimiento, panel del equipo.

### D10-1.5 Prueba automática

`tests/textos_caben_qml.py` (revisión genérica de U10a) amplía:

- 3 tipos nuevos de problema: `recortado` (Qt lo truncó: elide/maximumLineCount), `encogido`
  (una línea con `fontSizeMode` distinto de FixedSize cuyo texto a su tamaño no cabe: Qt lo
  achica — el caso CIC-10), `desborda_alto` (con ajuste de línea, las líneas no caben en el alto);
- contexto de recorte: un texto solo se compara con cuadros y divisores de su mismo `clip`
  (las filas de una lista recortada no chocan con lo que tapa su parte oculta);
- `revisar_main()`: Main.qml completo, con pasos (campos del puente, alarmas reales del catálogo
  con sus textos por idioma, abrir la campana) y capturas;
- `revisar_menu()`: Menú Principal con datos de ejemplo y cada una de sus ventanas.

`tests/opciones_qml_banco.py` (banco CAP9): `ancho`/`alto` (Escala.factor = ancho/1200) y
`revisar=True` (revisa los textos en cada `capturar()`).

`tests/test_u10b_textos_caben_qml.py`, en es y en × 1024x1638 y 1200x1920:
- 25 pantallas cargadas solas: sin problemas y sin avisos QML nuevos;
- Main en Preciclo con CIC-10 (motivo literal de T10) y SEN-06, tarjeta y campana: sin
  problemas, motivo COMPLETO y en el idioma de la interfaz (en inglés, el texto en español no
  aparece);
- Menú y sus 7 ventanas: sin problemas; abreviado solo si el completo no cabe;
- Opciones con datos (secciones, Reasignación R8, Manejo de ciclos C9 técnico e ingeniero):
  ninguna captura con problemas.

`tests/test_u10b_alarmas_idioma.py`: rol `descripciones` (bien formado, 7 formas mal formadas,
sin textos).

## Tabla de textos abreviados (nuevos en U10b)

Anchos en px (completo / disponible). Los de Preciclo y Ciclo son los de U10a (ver su informe).

| Pantalla | Idioma | Clave | Completo | Abreviado | ¿Se abrevia? |
|---|---|---|---|---|---|
| Reportes, tabla por programa | es | `reportes.col_completados` | Completados | Complet. | Sí (118 / 95.7 a 1024; 137 / 112.2 a 1200) |
| Reportes, tabla por programa | es | `reportes.col_cancelados` | Cancelados | Canc. | Sí (102 / 95.7; 118 / 112.2) |
| Reportes, tabla por programa | en | `reportes.col_completados` | Completed | Compl. | Sí (99 / 95.7; 114 / 112.2) |
| Reportes, tabla por programa | en | `reportes.col_cancelados` | Cancelled | Cancel. | No (cabe: 88 / 95.7; 101 / 112.2) |

## Textos traducidos (no abreviados)

Filas de alarma de la tarjeta de Preciclo y del panel de la campana: ahora salen en el idioma de
la interfaz con el texto del catálogo de alarmas (`alarmas_i18n`), p. ej. CIC-10 en inglés
«Chamber pressure sensor without reading: without the chamber pressure sensor the chamber cannot
be brought to a safe state. … The chamber is still not considered safe.» y SEN-06 «Chamber
pressure sensor without reading: call service.». No se agregó ninguna clave i18n para esto.

## Capturas

`docs/informes/tanda10/capturas/u10b/U10b_<antes|despues>_<es|en>_<vista>.png`, 1024x1638:

- `Preciclo_alarmas`: tarjeta de alarmas con CIC-10 y SEN-06 (antes: CIC-10 en letra mínima y
  cortado; en inglés, filas en español);
- `campana`: panel de notificaciones (antes recortado con «…» y en español);
- `Historial`: columna Programa (antes achicada);
- `Reportes`: encabezado de la tabla por programa (antes «Completados/Completed» achicados).

## Commits

- `b61617d` test(tanda10-u10b): la línea base de i18n resuelve las claves abrev. recorriendo el
  catálogo (pedido por la sesión principal: rojo de la suite de integración causado por U10a)
- `0bfb25e` test(tanda10-u10b): revisión de textos ampliada a todas las pantallas (D10-1.5)
- `0e0a71e` fix(tanda10-u10b): filas de alarma en el idioma de la interfaz y motivo completo
- `9451740` feat(tanda10-u10b): barrido de pantallas, Reportes e Historial sin textos fuera de
  su cuadro
- (este informe y las capturas de Reportes regeneradas tras cambiar «Cancel.» por «Canc.»)

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a26b3309f9ff1210b\src\autoclave\__init__.py`
(PYTHONPATH al `src` del worktree; pytest-xdist `-n auto`).

| Prueba | Resultado |
|---|---|
| `test_i18n_linea_base.py` (completo, tras el arreglo pedido) | 5 passed |
| Relacionadas con lo tocado, 1.ª pasada (45 archivos: `test_ui_bridge`, `test_v8b_textos`, `test_i18n*`, `test_main_menu_principal_qml`, `test_menu_principal_*`, `test_opciones_qml`, `test_c9_*`, `test_r8_*`, `test_n8_*`, `test_o2f/o2g/o2h`, `test_o3_*`, `test_pantalla_ciclo`, `test_b1/b5/b6`, `test_s2b`, `test_s4_cic10`, `test_s9_login_y_causa_qml`, `test_t10_texto_cic10`, `test_t2_p5/p6`, `test_t7_*`, `test_t8_modo_sin_bd`, `test_u1/u2/u4/u8`, `test_ui_qml_app`, `test_v8a_barra_inferior_geometria`, `test_x1`, `test_reconocer_falla`, `test_ciclos_historial_puente`, `test_historial_alarmas`, `test_acciones_ciclos_puente`, `test_reporte_resumen_puente`, `test_navegacion_*`) | 616 passed, 4 failed: `test_i18n_linea_base` (de U10a, arreglado), 2 de `test_ui_bridge` (esperaban los roles sin `descripciones`; ajustadas), `test_v8b_textos::test_es_sin_anglicismos` («Cancel.» en es; cambiado a «Canc.») |
| 2.ª pasada: `test_ui_bridge`, `test_v8b_textos`, `test_i18n`, `test_i18n_linea_base`, `test_u10b_alarmas_idioma`, `test_u10b_textos_caben_qml`, `test_u10a_textos_caben_qml` | **443 passed** (86 s) |

No se corrió la suite completa (regla 8). Las otras 41 del primer grupo no dependen de los dos
textos ni de las dos pruebas cambiadas después.

## DECISIONES SIN CONFIRMAR

1. Las alarmas se TRADUCEN en la pantalla con los textos por idioma que el servidor ya incluye en
   el DTO (`textos`), no con claves i18n en QML. Si el DTO no los trae, se muestra la
   descripción registrada (español), como antes.
2. Filas de alarma en varias líneas (tarjeta de Preciclo y campana) en vez de abreviar: un motivo
   de seguridad no se abrevia. La tarjeta crece en alto; con muchas alarmas largas la lista
   desplaza (ya era un ListView).
3. «Canc.» en español (no «Cancel.», que el filtro de anglicismos de D8-5 rechaza).
   `abrev.reportes.col_cancelados` en inglés («Cancel.») existe pero hoy no se usa (cabe).
4. Historial: se cambiaron proporciones de columna en vez de abreviar, porque el texto que no
   cabía es un dato (nombre de programa), no una etiqueta.
5. En Reportes, los nombres de programa (datos) siguen achicándose si no caben; la prueba usa
   nombres reales de ejemplo («Instrumental 134», «Bowie & Dick») que caben.
6. Avisos QML previos y ajenos a textos, tolerados en la prueba: «Binding loop» en
   `OpcionesBitacora.qml:111` y `TypeError` en `OpcionesCalibracionSensor.qml` con el doble de
   sesión sin datos. No se tocaron.

## PREGUNTAS PARA CRISTIAN

1. En inglés, el motivo de CIC-10 sale traducido por la plantilla del catálogo; ¿el texto
   libre del motivo (que arma ProtocoloFallo) debe tener también su versión en inglés en todos los
   casos? En la captura sale bien, pero no se revisaron todos los motivos posibles.
2. En Reportes, la causa de fallo sale como código crudo (`FALLO_SECADO`) en los dos idiomas.
   No es un problema de ancho (fuera de D10-1), pero se ve en las capturas: ¿se traduce?
3. «Complet.» / «Canc.» / «Compl.»: ¿aceptables?

## Pendientes

- La alarma de arranque superpuesta de `Main.qml` (`FilaAlarma` sin `multilinea`, alto fijo)
  todavía tiene `elide`; con los textos actuales (≤ 55 caracteres) cabe, y no la cubre la prueba
  (necesita la intro en fallo). Se deja como está.
- `FilaAlarma` conserva `elide: ElideRight` cuando `multilinea` es false (solo lo usa ese caso).
- No se revisaron diálogos que solo aparecen con datos raros o errores de red (p. ej. correo
  rechazado) más allá de los pasos del banco CAP9 (R8, C9).

## Puntos de choque

`src/autoclave/i18n/es.json` y `en.json` (sección `abrev.reportes`, dentro de `abrev`),
`ui_bridge.py` (rol nuevo), `PantallaPreciclo.qml`, `PanelNotificaciones.qml`,
`ListaCiclos.qml`, `ResumenPeriodo.qml` (QML compartidos), `tests/test_i18n_linea_base.py`,
`tests/test_ui_bridge.py`, `tests/textos_caben_qml.py`, `tests/opciones_qml_banco.py`.
Sin cambios en `app.py`, `doble_pantalla.py`, `test_v8b_textos.py`, ni en lógica de ciclo,
puertas o estado seguro.
