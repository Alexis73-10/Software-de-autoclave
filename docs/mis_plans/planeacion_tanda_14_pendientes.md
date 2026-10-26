# Planeación — Tanda 14: pendientes de las tandas 12 y 13

Estado: **borrador para decisión de Cristian** (25-oct). Recoge las PREGUNTAS y pendientes de `docs/informes/tanda12/DECISIONES_PARA_REVISAR.md`, `tanda12/V12_revision_seguridad.md` y `tanda13/S13_saturacion_if97.md`. Base: compilación I (IAPWS-IF97). Todas las cifras de presión están calculadas con IF97, en kPa absolutos.

Cada punto trae el problema, la propuesta recomendada (**R**), las alternativas y la decisión que hace falta (**D-14.x**). Los marcados 🔬 conviene confirmarlos con los datos del banco del lunes 26-oct antes de lanzar la tanda.

---

## P1. A 134 °C no se puede salir de RECUPERACION (SAF-04) 🔬
**Problema.** Para salir a PWM_ACTIVO hace falta `T ≥ T_est + brecha_segura_temperatura + 0,3 K` (C-08). Con vapor saturado, la temperatura máxima que permite el techo `P_control_max = Psat(T_est) + presion_add_esterilizacion` es `Tsat(P_control_max)`. Si esa temperatura queda por debajo del umbral de salida, el control nunca pasa a PWM y se queda en todo o nada contra el techo.

| T_est | presion_add | Tsat(techo) | Salida con brecha 1,0 | Salida con brecha 0,3 |
|---|---|---|---|---|
| 121 | 11 | 122,67 | 122,3 ✔ (margen 0,37) | 121,6 ✔ |
| 134 | 9 | 135,00 | 135,3 ✘ | 134,6 ✔ |
| 134 | 15 | 135,65 | 135,3 ✔ (margen 0,35) | ✔ |
| 134,5 | 9 | 135,49 | 135,8 ✘ | 135,1 ✔ |

**R.**
1. **Regla de coherencia al guardar y cargar** en `catalogo_parametros.errores_coherencia`. Se rechaza el programa si `Tsat(Psat(T_est) + presion_add_esterilizacion) < T_est + brecha_segura_temperatura + 0,3 + margen`, con `margen = 0,3 K`. El mensaje da el `presion_add_esterilizacion` mínimo. Equivale a exigir `presion_add_esterilizacion ≥ Psat(T_est + brecha + 0,6) − Psat(T_est)`: 10,5 kPa a 121 °C y 14,5 kPa a 134 °C, con brecha 1,0.
2. **Programas de fábrica:** se sube `presion_add_esterilizacion` al mínimo que pide la regla, redondeado hacia arriba (121 °C sigue en 11; 134 °C pasa de 11 a 15). Se verifica que la consigna de chaqueta + 10 siga por debajo de 385: a 134 °C con 15 queda en 344,2 kPa, por debajo incluso del suministro (350).

**Alternativas.**
- (a) Bajar la histéresis de salida de 0,3 K a 0 en temperatura.
- (b) Bajar `brecha_segura_temperatura` a 0,5 K. El control apuntaría a T_est + 0,5, que sigue por encima de la incertidumbre de la PT100.
- (c) Dejarlo como está. No es inseguro, porque el techo se respeta, pero el control no modula.

**D-14.1:** ¿R, (a), (b) o (c)? Si R, ¿el margen de 0,3 K está bien? 🔬 En el banco, mira a qué temperatura real se estabiliza la cámara con la presión en el techo.

## P2. Programas de usuario con `brecha_segura_temperatura` 0,3
**Problema.** La actualización conserva los programas del sitio, que siguen en 0,3 K. Ese valor es menor que la incertidumbre de la PT100 (±0,4 K), que fue la razón de C-07.

**R.** Migrar 0,3 → 1,0 con la migración correctiva que ya existe (auditoría con valor anterior y nuevo, aviso SIS-06, `.bak`). Se hace solo junto con P1: si después de migrar el programa no cumple la regla de P1, se sube también `presion_add_esterilizacion` al mínimo, con la misma auditoría. Si con eso la chaqueta + 10 llega a 385, no se migra nada, se deja el programa como está y se avisa.

