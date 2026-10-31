# J12 — Parámetros, validación y chaqueta (tanda 12)

Rama `tanda-12-j12` (desde `tanda-12`, c462114). Fuente: `docs/mis_plans/decisiones_tanda_12.md` (C-04, C-05, C-07.1, C-13.4).

## Qué se hizo, por punto

### C-04 (presion_add y techo de cámara)
- **C-04.1** `cycles/user/bowe_dick.json`: `presion_add_calentamiento` 99 → 9.
- **C-04.2** `catalogo_parametros.py`: `presion_add_calentamiento` y `presion_add_esterilizacion` con rango de catálogo 0–30 (`PRESION_ADD_MAX`). El `max` 100 de los JSON no se cambió: el rango efectivo (intersección) ya es 0–30.
- **C-04.3** reglas nuevas en `errores_coherencia` (las usan `set_param` al guardar y `errores_programa` al cargar), para todo tipo de carga. Techo = Psat(T) + presion_add de calentamiento y de esterilización:
  - techo `>= 385` → rechazo, código `LIMITE_PRESION_CAMARA`, con el máximo admisible de presion_add en el mensaje y en `valor` de la respuesta 422;
  - techo `> 350` → se guarda con advertencia no bloqueante (`aviso_techo_sobre_suministro`, texto es/en en `opciones.*`), devuelta por PATCH en `advertencias` y registrada en el log al iniciar el ciclo.
- **C-04.4** migración correctiva (`migrar_parametros(parameters, correcciones)` en `cycle_manager.py`): un `presion_add_*` > 30 baja a 9 al cargar. Cada corrección queda en `Cycle.migraciones_correctivas` y:
  - **aviso SIS-06** (AVISO, no bloquea, un origen por programa y parámetro; `state_machine/alarms/catalogo.py`, textos es/en en `alarmas.SIS-06`): se activa en `BackendContext.cargar_configuracion` (`_avisar_migraciones_correctivas`). Aparece en la bandeja de Preciclo y en la campana porque ambas listan el mismo modelo de alarmas activas (`raiz.alarmas`);
  - **auditoría de parámetros**: al abrir la base (`abrir_base_datos` → `auditar_migraciones_correctivas`) se escribe una fila `param_ciclo_cambio` por corrección: entidad `<programa>/<fase>/<parámetro>`, valor anterior y nuevo, usuario `sistema`, detalle con `origen: "migración tanda 12"`, `automatico: true`, `causa: "migracion_correctiva"`;
  - registrada la bitácora, el JSON del programa de usuario se reescribe con el valor migrado (atómico, versión anterior en `.json.bak`). Ver DSC-1.
  - Un programa que tras migrar sigue violando C-04.3/C-05 queda **dañado** por el camino actual, sin romper la carga de los demás (probado).
- **C-04.5** ningún programa de fábrica queda rechazado (T10 en verde; prueba propia sobre la carga real).

### C-05 (chaqueta acoplada al programa)
- **C-05.1/2** `catalogo_parametros.consigna_chaqueta(t_est, presion_add_est, delta, margen)` = max(Psat(T_est + delta), Psat(T_est) + presion_add_est + margen). 134/9 → 326.26 kPa; 121/11 → 230.27 kPa.
- **C-05.3** `globals.delta_temp_chaqueta` (1.5 °C, diferencia, 0–5) y `globals.margen_flujo_chaqueta` (15 kPa, diferencia, 0–40) en los 8 JSON, en el catálogo y en `migrar_parametros` (programa sin las claves → defecto, sin aviso).
- **C-05.4** `CicloState._mantener_chaqueta`: ON si `P < consigna − 10`, OFF si `P > consigna + 10`, sin cambio dentro (`_BANDA_CHAQUETA_KPA = catalogo_parametros.BANDA_CHAQUETA_KPA = 10`). La consigna se calcula en cada tick desde el programa en curso.
- **C-05.5** rechazo si `consigna + 10 >= 385` (código `LIMITE_CONSIGNA_CHAQUETA`, consigna en el mensaje y en `valor`); `consigna + 10 > 350` → advertencia `aviso_chaqueta_abierta`.
- **C-05.7** se conservan secado excluido, enfriamiento 4/5 (OFF), sin dato → OFF, SUM-06 (probados).
- **C-05.8** PREPARACION/PREPARADO siguen con `presion_chaqueta`/`rango_presion_chaqueta` (probado con `preparado_state`). Al iniciar el ciclo (`CicloState.reset` → `_registrar_consigna_chaqueta`) se registran en el log la consigna (y su Tsat) y todas las advertencias del programa.
- **C-05.9** `presion_chaqueta + rango_presion_chaqueta >= 385` → rechazo (`LIMITE_PRESION_CHAQUETA`); `> 350` → advertencia. Fábrica 300 + 50 = 350: sin advertencia. Usuario 134 y B&D 350 + 25 = 375: válidos, con advertencia, sin migrar.
- Descripciones de `presion_chaqueta` y `rango_presion_chaqueta` (es/en) actualizadas: ya no rigen durante el ciclo.

