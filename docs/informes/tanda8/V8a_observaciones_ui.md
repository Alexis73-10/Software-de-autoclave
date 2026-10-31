# V8a: observaciones de interfaz (tanda 8)

Rama `tanda-8-v8a` (worktree `.claude/worktrees/agent-ad7d3dc439dcc9b9f`), desde `tanda-8` (e1d8f5e).
Puntos: D8-5.1, 5.2, 5.3, 5.6, 5.7 (★), 5.8, 5.9 y 5.10 de `docs/mis_plans/decisiones_tanda_8.md`.

Pruebas corridas con `PYTHONPATH=<worktree>/src`. Paquete verificado:
`autoclave.__file__ = C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-ad7d3dc439dcc9b9f\src\autoclave\__init__.py`.

**Suite completa: NO corrida.** La sesión principal pidió explícitamente no correrla. Solo se corrieron las pruebas de los módulos tocados (ver abajo).

## Qué se hizo, por punto

| Punto | Qué | Commits |
|---|---|---|
| D8-5.3 | El botón del registro de mantenimiento dice "Registrar" / "Register". | 48adc72 |
| D8-5.1 | El recuadro Programa y el número del ciclo de Preciclo responden siempre. Si no se puede cambiar, la ventana muestra el motivo, tomado del catálogo. El backend (`ControlLoop`, motivo de no cambiar) ya no rechaza el cambio sin tarjeta o sin datos vigentes (`PARO_EMERGENCIA` sin `PARO_REAL`). Siguen bloqueando: ciclo en curso, paro leído (`PARO_REAL`), estado seguro / recuperación y modo prueba. FALLA permite el cambio. Elegir programa no acciona nada, y el inicio del ciclo sigue exigiendo todas sus condiciones. | ed6681d |
| D8-5.7 ★ | Tipo de carga Sólido/Líquido. Al pasar a Líquido, el modo de descompresión cambia a 4 si no era 4, 5 o 0. Al volver a Sólido, toma el defecto sólido del programa o el 1. El cambio y su arrastre van juntos, todo o nada, con bitácora (incluido el automático). Un modo no permitido con líquido se rechaza en el backend (`MODO_NO_PERMITIDO_LIQUIDO`, con su motivo). La UI ofrece solo los modos válidos, avisa del cambio automático con un texto del catálogo y muestra el motivo de cada rechazo. | 7f6833a, 27109cf; revisión: b3800d0, d498810, a83e447 |
| D8-5.8 | Todo parámetro "modo" (secado, descompresión o cualquiera con lista de modos del backend) se elige de una lista de modos válidos. Ya no se teclea. Catálogo `modos_programa` en es y en. | b2f6ee8 |
| D8-5.9 | La explicación de los modos es una lista, con una viñeta por modo (número, nombre y una línea). El modo elegido aparece resaltado, con la introducción de la sección y, con carga líquida, la nota de por qué solo quedan 4, 5 y 0. | 9233907 |
| D8-5.2 | La barra inferior flotante mide lo mismo que la tarjeta de encima en Login, Cambio de clave, Nuevo usuario, Preciclo, Ciclo en curso y Opciones. Prueba de geometría por pantalla en 1200x1920 y 1024x1638. | 2d60f91 |
| D8-5.10 | Barra flotante en todas las secciones de Opciones. Capturas en `docs/informes/tanda8/capturas/v8a/` (20 pantallas y secciones). | 2d60f91 (base), 01a1ae8 (capturas) |
| D8-5.6 | En Reportes › Resumen, cada causa de fallo se puede tocar (con flecha). Al tocarla se despliegan los ciclos del periodo con ese fallo (número, fecha, hora, programa y operador), 20 por página, con Anterior/Siguiente y "Página n de m". Al tocar un ciclo se abre su detalle (curva, imprimir y enviar por correo), igual que desde el Historial. "Volver" regresa al listado y "Volver al resumen" al resumen. Cambiar de periodo o cerrar la ventana cierra el listado. | df1cd02, b2bf54f |

### Detalle de D8-5.6

- Backend: nuevo `GET /report/failures?causa=&periodo=&fecha=&pagina=&por_pagina=`, de solo lectura. Usa el mismo criterio de periodo que `/report/summary` (fecha de inicio). Los ciclos salen del más reciente al más antiguo y con la misma forma que `/cycle/list`. Una página fuera de rango devuelve la última. `por_pagina` va de 1 a 100.
- `DbManager.get_ciclos_con_resultado(desde, hasta, resultado, limite, desplazamiento)` es solo una consulta. **No hay migración de base de datos.**
- Puente: `ReporteResumen.abrirFallo / moverPaginaFallo / cerrarFallo` y sus propiedades `causaFallo`, `ciclosFallo`, `paginaFallo`, `paginasFallo`, `totalFallo`, `cargandoFallo` y `sinConexionFallo`. Una respuesta que llega tarde se descarta.
- QML: `ResumenPeriodo` emite `causaElegida`. `ListaCiclos` tiene la nueva propiedad `conOperador`: la última columna pasa a ser Operador, porque en ese listado todos los ciclos tienen el mismo resultado. `MenuPrincipal` (ventanaReportes) incluye el listado, la paginación y el detalle del ciclo. La curva se pide al puente del Historial (`cargarGrafica` / `limpiarGrafica`).
- i18n: `menu.col_operador` y `reportes.ciclos_con_fallo / volver_resumen / pagina / pagina_anterior / pagina_siguiente / sin_ciclos_fallo`, en es y en.

