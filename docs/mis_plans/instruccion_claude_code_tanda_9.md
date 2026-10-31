# Instrucción maestra para Claude Code — Tanda 9 (sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 9` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda9/estado.md`.

**Contexto:**
- Cristian instaló la compilación B en el equipo de pruebas sin sensores conectados (22-oct) y encontró 18 hallazgos, más 3 puntos nuevos. Están evaluados en `decisiones_tanda_9.md`.
- La tanda 8 NO se instala. La tanda 9 parte de `dev` con la tanda 8 ya unida y produce la **compilación D** con su Setup.
- Los ciclos en el equipo empiezan el lunes 26-oct: lo de D9-1 (bloqueos al arrancar) es lo primero.

**Modo: rendimiento dentro del límite de uso** (igual que la tanda 8):
- máximo 4 subagentes a la vez; el resto en cola, por la prioridad de la regla 8;
- los subagentes corren solo las pruebas de lo que tocan (`PYTHONPATH=<worktree>/src`, comprobando `autoclave.__file__`); la suite completa la corre solo la sesión principal, una vez por cada rama que une;
- revisores (`safety-reviewer`, `timing-auditor`, `sensor-role-auditor`) solo en las etapas ★: una pasada y una re-revisión si hubo Altos;
- contexto mínimo: cada subagente lee su sección de `decisiones_tanda_9.md` y el código que toca;
- **NO termines el turno con subagentes activos** (en `-p` el CLI los mata a los 10 min).

