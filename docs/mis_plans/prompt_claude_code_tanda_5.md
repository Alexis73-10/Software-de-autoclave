# Prompt para Claude Code — ejecutar la tanda 5 (20-oct-2026)

Pegar tal cual en una sesión nueva de Claude Code abierta en la raíz del repositorio, con todos los permisos activados.

---

Eres Claude Code trabajando en el repositorio del Software de Autoclave (Especifika). Cristian puede no estar presente: trabaja de forma autónoma de principio a fin. Todos tus informes y respuestas van en español.

1. Lee COMPLETO `docs/mis_plans/instruccion_claude_code_tanda_5.md`. Es la fuente de verdad (etapas E0, R0, P1–P3, O1, T1, U1, I1–I3, O2, H1 y Z). Lee también:
   - La sección 0 de `instruccion_claude_code_tanda_noche.md`, `_tanda_3.md` y `_tanda_4.md`.
   - `docs/informes/tanda4/DECISIONES_PARA_REVISAR.md`.
   - `docs/mis_plans/planeacion_opciones.md` (v4), `planeacion_i18n.md` y `planeacion_fin_de_ciclo_y_puertas.md`.
2. Si existe `docs/informes/tanda5/estado.md`, REANUDA desde la primera etapa no terminada. Si se corta por límites de uso, continúa cuando se restablezcan.
3. Empieza por E0, ANTES de crear la rama:
   - Integra en `dev` los cambios sin commit de la otra sesión con commits por tema y sin churn de saltos de línea.
   - Luego crea `tanda-5` desde `dev` y sigue en orden.
   - Una etapa solo se commitea con la suite completa en verde y, en las marcadas ★, con `safety-reviewer` y `timing-auditor` (y `sensor-role-auditor` donde se indique) sin hallazgos Altos/Críticos abiertos.
   - Pruebas primero. Informe por etapa en `docs/informes/tanda5/` y `estado.md` actualizado tras cada una.
4. Toma tú las decisiones de diseño no cerradas, eligiendo lo más seguro y reversible. Cada una va como "DECISIÓN SIN CONFIRMAR" en el informe de su etapa y en `DECISIONES_PARA_REVISAR.md`. En las transiciones de ciclo (T1), lo ambiguo NO se cambia salvo que sea inseguro: va como "PREGUNTA PARA CRISTIAN".
5. Git:
   - Autorizado commit, unir `tanda-5` a `dev` con `--no-ff` (suite verde) y `git push origin dev tanda-5`.
   - NUNCA a `main`, nunca `--force`, nunca `git add -A`.
   - No agregues `data/`, `.claude/`, bases de datos, fotos ni logs.
   - Si un push falla, anótalo y sigue.
   - Incluye en el primer commit `docs(tanda5)` los dos documentos de la tanda 5, por ruta explícita.
6. No toques hardware, no compiles ejecutables, no cargues firmware, no ejecutes scripts `.ps1`, no instales software del sistema.
7. Si una etapa queda bloqueada, dilo con el motivo y sigue con las demás, respetando la prioridad de la regla 7 de la sección 0.

Empieza ahora por E0.
