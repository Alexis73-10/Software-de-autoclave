## CONTEXTO COMÚN (tanda 9, noche 23-oct-2026, sin supervisión; Cristian NO está — no preguntes, decide y documenta)
Repositorio: Software de Autoclave (Especifika), IEC 62304 Clase C. Todo informe en ESPAÑOL.
Estás en un worktree aislado creado desde la rama `tanda-9` (contiene `dev` 1ff5afa, con la tanda 8 unida). Lee COMPLETOS antes de empezar:
- tu sección de `docs/mis_plans/decisiones_tanda_9.md` (FUENTE DE VERDAD; tu etapa cita sus puntos D9-x) y la "Causa común" si tu etapa es S9;
- tu etapa en la sección 2 de `docs/mis_plans/instruccion_claude_code_tanda_9.md` y sus reglas §0;
- `CLAUDE.md` del repo (convenciones de fases, `time.monotonic()`, debounce de 3 lecturas, etc.);
- de la tanda 8, solo los informes que cite tu sección (`docs/informes/tanda8/*.md`).
Contexto mínimo: no leas otras secciones ni otros informes sin necesidad.

### Reglas obligatorias
1. Primero: `git log -1` (debe contener 1ff5afa en su historia; si tu worktree no parte de `tanda-9`, haz `git checkout -b tanda-9-<id> tanda-9`) y crea tu rama: `git checkout -b tanda-9-<id>` (id en minúsculas, indicado abajo). Todo commit va en esa rama.
2. Git: NUNCA `main`, `--force`, `git add -A`, `git push --delete`, ni rebase/merge a otras ramas. Agrega archivos por nombre. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, logs ni fotos (las capturas que pida tu etapa sí, en `docs/informes/tanda9/capturas/<id>/`). NO hagas push.
3. Prohibido: tocar hardware/puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. Compilar con PyInstaller/`ISCC.exe` solo si tu etapa lo dice.
4. El paquete `autoclave` está instalado en modo editable apuntando al repo PRINCIPAL. En tu worktree corre SIEMPRE con `PYTHONPATH=<ruta absoluta de tu worktree>/src` y comprueba `python -c "import autoclave;print(autoclave.__file__)"` antes de dar por buena cualquier prueba.
5. Todo texto visible nuevo va al catálogo i18n (es y en, `src/autoclave/i18n/`), sin abreviaturas ni anglicismos en es. Todo valor visible de presión/temperatura pasa por el módulo de unidades.
6. Ante ambigüedad: lo más seguro y reversible, marcado "DECISIÓN SIN CONFIRMAR" en tu informe. En transiciones de ciclo, estado seguro y puertas, lo no definido en las decisiones NO se cambia: va como "PREGUNTA PARA CRISTIAN".
7. TDD: prueba primero, luego código. Commits pequeños con mensaje `tipo(tanda9-<id>): ...` terminando con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
8. NO corras la suite completa (la corre solo la sesión principal al unir). Corre ÚNICAMENTE las pruebas de los módulos que tocas y de los que los importan (`grep -rl` en `tests/`). Si falla alguna prueba QML por temporización ajena a tu cambio, repítela aislada y documéntalo.
9. Si tu etapa es ★: lanza (si tienes la herramienta Agent) los revisores `safety-reviewer`, `timing-auditor` y, si tocas sensores, `sensor-role-auditor` sobre tu diff, EN PARALELO: una pasada y una re-revisión si hubo Altos; corrige todo Alto/Crítico. Si no puedes lanzarlos, dilo en el informe (la sesión principal los correrá). Además repite con la planta simulada, en los 4 programas de fábrica, las celdas de transición que tocas (modelo: `docs/informes/tanda8/S1_ensayo_tabla.md`, `tests/test_s1_ensayo_simulador.py`, `tests/test_r8_planta_simulada.py`) y agrega casos a `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` y entradas a `docs/riesgos/registro_riesgos.md`.
10. Códigos de alarma nuevos: usa el siguiente libre del catálogo actual e indícalo en tu respuesta final (la sesión principal renumera al unir si choca).
11. ANTES DE TERMINAR: escribe tu informe en `docs/informes/tanda9/<ID>_<nombre>.md` (qué se hizo por punto D9, commits, pruebas nuevas y su resultado EXACTO con la ruta de `autoclave.__file__`, DECISIONES SIN CONFIRMAR, PREGUNTAS PARA CRISTIAN, pendientes) y COMMITÉALO EN TU RAMA. Nada sin commit al terminar.
12. Tu respuesta final (para la sesión principal): rama, último commit, pruebas corridas y resultado, archivos "puntos de choque" que tocaste (i18n, `db_manager.py` + número de migración, `control_loop.py`, `set_io.py`, catálogo de alarmas, QML compartidos), códigos de alarma nuevos, y Altos/Críticos abiertos si los hay. Breve.
