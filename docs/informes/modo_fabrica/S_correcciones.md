# Modo fábrica: correcciones de la revisión de seguridad (SAF-01..08)

Fecha: 22-nov-2026. Rama `modo-fabrica`. Hallazgos en `S_revision_seguridad.md`. TDD: las pruebas nuevas (`tests/test_fab_s_cierre.py`, `tests/test_fab_s_correcciones.py`) se escribieron primero; contra el código anterior fallaban 26 de las 28 de la fase 2.

Cada decisión marcada `DECISIÓN SIN CONFIRMAR` espera a Cristian.

## SAF-01 (ALTA): la fase 2 valida antes de borrar

**Cambio (`core/runtime/cierre_fabrica.py`).** Antes del primer paso, `_validar_marca` comprueba lo siguiente.

- **La marca:** es legible, tiene `formato == 1`, `hash_paquete` es un hex de 64 en minúsculas, `fecha` es ISO legible, y las listas de pasos son listas.
- **Con `base` pendiente y `.nueva` presente:**
  - `.nueva` pasa `PRAGMA integrity_check` y está en ENTREGADO con el mismo hash y la misma fecha que la marca.
  - La base vigente está en FÁBRICA. Si un corte a mitad del reemplazo ya la había apartado, se mira `.vieja`.
- **Con `base` hecho**, o con `base` pendiente y sin `.nueva` (la base se reemplazó pero la marca no se actualizó):
  - La base vigente está en ENTREGADO con ese hash y esa fecha.
  - Tiene 0 ciclos.
  - Tiene la fila `equipo_liberado_fabrica` y ninguna fila de bitácora posterior a ella.

Las bases se leen con `sqlite3` en URI `mode=ro`, que nunca crea la base. Hay una prueba de eso.

**Si algo no valida:**
- No se borra nada.
- La marca se renombra a `cierre_fabrica.json.rechazada-AAAAMMDD-HHMMSS`. Si ya existe uno, se usa `-1`, `-2`…, sin sobrescribir.
- El motivo va al log y el arranque sigue normal.

**Base que no se puede abrir** (bloqueada, sin permisos): no se borra nada, la marca se conserva y el arranque queda detenido (SAF-02). Así un fallo transitorio no hace perder un cierre legítimo.

**Retirado:** «marca ilegible = repetir todo». La prueba E5 `test_p08_marca_ilegible_completa_igual` pasa a `test_p08_marca_ilegible_se_rechaza_sin_borrar`. El fixture de E5 ahora deja el equipo realmente en FÁBRICA (`entrar_modo_fabrica_e_instalar`); antes quedaba en ENTREGADO por omisión. Además fecha los respaldos de ciclos antes de la marca.

**Sello HMAC de la marca: no se implementó** (`DECISIÓN SIN CONFIRMAR`). La validación ya exige que el hash y la fecha coincidan con la base. Si `base` está hecho, exige además una base sin uso. Un sello con una clave derivada de K_t (común y legible en el equipo, AUT-R1) solo añadiría freno a la edición casual, y complicaría el cierre en desarrollo sin K_t.

**Pruebas (`test_fab_s_cierre.py`):**
- Marca vacía o parcial en un equipo ENTREGADO con ciclos y respaldos: nada se borra y la marca queda rechazada (5 casos).
- Dos rechazos no se sobrescriben.
- Marca legítima copiada a un equipo que ya operó: rechazada por ciclos.
- Bitácora posterior a la liberación: rechazada.
- `.nueva` fabricada en FÁBRICA: rechazada.
- Hash distinto y fecha distinta: rechazadas.
- Base vigente que no está en FÁBRICA: rechazada.
- Base no verificable: bloquea, y al reintentar termina.
- La validación no crea la base.
- El cierre legítimo sigue funcionando, y las pruebas de E5 siguen verdes.

## SAF-02 (ALTA): un cierre pendiente que no termina detiene el equipo

**Cambio.**
- **Fin del modo sin base:** ya no se escribe la `BD_BLOQUEADA` propia que dejaba el equipo en modo sin base (con ciclos). `_desbloquear_base` sigue retirando una de antes, si la hay.
- **Estado de la fase 2:** queda en `_ESTADO_FASE2`. `cierre_incompleto()` devuelve ese resultado si la fase 2 corrió en el proceso. Si no corrió, devuelve si existe la marca (falla cerrada).
- **Arranque detenido:** `BackendContext.verificar_instalacion` (etapa 1) lanza `ErrorArranque(ARR_CIERRE_FABRICA)` antes de leer nada más. Ese es el mecanismo de fallo bloqueante del arranque: no se construye el `ControlLoop` y todo salvo `/arranque` responde 503, así que no hay ciclos.
- **Código nuevo:** `ARR_CIERRE_FABRICA` está en `backend/arranque/secuencia.py` y en `docs/catalogo_alarmas.md`.
- **Pantalla:**
  - `ProgresoArranqueBackend.codigoFallo` publica el código de la etapa fallida (función `codigo_fallo`).
  - `Main.qml` y `detalle_aviso._textos_arranque` muestran «Fallo de arranque: Cierre de fabricación incompleto: reinicie el equipo; si persiste, contacte a Especifika».
  - En inglés: «Factory closing incomplete: restart the equipment; if it persists, contact Especifika».
  - La acción del detalle es `aviso_detalle.arranque.accion_cierre_fabrica`.
