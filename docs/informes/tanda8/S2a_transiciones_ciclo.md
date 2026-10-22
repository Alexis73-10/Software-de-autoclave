# S2a ★ — Transiciones del ciclo (D8-2.6 a D8-2.10), tanda 8

Rama: `tanda-8-s2a` (worktree `.claude/worktrees/agent-a74be21cea62bc278`). Sin push.
Fuente: `docs/mis_plans/decisiones_tanda_8.md` §D8-2 (aceptadas 22-oct 10:38).
La sesión se cortó una vez por el límite de uso; se continuó desde el estado commiteado (D8-2.6 a D8-2.8) y el trabajo sin commit de D8-2.9.

## 1. Qué se hizo, por punto

### D8-2.6 — salir de FALLA con `solo_lenta` (commit 4a55f06)
Sin cambio de lógica: `ProtocoloEstadoSeguro.permite_salir_de_falla` ya valía con `solo_lenta` sin importar cómo se llegó (R1-P4). Se fijó con pruebas y se aclaró el docstring. NO ABRIR sigue hasta que `camara_segura` (con el Principal) lo permita.
Revisión: CIC-10 se volvía invisible al salir de FALLA (el reinicio resuelve todas las alarmas). Ahora se reactiva si el protocolo sigue bloqueado (`_cic10_activa`, SAF-03).

### D8-2.7 — desconexión breve y ventana tras reconectar pausan la exposición (commit 3e566fa)
`ControlLoop._marcar_ciclo_sin_datos()` llama a `CicloState.marcar_sin_datos_tarjeta()` en cada tick de CICLO sin enlace o sin la primera DI. La desconexión, la ventana y una tolerancia de DI a continuación son un solo tramo; al volver los datos, `pausar_exposicion` corre el fin de ESTERILIZACION y los segundos van al ticket. F0 no se acumula con `exposicion_en_pausa`. `tolerancia_di_activa` (R1-P5) no cambia.
Revisión (TMG-01, Alta): el tramo empezaba al detectarse la falta de datos, hasta ~2 s después de la última DI válida. Ahora empieza en la última DI válida (`estado.ultima_di_valida_mono`, retroceso máximo 2 s) y el F0 acreditado desde ese instante se descuenta (`ControlLoop._descontar_f0_tramo_sin_datos`). La tolerancia por DI vencida también cuenta desde ahí.

### D8-2.8 — tope de pausas (commit a81e0eb)
Parámetro del equipo `pausa_max_esterilizacion_s` (30 s, 5-120, grupo sistema). Si las pausas de una exposición lo superan: FALLO con CIC-11 "Comunicación inestable en esterilización" (catálogo es/en).
Revisión (SAF-05): con un enlace que va y viene sin llegar a COM-02, `run()` no corre y el tramo queda abierto para siempre. Ahora `marcar_sin_datos_tarjeta()` revisa lo acumulado más el tramo abierto y falla con CIC-11 sin esperar a `run()` (`_revisar_tope_pausa_abierta`).

### D8-2.9 — 3 tramas DI distintas (commit aecf36a)
`SerialLink` numera cada trama DI válida (`secuencia_ultima_di()`, bajo `data_lock`; no se reinicia en la vida del proceso). `ControlLoop._contar_enlace_ok()` solo cuenta una trama nueva para `enlace_confirmado_ok` (DESPEJAR de COM-02/03) y publica `estado.trama_di_nueva`, que `CicloState` usa para salir de la tolerancia por DI vencida. Una caída reinicia la cuenta; la trama vigente antes de la caída no cuenta como nueva.
Revisión: TMG-02 (caer el enlace reinicia las tramas contadas de la tolerancia), TMG-05 (tras un tick fallido la misma trama no cuenta como nueva).

### D8-2.10 — líquidos, modos 4/5, Principal perdido en el enfriamiento (commits 165e97e, cb592e1, b2db729, 2a6f51a)
**Revisión previa del código (lo que pidió la decisión):** la contrapresión del enfriamiento se mantiene hoy con `aire_comprimido_camara` reafirmado cada 3 s según `pres_camara` contra `presion_camara_enfriamiento`, más `agua_chaqueta` y pulsos de `descompresion_chaqueta`; en modo 5 además la lenta queda ABIERTA todo el enfriamiento. No está claro en el código qué estado de válvulas significa "sellada con la contrapresión" (en modo 5 el enfriamiento normal no está sellado; la decisión no dice si sigue el agua de chaqueta ni si se repone aire sin conocer la temperatura). Por eso, como manda la decisión: **espera sellada con TODAS las salidas del protocolo cerradas** (vapor de cámara y chaqueta, lenta, rápida, chaqueta, aire comprimido, agua de chaqueta, aire atmosférico) y PREGUNTA (abajo).

