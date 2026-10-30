# Planeación de la V1.1 — BORRADOR

Fecha: 30-oct-2026. Estado: **BORRADOR para aprobación de Cristian. Todo este documento es DECISIÓN SIN CONFIRMAR**: objetivos, prioridades, alcance y esfuerzos son propuestas. Base: 1.0 según `docs/mis_plans/cierre_1_0_checklist.md`.

Convenciones:
- **Esfuerzo:** S = una sesión, sin cambio de seguridad grande; M = una tanda con revisión R; L = varias tandas o una planeación propia antes de codificar.
- **Riesgo (ISO 14971):** peligro → daño, y si la función **reduce** un riesgo existente o **introduce** uno nuevo. Las severidades son una primera estimación, no una evaluación aprobada.
- **«Suposición»** marca todo lo que no sale de un documento o del código.
- Ningún punto agrega requisitos nuevos: cada uno nace de un pendiente, anomalía, riesgo o planeación existente (columna «Origen»).

---

## 1. Objetivos de la V1.1 (propuesta)

1. **Bajar los residuales ALTOS** que la 1.0 deja aceptados: HAZ-IO-05 (a) y (e), y los abiertos de puertas con paro (HAZ-B9-03).
2. **Cerrar lo que la 1.0 aplazó por falta de banco o de diseño:** líquidos (C-11/C-12, sensor de líquido secundario), red Modbus (MED-04) y la parte de MED-03 que no se vigila con la conexión ya verificada.
3. **Licencia L1** si no entró en la 1.0 (ver C-02 del checklist).
4. **Deuda menor** de anomalías conocidas (AN-15, AN-16, AN-17, AN-19) y de las decisiones sin confirmar que Cristian decida cambiar.
5. Preparar lo que pide una **liberación clínica** (si C-01 del checklist la deja para la 1.1).

Fuera de alcance de esta propuesta: hardware nuevo, otro protocolo de E/S, nuevos tipos de programa.

---

## 2. Resumen priorizado

| Prio | ID | Función | Origen | Esfuerzo | Banco |
|---|---|---|---|---|---|
| P1 | V11-01 | Función analógica sin verificar no decide la cámara segura | HAZ-IO-05 (e), residual ALTO | M | Sí (en seco) |
| P1 | V11-02 | Reasignación con carga líquida sellada (H1) | HAZ-IO-05 (a), residual ALTO | M | Sí (G) |
| P1 | V11-03 | Puertas en movimiento se detienen con el paro | HAZ-B9-03 | M | Sí (puertas avanzadas) |
| P1 | V11-04 | Protección de la red Modbus | MED-04 | M | Sí (M) |
| P1 | V11-05 | Vigilancia de la configuración de seguridad con la conexión verificada | MED-03 residual | M | Sí (M-5, M-5b) |
| P2 | V11-06 | Líquidos: dos lazos y eliminación de aire | `planeacion_liquidos_dos_lazos.md` (C-11, C-12), AN-09 | L | Sí (G) |
| P2 | V11-07 | Sensor de líquido secundario (`temp_2_camara`) en dos puertas | `CLAUDE.md` «Pendiente compartido», `planeacion_fase_esterilizacion.md` | L | Sí (G) |
| P2 | V11-08 | Licencia L1 (y L2 en paralelo) | `planeacion_licencia_pago.md` §4 | L | No (simulador de fecha) |
| P2 | V11-09 | Puertas: `source_door` obligatorio y origen autenticado | Nota del 29-sep, `rutas/puertas.py` | S | Sí (en seco) |
| P2 | V11-10 | «Reiniciar software» con el aviso de la reasignación | HAZ-IO-05, «Abierto, fuera de alcance» | S | No |
| P2 | V11-11 | Estado seguro con `asignacion_io.json` inválido | HAZ-IO-03 | M | Sí (en seco) |
| P3 | V11-12 | Información del módulo E/S por esclavo | M-2, MED-05, ADB-02 | S | Sí (M-2) |
| P3 | V11-13 | Límites de presión atados al transductor; P2 con límites del sitio | AN-15, AN-16 | S | No |
| P3 | V11-14 | Histéresis del corte de chaqueta y CIC-18 | AN-19 | S | Sí (H-05) |
| P3 | V11-15 | Mantenimiento preventivo/correctivo con formulario y PDF | `planeacion_mantenimiento.md` v1 | M | No |
| P3 | V11-16 | Anuncios por voz | `planeacion_anuncios_voz.md` | M | Sí (audio) |
| P3 | V11-17 | `/cycle/select` con sesión | HAZ-SEN-05 (pregunta abierta) | S | No |
| P3 | V11-18 | Revisión de textos de seguridad por hablante nativo | HAZ-I18N-01 | S | No |

