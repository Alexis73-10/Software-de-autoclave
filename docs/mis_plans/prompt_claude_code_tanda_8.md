# Prompt para Claude Code — tanda 8 (noche 22/23-oct, sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 8` (`claude -p`, sin supervisión), y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todos los informes van en español.

1. Lee COMPLETOS:
   - `docs/mis_plans/instruccion_claude_code_tanda_8.md` (instrucción);
   - `docs/mis_plans/decisiones_tanda_8.md` (decisiones, fuente de verdad);
   - el índice de la tanda 7 `docs/informes/informe_tanda_2026-10-22_t7.md` y los informes que citen las decisiones.
2. Si existe `docs/informes/tanda8/estado.md`, REANUDA desde la primera etapa sin terminar. No rehagas el trabajo que ya tenga commits en su rama `tanda-8-*`.
3. **Velocidad, sin ahorrar tokens:**
   - después de A0, lanza EN PARALELO un subagente por etapa (H8, S1, S2, N8, R8, V8a, V8b, E1, E2, M8, U8, L8 y D8), cada uno en su worktree;
   - cada subagente commitea su informe en su rama y corre la suite con `PYTHONPATH=<worktree>/src`;
   - la sesión principal integra una rama a la vez, con la suite en verde, y luego compila (K8) y cierra (Z).
4. **Reglas:**
   - nunca `main`, `--force` ni `git add -A`;
   - no commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`;
   - compilar con PyInstaller está autorizado;
   - no toques hardware ni puertos COM reales, no cargues firmware, no ejecutes `.ps1` y no instales software del sistema;
   - ante ambigüedad, lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR";
   - en transiciones de ciclo, lo no definido es "PREGUNTA PARA CRISTIAN".
5. Al terminar, `estado.md` lleva la fila `| Z | Hecha | ... |`, y la primera línea del índice dice si se instala la compilación C.

Empieza ahora por A0 (o reanuda).
