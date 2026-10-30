# G10 — Código de activación (tanda 10, D10-2)

Rama: `tanda-10-g10` (parte de `tanda-10`, f73acf6). Commit de código: `1c246be`.

## D10-2.1 — Normalización antes de comparar

- Verificación previa: el generador produce `FR4QAXQ3O43N` (con letra O) para la serie `SN128745` y el 2026-10-23. Coincide con lo reportado: el operador tecleó `FR4QAXQ3043N` (con cero) y la comparación exacta lo rechazaba. La causa es solo la confusión O/0 al leer el código en el generador.
- `src/autoclave/installation/activation.py`: nueva función `normalizar_codigo(code)` (punto único): quita espacios y guiones, pasa a mayúsculas y traduce `0→O`, `1→I`, `8→B`. La usan `validate_installation_code` y `validate_factory_key` antes de `hmac.compare_digest`. El algoritmo y el formato del código no cambian (Base32 no usa 0, 1, 8 ni 9: un código generado queda idéntico tras normalizar, comprobado en la prueba).
- Revisión de otros usos (grep en `src/` y `tools/`):
  - `ui_qml/bridge/puente_instalacion.py`: `construir_perfil` y `PuenteInstalacion.validarCodigo` llaman a `validate_installation_code` (inyectada por defecto); no comparan por su cuenta. Sin cambios.
  - `tools/generador/app.py`: solo genera, no valida.
  - `validate_factory_key` no tiene ningún llamador en `src/` ni `tools/` hoy; queda normalizada igual.
  - `ui_qml/qml/Pruebas/PruebaInstalacion.qml` tiene un puente falso de banco que compara contra `"ABCDEFGHIJKL"`; es solo para capturas, no se tocó.

## D10-2.2 — Fuente del generador

`tools/generador/app.py`: la regla CSS `.code` (serie, código de instalación y clave de fábrica) pasa de `monospace` a `Consolas,"Cascadia Mono",monospace` (las dos primeras distinguen O de 0). Nada más cambia.

## Pruebas

Nuevo: `tests/test_g10_codigo_activacion.py` (16 pruebas): caso real con O, con cero, minúsculas, espacios, guiones y mezcla → válido; mismo código con otro día (22 y 24-oct) u otra serie → inválido; `normalizar_codigo`; códigos generados sin cambios al normalizar; clave de fábrica con guiones/minúsculas/0-1-8 → válida y de otro día → inválida; códigos no intercambiables; el asistente (`PuenteInstalacion.validarCodigo`) acepta el caso con cero y usa por defecto `validate_installation_code`; la regla `.code` del generador empieza en `Consolas`, incluye `Cascadia Mono` y termina en `monospace`.

Corrida con `PYTHONPATH=<worktree>/src`, `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a6aeb70a86fb83313\src\autoclave\__init__.py`:

```
tests/test_g10_codigo_activacion.py tests/test_activation.py tests/test_m1_puente_instalacion.py
tests/test_t9_instalacion.py tests/test_p1_lanzador_primer_arranque.py
tests/test_t8_e1_asistente_texto_final.py tests/test_g1_generador.py tests/test_generador_db.py
tests/test_s1_do1_do2_generador.py
125 passed in 13.44s
```

Antes del código, la prueba nueva fallaba (ImportError de `normalizar_codigo`).

## DECISIONES SIN CONFIRMAR

1. Se conserva el recorte a 12 caracteres (`[:12]`) que ya existía, ahora aplicado después de normalizar. Así un código con guiones (14 caracteres) se compara entero.
2. El campo del código en `Instalacion.qml` tiene `maximo: 12`; con guiones el operador no puede teclear el código completo en el asistente. No se amplió (el generador muestra el código sin guiones y la pantalla es compartida); la normalización de guiones sirve para otros caminos de entrada.

## PREGUNTAS PARA CRISTIAN

Ninguna (no se toca lógica de estado seguro, ciclo ni puertas).

## Pendientes

- Recompilar el generador (D10-5, en K10) para que la fuente nueva llegue a la entrega.
