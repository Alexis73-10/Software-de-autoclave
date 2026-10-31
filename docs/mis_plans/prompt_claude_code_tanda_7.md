# Prompt para Claude Code — tanda 7 (noche 21/22-oct, sin supervisión)

La envía sola `tools/tanda7/lanzar_tanda7.ps1` (`claude -p`, sin supervisión) cuando termina la tanda 6, y la reenvía si la sesión se corta. Para lanzarla a mano: pegarla en una sesión nueva en la raíz del repositorio, con todos los permisos activados.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma toda la noche, sin detenerte a preguntar. Todos tus informes van en español.

1. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_7.md` (la fuente de verdad) y `docs/mis_plans/planeacion_asistente_modelo.md`. Lee también la sección 0 de las instrucciones de las tandas noche, 3, 4, 5 y 6, y `docs/informes/tanda6/estado.md`.
2. Si existe `docs/informes/tanda7/estado.md`, REANUDA desde la primera etapa sin terminar. Si se corta por límites de uso, continúa cuando se restablezcan.
3. **Prioridad absoluta:** hay que dejar un ejecutable instalable para las 2 p. m. del 22-oct. Haz A0 y enseguida K1 (compilación de la base estable, en `entrega/2026-10-22_a/`).
4. **Velocidad, sin ahorrar tokens:**
   - después de K1, lanza EN PARALELO un subagente por etapa (L1, P1, M1, C2, M2, R6, Q1 y D2), cada uno en su worktree;
   - lanza los revisores en paralelo;
   - la sesión principal solo coordina, integra (una rama a la vez, con la suite en verde tras cada unión) y compila.
5. **Plazos:**
   - a las 12:30 (hora de Bogotá) se congela: lo que no esté unido y en verde se queda en su rama;
   - K2 (`entrega/2026-10-22_b/`) tiene que estar lista a las 13:45, solo si hay algo nuevo y la suite está en verde;
   - D2 (depuración) se une a `dev` solo DESPUÉS de K2;
   - si la tanda 6 sigue activa, no toques la carpeta principal (regla 10);
   - Z se hace siempre.
6. **Reglas:**
   - nunca `main`, `--force` ni `git add -A`;
   - no commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`;
   - compilar con PyInstaller está autorizado;
   - no toques hardware ni puertos COM reales, no cargues firmware, no ejecutes `.ps1` y no instales software del sistema;
   - ante ambigüedad, lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR";
   - en transiciones de ciclo, lo no definido es "PREGUNTA PARA CRISTIAN".
7. Al terminar, la primera línea del índice dice qué carpeta de `entrega/` debe instalar Cristian.

Empieza ahora por A0.