Prioridad: P1 = baja un residual ALTO o MEDIO de seguridad; P2 = función aplazada con planeación o pedido existente; P3 = mejora o deuda menor.

---

## 3. Detalle por función

### V11-01 — Función analógica sin verificar no decide la cámara segura (P1)
- **Problema.** HAZ-IO-05 (e), residual ALTO aceptado: tras reasignar `pres_camara` o el Principal, la lectura del puerto nuevo **sin verificar** (SEN-09) decide `camara_segura`, el fin del estado seguro, `no_abrir` y el interlock de puertas. Un puerto mal cableado que lea ~atm con la cámara presurizada habilita la puerta.
- **Alcance (propuesta).** Mientras `pres_camara` o el Principal estén sin verificar: `camara_segura` = no segura, el estado seguro no termina por ellas, «NO ABRIR» se mantiene y las puertas no abren por software. Se conserva la verificación por lectura de RSB-07 (la decisión de Cristian del 30-oct). Texto propio en la pantalla («Verifique la función reasignada para liberar la puerta»).
- **Riesgo.** Reduce HAZ-IO-05 (e) de ALTO a BAJO. Introduce: equipo con puerta bloqueada por software hasta verificar; con puertas manuales sin enclavamiento no hay bloqueo físico (igual que HAZ-ESS-01). Suposición: que esto no contradice la intención de la tanda 24 (permitir reasignar, no liberar la puerta).
- **Pruebas.** `tests/test_ess07_reasignacion_reinicio.py` (sección nueva), `tests/test_t4_camara_segura.py`; banco: reasignar la presión a un puerto con 101 kPa simulados y la cámara a presión → puerta no abre hasta verificar.
- **Esfuerzo.** M. **Dependencias de banco:** en seco, con un transmisor en un puerto libre.

### V11-02 — Reasignación con carga líquida sellada (P1)
- **Problema.** HAZ-IO-05 (a), H1, residual ALTO: el reinicio que aplica una reasignación arranca el estado seguro S9 en `solo_lenta` y ventea por la lenta una carga líquida que estaba sellada (D8-2.10). Los 2 `xfail(strict)` de `test_ess07` lo documentan.
- **Alcance (propuesta).** Una de dos, a decidir: (a) el arranque tras `reinicio_control` recupera el estado sellado del ciclo anterior si el último ciclo fue líquido y la cámara no es segura, o (b) volver a rechazar la reasignación solo en ese caso (líquido sellado), con aviso. Requiere decidir cuál.
- **Riesgo.** (a) reduce H1 pero agrega persistencia de estado entre procesos (riesgo nuevo: un estado guardado viejo). (b) reduce H1 y quita disponibilidad en un caso urgente.
- **Pruebas.** Convertir los 2 `xfail(strict)` en pruebas que pasan; planta simulada de líquidos modos 4/5.
- **Esfuerzo.** M. **Banco:** bloque G con vidrio real.

### V11-03 — Puertas en movimiento se detienen con el paro (P1)
- **Problema.** HAZ-B9-03 (abierto): la máquina de estados de una puerta avanzada sigue con el paro; una puerta en CERRANDO, o que pasó de ATRAPADA a ABRIENDO, reanuda sola al soltar el paro si no venció `timeout_puerta`. Daño: aplastamiento.
- **Alcance (propuesta, la que sugiere el registro).** Con el paro, toda puerta en movimiento pasa a un estado de parada y exige una orden nueva al soltarlo. HAZ-B9-02 (aire del empaque con el paro) se decide aparte.
- **Riesgo.** Reduce HAZ-B9-03. Introduce: puerta detenida a medio camino (empaque sin presión) que hay que volver a mandar.
- **Pruebas.** `tests/test_b9_buzzer_paro.py` (casos nuevos con `AdvancedDoor`), pruebas de `ServicioPuertas`.
- **Esfuerzo.** M. **Banco:** solo en un equipo con puertas avanzadas (el de pruebas tiene puertas abatibles manuales).

