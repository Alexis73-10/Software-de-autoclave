# I4 — Terminar el inglés: parte de backend y salidas (Bloque 1) ★

Rama `tanda-6-i4` (desde `tanda-6`). La parte QML de I4 (literales QML, capturas de truncado en 1024 px) NO está en esta etapa: es del Bloque 2. R-06 se mantiene: no se agregó ningún selector de idioma para el operador.

## Hecho

### Motivos de puerta con código y parámetros (D-22, §3.9)
- `core/runtime/motivos.py`: `Motivo` es un `str` con el mismo texto en español de siempre, más `codigo` y `valores`. La lógica de puertas no cambia: quien compara, registra o concatena el motivo sigue viendo el mismo texto.
- Lo devuelven `ServicioPuertas`, `camara_segura.evaluar` y `AdvancedDoor.cmd_abrir/cmd_cerrar` (25 códigos, en `motivos.CODIGOS`).
- Textos en `i18n/<idioma>.json` → `puerta.<codigo>`. Una presión (`pres`, kPa abs) o una temperatura (`temp`, °C) se presentan en las unidades vigentes, con el módulo de unidades. En psi sin P_atm válida se muestra "—", nunca un número.
- El 409 `puerta_rechazada` agrega `motivo_codigo`, `motivo_valores` y `motivo_textos` (`{"es", "en"}`). `detail` sigue siendo el español. Esos campos se arman cuando `_sm_lock` ya está libre, porque leen del disco la configuración de unidades.
- `/status` agrega `camara_segura_motivo_codigo`, `_valores` y `_textos` (la QML puede usarlos en el Bloque 2).
- `DoorCommandService` muestra `motivo_textos[idioma vigente]` si viene; el "Error de comunicación" sale del catálogo.

### `motivo_fallo` con parámetros en la BD (§3.10)
- Migración **v7**: columna `ciclos.valores_fallo` (JSON, `''` en los ciclos anteriores). `motivo_fallo` (texto en español) y `codigo_fallo` no cambian.
- `CicloState._registrar_fallo` deja `estado.valores_fallo` (serializable; NaN/inf → null). No lanza: se conserva SAF-03.
- `CycleLogger` lo guarda en la BD y en el respaldo JSONL (`cierre.valores`). La reimportación del respaldo también lo guarda.
- `alarmas_i18n.motivo_fallo(codigo, valores, motivo, idioma)` arma "CÓDIGO · título: descripción" en el idioma pedido. Un ciclo antiguo o de texto libre conserva su motivo.

### Nombres de ciclo, roles y enums
- `nombre_clave` en los 4 `cycles/factory/*.json` (`ciclos_fabrica.<cycle_id>.nombre`). Es el único cambio en esos archivos. Los `cycles/user/*.json` no se tocaron (C1).
- `CycleManager.nombre_clave_de/nombres_de`: un ciclo de usuario usa la clave del de fábrica con el mismo `cycle_id` si no se renombró. Si se renombró, su nombre se muestra igual en los dos idiomas (§3.7).
- `/cycle`, `/cycles`, `/programas` y la lista del selector agregan `nombres: {es, en}`. `name`/`nombre` no cambian.
- Roles: `roles.<valor>` en el catálogo y `roles.etiqueta_rol()`. La pantalla Nuevo usuario muestra la etiqueta en el idioma vigente.
- Enums del panel de Información (D-17): `equipment_class` y `door_type` llevan `valorClave` → `equipo.clase_*` / `equipo.tipo_puerta_*`. PanelEquipo.qml ya lo soporta: no se tocó QML.

### Textos que Python entrega a QML
- El rótulo del periodo del Historial (días y meses) y la fecha del splash salen del catálogo (`fecha.dias`, `fecha.meses_largos`, `fecha.meses`).

### PDF y correo
- El PDF de ciclo y el consolidado se generan en el idioma de la UI y en las unidades del singleton `Unidades`:
  - el ticket embebido, con `format_ticket(…, p)`;
  - las series de la gráfica, la consigna y los rótulos de los ejes (`ui_qml/exportacion/unidades_pdf.py`).
- La cabecera del PDF de ciclo lleva el campo **Unidades** ("°F, psig" / "°C, kPa abs") y, si hay fallo, el **Motivo** traducido a partir del código y los parámetros.
- El correo (asunto y cuerpo) ya usaba el catálogo en el idioma vigente. El PDF de resumen no tiene magnitudes con unidad.

