# L12 — Especificación de líquidos (C-11, C-12) y casos de banco de la tanda 12

**Rama:** `tanda-12-l12` (desde `tanda-12`, c462114). **Solo documentos, sin código.** 24-oct-2026, sin supervisión.

## Qué se hizo

### C-11 y C-12 → `docs/mis_plans/planeacion_liquidos_dos_lazos.md` (nuevo)
Formato de los otros `planeacion_*.md`: objetivo y alcance, comportamiento actual con referencias a código, diseño, parámetros con defecto y rango, interlocks, modos de falla, pruebas de aceptación (unitarias y de banco), dependencias y 11 preguntas abiertas numeradas.
- **LIQ-01 documentado en el código:** el vapor de cámara se controla con `_temp_principal()` (`base_fase.py:69`), que en líquidos es la sonda del líquido: `calentamiento.py:257/308-327/395/401` y `esterilizacion.py:208-221` (banda de PWM sobre `Psat(T_líquido)`) y `:330-337` (RECUPERACION con vapor ON continuo). El retardo térmico de la carga queda dentro del lazo: oscila y termina en FALLO por presión alta (`esterilizacion.py:302-308`).
- **C-11:** lazo de presión hacia `Psat(T_est + delta_temp_lazo_presion)` (defecto 1.0 K) con banda fija −2/+1 kPa y techo `P_control_max`. La sonda del líquido solo decide el inicio y la pérdida de la exposición, el F0 y las fallas de temperatura. Hay un rol de sensor nuevo, **`vapor`** (recomendado: `temp_ref`), solo para líquidos y como máximo uno, que hace C-02 y C-03 con las mismas constantes y alarmas (CIC-12/CIC-13). Si la sonda de vapor no está asignada, no está declarada o no lee al iniciar, se bloquea el inicio. Si deja de leer en CALENTAMIENTO, la ventana no completa y se dispara el timeout. Si deja de leer en ESTERILIZACION, el ciclo sigue con la alarma SEN-12 (propuesta) y la marca NO CONFORME "saturación del vapor sin verificar".
- **C-12:** se describen la Opción A (fase PURGA solo para líquidos) y la Opción B (prevacío con interlock de temperatura del líquido y de `Psat(T_líquido)`), cada una con sus riesgos. **Recomendación: A**, con fin de purga por coherencia `|Tsat(P) − T_vapor| ≤ 1 K` más un piso `temp_fin_purga`. B queda opcional y apagada por defecto.
- **Hallazgo nuevo de L12 (altitud):** en Bogotá (74,6 kPa) el vapor a presión atmosférica está a `Tsat = 91,4 °C`. Con el drenaje abierto, el umbral de 95 °C de C-12 solo se alcanza si la cámara sube ~10,7 kPa sobre la atmósfera (`Psat(95) = 85,3 kPa`). Por eso se propone el criterio por coherencia y una advertencia al guardar (pregunta 1 del documento).
- El hecho de origen (226 kPa → ~106 °C) se comprobó con `steam.py`: `Psat(106) = 125,4` más el aire de Bogotá calentado (~96,5) ≈ 222 kPa. Conclusión: C-11 no debe habilitarse sin C-12.

### Casos de banco → `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`
Bloque nuevo **"T12. Tanda 12: calentamiento, esterilización y chaqueta (lunes 26-oct)"**, con 7 filas nuevas en el Resumen y el formato de las secciones existentes:
- A-T12-01: migración del Bowie & Dick de 99 a 9, aviso SIS-06 en Preciclo y en la campana, fila de auditoría, chaqueta 350/25 conservada, validación 31 / 137 °C / 140 °C.
- E-T12-01: consigna de chaqueta 326,3 kPa y banda 316,3–336,3 (C-05).
- E-T12-02: entrada con `P ≥ 300,3` y coherencia de 1 K (C-01/C-02).
- E-T12-03: sin conmutación rápida RECUPERACION↔PWM (C-07/C-08).
- E-T12-04: Bowie & Dick con 9 (techo 315,7).
- F-T12-01: excursión de Referencia con simulador de PT100, CIC-14 (C-13).
- F-T12-02: Referencia desconectada → SEN-11 y NO CONFORME, sin apertura automática (C-13.7b).

