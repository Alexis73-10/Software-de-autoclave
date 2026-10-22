# Instrucción maestra para Claude Code — Tanda 7 (noche 21/22-oct-2026, sin supervisión)

> Arranca sola: la lanza `tools/tanda7/lanzar_tanda7.ps1` cuando termina la tanda 6. Esa sesión es headless (`claude -p`): si se corta, el lanzador te vuelve a abrir con el mismo prompt, así que REANUDA siempre desde `estado.md`.

**Contexto:** el JUEVES 22-oct, hacia las 2 p. m., Cristian instala el software en el equipo de pruebas. Ese día solo hará:
- instalación con el asistente;
- verificación de Entradas/Salidas;
- calibración de sensores.

Los ciclos NO se ejecutan hasta el lunes 26-oct. **Lo único imprescindible es que haya un ejecutable instalable.** Todo lo demás es mejora.

**Modo de trabajo: VELOCIDAD, sin ahorrar tokens.**
- Lanza subagentes EN PARALELO, cada uno en su propio worktree (`isolation: worktree`), en lugar de uno a uno.
- Usa tantos como etapas independientes haya y lanza las revisiones (safety-reviewer, timing-auditor, sensor-role-auditor) en paralelo con el trabajo siguiente.
- No resumas ni recortes contexto para ahorrar.
- La sesión principal coordina, integra (une ramas, resuelve conflictos, corre la suite) y compila.

## 0. Reglas
Aplican las de la sección 0 de las tandas noche, 3, 4, 5 y 6, con estos cambios:
1. **Rama y archivos.**
   - Rama `tanda-7`, creada desde `dev` DESPUÉS de verificar el cierre de la tanda 6 (etapa A0).
   - Subramas `tanda-7-<id>`.
   - Estado en `docs/informes/tanda7/estado.md`; si existe, REANUDA.
   - Informes en `docs/informes/tanda7/<id>_<nombre>.md` y decisiones en `docs/informes/tanda7/DECISIONES_PARA_REVISAR.md`.
   - Índice en `docs/informes/informe_tanda_2026-10-22_t7.md`.
   - Si se corta por límites de uso, continúa cuando se restablezcan.
2. **Git.**
   - Commit en las ramas de la tanda; unir a `dev` con `--no-ff` solo con la suite en verde; `git push origin dev tanda-7` y las etiquetas.
   - NUNCA `main`, `--force` ni `git add -A`. No agregues `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`, fotos ni logs.
   - Si el push falla o lo bloquea el control de permisos, anota el error exacto y sigue: el push lo hace Cristian.
3. **Compilar está AUTORIZADO en esta tanda** (etapas K1 y K2), solo con PyInstaller y los `.spec` del repositorio. Sigue PROHIBIDO:
   - tocar hardware o puertos COM reales;
   - cargar firmware;
   - EJECUTAR scripts `.ps1`;
   - instalar software del sistema.

   Si PyInstaller falta en el entorno virtual del proyecto, puedes instalarlo con `pip` SOLO dentro de ese entorno virtual.
4. **Ante ambigüedad,** haz lo más seguro y reversible, márcalo "DECISIÓN SIN CONFIRMAR" y regístralo. En transiciones de ciclo y puertas, lo que no esté definido en la sección 1 NO se cambia: va como "PREGUNTA PARA CRISTIAN".
5. **Textos y unidades.** Todo texto visible nuevo va en i18n es/en. Todo valor de presión o temperatura visible pasa por el módulo de unidades. Nada nuevo bloquea un ciclo ni altera la seguridad, salvo Q1.
6. **Agentes.**
   - En las etapas ★, `safety-reviewer` y `timing-auditor` (y `sensor-role-auditor` si toca sondas) deben quedar sin hallazgos Altos/Críticos abiertos antes de unir.
   - Suite completa en verde en cada unión. Anota la línea base al inicio.
7. **Conflictos.** `i18n/es.json` y `en.json`, `Instalacion.qml` y `db_manager.py` son puntos de choque entre subagentes.
   - La sesión principal une de UNA rama a la vez y corre la suite después de cada unión.
   - En los JSON de i18n, resuelve por unión de claves, sin perder ninguna, y corre `tests/test_i18n.py`.
