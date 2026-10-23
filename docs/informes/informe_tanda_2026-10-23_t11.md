**Hay compilación G y se recomienda instalarla en el equipo de pruebas antes del lunes 26-oct: `entrega/2026-10-23_g/usb/` con `Autoclave_Setup_1.0.0-g.exe`, sección 8f del LEEME (F → G, dejando marcada «Actualizar (conserva los datos)»; NO usar «Instalación limpia» en el equipo de pruebas).**

# Tanda 11 — índice (23-oct-2026)

Rama `tanda-11` (desde `dev` c607dc4), unida a `dev` con `--no-ff` y la suite en verde. Etiqueta `inst-2026-10-23-g`. Estado detallado: `docs/informes/tanda11/estado.md`.

## Resumen
| Etapa | Qué | Informe |
|---|---|---|
| A0 | Precondición (tanda 10 cerrada y en `dev`), rama, línea base: 6993 passed, 10 skipped, 3 xfailed | `tanda11/estado.md` |
| R11 | D11-1: al habilitar o deshabilitar la impresora, se pide confirmar y luego se guarda. El software se cierra de forma ordenada (ALL_OFF, sin apagar Windows) y el lanzador lo vuelve a abrir con una sola instancia. Se rechaza en CICLO, con el estado seguro actuando o con una confirmación pendiente. Se audita como `software_reiniciado`. Revisor de seguridad: sin bloqueantes, 4 hallazgos corregidos | `tanda11/R11_reinicio_software.md` |
| E11 | D11-2: se retira `aire_comprimido_chaqueta`. DO 13 queda libre y siempre en 0; las demás salidas, la trama y el firmware no cambian. Un YAML o una asignación antigua que la traiga se ignora con una advertencia | `tanda11/E11_retiro_aire_chaqueta.md` |
| S11 | D11-3: SEN-03 solo se activa para las sondas en uso de los programas vigentes. RS-06 no cambia | `tanda11/S11_sen03_sensores_en_uso.md` |
| U11 | D11-6: cuentas `Admin`/`Ingeniero` con la marca `cuenta_sistema` (BD v11), protegidas en el backend (409 auditado), en la BD (triggers) y en la UI. Inicio de sesión sin distinguir mayúsculas (NFKC + casefold). Migración idempotente. Revisor de seguridad (★): sin bloqueantes, 4 hallazgos corregidos | `tanda11/U11_cuentas_admin_ingeniero.md` |
| N11 | D11-4/5: el Setup ofrece «Actualizar» o «Instalación limpia». La limpia pide doble confirmación, hace un respaldo verificado y aparta la carpeta con un solo renombrado. Paso 06 de la estación para asociar los táctiles. Revisor de seguridad: sin bloqueantes, 8 hallazgos corregidos. ISCC compila; no se ejecutó nada | `tanda11/N11_instalador_limpia_tactiles.md` |
| O11 | D11-7: Entradas 1/2/3 con desplegable por fila. Las sondas «No en uso» no se ofrecen (422 `SENSOR_NO_EN_USO`) ni se muestran en Preciclo, Ciclo ni la gráfica. El cambio de rol las quita de la selección, con auditoría. Capturas antes y después, en es y en | `tanda11/O11_entradas_mostradas.md` |
| K11 | Compilación G con Setup, prueba de humo (2 pantallas), ensayo F → G (migración de usuarios), SHA-256 y `usb/` | `tanda11/K11_compilacion_g.md` |
| Z | Suite en verde, unión a `dev`, push de `dev`, `tanda-11` y la etiqueta | este índice |

Suite final (25bbe81, con todas las etapas unidas; después solo documentación): **7218 passed, 10 skipped, 3 xfailed** (7216 con `-n auto` + 2 de impresión que fallan solo en paralelo y pasan en serie, como en la línea base). Hubo un rojo real de integración tras unir O11 (`test_o2e_bitacora::test_textos_de_todos_los_eventos`, evento `entradas_mostradas` sin texto) y se arregló en `tanda-11`.

## DECISIONES SIN CONFIRMAR y PREGUNTAS PARA CRISTIAN
Están en `docs/informes/tanda11/DECISIONES_PARA_REVISAR.md`. Las preguntas:
- **S11:** ¿la unión para SEN-03 incluye el programa del último ciclo?
- **U11:**
  - ¿qué hacer si un usuario choca con `Admin`/`Ingeniero` al migrar?
  - ¿se mantiene la regla del último ingeniero?
  - ¿qué hacer con una semilla de rol inesperado?
  - ¿cómo se recupera el acceso si `Ingeniero` pierde su contraseña?
- **N11:**
  - ¿la limpia revierte también la estación?
  - ¿cuántos respaldos se guardan?
  - ¿se borra el usuario recordado del menú de ajustes?
  - ¿`MultiDigitizer.exe` funciona en la estación?
- **O11:**
  - ¿queda así la omisión [Principal, primera Referencia, presión]?
  - ¿se corrigen los botones sin ancho que quedan («Cerrar» del aviso y psig/inHg)?

## Lo que quedó sin hacer
- **R11 SAF-06:** el aviso «Si el software no vuelve a abrir en 1 minuto…» solo lo ve la pantalla que pidió el cambio. La otra pantalla se cierra sin aviso.
- **R11 SAF-05:** si el ALL_OFF del reinicio quedó confirmado solo consta en el log del backend, no en la bitácora.
- **Hoja de banco:** `docs/mis_plans/hoja_pruebas_banco/generar.py` ya no reproduce el `.md` (unas 300 líneas editadas a mano). En esta tanda se editó a mano; falta sincronizar `pruebas.py`.
- `entrega/drivers/` sigue vacía, así que `usb/drivers/` también.
- **Verificación en sitio:**
  - Setup F → G (8f);
  - reinicio por impresora en el equipo real;
  - DO 13 libre;
  - SEN-03 con sondas «No en uso»;
  - filas de Entradas;
  - Instalación limpia y táctiles, solo en un PC de prueba (A-N11-01 a 05).
- Siguen abiertas las preguntas de las tandas 8 a 10.
