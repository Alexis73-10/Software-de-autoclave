
## 2026-10-30 — Instalación por automatización (rama automatizacion-instalacion)

- **Revisión A+B+C (M2, B1, B2, B4, B5):** decidió el director tras el informe del revisor; cambios en `activacion_v2.py`, `profile.py`, `tests/helpers/codigo_doble.py`, `backend/rutas/historial.py`. B3 (`machine_id` fuera del sello) y B6 (intentos) se dejaron documentados.
- **Revisión D+E (7 arreglos):** decidió el director; implementó un implementador (PDF, pantallas, `puente_instalacion.py`, i18n).
- **Rotulado del PDF en automatización:** Cristian delegó la redacción al director («cambialo a tu criterio»); queda «Automatizado por Especifika S.A.S.», pendiente de confirmación regulatoria.
- **Fallo de `test_v8b_textos`:** `elide` en 3 QML contradecía la regla D8-5.4; el director los cambió por `HorizontalFit`/`Escala.fuenteMinima`.
- **Cuelgue atribuido a la migración v12:** descartado (la prueba pasa sola; fue contención al correr en paralelo).
