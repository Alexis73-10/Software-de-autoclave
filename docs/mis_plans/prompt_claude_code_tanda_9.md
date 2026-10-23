# Prompt para Claude Code — tanda 9 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 9` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_9.md` y `docs/mis_plans/decisiones_tanda_9.md`. De la tanda 8, solo el índice (`docs/informes/informe_tanda_*_t8.md`) y los informes que citen las decisiones.
2. Si existe `docs/informes/tanda9/estado.md`, REANUDA desde la primera etapa sin terminar, sin rehacer lo commiteado en `tanda-9-*`.
3. Precondición: la tanda 8 cerrada (`| Z | Hecha |` en `docs/informes/tanda8/estado.md`) y unida a `dev`. Si no, anótalo en `tanda9/estado.md` y termina.
4. Máximo 4 subagentes a la vez, cada uno en su worktree, con solo sus pruebas y su informe commiteado en su rama; la suite completa solo en la sesión principal al unir. NO termines el turno con subagentes activos.
5. Nunca `main`, `--force` ni `git add -A`; no toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup, no instales software del sistema. PyInstaller e `ISCC.exe` (solo compilar) están autorizados.
6. Ante ambigüedad, lo más seguro y reversible como "DECISIÓN SIN CONFIRMAR"; en estado seguro, ciclo y puertas, "PREGUNTA PARA CRISTIAN".
7. Al terminar, la fila `| Z | Hecha | ... |` en `estado.md` y la primera línea del índice dice si se instala la compilación D.

Empieza por A0 (o reanuda).
