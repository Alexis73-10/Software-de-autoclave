# R1 — Hallazgos Medios y Bajos pendientes (tandas 4, 5 y 6)

Recorrido: `docs/informes/tanda4/`, `docs/informes/tanda5/`, `docs/informes/tanda6/` (T2, C1, I4, X1, W1, D1) e índices `informe_tanda_2026-10-20_t4.md`/`_t5.md`. Solo se listan hallazgos de revisores (safety, timing, sensor-role) que quedaron **abiertos** en su informe; los marcados "corregido" allí no se repiten.

Criterio: se corrigen los de bajo riesgo que no cambian la lógica de seguridad, con prueba primero (`tests/test_r1_hallazgos_bajos.py`). Los que tocan transiciones, actuadores o seguridad quedan como **PREGUNTA PARA CRISTIAN** con recomendación. Los de pantallas Preciclo/Ciclo/BarraInferiorMenu no se tocan (B1 trabaja en paralelo).

## Tabla

| Id | Origen | Sev. | Estado |
|---|---|---|---|
| SAF-04 | t4 B8 (`exit_test_mode` descarta el ACK del ALL_OFF) | Bajo | **Abierto, PREGUNTA R1-P1**: cambia el contrato de `ControlLoop.exit_test_mode` |
| TMG-06 | t4 B7 (aviso periódico y validación al reconectar comparten operación) | Bajo | Abierto, aceptado: solo experiencia de uso, el backend rechaza con 401 |
| TMG-07 | t4 B8 (timer de inactividad del modo prueba saca a sesión nueva) | Bajo | Cerrado en t5 P1 (`_generacion_prueba`) |
| TMG-08 | t4 B7/B8 (bitácora sin usuario) | Bajo | Cerrado en t5 E0 (`quien_fue`) |
| SAF-M1 | t4 B3 (reloj adelantado hasta reiniciar) | Medio | Aceptado en t4 (mensaje pide reiniciar); sin cambio |
| SAF-M2/M3 | t4 B3 (auditoría tras la acción) | Medio | Aceptado en t4; sin cambio |
| B3-Bajos | t4 B3 (umbral 1 día, OSError como 500, etc.) | Bajo | Aceptados en t4; sin cambio |
| SAF-05 (O1) | t5 O1 (`server.py` itera `cycles.values()` sin copia) | Bajo | **Corregido R1**: todas las iteraciones usan `list(...)` |
| SAF-06 (O1) | t5 O1 (`.bak` sin actualizar en habilitado y entradas) | Bajo | Abierto: depende del diseño de respaldo de O2; sin riesgo de control |
| SAF-07 (O1) | t5 O1 (`editable` de display-inputs sin rol ni estado) | Bajo | Abierto: la UI ya combina con `edicionPermitida` y el backend valida al guardar |
| O1-2 | t5 O1 (escrituras de archivo dentro del lock de máquina) | Medio | DECISIÓN SIN CONFIRMAR de t5; sin cambio |
| SAF-03 (P3) | t5 P3 (secado guardado a medias si se cancela el login) | Bajo | Abierto: PySide, flujo de guardado por partes; requiere rediseño |
| SAF-04 (P3) | t5 P3 (encabezado sigue mostrando usuario al caducar) | Bajo | Abierto: PySide, cosmético |
| SAF-05 (P3) | t5 P3 (renovación en hilo de UI, hasta 2 s) | Bajo | Abierto: mover a hilo exige reestructurar la ventana PySide |
| TMG-02 (P1) | t5 P1 (bloqueo de UI en logout) | Medio | Acotado a 0,5 s en t5; sin cambio |
| T1-01-C | t5 T1 (`mantener_presion_camara` dos veces por tick en PREPARADO; debounce del aire avanza de a 2) | Medio | **Abierto, PREGUNTA R1-P2**: actuadores/debounce |
| SEN-02 (T1) | t5 T1 (lógica de "carga líquida" duplicada con `_carga_liquida`) | Bajo | Abierto: refactor de la fuente de verdad de líquidos; no en la noche previa a la instalación |
| SAF-03 (U1) / Bajo 2 (C1) | t5 U1, t6 C1 (`rango_calentamiento` es banda de temp y de presión; unidad "kPa" engañosa) | Bajo | **Abierto, PREGUNTA R1-P3** (ya estaba como pregunta en U1) |
| Bajo 3 (C1) | t6 C1 (clase válida pero equivocada en JSON editado a mano) | Bajo | Abierto: solo visual; el JSON de fábrica está probado |
| SAF-05 (C1) | t6 C1 (contraseña vacía: Confirmar no avisa) | Bajo | Abierto: PySide, cosmético |
| SAF-02/TMG (T2) | t6 T2 (timers de fase, incluida la exposición, corren durante la tolerancia de DI) | Medio | **PREGUNTA ya abierta en T2** (exposición); sin cambio |
| SAF-03 (T2) | t6 T2 (DESPEJAR no comprueba que la causa haya desaparecido) | Medio | **PREGUNTA ya abierta en T2**; sin cambio |
| SAF-05 (T2) | t6 T2 (Principal perdido tras protocolo ya ejecutado no pasa a `solo_lenta`) | Medio | **Abierto, PREGUNTA R1-P4**: transición de seguridad |
| SAF-06 (T2) | t6 T2 ("no estéril" solo en INTERRUMPIDO) | Bajo | **PREGUNTA ya abierta en T2**; sin cambio |
| SEN-03 (T2) | t6 T2 (sin `programas_seguridad`, P-12 mide el programa seleccionado) | Bajo | Abierto: todos los perfiles actuales lo traen; incluido en R1-P4 |
| T2-lock | t6 T2 (`ack_confirma_estado_seguro` sin lock) | Bajo | Abierto, aceptado: solo afecta el texto del diálogo en un tick |
| T2-salidas | t6 T2 (durante la tolerancia no se tocan escape ni vacío) | Bajo | Incluido en la pregunta de exposición de T2 |
| T2-409 | t6 T2 (texto del 409 de abort durante la tolerancia) | Bajo | **Abierto, PREGUNTA R1-P5**: el rechazo mismo (no poder cancelar 4 s) es de transición |
| T2-alias | t6 T2 (alias `DISTINTO_DE_CICLO_E_HIBERNACION`, docstring, manejador muerto en `Main.qml`) | Bajo | Conservado por T2-6; sin cambio |
| SAF-02/TMG-02 (I4) | t6 I4 (`/status` lee `unidades.json` del disco en cada sondeo) | Bajo | **Corregido R1**: `ConfigUnidades.leer` cachea por (mtime, tamaño); `guardar` invalida |
| TMG-03 (I4) | t6 I4 (carga diferida de catálogos i18n sin lock) | Bajo | **Corregido R1**: doble chequeo con `_lock_carga` |
| TMG-04 (I4) | t6 I4 (`Motivo.valores` mutable) | Bajo | **Corregido R1**: `MappingProxyType` de una copia |