- **Defensa en profundidad:**
  - `respaldo_ciclos` no borra archivos con fecha de modificación posterior a la `fecha` de la marca. Los conserva en su sitio y lo anota en el log como error.
  - `contadores` no toca `ciclo_contador.json` ni `mantenimiento_base.json` si la base vigente tiene ciclos. `numeros_usados.json` sí se ajusta.

**Pruebas:**
- `cierre_incompleto` sin fase 2 en el proceso.
- Paso crítico fallido: bloquea sin `BD_BLOQUEADA`.
- La etapa 1 lanza `ARR_CIERRE_FABRICA`.
- `ejecutar_arranque` no construye el control y publica el código.
- Respaldo posterior conservado.
- Contador que no baja.
- Textos es/en, `codigo_fallo`, `detalle_aviso` y `Main.qml` (en `test_fab_s_correcciones.py`).

**Residual:**
- Un respaldo posterior conservado se reimportará en la base nueva al arrancar, como un ciclo de la base entregada. Es preferible a borrarlo; queda en el log.
- Con el bloqueo, el equipo no opera hasta que un reinicio complete el cierre o un técnico intervenga. Es la dirección segura.
- No se verificó en pantalla real (solo la prueba de texto de `Main.qml`).

## SAF-03 (MEDIA): marca que no se actualiza o no se borra

**Cambio.**
- `_guardar_marca` lanza `_MarcaNoGuardada`. Si falla tras un paso, la fase 2 se corta: el paso queda como pendiente y el arranque bloqueado (SAF-02). En el arranque siguiente el paso se repite tras validar: si era `base`, se valida como base hecha.
- `_quitar_marca`: si el `unlink` final falla, se renombra a `cierre_fabrica.hecho`. Si eso también falla, la marca queda con todos los pasos hechos y el arranque siguiente solo intenta quitarla, sin validar ni repetir nada.
- Una marca vieja que dijera que quedan pasos se rechaza porque la base tiene ciclos o bitácora posterior a la liberación.

**Pruebas (con fallos inyectados):**
- Marca no actualizada tras `base`: corta sin tocar respaldos ni contador, y el reintento termina.
- `unlink` fallido: queda `.hecho`.
- `unlink` y renombre fallidos: tras operar no se repite nada, y una marca con pasos pendientes se rechaza.

## SAF-04 (MEDIA): primera instalación

**Cambio (`ui_qml/bridge/puente_instalacion.py`).**
- **(a)** `es_primera_instalacion` acepta solo v2 de tipo `INS` (también INSA). Un v1 ya no cuenta.
- **(b)** `hay_evidencia_entregado(carpeta)`: si en la carpeta de datos de la base existe `parametros_fabrica_equipo.json` o `calibracion_fabrica_equipo.yaml`, `registrar_equipo_instalado` no entra en FÁBRICA aunque la base esté vacía.
  - En el equipo, la carpeta de la base es la misma que `fabrica_equipo.carpeta_datos()`.
  - Un error al buscar cuenta como evidencia (falla segura).
  - Los temporales `*.fab_nuevo` no cuentan.

**Pruebas actualizadas:** en `test_fab_e1_asistente.py`, v1 → False y `test_instalacion_con_v1_queda_entregado`. La decisión DF-02 de `decisiones.md` está marcada como corrección SAF-04.

**Pruebas nuevas:**
- v1 no es primera instalación.
- Evidencia → ENTREGADO, con cada uno de los dos archivos.
- Sin evidencia → FÁBRICA.
- Error al buscar → ENTREGADO.
- Asistente completo con evidencia.