### C-07.1 y C-13.4 (valores JSON)
- `brecha_segura_temperatura` 0.3 → 1.0 en los 8 JSON, **en un commit aparte** (c059dd3). Ver "NECESITA DE OTRA ETAPA".
- `esterilizacion.timeout_excursion_referencia` = 5 (min, int, 1–30) en los 8 JSON, catálogo y migración.

### Pantalla (Opciones › Parámetros del ciclo)
- `parametros_ciclo_controller.py` y `sesion_backend.py`: los 3 códigos nuevos con su texto (`opciones.err_limite_*`, con `{valor}`), y las advertencias de la respuesta PATCH se muestran con el aviso existente (`opciones.aviso_techo_sobre_suministro`, `opciones.aviso_chaqueta_abierta`).
- PATCH devuelve `advertencias` solo si dependen del parámetro editado (o de su vinculado de temperatura). Ver DSC-4.
- Etiquetas y descripciones es/en de los 3 parámetros nuevos (`parametros.*`, `parametros_desc.*`).

`docs/informes/limites_catalogo.md` actualizado (constantes con el cálculo de 40 psig, reglas y filas nuevas).

## Commits
- `8354776` feat(tanda12-j12): presion_add max 30, límites físicos, consigna de chaqueta y migración correctiva
- `c059dd3` feat(tanda12-j12): brecha_segura_temperatura 1.0 en los 8 programas (C-07.1)
- (este informe) docs(tanda12-j12)

## Pruebas
`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a75eb91611b96fbb1\src\autoclave\__init__.py` (PYTHONPATH del worktree).

Nuevas:
- `tests/test_t12_c04_presion_add.py` — B&D 9; 31 rechazado / 30 aceptado; 99 migra a 9 (las dos secciones y el B&D de usuario cargado desde archivo); B&D original sin migrar rechazado (405.7 kPa); programa inválido tras migrar queda dañado sin romper la carga; techo ≥ 385 rechazado para calentamiento y esterilización con sólido y con líquido; techo entre 350 y 385 guardado con advertencia; PATCH: 422 con el máximo, 200 con `advertencias`; textos del controlador.
- `tests/test_t12_c05_chaqueta.py` — consigna 134/9 = 326.3 ± 0.2 y 121/11 = 230.3 ± 0.2; ON bajo consigna−10, OFF sobre consigna+10, sin cambio dentro; secado, enfriamiento 4/5, sin dato, SUM-06; programa sin datos → control anterior; log al iniciar; PREPARADO con `presion_chaqueta`; consigna+10 ≥ 385 rechazado (140 °C); 139 °C (384.95) con advertencia; consigna+10 entre 350 y 385 con advertencia; C-05.9 rechazo y 350/25 con advertencia sin migrar.
- `tests/test_t12_c04_migracion_aviso.py` — SIS-06 AVISO no bloqueante; aviso activo al cargar; fila de auditoría con anterior/nuevo y origen; archivo reescrito y `.bak`; sin auditoría el archivo no se toca; `/status` (`_alarma_dto`) con textos es/en; `AlarmListModel` (bandeja de Preciclo y campana) lo lista.
- `tests/test_t12_c07_c13_json.py` — los 8 JSON con las claves nuevas, sin errores, sin nada que migrar; carga real sin dañados ni migraciones; catálogo de `timeout_excursion_referencia`; etiquetas i18n; `brecha_segura_temperatura` = 1.0.

Resultado:
- Con el commit 8354776 (brecha aún en 0.3): pruebas nuevas + las 232 que importan los módulos tocados → **4804 passed, 10 skipped** (`pytest -n auto`, 438 s).
- Con c059dd3 (brecha 1.0): `test_t12_c07_c13_json.py` + `test_t10_endurecimiento.py` → 65 passed. **Los ensayos de simulador fallan sin E12** (abajo).

Pruebas existentes modificadas:
- `tests/test_alarmas_catalogo.py`: ejemplo de valores para `SIS-06` en `_EJEMPLOS` (la prueba exige un ejemplo por código del catálogo).

