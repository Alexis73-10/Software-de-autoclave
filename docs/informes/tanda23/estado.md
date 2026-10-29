# Tanda 23 — estado

Rama `tanda-23` (desde `dev` acd17d36). Spec: `docs/mis_plans/decisiones_tanda_23.md`; prompt: `docs/mis_plans/prompt_claude_code_tanda23.md`.

| Paso | Estado | Notas / último commit |
|---|---|---|
| A0.1 verificación tanda 22 | Hecho | CERRADO.txt sin BLOQUEADO; dev contiene 45966035 |
| A0.2 rama y commit del prompt | Hecho | 0b92a352 |
| A0.3 inventario | Hecho | `inventario.md`; `codigo_visible()` en a138033d |
| B AIN | Hecho | tanda-23-ain 43b7cfbe..9f36f0ae (4 commits), 5479 pruebas afectadas verdes |
| C1 UI | Hecho | tanda-23-ui: f68cd0eb, ce3f0b0a, 3248589e |
| Unión B (+C1) | Hecho | 90e86ab0 (B), 391288c0 (C1); 319 pruebas cruzadas verdes |
| C2 núcleo | Hecho | 04000cf2 (104 archivos); base t15: docstring de POST /system/shutdown |
| C3 tools/packaging/tests | Hecho | 59c92686, d0a751bb, bd4835cb; unido |
| C4 docs | Hecho | tanda-23-docs, 6 commits; unido en 4b8af9c9 |
| Unión C1..C4 | Hecho | C1 391288c0, C4 4b8af9c9, C3 2e23c9aa, C2 34b16400 (13 conflictos de nombres en pruebas resueltos conservando ambos cambios; 371 pruebas verdes) |
| D prueba de regla | Hecho | a4708840 `test_t23_sin_tarjeta.py` (26 pruebas, verde tras C2) |
| R revisión | Hecho | 1 MEDIA + 5 BAJA corregidas en 819ba50d; `R_revision.md` (d903a660) |
| Suite | Hecha | corrida 1: 2 rojas (bloque T23 en test_f1, corregido en 18e2a436; test_home_view, caída conocida de xdist); corrida 2: 2 rojas (test_home_view; aislamiento de filtros en test_t23_ain_grupos, corregido); corrida final en dev tras K |
| K merge a dev (sin compilar) | Pendiente | |
| Z cierre | Pendiente | |
