# E-0 — Commits previos en `dev` (tanda 2026-10-14)

Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_noche.md` §2 E-0, decisiones 1.4 y 1.5.

## 1. Pruebas

| Momento | Resultado |
|---|---|
| Línea base (árbol de F1 + E6 sin commitear, más el bloque `alarmas` ya agregado) | **2808 passed**, 6 warnings (coincide con el informe F1) |
| Al cerrar E-0 | ver `estado.md` (fila E-0) |

Nota: una primera corrida de la línea base se cruzó con la edición del catálogo y falló en `test_i18n_linea_base`; se descartó y se repitió.

## 2. Revisores sobre E6 (a)

Se ejecutaron `safety-reviewer` y `timing-auditor` sobre los cambios E6 sin commitear y luego una segunda pasada de verificación sobre las correcciones. Ambos confirman resueltos los Crítico/Alto.

### Corregidos (Crítico / Alto)

| Id | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| SAF-01 | Crítico | Expansor de entradas caído en ciclo: tras reconocer la falla el equipo seguía operando con DI congeladas (puertas, paro) | `SerialLink.expansor_fuera_de_linea()`; en `ControlLoop._tick()`, fuera de CICLO, si es True se repite el handshake. Falla en el paso 6 mientras `pcf_ok≠3F` → FALLA bloqueante y sin conexión |
| TMG-01 / SAF-04 | Alto | `marcar_tick_control()` al inicio del tick: un lazo que lanza excepción en cada tick seguía alimentando el HB y el watchdog del firmware nunca disparaba | Se marca en `run()` solo si `_tick()` termina sin excepción |
| TMG-02 | Alto | Handshake invalidado con la tarjeta SINCRONIZADA y salidas en ON: si fallaba en VER/HB, esas líneas alimentaban el watchdog y las salidas quedaban encendidas sin límite | ALL_OFF de mejor esfuerzo al iniciar cada handshake |
| TMG-03 / SAF-10 | Alto | Carrera: el reenvío por discrepancia del hilo lector podía salir después de una orden nueva del lazo e invertir la salida | `_cmd_lock` (RLock): registro + envío atómicos en `set_output`/`all_off`; el reenvío relee `_comandado` bajo el lock |
| SAF-02 | Alto | `_hs_st` crecía sin límite en operación (~172 800 entradas/día) | El `finally` de `_ejecutar_handshake` limpia `_hs_esperando_estado`, `_hs_st`, `_hs_do` |
| SAF-03 / TMG-07 | Alto | Falla de tarjeta en CICLO con el resultado ya pendiente (espera de confirmación, protocolo de fallo): se descartaba en silencio | `abortar_por_falla_io` devuelve bool; si no actúa, se reporta como FALLA bloqueante |

Corregidos además (Medio): TMG-05 (`write_timeout=0.5` en el puerto), TMG-06 (cada evento de tarjeta en su propio `try`).

Regresión detectada en la verificación (Medio) y corregida: con SAF-03, una discrepancia en CICLO con resultado pendiente pedía handshake; su ALL_OFF cerraba el venteo del protocolo de fallo. Ahora en CICLO nunca se pide handshake (decisión 8 de E6); al salir de CICLO lo hace el chequeo SAF-01.

Pruebas nuevas: `test_e6_control_loop_tarjeta.py` (+8) y `test_e6_enlace_handshake.py` (+4). Ajustadas por cambio de comportamiento: orden de comandos del handshake (ALL_OFF previo) y conteo de ALL_OFF (4 = 1 previo + 3 intentos). Las pruebas se escribieron junto con la corrección; no se registró la corrida en rojo de cada una (excepción a la regla de pruebas primero, por ser correcciones de revisión).

### Pendientes (Medio / Bajo), sin corregir

- SAF-05: corte y reapertura del puerto en < 5 s durante un ciclo sin FALLO; un `BOOT` fuera de handshake se descarta.
- SAF-06: `conectada` despeja por id; una EMERGENCIA de ciclo con el mismo id que una FALLA fuera de ciclo podría despejarse. **Se resuelve en T1** (el catálogo nuevo distingue instancia y origen).
- SAF-07: tras WD/BOOT en ciclo con un expansor de entradas caído, el re-handshake no se completa y el protocolo de fallo no puede ventear. Requiere definir un handshake degradado (decisión de seguridad: PENDIENTE para Cristian).
- SAF-08: el firmware no suscribe `loop()` al TWDT; un cuelgue del firmware deja los PCF con su último estado. Revisar al compilar (fuera de alcance).
- SAF-09: AI/DI congeladas por el firmware (FW-01) durante el debounce; `ai_inv` no se usa en el PC.
- SAF-11, SAF-12 / TMG-04: aborto fuera de `_sm_lock`; `al_conectar` escribe SQLite desde el hilo de supervisión.
- TMG-08 (cola de eventos sin límite), TMG-09 (peor caso real ~6,6 s del watchdog, para la prueba de banco 11), TMG-10 (banderas sin lock), TMG-11 (`stop()` apaga antes de detener el lazo; previo a E6).
- Residual de la verificación: `set_output` revisa `_handshake_ok` fuera de `_cmd_lock` y el handshake envía sus ALL_OFF sin él; el paso 6 lo detecta (lado seguro).
- Efecto de SAF-04: una excepción persistente en un paso no crítico (`cycle_logger`, buzzer) ahora detiene el HB → watchdog → FALLO en ciclo. Fallo hacia el lado seguro con pérdida de disponibilidad.

## 3. Decisiones 1.4 y 1.5 (b)

- P1: bloque `alarmas.<ID>.{titulo, accion}` en `es.json` y `en.json` con los 9 ids de la tarjeta (textos tomados del catálogo §2.2). Aún no los lee ninguna pantalla: la UI sigue mostrando `Alarm.description`. Se conectan en T1.
- P2, P3, P5: ya implementados así en E6; sin cambios.
- P4: aceptado; T5 (E3) lo contempla.
- 1.5: la clave desconocida ya mostraba la clave (R-05 de F1). Se agregaron los textos de las 6 etapas de arranque (`arranque.verificando_instalacion`, `liberando_procesos`, `cargando_configuracion`, `verificando_calibracion`, `conectando_modulos_es`, `preparando_interfaz`) en es y en. `sistema.modo_prueba` se conecta en T7 (E5).
- Traducciones nuevas registradas en `docs/mis_plans/revision_traducciones.md` como "sin revisar".
- `test_i18n_linea_base.py`: la equivalencia con el `txRuta` viejo no resolvía un tercer nivel; se agregó la misma excepción que ya existía para `opciones.secciones`.

## 4. Commits (c)

Tres commits en `dev` (hash en `estado.md`):

1. **F1 i18n**: módulo `autoclave.i18n`, catálogos es/en (incluye el bloque `alarmas` y los textos de arranque), singleton QML, migración de QML y Python, archivos del asistente de instalación (`Instalacion.qml`, `PruebaInstalacion.qml`, `prueba_instalacion.py`, 6 componentes nuevos), `tools/claves_sin_uso_i18n.py` y sus pruebas.
2. **E6**: firmware V3 (sin compilar), enlace serial, ControlLoop, `abortar_por_falla_io`, emparejamiento (`board_id`, `tools/emparejar_tarjeta.py`), `/status.tarjeta`, Información del sistema y pruebas, con las correcciones de los revisores.
3. **docs**: planes, informes, catálogo de alarmas, mockups de instalación, estado de la tanda.

Fuera de los commits: `.claude/`, `docs/informes/analisis_sistema_alarmas.md`, el plan y la spec de `alarmas-parte-a` (llegan con la rama), `docs/catalogo_alarmas.2026-09-18.bak.md` y `src/autoclave/images/icono autoclave.jpg` (declarados no versionables en `informe_p1_commits.md`).

## 5. DECISIONES SIN CONFIRMAR

- **D-E0-1.** Archivos mezclados F1/E6 (`es.json` con las 4 claves `equipo.*` de E6 y `PanelEquipo.qml` con `valorClave`): van enteros en el commit F1. `valorClave` es opcional, así que el commit intermedio no rompe la vista. No se verificó la suite en el commit intermedio aislado; sí en el conjunto. Alternativa: separar por hunks.
- **D-E0-2.** ALL_OFF de mejor esfuerzo al inicio de *todo* handshake (no solo cuando se invalida uno completo). Con una tarjeta recién arrancada la deja SINCRONIZADA con todo apagado antes de VER; es inocuo. Alternativa: enviarlo solo si había handshake previo.
- **D-E0-3.** SAF-01 se resolvió solo en el PC. No se cambió el firmware (FW-01 "conservar el último valor válido" es decisión de spec). Alternativa recomendada por el revisor: forzar a inactivo los bits de un expansor caído en el firmware.
- **D-E0-4.** Textos en español de las 9 alarmas: derivados de la columna "Acción del operador" del catálogo, reescritos en segunda persona.

## 6. Comprobaciones manuales de Cristian

- Verificación visual de F1 (lista en `informe_f1_i18n.md`): queda pendiente; el commit se hizo por orden de la tanda.
- Banco (con la tarjeta, sin autoclave): las 13 del informe E6 §4, más:
  - Desconectar un expansor de entradas en reposo y luego reconectarlo: el equipo debe quedar sin conexión y con `TARJETA_EXPANSOR_FUERA_DE_LINEA` hasta reconectarlo.
  - Prueba 11 (lazo congelado): el apagado puede tardar hasta ~6,6 s, no 5 s (TMG-09).
