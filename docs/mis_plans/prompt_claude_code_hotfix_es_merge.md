# Hotfix ES: unión con la tanda 28 y compilación (6-nov-2026)

Responde e informa SOLO en español. Trabajo sin supervisión. Lleva `docs/informes/hotfix_es_merge/estado.md` (paso → Hecho/Pendiente, último commit) al día tras cada commit; al reanudar, sigue desde el primer paso pendiente. Máximo 2 subagentes a la vez. El equipo de pruebas está fuera de servicio: prioridad velocidad y cambio mínimo. Ningún paso de este prompt lo hace otra sesión: tú haces la unión, la suite, la revisión, el merge a `dev`, la compilación y el cierre.

## Contexto
- `hotfix-estado-seguro` (d520f7ab) retira el protocolo automático de estado seguro: ver `docs/mis_plans/prompt_claude_code_hotfix_estado_seguro.md`, `docs/informes/hotfix_estado_seguro/R_informe.md` y su `CERRADO.txt` (BLOQUEADO por esta unión). Revisión de seguridad hecha y corregida (cf7fba48, 2849c6e8, f12f74ce, 91b52ae1).
- `dev` (fa18324a) trae la tanda 28b (merge 7e454049): A9 arranque sin protocolo con marca persistente, A10 el estado seguro dice qué le falta, A13 secado tras fallo. Tocan el mismo código: 18 archivos en conflicto.
- `AJUSTES.md` tiene cambios sin commitear que no son tuyos: no los descartes ni los incluyas en tus commits. Si algún paso exige árbol limpio, `git stash push AJUSTES.md` antes y `git stash pop` después.

## Decisiones de Cristian (6-nov) para resolver los conflictos
- D1. Manda el hotfix: `ProtocoloEstadoSeguro` no actúa después de CICLO ni en el arranque. Ninguna resolución puede reintroducirlo, ni parcialmente.
- D2. A9: la marca persistente se retira si solo sirve para decidir si arranca el protocolo. Si además la usa el cierre del ciclo interrumpido (bitácora, ticket), se conserva solo para eso.
- D3. A10 y el punto 5 del hotfix hacen lo mismo (motivo con valor y límite en NO ABRIR y en el bloqueo de inicio): queda UN solo mecanismo, el más completo de los dos, sin claves i18n duplicadas. Lo de A10 que describe el protocolo activo (p. ej. la pausa por modo prueba) se retira.
- D4. A13 se conserva: secado tras fallo con carga sólida y secado disponible, con M3 (verifica el vacío), M4 (NO ABRIR con `secando_vapor_residual` mientras corre) y la falla cerrada de M5. Corre dentro de CICLO, en el `ProtocoloFallo` de `CicloState`, antes de salir de CICLO. Si hoy alguna parte la dispara `ProtocoloEstadoSeguro` o el arranque, se mueve a `ProtocoloFallo` sin cambiar su lógica ni los parámetros `secado_tras_fallo_s` y `secado_tras_fallo_vacio_s`.
- D5. A13-M5 en el arranque (secado del ciclo interrumpido al encender) se retira: sin protocolo no hay quien lo ejecute. El ciclo interrumpido se cierra y registra como interrumpido y PREPARACION nivela la cámara; NO ABRIR sigue por presión y temperatura. Anótalo como residual en HAZ-ES-RET-01.
- D6. Lección del 6-nov: el secado tras fallo NUNCA puede dejar la cámara no segura indefinidamente. Al salir de CICLO `estado.secado_tras_fallo` queda en un estado final (hecho, omitido, sin_vacio, sin_ruptura) y nunca en pendiente; tras un reinicio vale None. Prueba que lo demuestre.

## Pasos
1. Rama `hotfix-es-merge` desde `dev` (fa18324a), en un worktree aparte; `git merge hotfix-estado-seguro`. Resuelve los 18 conflictos con D1–D6. En `registro_riesgos.md` y `CLAUDE.md` conserva las dos historias y deja coherentes las secciones de A9/A10/A13 con el retiro del protocolo.
2. Pruebas: las de A9/A10 que prueban el protocolo se retiran o ajustan; las de A13 se conservan, ajustadas a que el secado corra en CICLO. Lista de pruebas retiradas y ajustadas en `docs/informes/hotfix_es_merge/R_informe.md`. Si la roja preexistente `test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite` queda resuelta por D3, déjala en verde; si no, documéntala.
3. Búsqueda de restos: `git grep` de `ProtocoloEstadoSeguro`, `estado_seguro.iniciar`, `_TICKS_SEGUROS`, `estado_seguro_causa_` y la marca de A9 en `src/` y `tests/`; cada aparición que quede, justificada en el informe.
4. Suite completa (`pytest tests -n auto`) en verde, salvo la roja preexistente si sigue documentada.
5. 1 subagente revisor de seguridad, solo sobre el diff de la unión contra las dos ramas: protocolo reintroducido, A13 que bloquee o deje la bomba o válvulas encendidas, salidas tras soltar el paro sin confirmar, FALLA/PREPARACION con presión congelada. Corrige ALTA y MEDIA y repite la suite.
6. Merge de `hotfix-es-merge` a `dev` (sin reescribir historia) y push de `dev` si el remoto está configurado como en las tandas anteriores.
7. Desde `dev` limpio: `python tools/entrega/compilar_entrega.py` (debe salir la 1.0.0-alpha.18). Si se detiene (p. ej. LIC-01), anota el motivo y el comando exacto para Cristian.
8. Último acto: `docs/informes/hotfix_es_merge/CERRADO.txt` (fecha, commit del merge, suite, versión compilada y ruta del instalador, o motivo de no compilar). Si te bloqueas por algo que necesite a Cristian, escríbelo igual con `BLOQUEADO:` en la primera línea.