## Pruebas

Pruebas nuevas:
- `test_v8a_textos.py` (1)
- `test_v8a_cambio_programa_sin_datos.py` (7)
- `test_v8a_tipo_carga_modos.py` (28)
- `test_v8a_parametros_ciclo_qml.py` (7)
- `test_v8a_barra_inferior_geometria.py` (2)
- `test_v8a_reportes_fallos_backend.py` (7)
- `test_v8a_reportes_fallos_puente.py` (6)

Pruebas existentes ampliadas o ajustadas:
- `test_menu_principal_pantalla_qml.py`: se agregó `test_reportes_ciclos_de_un_fallo`, con el recorrido completo causa → listado → detalle → imprimir → volver.
- `test_i18n.py`: se enumeran las familias dinámicas `modos_programa.` (de D8-5.8/5.9; antes quedaba sin enumerar y la prueba fallaba) y la columna `col_operador`.
- Ajustadas por el cambio de geometría o de comportamiento: `test_b6_selector_ciclo_ui.py`, `test_b1_barra_preciclo_ciclo_qml.py`, `test_barra_inferior_flotante_qml.py` y `test_u2_navegacion_qml.py`.

Resultados de la última corrida, con el worktree:
- `tests/test_v8a_*.py`, `test_b6_selector_ciclo_ui`, `test_b1_barra_preciclo_ciclo_qml`, `test_barra_inferior_flotante_qml`, `test_u2_navegacion_qml`, `test_i18n`, `test_i18n_linea_base` y `test_menu_principal_pantalla_qml`: **214 passed**.
- Reportes e Historial (`test_reporte_resumen*`, `test_ciclos_historial_puente`, `test_resumen_sistema_*`, `test_pdf_resumen`, `test_historial_alarmas`, i18n, menú principal QML): **244 passed**.
- `test_v8a_tipo_carga_modos` y `test_v8a_parametros_ciclo_qml`, tras la última corrección: **41 passed**.
- `test_t17_copia_programa` y `test_backend_autenticacion`, que usan el PATCH de parámetros: **99 passed**.

## Revisores de D8-5.7 (★)

Primera ronda (`safety-reviewer`, `timing-auditor`). Se corrigieron:
- TMG-01 (Crítico, anterior a D8-5.7): `_gestion` tomaba los locks en orden inverso al resto, lo que podía interbloquear el tick.
- TMG-02 (Alto): el PATCH no estaba serializado y la reversión pisaba cambios posteriores.
- SAF-05 / TMG-05: sin respuesta del backend, la pantalla no avisaba del cambio automático del modo.

Commit: b3800d0.

Re-revisión del timing-auditor: un Medio (la escritura del JSON quedaba fuera del todo o nada con la bitácora). Corregido en d498810.

Re-revisión final (esta sesión), con los dos revisores sobre el código actual. **Altos/Críticos abiertos: 0 en ambos.** Quedaron abiertos:
- **timing TMG-01, Medio.** Si la fase ya empezó, la reversión no alcanza a la copia del ciclo en curso. Mitigación mínima aplicada: ahora queda como error en el log (a83e447). La solución completa sigue abierta: aplicar al ciclo en curso solo después de registrar la bitácora.
- **timing TMG-02 a TMG-04, Bajos.** `duplicar` no toma `_lock_param_ciclo`. El `.bak` se pisa al revertir. `_gestion` hace fsync con `_sm_lock` tomado.
- **safety SAF-01, Medio.** Las filas de bitácora del cambio y del arrastre no van en una sola transacción de base de datos.
- **safety SAF-02, Medio.** Doble falla (bitácora y luego JSON al revertir) deja el valor en disco sin bitácora.
- **safety SAF-03, Bajo.** `descompresion.py` no tiene una segunda barrera en tiempo de ejecución para modo y carga líquida.
- **safety SAF-04, Bajo.** Los perfiles `cycles/defecto/` no se validan al cargar.

El safety-reviewer confirmó que todas las rutas por las que un programa líquido podría ejecutar un modo distinto de 4/5/0 están cerradas: PATCH, ciclo en curso, carga de JSON, `.bak`, migración, respaldo y duplicar.