Implementación (`ProtocoloFallo`):
- Dos entradas: (a) el protocolo ya enfriaba con contrapresión por otra causa y el Principal se pierde (3 lecturas, R1-P4) → `pasar_a_solo_lenta` sella en vez de abrir la lenta; mientras corre el debounce, cada lectura inválida cierra todo (antes abría la lenta en el acto); (b) se pierde el Principal con la fase DESCOMPRESION enfriando (`DescompresionFase.en_enfriamiento_con_contrapresion`) → `CicloState` llama `ejecutar(solo_lenta=True, en_enfriamiento_contrapresion=True)`.
- Solo carga líquida (`globals.tipo_carga`) y modos 4/5; en (a) además la cámara presurizada al disparo (solo entonces hay contrapresión). Sólidos y otros modos: sin cambios (P-2).
- Sellada mientras alguna sonda válida (Referencia del programa, drenaje, o el Principal si vuelve a leer) esté sobre `temp_max_apertura` (el menor entre el global y el del programa). Con todas las Referencias válidas en o bajo ese valor, 3 lecturas → lenta (`motivo_venteo = "sondas_frias"`).
- Sin Referencia válida: espera `espera_sellado_sin_sonda_min` (parámetro del equipo nuevo, 30 min, 10-240, grupo sistema) → lenta (`"espera_sin_sonda"`). Se desarma solo con 3 lecturas calientes seguidas (TMG-03).
- Alivio por sobrepresión (SAF-01): con 3 lecturas sobre max(`presion_camara_enfriamiento`, P_sat(`temperatura_esterilizacion`)) + `rango_presion_ester`, la lenta abre como alivio; cierra con 3 lecturas bajo el tope menos 5 kPa; si se pierde la lectura con el alivio abierto, sigue abierto.
- `solo_lenta` queda True (enclavado): D8-2.6 permite salir de FALLA; NO ABRIR sigue (sin Principal, `camara_segura` no es segura). CIC-10 con el motivo "cámara sellada…". El estado seguro registra `estado_seguro_sellado` y `estado_seguro_venteo_tras_sellado`.

**Hallazgo del ensayo con la planta simulada (corregido en cb592e1):** el drenaje lo mantiene frío su agua de enfriamiento (`temp_segura_drenaje` 70 °C < `temp_max_apertura` 80 °C), y con la cámara sellada no pasa vapor por él. Con el texto literal de la decisión ("Referencia o drenaje"), en el programa Líquidos de fábrica (sin Referencia) la cámara se venteaba a los 3 ticks con la carga a 113 °C. DECISIÓN SIN CONFIRMAR: el drenaje caliente mantiene el sellado, pero el drenaje solo nunca autoriza el venteo; sin Referencia válida rige la espera sin sonda.

## 2. Ensayo con la planta simulada (4 programas de fábrica)
`tests/test_t8_s2a_ensayo_simulador.py` (modelo: Q1). Tabla en `docs/informes/tanda8/S2a_ensayo_tabla.md` (`S2A_ESCRIBIR_INFORME=1`). Resultado: 25 passed.
- d826: cancelar en ESTERILIZACION y perder el Principal → `solo_lenta`, sale de FALLA sin técnico, cámara no segura, rápida cerrada (4/4).
- d827: 3 s sin enlace en ESTERILIZACION → COMPLETADO, exposición +3,5 s, "Sin datos: 3 s" (4/4).
- d828: 11 cortes de 3 s → FALLO_ESTERILIZACION con CIC-11 (4/4).
- d829: vuelven los datos sin tramas nuevas y cae otra vez → FALLO_CONEXION (4/4).
- d8210 / d8210_ref: Principal perdido en DESCOMPRESION. Líquidos: sellada 10 min sin abrir ninguna válvula; sin Referencia abre la lenta a los 30,0 min (espera sin sonda); con Referencia, al enfriarse a 70 °C. Programas sólidos (modo 1): la lenta de inmediato, como antes.
También pasan sin cambios `test_q1_ensayo_simulador.py`, `test_e1_ensayo_simulador.py` y `test_t11_programas_integracion.py`.

## 3. Hoja de banco y riesgos
- Hoja de banco: F-12 (D8-2.7), F-13 (D8-2.8), F-14 (D8-2.9, bloque C), F-15 y F-16 (D8-2.10) en `docs/mis_plans/hoja_pruebas_banco/pruebas.py`; md/html regenerados (88 pruebas).
- `docs/riesgos/registro_riesgos.md`: HAZ-S2A-01 a 05. `docs/riesgos/matriz_trazabilidad.md`: REQ-28 a REQ-32.

