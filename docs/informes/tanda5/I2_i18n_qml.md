# I2 — i18n F3: UI QML, con unidades

## Hecho
- **Literales fijos a `I18n.t(...)`:**
  - `Login.qml`: título, subtítulo, marcadores de usuario y contraseña, "Recordar usuario", "INICIAR SESIÓN" y "¿Olvidó su contraseña?".
  - `NuevoUsuario.qml`: título, marcadores, "Seleccione rol" y diálogo de descarte.
  - Los meses de `BarraSuperior.qml` salen de `fecha.meses` en el idioma vigente.
  - Claves nuevas en es/en: `sesion.titulo_login`, `sesion.subtitulo_login`, `usuarios.titulo_nuevo`, `usuarios.marcador_nombre`, `usuarios.marcador_clave`, `usuarios.seleccione_rol`, `usuarios.descartar_titulo`, `usuarios.descartar_mensaje` y `acciones.descartar` (las inglesas, "sin revisar").
- **Prueba automática:** `tests/test_i2_sin_literales_qml.py` falla si una pantalla QML (sin contar `Pruebas/`) conserva un texto visible fijo con letras.
  - Lista blanca: el eslogan de `IntroArranque.qml`, que es marca y va siempre en español (D-06, ARR-02).
  - Se ignoran los identificadores en minúsculas (claves, nombres de campo).
- **Unidades (U1) en Preciclo y Ciclo:**
  - Las temperaturas (consigna de esterilización, cámara, referencia) y la presión de cámara pasan por el formateador único (`domain/pantalla_ciclo.py` → `core/runtime/unidades.py`).
  - La etiqueta de unidad sale del puente: `tempUnidad`, y `presionUnidad`, que en psi cambia entre psig e inHg según el lado de la atmosférica.
  - En psi sin P_atm válida se muestra "---". Sin el singleton (pruebas), se queda en °C y kPa.

## PENDIENTE
- **Gráficas (eje y unidad), historial y diálogos de resultado** siguen en °C/kPa, con su unidad visible (no engañan, pero no siguen la selección). Hace falta convertir las series de `GraficaCiclo.qml`.
- **Textos que Python entrega a QML** (días y meses de los paneles de Información y Resumen, roles, resultados) y **etiquetas del teclado (D-18)**: no se revisaron en esta pasada. Los controladores de teclado tienen cambios sin commit de otra sesión.
- **Capturas** de Preciclo, Ciclo y una pantalla de Opciones en es/en y en °F/psig, y **revisión de truncados en 1024 px**: no se generaron. Quedan como comprobación manual en la hoja de banco (H1).
- La UI no cambia de idioma en caliente desde el backend (`/language`): R-06 sigue vigente y no hay selector para el operador.

## Pruebas
`tests/test_i2_sin_literales_qml.py` (2) y `tests/test_pantalla_ciclo.py` (ajustada y con una prueba nueva en °F, psig/inHg y sin P_atm).
