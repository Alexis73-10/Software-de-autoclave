# Instrucción maestra para Claude Code — Tanda 8 (noche 22/23-oct-2026, sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 8`. Es una sesión headless (`claude -p`) que se relanza si se corta, así que REANUDA siempre desde `docs/informes/tanda8/estado.md`.

**Contexto:**
- El equipo de pruebas se instaló el 22-oct con la compilación B, `inst-2026-10-22-b`.
- Los CICLOS empiezan el lunes 26-oct.
- Esta tanda deja el software listo para esos ciclos y produce una compilación C, para actualizar el equipo antes del lunes.

**Modo: RENDIMIENTO DENTRO DEL LÍMITE DE USO** (cambio de Cristian, 22-oct 12:51; reemplaza "velocidad sin ahorrar tokens"). Con 13 subagentes y 13 suites completas a la vez, el límite se agotó en 40 min. Reglas:
- **Máximo 4 subagentes a la vez.** Los demás esperan en cola, en el orden de prioridad de la regla 8; cuando uno termina, entra el siguiente.
- **Los subagentes NO corren la suite completa.** Corren solo las pruebas de los módulos que tocan, más las que importan esos módulos (`pytest -q <archivos>` o `-k`).
- **La suite completa la corre ÚNICAMENTE la sesión principal**, una vez por cada rama que une a `tanda-8`.
- **Los revisores (`safety-reviewer`, `timing-auditor`, `sensor-role-auditor`) van solo en las etapas ★**, una pasada y una re-revisión si hubo Altos.
- **Contexto mínimo:** cada subagente lee solo su sección de `decisiones_tanda_8.md` y los archivos de código que va a tocar, no los informes completos de otras tandas.

La sesión principal coordina, integra y compila.

## 0. Reglas
Aplican las de la sección 0 de las tandas 6 y 7, con estos cambios:
1. **Rama y archivos.**
   - Rama `tanda-8`, creada desde `dev`; subramas `tanda-8-<id>`.
   - Estado en `docs/informes/tanda8/estado.md`; informes en `docs/informes/tanda8/<id>_<nombre>.md`.
   - Decisiones en `docs/informes/tanda8/DECISIONES_PARA_REVISAR.md`; índice en `docs/informes/informe_tanda_2026-10-23_t8.md`.
2. **Lecciones de la tanda 7, OBLIGATORIAS:**
   - Cada subagente commitea su informe EN SU RAMA antes de terminar. Nada de informes sin commit en el worktree.
   - El paquete `autoclave` está instalado en modo editable y apunta al repositorio principal. En un worktree, corre SIEMPRE `PYTHONPATH=<worktree>/src` y comprueba `autoclave.__file__` antes de dar una suite por buena.
   - La sesión principal actualiza `estado.md` y lo commitea al lanzar y al recibir cada subagente, para que el estado sea legible si la sesión se corta.
   - Al terminar, `estado.md` lleva la fila exactamente así: `| Z | Hecha | ... |`. El lanzador la busca.