## 4. Revisores ★
Lanzados en paralelo (`safety-reviewer`, `timing-auditor`) sobre el código de la rama (no tenían Bash: leyeron los archivos, no el diff).
Primera vuelta: Seguridad 2 Altos (SAF-01, SAF-02), 3 Medios, 2 Bajos; Temporización 1 Alto (TMG-01), 3 Medios, 4 Bajos. Corregidos en b2db729: SAF-01 (en parte, ver abajo), SAF-02, SAF-03, SAF-05, SAF-06, TMG-01, TMG-02, TMG-03, TMG-04, TMG-05, TMG-08.
Sin cambio, con motivo: SAF-04 (el handshake de reconexión manda ALL_OFF y verifica las salidas apagadas antes de dar el enlace por conectado), SAF-07 y TMG-06 (Bajos), TMG-07 (el timeout de F0 no se corre con las pausas a propósito: los timeouts son límites de seguridad, mismo principio que D8-2.12).

Segunda vuelta (sobre b2db729): **0 Críticos, 0 Altos** en ambos. Seguridad baja SAF-01 a Media "con condición": SAF-08 y SAF-09 pasarían a Alta si la cámara NO tiene válvula de seguridad mecánica (pregunta 4). Corregidos después en 2a6f51a: SAF-08 (perder la lectura de presión no cierra el alivio abierto), SAF-11 (histéresis de 5 kPa y 3 lecturas para cerrar), TMG-09 (`abortar_por_falla_io` bajo `_sm_lock` y sin apagado en curso; era anterior a la rama), TMG-10 (no se descuenta F0 si el tramo se detecta fuera de las fases de F0), TMG-12, TMG-13; `ultima_di_valida_mono` declarado en `status.py`. Esas correcciones (Medias/Bajas) no pasaron por una tercera vuelta de revisores.
Abiertos (Medios/Bajos, documentados): SAF-09 (con paro, paro sin confirmar o sin datos el protocolo no corre y el alivio no actúa: igual que antes para todos los modos, pero el sellado puede durar horas), SAF-10 (el tope de alivio no tiene un máximo absoluto del equipo), SAF-12 (preexistente: el pitido de "condiciones seguras" acepta un Principal en 0 y usa solo el `temp_max_apertura` global), TMG-11 (pausa sobrecontada unos segundos, del lado seguro), TMG-14 (con FALLO pendiente y una desconexión breve, el protocolo no llama `reanudar()`), TMG-15 (la tolerancia por DI cuenta desde la última DI válida: quedan ~2-2,5 s tras detectarla; más conservador frente al WD de 5 s, más abortos COM-03 con intermitencia).

## 5. Pruebas
Por la regla 8 de esta sesión NO se corrió la suite completa (la corre la sesión principal al unir). Siempre con `PYTHONPATH=<worktree>/src`; `autoclave.__file__` = `C:\\Users\\tecni\\Documents\\codigo_autoclave\\.claude\\worktrees\\agent-a74be21cea62bc278\\src\\autoclave\\__init__.py`.
Pruebas nuevas: `test_t8_s2a_26_salir_falla_solo_lenta.py`, `test_t8_s2a_27_pausa_desconexion.py`, `test_t8_s2a_28_tope_pausa.py`, `test_t8_s2a_29_tramas_di_distintas.py`, `test_t8_s2a_210_liquidos_sellado.py`, `test_t8_s2a_revision.py`, `test_t8_s2a_ensayo_simulador.py`. Modificada: `test_o2a_parametros_equipo.py` (parámetros nuevos).
Corrida relevante (pruebas de S2a y de lo que importa lo tocado: ciclo, ControlLoop, F0, protocolo, estado seguro, esterilización, descompresión, T2/T3/T5/T7/T11, Q1, E1, U4, serial, enlace, tarjeta, alarmas, máquina de estados, parámetros del equipo): **1828 passed, 4 skipped, 1 failed**; la falla (`test_e6_enlace_handshake.py::test_uptime_que_retrocede_es_reinicio`, hilos con espera por tiempo) pasa 3/3 aislada: temporización por la carga de la máquina, ajena al cambio (SerialLink no se tocó en esa corrección).
Tras las correcciones de la segunda vuelta: 557 passed / 2 skipped (S2a, F0, ControlLoop, E6, T5, Q1, P-2, esterilización) y 686 passed / 1 skipped (ensayos S2a/E1/T11, ciclo, T3, U4, estado seguro, protocolo). Otra corrida de backend/endpoints/ciclos (sobre b2db729): 1395 passed.

