# Modo fábrica, Etapa 1: estado, entrada, `/status`, protección y franja

Fecha: 22-nov-2026. Rama `modo-fabrica`. Base: spec `docs/mis_plans/planeacion_modo_fabrica.md`, revisión `R_revision_plan.md` y decisiones `decisiones.md` (DF-01..DF-04, D-13).

## Qué se hizo

1. **Migración v16** (`services/domain/logging/db_manager.py`, `_migracion_v16`, `ESQUEMA_VERSION` = 16). Tabla `estado_fabrica` con una sola fila:
   - columnas `id` (CHECK `id = 1`), `estado` (CHECK `IN ('FABRICA','ENTREGADO')`), `fecha_liberacion`, `hash_paquete` y `creado`;
   - triggers `estado_fabrica_sin_delete` (la fila no se borra), `estado_fabrica_entregado_inmutable` (una fila ENTREGADO no cambia) y `estado_fabrica_solo_base_nueva` (FÁBRICA no entra en una base con ciclos o con `equipo_instalado`);
   - si la base ya tiene filas en `ciclos` o una fila `audit_log` con `evento = 'equipo_instalado'`, la migración inserta ENTREGADO. Una base nueva queda sin fila. No hay `DROP TRIGGER` en `src/`.
2. **`DbManager`:**
   - `estado_fabrica() -> str`: devuelve 'FABRICA' o 'ENTREGADO'. Sin fila, con un valor desconocido o ante cualquier error, da 'ENTREGADO'. Nunca lanza.
   - `entrar_modo_fabrica_e_instalar(*, primera_instalacion, entidad, detalle, usuario="sistema") -> str`: en una sola transacción (`BEGIN IMMEDIATE`, con el lock) comprueba las tres condiciones de DF-02, inserta FÁBRICA (antes que la fila de bitácora, por el trigger) y escribe `equipo_instalado`.
     - Si una condición no se cumple, solo escribe `equipo_instalado`.
     - Si la transacción falla, la deshace y escribe solo `equipo_instalado`.
     - Respeta `_motivo_no_registrar`: con la instalación suprimida no escribe nada.
     - Devuelve el estado resultante.
   - Constantes `ESTADO_FABRICA`, `ESTADO_ENTREGADO` y `EVENTO_EQUIPO_INSTALADO`.
3. **Asistente** (`ui_qml/bridge/puente_instalacion.py`):
   - `construir_perfil_y_codigo()` devuelve `(perfil, ResultadoCodigo)`; `construir_perfil()` lo envuelve y no cambia de firma.
   - `es_primera_instalacion(resultado)`: True con un código v1, o v2 de tipo `INS` (INSA llega como INS con originales). REI y REIA nunca.
   - `PuenteInstalacion.instalar()` guarda el resultado en `_resultado_codigo`.
   - `registrar_equipo_instalado(..., primera_instalacion=False) -> str` usa el método anterior. Un error queda en el log, devuelve "ENTREGADO" y no deshace la instalación.
4. **Backend:**
   - `BackendContext.releer_estado_fabrica()` se llama en `abrir_base_datos`, justo después de abrir `DbManager`.
   - `BackendContext.modo_fabrica() -> bool` da False sin base, en el modo sin base o ante un error.
   - `/status.modo_fabrica` es un bool, True solo estricto (`rutas/sistema.py`, `_modo_fabrica()`).
   - Dependencia `dependencias.requiere_modo_fabrica()`:
     - En ENTREGADO, o si no se puede saber el estado, responde 409 `solo_modo_fabrica` antes de mirar la sesión, también sin token.
     - En FÁBRICA aplica `requiere_rol("ingeniero")` (401/403).
     - No se registró ninguna ruta nueva, así que la base de la tanda 15 no cambia.
   - Evento `equipo_liberado_fabrica` en `core/runtime/bitacora.py`, categoría sistema, con sus textos `bitacora.ev`/`bitacora.tipo` en es y en.