### V11-04 — Protección de la red Modbus (P1)
- **Problema.** MED-04 (MEDIA): Modbus TCP sin autenticación; cualquiera en la red de los módulos puede escribir bobinas y la configuración de seguridad, y leer la contraseña web (fc03 0x7590). Hoy la protección es solo la red dedicada.
- **Alcance (propuesta, opciones a elegir).**
  1. Regla del Firewall de Windows en el paso 08 del Setup: el adaptador 192.168.3.10 solo habla con 192.168.3.7:502 (y la web del módulo solo desde el PC).
  2. Detección de otro equipo en la red de los módulos (ARP de la subred) con aviso no bloqueante. Suposición: que el M31 no tenga filtro de IP propio; revisar el manual antes.
  3. Bloquear físicamente el segundo RJ45 del principal (procedimiento, no software).
- **Riesgo.** Reduce MED-04. Introduce: una regla de firewall mal hecha deja el equipo sin E/S (falla cerrada, alarma de conexión).
- **Pruebas.** `tests/test_t20_s3_setup_modbus.py` (funciones puras del paso 08 con la regla nueva); banco M-0/M-7 con un segundo PC en la red.
- **Esfuerzo.** M. **Banco:** bloque M.

### V11-05 — Vigilancia de la configuración de seguridad con la conexión verificada (P1)
- **Problema.** MED-03, residual: un cambio por la web con la conexión ya verificada no se detecta hasta la siguiente conexión; la evidencia del reinicio es indirecta y el tope de reinicios vive en memoria.
- **Alcance (propuesta).** Relectura periódica (p. ej. cada 60 s, fuera del sondeo rápido) de los bloques de configuración de seguridad; una diferencia da `TARJETA_CONFIG_SEGURIDAD` (en ciclo, COM-03, como hoy al conectar). Si M-5b confirma que 0x0C37 cuenta desde el encendido, usarlo como prueba positiva del reinicio.
- **Riesgo.** Reduce MED-03. Introduce: más tráfico en el lock único del cliente (riesgo de temporización: pasar por `timing-auditor`).
- **Pruebas.** `tests/test_t20_s1_adb.py`, `tests/test_t20_integracion.py` con `m31_simulado` cambiando un registro a mitad.
- **Esfuerzo.** M. **Banco:** M-5, M-5b.

### V11-06 — Líquidos: control en dos lazos y eliminación de aire (P2)
- **Problema.** AN-09: líquidos con la implementación provisional de la tanda 11; C-02/C-03 desactivados con carga líquida. Sin quitar el aire, la cámara a 226 kPa queda en ~106 °C (cálculo de la planeación).
- **Alcance.** El de `docs/mis_plans/planeacion_liquidos_dos_lazos.md` (C-11 lazo de presión hacia `Psat(T_est + delta)` y sonda en el vapor para C-02/C-03; C-12 purga A o prevacío en frío B). La planeación dice «C-11 no se debe habilitar sin C-12». Tiene preguntas abiertas en su §10 que hay que cerrar antes.
- **Riesgo.** HAZ-LIQ-01, HAZ-S2A-05, HAZ-S1-05: ebullición, rotura de vidrio, carga no estéril. Introduce un modo de control nuevo (riesgo alto si se equivoca el lazo).
- **Pruebas.** Planta simulada de líquidos; las de la planeación §(pruebas).
- **Esfuerzo.** L. **Banco:** bloque G con vidrio real, sonda en la carga y sonda en el vapor.

### V11-07 — Sensor de líquido secundario (`temp_2_camara`) en equipos de dos puertas (P2)
- **Problema.** `CLAUDE.md` y `planeacion_fase_esterilizacion.md`: «aplazado en ambas fases (CALENTAMIENTO y ESTERILIZACION), requiere levantamiento aparte antes de codificar». Hoy `has_liquid_sensor` solo habilita `temp_2_camara` en clases de laboratorio y el F0 (HAZ-SEN-02: F0 solo con el Principal).
- **Alcance.** **Primero el levantamiento** (no hay requisito escrito): qué decide esa sonda (entrada a esterilización, exposición, F0, apertura) y en qué configuraciones. Suposición: que el pedido es para equipos de dos puertas con carga líquida; confirmarlo con Cristian.
- **Riesgo.** HAZ-SEN-02 (F0 optimista), HAZ-LIQ-01. Se cruza con V11-06 (rol de la sonda del líquido): conviene hacerlas en la misma planeación.
- **Pruebas.** A definir con el levantamiento.
- **Esfuerzo.** L (incluye la planeación). **Banco:** G.

