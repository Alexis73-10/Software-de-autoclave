# Reportes, parte 2: reporte consolidado del periodo

Fecha: 2026-10-06. Rama: `dev`, sin commit (espera tu revisión).

Diseño aprobado en el chat el 2026-10-06:
- todos los ciclos del periodo, sin filtro;
- solo por correo, sin térmica;
- consignas también en el PDF de un ciclo del Historial.

## 1. Qué hace

- **Pestaña nueva.** La ventana REPORTES tiene ahora las pestañas **Resumen** y **Consolidado**. El periodo (Diario / Semanal / Mensual con flechas) es **común a las dos**: al cambiar de pestaña se conserva.
- **Contenido de la pestaña Consolidado:**
  - cuántos ciclos tiene el periodo;
  - un texto que explica qué se enviará;
  - el botón **ENVIAR POR CORREO**, con la misma elección de destino.

  No tiene IMPRIMIR.
- **Avance.** Mientras trabaja, el aviso muestra el avance: "Preparando ciclo 3 de 40…", luego "Generando el PDF… 60 %" y al final el resultado.
- **Límite.** Si el periodo tiene más de **200 ciclos**, avisa que se elija uno más corto. Si no tiene ciclos, avisa y no envía nada.
- **El PDF**, uno solo, llamado `consolidado_<desde>_<hasta>.pdf`:
  1. **Portada:** el resumen del periodo (totales, barra, por programa, causas de fallo) y el **índice de ciclos** con Ciclo, Fecha, Hora, Programa, Resultado y la **página** donde empieza cada uno.
  2. **Cada ciclo**, del más antiguo al más reciente, con las mismas páginas del PDF del Historial: datos, gráfica y ticket completo, que puede ocupar varias páginas.
- **Consignas (D-14)**, en el consolidado **y en el PDF de un ciclo del Historial**:
  - Son dos líneas discontinuas, solo en el tramo de la fase de esterilización: la temperatura de esterilización guardada con el ciclo y su presión de vapor saturado (`p_saturacion_kpa`, la misma función del control).
  - No se dibujan si el ciclo no llegó a esterilizar, o si la temperatura falta o está fuera del rango válido de la función (99–145 °C).
  - La leyenda las muestra como "Consigna temp." y "Consigna presión".
- **Número de página del índice.** Las páginas de cada ciclo dependen de lo largo de su ticket, así que el PDF se dibuja dos veces: la primera, en memoria, para saber en qué página empieza cada ciclo, y la segunda con esos números.

No hay rutas nuevas en el backend. Se usan `/report/summary`, `/cycle/list` (con `fecha` y `limite`) y el ticket y la curva de cada ciclo.

## 2. Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/ui_qml/exportacion/pdf_consolidado.py` | nuevo | `generar_pdf_consolidado`: portada, índice y ciclos, en dos pasadas. |
| `src/autoclave/ui_qml/exportacion/pdf_ciclo.py` | modificado | `Documento` (escritor, pintor y número de página) y `dibujar_ciclo`, que usan el PDF de un ciclo y el consolidado; consignas en la gráfica y la leyenda. |
| `src/autoclave/ui_qml/exportacion/pdf_resumen.py` | modificado | `dibujar_resumen` (también es la portada del consolidado); `tabla` con alineación por columna. |
| `src/autoclave/ui_qml/exportacion/textos.py` | nuevo | Rótulos de los PDF de ciclo (antes estaban dentro del puente). |
| `src/autoclave/ui_qml/domain/consignas.py` | nuevo | `consigna_esterilizacion`. |
| `src/autoclave/ui_qml/bridge/acciones_ciclos.py` | modificado | `enviarConsolidado`, `progreso`; los datos de un ciclo se arman en un solo lugar (`_datos_ciclo`) y llevan su consigna. |
| `src/autoclave/ui_qml/qml/Pantallas/MenuPrincipal.qml` | modificado | Pestañas Resumen / Consolidado y avance en el aviso. |
| `src/autoclave/ui_qml/assets/textos/es.json` | compartido | Claves del consolidado y de las consignas en `exportacion` y `reportes`. |

## 3. Pruebas

- `tests/test_consignas_pdf.py` (nuevo): el tramo de esterilización, un ciclo que termina en esterilización y los casos sin consigna.
- `tests/test_pdf_consolidado.py` (nuevo, en subproceso): portada con la página 1 y cada ciclo en la suya, la página real de un ciclo que ocupa varias, y el avance.
- `tests/test_acciones_ciclos_puente.py` (pruebas agregadas):
  - consolidado en orden de inicio, con su índice, nombre de archivo y avance;
  - periodo sin ciclos, más de 200, sin backend y destino inválido;
  - consignas en el PDF de un ciclo.
- `tests/test_menu_principal_pantalla_qml.py` (+1): la pestaña Consolidado conserva el periodo, oculta el resumen y la impresión, y envía. Sigue sin avisos del motor QML.
- Revisé a ojo un consolidado de ejemplo de 10 ciclos (11 páginas), generado por el puente real con el backend de ejemplo.

Suite completa (`python -m pytest`, 2026-10-06): **1789 passed**, 0 fallos.

## 4. Pendientes

- **Parte 3, alarmas:** imprimir las alarmas activas y llevar un historial de alarmas. El historial necesita una tabla nueva y registrar las alarmas desde `alarm_manager` (máquina de estados): pasaría por el revisor de seguridad.
- **Rendimiento con equipo real:** no lo medí con un mes completo. Cada ciclo pide su curva al backend, y con 200 ciclos la generación puede tardar del orden de un minuto; el aviso de avance lo cubre.
- **Diseño provisional:** las pestañas y la vista del consolidado no tienen diseño del diseñador.

## 5. Corrección: los filtros conservan la fecha vista (2026-10-06, a pedido tuyo)

- **Antes:** al pasar de Mensual a Semanal o Diario, tanto en Historial como en Reportes, se volvía al periodo actual. Para llegar a un día de hace meses había que retroceder día por día.
- **Ahora:** los filtros conservan la fecha que se está viendo. Por ejemplo, con julio en Mensual:
  - Semanal muestra la semana del 1 de julio;
  - las flechas avanzan semana por semana;
  - Diario muestra el día en que empieza la semana elegida.
- **Al abrir la ventana** se sigue empezando por hoy.
- **Archivos:** `NavegadorPeriodo.cambiar()` y el slot `cambiarPeriodo` en `CiclosHistorial` y `ReporteResumen`; los filtros de `MenuPrincipal.qml` lo usan.
- **Pruebas:** +3 en el puente del Historial, +1 en el de Reportes y +1 en QML.
- **Suite completa:** **1794 passed**, 0 fallos.
