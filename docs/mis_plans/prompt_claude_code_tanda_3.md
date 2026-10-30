# Prompt para Claude Code — ejecutar la tanda 3 (noche del 20-oct-2026)

Pegar tal cual en una sesión nueva de Claude Code abierta en la raíz del repositorio, con todos los permisos activados.

---

Eres Claude Code trabajando en el repositorio del Software de Autoclave (Especifika). Cristian se acostó y NO responderá preguntas esta noche: trabaja de forma autónoma de principio a fin.

1. Lee COMPLETO `docs/mis_plans/instruccion_claude_code_tanda_3.md`. Es la fuente de verdad (incluye E0, las etapas A1, A2, S4, U5, T1, M1, C1, C2, O1, F1, E1, H1 y Z). Lee también la sección 0 de `docs/mis_plans/instruccion_claude_code_tanda_noche.md` (reglas generales) y `docs/informes/informe_tanda_2026-10-19.md` y `docs/informes/tanda2/S3b_cic10_propuesta.md` como contexto.
2. Si existe `docs/informes/tanda3/estado.md`, REANUDA desde la primera etapa no terminada; no repitas lo ya commiteado. Si se corta por límites de uso, continúa solo cuando se restablezcan.
3. Ejecuta las etapas en el orden indicado, empezando por E0. Una etapa solo se commitea con la suite completa en verde y, en las de seguridad, con `safety-reviewer` y `timing-auditor` sin hallazgos Altos/Críticos abiertos. Pruebas primero. Informe por etapa en `docs/informes/tanda3/`, y `estado.md` actualizado tras cada una.
4. Toma tú las decisiones de diseño que no estén cerradas en el documento, eligiendo siempre lo más seguro y reversible. Cada decisión va como "DECISIÓN SIN CONFIRMAR" en el informe de su etapa y se resume en `docs/informes/tanda3/DECISIONES_PARA_REVISAR.md` con: qué decidiste, por qué, la alternativa, el commit y cómo revertirla. Cristian las revisará mañana y cambiará lo que no le parezca; por eso cada decisión debe estar en su propio commit, separable.
5. Git: tienes autorización expresa de Cristian, solo para esta tanda, para hacer commits, unir `tanda-2` y luego `tanda-3` a `dev` con `--no-ff` (solo con la suite en verde) y hacer `git push origin` de `dev`, `tanda-2` y `tanda-3`. NUNCA a `main`, nunca `--force`, nunca reescribas historia publicada, nunca `git add -A`. No agregues `data/`, `.claude/`, bases de datos, fotos ni logs. Si un push falla, anótalo y sigue.
6. Hay otra sesión de Claude con trabajo sin commit en el mismo árbol (ejecutable único e intro de arranque). Sigue exactamente lo que dice la Etapa 0 sobre esperar, revisar y commitear ese trabajo, o dejarlo fuera si sigue activo o rompe pruebas.
7. No toques hardware, no compiles ni cargues firmware, no compiles ejecutables, no ejecutes los scripts de Windows (`.ps1`) que escribas, no instales software del sistema.
8. Al terminar deja: `docs/informes/informe_tanda_2026-10-20.md` (índice), `estado.md`, `DECISIONES_PARA_REVISAR.md` con un resumen de 10 líneas arriba, y el comando exacto para unir `dev` a `main` más la lista de commits que entrarían. Si una etapa queda bloqueada o pendiente, dilo con el motivo y sigue con las demás.

Empieza ahora por la Etapa 0.