Resumen: 31 filas; 4 corregidos en R1, 2 ya cerrados en tandas previas, 25 siguen abiertos (8 aceptados o decididos antes, 6 con pregunta, 11 abiertos de bajo impacto).

## Correcciones R1
Prueba: `tests/test_r1_hallazgos_bajos.py` (7 casos; 4 en rojo antes del cambio).
- `src/autoclave/backend/server.py`: 5 iteraciones de `cycle_manager.cycles` con `list(...)`.
- `src/autoclave/core/runtime/unidades.py`: caché de `ConfigUnidades.leer`; sigue detectando ediciones externas y archivo borrado; devuelve copias.
- `src/autoclave/i18n/__init__.py`: `_todos()` carga una sola vez aunque entren varios hilos.
- `src/autoclave/core/runtime/motivos.py`: `valores` de solo lectura; `__reduce__` y `valores_json` siguen igual.

Ninguna toca actuadores, fallas, umbrales ni transiciones.

## PREGUNTAS PARA CRISTIAN
- **R1-P1 (SAF-04 t4):** ¿auditar si el ALL_OFF de la salida del modo prueba fue confirmado por la tarjeta? *Rec.:* sí. Que `exit_test_mode` devuelva el ACK y se anote en la bitácora, sin cambiar qué se apaga.
- **R1-P2 (T1-01-C):** `mantener_presion_camara` corre dos veces por tick en PREPARADO y el debounce del aire avanza de a 2. *Rec.:* que `esta_preparado()` use el resultado del tick y no vuelva a llamar el control. Pide banco (el aire cerraría a los 3 ticks reales, no a 1,5).
- **R1-P3 (`rango_calentamiento`):** *Rec.:* separarlo en `rango_calentamiento_temp` (°C) y `rango_calentamiento_pres` (kPa), con el mismo valor por defecto, en una tanda con banco.
- **R1-P4 (SAF-05/SEN-03 T2):** si el protocolo de fallo ya corrió por otra causa y después se pierde el Principal, ¿debe pasar a `solo_lenta`? *Rec.:* sí. Es el criterio de P-2 aplicado sin importar el orden.
- **R1-P5 (409 de abort en tolerancia DI):** hoy, durante los 4 s, el abort responde 409 "sin datos de la tarjeta". *Rec.:* aceptar la cancelación (la marca se procesa al volver los datos o al vencer la tolerancia) o, como mínimo, un texto "espere unos segundos". Es de transición, no se cambió.

## Revisión
safety-reviewer sobre el diff: sin Críticos ni Altos. Bajo: carrera entre `leer()` y `guardar()` (podía cachear la firma vieja) y misma firma en FAT (resolución de 2 s). **Corregido:** `leer()` toma la firma antes de leer y todo bajo `_lock`. El caso FAT queda aceptado (el equipo usa NTFS). Confirmado que `alarmas_i18n.valores_json` devuelve un `dict` nuevo, así que el proxy de `Motivo.valores` no llega a `json.dumps`.
