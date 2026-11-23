# Modo fábrica, Etapa 5: cierre de fabricación en dos tiempos y pantalla de cierre

Fecha: 22-nov-2026. Rama `modo-fabrica`. Base:
- spec `docs/mis_plans/planeacion_modo_fabrica.md`: D-09..D-12, FAB-01/02/05/07/10, §6, §8, pruebas P-04, P-07, P-08, P-10, P-12;
- revisión `R_revision_plan.md`: R-02, R-04, tabla de la sección 1 (logs, contadores y archivos de `data/`), «Base nueva incompleta», «Cámara sin presión», «Borrado en 6.4»;
- decisiones `decisiones.md`: DF-05, DF-09, DF-10, PA-06 (= rige D-11), PA-08, PA-09.

## Qué se hizo

### 1. Fase 1, con el equipo en marcha

Módulo nuevo `core/runtime/cierre_fabrica.py` (lógica, sin FastAPI) y router nuevo `backend/rutas/fabrica.py` (precondiciones, hilo, estado publicado, reinicio). El borrado de programas de la Etapa 2 sigue en `rutas/programas.py`: no había un `rutas/fabrica.py`.

Secuencia del hilo `CierreFabricacion` (fuera del lazo de control):
1. Revalida las precondiciones y la USB con el tamaño estimado.
2. `generar_paquete_liberacion` + `verificar_paquete` (el hash de la relectura debe ser el del resultado). Si falla: error publicado, la USB queda sin el paquete y nada cambió (FAB-02).
3. Consolida en temporales sin tocar los vigentes:
   - `data/<parámetros del equipo>.fab_nuevo` y `data/<calibración del equipo>.fab_nuevo` (con las funciones de la Etapa 3 y `destino`);
   - `cycles/defecto.fab_nuevo/`: copia de `cycles/defecto/` (también los archivos que no son `.json`) y `consolidar_defectos_programas` sobre la copia. La función de la Etapa 3 no se cambió.
4. Construye `autoclave.db.nueva` junto a la base:
   - `DbManager(ruta_nueva)`: esquema, migraciones, triggers y semillas D-11 tal cual (`Admin`/`Ingeniero`, contraseña semilla, `debe_cambiar_clave=1`);
   - método nuevo `DbManager.preparar_base_entregada(...)`, en una sola transacción: `system_params` vigentes, `estado_fabrica` ENTREGADO con `fecha_liberacion` y `hash_paquete`, la fila `equipo_instalado` original (la primera; mismos campos y fecha, PA-08) y una sola fila `equipo_liberado_fabrica` (usuario y rol del ingeniero; detalle `{fecha, serie, paquete}`, sin el hash, D-12). Rechaza una base que no esté vacía;
   - `cycle_params_audit` y `sensor_calibration_audit` con el mismo SQL de sus clases;
   - se cierra, se pasa a diario DELETE (un solo archivo, sin `-wal`) y se verifica (`integrity_check`, estado ENTREGADO).
   - Nada más: sin ciclos, lecturas, alarmas, mantenimientos, operadores, catálogo de carga ni usuarios distintos de las semillas. Nunca se quitan triggers ni se borran filas: la base vieja no se toca (FAB-07).
5. Detiene el lazo con todo apagado con el mecanismo del reinicio del software (`apagado.bloquear_para_reinicio`, bajo `_sm_lock`). Si se rechaza (p. ej. alguien entró al modo prueba), se borran los temporales y nada cambió.
6. Escribe de forma atómica la marca `data/cierre_fabrica.json` (punto de no retorno): fecha, usuario, hash, ruta del ZIP, `pasos_pendientes` y `pasos_hechos`. Antes comprueba que estén los cuatro temporales.
7. Publica el resultado (ruta del ZIP, hash) durante `ESPERA_ANTES_DE_REINICIAR_S` (10 s) y reinicia el software con `apagado.lanzar_reinicio` (todo apagado; `software_reiniciado` queda en la base vieja, que se borra).

Si la marca no se puede escribir, se borran los temporales y se reinicia igual (el lazo ya está detenido): el equipo sigue en FÁBRICA, intacto.

### 2. Fase 2, al arrancar