**Residual:** si se pierden a la vez la base, el perfil y la carpeta de datos (por ejemplo, el desinstalador borra `datos\`; pregunta abierta 2), un INS vigente todavía deja el equipo en FÁBRICA.

## SAF-05 (BAJA): solo se documenta

**Residual:** lo que se escribe en la base entre la copia que va al paquete (fase 1, paso «paquete») y la marca no llega al paquete. En ese tramo el lazo está detenido y el middleware responde 409 a las rutas durante el cierre, así que solo podrían entrar escrituras internas (alarmas de lectura, bitácora del propio cierre). No se corrigió: hacerlo exigiría congelar la base antes del paquete y reordenar la fase 1, que no es una corrección trivial.

## SAF-06 (BAJA): restos solo tras un cierre

**Cambio.**
- `_limpiar_restos` solo sobrescribe y borra la base vieja, `defecto.fab_viejo` y `respaldo_ciclos.fab_borrar` si la base vigente, leída en solo lectura, está en ENTREGADO con `fecha_liberacion` no nula. Si no, no los toca y lo anota en el log.
- Los temporales de una fase 1 cortada (`*.fab_nuevo`, `.nueva`, `defecto.fab_nuevo`) se siguen borrando siempre (FAB-05): solo los crea el cierre y no son datos del equipo. `DECISIÓN SIN CONFIRMAR`.

**Pruebas:**
- En FÁBRICA, los restos no se tocan.
- En ENTREGADO sin fecha, no se tocan.
- Tras un cierre, se borran.
- Los temporales se borran siempre.

## SAF-07 (BAJA): paquete de liberación por contenido y nombre

**Cambio (`core/runtime/respaldo.py`).**
- `es_paquete_liberacion(nombre, nombres_zip)` detecta el nombre `liberacion_*`, o `informe_liberacion.pdf`, `bitacora.csv` o `ciclos/` en el ZIP (no solo en el manifiesto).
- `leer` y `ruta_respaldo_segura` lanzan `ErrorRespaldo("paquete_no_restaurable")` antes que cualquier otro motivo. La ruta de restauración ya convierte eso en 422 con el mismo código, y la lista de la USB lo muestra como motivo.

**Pruebas:**
- Contenido de liberación fuera del manifiesto (3 casos).
- Nombre `liberacion_*`.
- Un respaldo normal sigue válido.
- Paquete de liberación con el `tipo` editado a «respaldo» y el hash recalculado: 422.

## SAF-08 (BAJA): polinomio plausible

**Cambio.**
- `catalogo_parametros.evaluar_desviacion_polinomio(tipo, poly, sensor)` aplica la misma prueba que `evaluar_desviacion_acumulada`, sobre el polinomio, en 36 puntos del rango operativo: desviación respecto de la neutra con los mismos umbrales de aviso y rechazo por canal.
- Además exige que el polinomio sea creciente en el rango; si no, la lectura no es invertible. `DECISIÓN SIN CONFIRMAR`.
- `fabrica_equipo.entrada_calibracion_equipo` la usa cuando el polinomio rige la lectura (`len >= 2`, como en `converters._user_calibrate`). Un rechazo da None: rige el neutro, con aviso en el log.

**Prueba de E3 corregida:** `test_defecto_con_poly` usaba `[0.0, 1.01]`, que es la constante 1,01 kPa. Ahora usa `[1.01, 0.0]`.

**Pruebas:**
- Constante, 1,6·x, decreciente y no creciente: rige el neutro.
- Tres polinomios plausibles se conservan.
- Niveles de la función.

## Pregunta abierta 4: «NO ABRIR» tras borrar el programa del último ciclo

Verificado, sin cambio de código. `ControlLoop._programa_ultimo_ciclo` y `_recuperacion_pendiente` son copias en memoria del programa del ciclo. `gestion_programas.borrar_fabrica` no las toca y rechaza el programa seleccionado. Tras un reinicio, `_programa_para_arranque` reconstruye el programa desde la instantánea `programa_json` del ciclo, no desde el archivo del programa. Sin programa, `temp_max_tras_ciclo()` es None y rige `temp_max_apertura` del equipo (`camara_segura.temp_max_vigente`). Si falta esa configuración, `falta_config` da NO segura. No hay falla abierta.

## Arreglo adicional (pedido del coordinador)

`backend/rutas/fabrica.py` definía su propio `_unidades_usb()`. Ahora lo importa de `rutas/respaldo.py`, como `rutas/carga.py`: un solo objeto, que `tests/helpers/backend_doble.py` exige y parchea en los tres módulos a la vez. Así vuelven a pasar `tests/test_rcb_catalogo.py::test_importar_csv_invalido` y `::test_importar_csv_vista_previa_y_aplicacion`.

## Archivos

- **Código:**
  - `src/autoclave/core/runtime/cierre_fabrica.py`, `core/runtime/respaldo.py`, `core/runtime/fabrica_equipo.py`
  - `core/managers/catalogo_parametros.py`
  - `backend/context.py`, `backend/arranque/secuencia.py`, `backend/rutas/fabrica.py`
  - `ui_qml/bridge/progreso_arranque.py`, `ui_qml/bridge/puente_instalacion.py`, `ui_qml/domain/detalle_aviso.py`, `ui_qml/qml/Main.qml`
  - `i18n/es.json`, `i18n/en.json`
- **Documentos:** `docs/catalogo_alarmas.md`, `docs/informes/modo_fabrica/decisiones.md`.
- **Pruebas nuevas:** `tests/test_fab_s_cierre.py`, `tests/test_fab_s_correcciones.py`.
- **Pruebas ajustadas:** `tests/test_fab_e5_cierre.py`, `tests/test_fab_e1_asistente.py`, `tests/test_fab_e3_calibracion.py`.

## `DECISIÓN SIN CONFIRMAR`

1. Sin sello HMAC de la marca (SAF-01).
2. Una base no verificable bloquea en lugar de rechazar la marca (SAF-01/02).
3. Respaldos posteriores a la marca conservados aunque luego se reimporten (SAF-02).
4. Los temporales de la fase 1 se borran siempre; solo los restos destructivos exigen ENTREGADO con fecha (SAF-06).
5. Polinomio: además de la desviación, debe ser creciente en el rango operativo (SAF-08).
6. Texto de la acción del detalle: «Reinicie el equipo. Si el fallo persiste, contacte a Especifika. No opere el equipo.»