8. **Plazos (hora de Bogotá; usa la hora del sistema).**
   - K1 tiene prioridad absoluta sobre todo lo demás.
   - A las **12:30 del 22-oct** se congela el trabajo: lo que no esté unido y en verde queda en su rama, sin unir, y se pasa a K2 y Z.
   - K2 tiene que estar lista a las **13:45**. Cristian instala hacia las 14:00.
   - D2 (depuración) NUNCA entra en las compilaciones de mañana: se une a `dev` solo DESPUÉS de K2.
9. **Orden de prioridad** (si no alcanza el tiempo, se cae lo último): A0 → K1 → L1 → P1 → M1 → C2 → M2 → R6 → Q1 → K2 → D2 → Z. Z se hace SIEMPRE.
10. **Si la tanda 6 sigue activa** (A0 lo detecta): NO toques la carpeta principal del repositorio, ni hagas checkout ni stash en ella. Trabaja todo en worktrees creados desde el último commit de `tanda-6`. Las uniones a `dev` esperan a que la tanda 6 cierre. Si no ha cerrado a las 12:30, compila K2 desde la rama `tanda-7` en un worktree y explícalo en el índice.

## 1. Decisiones de Cristian (21-oct, noche) — fuente de verdad
1. **Asistente con cálculo de modelo:** según `docs/mis_plans/planeacion_asistente_modelo.md` (aprobado), que incluye:
   - el nombre `SPK-SAT <L><V|H>[2][-LAB]`;
   - solo piso y laboratorio de piso;
   - capacidad entera de 20 a 2000 L;
   - nombre siempre calculado;
   - sin perfil preinstalado.
2. **Fallo del correo (pendiente (a) de la tanda 6):** a una dirección escrita a mano no llega nada, aunque el software diga que se envió. Hay que corregirlo.
3. **Preguntas abiertas: se aceptan las recomendaciones.**
   - **R1-P1:** `exit_test_mode` devuelve el ACK del ALL_OFF y se anota en la bitácora, sin cambiar qué se apaga.
   - **R1-P2:** `esta_preparado()` usa el resultado del tick y no vuelve a llamar a `mantener_presion_camara`. Va con prueba y con un caso nuevo en la hoja de banco (el aire cierra a los 3 ticks reales).
   - **R1-P3:** `rango_calentamiento` se separa en `rango_calentamiento_temp` (°C, clase "diferencia") y `rango_calentamiento_pres` (kPa, clase "diferencia"), con el mismo defecto que hoy. Incluye migración de los archivos viejos (copiar el valor a los dos) y un caso en la hoja de banco.
   - **R1-P4:** si el protocolo de fallo ya corrió por otra causa y después se pierde el Principal, se pasa igual a `solo_lenta` (criterio de P-2 sin importar el orden).
   - **R1-P5:** durante la tolerancia por DI vencida, `/cycle/abort` ACEPTA la cancelación. La marca se procesa al volver los datos o al vencer la tolerancia, y la respuesta lo dice.
   - **T2-a:** los segundos de tolerancia por DI vencida NO cuentan como exposición en ESTERILIZACION. El temporizador de exposición se pausa durante la tolerancia y el ticket anota "Sin datos de la tarjeta: n s".
   - **T2-b:** DESPEJAR de COM-02/03 exige que el enlace haya vuelto a "ok" (3 tramas vigentes seguidas). No exige sesión, porque el operador despeja sin técnico (D-06).
   - **T2-c:** la marca "CARGA NO ESTÉRIL" va en TODO ciclo que no termine COMPLETADO: FALLO, CANCELADO, paro de emergencia e INTERRUMPIDO.
4. **Mantenimiento: E1 SÍ entra (etapa M2); el formulario del preventivo NO.** (Corrección del 22-oct, 00:30: la versión anterior de este punto contradecía la etapa M2.)
5. **Recordatorios para el informe final (no se tocan):**
   - el formulario del preventivo (P-1 a P-10 de `planeacion_mantenimiento.md`);
   - el retiro del código de equipos de mesa;
   - el predictivo.

## 2. Etapas

