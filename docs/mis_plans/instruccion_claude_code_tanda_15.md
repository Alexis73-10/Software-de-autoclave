# Instrucción maestra para Claude Code — Tanda 15 (reorganización sin cambio funcional, sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 15` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda15/estado.md`.

**Fuente de verdad:** `docs/mis_plans/decisiones_tanda_15.md`, COMPLETO. Contexto: `docs/informes/analisis_estructura_proyecto_2026-10-24.md`. Prioridad: velocidad, sin sacrificar la prueba de equivalencia.

**Modo:** sesión principal para todos los movimientos de código (son secuenciales: tocan los mismos imports). **Hasta 4 subagentes a la vez**, solo en tareas independientes: las compilaciones de A0, ORG-07 y K (uno por `.spec`, cada uno en su propio clon) y los 4 revisores de V. Los subagentes no ejecutan la suite completa; la suite la corre solo la sesión principal, con `pytest -n auto` (lo que falle solo en paralelo, repetir en serie).

## 0. Reglas
1. Rama `tanda-15` desde `dev`. Estado en `docs/informes/tanda15/estado.md` (tabla `| Etapa | Estado | Nota |`); informe único `docs/informes/tanda15/R15_reorganizacion.md`; índice `docs/informes/informe_tanda_<fecha>_t15.md`.
2. **Git:** nunca `main`, `--force`, `git add -A`, `git push --delete`, `git branch -D` ni reescritura de historial. No toques `stash@{0}` ni `stash@{1}`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`. Mover siempre con `git mv` (conserva historial). **No unir a `dev`** (D10).
3. **Cero cambio funcional.** Prohibido cambiar lógica, textos, mensajes, códigos HTTP, firmas, valores, constantes de roles, umbrales. Si un movimiento obliga a cambiar lógica → no lo hagas, anótalo.
4. **Tests:** solo se permite cambiar rutas de import y destinos de `monkeypatch`. Prohibido borrar, saltar (`skip`/`xfail`) o relajar un test. Cada test tocado va en el informe.
5. **Prohibido:** hardware o puertos COM, firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema, borrar archivos sin seguimiento de git (D9). **Autorizado:** PyInstaller e `ISCC.exe` (solo compilar), en clones limpios fuera del repo (`..\_build_t15_base`, `..\_build_t15`).
6. Un commit por ítem `ORG-xx` (mensaje `refactor(t15): ORG-xx …`), para poder revertir uno solo. Antes de cada commit: `pytest --collect-only -q` sin errores + los tests del área. Al final de cada etapa: suite completa.
7. **Si una etapa no queda en verde** tras un intento razonable de corregir imports: `git revert` de los commits de esa etapa, estado `Revertida` con el motivo, y sigue con la siguiente.
8. Ante ambigüedad: lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". Todo en español.

## 1. Etapas

**A0. Precondición y línea base.**
- Precondición (si falla algo, escribe la fila `| A0 | Esperando | <qué falta> |` y TERMINA sin hacer nada más):
  `docs/informes/tanda13/estado.md` tiene `| Z | Hecha |`; `git merge-base --is-ancestor tanda-13 dev`; `git merge-base --is-ancestor licencia-l0 dev`; `git status --porcelain --untracked-files=no` vacío.
- Rama `tanda-15`; commit `docs(tanda15)` con decisiones, instrucción y prompt.
- Línea base en `docs/informes/tanda15/base/` (sobre `dev`, antes de mover nada):
  - `suite.txt`: número de tests recolectados (`--collect-only -q`) y resultado de la suite completa;
  - `rutas.json`: por cada `app.routes` de `autoclave.backend.server`, en orden: `path`, `methods` ordenados, `name`, nombres de todas las dependencias (recorriendo `route.dependant` recursivamente), `status_code`, `response_model` (nombre);
  - `openapi.json`: `app.openapi()` con claves ordenadas;
  - `roles.json`: valores de `ROL_*`, `ROLES_CREABLES` y los nombres públicos de `validacion_usuario`;
  - `compilacion/<spec>.txt`: 4 subagentes en paralelo, uno por `.spec`, cada uno en su clon limpio de `dev` (`..\_build_t15_base_<spec>`), compilan; guarda la lista de archivos de `dist/<x>/` (ruta relativa, sin tamaño) y la lista ordenada de módulos de `build/<x>/PYZ-00.toc`.

**G. Limpieza git (ORG-01).** `git worktree list` antes/después; `git worktree prune`; `git branch --merged dev | grep tanda-` → `git branch -d` (nunca `-D`). No toques `licencia-l0`, `tanda-13` ni las ramas de D3. Lista las ramas remotas `tanda-*` en el informe (Cristian decide si las borra). Lista los archivos sin seguimiento de D9. Sin commit.

**R. Raíz y docs (ORG-02 a ORG-07).**
- Antes de cada `git mv`, `git grep` de la ruta vieja; actualiza las referencias vigentes (D8) en el mismo commit.
- ORG-05: `.gitignore` con `docs/informes/**/*.log` y `git rm --cached` de los `.log` versionados (no se borran del disco).
- ORG-06: `docs/README.md`, una línea por carpeta de `docs/`: qué va ahí y convención de nombre (incluir `mis_plans/` = planeaciones, decisiones, instrucciones y prompts de tanda; `superpowers/specs|plans/` = specs de diseño; `informes/tandaNN/`).
- ORG-07: mover los 4 `.spec` a `packaging/`; dentro de cada uno, una raíz `RAIZ = os.path.abspath(os.path.join(SPECPATH, '..'))` y todas las rutas (`src`, datas, iconos, `pathex`, `sys.path.insert`) relativas a ella. Actualiza `tests/test_b2_spec_excludes.py` (y cualquier test que lea un `.spec`), `tools/instalador/` (`.iss`, LEEME), `docs/instalacion/LEEME_INSTALACION.md`, `docs/mis_plans/hoja_pruebas_banco/pruebas.py` y su `.md`, `requirements-dev.txt`, `docs/riesgos/lista_soup.md`. Compilación de comprobación con 4 subagentes en paralelo, uno por `.spec`, cada uno en su clon `..\_build_t15_<spec>`, desde la raíz (`pyinstaller packaging\<x>.spec`): la lista de archivos de `dist/` y de módulos de PYZ debe ser **idéntica** a la base. Si no → revertir ORG-07.

**U. Autorización fuera de la UI (ORG-08 a ORG-11).**
- ORG-08: `src/autoclave/auth/__init__.py`; `git mv` de `roles.py` y `validacion_usuario.py`. Primero verifica que ninguno importe PySide6 ni `autoclave.ui*`; si lo hacen, mueve solo la parte pura y anótalo (DECISIÓN SIN CONFIRMAR). Actualiza los 14 importadores (`git grep -l "ui_pyside.services.roles\|ui_pyside.services.validacion_usuario"`). Contenido de los dos archivos idéntico salvo líneas de import (`git diff -M --stat` debe mostrar renombre). `roles.json` idéntico a la base.
- ORG-09: `git mv` de `ui/service_ui/*.py` a `src/autoclave/cliente/`; actualiza los importadores de `src/`, `tests/`, `tools/` y los `.spec` (`hiddenimports`; en `GeneradorCodigos.spec` añade `autoclave.cliente` a `excludes` solo si el generador no lo importa). Elimina `src/autoclave/ui/` (solo quedan `__pycache__`, sin seguimiento: borrarlos sí está permitido por ser caché).
- ORG-10: `git mv` de los demos a `tools/demos_qml/`; corrige su ruta a `ui_qml/qml` (deben resolverla y `py_compile` sin error). Si algún módulo de producción o test los importa, déjalos y anótalo.
- ORG-11: `tests/test_arquitectura_capas.py` (AST, sin importar módulos): ningún archivo de `backend/`, `auth/`, `cliente/`, `simulador/`, `core/`, `services/`, `state_machine/`, `protocols/`, `devices/`, `hal/` importa `autoclave.ui`, `autoclave.ui_pyside` ni `autoclave.ui_qml`; `auth/` no importa PySide6. Debe fallar sobre `dev` (compruébalo en la base) y pasar en la rama.
- Suite completa.

**B. Partir `server.py` (ORG-12).**
- `backend/rutas/<area>.py`, uno por área, cada uno con `router = APIRouter()`. Agrupación orientativa por prefijo (ajústala si hace falta; anótala): `ciclo` (cycle, cycles, programas, fault, safe, outputs), `mantenimiento`, `usuarios` (usuarios, auth, operadores), `io` (io, calibration, units), `sistema` (system, system_params, global_params, status, arranque, network, language, ui, db, audit_log, backup), `reportes` (report, printer, email), `puertas`, `alarmas`. Las dependencias compartidas (token, rol, contexto) en `backend/dependencias.py`. `server.py` conserva `app`, `lifespan`, middleware y el registro de routers; `autoclave.backend.server:app` sigue siendo el punto de entrada.
- Cada función auxiliar se mueve con la ruta que la usa; si la usan varias, a `dependencias.py` o a un `backend/rutas/_comun.py`. Sin imports circulares (`rutas/*` nunca importa `server`).
- Los 13 archivos de test que hacen `monkeypatch.setattr(srv, "<nombre>", …)` se actualizan para parchear el módulo donde ahora se **busca** el nombre. Lista cada uno: test → destino viejo → nuevo.
- **Equivalencia obligatoria** (test nuevo `tests/test_t15_rutas_equivalentes.py` que compara contra `docs/informes/tanda15/base/rutas.json` y `openapi.json`): mismo conjunto de rutas con mismos métodos, `name`, dependencias, `status_code` y `response_model`; para cada par de rutas con el mismo método cuyos paths puedan coincidir con la misma URL (alguna con parámetro), mismo orden relativo; OpenAPI idéntico comparando con claves ordenadas. Ninguna ruta pierde una dependencia de autenticación.
- Meta: `server.py` ≤ 500 líneas, cada router ≤ 900. Si un área supera eso, divídela.
- Suite completa.

**T. tests/ (ORG-13).** `tests/helpers/` (con `__init__.py`): los ayudantes importados por algún `test_*.py` (`backend_doble`, `serial_doble`, `smtp_falso`, `alarmas_helpers`, `opciones_qml_doble`, `t12_e12_apoyo`, `textos_caben_qml` si aplica). `tests/banco/`: `*_banco.py` y `*_capturas.py` que no son pruebas automáticas. Actualiza imports (`from tests.helpers.x`) y las referencias en `docs/` vigentes. `tests/Github.ico` fuera si nadie lo usa. Registra en `pyproject.toml` `markers = ["req(id): requisito trazado (IEC 62304 7.3.3)"]` y añade `tests/README.md` (convención: `test_<modulo>_<aspecto>.py`, marcador `req` en pruebas nuevas). Número de tests recolectados **idéntico** a la base (más los dos tests nuevos de la tanda). Suite completa.

**K. Compilación de verificación (no es liberación).** 4 subagentes en paralelo, uno por `.spec`, cada uno en su clon limpio de `tanda-15` (`..\_build_t15_<spec>`), compilan desde `packaging/` y hacen su prueba de humo; luego la sesión principal compila el `.iss` con `ISCC.exe` (solo compilar, no ejecutar el Setup). Compara con la base: lista de archivos de `dist/` idéntica; módulos de PYZ iguales salvo los renombres esperados (`ui_pyside.services.roles` → `auth.roles`, etc.) y, en el backend, la posible desaparición de módulos de UI que solo entraban por los roles: cada diferencia, explicada en el informe. Prueba de humo de los `.exe` igual que en K13 (sin hardware). Sin etiqueta, sin `usb/`, sin SHA de entrega.

**V. Revisión (4 subagentes en paralelo, solo lectura)**, uno por área del diff: (1) U — `auth/`, `cliente/` e importadores; (2) B — `backend/` y tests del backend; (3) R y K — `packaging/`, `.iss`, `.gitignore`, docs vigentes; (4) T — `tests/helpers`, `tests/banco` y el resto de tests tocados. Prompt común, con su área: "Revisa `git diff dev...tanda-15 -- <rutas del área>` del repositorio. Busca cualquier cambio funcional escondido en una refactorización: lógica alterada, textos o códigos HTTP cambiados, una ruta que perdió o cambió una dependencia de autenticación o rol, un `monkeypatch` que ahora parchea un nombre que el código ya no busca ahí (test que pasa sin probar nada), imports circulares, rutas de datos rotas en los `.spec`. No ejecutes la suite completa. Responde en español con hallazgos numerados `V15-<área>-xx` (archivo:línea, severidad, motivo) o 'sin hallazgos'." Corrige los hallazgos válidos (nuevo commit) y repite la suite.

**Z. Cierre (OBLIGATORIO).**
- CLAUDE.md: sección corta "Estructura del repositorio" (`auth/`, `cliente/`, `backend/rutas/`, `packaging/`, `tests/helpers|banco/`, `docs/README.md`); ninguna ruta citada en CLAUDE.md puede quedar rota (`git grep` de cada una).
- Informe R15 con: tabla de ítems (Hecho / Revertido / No hecho + motivo); tests tocados; diferencias de compilación explicadas; ramas borradas y remotas por borrar; archivos sin seguimiento por borrar a mano (D9); evaluación 62304 (§ de decisiones) con la evidencia de cada punto 1–7; pendiente: actualizar `docs/arquitectura/DOC_Backend_Arquitectura_API_Servicios.docx`; DECISIONES SIN CONFIRMAR.
- Push de `tanda-15` (NO de `dev`, NO unir).
- Índice cuya **primera línea** dice: "Tanda 15: reorganización sin cambio funcional — suite N passed (base M), rutas/OpenAPI idénticos: sí/no, compilación equivalente: sí/no. Lista para unir a dev: sí/no."
- Fila `| Z | Hecha | … |` en `estado.md`.
