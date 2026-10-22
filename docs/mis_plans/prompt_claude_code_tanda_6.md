# Prompt para Claude Code — ejecutar la tanda 6 (nocturna, ~8 h)

Pegar tal cual en una sesión nueva de Claude Code abierta en la raíz del repositorio, con todos los permisos activados.

---

Eres Claude Code trabajando en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma y de corrido toda la noche, etapa tras etapa, sin detenerte a preguntar. Todos tus informes van en español.

1. Lee COMPLETO `docs/mis_plans/instruccion_claude_code_tanda_6.md`. Es la fuente de verdad (Bloque 1: E0, T2, C1, X1, I4 backend, R1, W1, D1; Bloque 2: B1, O3, O2a–O2h, I4 QML, H1; y Z). Lee también:
   - la sección 0 de las instrucciones de las tandas noche, 3, 4 y 5;
   - `docs/informes/tanda5/DECISIONES_PARA_REVISAR.md`, `T1_matriz_transiciones.md` y `O1_inventario_opciones.md`;
   - `docs/mis_plans/planeacion_opciones.md` (v4), `planeacion_i18n.md`, `planeacion_fin_de_ciclo_y_puertas.md` y `planeacion_estacion_windows.md`.
2. Si existe `docs/informes/tanda6/estado.md`, REANUDA desde la primera etapa no terminada. Si se corta por límites de uso, continúa cuando se restablezcan.
3. Orden de trabajo:
   - Empieza por E0: commitea lo pendiente en `tanda-5`, únela a `dev` y VERIFICA la unión con `git merge-base --is-ancestor`, haz el push y luego crea `tanda-6`.
   - Haz el Bloque 1 completo. El Bloque 2 (UI nueva) SOLO si existe `docs/mockups/tanda6/APROBADO.md`, siguiendo los mockups de esa carpeta. Vuelve a comprobarlo antes de empezar el Bloque 2. Si no existe, sáltalo y ve a Z.
   - Sigue en orden. Una etapa solo se commitea con la suite completa en verde y, en las ★, con los agentes indicados sin hallazgos Altos/Críticos abiertos.
   - Pruebas primero. Informe por etapa y `estado.md` actualizado tras cada una.
4. Decisiones:
   - Las de diseño no cerradas las tomas tú, eligiendo lo más seguro y reversible. Cada una va como "DECISIÓN SIN CONFIRMAR" en su informe y en `DECISIONES_PARA_REVISAR.md`.
   - En transiciones de ciclo y puertas, lo no definido en la sección 1 NO se cambia salvo que sea inseguro: va como "PREGUNTA PARA CRISTIAN".
5. Git:
   - Autorizado commit, unir `tanda-6` a `dev` con `--no-ff` (suite verde) y `git push origin dev tanda-6`.
   - NUNCA a `main`, nunca `--force`, nunca `git add -A`.
   - No agregues `data/`, `.claude/`, bases de datos, fotos ni logs.
   - Si un push falla, anota el error exacto y sigue.
6. No toques hardware, no compiles ejecutables, no cargues firmware, no EJECUTES scripts `.ps1` (sí puedes escribirlos en W1), no instales software del sistema.
7. Si una etapa queda bloqueada, anota el motivo y pasa a la siguiente según la prioridad de la regla 7. La etapa Z se hace siempre, con verificación de la unión y del push.

Empieza ahora por E0.