5. **Franja «MODO FÁBRICA»:**
   - `UiBridge.modoFabrica`: propiedad bool con la señal `modoFabricaChanged`, que sale de `/status.modo_fabrica`; solo cuenta True estricto, con la función `modo_fabrica()`.
   - Componente nuevo `Componentes/FranjaModoFabrica.qml`, que usa en `Main.qml` la ventana de las dos puertas:
     - va fuera del lienzo, anclado al borde inferior a todo el ancho, con z 2000 (por encima de las capas emergentes, que usan z 1000);
     - mide 30 px de diseño, con `enabled: false` y sin MouseArea.
   - Texto `fabrica.franja`: «MODO FÁBRICA» / «FACTORY MODE».
   - Colores `franjaFabricaFondo` (#6A1B9A / #4A1470) y `franjaFabricaTexto` (#FFFFFF / #F3E5FF) en `Tema/Colores.qml`, declarados en la paleta (§6) y en `_ORIGEN_CLARO` de `test_tema_oscuro.py`.

## Archivos

- Código: `services/domain/logging/db_manager.py`, `ui_qml/bridge/puente_instalacion.py`, `backend/context.py`, `backend/dependencias.py`, `backend/rutas/sistema.py`, `core/runtime/bitacora.py`, `i18n/es.json`, `i18n/en.json`, `ui_qml/bridge/ui_bridge.py`, `ui_qml/qml/Main.qml`, `ui_qml/qml/Tema/Colores.qml`, `ui_qml/qml/Componentes/FranjaModoFabrica.qml` (nuevo).
- Documentos: `docs/diseno/mockups/modo_oscuro/paleta_modo_oscuro.md` (dos colores nuevos).
- Pruebas nuevas, con marcador `req` DF-01..DF-04, D-13, FAB-01 y FAB-03:
  - `test_fab_e1_estado_fabrica.py`: migración, triggers, P-12 y entrada.
  - `test_fab_e1_asistente.py`: INS, v1, INSA, REI y REIA, base usada y errores.
  - `test_fab_e1_backend.py`: contexto, `/status` y la dependencia con una ruta local de la prueba.
  - `test_fab_e1_franja_qml.py`: Main.qml offscreen en las puertas 1 y 2, en vertical y en horizontal, en arranque, Preciclo y Ciclo en curso, con el detector de solapes, más el contraste.
- Pruebas modificadas:
  - `test_db_audit_log.py` y `test_automatizacion_ciclos_bd.py`: versión de esquema 15 → 16, cambio esperado por la migración nueva.
  - `test_tema_oscuro.py`: se agregan los dos colores nuevos a `_ORIGEN_CLARO`; no se relaja nada.

## Pruebas

- Las 4 pruebas nuevas están en verde. El subconjunto relacionado (arquitectura de capas, rutas equivalentes, `/status`, bitácora, BD, navegación QML, tema oscuro, instalación, i18n) da 1042 en verde.
- Suite completa comparada con la base: ver la sección siguiente.

Suite completa (`python -m pytest tests -q -p no:cacheprovider -n auto`):

- Base (`suite_base.txt`, corrida en un worktree aislado de 220fa6fd): 20 fallos y 6 errores, todos preexistentes.
- Con la Etapa 1, primera corrida: 30 fallos y 6 errores. Los 10 fallos nuevos eran:
  - 6 pruebas de migración que fijaban `ESQUEMA_VERSION == 15` (`test_i4_ingles_backend`, `test_o1_operador_ciclo`, `test_rcb_migracion_v15`, `test_s2b_d8_2_14_avisos_ticket_bd`, `test_t30_03_usuarios`), pasadas a 16. Es un cambio esperado: se agrega una versión, no se relaja la regla.
  - 4 de `test_t24_codigos_reasignacion.py`: la extracción por AST trata todo código de `dependencias.py` como alcanzable desde Reasignación, y `solo_modo_fabrica` no tiene texto en esa pantalla. Se excluye la función `requiere_modo_fabrica` (lista `_NO_REASIGNACION_DEP`, mismo mecanismo que `_SOLO_RESPALDO`), porque ninguna ruta `/io/assignment*` la usa.
  - 1 de `test_v8b_textos.py`: un archivo temporal de otra prueba QML se borró mientras corría en paralelo (`FileNotFoundError` de `_prueba_opciones_doble_*.qml`). Es intermitente y ajeno al cambio; aislada pasa.
- Tras esos ajustes, las pruebas afectadas pasan. Los fallos que quedan son exactamente los de la base: 20 fallos (programas dañados por el alivio de 340 kPa, `test_t29_*`, `test_s9_planta_simulada`, `test_t12_*`, etc.) y 6 errores (`test_hor_b_textos_contraste_qml.py`).

## Decisiones tomadas en esta etapa (todas `DECISIÓN SIN CONFIRMAR`)

- **E1-D1. Franja en el borde inferior, no en el superior.** En el superior, el detector de solapes encontró el reloj de Preciclo y de Ciclo en curso debajo del texto. En el inferior no hay solape en arranque, Preciclo ni Ciclo en curso (puertas 1 y 2, vertical y horizontal). No se revisaron con el detector las pantallas de menú, Opciones, Historial y Reportes, que no se cargan desde `Main.qml` en un arnés automático. Queda pendiente validarlas con la skill revision-visual-pantallas, como pide la spec (§5.4).
- **E1-D2. Color violeta** (#6A1B9A en claro, #4A1470 en oscuro), para que no se confunda con las alarmas IEC (rojo, amarillo, cian) ni con la advertencia (naranja). El contraste del texto es ≥ 4,5:1 en los dos temas.
- **E1-D3. La franja queda por encima de todo (z 2000)**, también de los diálogos emergentes. Es delgada y no recibe toques.
- **E1-D4. Sin conexión con el backend, la franja conserva el último valor recibido** (el caché de `/status`), para que no desaparezca por un corte (HAZ-FAB-03).
- **E1-D5. En ENTREGADO, el 409 `solo_modo_fabrica` sale antes de la autenticación**, también sin token, para cumplir «409 para todos los roles» (DF-04). En FÁBRICA rigen 401/403 normales.
- **E1-D6. INSA cuenta como primera instalación** (automatización). DF-02 dice «v2 de tipo INS», y el verificador devuelve INSA como tipo `INS` con originales.
- **E1-D7. Si `equipo_instalado` no se registra por el filtro de la bitácora** (instalación suprimida), tampoco se entra a FÁBRICA.
- **E1-D8. Defensa en profundidad:** el trigger `estado_fabrica_solo_base_nueva` rechaza FÁBRICA en una base con ciclos o `equipo_instalado` aunque se intente por SQL. El cierre de la Etapa 5 escribe ENTREGADO, al que este trigger no se aplica.
- **E1-D9. La fila FÁBRICA se puede pasar a ENTREGADO** (UPDATE permitido desde FÁBRICA). Es el sentido único que usará el cierre. Hoy ningún código lo hace.
- **E1-D10. `requiere_modo_fabrica` no tiene todavía texto propio en el cliente** (`sesion_backend.py`), porque aún no hay rutas de fábrica. Se agregará en la etapa que cree la primera.

## Observaciones

- Un equipo instalado antes de la tanda 17 (sin fila `equipo_instalado`) y que nunca corrió un ciclo queda sin fila tras la migración, es decir en ENTREGADO. Solo pasaría a FÁBRICA si se reinstala con un código INS, que Especifika emite solo para primera instalación (FAB-03). Se acepta.
- No se tocaron `docs/riesgos` ni `CLAUDE.md` (Etapa 6).
