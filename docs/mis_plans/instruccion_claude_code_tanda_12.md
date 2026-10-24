# Instrucción maestra para Claude Code — Tanda 12 (sin supervisión)

> La lanza `tools/tandas/lanzar_tanda.ps1 -Tanda 12` (`claude -p`, se relanza si se corta): REANUDA siempre desde `docs/informes/tanda12/estado.md`.

**Contexto:** correcciones de proceso de CALENTAMIENTO y ESTERILIZACION pedidas por Cristian el 24-oct (C-01..C-13). Fuente de verdad: `docs/mis_plans/decisiones_tanda_12.md`, COMPLETO. Prioridad: **velocidad**. Los ciclos en el equipo de pruebas empiezan el lunes 26-oct.

**Modo:** **máximo 4 subagentes a la vez**, cada uno en su worktree y rama `tanda-12-<id>`, solo con sus pruebas (`PYTHONPATH=<worktree>/src`, comprobando `autoclave.__file__`). La suite completa solo la corre la sesión principal: una vez por cada unión, con `pytest -n auto` (si algo falla, repite en serie solo lo que falló). **NO termines el turno con subagentes activos.** Un solo revisor `safety-reviewer` en toda la tanda (etapa V12).

## 0. Reglas
1. **Rama y archivos:** rama `tanda-12` desde `dev`; subramas `tanda-12-<id>`. Estado en `docs/informes/tanda12/estado.md`. Informes en `docs/informes/tanda12/<id>_<nombre>.md`. Decisiones sin confirmar en `docs/informes/tanda12/DECISIONES_PARA_REVISAR.md`. Índice en `docs/informes/informe_tanda_<fecha>_t12.md`.
2. **Precondición (A0):** `docs/informes/tanda11/estado.md` tiene `| Z | Hecha |` y `dev` contiene `tanda-11`. Si no, escribe "Esperando el cierre de la tanda 11" en `tanda12/estado.md` y termina.
3. **Git:** nunca `main`, `--force`, `git add -A` ni `git push --delete`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/` ni `entrega/`. No toques `stash@{0}`. Une a `dev` con `--no-ff` y la suite en verde. Une las subramas **de una en una**; en conflictos de `i18n/es.json`/`en.json` conserva las claves de ambas.
4. **Prohibido:** hardware o puertos COM reales, cargar firmware, EJECUTAR `.ps1` o el Setup, instalar software del sistema. **Autorizado:** PyInstaller en un clon limpio de la etiqueta e `ISCC.exe` (solo compilar).
5. **Ante ambigüedad:** lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". Fuera de lo que dicen las decisiones, la lógica de ciclo, estado seguro o puertas no se cambia: va como "PREGUNTA PARA CRISTIAN".
6. **Propiedad de archivos (evita choques):** cada archivo de código lo toca una sola etapa, según la tabla de la sección 1. Única excepción: `states/ciclo.py`, que comparten J12 y E12 en funciones distintas (ver tabla); ninguno toca la función del otro y se une J12 antes que E12. Si una etapa necesita algo de un archivo ajeno, lo anota en su informe y la sesión principal lo resuelve al unir.
7. **`CLAUDE.md`** no lo tocan los subagentes: lo actualiza la sesión principal en Z (secciones de CALENTAMIENTO, ESTERILIZACION, convención de debounce por tiempo y chaqueta).
8. **Prioridad:** A0 → (J12, P12, E12, L12 en paralelo) → uniones J12 → P12 → E12 → L12 → V12 → K12 → Z. Si el límite de uso amenaza, V12, K12 y Z van antes que lo no empezado; Z se hace SIEMPRE.

## 1. Etapas

| Etapa | Tareas | Archivos propios |
|---|---|---|
| A0 | `t_saturacion_c` | `core/runtime/steam.py` y su prueba |
| J12 | C-04, C-05 (incl. C-05.9), valores JSON de C-07 y C-13, aviso de migración correctiva | `states/ciclo.py` (solo `_mantener_chaqueta` y su registro de consigna), `core/managers/catalogo_parametros.py`, `core/managers/cycle_manager.py` (`migrar_parametros`), `cycles/factory/*.json`, `cycles/user/*.json`, `docs/informes/limites_catalogo.md` |
| P12 | C-01, C-02, C-09, C-13.7b en la ventana | `cycle_phases/calentamiento.py` |
| E12 | C-03, C-07 (código), C-08, C-10, C-13 (incl. 7b) | `cycle_phases/esterilizacion.py`, `states/ciclo.py` (solo §4 vigilancia SENSOR_AUSENTE, bandera NO CONFORME y `_mantener_apertura_automatica`), `alarms/catalogo.py`, `i18n/es.json`/`en.json`, `core/runtime/motivos_fase.py`, formateador del ticket y `core/runtime/progreso_ciclo.py` si C-13.7 lo exige |
| L12 | C-11, C-12 [SPEC], casos de banco | `docs/mis_plans/planeacion_liquidos_dos_lazos.md`, `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` |

**A0.** Comprueba la precondición, crea `tanda-12` desde `dev`, lanza la línea base de la suite (en segundo plano, no la esperes para lanzar los subagentes) y:
- agrega `t_saturacion_c(p_kpa)` a `core/runtime/steam.py` según las reglas generales de las decisiones, con prueba de ida y vuelta (`t_saturacion_c(p_saturacion_kpa(T)) ≈ T` en 100–145 °C, tolerancia 1e-6) y de error con `p<=0`;
- escribe `tanda12/brief_subagentes.md` adaptando `docs/informes/tanda11/brief_subagentes.md` (rama `tanda-12`, ids de la tabla, regla 6 de propiedad de archivos, sin capturas);
- commit `docs(tanda12)` con esta instrucción, `decisiones_tanda_12.md`, el prompt y el brief, y commit `feat(tanda12-a0)` con `steam.py`. Los subagentes parten de ese commit.

**J12. Parámetros, validación y chaqueta** (subagente). C-04 y C-05 completos; además, en los 8 JSON: `brecha_segura_temperatura` = 1.0 (C-07.1) y la clave nueva `esterilizacion.timeout_excursion_referencia` = 5 (min, int, rango 1–30, C-13.4); `globals.delta_temp_chaqueta` y `globals.margen_flujo_chaqueta` (C-05.3). Las claves nuevas se agregan también a `migrar_parametros` con su defecto y al catálogo de límites. Si existe una prueba que exija etiqueta i18n por parámetro, agrega las etiquetas (es/en). Pruebas:
- `bowe_dick` de usuario con 9; `presion_add_*` = 31 rechazado; programa cargado con 99 migra a 9 con advertencia;
- techo `Psat(T)+presion_add >= 385` rechazado al guardar, para calentamiento y para esterilización, con sólido y con líquido; entre 350 y 385 se guarda con la advertencia no bloqueante; el B&D original (134.5 °C + 99 = 405.7) queda rechazado sin la migración;
- consigna de chaqueta: 134/9 → 326.3 ± 0.2 kPa; 121/11 → 230.3 ± 0.2; ON bajo `consigna-10`, OFF sobre `consigna+10`, sin cambio dentro; programa con consigna+10 >= 385 rechazado; con consigna+10 entre 350 y 385 se guarda con la advertencia no bloqueante de válvula abierta;
- se conservan: secado excluido, enfriamiento 4/5, sin dato → OFF, SUM-06; PREPARADO sigue usando `presion_chaqueta`;
- C-05.9: `presion_chaqueta + rango_presion_chaqueta >= 385` rechazado; 350/25 (usuario 134 y B&D) se guarda con advertencia y sin migrar;
- migración correctiva (C-04.4): fila de auditoría de parámetros con valor anterior y nuevo, y aviso no bloqueante visible en la bandeja de Preciclo y en la campana (prueba del backend que expone avisos + prueba de que el modelo de la campana lo lista); textos es/en;
- los 8 JSON cargan sin errores y ningún programa de fábrica queda rechazado (T10).

**P12. CALENTAMIENTO** (subagente). C-01, C-02 (solo sólidos) y C-09 en `calentamiento.py`, usando `t_saturacion_c` de A0. Actualiza el encabezado del módulo. Pruebas (una por punto, con fase simulada como en las pruebas existentes de calentamiento):
- C-01: entrada con `P = Psat(T_obj) - 1.9` y `T = T_obj` sí entra; con `-2.1` no; techo en `Psat(T_obj) + presion_add` (no 2×); con aire (P = Psat + 30, T = T_obj) el duty va a 0 por techo y no entra a sostener;
- C-02: banda con `|Tsat(P)-T| = 1.2 K` reinicia la ventana y arma el timeout de recuperación; con 0.8 K completa; con `tipo_carga = liquido` la coherencia no se exige;
- C-09: con `T_obj = 121` el corte de calidad empieza en 118.0 °C (no en 117.37); con 134, en 131.0;
- `duty_calidad_vapor` usa `Psat(T) - 2` sin `presion_add`;
- C-13.7b: una Referencia en `None` no bloquea la ventana de sostenimiento (las que leen sí deben estar en consigna).

**E12. ESTERILIZACION** (subagente, la más larga: arranca primero). C-03 (solo sólidos), C-07.2, C-08, C-10 y C-13 en `esterilizacion.py`. Lee los parámetros nuevos con su defecto en código (`timeout_excursion_referencia` 5 min) porque los JSON los pone J12. Alarmas nuevas: siguientes códigos CIC libres, mecanismo de CIC-11, textos es/en sin anglicismos; claves de ticket nuevas en i18n. Actualiza el encabezado del módulo. Pruebas (todas con reloj monotonic simulado):
- C-03: `dT = +2.5 K` durante 4.9 s no falla, 5.0 s falla con la alarma de aire; `-2.5 K` 5 s falla con la de sobrecalentado/sonda; una lectura dentro reinicia el conteo; con líquido no aplica;
- C-07: cada una de las 4 fallas requiere 5 s continuos (no 3 lecturas);
- C-08: con `T` oscilando entre `T_est+1.0` y `T_est+1.2` no hay conmutación repetida RECUPERACION↔PWM; en RECUPERACION con `P >= P_control_max` el vapor queda OFF;
- C-10: lo de C-10.1 sobre `CicloState` (un tick con el Principal en `None` termina en FALLO SEN-02 sin avanzar la exposición) y lo de C-10.2 sobre la fase (60 s sin datos corren el fin 60 s);
- C-13: excursión de una Referencia > 5 s detiene el conteo; al volver reinicia desde cero; F0 no se reinicia; sin retorno en `timeout_excursion_referencia` → FALLO con la alarma nueva; excursión < 5 s no detiene; el ticket lista sensor, duración y mínimo; el tiempo restante de la UI refleja el reinicio; Principal fuera de banda sigue fallando;
- C-13.7b: Referencia sin lectura → el ciclo continúa, alarma no bloqueante con el sensor, ticket y registro con "NO CONFORME: punto de referencia sin verificar" (es/en) aunque vuelva a leer, sin apertura automática; Principal sin lectura → FALLO SEN-02 igual que hoy; presión sin lectura igual que hoy. Actualiza las pruebas existentes que exigían FALLO con Referencia caída y lístalas en el informe.

**L12. Especificación de líquidos y casos de banco** (subagente, corto, solo documentos). `planeacion_liquidos_dos_lazos.md` con C-11 (incluida la sonda en el vapor para C-02/C-03) y C-12 según las decisiones, en el formato de los otros `planeacion_*.md`: objetivo, comportamiento actual con referencia a código (LIQ-01), diseño propuesto, parámetros nuevos con defecto y rango, interlocks, modos de falla, pruebas de aceptación, preguntas abiertas numeradas. Sin código. Además agrega a `hoja_pruebas_banco_equipo_pruebas.md` una sección "Tanda 12" con lo que Cristian debe observar el lunes: consigna de chaqueta calculada vs presión real, entrada a ESTABLE_PREESTERILIZACION con presión de saturación sin aire, ausencia de conmutación rápida en esterilización, Bowie & Dick con `presion_add` 9, cómo provocar/observar una excursión de Referencia si hay Referencia asignada, el aviso de migración en Preciclo/campana tras instalar la H (B&D 99 → 9) y el ticket NO CONFORME desconectando una Referencia.

**V12. Revisión de seguridad ★** (un solo revisor `safety-reviewer`, tras unir J12, P12 y E12). Alcance: `git diff dev...tanda-12` de código (no docs). Foco: que ninguna ruta cuente exposición sin datos o con una sonda fuera de banda, que los nuevos FALLO apaguen salidas y registren alarma, techo de presión en todos los tramos, consigna de chaqueta dentro de los límites, migración de programas, y que Referencia sin lectura nunca libere un ciclo sin la marca NO CONFORME ni con apertura automática. Corrige los bloqueantes en `tanda-12` (con prueba) y anota el resto en el informe V12.

**K12. Compilación H** (sesión principal). Mismos pasos y verificaciones que K11: verificador neutro y prueba de humo; ensayo G → H sobre una copia con el perfil y la BD de la G (comprobar que los programas de usuario cargan, que `bowe_dick` migra 99 → 9, que la chaqueta 350/25 se conserva, y que aparecen la auditoría y el aviso); Setup compilado y no ejecutado; SHA-256; `usb/` con exactamente lo que va a la USB.

**Z. Cierre (OBLIGATORIO).**
- `CLAUDE.md` actualizado (regla 7).
- Suite en verde y unión a `dev` comprobada.
- Push de `dev`, `tanda-12` y la etiqueta.
- Índice con el resumen por C-xx, las DECISIONES SIN CONFIRMAR, las PREGUNTAS y los pendientes registrados PRG-01 (validar roles contra sondas cableadas) y DEU-01 (límites de presión desde el perfil/Parámetros del equipo) y lo que quedó sin hacer.
- Primera línea del índice: si hay compilación H y si se recomienda instalarla antes del lunes.
- Fila `| Z | Hecha |` en `estado.md`.
