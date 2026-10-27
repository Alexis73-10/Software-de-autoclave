# Prompt para Claude Code — tanda 20 (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 20` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Código Clase C: velocidad sin sacrificar seguridad. Objetivo: que la entrega instale con el Setup y conecte con los módulos M31-U reales.

1. **Primero**, si existe `docs/informes/tanda20/estado.md` con etapas hechas, REANUDA desde la primera sin terminar (si una P quedó a medias, revisa su rama `tanda-20-<s>` antes de relanzarla). Si no existe, empieza por A0.
2. Lee COMPLETOS, en este orden: `docs/mis_plans/instruccion_claude_code_tanda_20.md`, `docs/mis_plans/decisiones_tanda_20.md`, `docs/mis_plans/adenda_tanda_19_banco.md`, `docs/informes/banco_m31_2026-10-27.md`, `docs/mis_plans/planeacion_enlace_modbus.md`.
3. **Nada del enlace serial se borra antes de que la etapa B (copia en `G:\Respaldos_autoclave\`) esté Hecha y verificada.** Si `G:` no está disponible, `CERRADO.txt` con `BLOQUEADO:` y terminas.
4. Hasta 4 subagentes a la vez: V y R de solo lectura; P en worktrees con su tabla de propiedad. Ningún subagente corre la suite completa; la principal sí, con `pytest tests -n auto`.
5. Reglas: nunca `main`, `--force`, `git add -A`, `git push` ni `git branch -D`. No toques módulos reales, puertos COM ni red real (simulador solo en 127.0.0.1). No ejecutes `.ps1`, el Setup ni la herramienta de táctiles. No escribas en el registro de Windows ni cambies la red de esta máquina. No leas el archivo de secretos. Ninguna contraseña real en repositorio, logs ni pruebas. En K, une a `dev` y ejecuta `tools/entrega/compilar_entrega.py --con-generador` solo si se cumplen sus condiciones.
6. Ante ambigüedad, lo más seguro y reversible, como «DECISIÓN SIN CONFIRMAR».
7. Al terminar: `docs/informes/tanda20/CERRADO.txt`, fila `| Z | Hecha | ... |` en `estado.md`, y la primera línea del índice dice si quedó unida a `dev` y qué versión se entregó. Si te detiene un bloqueo que necesita a Cristian, escribe igual `CERRADO.txt` con `BLOQUEADO:` y el motivo en la primera línea.

Empieza por A0 (o reanuda).
