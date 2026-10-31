# R_informe: instalación por automatización (30-oct-2026)

Rama `automatizacion-instalacion` (desde `dev`), **sin commit** (a decisión de Cristian). Diseño: `diseno.md`; plan: `plan.md`; riesgos: AUT-R1..R8 en `docs/riesgos/registro_riesgos.md`.

## Qué se hizo

- **A. Verificador v2** (`installation/activacion_v2.py`, `secretos.py`, 3 `.spec`, `tools/verificar_entrega_neutra.py`, `tests/helpers/codigo_doble.py`): despacho por longitud exacta (12 = v1, 48 = v2); `INS`/`REI` de fabricación y `INSA`/`REIA` de automatización; normalización de originales copiada del generador; sello de identidad; carga perezosa de `K_t` (falla cerrado solo v2).
- **B. Perfil** (`profile.py`, `storage.py`, `cambio_perfil.py`): `tipo_instalacion`, `serial_original`, `modelo_original`, `sello_identidad`; fabricación guarda el JSON idéntico; `CAMPOS_DE_IDENTIDAD` protegido.
- **C. BD de ciclos** (`db_manager.py`, `cycle_logger.py`): `_migracion_v12`, columnas NULL en fabricación; ticket en vivo con los originales.
- **D. Asistente** (`puente_instalacion.py`, `Instalacion.qml`, i18n): interruptor de automatización, validación en vivo, resumen normalizado, `equipo_instalado` con los campos solo en automatización.
- **E. Salidas** (`installation/identidad.py` y 12 salidas): ticket de arranque/ciclo/mantenimiento, PDF y correo, `/system/info`, Información del equipo/sistema, Parámetros del equipo. En automatización: originales + «Serial Especifika». Fabricación idéntica.
- **Revisiones (opus):** A+B+C → aprobado con cambios (M2 caché del fallo de `K_t`, B1/B2/B4/B5 aplicados; B3 `machine_id` fuera del sello y B6 intentos, documentados). D+E → aprobado con cambios (7 arreglos aplicados: PDF envuelto, pies de barra con letra ajustada, fila Serial Especifika en Parámetros, fecha única, `_codigo` limpio, originales normalizados en el resumen, ayuda visible, bitácora de fabricación sin claves nuevas).
- **Ajustes propios del director:** `profile.py` reutiliza la normalización de `activacion_v2`; `test_t9_e9_entrega_neutra` crea un transporte no de prueba; stub de `PruebaInstalacion.qml` al contrato nuevo; `elide` → `HorizontalFit` (regla D8-5.4).

## Verificación

- Suite completa (`pytest tests`, 1 h 11 min): 9541 pasadas, 38 saltadas, 7 esperadas como fallo, **1 fallo** (`test_v8b_textos::test_qml_no_recorta_textos_con_puntos_suspensivos`, por los `elide` añadidos). Corregido; repetidas `test_v8b_textos`, `test_b1_barra_preciclo_ciclo_qml`, `test_intro_arranque_qml`, `test_u10b_textos_caben_qml`, `test_i4_truncado_qml` y `test_i18n*`: todas verdes (318 + 73). **La suite completa NO se repitió tras ese último cambio** (3 líneas de QML).
- 27 pruebas en `skip` esperando los vectores INSA/REIA finales del generador.

## Pendiente / abierto

1. **Bloqueante de entrega (AUT-R3):** vectores INSA/REIA finales del generador → copiar `vectores_formato_v2.json` y quitar `SKIP_A`.
2. Captura de `Instalacion.qml` en automatización a 1024 px y de las barras de Preciclo/Ciclo en curso con un modelo de 80 caracteres (no se probó visualmente).
3. Confirmación regulatoria del rotulado «Automatizado por Especifika S.A.S.» (INVIMA / responsabilidad del integrador).
4. Especificación del formato (`formato_codigos_v2.md`): §3.1 retira el v1 y §4.2 guarda `K_e` con DPAPI; ambas chocan con las decisiones de convivencia y de no guardar `K_e`. Pedir nota en la spec (la spec 2.1.0 sigue pendiente de revisión de Cristian).
5. Quién genera y custodia el archivo de `K_t` para compilar (`exportar-transporte` del generador) y su ubicación de desarrollo (`%USERPROFILE%\Documents\especifika_secretos\activacion_v2.json` o `ESPECIFIKA_TRANSPORTE`).
6. Contador de intentos del asistente (AUT-R5), fuera de alcance.
7. Con L1, todo equipo instalado con v2 se reinstalará con `REI`/`REIA` (AUT-R7).

## Qué haría falta para retirar el v1 (no se hizo)

Dejar de aceptar 12 caracteres en el despachador; retirar `activation.validate_installation_code` y `activacion.json` (y su recurso en los `.spec`); migrar los equipos de campo a un código v2 de reinstalación; actualizar las pruebas de `test_activation.py`, `test_g10_codigo_activacion.py` y `test_l0_secretos_activacion.py`.
