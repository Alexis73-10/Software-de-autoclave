# Tanda 10: decisiones sin confirmar y preguntas

## DECISIONES SIN CONFIRMAR
- **A0-1:** los 2 commits de la Entrega E (376eeb5, cafb06e, en `tanda-9` sin push) se unieron a `tanda-10` porque la compilación los necesita.
- **A0-2:** la compilación de esta tanda se llama **F** (la E ya existía con etiqueta, entrega y Setup en la USB; reusarla exigía `--force`).
- **A0-3:** la suite de integración de G10+W10+T10+U10a se corrió una sola vez para las cuatro uniones.
- **K10-1:** `pytest-xdist` instalado en el Python del proyecto pero NO agregado a `requirements-dev.txt` (§2.1). Se recomienda agregarlo si la suite en paralelo se adopta para siempre.
- **K10-2:** el Setup F lleva la versión por línea de órdenes (`/DAppVer=1.0.0-f /DAppVerNum=1.0.0.6`), como la E; los valores por defecto de `autoclave.iss` siguen en la D.
- **K10-3:** el LEEME de la E, que solo existía en la entrega, se versionó en `docs/instalacion/` con las secciones de la F.
- **K9-1 (se mantiene):** casilla de estación DESMARCADA en el equipo de pruebas.
- **G10:** recorte a 12 caracteres después de normalizar; el campo del asistente sigue con `maximo: 12` (con guiones no cabe; el generador no los muestra).
- **T10:** el motivo cambió en el literal de `ProtocoloFallo.bloqueado_motivo` (solo texto, misma condición y prioridad); la acción variante empieza con «No abra la puerta.»; la tarjeta de Preciclo y la campana siguen sin mostrar la acción.
- **W10:** la pantalla 2 la cierra el lanzador al terminar el asistente (`AUTOCLAVE_EXE_UNICO=1`); en `doble_pantalla` (desarrollo) sale con código 3 sin relanzarse; la pantalla 2 de Reposo no se vigila durante el asistente; aspecto del aviso sin referencia del diseñador.
- **U10a:** convención `abrev.<ruta completa>`; margen de 4 px; abreviaturas distintas de las sugeridas donde no cabían (es «Temp. referencia», «Temp. dren. cám.», «Pres. chaq.», «Pres. emp. 1/2»; en «Reference temp.», «Chamber temp. 2», «Chbr. drain temp.», «Gskt. press. 1/2»); probadas a 1024x1638 y 1200x1920.
- **U10b:** las alarmas se traducen con los `textos` por idioma que ya manda el servidor (si faltan, español como antes); filas de alarma en varias líneas en vez de abreviar un motivo de seguridad; «Canc.» en español; Historial con columnas reproporcionadas en vez de abreviar datos; nombres de programa en Reportes aún se achican si no caben; dos avisos QML ajenos tolerados en la prueba.

## PREGUNTAS PARA CRISTIAN
1. (U10a) ¿Son aceptables «Chbr.» y «Gskt.» en inglés, o se mueve la etiqueta de presión (cambia el mockup)?
2. (U10b) ¿Todo motivo de texto libre de ProtocoloFallo debe tener versión en inglés? CIC-10 sí la tiene; no se revisaron todos.
3. (U10b) En Reportes la causa de fallo sale como código crudo (`FALLO_SECADO`) en ambos idiomas: ¿se traduce?
4. (U10b) «Complet.» / «Canc.» / «Compl.» en el encabezado de Reportes: ¿aceptables?
5. (K10) `entrega/drivers/` sigue vacía: ¿el PC del equipo necesita el controlador del puerto serie de la tarjeta?