`completar_cierre_si_pendiente(rutas=None)` en `core/runtime/cierre_fabrica.py`. Nunca lanza.

**Punto del arranque elegido:** `backend/main.py`, función `completar_cierre_fabrica()`, llamada en `main()` justo después de configurar el log y **antes de importar `autoclave.backend.server`**. Es lo primero que hace el proceso del backend: antes del contexto, del perfil, de `ConfigManager` (que lee el archivo de parámetros del equipo), de `CycleManager` (que lee `cycles/defecto`) y de cualquier `DbManager`. No depende del perfil, así que el arranque sin perfil no lo salta. El lanzador (`exe_unico`) no abre la base antes del backend (solo lee el perfil), y el asistente solo corre sin perfil, que el cierre conserva.

Con marca, pasos en orden; cada uno se anota en la marca al terminar y **no se repite nunca** una vez hecho:

| Paso | Qué hace | Tipo |
|---|---|---|
| `archivos_fabrica` | `os.replace` de los dos `.fab_nuevo` a los finales | crítico |
| `defectos` | `defecto` → `defecto.fab_viejo`, `defecto.fab_nuevo` → `defecto`, borra el viejo | crítico |
| `base` | aparta primero `-wal`/`-shm`/`-journal` y luego `autoclave.db` a `autoclave.db.vieja*`; `os.replace(.nueva, autoclave.db)` | crítico |
| `respaldo_ciclos` | renombra `respaldo_ciclos/` (con `importados/`) a `respaldo_ciclos.fab_borrar` (atómico: nada queda para reimportar) y lo borra con ceros (FAB-10) | crítico |
| `contadores` | `ciclo_contador.json` = `{"ultimo": 0}`, `mantenimiento_base.json` = `{"ciclos_instalacion": 0}` (DF-09), `numeros_usados.json` sin 1–10 (DF-10) | crítico |
| `registros` | `*.log` y `*.log.*` de `data/` y `logs/`, `installation_profile_cambios.log`, `login_recordado.json`, `last_shutdown.json`, `autoclave.db.corrupta-*`, `asignacion_io.json.bak` (conserva `.formato1.bak`), `cycles/user/*.bak`. Un archivo abierto se vacía en lugar de borrarse | mejor esfuerzo |
| `base_vieja` | sobrescribe con ceros (`fsync`) y borra `autoclave.db.vieja*` (FAB-07) | mejor esfuerzo |

Al final borra la marca. Si un paso **crítico** falla (con 3 reintentos de 0,5 s en cada renombrado), se detiene, queda en la marca para el próximo arranque y escribe `BD_BLOQUEADA` con el texto «Cierre de fabricación incompleto…»: el backend arranca en modo sin base y no reimporta nada, de modo que un ciclo de prueba nunca entra en la base entregada. Cuando el cierre termina, retira esa marca, pero solo la suya (una `BD_BLOQUEADA` de base corrupta no se toca). Un paso de mejor esfuerzo se da por hecho con aviso en el log.

Sin marca: borra los temporales que hayan quedado (`autoclave.db.nueva*`, `data/*.fab_nuevo`, `cycles/defecto.fab_nuevo/`; corte antes del punto de no retorno, FAB-05) y los restos de un cierre ya terminado (`autoclave.db.vieja*` con ceros, `defecto.fab_viejo`, `respaldo_ciclos.fab_borrar`).