## 0. Reglas
Las de la sección 0 de la tanda 8, con estos cambios:
1. **Rama y archivos:** rama `tanda-9` desde `dev`; subramas `tanda-9-<id>`. Estado en `docs/informes/tanda9/estado.md`; informes en `docs/informes/tanda9/<id>_<nombre>.md`; decisiones sin confirmar en `docs/informes/tanda9/DECISIONES_PARA_REVISAR.md`; índice en `docs/informes/informe_tanda_<fecha>_t9.md`.
2. **Precondición (A0):** `docs/informes/tanda8/estado.md` tiene la fila `| Z | Hecha |` y `dev` contiene `tanda-8`. Si no, NO empieces: escribe en `tanda9/estado.md` "Esperando el cierre de la tanda 8" y termina el turno.
3. **Git:** nunca `main`, `--force`, `git add -A` ni `git push --delete`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`. Cada subagente commitea su informe en su rama antes de terminar. Une a `dev` con `--no-ff` y la suite en verde.
4. **Prohibido:** tocar hardware o puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. Autorizado: PyInstaller en un clon limpio de la etiqueta y compilar el `.iss` con `ISCC.exe` (sin ejecutar el instalador resultante).
5. **Ante ambigüedad:** lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". En transiciones de ciclo, estado seguro y puertas, lo no definido va como "PREGUNTA PARA CRISTIAN".
6. **Etapas ★:** sin Altos/Críticos abiertos antes de unir; repiten con la planta simulada, en los 4 programas, las celdas de transición que tocan; agregan casos a `hoja_pruebas_banco_equipo_pruebas.md` y entradas a `docs/riesgos/registro_riesgos.md`.
7. **Conflictos:** una rama a la vez, suite después de cada unión. i18n por unión de claves. Códigos de alarma nuevos: el siguiente libre según el orden de unión (S9 crea la alarma de coherencia puerta-presión; A9 cambia niveles: renumera al unir si hace falta). S9 y B9 tocan `control_loop.py`/`set_io.py`: une S9 primero.
8. **Prioridad:** A0 → S9 → B9 → E9 → A9 → P9 → C9 → X9 → K9 → Z. Después de K9, si queda límite: D9-13.5 (capturas) y D9-12. Z se hace SIEMPRE. Si el límite de uso amenaza con no alcanzar, K9 y Z van antes que cualquier etapa no empezada: la compilación D debe salir esta noche con lo que esté unido.

## 1. Fuente de verdad
`docs/mis_plans/decisiones_tanda_9.md`, COMPLETO (D9-1 a D9-13 y §Q). Prevalece sobre decisiones anteriores donde las revierte (E4/D-08 en parte, SAF-03 de T6, ES-11 para entradas NC).

## 2. Etapas
**A0.** Precondición de la regla 2. Crea `tanda-9` desde `dev`, anota la línea base de la suite y commitea `docs(tanda9)` con esta instrucción, `decisiones_tanda_9.md` y el prompt.

**S9. Estado seguro al arrancar y bloqueos ★** (subagente). D9-1 completo (1.1 a 1.6). Pruebas obligatorias, además de las celdas de planta simulada:
- arranque sin presión de cámara: sin confirmación, sin texto de "paro liberado", login, modo prueba, cambio de programa y apagado permitidos; inicio de ciclo bloqueado; CIC-10 + SEN-06;
- arranque con presión sobre la atmosférica: solo la lenta; con vacío: aire atmosférico;
- paro real pulsado y liberado en este encendido: sí exige confirmación;
- cambio de programa durante el protocolo: la seguridad no se relaja (temperatura de apertura y Principal del protocolo);
- coherencia puerta-presión: dispara con 3 lecturas, despeja con 3, no actúa en ciclo.

**B9. Buzzer y paro ★** (subagente). D9-9: primero la evidencia (registro de órdenes con la planta simulada y lectura del `.ino`), después la corrección en el PC y, si aplica, en el firmware (sin cargarlo). El informe dice la causa confirmada y deja el caso de banco.

**A9. Niveles de alarma y bitácora** (subagente, corto). D9-2 y D9-6. Prueba que los eventos retirados ya no se escriben y que los conservados sí.

**P9. Opciones: puertas simples, refresco y entradas NC** (subagente). D9-3, D9-4 y D9-5. Capturas de Parámetros del ciclo › Finalización, Parámetros del equipo (con el grupo "Cámara segura") y Entradas/Salidas, para un perfil de puertas simples y uno con puertas automáticas, en es y en. D9-4: barrido de todas las pantallas de Opciones con `model:` o bindings que llamen funciones, con prueba QML de refresco tras guardar.

**C9. Manejo de ciclos** (subagente). D9-10. Sección nueva en Opciones avanzadas, visible para técnico e ingeniero (la reasignación sigue solo para ingeniero); retira los botones de Parámetros del ciclo; textos es/en; capturas.

**E9. Entrega y Setup** (subagente). D9-7, D9-11 y D9-8:
- correo neutro y solo `cycles/factory/` en los `.spec`, con verificación en el build (como D8-3.18);
- Setup: casilla "Configurar este PC como estación del autoclave" (marcada) que ejecuta 01, 04 y 05 con la cuenta que instala; casilla aparte "Arranque sin logo" (desmarcada) para el 02; página de usuario y contraseña; reversión en el desinstalador; permisos de escritura en `C:\ProgramData\Especifika\Autoclave`. Revisa que los scripts acepten correr sin interacción y sin `-WhatIf`; NO los ejecutes;
- lista de verificación en `tools/instalador/LEEME.md` para el PC de prueba (instalar, reiniciar, inicio automático, Autoclave abierto, desinstalar, reversión);
- hoja de banco: casos de H4, H13, H16 (resueltos en la tanda 8) y D9-8 (modo 5 tras instalación limpia);
- D9-13.1: refresco de los archivos de configuración de fábrica al actualizar, con respaldo previo y el ensayo B → D sobre una copia (perfil y BD de la B).

**X9. Pendientes de la tanda 8** (subagente; ★ solo D9-13.3). D9-13.3 y D9-13.4.

**K9. Compilación D** (sesión principal, antes de Z). Desde `dev` en verde: etiqueta `inst-<fecha>-d`, pasos de K8 en `entrega/<fecha>_d/`, verificaciones D8-3.18 y D9-7, Setup `Autoclave_Setup_1.0.0-d.exe` con su SHA-256, y sección "Actualizar B → D" del LEEME (qué no tocar: perfil, calibración del equipo, BD, `ProgramData`), SIN pasos de copia a mano (D9-13.1). El equipo de pruebas tiene la B: la D se instala encima con el Setup.
- Además, arma `entrega/<fecha>_d/usb/` con EXACTAMENTE lo que va a la USB: `Autoclave_Setup_1.0.0-d.exe`, `SHA256SUMS.txt` (verificado contra el Setup ya copiado en esa carpeta), `LEEME_INSTALACION.md` y la carpeta `drivers/` de `entrega/`. NUNCA `GeneradorCodigos.exe`, el `.zip` ni la carpeta `Autoclave/` suelta. No formatees ni copies a ninguna USB: eso lo hace Cristian.

**Z. Cierre (OBLIGATORIO).** Suite en verde; unión a `dev` comprobada; push de `dev`, `tanda-9` y etiquetas; índice con resumen de 10 líneas, PREGUNTAS (incluidas las arrastradas de la tanda 8, D9-13), DECISIONES SIN CONFIRMAR y lo que quedó sin hacer; primera línea del índice: si hay compilación D y si se recomienda instalarla; fila `| Z | Hecha |` en `estado.md`.
