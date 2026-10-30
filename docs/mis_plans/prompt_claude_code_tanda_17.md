# Prompt para Claude Code — tanda 17 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 17` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Prioridad: velocidad, sin sacrificar seguridad (código Clase C).

1. **Primero, antes de leer nada más**, si existe `docs/informes/tanda17/estado.md` con etapas hechas, REANUDA desde la primera sin terminar. Si una etapa P quedó a medias, revisa la rama `tanda-17-<s>` antes de relanzar su subagente. Si no existe, empieza por A0 tal como la define la instrucción.
2. Lee COMPLETOS, en este orden:
   - `docs/mis_plans/instruccion_claude_code_tanda_17.md`;
   - `docs/mis_plans/decisiones_tanda_17.md`.
3. Hasta 4 subagentes a la vez:
   - V y R: solo lectura;
   - P: en worktrees, cada uno con sus archivos de la tabla de propiedad.

   Ningún subagente corre la suite completa; la sesión principal sí, con `pytest tests -n auto`.
4. Reglas:
   - Nunca `main`, `--force`, `git add -A` ni `git branch -D`.
   - No toques hardware ni puertos COM, no cargues firmware.
   - No ejecutes `.ps1`, el Setup ni la herramienta de táctiles.
   - No escribas en el registro de Windows ni cambies la zona horaria de esta máquina.
   - No leas el archivo de secretos.
   - En K, une a `dev` y ejecuta `tools/entrega/compilar_entrega.py --con-generador` solo si se cumplen sus condiciones.
5. Ante ambigüedad, lo más seguro y reversible, como «DECISIÓN SIN CONFIRMAR».
6. Al terminar:
   - escribe `docs/informes/tanda17/CERRADO.txt`;
   - escribe la fila `| Z | Hecha | ... |` en `estado.md`;
   - la primera línea del índice dice si quedó unida a `dev` y qué versión se entregó.

   Si te detiene un bloqueo que necesita a Cristian, escribe igual `CERRADO.txt` con `BLOQUEADO:` y el motivo en la primera línea.

Empieza por A0 (o reanuda).