### Tickets
- **Arranque (I18N-18):** el estado de cada subsistema es un código (`ok`/`fallo`/`sin_datos`). "Sistema listo" / "FALLO EN ARRANQUE" se decide por el código y el rótulo se pone al imprimir, en es/en. Los textos antiguos ("OK", "FALLO", "ERROR", "Sin datos") se siguen aceptando.
- **Conectividad y resumen:** en es/en, según el idioma de `presentacion_actual()`. El resumen conserva sus 24 columnas.
- **cp437:** una prueba codifica en cp437 los tickets de arranque, conectividad y resumen en los dos idiomas. El de ciclo ya lo verificaba la prueba de I3.

## DECISIONES SIN CONFIRMAR
- **I4-1:** en el ticket de arranque, un valor de estado desconocido cuenta como FALLO (antes contaba como listo). Es lo más seguro y solo afecta al texto del ticket.
- **I4-2:** los nombres de fábrica van en una sección propia, `ciclos_fabrica.<cycle_id>.nombre`, y no en `ciclo.<cycle_id>.nombre` (como dice el plan §3.2). Así no se mezclan con los textos planos de la sección `ciclo`. Inglés propuesto: "Bowie & Dick", "Instruments 121°C/134°C", "Liquids" (sin revisar).
- **I4-3:** en psi, la gráfica del PDF usa psig en un solo eje continuo (negativo por debajo de la atmosférica), en vez de partirla en psig/inHg como el ticket. Sin P_atm válida, la serie de presión y la consigna no se dibujan.
- **I4-4:** las descripciones de alarma del motivo de fallo (PDF) siguen en las unidades de la plantilla del catálogo (°C/kPa), como las alarmas en pantalla (I1). Convertirlas exige marcar la clase de cada parámetro en las 49 plantillas: queda para revisión.
- **I4-5:** el ticket térmico sigue imprimiendo solo "código - título" del motivo (spec §5.4). Los parámetros se usan en el PDF.
- **I4-6:** las causas de fallo del ticket de resumen se imprimen con el código de resultado guardado, sin traducir.

## PENDIENTE
- Parte QML de I4 (Bloque 2): literales QML, uso de `motivo_textos`/`camara_segura_motivo_textos` y `nombres` en las pantallas, gráfica en vivo (`GraficaCiclo.qml`) en las unidades vigentes, capturas en 1024 px.
- Unificar las familias de códigos (D-22: `EMERGENCIA` ↔ `PARO_EMERGENCIA`…): no se hizo, porque toca la lógica de alarmas.
- Etiquetas del teclado (D-18).

## Pruebas
- `tests/test_i4_ingles_backend.py` (102):
  - cada alarma se dispara con AlarmManager y tiene texto es/en;
  - cada motivo de puerta tiene texto es/en con los mismos campos, y el conjunto declarado coincide con el usado en el código;
  - cada motivo de cámara segura se dispara con su código;
  - ServicioPuertas dispara los motivos con su código;
  - unidades, BD v7 y migración desde v6, `valores_fallo` en el estado;
  - nombres de fábrica, roles y enums, rótulo del periodo en inglés;
  - PDF (gráfica, consigna, unidades y motivo);
  - tickets en cp437.
- Se ajustaron dos pruebas existentes: la versión del esquema (7) y el 409 de puerta, que ahora trae campos extra.

## Revisión (safety-reviewer y timing-auditor)
Ningún hallazgo Crítico, Alto ni Medio. La lógica de seguridad no cambia: `Motivo` es el mismo `str`, y las condiciones, los umbrales y el orden del interlock quedan igual.
- **SAF-01 (Bajo), corregido:** `Motivo` no se podía copiar ni pasar por pickle. Se agregó `__reduce__`.
- **SAF-02 / TMG-02 (Bajo), abierto:** mientras la cámara no está segura, `/status` lee del disco el archivo de unidades en cada sondeo. No toma `_sm_lock`. Pendiente: guardar las unidades en caché.
- **TMG-01 (Bajo), corregido:** `valores_fallo` se asigna antes que `codigo_fallo`.
- **TMG-03 y TMG-04 (Bajo), abiertos:** la carga diferida de los catálogos i18n no tiene lock, y `Motivo.valores` es mutable. Hoy no causan problemas.
- E/S bajo lock en el endpoint de puertas: corregido antes de la revisión. El 409 se arma fuera de `guard_estado`.