**Alternativa.** No migrar; el aviso SIS-06 recomienda revisar el valor.

**D-14.2:** ¿Se migra? ¿Se acepta que la migración pueda cambiar también `presion_add_esterilizacion`?

## P3. Referencia más fría que el Principal en la ventana de CALENTAMIENTO 🔬
**Problema.** Hoy la ventana exige `T_ref ≥ T_obj` para cada Referencia. En ESTERILIZACION, en cambio, la banda inferior de la Referencia es `T_est − brecha_error_temperatura`. Una Referencia 0,1–0,2 K más fría que el Principal hace fallar el ciclo con `cal_no_sostuvo`. El criterio de las dos fases es distinto.

**R.** Usar el mismo límite en las dos fases: en la ventana, `T_ref ≥ T_obj − brecha_error_temperatura` (de la sección `esterilizacion`). No se agrega un parámetro nuevo. Una tolerancia mayor solo en CALENTAMIENTO no sirve: el fallo se correría a ESTERILIZACION (excursión, después CIC-14).

**Nota física.** Si el Principal está en el punto frío, que una Referencia lea menos que él de forma sostenida indica un desfase de calibración o una sonda mal ubicada, no algo del control. El banco debe mostrar cuál es el caso.

**D-14.3:** ¿Se acepta igualar los límites? 🔬 ¿Cuál es la diferencia real entre Principal y Referencia en el equipo de pruebas, y está bien `brecha_error_temperatura` = 0,1?

## P4. NO CONFORME visible (SAF-02, P-V12-1)
**Problema.** Hoy la marca NO CONFORME solo va al ticket y al registro. La pantalla muestra COMPLETADO. Con la impresora desconectada, el operador libera la carga sin enterarse.

**R.**
1. `/status` y el historial exponen `no_conforme` y su motivo.
2. La pantalla final muestra una franja roja: «CICLO NO CONFORME — carga no liberable: punto de referencia sin verificar» (es/en).
3. Confirmar exige un **reconocimiento explícito** (un segundo botón «Reconozco que la carga no es liberable»). Se audita con el usuario.
4. El historial y el ticket llevan el encabezado «NO CONFORME». El resultado técnico sigue siendo COMPLETADO.

**Alternativa.** Un resultado nuevo, `NO_CONFORME`, distinto de COMPLETADO. Es más claro, pero toca estadísticas, filtros, correo y PDF.

**D-14.4:** ¿R o resultado nuevo? ¿El ticket dice «NO CONFORME» o «CARGA NO ESTÉRIL»?

## P5. Tope de reinicios de exposición sin F0
**Problema.** Las excursiones de Referencia repetidas pueden reiniciar la exposición sin límite.

**R.** Nuevo parámetro `max_reinicios_exposicion` en la sección `esterilizacion` (int, defecto 3, rango 0–10). La siguiente excursión confirmada después del tope da FALLO con un código CIC nuevo (es/en), venga o no de la misma Referencia. Con F0 activo se mantiene además el timeout 2× actual.

**D-14.5:** ¿Tope por cantidad (R) o por tiempo total de fase? ¿El defecto 3 está bien?

## P6. Debounce que no confirma con señal oscilante 🔬
**Problema.** «5 s continuos» se reinicia con cada lectura dentro de rango. Una señal que oscila alrededor del umbral (ruido de la PT100 frente a `brecha_error_temperatura` = 0,1 K) nunca confirma la falla.

**R.** Criterio **acumulado en ventana deslizante**: se confirma cuando el tiempo fuera de rango suma 5 s dentro de los últimos 10 s. Aplica a las 4 fallas de ESTERILIZACION, a C-03 (CIC-12/13) y a la confirmación de excursión de C-13. Una sola implementación compartida (`DebounceAcumulado` en `control_banda.py` o en un módulo nuevo), con `time.monotonic()`.

**D-14.6:** ¿Se acepta 5 s de 10? 🔬 Del registro del banco: ¿cuánto oscilan el Principal y la Referencia en la exposición (pico a pico)?

