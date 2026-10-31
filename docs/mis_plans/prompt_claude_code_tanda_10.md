# Prompt para Claude Code — tanda 10 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 10` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_10.md` y `docs/mis_plans/decisiones_tanda_10.md`. De la tanda 9, solo el índice (`docs/informes/informe_tanda_*_t9.md`) y los informes que necesites (CAP9 para el banco de capturas, K9 para la compilación).
2. Si existe `docs/informes/tanda10/estado.md`, REANUDA desde la primera etapa sin terminar, sin rehacer lo commiteado en `tanda-10-*`.
3. Precondición: la tanda 9 cerrada (`| Z | Hecha |` en `docs/informes/tanda9/estado.md`) y unida a `dev`. Si no, anótalo en `tanda10/estado.md` y termina.
4. Máximo 4 subagentes a la vez, cada uno en su worktree, con solo sus pruebas y su informe commiteado en su rama; la suite completa solo en la sesión principal al unir. NO termines el turno con subagentes activos.
5. Nunca `main`, `--force` ni `git add -A`; no toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup, no instales software del sistema. PyInstaller e `ISCC.exe` (solo compilar) están autorizados.
6. Ante ambigüedad, lo más seguro y reversible como "DECISIÓN SIN CONFIRMAR". Si algo termina tocando la lógica de estado seguro, ciclo o puertas, no lo cambies: "PREGUNTA PARA CRISTIAN".
7. Al terminar, la fila `| Z | Hecha | ... |` en `estado.md` y la primera línea del índice dice si se instala la compilación E.

Lee y aplica la sección 2 (ACELERACIÓN) de la instrucción antes de seguir.

Empieza por A0 (o reanuda).