**No hechos de la regla ★ (pendientes para la sesión principal):**
- No se repitieron celdas de transición con la planta simulada. D8-5.7 no toca transiciones del ciclo ni de las puertas: es configuración del programa, validada al guardar y al cargar.
- No se agregaron casos a la hoja de banco ni al registro de riesgos. `docs/riesgos/registro_riesgos.md` está en conflicto de fusión en la rama `tanda-8` principal, y se evitó agregar otro choque. Casos propuestos para el banco:
  1. Programa sólido con modo 1: pasar a Líquido → modo 4, con aviso y dos filas de bitácora.
  2. Con Líquido, intentar el modo 1 → rechazo con su motivo.
  3. Volver a Sólido → defecto del programa, o el 1.

  Riesgo propuesto: "descompresión rápida con carga líquida → ebullición violenta". Control: lista cerrada 4/5/0 en UI y backend, con validación al cargar.

## DECISIONES SIN CONFIRMAR

1. **D8-5.7:** al volver a Sólido, si el programa no tiene un defecto sólido (por ejemplo, Líquidos), el modo pasa a **1** (`MODO_SOLIDO_SIN_DEFECTO` en `catalogo_parametros.py`).
2. **D8-5.2:** el Menú Principal no tiene una tarjeta única, así que la barra se alinea con la grilla de tarjetas (de 54 a 1139 del lienzo).
3. **D8-5.1:** FALLA permite cambiar de programa. Solo bloquean el ciclo en curso, el paro leído, el estado seguro o la recuperación pendiente, y el modo prueba.
4. **D8-5.6:**
   - 20 ciclos por página.
   - En el listado de un fallo, la última columna muestra el Operador en lugar del Resultado, porque todos los ciclos comparten el resultado.
   - La causa se muestra con su código (por ejemplo, `FALLO_SECADO`), como ya lo hacía el resumen.
   - El periodo cuenta por fecha de inicio, igual que el resumen.
5. **D8-5.6:** la reimpresión desde el detalle usa la misma impresión y el mismo correo de ciclo que el Historial (`/cycle/history/print`, `enviarCorreo`).

## PREGUNTAS PARA CRISTIAN

1. ¿Confirmas el modo 1 al volver a Sólido sin defecto sólido? (D8-5.7)
2. ¿Las causas del resumen y del listado deben mostrarse traducidas (texto del catálogo de alarmas) en vez del código `FALLO_*`? Hoy el resumen ya mostraba el código. No se cambió.
3. ¿Las filas de bitácora de un cambio con arrastre deben ir en una sola transacción de base de datos (SAF-01)? Exige un método por lote en `db_manager.py`.
4. ¿Se agrega a `descompresion.py` una segunda barrera en tiempo de ejecución, para que con líquido y un modo fuera de 4/5/0 pase al modo 0 o 5, o termine en FALLO (SAF-03)? Toca una fase del ciclo, así que no se hizo sin orden.
5. Un ciclo recuperado tras una interrupción sin `tipo_carga` se fuerza a líquido, pero conserva el modo de su instantánea sin revalidarlo (`context.py:607-608`). ¿Esa ruta de recuperación debe exigir 4/5/0?

## Puntos de choque para la fusión

- `src/autoclave/backend/server.py`: PATCH `/cycle/parameter` (locks, reversión, arrastre), `_gestion` (orden de locks), nuevo `GET /report/failures` e import de `Query` de FastAPI.
- `src/autoclave/i18n/es.json` y `en.json`: claves de D8-5.1, 5.3, 5.7, 5.8 (`modos_programa`), 5.6 (`reportes.*`, `menu.col_operador`) y de la bitácora.
- `src/autoclave/services/domain/logging/db_manager.py`: un método de lectura nuevo, **sin migración**.
- `src/autoclave/services/domain/loop/control_loop.py`: motivo de no cambiar de programa (D8-5.1).
- `src/autoclave/core/managers/catalogo_parametros.py`, `cycle_manager.py` y `core/runtime/bitacora.py`.
- QML compartidos: `Componentes/BarraInferiorMenu.qml`, `ListaCiclos.qml` y `ResumenPeriodo.qml`; `Pantallas/MenuPrincipal.qml`, `Opciones.qml`, `OpcionesParametrosCiclo.qml`, `PantallaPreciclo.qml`, `PantallaCicloEnCurso.qml`, `Login.qml`, `CambioClave.qml` y `NuevoUsuario.qml`.
- Pruebas compartidas: `test_i18n.py`, `test_menu_principal_pantalla_qml.py`, `test_b6_selector_ciclo_ui.py`, `test_b1_barra_preciclo_ciclo_qml.py`, `test_barra_inferior_flotante_qml.py` y `test_u2_navegacion_qml.py`.

## Pendientes

- Suite completa (la corre la sesión principal).
- Solución completa del Medio de timing (aplicar al ciclo en curso después de la bitácora), SAF-01 y SAF-02.
- Hoja de banco y registro de riesgos (casos propuestos arriba).
- Repetición con la planta simulada, si la sesión principal la considera necesaria para D8-5.7.
