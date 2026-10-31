# Prompt para Claude Code — tanda 13 (mini-tanda, sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 13` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Prioridad: velocidad.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_13.md` y `docs/mis_plans/decisiones_tanda_13.md`. De la tanda 12 lee solo el informe K12 (plantilla de K13).
2. Si existe `docs/informes/tanda13/estado.md`, REANUDA desde la primera etapa sin terminar.
3. Precondición: la tanda 12 está cerrada (`| Z | Hecha |`) y unida a `dev`. Si no, anótalo en `tanda13/estado.md` y termina.
4. Sin subagentes ni revisor: todo en la sesión principal. Suite completa con `-n auto`.
5. Nunca uses `main`, `--force` ni `git add -A`. No toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup y no instales software del sistema. Están autorizados PyInstaller e `ISCC.exe` (solo compilar).
6. Ante ambigüedad, elige lo más seguro y reversible y anótalo como "DECISIÓN SIN CONFIRMAR".
7. Al terminar, escribe la fila `| Z | Hecha | ... |` en `estado.md`; la primera línea del índice dice si se instala la compilación I.

Empieza por A0 (o reanuda).
