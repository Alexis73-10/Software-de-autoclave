**Hay compilación (se llama F, no E: la letra E ya la usó la compilación de esta mañana) y se recomienda instalarla en el equipo de pruebas antes del lunes 26-oct: `entrega/2026-10-23_f/usb/` con `Autoclave_Setup_1.0.0-f.exe`, sección 8e del LEEME (E → F o D → F, sin copias a mano).**

# Tanda 10 — índice (23-oct-2026)

Rama `tanda-10` (desde `dev` 748337a), unida a `dev` con `--no-ff` y la suite en verde. Etiqueta `inst-2026-10-23-f`. Estado detallado: `docs/informes/tanda10/estado.md`.

## Resumen
| Etapa | Qué | Informe |
|---|---|---|
| A0 | Precondición (tanda 9 cerrada y en `dev`), rama, línea base: 6633 passed, 10 skipped, 3 xfailed | `tanda10/estado.md` |
| G10 | D10-2: el código de activación se normaliza (mayúsculas, sin espacios/guiones, 0→O, 1→I, 8→B) en `activation.py`; caso real `SN128745` / `FR4QAXQ3043N` válido. Generador con fuente monoespaciada | `tanda10/G10_codigo_activacion.md` |
| T10 | D10-3: texto de CIC-10 cuando falta el sensor de presión de cámara (es/en); comportamiento sin cambios | `tanda10/T10_texto_cic10.md` |
| W10 | D10-4: pantalla 2 en Reposo con «Instalación en curso en la pantalla 1» y paso solo al flujo normal | `tanda10/W10_pantalla2_instalacion.md` |
| U10a | D10-1.1 a 1.3: componente `TextoAjustable`, claves `abrev.*`, tarjeta de Ciclo y Preciclo | `tanda10/U10a_abreviatura_ciclo_preciclo.md` |
| U10b | D10-1.4/1.5: barrido de todas las pantallas (es/en, 1024x1638 y 1200x1920), alarmas de Preciclo y campana en el idioma de la interfaz, CIC-10 completo en varias líneas, prueba automática de textos en 25 pantallas | `tanda10/U10b_barrido_abreviaturas.md` |
| K10 | Compilación F con Setup, prueba de humo (2 pantallas), ensayo E → F, SHA-256 y `usb/` | `tanda10/K10_compilacion_f.md` |
| Z | Suite en verde, unión a `dev`, push de `dev`, `tanda-10` y la etiqueta | este índice |

Suite final (0635da5, tras unir U10b; después solo documentación): **6993 passed, 10 skipped, 3 xfailed** (con `-n auto`: 6990 passed y 3 de impresión que fallan solo en paralelo y pasan en serie). Un rojo real de la integración intermedia (`test_i18n_linea_base`, claves `abrev.*` de U10a) se arregló en U10b.

## DECISIONES SIN CONFIRMAR y PREGUNTAS PARA CRISTIAN
En `docs/informes/tanda10/DECISIONES_PARA_REVISAR.md`. Las preguntas: «Chbr.»/«Gskt.» en inglés; motivos de ProtocoloFallo en inglés; causa de fallo cruda en Reportes; «Complet.»/«Canc.»/«Compl.»; controlador serie para `drivers/`.

## Lo que quedó sin hacer
- `entrega/drivers/` vacía, así que `usb/drivers/` también.
- La alarma de arranque superpuesta de `Main.qml` aún usa `elide` (cabe con los textos actuales; la prueba no la cubre).
- Diálogos que solo salen con datos raros o errores de red no se barrieron.
- Verificación en sitio: dos monitores (W10), resolución real del equipo (U10), Setup E → F.
- Siguen abiertas las preguntas de la tanda 9 y las arrastradas de la tanda 8 (índice de la tanda 9).