## NECESITA DE OTRA ETAPA (E12)
- **brecha_segura_temperatura 1.0 sin C-08.3 rompe 53 ensayos de simulador** (`test_t11_programas_integracion`, `test_t2/q1/s1/s2b/t8_s2a/e1_ensayo_simulador`, `test_r8_planta_simulada`, `test_b9_buzzer_paro`): en RECUPERACION el vapor abre sin techo hasta T_est + 1 y la presión del simulador sube a 334 kPa → CIC-04 presión alta. Con brecha 0.3 pasan. Lo comprobé emulando a mano (sin commit, archivo restaurado) el techo de C-08.3 en `esterilizacion.py`: con él, los 156 ensayos pasan con brecha 1.0. Por eso c059dd3 va aparte: **unir J12 hasta 8354776, y c059dd3 después de E12** (o correr la suite tras unir las dos).
- Puntos de choque: `states/ciclo.py` (`_mantener_chaqueta`, dos métodos nuevos debajo, una línea en `reset()` tras `self._protocolo.reset()`, dos imports y la constante `_BANDA_CHAQUETA_KPA` junto a `_DEBOUNCE_LECTURAS_DRENAJE`); `alarms/catalogo.py` (`SIS_06`/`MIGRACION_CORRECTIVA` tras `IMPRESORA_DESCONECTADA` y su definición tras la de SIS-05); `i18n/es.json`/`en.json` (`alarmas.SIS-06` tras SIS-04, `opciones.*` tras `aviso_modo_solido`, `parametros.*` y `parametros_desc.*`).
- E12 debe leer `timeout_excursion_referencia` (ya está en los 8 JSON y en el catálogo).

## DECISIONES SIN CONFIRMAR
1. **DSC-1** Tras registrar la auditoría, el JSON del programa de usuario migrado se reescribe (con `.bak`), para que archivo, memoria y bitácora coincidan y la migración, la fila y el aviso no se repitan en cada arranque. Si la bitácora falla, el archivo no se toca y todo se repite en el siguiente arranque. Los programas de fábrica nunca se reescriben.
2. **DSC-2** Un programa sin `temperatura_esterilizacion` o `presion_add_esterilizacion` numéricos controla la chaqueta en CICLO como antes (`presion_chaqueta ± rango`), con aviso en el log. Con los 8 JSON nunca ocurre.
3. **DSC-3** La advertencia es estricta: `> 350`. Exactamente 350 (fábrica 300 + 50) no avisa.
4. **DSC-4** PATCH devuelve solo las advertencias que dependen del parámetro editado; editar otro parámetro de un programa 350/25 no repite el aviso de chaqueta. El log al iniciar el ciclo las registra todas.
5. **DSC-5** La fila de auditoría usa el evento existente `param_ciclo_cambio` (aparece en la bitácora y en "última modificación") con usuario `sistema`; el origen va en `detalle.origen`.
6. **DSC-6** SIS-06: un aviso por programa y parámetro; queda activo hasta reiniciar el software o reconocer una FALLA (despeje de todas). Con DSC-1, no reaparece en el siguiente arranque.
7. **DSC-7** Los defectos del hospital (`cycles/defecto`) también se migran en memoria (con log), pero sin auditoría ni aviso.

## PREGUNTAS PARA CRISTIAN
1. **brecha 1.0 + histéresis de salida 0.3 (C-08.2) contra el techo de control.** Para salir de RECUPERACION hace falta T ≥ T_est + 1.3, es decir P ≥ Psat(T_est + 1.3): +11.6 kPa a 134 °C y +11.8 kPa a 134.5 °C. Pero el techo es P_control_max = Psat(T_est) + `presion_add_esterilizacion`, que vale 9 en los de usuario y 11 en los de fábrica. Con vapor saturado puro, a 134/134.5 °C la fase se quedaría siempre en RECUPERACION, sostenida por el techo (todo/nada en P_control_max), y el PWM no actuaría nunca. A 121 °C no pasa: hacen falta +8.4 kPa, menos que 9 y que 11. ¿Lo acepta así o sube `presion_add_esterilizacion` a 12 o más en los programas de 134?
2. Los programas de usuario ya instalados en sitio conservan `brecha_segura_temperatura` 0.3: la migración solo agrega las claves que faltan y corrige presion_add > 30. ¿Hay que migrarla también a 1.0, o el Setup H reemplaza esos archivos?

## Pendientes
- DEU-01 (límites desde el perfil o Parámetros del equipo) sigue registrado como deuda.
- Sin prueba de arranque completa (`cargar_configuracion` + `abrir_base_datos` con la base real): las dos llamadas nuevas se probaron como métodos sueltos. K12 lo cubre en el ensayo G → H.