## 6. DECISIONES SIN CONFIRMAR
1. D8-2.10: espera sellada con TODAS las salidas del protocolo cerradas (sin reponer aire comprimido, sin agua de chaqueta).
2. D8-2.10: el drenaje solo no autoriza el venteo (ver hallazgo del ensayo); el Principal que vuelve a leer caliente también veta el venteo (nunca lo autoriza).
3. D8-2.10: alcance = carga líquida y modos 4/5, enfriando con contrapresión (fase DESCOMPRESION en su sub-etapa de enfriamiento, o el protocolo de fallo con la cámara presurizada al disparo).
4. D8-2.10: alivio por sobrepresión con tope max(`presion_camara_enfriamiento`, P_sat(t_est)) + `rango_presion_ester`, 3 lecturas para abrir, histéresis de 5 kPa y 3 lecturas para cerrar; sin lectura de presión no se abre, pero si ya estaba abierto no se cierra.
5. D8-2.10: la espera sin sonda sigue contando durante una pausa (paro, sin datos): la cámara estuvo igual de sellada.
6. D8-2.9: un enlace que no informa la secuencia (solo dobles de prueba) cuenta cada tick, como antes.
7. TMG-01: retroceso máximo del inicio del tramo sin datos de 2 s (vigencia de la DI 1,5 s + un tick).
8. SAF-05: el corte por tramo abierto solo en ESTERILIZACION (es lo que define D8-2.8) y solo con la exposición ya iniciada.
9. Textos del motivo de CIC-10 (parámetro `motivo`) en español, como los existentes (no están en el catálogo i18n).
10. TMG-10: si el tramo sin datos se detecta ya fuera de las fases que acumulan F0, no se descuenta (la fase ya se dio por cumplida con ese F0).

## 7. PREGUNTAS PARA CRISTIAN
1. **D8-2.10, contrapresión:** ¿durante la espera sellada se repone aire comprimido hasta `presion_camara_enfriamiento` (solo depende de `pres_camara`) y se sigue con el agua de chaqueta? Hoy todo cerrado: la presión cae al enfriarse el gas. En banco (F-15) anotar cuánto baja.
2. **D8-2.10, drenaje:** ¿confirmas que el drenaje solo no basta para ventear? (su agua lo mantiene bajo 70 °C con la carga caliente).
3. **D8-2.10, otras fases:** perder el Principal con líquido caliente en la pre-espera de DESCOMPRESION o en ESTERILIZACION sigue venteando por la lenta (P-2). ¿Se extiende el sellado?
4. **¿Hay válvula de seguridad mecánica en la cámara, y a qué presión está tarada?** Si no la hay, SAF-08/SAF-09 de la revisión pasan a Alta (toda la protección contra sobrepresión del sellado sería por software). ¿Y qué entrega el transductor fuera de rango (None o un valor saturado)?
5. **D8-2.6:** ¿la salida de FALLA sin técnico vale también si la causa original fue una falla de E/S (COM-03) o de puerta?
6. **CIC-11 por tramo abierto (SAF-05):** con la tarjeta caída el paro está activo, así que el protocolo se dispara sin abrir válvulas y pide confirmación (la cámara queda presurizada hasta confirmar). ¿Es lo que quieres para CIC-11?
7. **Alivio con paro o sin datos (SAF-09):** ¿se deja actuar el alivio por sobrepresión del sellado con el paro liberado sin confirmar, como excepción a §15.1?
8. **SAF-05 fuera de ESTERILIZACION:** un enlace que va y viene sin llegar a COM-02 deja el ciclo detenido sin tope en las demás fases. ¿Tope general?

## 8. Puntos de choque al unir
- i18n: `src/autoclave/i18n/es.json` y `en.json` (claves `parametros_equipo` / `parametros_equipo_desc`: `pausa_max_esterilizacion_s`, `espera_sellado_sin_sonda_min`).
- Parámetros del equipo nuevos: `src/autoclave/config/global_params.json` (`pausa_max_esterilizacion_s`, `espera_sellado_sin_sonda_min`) y `tests/test_o2a_parametros_equipo.py`.
- Catálogo de alarmas: CIC-11 en `state_machine/alarms/catalogo.py` y `tests/test_alarmas_catalogo.py`.
- `db_manager.py`: no se tocó (sin migración).
- QML: no se tocó.
- Hoja de banco F-12 a F-16 y REQ-28 a REQ-32 / HAZ-S2A-xx: pueden chocar en numeración con otras etapas (renumerar al unir).
- Archivos compartidos con S2b probablemente: `control_loop.py`, `states/ciclo.py`, `estado_seguro.py`, `protocolo_fallo.py`, `core/runtime/status.py`.

## 9. Pendientes
- Banco: F-12 a F-16.
- Abiertos Medios/Bajos de §4 (SAF-09, SAF-10, SAF-12, TMG-11, TMG-14, TMG-15).
- Tercera vuelta de revisores sobre 2a6f51a (no corrida).
- Preguntas de §7.
