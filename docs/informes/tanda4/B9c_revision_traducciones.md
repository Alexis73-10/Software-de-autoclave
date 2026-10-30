# B9c — Revisión de traducciones es/en (tandas 2, 3 y 4)

**Método (automático, sobre `i18n/es.json` y `en.json` del árbol de trabajo):**
- Mismas claves en ambos idiomas: 622 / 622, sin faltantes ni sobrantes (además lo exige `tests/test_i18n.py`).
- Mismos marcadores `{nombre}` en cada par: sin diferencias.
- Sin caracteres españoles (á é í ó ú ñ ¿ ¡) en `en.json`: ninguno.
- Textos idénticos en es y en que parezcan palabras (posibles sin traducir): 6 — `instalacion.puerta_simple`, `app.nombre`, `reportes.col_total`, `reportes.col_completados`, `reportes.col_cancelados`, `io.ui.offset`. Todos son nombres propios, términos o cognados aceptables ("Total", "Offset", marca), no son faltas.
- Inglés mucho más largo que el español (riesgo de truncado a 1024 px): ninguno (>1.6×) .

**Lo añadido en la tanda 4** (B3 intervalos de mantenimiento, B4 "Equipment parameters", B5 `alarmas.SIS-05`, B6 `selector_ciclo.*`) quedó registrado como "sin revisar" en `docs/mis_plans/revision_traducciones.md` (las de alarmas y seguridad marcadas "requiere revisión explícita").

**No verificado (requiere ojos en pantalla):** truncado visual a 1024 px. Los textos nuevos usan `WordWrap` o `elide` (ayuda de intervalos, aviso del selector, filas del selector); el aviso de impresora y la acción de SIS-05 se muestran en la tarjeta/campana existentes. Comprobar a mano en el equipo: la ayuda "Toque para cambiar de ciclo" bajo el programa y la fila "Más usado" con nombres largos.
