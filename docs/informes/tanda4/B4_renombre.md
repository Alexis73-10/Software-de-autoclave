# B4 — Renombre "Parámetros del sistema" → "Parámetros del equipo"

**Equivalencia (nota para los informes históricos ya firmados, que NO se tocaron):** donde los informes de las tandas 2 y 3, `lotes_auditoria/*` y las instrucciones de tanda digan "Parámetros del sistema", léase **"Parámetros del equipo"** (en inglés "Equipment parameters", antes "System parameters").

**Texto visible cambiado:** `i18n/es.json` y `en.json` (`opciones.secciones.parametros_sistema`), `ui_pyside/views/admin_menu.py` (menú PySide), la prueba `test_opciones_qml.py` (título en mayúsculas), y las menciones en `docs/informes/estructura_configuracion.md`, `INFORME_OPCIONES_POST_LOGIN.md` y `docs/mis_plans/` (informe_estado_opciones, inventario_cadenas_i18n.csv, planeacion_*). El comentario de `OpcionesMantenimiento.qml` ya se reescribió en B3. `hoja_pruebas_banco/pruebas.py` no menciona el nombre.

**NO cambiado (compatibilidad):** identificador/clave `parametros_sistema`, nombres de sección del catálogo, rutas de API, tablas.

**Pruebas:** `tests/test_b4_renombre_parametros_equipo.py` (texto es/en, clave interna intacta, sin apariciones del nombre antiguo en `src/` y `tools/`).
**Decisiones sin confirmar:** ninguna.
