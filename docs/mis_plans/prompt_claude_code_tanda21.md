# Prompt para Claude Code — tanda 21: fin de ciclo, puerta sin actuador y textos (sin supervisión)

Lo envía `powershell -ExecutionPolicy Bypass -File tools\tandas\lanzar_prompt.ps1 -Nombre tanda21` y lo reenvía si la sesión se corta.

---

Eres Claude Code en el repositorio del Software de Autoclave (Especifika). Cristian NO está presente: trabaja de forma autónoma, sin detenerte a preguntar. Todo en español (código, comentarios, commits, informe). Código Clase C (NTC-IEC 62304): velocidad sin sacrificar seguridad.

## Reglas

1. Si existe `docs/informes/tanda21/estado.md` con pasos hechos, REANUDA desde el primero pendiente (si una P quedó a medias, revisa su worktree/rama `tanda-21-<p>` antes de relanzarla). Si no existe, créalo y empieza por A0.
2. Lee COMPLETA la spec `docs/mis_plans/planeacion_fin_de_ciclo.md` (FC-01 a FC-13) y mira los mockups `docs/diseno/mockups/fin_de_ciclo/*.png`. La spec manda; ante ambigüedad, lo más seguro y reversible, marcado «DECISIÓN SIN CONFIRMAR» en el informe.
3. Rama `tanda-21` creada desde `dev`. Nunca `main`, `--force`, `git add -A`, `git push` ni `git branch -D`. No toques módulos reales, red real, registro de Windows, `.ps1`, el Setup ni la herramienta de táctiles. No leas el archivo de secretos.
4. **Subagentes: 4 a la vez como norma, 5 como máximo absoluto.** Ningún subagente corre la suite completa; solo sus pruebas. La sesión principal corre `pytest tests -n auto`. Las P trabajan en worktrees con la tabla de propiedad de abajo; nadie edita archivos de otra P.
5. Después de cada commit, actualiza `estado.md` (paso → Hecho/Pendiente, último commit).

## Etapas

**A0 (principal).** Crea la rama. Haz commit de la spec y los mockups (`docs/mis_plans/planeacion_fin_de_ciclo.md`, `docs/mis_plans/prompt_claude_code_tanda21.md`, `docs/diseno/mockups/fin_de_ciclo/`), con `git add` de esas rutas explícitas. Verifica y anota en `estado.md`:
- dónde se escribe `alarmas_historial` y si toda alarma en CICLO lleva `ciclo_id` (FC-03);
- cómo se determina hoy la fase en la que terminó el ciclo (FC-06);
- dónde se activa SEN-11 y se marca NO CONFORME (FC-08);
- de dónde sale `tiene_actuador` (FC-11).

**Ola 1 — en paralelo (4 P + 1 V como máximo):**
- **P1 backend** (`tanda-21-backend`), FC-06, FC-08, FC-12, FC-13 y la parte backend de FC-11.
  - Propiedad: `state_machine/`, `backend/`, `core/runtime/`, `services/`, `state_machine/alarms/catalogo.py`, ticket/PDF/correo, `docs/riesgos/registro_riesgos.md`, `CLAUDE.md`, i18n de alarmas y ticket.
  - Incluye CIC-19 y el retiro de NO CONFORME.
  - Con sus pruebas pytest.
- **P2 componentes de fin de ciclo** (`tanda-21-panel`): `Componentes/PanelFinCiclo.qml`, `Componentes/FilaAcordeon.qml`, `Componentes/ModalConfirmacion.qml` y los estados `fallida`/`interrumpida` de `Componentes/BarraFases.qml`.
  - Componentes autónomos con propiedades de entrada, sin conectarlos a las pantallas.
  - Pruebas QML offscreen del acordeón, del regreso automático con tiempo inyectable y del modal.
- **P3 indicador de puerta** (`tanda-21-puerta`): componente `Componentes/IndicadorPuerta.qml` con sus 3 estados, claves i18n `ciclo.puerta_*_estado` y sus pruebas (sin MouseArea, nunca envía comandos).
- **P4 textos** (`tanda-21-textos`), FC-10.
  - Propiedad: cualquier QML y clave i18n **excepto** `Pantallas/PantallaCicloEnCurso.qml`, `Pantallas/PantallaPreciclo.qml` y los archivos de P2/P3. Si algo de esas pantallas desborda, lo anota para la ola 2.
  - Incluye la prueba nueva de textos que caben.
- **V (solo lectura)**: revisa que P1 no rompa ticket, historial ni correo de ciclos viejos (NO CONFORME histórico) ni las rutas de `test_t15_rutas_equivalentes.py`.

Une cada P a `tanda-21` al terminar y verificar sus pruebas. Resuelve tú los conflictos.

**Ola 2 (principal, secuencial).** Conecta todo:
- `PantallaCicloEnCurso.qml`, `bridge/progreso_ciclo.py`, `domain/ciclo_en_curso.py` y el envío del token en cancelar (FC-01 a FC-07, FC-09, FC-12);
- `PantallaPreciclo.qml` + `UiBridge.puertaConActuador` (FC-09, FC-11);
- los desbordes que P4 dejó anotados.

Elimina `cargaNoEsteril`, la franja NO CONFORME y los `DialogoConfirmacion` de esas dos pantallas.

**G capturas.** Harness de prueba (como `Pruebas/PruebaCicloEnCurso.qml`, no forma parte de la navegación). Captura a 800 × 1280 cada estado de los mockups en `docs/informes/tanda21/capturas/`, con los mismos nombres.

**R revisión de seguridad (1 subagente, solo lectura)**, sobre el diff completo de `tanda-21` contra `dev`. Revisa en particular:
- FC-08: COMPLETADO solo en carga sólida; FALLO en líquidos; apertura automática bloqueada; P8 y C-03 intactos;
- que ningún estado inseguro se muestre como seguro (indicador de puerta, panel con resultado desconocido);
- que CONFIRMAR, cancelar y estado seguro sigan enviando lo mismo al backend.

Corrige lo que encuentre y anótalo.

**Suite.** `pytest tests -n auto` verde.

**K entrega (se compila sola, decisión de Cristian 28-oct).**
1. Une `tanda-21` a `dev` (merge sin fast-forward) y ejecuta `python tools/entrega/compilar_entrega.py --con-generador` desde `dev`.
2. Si la entrega se niega solo por archivos sin seguimiento que esta tanda no creó (p. ej. `.claude/`, `Claude outputs/`, `_suites_t11/`, `docs/informes/*/CERRADO.txt` viejos):
   - agrégalos uno por uno a `.git/info/exclude` (local, no versionado y reversible) y reintenta;
   - nunca los borres ni hagas commit de ellos;
   - lístalos en el informe con la instrucción para revertir.
3. Si se niega por cualquier otra causa, no la fuerces: `CERRADO.txt` con `BLOQUEADO:` y el motivo.

**Z cierre.**
1. Escribe `docs/informes/tanda21/R21_informe.md` con:
   - qué cambió por FC, archivos y pruebas;
   - decisiones sin confirmar;
   - usos de `DialogoConfirmacion` que quedan en otras pantallas;
   - textos corregidos por FC-10;
   - qué verificar en pantalla, comparando las capturas con los mockups;
   - la versión entregada.
2. Agrega la fila `| Z | Hecha | ... |` en `estado.md`.
3. Como último acto, escribe `docs/informes/tanda21/CERRADO.txt` con la fecha, el commit del merge, el resultado de la suite y la versión entregada o el motivo de no entrega.

Empieza por A0 (o reanuda).
