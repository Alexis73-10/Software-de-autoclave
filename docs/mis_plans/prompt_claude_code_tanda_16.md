# Prompt para Claude Code — tanda 16 combinada (sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 16` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Prioridad: velocidad, sin sacrificar seguridad (código Clase C).

1. **Primero, antes de leer nada más**, comprueba la precondición de A0: `tanda-15` y `versionado` contenidas en `dev`, y árbol limpio (sin contar los archivos no versionados). Si falla, escribe `| A0 | Esperando | <qué falta> |` en `docs/informes/tanda16/estado.md` y TERMINA de inmediato.
2. Lee COMPLETOS, en este orden:
   - `docs/mis_plans/instruccion_claude_code_tanda_16.md`;
   - `docs/mis_plans/decisiones_tanda_16.md`;
   - `docs/mis_plans/planeacion_control_vapor_chaqueta.md`;
   - `docs/mis_plans/planeacion_tanda_14_pendientes.md`.
3. Si existe `docs/informes/tanda16/estado.md` con etapas hechas, REANUDA desde la primera sin terminar. Si una etapa P quedó a medias, revisa la rama `tanda-16-<s>` antes de relanzar su subagente.
4. Hasta 5 subagentes a la vez:
   - V y R: solo lectura;
   - P: en worktrees, cada uno con sus archivos de la tabla de propiedad.

   Ningún subagente corre la suite completa; la sesión principal sí, con `pytest tests -n auto`.
5. El modo cámara (equipos sin chaqueta) queda idéntico al actual, salvo los cambios de la tanda 14.
   - Nunca `main`, `--force`, `git add -A` ni `git branch -D`.
   - No toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup, no leas el archivo de secretos.
   - En K, une a `dev` y ejecuta `tools/entrega/compilar_entrega.py --con-generador` solo si se cumplen sus condiciones.
6. Ante ambigüedad, lo más seguro y reversible, como «DECISIÓN SIN CONFIRMAR».
7. Al terminar, escribe la fila `| Z | Hecha | ... |` en `estado.md`. La primera línea del índice dice si quedó unida a `dev` y qué versión se entregó.

Empieza por A0 (o reanuda).