## P7. Lecturas fuera del rango físico (S13 §4.2)
**Problema.** Una temperatura fuera de 0–200 °C (sensor o tarjeta fuera de escala) hoy hace lanzar `t_saturacion_c` en cada tick. El estado termina seguro, por el apagado tras 3 excepciones y el watchdog, pero el motivo queda solo en el log.

**R.** Filtro de plausibilidad en el punto único donde se publican las lecturas vivas (`estado.sensores_temp` / `sensores_pres`):
- temperatura fuera de 0–200 °C → `None`;
- presión fuera de −10–450 kPa (el rango de `CALIBRACION_PLAUSIBLE`) → `None`.

A partir de ahí actúan las rutas que ya existen: Principal → SEN-02 FALLO; Referencia → SEN-11 y NO CONFORME; presión → FALLO de presión sin lectura. Se agrega un log con el valor crudo, una vez por episodio.

**D-14.7:** ¿Se aceptan esos rangos?

## P8. Defensa en profundidad (sin decisión de proceso)
- **SAF-05:** al pasar de una lectura válida a una sin lectura, se descuenta de la exposición también el intervalo desde la última lectura válida, no solo desde el primer tick sin dato.
- **SAF-09:** en `_mantener_chaqueta`, `vapor_chaqueta` se apaga siempre que `P ≥ PRESION_ALIVIO_CHAQUETA − 10`, sin importar la consigna. Además, `_registrar_consigna_chaqueta()` va dentro de `try`.
- **P-V12 1 / P-E12 4:** una Referencia con excursión confirmada que pierde la lectura mantiene la exposición detenida y CIC-14 sigue corriendo. **R: confirmar**, porque es el comportamiento conservador.

**D-14.8:** ¿Se confirma el último punto?

## P9. VER-01: la versión no llega al `.exe` (62304 §5.8.4)
**Problema.** Todo el código lee la versión con `importlib.metadata.version("autoclave")`: `ui_qml/bridge/info_equipo.py`, `backend/rutas/sistema.py`, `backend/rutas/respaldo.py`, `services/domain/logging/cycle_logger.py` y `devices/printer/arranque_equipo.py`. Esa información solo existe con el paquete instalado con pip. Ningún `.spec` usa `copy_metadata`, y en `entrega/2026-10-24_i/Autoclave/_internal` no hay `autoclave-*.dist-info`. En los equipos, «Información del sistema» muestra la versión vacía, y respaldos y registros de ciclo guardan **"0"** (`validar_para_equipo` compara respaldos con ese valor). Hay tres fuentes que no coinciden: `pyproject.toml` (0.5.0), el `/DAppVer=1.0.0-i` que se pasa a mano a ISCC y la etiqueta `inst-…`.

**R.**
1. Fuente única `src/autoclave/_version.py` con `__version__ = "1.0.0"`; `pyproject.toml` la lee con `dynamic = ["version"]`.
2. Función única `version_sw()` (en `_version.py`) para los 5 llamadores; desaparecen los `importlib.metadata.version("autoclave")`.
3. El `/DAppVer` del `.iss` sale de `_version.py` (el paso de compilación lo lee; ya no se escribe a mano).
4. Test que falla si `pyproject`, `_version.py` y el `.iss` difieren, y si queda algún `importlib.metadata.version("autoclave")` en `src/`.
5. Compatibilidad: un respaldo hecho con versión "0" se sigue aceptando en `validar_para_equipo` (se trata como «anterior a 1.0.0»).
6. La prueba de humo de K verifica que «Información del sistema» muestra la versión, y el ticket también.
7. Tag `v1.0.0` sobre el commit de cierre; la compilación J sale **de ese tag**, no de una rama.

**D-14.9:** ¿La compilación J es la 1.0.0 (tag `v1.0.0`), o se usa un sufijo de prueba (`1.0.0-j`) hasta la validación en campo? ¿Se acepta el criterio de compatibilidad del punto 5?

