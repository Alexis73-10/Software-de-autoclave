# Informe — Tanda 4 (20-oct-2026)

Objetivo: dejar el software listo para instalar el equipo de pruebas el lunes 26-oct-2026. Rama `tanda-4` desde `dev` (9fb8d4e). Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_4.md`. Decisiones a revisar: `docs/informes/tanda4/DECISIONES_PARA_REVISAR.md` (leer primero). Estado: `docs/informes/tanda4/estado.md`.

## Etapas
| Etapa | Qué | Commit | Informe |
|---|---|---|---|
| B1 | Secado PySide guarda por `PATCH /cycle/parameter`; barrido de rutas PySide (solo había una errónea) | 2163466 | `B1_secado_pyside.md` |
| B2 | `Autoclave.spec` ya no excluye `scipy`; pruebas de `excludes`; comando y 5 comprobaciones del .exe | a806594 | `B2_spec_scipy.md` |
| B3 | Mantenimiento 365 días / 1000 ciclos, migración, reloj adelantado/atrasado, pantalla de intervalos (revisada: sin Críticos/Altos) | d5ef909 | `B3_mantenimiento.md` |
| B4 | "Parámetros del sistema" → "Parámetros del equipo" (texto visible y docs) | 64d1ada | `B4_renombre.md` |
| B5 | Aviso no bloqueante SIS-05 de impresora desconectada al arrancar; bandera `habilitada` | 9a3facc | `B5_aviso_impresora.md` |
| B6 | Selector de ciclo en Preciclo (3 más usados primero), capturas | edda249 | `B6_selector_ciclo.md` + 2 PNG |
| B7 | Caducidad de tokens por inactividad en el backend (5 min) + renovación desde la UI | b682c6c | `B7_caducidad_tokens.md` |
| B8 | Salida forzada del modo prueba huérfano (ingeniero) | b682c6c | `B8_salida_forzada_modo_prueba.md` |
| B9a | Llamadas síncronas del contador en el tick: medidas (~2 ms), sin cambio | e071aed | `B9a_llamadas_sincronas_tick.md` |
| B9b | Permisos de puertas por rol: DIFERIDO con `xfail` | 6ead212 | `B9b_puertas_permisos_diferido.md` |
| B9c | Revisión de traducciones es/en y altas sin revisar | 954646f | `B9c_revision_traducciones.md` |
| H1 | Hoja de banco: A-05, D-10…D-14 nuevas y D-06 actualizada (41 pruebas, ids estables) | fc547c0 | `hoja_pruebas_banco_equipo_pruebas.{md,html}` |

## Pruebas
Línea base 3793 pasan / 1 omitida. Al cierre: **3938 pasan, 1 omitida, 3 xfailed** sobre `tanda-4` limpia (worktree sin los cambios ajenos) y **4008 pasan, 1 omitida, 3 xfailed** sobre el árbol de trabajo (con los cambios sin commit de la otra sesión). Los 3 `xfail` son B9b (contrato diferido, a propósito).

## Revisiones de seguridad/temporización
Por orden de Cristian durante la tanda, NO se ejecutaron `safety-reviewer` ni `timing-auditor` salvo el de B3 (sin Críticos ni Altos; hallazgos Medios/Bajos en `B3_mantenimiento.md`). **Quedan sin revisión de agentes: B5, B7, B8 y B9a.** Cada informe lista las comprobaciones propias hechas.

## Entrega
- `tanda-4` se une a `dev` con `--no-ff` solo con la suite verde; luego `git push origin dev tanda-4` (si falla, lo hace Cristian a mano). **`main` no se tocó.** (Resultado real del push en `estado.md`.)
- El árbol de trabajo conserva cambios SIN commit de otra sesión (teclados QML, Entradas/Salidas, calibración, parte de `server.py` y `sesion_backend.py`, `es.json`/`en.json`). No se incluyeron en ningún commit de esta tanda.

## Pasos manuales previos al lunes 26-oct
1. **Compilar el .exe** (`pyinstaller --noconfirm Autoclave.spec`) y hacer las 5 comprobaciones de `B2_spec_scipy.md` (hoja A-05): engrane abre ajustes, calibración, Entradas/Salidas, login técnico, cierre limpio.
2. **Reinstalar el perfil del equipo de pruebas con el asistente QML** (fuente de vapor = generador interno; A-01/A-04).
3. **Cargar el firmware 1.0.0** a la tarjeta (A-02/A-03).
4. **Probar la app de registro F1 desde el teléfono** (Wi-Fi del banco, firewall, 2 usuarios, foto, firma, corte de Wi-Fi).
5. **Probar el generador compilado** (`tools/generador`).
6. Probar con el equipo real las funciones nuevas de esta tanda: D-10 (selector), D-11 (impresora desconectada), D-12 (caducidad de sesión), D-13 (salida forzada, por API), D-14 (nombre), D-06 (mantenimiento 365/1000 y pantalla de intervalos).
7. Decidir los pendientes: botón de salida forzada del modo prueba (B8), control de `impresora.habilitada` en "Parámetros del equipo" y en el asistente (B5), revisión con agentes de B5/B7/B8/B9a, revisión lingüística del inglés nuevo (`revision_traducciones.md`).
