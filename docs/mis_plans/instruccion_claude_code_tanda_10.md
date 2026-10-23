# Instrucción maestra para Claude Code — Tanda 10 (sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 10` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda10/estado.md`.

**Contexto:** correcciones vistas en el equipo de pruebas el 23-oct (compilación D). Fuente de verdad: `docs/mis_plans/decisiones_tanda_10.md`, COMPLETO. Prevalece sobre D8-5.4 donde lo revierte (D10-1). Los ciclos en el equipo empiezan el lunes 26-oct.

**Modo:** igual que la tanda 9: máximo 4 subagentes a la vez, cada uno en su worktree y rama `tanda-10-<id>`, con solo sus pruebas (`PYTHONPATH=<worktree>/src`, comprobando `autoclave.__file__`); la suite completa solo en la sesión principal, una vez por cada unión. **NO termines el turno con subagentes activos.** No hay etapas ★ (ninguna cambia lógica de seguridad); si una etapa termina tocando lógica de seguridad, detente en ese punto y déjalo como PREGUNTA PARA CRISTIAN.

## 0. Reglas
Las de la sección 0 de la tanda 9, con estos cambios:
1. **Rama y archivos:** rama `tanda-10` desde `dev`; subramas `tanda-10-<id>`. Estado en `docs/informes/tanda10/estado.md`; informes en `docs/informes/tanda10/<id>_<nombre>.md`; decisiones sin confirmar en `docs/informes/tanda10/DECISIONES_PARA_REVISAR.md`; índice en `docs/informes/informe_tanda_<fecha>_t10.md`.
2. **Precondición (A0):** `docs/informes/tanda9/estado.md` tiene `| Z | Hecha |` y `dev` contiene `tanda-9`. Si no, escribe "Esperando el cierre de la tanda 9" en `tanda10/estado.md` y termina.
3. **Git:** nunca `main`, `--force`, `git add -A` ni `git push --delete`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`. No toques la entrada `stash@{0}` ajena. Une a `dev` con `--no-ff` y la suite en verde.
4. **Prohibido:** hardware o puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. Autorizado: PyInstaller en un clon limpio de la etiqueta e `ISCC.exe` (solo compilar).
5. **Ante ambigüedad:** lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR".
6. **Prioridad:** A0 → G10 → T10 → W10 → U10 (Ciclo/Preciclo primero, luego el barrido) → K10 → Z. Si el límite de uso amenaza, K10 y Z van antes que lo no empezado; Z se hace SIEMPRE.

## 1. Etapas
**A0.** Precondición; crea `tanda-10` desde `dev`; línea base de la suite; commit `docs(tanda10)` con esta instrucción, `decisiones_tanda_10.md` y el prompt.

**G10. Código de activación** (subagente, corto). D10-2: normalización en `activation.py` con la prueba del caso real, y fuente monoespaciada en el generador. Revisa que el asistente (`puente_instalacion.py`) y cualquier otro uso pasen por la misma validación.

**T10. Texto de CIC-10 sin presión** (subagente, corto). D10-3: solo textos es/en según la causa; prueba que con causa «sin presión de cámara» la acción no menciona la sonda Principal y que con causa de sonda Principal el texto no cambia. Caso en `hoja_pruebas_banco_equipo_pruebas.md`. No cambies la lógica del protocolo.

**W10. Pantalla 2 durante la instalación** (subagente). D10-4 con sus tres pruebas.

**U10. Abreviatura automática** (subagente; puede dividirse en U10a Ciclo/Preciclo y U10b barrido, una después de la otra). D10-1 completo:
- U10a: componente, convención de claves, ajuste de `test_v8b_textos.py`, Ciclo y Preciclo en es y en, y la prueba de D10-1.5 para esas dos pantallas.
- U10b: barrido de todas las pantallas con el banco de capturas y la prueba de D10-1.5 extendida a todas. Capturas antes/después en el informe.

**K10. Compilación E** (sesión principal). D10-5, con los mismos pasos y verificaciones de K9 (verificador neutro, prueba de humo, ensayo D → E sobre una copia con el perfil y la BD de la D, Setup compilado y no ejecutado, SHA-256, `usb/` con exactamente lo que va a la USB). Agrega a `usb/drivers/` lo que haya en `entrega/drivers/`; si sigue vacía, anótalo en el índice.

**Z. Cierre (OBLIGATORIO).** Suite en verde; unión a `dev` comprobada; push de `dev`, `tanda-10` y la etiqueta; índice con resumen, DECISIONES SIN CONFIRMAR, PREGUNTAS y lo que quedó sin hacer; primera línea del índice: si hay compilación E y si se recomienda instalarla antes del lunes; fila `| Z | Hecha |` en `estado.md`.

## 2. ACELERACIÓN (solo tanda 10, aprobada por Cristian 23-oct 11:34) — prevalece sobre la sección 0
La sesión se relanzó para acelerar. Al reanudar:
1. **Suite en paralelo:** instala `pytest-xdist` en el entorno de Python del proyecto (`pip install pytest-xdist`; es dependencia de prueba, no software del sistema) y corre la suite completa con `-n auto`. Si falla alguna prueba, repite SOLO esas pruebas en serie: si pasan en serie, es interferencia del paralelo (anótala en el informe, no es rojo); si fallan en serie, es rojo real. No agregues xdist a `requirements-dev.txt` (DECISIÓN SIN CONFIRMAR si crees que debe ir).
2. **Suite de integración en curso al cortar:** si `_suites_t10/integ` no dejó un resultado final en `suites/`, no la repitas aparte: se cubre con la suite tras unir U10b.
3. **U10b:** NO relances desde cero; revisa la rama `tanda-10-u10b` y su informe y continúa desde ahí (en un subagente). Mientras tanto, la sesión principal prepara K10 (clon limpio, entorno de compilación, dependencias); la compilación en sí empieza cuando U10b esté unida y la suite en verde.
4. **Una sola suite tras unir U10b**, y esa vale para K10 y para Z: no la repitas en Z si `dev` no cambió desde entonces.