Se conservan: perfil, licencia, `asignacion_io.json` y su `.formato1.bak`, configuración del módulo y red, calibración vigente, programas y listas `.lst`, idioma, unidades, tema, impresora, correo, `mantenimiento.json`, `datos\estacion\`.

`core/runtime/respaldo_ciclos.py`: el comentario «Nunca se borra un respaldo» documenta la única excepción (FAB-10).

### 3. Bloqueo durante el cierre

`server._compuerta_de_arranque` (el middleware, aplicado siempre, no solo con la compuerta de arranque) responde **409 `cierre_en_curso`** a toda escritura (POST/PUT/PATCH/DELETE) mientras el cierre corre, salvo `/auth/login`, `/auth/logout`, `/ui/activity`, `/ui/standby`, `/system/shutdown`, `/alarms/*`, `/arranque/*` y la propia `/fabrica/cierre`. El estado queda «en curso» también durante la espera del reinicio. El apagado sigue permitido: un corte antes de la marca deja el equipo intacto.

### 4. Interfaz

- `ui_qml/controllers/cierre_fabrica_controller.py` (`CierreFabricaController`): solo presenta `GET /fabrica/cierre`; `iniciar(clave)` envía el POST; sondea cada segundo mientras el cierre corre. Sin HTTP síncrono.
- `qml/Pantallas/OpcionesCierreFabrica.qml`: explicación, «Se borra» con los conteos, «Se conserva», USB (unidad, libre y necesario, con «Actualizar»), precondiciones con su motivo, botón «Iniciar cierre de fabricación» → `ModalConfirmacion` → contraseña con `PanelTeclado.abrirAlfanumericoAccion` (texto oculto; TEC-ACC). Luego, avance por etapa con barra y el resultado (ruta del ZIP; hash en letra pequeña; aviso de reinicio). Sin `elide`, colores solo de `Tema/Colores.qml` (ninguno nuevo).
- Entrada: tercer segmento «Cierre de fabricación» en **Opciones › Opciones avanzadas** (junto a Manejo de ciclos y Reasignación), visible solo con `cierreFabrica` = `control.puedeReasignarIo && puente.modoFabrica === true` (ingeniero y FÁBRICA, la misma condición que el borrado de fábrica de la Etapa 2).
- `ui_qml/sesion_backend.py`: `cierre_en_curso` global (`fabrica.err_cierre_en_curso`); tabla `_CLAVES_CIERRE_FABRICA` para `/fabrica/cierre` (`cierre_estado_no_permitido`, `usb_ausente`, `usb_no_escribible`, `usb_sin_espacio`). `solo_modo_fabrica` y los 403 de reautenticación ya eran globales.
- i18n es/en: sección `cierre_fabrica` (53 claves), `fabrica.err_cierre_en_curso` y `manejo_ciclos.segmento_cierre_fabrica` (insertadas sin reformatear los archivos).

### 5. Base de rutas de la tanda 15

Mismo procedimiento que la Etapa 2: las dos rutas se insertaron en `docs/informes/tanda15/base/rutas.json` tras las del catálogo de carga, sin reordenar las demás, y `openapi.json` se regeneró con `openapi_ordenado`. La diferencia es solo el path `/fabrica/cierre` y el esquema `_CierreBody`. Anotado en el docstring de `tests/test_t15_rutas_equivalentes.py`.

## API exacta

```
GET  /fabrica/cierre     requiere_modo_fabrica (ENTREGADO: 409 solo_modo_fabrica para todos; FÁBRICA: ingeniero, 401/403)
  200 {"resumen": {"conteos": {ciclos, lecturas, alarmas, bitacora, mantenimientos, operadores,
                               usuarios_prueba, catalogo_carga} | null,
                   "se_borra": [...], "queda": [...]},
       "usb": {"unidades": [{ruta, libre_bytes}], "unidad", "libre_bytes", "estimado_bytes", "requerido_bytes"},
       "precondiciones": {"ok": bool, "motivos": [{codigo, motivo, (motivos_camara)}]},
       "cierre": {"en_curso", "etapa", "etapas", "progreso", "error": {codigo, detalle} | null,
                  "resultado": {ruta_paquete, nombre_paquete, hash_paquete, fecha_liberacion} | null}}

POST /fabrica/cierre     requiere_modo_fabrica; cuerpo {"clave": str, "unidad": str | null}
  202 {"ok": true, "unidad"}
  403 reautenticacion_requerida | reautenticacion_fallida   (dependencias.reautenticar, origen "cierre_fabrica")
  409 cierre_en_curso
  409 cierre_estado_no_permitido  {motivo, motivos}  motivo ∈ sin_base, ciclo, falla, estado, paro,
      confirmacion_pendiente, modo_prueba, apagando, camara_no_segura, reinicio_no_disponible
  409 usb_ausente | usb_no_escribible | usb_sin_espacio      (prueba real de escritura y espacio estimado)
```

Errores asíncronos del hilo (`cierre.error.codigo`): los de `paquete_liberacion.ErrorPaquete`, `paquete_no_verifica`, `base_nueva_invalida`, `temporales_incompletos`, `marca_no_escrita`, `error_cierre`, `cierre_estado_no_permitido` y los de `bloquear_para_reinicio`.

Python:

```python
from autoclave.core.runtime import cierre_fabrica as cf
cf.RutasCierre(carpeta_datos, carpeta_ciclos, ruta_base=None, carpeta_logs=None, ruta_registro_perfil=None)
cf.rutas_del_equipo(carpeta_ciclos=None) -> RutasCierre
cf.resumen(db) -> dict; cf.tamano_estimado(rutas) -> int
cf.ejecutar_fase1(*, fuentes, carpeta_usb, usuario, rol, rutas, config_manager, cycle_manager,
                  leer_base_vieja, serie, progreso=..., ahora=None, mapas=None,
                  origen_calibracion=None) -> ResultadoFase1(ruta_paquete, nombre_paquete,
                                                             hash_paquete, fecha_liberacion)
cf.consolidar_en_temporales(...); cf.construir_base_nueva(...); cf.limpiar_temporales(rutas)
cf.escribir_marca(rutas, resultado, usuario) -> Path       # punto de no retorno
cf.completar_cierre_si_pendiente(rutas=None) -> {"marca", "completado", "hechos", "pendientes", "fallos", "restos"}
cf.PASOS, cf.PASOS_CRITICOS, cf.ETAPAS, cf.NOMBRE_MARCA, cf.PREFIJO_BLOQUEO

DbManager.conteos_cierre_fabrica() -> dict
DbManager.datos_para_cierre_fabrica() -> (system_params crudos, equipo_instalado | None)
DbManager.preparar_base_entregada(*, parametros, equipo_instalado, usuario, rol,
                                  detalle_liberacion, fecha_liberacion, hash_paquete)
backend.main.completar_cierre_fabrica(completar=None)
backend.rutas.fabrica.cierre_en_curso() / ruta_bloqueada_por_cierre(metodo, ruta)
```

## Archivos

- Nuevos:
  - `src/autoclave/core/runtime/cierre_fabrica.py`
  - `src/autoclave/backend/rutas/fabrica.py`
  - `src/autoclave/ui_qml/controllers/cierre_fabrica_controller.py`
  - `src/autoclave/ui_qml/qml/Pantallas/OpcionesCierreFabrica.qml`
- Cambiados:
  - `src/autoclave/services/domain/logging/db_manager.py` (constante `EVENTO_EQUIPO_LIBERADO` y los tres métodos)
  - `src/autoclave/backend/server.py` (router y bloqueo en el middleware)
  - `src/autoclave/backend/main.py` (fase 2)
  - `src/autoclave/core/runtime/respaldo_ciclos.py` (solo el comentario de FAB-10)
  - `src/autoclave/ui_qml/sesion_backend.py`, `ui_qml/controllers/__init__.py`
  - `src/autoclave/ui_qml/qml/Pantallas/OpcionesAvanzadas.qml`, `Opciones.qml`
  - `src/autoclave/i18n/es.json`, `en.json`
  - `docs/informes/tanda15/base/rutas.json`, `openapi.json`
- Pruebas nuevas (79): `tests/test_fab_e5_cierre.py` (29), `tests/test_fab_e5_rutas.py` (34, con el equipo de `test_fab_e5_cierre`), `tests/test_fab_e5_ui.py` (16).
- Pruebas modificadas: `tests/test_fab_e3_solo_lectura.py` (`CIERRE = {"core/runtime/cierre_fabrica.py"}`, como pedía la Etapa 3) , `tests/test_t15_rutas_equivalentes.py` (solo el docstring) y `tests/test_i18n.py` (familia `cierre_fabrica.etapa_` en `FAMILIAS`).

## Pruebas

Todas en carpetas temporales (un «equipo» con `datos/`, `cycles/` copiado de `src/autoclave/cycles` y `logs/`); ninguna escribe en `data/` ni en `src/autoclave/cycles`.

- Fase 1: ZIP verificado; temporales sin tocar los vigentes; `.nueva` con solo las semillas (con cambio obligatorio), `system_params` sin usuario ni fecha, estado ENTREGADO con hash, `equipo_instalado` con su fecha original y una fila `equipo_liberado_fabrica` sin el hash; triggers presentes; la base nueva rechaza volver a FÁBRICA y borrar la bitácora; `preparar_base_entregada` rechaza una base usada.
- **P-04**: tras la fase 2 y un segundo arranque (dos llamadas), la base solo tiene las semillas, las dos filas de bitácora y el estado; `respaldo_ciclos` no existe; contadores en cero; `mantenimiento_base` en 0; `numeros_usados` = `[11, 12]`; base de fábrica del equipo y defectos en su sitio; registros borrados; lo que se conserva, intacto. La segunda llamada no hace nada.
- **P-07**: sin USB, no escribible y sin espacio, tanto en la fase 1 directa como en el POST: rechazo, la USB y el equipo sin cambios (comparando el árbol de archivos).
- **P-08**: corte antes de la marca (al consolidar, al construir la base y justo antes de la marca) → al arrancar se borran los temporales, el equipo queda intacto y el cierre se puede repetir. Corte en cada uno de los 7 pasos de la fase 2 → los críticos quedan pendientes con `BD_BLOQUEADA` y el siguiente arranque termina; los de mejor esfuerzo se dan por hechos. También: corte a mitad del reemplazo de la base, marca ilegible, `-wal` viejo junto a la base, log abierto (se vacía) y `BD_BLOQUEADA` ajena (no se retira).
- **P-10**: la cadena de los datos de prueba (operador, lote, alarma, mantenimiento, usuario, catálogo, respaldo, logs, `.bak`) no aparece en ningún archivo de `datos/` ni de `cycles/` tras el cierre (UTF-8 y UTF-16).
- **P-12**: ni `cierre_fabrica.py` ni `rutas/fabrica.py` contienen `DROP TRIGGER` ni `DELETE FROM`, y ningún archivo de `src/` contiene `DROP TRIGGER`.
- **P-05**: en ENTREGADO, `GET` y `POST /fabrica/cierre` → 409 `solo_modo_fabrica` sin token, ingeniero, técnico y admin, sin reautenticar.
- Precondiciones (ciclo, FALLA, modo prueba, paro, confirmación pendiente, cámara no segura, sin base, sin reinicio): 409 `cierre_estado_no_permitido` con su motivo, también en el GET, sin cambios. La cámara sin datos vigentes no es segura.
- POST completo hasta el reinicio: resultado publicado, ZIP verificado, marca y `.nueva` escritas, lazo detenido una vez, reinicio con el nombre del ZIP; durante la espera `/cycle/start` da 409 `cierre_en_curso`; luego la fase 2 termina. Error en la fase 1 o rechazo al detener el lazo: error publicado, sin reinicio, equipo intacto.
- Bloqueo de rutas durante el cierre (12 casos) y el middleware.
- `main()` llama a la fase 2 antes de importar el servidor (AST) y `completar_cierre_fabrica` no lanza.
- UI: códigos y textos es/en; controlador (resumen, USB, POST con clave y unidad, sondeo, rechazos, motivos, error publicado, resultado); pantalla offscreen en es y en: ingeniero en FÁBRICA ve el segmento, la confirmación y el teclado oculto, y se envía el POST; en ENTREGADO o como técnico no hay segmento ni POST; sin avisos de QML.
- Subconjunto pedido (`-k "fab_ or t15_rutas or arquitectura or t22_regla or tema_oscuro or respaldo"`): **489 en verde**.
- Pruebas de reglas que toca la etapa (códigos de rutas `f6`/`t24`/`t25`, i18n y su línea base, literales e inglés en QML, escala, textos que caben, anglicismos `v8b`, `c9` de Manejo de ciclos, envío síncrono, bitácora `t17`): 526 en verde tras dos ajustes: la familia dinámica `cierre_fabrica.etapa_` se enumeró en `tests/test_i18n.py` (`FAMILIAS`, con `cf.ETAPAS`; no se relaja nada) y se quitó «logs» de un texto en español.
- La suite completa no se corrió (la corre el coordinador).

## Lo que no se pudo verificar sin el equipo real

- El reinicio real con el lanzador del ejecutable único (en las pruebas `bloquear_para_reinicio` y `lanzar_reinicio` son dobles) y la fase 2 en el compilado (`app_root()`, `_carpeta_persistente()`, registro de Windows).
- Borrar o vaciar logs abiertos por otros procesos de Windows (`lanzador.log`, `ui_puerta*.log`): las pruebas simulan el `PermissionError`.
- La sobrescritura con ceros en el SSD real (mejor esfuerzo, aceptado en FAB-07).
- La USB real (psutil, protección contra escritura, tiempo de escritura del paquete con cientos de ciclos).
- La pantalla en las táctiles reales y su revisión visual (solo offscreen, sin el detector de solapes).

## Decisiones tomadas en esta etapa (todas `DECISIÓN SIN CONFIRMAR`)

- **E5-D1.** La fase 2 se llama en `backend/main.main()` antes de importar el servidor, no en el lifespan ni en `abrir_base_datos`: es el único punto anterior a `ConfigManager` y `CycleManager`, que leen archivos que el cierre reemplaza.
- **E5-D2.** Los pasos ya hechos se anotan en la marca y no se repiten nunca: así una marca que quedara por un fallo no vuelve a borrar respaldos de ciclos reales ni a poner contadores en cero en arranques posteriores.
- **E5-D3.** Un paso crítico de la fase 2 que falla deja `BD_BLOQUEADA` (texto propio) para que el backend opere sin base hasta que el cierre termine; el cierre retira solo esa marca. Alternativa descartada: arrancar con la base nueva y el respaldo de ciclos aún sin borrar (reimportaría los ciclos de prueba, FAB-10).
- **E5-D4.** `registros` y `base_vieja` son de mejor esfuerzo: si algo no se puede borrar, se da por hecho con aviso en el log; los restos de la base vieja, de los defectos viejos y del respaldo apartado los vuelve a intentar la limpieza «sin marca» en cada arranque.
- **E5-D5.** En la base nueva, cada `system_params` lleva el valor vigente también como `defecto`, sin usuario ni fecha (la base de fábrica del equipo; no quedan nombres de usuarios de las pruebas).
- **E5-D6.** Se copia la **primera** fila `equipo_instalado` (la instalación original). Si hubo reinstalaciones con REI en FÁBRICA, las siguientes no se copian.
- **E5-D7.** El detalle de `equipo_liberado_fabrica` es `{fecha, serie, paquete}` (nombre del ZIP); su `ts` es la fecha de liberación.
- **E5-D8.** El resultado queda en pantalla 10 s (`ESPERA_ANTES_DE_REINICIAR_S`) con el lazo ya detenido y todo apagado, y luego el software se reinicia.
- **E5-D9.** Orden en la pantalla: confirmación modal primero y contraseña después (el teclado envía al confirmar).
- **E5-D10.** La entrada es un tercer segmento de Opciones › Opciones avanzadas, con la misma condición que el borrado de fábrica (ingeniero y FÁBRICA), y no una sección nueva del cajón: no toca `permisos_opciones`, que no conoce el modo fábrica.
- **E5-D11.** Durante el cierre se bloquean todas las escrituras salvo la lista de la sección 3, no solo las rutas actuadoras: un cambio de parámetros o de usuarios a mitad del paquete haría que el paquete no coincidiera con la base de fábrica del equipo.
- **E5-D12.** El POST pide la contraseña antes de mirar las precondiciones (403 antes que 409). Comprueba la USB con una prueba real de escritura y el tamaño estimado (base, respaldo de ciclos y logs); la generación la vuelve a comprobar con el tamaño real.
- **E5-D13.** Sin bitácora propia de «cierre iniciado» o «cierre abortado»: el inicio y los errores van al log de desarrollo (iría a la base vieja, que se borra; el paquete ya lleva la bitácora completa).
- **E5-D14.** `/system/shutdown` sigue permitido durante el cierre: antes de la marca deja el equipo intacto y después la fase 2 termina al arrancar.

## Observaciones

- El asistente de instalación sigue abriendo `DbManager` desde la UI; corre solo sin perfil, que el cierre conserva, así que no compite con la fase 2.
- No se tocaron `docs/riesgos` ni `CLAUDE.md` (Etapa 6).
