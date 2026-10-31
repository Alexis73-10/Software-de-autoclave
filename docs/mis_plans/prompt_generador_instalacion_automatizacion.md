# Prompt para la sesión del generador: variante INSA/REIA (instalación por automatización)

**Para pegar en la sesión del generador de códigos.** Decisiones ya tomadas por Cristian a partir de tu informe; impleméntalas. Si algo del código real contradice lo que dice este prompt, detente en ese punto y repórtalo antes de seguir.

## Objetivo

Que el código de activación INS/REI pueda indicar «instalación por automatización» y quedar atado a la serie y al modelo originales del fabricante, sin alargar el código ni cambiar los códigos de fabricación ya emitidos. Cambio **menor 2.1.0** del formato.

## Decisiones (cerradas)

1. **Variante en el mensaje del HMAC**, sin gastar bits: en automatización el mensaje usa `"ESPK2|INSA|…"` (instalación) y `"ESPK2|REIA|…"` (reinstalación), en lugar de `INS`/`REI`. Misma `K_t`, misma etiqueta de 56 bits, misma cabecera y 48 caracteres. Los códigos y vectores de fabricación no cambian ni un carácter. No se usan los tipos reservados 6 y 7 ni se crea `K_t2`.
2. **Qué se firma:** `h_orig = hex(SHA-256("ESPK2|ORIG|" + serie_n + "|" + modelo_n))` entra en el mensaje de INSA/REIA. Con eso el código cubre serie y modelo originales.
3. **Normalización** (una sola función, usada por emisión, validación y vectores; el autoclave la copiará idéntica):
   - `serie_n`: quitar todo espacio en blanco y pasar a mayúsculas (como ya hace `emision/servicio.py:158-160`).
   - `modelo_n`: quitar extremos, colapsar espacios internos a uno solo y pasar a mayúsculas.
   - Ambos campos: **ASCII imprimible sin `|`**, serie 1–40 caracteres, modelo 1–80. Rechazar con código de error propio lo demás (Unicode, `|`, vacío tras normalizar).
4. **Identidad del equipo:** no cambia. `SNAANNNN` sigue siendo el serial de licencia, de `K_e` y de `machine_id`. Serie y modelo originales son datos adicionales.
5. **`modelo_id` del catálogo** sigue obligatorio también en automatización; agrega una entrada genérica «AUTOMATIZACION» al catálogo (migración/semilla). Antes verifica que nada del generador derive clase, capacidad u otros datos de `modelo_id`; si algo lo hace, repórtalo.
6. **Unicidad:** la combinación (`serial_original`, `modelo_original`) normalizados debe ser única; bloquear el duplicado exacto con mensaje claro. La misma serie con otro modelo es válida. Índice único en una migración nueva (primero revisa si hay filas existentes que lo violen o con Unicode/`|` y reporta qué pasaría; no las borres).
7. **FIN, EMG y EXT no cambian.**
8. **Pantalla de emisión:** al emitir un código de automatización, mostrar serie y modelo originales **normalizados** en grande junto al código, con la advertencia «el técnico debe teclear exactamente estos datos en el asistente; si no coinciden, el código se rechaza». La reinstalación de un equipo de automatización usa `REIA` con los mismos originales (no se pueden cambiar tras `generacion = 0`, como ya ocurre).

## Entregables

- `formato/codigos.py`, Anexo A del formato y `tests/referencia_anexo_a.py` actualizados; versión del formato 2.1.0 con nota de cambio menor.
- `tests/vectores/vectores_formato_v2.json`: los vectores de fabricación **idénticos** a los actuales (prueba que no cambian) más vectores nuevos INSA/REIA (incluyendo normalización: espacios, minúsculas, modelo con espacios internos, y casos rechazados). Que cada vector traiga serie y modelo tal como los teclea el técnico y los normalizados.
- Que un código INS no valide como INSA y al revés (prueba explícita en ambos sentidos).
- `emision/servicio.py` (pasa `h_orig`), `validacion.py` (charset y normalización), migración (índice único + entrada genérica), pantalla de emisión.
- Pruebas y la suite completa del generador en verde.
- Un informe corto en español con los vectores finales que el autoclave debe replicar, la función de normalización exacta (texto y código) y cualquier hallazgo de la verificación del punto 5 y de datos existentes del punto 6.

## Fuera de alcance

El autoclave (otro prompt), etiqueta física y trámite regulatorio (decisión de Cristian). No hagas push.
