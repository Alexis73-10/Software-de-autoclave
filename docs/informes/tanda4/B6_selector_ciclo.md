# B6 — Selector de ciclo en Preciclo

## Hecho
- **Recuadro "Programa" tocable** (`PantallaPreciclo.qml`, zona 351–839 × 219–384 del mockup): con texto de ayuda "Toque para cambiar de ciclo" (es/en) visible solo cuando es tocable. Tocable únicamente con datos vigentes, estado de máquina PREPARACION o PREPARADO (reposo/preciclo), sin estado seguro (activo o pendiente de confirmar), sin paro y sin modo prueba. En CICLO (y FALLA, EMERGENCIA, sin conexión…) no es tocable: sin efecto y sin ventana.
- **Ventana flotante** (reutiliza `VentanaFlotante.qml`): una fila por programa con número, nombre y "temperatura °C · tiempo min"; el programa activo resaltado; los 3 más usados primero con la marca "• Más usado". Se puede cerrar sin cambiar (X o tocar fuera). Las filas se atenúan y no responden si el backend dice que hoy no se puede cambiar, y la ventana muestra el motivo textual del backend.
- **Backend** `GET /programas/seleccionables` (solo lectura, sin sesión): lista ya ordenada con `mas_usado`, `seleccionado`, `seleccionable` y `motivo` (la misma regla `_motivo_no_cambiar_ciclo` que usa `/cycle/select`). Conteo desde el historial: `DbManager.conteo_ciclos_por_programa()` (columna `numero_programa`).
- **Orden:** los 3 programas con más ciclos terminados (mayor→menor; empate por número predefinido) marcados, luego el resto por número. Sin historial, con menos de 3 programas con historial (se marcan solo esos) o sin base de datos / base que falla → orden predefinido sin marcas. Solo se listan programas de usuario ejecutables (los 4 predefinidos están sembrados como copias de usuario; los programas de usuario adicionales de C2 entran solos); no se listan dañados ni, sin capacidad de líquidos, el de Líquidos.
- **Elegir:** `POST /cycle/select` con `origen` = `puerta_1`/`puerta_2` (mismo endpoint y mismo origen declarado que ya existía; no se inventó otro camino). Éxito → cierra la ventana, refresca el caché de `/cycle` al instante (`UIServiceBackend.refrescar_cache()`) y el programa queda como predeterminado (persistente, `set_default_cycle`). Rechazo del backend → se muestra su `detail`; sin respuesta → "Sin respuesta del equipo".
- **Sesión:** `/cycle/select` hoy NO exige sesión (decisión 2 de Cristian, 19-oct); el selector tampoco. Anotado.
- Puente `ui_qml/bridge/selector_ciclo.py` (`SelectorCiclo`), cableado en `app.py` y `Main.qml`.

## Pruebas
`tests/test_b6_selector_ciclo_backend.py` (15: orden con/sin historial, empates, <3 con historial, abortados sí / en curso no, sin BD, BD que falla, parámetros por fila, seleccionado, dañados/fábrica/líquidos, programas de usuario extra, seleccionable+motivo, solo lectura) y `tests/test_b6_selector_ciclo_ui.py` (11: puente con lista, motivo, backend caído, elegir con origen de la puerta, rechazo, sin respuesta, respuesta vieja, filas mal formadas, refresco del caché; pantalla: tocable solo en reposo y bloqueada en ciclo/estado seguro/pendiente/paro/modo prueba/sin conexión/falla; la ventana abre, lista 4 filas y elegir hace el POST y cierra).
Capturas: `B6_selector_ciclo.png` (con historial: 3 y 2 marcados "Más usado") y `B6_selector_ciclo_sin_historial.png` (orden predefinido, sin marcas).

## DECISIONES SIN CONFIRMAR
1. El conteo incluye todos los ciclos terminados (completos, abortados y con fallo), no los que siguen en curso. Alternativa: solo COMPLETADO (cambiar el `WHERE` de `conteo_ciclos_por_programa`).
2. Los ciclos anteriores a la columna `numero_programa` (tandas previas) no cuentan.
3. FALLA no permite cambiar de programa desde este selector (el backend sí lo permite: decisión 2 del 19-oct). Alternativa: agregar "FALLA" al conjunto de estados tocables.
4. Diseño de la ventana PROVISIONAL (sin mockup).