**A0. Verificar el cierre de la tanda 6** (sesión principal, sin subagentes).
- Lee `docs/informes/tanda6/estado.md` y el índice de la tanda 6.
- Primero decide si la tanda 6 sigue activa: Z no aparece "Hecha" en su `estado.md` y hay archivos del árbol principal modificados en los últimos 20 min. Si sigue activa, aplica la regla 10.
- Comprueba que `git merge-base --is-ancestor tanda-6 dev` sea OK y que las ramas `tanda-6-o2fgh` y demás `tanda-6-*` estén contenidas en `tanda-6`.
- Si la tanda 6 dejó etapas sin hacer o ramas sin unir, NO las completes aquí: anótalas para R6.
- Si `tanda-6` no está unida a `dev` y su suite está en verde, únela tú (`--no-ff`) y anótalo.
- Si hay cambios sin commit de la tanda 6 en el árbol, NO los descartes ni los commitees: anótalos y créale a R6 una rama con un `git stash` nombrado `t6-pendiente`. No borres el stash.
- Crea `tanda-7` desde `dev`, anota la línea base de la suite y haz el primer commit `docs(tanda7)` con esta instrucción, la de la spec del asistente y el prompt.

**K1. Compilación 1: base estable** (sesión principal, en cuanto termine A0).
1. Desde `dev` con la suite en verde, etiqueta `inst-2026-10-22-a`.
2. Determina qué `.spec` son los de producción (`Autoclave.spec` y los que lance según el informe de la tanda 2, el LEEME o la hoja de banco) y compílalos con `pyinstaller --noconfirm <spec>` en un clon limpio de esa etiqueta, por ejemplo `git worktree add ../_build_a inst-2026-10-22-a`, para que no entren archivos sin commit.
3. Verifica la carpeta resultante. NO debe contener `installation_profile.json*`, `data/`, `*.db`, `.claude/`, logs ni fotos. SÍ debe contener los recursos (QML, i18n, ciclos de fábrica, imágenes, sonidos si aplica). Lista el tamaño y el árbol de primer nivel.
4. **Prueba de humo** sobre una COPIA de la carpeta, nunca sobre la que se entrega, sin tarjeta y sin abrir puertos COM reales (usa el modo simulado o sin tarjeta si existe):
   - el ejecutable arranca;
   - sin perfil, abre el asistente de instalación;
   - no cae con un traceback.

   Ciérralo y borra la copia. Si para esto hace falta abrir un puerto real, NO lo hagas: anótalo y limita la prueba a que el proceso arranque y muestre el asistente.
5. **Antes de entregar:** congela el entorno exacto con el que compilaste (`pip freeze`) en `entrega/2026-10-22_a/entorno_build.txt`.
6. **Entrega:**
   - `entrega/2026-10-22_a/` con la carpeta compilada, un `.zip` y el SHA-256 de ambos;
   - `LEEME_INSTALACION.md`, que escribe P1 (deja un borrador ya).

   `entrega/` NO se commitea; agrégalo a `.gitignore` si no está.
7. Informe `K1_compilacion_a.md`: comando, versión de PyInstaller y de Python, advertencias del build y resultado de la prueba de humo.

**L1. Lock de dependencias** (subagente, sin tocar código).
- Regenera `requirements.lock.txt` desde el entorno con el que compila K1. El archivo actual está en UTF-16; guárdalo en UTF-8 y avisa en el informe del cambio de codificación.
- Actualiza `docs/riesgos/lista_soup.md` con las versiones exactas, incluidos PySide6, FastAPI y PyInstaller.
- Informe `L1_lock_soup.md`.

**Después de K1, lanza EN PARALELO** L1, P1, M1, C2, M2, R6, Q1 y D2, cada uno en su worktree. La sesión principal integra en el orden de prioridad de la regla 9.

**P1. Preparación de la instalación de mañana** (subagente; revisión de punta a punta con el simulador, sin hardware).
- Recorre el flujo exacto de mañana y corrige lo que lo bloquee, con prueba:
  1. primer arranque sin perfil;
  2. asistente: código del día del generador y perfil;
  3. arranque con perfil;
  4. creación o ingreso del primer usuario técnico/ingeniero;
  5. Opciones › Entradas/Salidas: lecturas, modo prueba de cada salida y salida del modo prueba por todos los caminos;
  6. calibración de sensores de temperatura y de presión: dos puntos, captura y escritura manual, guardar, reiniciar y comprobar que se conserva;
  7. calibración de presión atmosférica (O2f);
  8. Información del sistema;
  9. apagado del equipo desde el software.