### V11-08 — Licencia L1 (P2, o P1 si se va a vender a plazos)
- **Problema.** Solo existe L0; el secreto de activación va empaquetado en el ejecutable («riesgo aceptado hasta L1»). LIC-01..03.
- **Alcance.** El de `planeacion_licencia_pago.md` v3 §2 (estados PLAZO/GRACIA/BLOQUEADO/PERMANENTE, códigos, pantalla de bloqueo con franja de cámara y paro, reloj, auditoría) y L2 en su repositorio aparte.
- **Riesgo.** §2.7 de esa planeación. El bloqueo nunca interrumpe un ciclo (DL-10) y el estado seguro sigue con el equipo bloqueado: es la parte que toca seguridad.
- **Pruebas.** §5 de esa planeación (simulador de fecha).
- **Esfuerzo.** L. **Banco:** arranque bloqueado con la cámara presurizada (en seco).

### V11-09 — Puertas: `source_door` obligatorio y origen autenticado (P2)
- **Problema.** La nota de memoria del 29-sep está **parcialmente resuelta** (tanda 2, S3e): con `source_door`, otra puerta da 409 `puerta_ajena`. Queda: (1) sin `source_door` se acepta como «desconocido» (clientes antiguos); (2) el valor es declarado por el cliente, sin autenticar.
- **Alcance (propuesta).** Rechazar la orden sin `source_door` (422) ahora que ningún cliente antiguo queda (suposición: verificar que `ui_pyside` ya no manda órdenes de puerta). Lo de autenticar la pantalla queda como pregunta: el backend escucha solo en 127.0.0.1, así que un atacante ya tendría el PC.
- **Riesgo.** HAZ-FC-01 (apertura con la otra puerta). Introduce: un cliente olvidado deja de poder abrir.
- **Pruebas.** `tests/test_comandos_puerta.py`, `tests/test_puertas_fallas_endpoints.py`. Pasar por `safety-reviewer` (interlock de puertas).
- **Esfuerzo.** S. **Banco:** en seco, abrir desde cada pantalla.

### V11-10 — «Reiniciar software» con el aviso de la reasignación (P2)
- **Problema.** HAZ-IO-05: «Abierto, fuera de alcance: “Reiniciar software” (`rutas/apagado.py`) aplica una asignación guardada pendiente», sin el aviso RSB-03.
- **Alcance.** Si hay asignación pendiente, «Reiniciar software» muestra el mismo aviso (`aviso_camara`) y pide la misma confirmación que Aplicar, o no la aplica.
- **Riesgo.** Reduce la rama no cubierta de HAZ-IO-05.
- **Pruebas.** `tests/test_r8_reinicio_backend.py`, caso nuevo.
- **Esfuerzo.** S.

### V11-11 — Estado seguro con `asignacion_io.json` inválido (P2)
- **Problema.** HAZ-IO-03 (MEDIO, pregunta abierta desde la tanda 8): con CONFIGURACION_INVALIDA no corre la recuperación de ciclo interrumpido ni el estado seguro.
- **Alcance.** Depende de C-08 del checklist. Sin decisión, no se codifica.
- **Riesgo.** Cámara presurizada sin venteo por software tras un corte.
- **Pruebas.** `tests/test_r8_arranque.py`.
- **Esfuerzo.** M. **Banco:** en seco con el archivo dañado a propósito.

### V11-12 — Información del módulo E/S por esclavo (P3)
- **Problema.** El pedido de «versión de la tarjeta» en Información del equipo **ya está hecho** (`/status.modulo_es.version`, cadena «9232-0-13 / v1.0,…,-»); el «último mantenimiento» también (`GET /maintenance`). Queda: M-2 (qué esclavo es cada posición de 0x0D80 y por qué una da 0x0000).
- **Alcance.** Tras M-2, mostrar una fila por módulo (modelo y versión) en Información del sistema, en lugar de la lista separada por comas.
- **Riesgo.** Ninguno de seguridad (informativo, MED-05 BAJO).
- **Pruebas.** `tests/test_t20_s1_adb.py`, puente `info_equipo`.
- **Esfuerzo.** S. **Banco:** M-2 primero.

