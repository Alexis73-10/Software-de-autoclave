# Prompt para Claude Code — tanda 15 (reorganización, sin supervisión)

Lo envía `tools/tandas/lanzar_tanda.ps1 -Tanda 15` (`claude -p`) y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español. Prioridad: velocidad.

1. **Primero y antes de leer nada más**, comprueba la precondición de A0 (tanda 13 cerrada y unida a `dev`, `licencia-l0` unida a `dev`, árbol limpio). Si falla, escribe `| A0 | Esperando | <qué falta> |` en `docs/informes/tanda15/estado.md` y TERMINA de inmediato.
2. Lee COMPLETOS `docs/mis_plans/instruccion_claude_code_tanda_15.md` y `docs/mis_plans/decisiones_tanda_15.md`.
3. Si existe `docs/informes/tanda15/estado.md` con etapas hechas, REANUDA desde la primera sin terminar.
4. Hasta 4 subagentes a la vez, solo en compilaciones (A0, ORG-07, K) y revisores (V); los movimientos de código los hace la sesión principal. Los subagentes no corren la suite completa; la sesión principal sí, con `-n auto`.
5. Cero cambio funcional. Nunca `main`, `--force`, `git add -A`, `git branch -D`, ni unir a `dev`. No toques hardware ni puertos COM, no cargues firmware, no ejecutes `.ps1` ni el Setup, no instales software del sistema, no borres archivos sin seguimiento de git. Autorizados PyInstaller e `ISCC.exe` (solo compilar).
6. Ante ambigüedad, lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR".
7. Al terminar, fila `| Z | Hecha | ... |` en `estado.md`; la primera línea del índice dice si la rama está lista para unir a `dev`.

Empieza por A0 (o reanuda).