- Con la tarjeta desconectada debe mostrar "tarjeta desconectada", no paro ni datos inválidos (U4).
- Lo que no se pueda corregir sin riesgo va en el informe como "PROBLEMA CONOCIDO PARA MAÑANA", con un rodeo manual.
- Escribe `entrega/LEEME_INSTALACION.md` y la copia versionada en `docs/instalacion/LEEME_INSTALACION.md`, con la lista de comprobación para Cristian:
  - qué copiar y dónde;
  - cómo generar el código de activación del día con `tools/generador`;
  - datos que pide el asistente: serie, clase, puertas, cámara (litros y V/H), fuente de vapor (solo generador interno en este equipo), suministros (solo aire comprimido cableado) y sondas (cámara 1, cámara 2, referencia y drenaje);
  - primer usuario;
  - orden de verificación de E/S y de calibración;
  - qué hacer si el perfil queda mal (reinstalar el perfil);
  - cómo volver a la compilación A si la B falla.

  Lo que no puedas comprobar desde el código, márcalo "verificar en sitio".
- Informe `P1_preparacion_instalacion.md`.

**M1. Asistente con cálculo de modelo** (subagente). Implementa `planeacion_asistente_modelo.md` completo (§2 a §7):
- `installation/modelo.py`;
- campos del perfil;
- puente;
- paso "Cámara" en `Instalacion.qml`;
- retiro de mesa del asistente;
- i18n es/en;
- Información del sistema;
- ticket a 18 caracteres;
- riesgo HAZ-INS-02 en `docs/riesgos/`.

Pruebas de §6 y capturas 1200×1920 de cada paso del asistente en `docs/informes/tanda7/capturas/`. Informe `M1_asistente_modelo.md`.

**C2. Correo a direcciones escritas a mano** (subagente).
- Reproduce el fallo con un SMTP falso local (por ejemplo `aiosmtpd` o un stub en las pruebas, sin red real). Revisa `ui_qml/exportacion/correo.py`, `config_correo.py`, `ui_qml/bridge/acciones_ciclos.py` y las vistas PySide (`views/ciclos.py`, `_email_dialog.py`).
- **Corrección:**
  - la dirección escrita a mano se valida (formato) y se envía, sola o junto con las guardadas, según lo que eligió el usuario;
  - el resultado que ve el usuario sale de lo que el relay ACEPTÓ por destinatario. Si se rechaza alguna dirección, el mensaje lo dice con esa dirección. Nunca muestres "enviado" si no hubo aceptación;
  - escribir una dirección a mano NO la agrega a los destinatarios guardados: eso sigue siendo de admin e ingeniero;
  - el envío queda en la bitácora con las direcciones y el resultado, sin la contraseña.
- Pruebas: guardadas, manual, mixtas, dirección inválida, rechazo parcial del relay y relay caído.
- Informe `C2_correo_manual.md`.

**M2. Mantenimiento E1** (subagente). Ejecuta la §10 de `docs/mis_plans/planeacion_mantenimiento.md` (MNT-01, 02, 03 y 05, con sus pruebas), con estos cambios:
- el commit está AUTORIZADO, sin esperar confirmación;
- la frase "no toques `state_machine.py`" sigue vigente: si hace falta tocarlo, va como PREGUNTA PARA CRISTIAN.

El formulario del preventivo NO entra. Informe `M2_mantenimiento_e1.md`.

**R6. Remanente de la tanda 6** (uno o varios subagentes en paralelo, según lo que A0 encontró sin hacer).
- Pueden quedar pendientes O2e (si no se commiteó), la unión de `tanda-6-o2fgh`, O2h, I4 QML y H1, según `instruccion_claude_code_tanda_6.md`.
- Usa el stash `t6-pendiente` si existe, revisando que la suite pase.
- Lo de la tanda 6 que requiera `docs/mockups/tanda6/APROBADO.md` sigue esa regla.
- Informes en `docs/informes/tanda7/R6_<id>.md`.

**Q1. Respuestas a las preguntas abiertas** ★ (subagente; los tres revisores).
- Implementa la decisión 1.3 completa, cada punto en su propio commit con pruebas: R1-P1 a P5, T2-a, T2-b y T2-c.
- Repite con la planta simulada las celdas afectadas de `docs/informes/tanda6/T2_matriz_actualizada.md` en los 4 programas.
- Actualiza el fichero de riesgos y agrega casos a la hoja de banco para R1-P2, R1-P3, T2-a y T2-c.
- Informe `Q1_preguntas_abiertas.md`.
- Si a las 10:30 Q1 no tiene a los revisores sin Altos/Críticos, NO se une a `dev` y queda en su rama: los ciclos empiezan el lunes.

