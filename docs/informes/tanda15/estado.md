# Tanda 15: estado

Rama `tanda-15`, creada desde `dev` (d09d2a9) en A0. Sesión principal arrancada por el lanzador el 24-oct a las 23:50 (hora de Bogotá).

Precondición A0: `tanda13/estado.md` tiene `| Z | Hecha |`; `tanda-13` y `licencia-l0` son ancestros de `dev`; `git status --porcelain --untracked-files=no` vacío: **cumplida**.

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | aee5334 (docs) + d35e544 (línea base). Base: 7832 recolectados; 7816 passed + 2 rojas ajenas de `test_config_correo` (en serie), 11 skipped, 3 xfailed. 107 rutas. Compilación base de los 4 `.spec` OK (Autoclave 2301 archivos / 2086 módulos PYZ; Backend 1387; Settings 2093; Generador 795). |
| G | Hecha | Sin commit. `git worktree prune`: nada que podar (los 53 worktrees existen). 14 ramas `tanda-*` borradas con `-d`; 37 no se pudieron borrar porque están en worktrees de `.claude/worktrees/` (`G_ramas.log`). |
| R | Hecha | 324e6a5 (ORG-02), c97ac8c (ORG-03), 5b21c9e (ORG-04), 3fed414 (ORG-05), f580047 (ORG-06), 712448f (ORG-07). Compilación desde `packaging/` de los 4 `.spec`: listas de `dist/` y módulos PYZ **idénticas** a la base (`org07/`). Suite: 7824 passed en paralelo; en serie quedan solo las 2 ajenas de `test_config_correo` (las 3 de `test_arquitectura_capas` son el test nuevo de ORG-11, aún sin etapa U). |
| U | Hecha | 7698d6e (ORG-08), 0586850 (ORG-09), b165fbc (ORG-10), 5947102 (ORG-11). roles.json idéntico a la base. Test de arquitectura: 3 failed sobre dev, 11 passed en la rama. Suite: 7826 passed en paralelo + 6 en serie = 7832 passed; 2 ajenas de `test_config_correo`. |
| B | Hecha | 6d64cce (ORG-12) + 8e7cbed (finales de línea). server.py 4980 → 155 líneas; 13 routers (máx. io 863) + dependencias.py + rutas/_comun.py. Rutas/OpenAPI idénticos a la base (test_t15_rutas_equivalentes). 323 bloques movidos literales. Suite: 7828 passed en paralelo + 5 en serie = 7833 passed; 2 ajenas. |
| T | Hecha | 6a143bc (ORG-13). 7 ayudantes a `tests/helpers/`, 8 bancos/capturas a `tests/banco/`, `Github.ico` fuera, marcador `req` y `tests/README.md`. Recolectados 7848 = 7832 base + 16 de los 2 tests nuevos. Suite: 7826 + 7 en serie = 7833 passed; 2 ajenas. |
