# Prompt para Claude Code — ejecutar la tanda 4 (20-oct-2026)

Pegar tal cual en una sesión nueva de Claude Code abierta en la raíz del repositorio, con todos los permisos activados.

---

Eres Claude Code trabajando en el repositorio del Software de Autoclave (Especifika). Cristian puede no estar presente: trabaja de forma autónoma de principio a fin.

1. Lee COMPLETO `docs/mis_plans/instruccion_claude_code_tanda_4.md`. Es la fuente de verdad (etapas B1 a B9, H1 y Z). Lee también la sección 0 de `docs/mis_plans/instruccion_claude_code_tanda_noche.md` y de `docs/mis_plans/instruccion_claude_code_tanda_3.md`, y `docs/informes/tanda3/DECISIONES_PARA_REVISAR.md` como contexto.
2. Si existe `docs/informes/tanda4/estado.md`, REANUDA desde la primera etapa no terminada; no repitas lo ya commiteado. Si se corta por límites de uso, continúa cuando se restablezcan.
3. Crea la rama `tanda-4` desde `dev` actualizada y ejecuta las etapas en orden. Una etapa solo se commitea con la suite completa en verde y, en las marcadas ★, con `safety-reviewer` y `timing-auditor` sin hallazgos Altos/Críticos abiertos. Pruebas primero. Informe por etapa en `docs/informes/tanda4/` y `estado.md` actualizado tras cada una.
4. Toma tú las decisiones de diseño que no estén cerradas, eligiendo lo más seguro y reversible. Cada una va como "DECISIÓN SIN CONFIRMAR" en el informe de su etapa y en `docs/informes/tanda4/DECISIONES_PARA_REVISAR.md`, en su propio commit para poder revertirla.
5. Git: autorizado commit, unir `tanda-4` a `dev` con `--no-ff` (suite verde) y `git push origin dev tanda-4`. NUNCA a `main`, nunca `--force`, nunca `git add -A`. No agregues `data/`, `.claude/`, bases de datos, fotos ni logs. Si un push falla, anótalo y sigue. Incluye en el primer commit `docs(tanda4)` los documentos `docs/mis_plans/instruccion_claude_code_tanda_4.md` y `docs/mis_plans/prompt_claude_code_tanda_4.md`, por ruta explícita.
6. No toques hardware, no compiles ejecutables, no cargues firmware, no ejecutes scripts `.ps1`, no instales software del sistema. Sí puedes editar `Autoclave.spec` (B2).
7. Si una etapa queda bloqueada o pendiente, dilo con el motivo y sigue con las demás.

Empieza ahora por crear `tanda-4` y la etapa B1.