**K2. Compilación 2: con lo de esta noche** (sesión principal; debe estar lista a las 13:45).
- Solo si `dev` tiene unido algo nuevo desde K1 y la suite está en verde: etiqueta `inst-2026-10-22-b` y repite K1, pasos 2 a 6, en `entrega/2026-10-22_b/`.
- Prueba de humo adicional: el asistente muestra solo Piso y Piso laboratorio, y el paso Cámara (si M1 entró).
- En `entrega/LEEME_INSTALACION.md` agrega una tabla A frente a B: qué tiene cada compilación y cuál recomiendas instalar y por qué.
- Si no hay nada nuevo o la suite no está en verde, NO compiles y anota que se instala la A.

**D2. Depuración del repositorio** (subagente; trabaja desde el principio en paralelo, pero se une a `dev` SOLO después de K2).
- **a) Código muerto:**
  - Inventario de módulos, funciones, UI y recursos que nadie importa ni llama. Compruébalo con `grep` y con un análisis de imports desde los puntos de entrada reales de los `.spec` y del lanzador; puedes usar `vulture` en el entorno virtual.
  - Incluye la UI tkinter (`ui/`, `installation/wizard.py` y su `main.py`), las vistas PySide sin llamador, las pantallas QML de prueba no usadas, `generar_iconos_emoji.py`, `listar_puertos.py` y los `.bak`.
  - Por cada elemento: quién lo usaba, evidencia de que no se usa y decisión (eliminar, conservar o PREGUNTA).
  - Elimina solo lo que tenga evidencia clara y la suite en verde después de eliminarlo. Retira `wizard.py` (decisión del 19-oct).
  - NO toques nada de los `.spec`, las herramientas de `tools/` en uso (generador, estación, declarar), las pruebas del banco ni el firmware.
  - En la duda, se conserva y va como PREGUNTA.
- **b) Ramas y worktrees:**
  - tabla de TODAS las ramas locales y remotas con: último commit, si está contenida en `dev` (`git branch --merged dev`), commits propios, si existe en `origin` y recomendación;
  - quita los worktrees `prunable` y los de la tanda 6 ya unidos (`git worktree remove`; nunca `--force` si tienen cambios sin commit);
  - borra con `git branch -d` (nunca `-D`) solo las ramas locales ya contenidas en `dev`;
  - las ramas con commits propios sin unir (por ejemplo `alarmas-parte-a`, `feature/roles-sensor-temperatura`, `worktree-anuncios-voz` y `audit/62304-snapshot`) NO se unen ni se borran: se evalúan (qué contienen, si ya está reimplementado en `dev`, conflictos) y quedan como PREGUNTA con recomendación;
  - nunca borres ramas remotas.
- **c) Commits sin push:** lista lo que falta en `origin` (hoy `dev` lleva 24 commits sin subir y `tanda-5`/`tanda-6` no están en el remoto) e intenta el push de `dev`, de las ramas `tanda-*` y de las ramas con trabajo propio, como respaldo. Anota el resultado exacto.
- **d) PR:** el flujo del proyecto no usa PR (GitHub es solo respaldo). No crees ninguno. Lista los PR abiertos con `gh pr list` si `gh` está autenticado; si no, anótalo.
- Informe `D2_depuracion.md`.

**Z. Cierre (OBLIGATORIO).**
1. Suite completa en verde.
2. `tanda-7` unida a `dev` con `--no-ff` y comprobada con `git merge-base --is-ancestor`.
3. Push de `dev`, `tanda-7` y las etiquetas, con el resultado exacto anotado.
4. Índice, `estado.md` y `DECISIONES_PARA_REVISAR.md`: arriba, un resumen de 10 líneas; las "PREGUNTA PARA CRISTIAN" en sección aparte; "PROBLEMAS CONOCIDOS PARA MAÑANA"; lo que quedó sin hacer y en qué rama está; y los recordatorios de la decisión 1.5.
5. Primera línea del índice: **qué carpeta de `entrega/` instalar**.
6. Al final, en `estado.md`, escribe la fila exactamente así: `| Z | Hecha | ... |`. El lanzador busca ese patrón para saber que la tanda terminó; si no lo encuentra, te relanza.
7. Limpia los worktrees de la tanda 7 ya unidos (`git worktree remove`) y deja los no unidos. Nada a `main`.
