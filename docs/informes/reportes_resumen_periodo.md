# Reportes, parte 1: resumen de ciclos por periodo

Fecha: 2026-10-06. Rama: `dev`, sin commit (espera tu revisión).

Diseño aprobado en el chat el 2026-10-06. Reportes se divide en tres partes, en este orden: **resumen por periodo** (esta), reporte consolidado y alarmas.

## 1. Qué hace

- La tarjeta **Reportes** del menú ya está habilitada y abre la ventana "REPORTES". Por ahora tiene una sola pestaña, **Resumen**; el consolidado y las alarmas se agregarán como pestañas nuevas.
- **Periodo.** Diario / Semanal / Mensual de calendario, con flechas, igual que en el Historial.
- **Totales.** Ciclos del periodo, Completados, Con fallo, Cancelados y Sin cierre, cada uno con su porcentaje, y una barra de proporciones con los colores de cada resultado.
- **Qué es "Sin cierre".** Son los ciclos sin resultado guardado: el ciclo en marcha o un proceso que se interrumpió.
- **Por programa.** Una tabla con Total, Compl., Fallo, Cancel. y Sin cierre, ordenada de más a menos ciclos.
- **Causas de fallo.** Cada causa con su cantidad, de la más frecuente a la menos (por ejemplo FALLO_ESTERILIZACION o EMERGENCIA). Si no hay fallos, aparece "Sin fallos en el periodo".
- **Criterio.** Los ciclos se cuentan **por fecha de inicio**, como en el Historial, y se agrupan con la misma regla del resto del sistema (`progreso_ciclo.resultado`).
- **IMPRIMIR.** Imprime un ticket de 24 columnas con estos datos:
  - periodo (desde / hasta), serie, modelo, fecha y hora de impresión;
  - totales con porcentaje;
  - el desglose por programa y las causas de fallo.

  Tiene las mismas reglas que la reimpresión de ciclos: se rechaza durante un ciclo y avisa si la impresora no está lista.
- **ENVIAR POR CORREO.** Envía un PDF A4 con el encabezado del equipo, el periodo, los totales, la barra y las dos tablas, a los mismos destinos que el Historial.
- **Sin conexión.** Si no hay conexión con el equipo, la ventana muestra "Sin conexión con el equipo" y los botones quedan deshabilitados.

## 2. Backend

- `GET /report/summary?periodo=dia|semana|mes&fecha=` devuelve el periodo, desde/hasta, serie, modelo, totales, por programa y causas de fallo. Se calcula con un conteo agrupado en la base (`DbManager.get_conteo_resultados`), así que no tiene límite de filas.
- `POST /report/summary/print` con `{periodo, fecha}`.
- Las dos rutas de impresión comparten ahora `_encolar_en_impresora()` (409 durante un ciclo, 503 si la impresora no está lista).

**Recuerda reiniciar el backend** para que existan las rutas nuevas.

## 3. Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/services/domain/reportes/resumen_periodo.py` | nuevo | `resumir()` y `format_ticket_resumen()`. |
| `src/autoclave/services/domain/logging/db_manager.py` | compartido | `get_conteo_resultados(desde, hasta)`, solo lectura. |
| `src/autoclave/backend/server.py` | compartido | Las dos rutas nuevas y `_encolar_en_impresora`. |
| `src/autoclave/ui_qml/domain/navegador_periodo.py` | nuevo | Periodo elegido con flechas; lo usan el Historial y Reportes (antes estaba dentro de `ciclos_historial.py`). |
| `src/autoclave/ui_qml/domain/reporte_resumen.py` | nuevo | Formateo del resumen para la pantalla y el PDF. |
| `src/autoclave/ui_qml/bridge/reporte_resumen.py` | nuevo | Puente `ReporteResumen`. |
| `src/autoclave/ui_qml/bridge/acciones_ciclos.py` | modificado | `imprimirResumen` y `enviarResumen`; las rutas de impresión y correo comparten el manejo de errores. |
| `src/autoclave/ui_qml/exportacion/pdf_resumen.py` | nuevo | PDF del resumen. |
| `qml/Componentes/BotonPildora.qml`, `SelectorPeriodo.qml`, `SelectorDestino.qml`, `AvisoAccion.qml` | nuevos | Piezas que antes estaban dentro de la ventana Historial y ahora comparten Historial y Reportes. |
| `qml/Componentes/ResumenPeriodo.qml` | nuevo | Vista del resumen (totales, barra, tablas); se desplaza si no cabe. |
| `qml/Pantallas/MenuPrincipal.qml` | modificado | Ventana Reportes, tarjeta habilitada (sale `TODO(MP-04)`) e Historial con los componentes compartidos. |
| `Main.qml`, `app.py`, arnés (`PruebaMenuPrincipal.qml`, `prueba_menu_principal.py --ventana reportes`, `historial_ejemplo.py`) | modificados | Crean y pasan `reporte`; el backend de ejemplo calcula el resumen sobre sus ciclos de ejemplo. |
| `assets/textos/es.json` | compartido | Sección nueva `reportes` y claves del resumen en `exportacion`. |

## 4. Pruebas

- `tests/test_reporte_resumen.py` (nuevo): conteo agrupado dentro del periodo, totales, por programa, causas, programa sin número, ticket de 24 columnas y periodo sin ciclos.
- `tests/test_backend_cycle_summary.py` (pruebas agregadas): resumen de un mes, periodo por defecto, periodo inválido, impresión, y rechazo con 409 y con 503.
- `tests/test_reporte_resumen_puente.py` (nuevo): formateo, consulta, flechas, sin conexión, sin ciclos y respuesta tardía.
- `tests/test_acciones_ciclos_puente.py` (pruebas agregadas): imprimir el resumen, impresora desconectada, envío del PDF, envío sin backend y destino inválido.
- `tests/test_pdf_resumen.py` (nuevo, en subproceso): una página, muchos programas en varias páginas y periodo sin ciclos.
- `tests/test_menu_principal_pantalla_qml.py`: la tarjeta Reportes queda habilitada; tres pruebas nuevas (periodo y datos, imprimir y enviar, sin conexión). Sigue sin avisos del motor QML.

Suite completa (`python -m pytest`, 2026-10-06): **1771 passed**, 0 fallos.

## 5. Pendientes

- **Parte 2, reporte consolidado.** Para las líneas de consigna de la gráfica (D-14) hace falta definir qué consignas se guardan con cada ciclo.
- **Parte 3, alarmas.** El historial de alarmas necesita una tabla nueva y registrar las alarmas desde `alarm_manager`, que toca la máquina de estados; pasaría por el revisor de seguridad.
- **Diseño provisional.** La ventana, la pestaña, las tablas y la barra de proporciones no tienen diseño del diseñador.