## P10. Limpieza de git (pendiente de las tandas 13 y 15)
**Situación verificada el 25-oct.** 38 worktrees en `.claude/worktrees/`; ramas locales: 44 `worktree-agent-*` y 39 `tanda-*`; 12 remotas `origin/tanda-*`. Las ramas `feature/roles-sensor-temperatura` (16 commits), `worktree-anuncios-voz` (17) e `instalador-setup` (1) están entre 368 y 657 commits detrás de `dev`. `main` tiene **3 commits que no están en `dev`** (24 al 29 de septiembre): «Mejoras en máquina de estados de AdvancedDoor y correcciones menores» (3d55cc1), audios mp3 de la puerta (d5e602f) y reorganización del diseño UI v2 (5fe9e1c).

**R.**
1. Solo al final de la tanda, **después** de que terminen los agentes de la tanda 14 (no tocar sus worktrees activos): `git worktree remove` de los worktrees viejos de `.claude/worktrees/` sin cambios sin commit (los que tengan cambios se listan y no se tocan), `git worktree prune`, y `git branch -d` de las `tanda-*` y `worktree-agent-*` unidas a `dev`. Nunca `-D`: las que git se niegue a borrar se listan con su número de commits sin unir.
2. Las tres ramas viejas: etiqueta `archivo/<rama>` en su último commit y borrado de la rama local con `-d` o, si git se niega, se deja y se lista.
3. Los 3 commits de `main`: informe, sin integrar, de si su contenido ya está en `dev` (por archivo y por función; en especial AdvancedDoor). No se toca `main`.
4. Remotas `origin/tanda-*`: solo listado; las borra Cristian.
5. `.gitignore`: `/data/` completo (hoy solo algunos archivos).

**D-14.10:** ¿Se aceptan las etiquetas `archivo/*` para las tres ramas viejas? ¿Se borran también las remotas `origin/tanda-*` (lo haría Cristian)?

---

## Fuera de la tanda 14 (tanda 16)
- **C-11 / C-12, implementación de líquidos:** la especificación está en `planeacion_liquidos_dos_lazos.md`. Faltan las 11 preguntas de su §10, sobre todo el umbral de purga en Bogotá, qué salida drena el fondo y dónde está físicamente `temp_ref`.
- **PRG-01:** validar que cada rol de sensor corresponda a una sonda cableada en el perfil.
- **DEU-01:** límites de presión desde el perfil de instalación o Parámetros del equipo. Toca la UI de Parámetros del equipo.

## Reparto propuesto de la tanda 14 (4 agentes, una sola revisión de seguridad)
| Etapa | Puntos | Archivos propios |
|---|---|---|
| E14 | P5, P6, SAF-05, P8 (excursión) | `esterilizacion.py`, módulo del debounce, `alarms/catalogo.py`, i18n |
| J14 | P1, P2, SAF-09 | `catalogo_parametros.py`, `cycle_manager.py`, `cycles/*.json`, `ciclo.py` (`_mantener_chaqueta`) |
| C14 | P3, P7 | `calentamiento.py`, el publicador de lecturas vivas (converters/estado) |
| U14 | P4 | `ciclo.py` (bandera NO CONFORME y `/status`), `server.py`, QML de pantalla final e historial, ticket/PDF |

| G14 (sesión principal) | P9 | `_version.py` (nuevo), `pyproject.toml`, los 5 llamadores, `packaging/*.spec`, `.iss` y su paso de compilación |

P10 lo hace la sesión principal en el cierre, cuando ya no hay agentes activos.

**Precondición:** `tanda-15` unida a `dev` (la reorganización cambió `backend/server.py` por `backend/rutas/*` y los `.spec` a `packaging/`). U14 trabaja sobre `backend/rutas/` en lugar de `server.py`.

Después vienen la revisión V14 ★, la compilación J (desde el tag de P9) y el cierre Z. Duración estimada: 1 h 30 a 2 h, parecida a la tanda 12.

## Orden sugerido
1. Cristian responde D-14.4, D-14.5, D-14.7, D-14.8, D-14.9 y D-14.10, que no dependen del banco.
2. Banco del lunes: datos para D-14.1, D-14.3 y D-14.6. Hay que registrar el Principal, la Referencia, la presión de cámara y la de chaqueta durante la exposición.
3. Con las respuestas, el asistente arma `decisiones_tanda_14.md`, la instrucción y el prompt.