Los valores se calcularon con `steam.py` del worktree.

## Commits
- `docs(tanda12-l12): especificación de líquidos en dos lazos, casos de banco T12 e informe` (único commit de la etapa).

## Pruebas
No hay pruebas de código (etapa solo de documentos). Los valores numéricos se calcularon con `PYTHONPATH=<worktree>/src`. Se comprobó que `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a31a938724291c22a\src\autoclave\__init__.py`. Funciones usadas: `p_saturacion_kpa` y `t_saturacion_c`.

## Pruebas existentes modificadas
Ninguna.

## DECISIONES SIN CONFIRMAR
1. Rol de sensor nuevo `vapor` (y no la reutilización de `referencia`). Solo para líquidos, máximo uno; `temp_ref` por defecto en el programa de fábrica de Líquidos.
2. Programa de líquidos sin sonda de vapor utilizable → inicio bloqueado.
3. Sonda de vapor sin lectura en la exposición → el ciclo continúa con SEN-12 (código nuevo propuesto, no preasignado) y NO CONFORME. En CALENTAMIENTO → la ventana no completa y vence el timeout.
4. Pérdida de exposición del líquido → FALLO, como en sólidos.
5. El equilibrio del líquido lo cubre `timeout_calentamiento`, sin timeout nuevo.
6. Fin de purga por coherencia más un piso de 95 °C, con advertencia por altitud. `valvula_purga` = `ambas` por defecto.
7. Opción B: si el líquido está tibio, el prevacío termina sin más pulsos de vacío (no falla).
8. Hoja de banco editada directamente en el `.md` (como hizo N11 en la tanda 11). **No** se tocaron `hoja_pruebas_banco/pruebas.py` ni el `.html`: quedan desactualizados respecto al `.md`. Si se regenera con `generar.py`, se pierden los bloques N11 y T12.

## PREGUNTAS PARA CRISTIAN
1. **(Afecta a E12/V12 y al banco del lunes.) Techo frente a histéresis de C-08 en los programas de 134 °C.** Con `brecha_segura_temperatura` 1,0 y `_HIST_RECUP_TEMP_K` 0,3, la salida a PWM exige `T ≥ 135,3 °C`. Pero el techo `P_control_max` corresponde a `Tsat(302,3 + 9) = 135,0 °C` (y a 135,23 °C con 11; en Bowie & Dick 134,5/9, 135,5 frente a 135,8 exigidos). Con vapor saturado, la fase **nunca sale de RECUPERACION** y la válvula de vapor se regula en el techo, sin histéresis allí: puede abrir y cerrar a ritmo de tick (0,5 s). En 121 °C sí funciona (salida en 122,3 °C, techo en 122,39 °C). Se dejó como punto de observación en E-T12-03 (contar los cambios de Vapor cámara por minuto). ¿Se acepta, o se agrega histéresis al techo / se baja la brecha a 134 °C?
2. Las 11 preguntas numeradas de la §10 de `planeacion_liquidos_dos_lazos.md`. Las más urgentes son la 1 (umbral de purga en Bogotá), la 5 (qué salida drena el fondo de la cámara) y la 6 (dónde están físicamente `temp_ref` y la sonda flexible en el equipo de pruebas).

## NECESITA DE OTRA ETAPA
- Nada de código. Para la sesión principal y V12: ver la pregunta 1 (techo de C-08 a 134 °C).
- J12 y E12: los textos de A-T12-01, F-T12-01 y F-T12-02 suponen lo que dicen las decisiones (SIS-06 en Preciclo y en la campana, auditoría con origen "migración tanda 12", CIC-14, SEN-11, marca NO CONFORME). Si su implementación cambia algún nombre o comportamiento (por ejemplo, si el aviso persiste o no tras reiniciar), conviene ajustar la hoja al unir.

## Pendientes
- Implementar C-11/C-12 en una tanda futura, cuando Cristian responda las preguntas.
- Regenerar `pruebas.py` y el `.html` de la hoja de banco desde el `.md` (deuda heredada de la tanda 11).