3. **Git.**
   - Commit en las ramas de la tanda; unir a `dev` con `--no-ff` y la suite en verde; push de `dev`, `tanda-8` y las etiquetas.
   - NUNCA `main`, `--force`, `git add -A` ni `git push --delete`.
   - No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`.
   - `git branch -D` solo en los casos autorizados por D8-3.27.
4. **Compilación:**
   - autorizada con PyInstaller, en un clon limpio de la etiqueta;
   - prohibido tocar hardware o puertos COM reales, cargar firmware, EJECUTAR `.ps1` o instalar software del sistema;
   - para D8-3.26 se puede crear un entorno virtual nuevo con `pip`.
5. **Ante ambigüedad,** haz lo más seguro y reversible, márcalo "DECISIÓN SIN CONFIRMAR" y regístralo. En transiciones de ciclo y puertas, lo no definido en las decisiones va como "PREGUNTA PARA CRISTIAN".
6. **Etapas ★:** `safety-reviewer`, `timing-auditor` y `sensor-role-auditor` sin Altos/Críticos abiertos antes de unir. Cada etapa ★ repite con la planta simulada, en los 4 programas, las celdas de transición que toca, y agrega casos a la hoja de banco y al registro de riesgos.
7. **Conflictos:** une una rama a la vez y corre la suite después de cada unión. Los JSON de i18n se resuelven por unión de claves. `db_manager.py` tiene migraciones de S1, S2 y M8: usa números de migración consecutivos según el orden de unión y renumera al integrar si hace falta.
8. **Orden de prioridad:** A0 → H8 → S1 → S2 → N8 → R8 → V8a → E1 → E2 → M8 → U8 → L8 → D8 → V8b → K8 → Z. Z se hace SIEMPRE.

## 1. Fuente de verdad
- `docs/mis_plans/decisiones_tanda_8.md`, COMPLETO: D8-0 a D8-5.
- La sección "Hallazgos de la instalación del 22-oct" de este documento (al final): Cristian la completa antes de lanzar la tanda. Si está vacía, H8 no tiene objeto.

## 2. Etapas
**A0.** Crea `tanda-8` desde `dev`, anota la línea base de la suite y haz el primer commit `docs(tanda8)` con esta instrucción, `decisiones_tanda_8.md` y el prompt.

**H8. Hallazgos de la instalación** (subagente; ★ si toca ciclo, puertas o sensores). Corrige lo que se lista al final de este documento, con prueba. Lo que no tenga solución clara va como PREGUNTA.

**S1. SEN-01, sensor de presión sin señal** ★ (subagente). D8-1 completo.
- Detección sobre la señal cruda, con los márgenes como parámetros. Si Cristian anotó las cuentas ADC de la prueba de banco en la sección de hallazgos, úsalas para los valores por defecto y documenta el cálculo.
- Código de fallo propio, venteo solo por la lenta, bloqueo de inicio, "NO ABRIR", chaqueta, y solo los canales habilitados.

**S2. Transiciones del ciclo** ★ (uno o dos subagentes; si van dos, uno toma 2.6–2.10 y otro 2.11–2.16). D8-2 completo, un punto por commit.
- D8-2.10 (líquidos) con la verificación previa de las salidas que exige la decisión.
- D8-2.14 lleva migración de BD.

**E1. Equipo e instalación** (subagente; ★ solo D8-3.19).
- D8-3.17, `io_enabled` desde el perfil.
- D8-3.19, `aire_atmosferico_camara` en modo prueba.
- D8-3.21, apagado rechazado.
- D8-3.22, texto final del asistente.
- D8-3.20, el LEEME.

**E2. Nombres de familia y modelo** (subagente). D8-0 (Hospitalario/Laboratorio en toda la UI, el ticket, el PDF e Información del sistema, más la traducción en el ticket de arranque) y D8-3.23. Capturas del asistente y de Información del sistema en es y en.

**N8. Navegación de Opciones y cierre de sesión** (subagente). D8-4 completo, con capturas de los recorridos. Además, VERIFICA contra el código, sin cambiarlas salvo error evidente, las reglas de navegación de la UI del 19-oct y deja una tabla cumple / no cumple en el informe:
- Atrás regresa a la pantalla anterior;
- Home lleva a Preciclo o Ciclo;
- en Preciclo, el login va en el lugar de Home;
- las fallas y alarmas van en el espacio de alarmas, no en una barra superior;
- el panel de la campana no se abre solo;
- el Menú principal no tiene el botón de agregar tiempo de secado.

**R8. Opciones avanzadas: reasignación de E/S** ★ (subagente). D8-5.12 completo.

**V8. Observaciones de UI de Cristian** (dos subagentes en paralelo; ★ solo D8-5.7).
- V8a: D8-5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.9 y 5.10.
- V8b: D8-5.4, 5.5 y 5.11 (catálogos, abreviaturas, anglicismos, traducciones y capturas en es y en). Es el ÚLTIMO en unirse, para cubrir los textos nuevos de las demás etapas.

**M8. Mantenimiento** (subagente). D8-3.25.

**U8. Correo** (subagente, corto). D8-3.24: verifica que lo de C2 cumple. Además, retira `_email_dialog.py` (D8-3.27) si ya no lo usa nadie.

**L8. Dependencias** (subagente). D8-3.26, con un entorno virtual limpio solo para el producto. Verifica que la compilación C se pueda hacer con él. Si no se puede, compila con el entorno actual y explícalo.

**D8. Depuración** (subagente). D8-3.27 completo. Incluye la etapa aparte de P5: el posible código muerto en zonas de seguridad, revisado con `safety-reviewer`, que en la duda se CONSERVA. Mover imágenes de diseño o `estudio/` solo con la suite en verde y comprobando con `grep` que nada las carga.

**K8. Compilación C** (sesión principal, al final, antes de Z).
- Desde `dev` en verde: etiqueta `inst-2026-10-23-c` y repite los pasos de K1 de la tanda 7 en `entrega/2026-10-23_c/`.
- Además, verifica D8-3.18 (calibración neutra).
- Actualiza `entrega/LEEME_INSTALACION.md` con una sección "Actualizar un equipo ya instalado (B → C)". Debe decir qué carpetas reemplazar y cuáles NO tocar (perfil, calibración del equipo, BD, `ProgramData`), y en qué orden, con el software cerrado. Verifícalo leyendo el código de rutas (`app_root`, `ProgramData`) y prueba la actualización sobre una copia con un perfil y una BD de ejemplo.

**Z. Cierre (OBLIGATORIO).** Igual que en la tanda 7:
- suite en verde; unión a `dev` comprobada; push;
- índice con un resumen de 10 líneas; PREGUNTAS; lo que quedó sin hacer y en qué rama;
- la primera línea del índice dice si hay compilación C y si se recomienda instalarla;
- la fila `| Z | Hecha |` en `estado.md`.

## Hallazgos de la instalación del 22-oct (los completa Cristian antes de lanzar)
- (vacío)