### V11-13 — Límites de presión atados al transductor; migración P2 con los límites del sitio (P3)
- **Problema.** AN-15 (P2 se evalúa con los límites de fábrica) y AN-16 (fondo de escala 100–1000 kPa sin atar al transductor 0–400 kPa ni a P7 450 kPa).
- **Alcance.** Coherencia `fondo de escala <= rango del transductor` y P2 después de leer `global_params.json`.
- **Riesgo.** Corte de chaqueta por encima de lo medible.
- **Pruebas.** `ConfigManager`, `limites_equipo`.
- **Esfuerzo.** S.

### V11-14 — Histéresis del corte de chaqueta y CIC-18 (P3)
- **Problema.** AN-19: con la chaqueta en 375 kPa la válvula y el aviso conmutan en ticks alternos.
- **Alcance.** Histéresis de reapertura (valor a decidir con H-05) sin cambiar el corte (sigue siendo inmediato).
- **Riesgo.** Lado seguro (corta igual); riesgo de desgaste de válvula si no se hace.
- **Pruebas.** Pruebas de D-CHQ/SAF-09 de la tanda 16.
- **Esfuerzo.** S. **Banco:** H-05.

### V11-15 — Mantenimiento preventivo/correctivo con formulario y PDF (P3)
- **Problema.** `planeacion_mantenimiento.md` v1 (20-oct) está como «borrador para revisión de Cristian». Suposición: que solo existe el registro básico de M1 (fecha y contador) y no los formularios; verificar antes de planear.
- **Alcance.** El de esa planeación (solo informativo, sin bloquear ciclos). Mantenimiento predictivo sigue fuera.
- **Riesgo.** Bajo (informativo).
- **Esfuerzo.** M.

### V11-16 — Anuncios por voz (P3)
- **Problema.** `planeacion_anuncios_voz.md`: especificación pendiente de aprobación, objetivo V1.0 en ese documento, no implementada.
- **Alcance.** El de esa planeación (WAV pregrabados, cola con prioridad, Clase A propuesta).
- **Riesgo.** Clase A propuesta en la planeación; un anuncio equivocado no debe reemplazar a la alarma visual ni al buzzer.
- **Esfuerzo.** M. **Banco:** salida de audio del PC.

### V11-17 — `/cycle/select` con sesión (P3)
- **Problema.** HAZ-SEN-05: «`/cycle/select` sigue sin autenticación y se permite en FALLA (pregunta abierta)».
- **Alcance.** A decidir: exigir sesión o dejarlo (el control de seguridad ya toma el máximo de los Principales).
- **Riesgo.** Bajo (mitigado por `temp_seguridad`).
- **Esfuerzo.** S.

### V11-18 — Revisión de textos de seguridad por hablante nativo (P3)
- **Problema.** HAZ-I18N-01: «Por completar: revisión por hablante nativo de textos de seguridad».
- **Alcance.** Lista de claves de seguridad (NO ABRIR, alarmas, estado seguro, fin de ciclo) a un revisor; `docs/mis_plans/revision_traducciones.md` existe como base.
- **Esfuerzo.** S (sin código).

---

## 4. Orden propuesto (tandas)

1. **Tanda A (seguridad, sin hardware nuevo):** V11-01, V11-10, V11-09, V11-17. Revisión R con `safety-reviewer`.
2. **Tanda B (Modbus):** V11-04, V11-05, V11-12. Depende del bloque M del banco.
3. **Tanda C (puertas y paro):** V11-03 (y la decisión de HAZ-B9-02). Necesita un equipo con puertas avanzadas.
4. **Planeación propia antes de código:** V11-06 + V11-07 juntas (líquidos y sondas), V11-02 (depende de cómo quede el sellado en V11-06).
5. **En paralelo, según negocio:** V11-08 (licencia).
6. **Deuda menor cuando haya hueco:** V11-11 (tras C-08), V11-13, V11-14, V11-15, V11-16, V11-18.

## 5. Preguntas para Cristian

1. ¿La V1.1 es la de la liberación clínica, o sigue siendo para el equipo de pruebas?
2. ¿Qué equipo hay para probar puertas avanzadas (V11-03) y modo chaqueta (VCH-01)?
3. V11-02: ¿opción (a) recuperar el sellado o (b) rechazar la reasignación con líquido sellado?
4. V11-07: ¿qué debe decidir la sonda de líquido secundaria y en qué configuraciones?
5. V11-04: ¿se acepta una regla de firewall en el Setup, o la protección queda en procedimiento?
6. ¿Licencia en la 1.1 o más adelante?
