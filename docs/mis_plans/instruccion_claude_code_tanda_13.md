# Instrucción maestra para Claude Code — Tanda 13 (mini-tanda, sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 13` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda13/estado.md`.

**Contexto:** VAP-01, la presión de saturación de `steam.py` da ≈2 kPa menos que las tablas de vapor. Fuente de verdad: `docs/mis_plans/decisiones_tanda_13.md`, COMPLETO. Prioridad: **velocidad**; la compilación sale esta noche para instalarla el lunes 26-oct en lugar de la H.

**Modo:** **sin subagentes ni revisor**: todo lo hace la sesión principal. La suite completa con `pytest -n auto` (si algo falla, repite en serie solo lo que falló).

## 0. Reglas
1. Rama `tanda-13` desde `dev`. Estado en `docs/informes/tanda13/estado.md`; informe único `docs/informes/tanda13/S13_saturacion_if97.md`; índice `docs/informes/informe_tanda_<fecha>_t13.md`.
2. **Precondición:** `docs/informes/tanda12/estado.md` tiene `| Z | Hecha |` y `dev` contiene `tanda-12`. Si no, anótalo y termina.
3. **Git:** nunca `main`, `--force`, `git add -A` ni `git push --delete`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`. No toques `stash@{0}`. Une a `dev` con `--no-ff` y la suite en verde.
4. **Prohibido:** hardware o puertos COM reales, firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. **Autorizado:** PyInstaller en un clon limpio de la etiqueta e `ISCC.exe` (solo compilar).
5. Ante ambigüedad: lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". No se cambia ninguna otra lógica de ciclo: solo `steam.py`, pruebas y documentos.
6. Todo en español.

## 1. Etapas
**A0.** Precondición, rama, commit `docs(tanda13)` con esta instrucción, las decisiones y el prompt. No hace falta línea base aparte: sirve la suite final de la tanda 12 (7531 passed).

**S13.** TDD:
- primero las pruebas de la decisión 4 (rojas con la fórmula vieja), luego `steam.py` con IAPWS-IF97 región 4;
- `grep -rn "p_saturacion_kpa\|t_saturacion_c" src tools` y comprobar en cada llamador que la excepción fuera de rango (decisión 3) no puede romper un ciclo;
- suite completa; recalcula y corrige los tests con valores de la fórmula vieja (decisión 5), sin relajar tolerancias, listando cada uno en el informe con valor viejo → nuevo;
- decisión 7 (programas del repo validan) y decisión 6 (documentos y `CLAUDE.md`);
- informe S13 con: tabla T / IF97 / fórmula vieja / diferencia para 100, 110, 121, 128, 134, 135, 140 °C; tests cambiados; DECISIONES SIN CONFIRMAR.

**K13. Compilación I** (mismos pasos y verificaciones que K12): verificador neutro y prueba de humo; ensayo H → I y G → I sobre copias con perfil y BD (los programas de usuario cargan; la consigna mostrada a 134 °C es 304.2 kPa); Setup compilado y no ejecutado; SHA-256; `usb/` con exactamente lo que va a la USB; LEEME con la sección «Cambios respecto a la H».

**Z. Cierre (OBLIGATORIO).** Suite en verde, unión a `dev`, push de `dev`, `tanda-13` y la etiqueta; índice cuya primera línea dice si hay compilación I y si se instala el lunes en lugar de la H; fila `| Z | Hecha |` en `estado.md`.
