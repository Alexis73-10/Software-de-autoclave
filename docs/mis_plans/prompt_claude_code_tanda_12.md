# Prompt para Claude Code — tanda 12 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 12` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Prioridad: velocidad.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_12.md` y `docs/mis_plans/decisiones_tanda_12.md`. De la tanda 11 lee solo `docs/informes/tanda11/brief_subagentes.md` y el informe K11 (plantilla de K12).
2. Si existe `docs/informes/tanda12/estado.md`, REANUDA desde la primera etapa sin terminar, sin rehacer lo commiteado en `tanda-12-*`. Los subagentes interrumpidos se continúan desde su rama e informe, no desde cero.
3. Precondición: la tanda 11 está cerrada (`| Z | Hecha |`) y unida a `dev`. Si no, anótalo en `tanda12/estado.md` y termina.
4. Máximo 4 subagentes a la vez, cada uno en su worktree, solo con sus pruebas y con su informe commiteado en su rama. Lanza E12 primero (es la más larga). La suite completa solo la corre la sesión principal, con `-n auto`, al unir. Un solo revisor (V12). NO termines el turno con subagentes activos.
5. Nunca uses `main`, `--force` ni `git add -A`. No toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup y no instales software del sistema. Están autorizados PyInstaller e `ISCC.exe` (solo compilar).
6. Ante ambigüedad, elige lo más seguro y reversible y anótalo como "DECISIÓN SIN CONFIRMAR".
7. Al terminar, escribe la fila `| Z | Hecha | ... |` en `estado.md`; la primera línea del índice dice si se instala la compilación H.

Empieza por A0 (o reanuda).
