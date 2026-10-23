# Prompt para Claude Code — tanda 11 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 11` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_11.md` y `docs/mis_plans/decisiones_tanda_11.md`. De la tanda 10, lee solo el índice (`docs/informes/informe_tanda_*_t10.md`) y el informe K10, que es la plantilla de K11.
2. Si existe `docs/informes/tanda11/estado.md`, REANUDA desde la primera etapa sin terminar, sin rehacer lo commiteado en `tanda-11-*`.
3. Precondición: la tanda 10 está cerrada (`| Z | Hecha |`) y unida a `dev`. Si no, anótalo en `tanda11/estado.md` y termina.
4. Máximo 4 subagentes a la vez (aprobado para esta tanda), cada uno en su worktree, solo con sus pruebas y con su informe commiteado en su rama. La suite completa solo la corre la sesión principal, con `-n auto`, al unir. NO termines el turno con subagentes activos.
5. Nunca uses `main`, `--force` ni `git add -A`. No toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup y no instales software del sistema. Están autorizados PyInstaller e `ISCC.exe` (solo compilar).
6. Ante ambigüedad, elige lo más seguro y reversible y anótalo como "DECISIÓN SIN CONFIRMAR".
7. Al terminar, escribe la fila `| Z | Hecha | ... |` en `estado.md`; la primera línea del índice dice si se instala la compilación G.

Empieza por A0 (o reanuda).
