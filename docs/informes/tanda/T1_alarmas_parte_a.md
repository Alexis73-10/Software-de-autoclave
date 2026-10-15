# T1 — Integración de `alarmas-parte-a` en `dev-noche`

Instrucción: tanda 2026-10-14 §2 T1. Informe de referencia: `docs/informes/estado_ramas_2026-10-10.md`.
Informe propio de la rama: `docs/informes/sistema_alarmas_parte_a.md` (llega con el merge).

## 1. Cómo se integró

- **Merge `--no-ff`** de `alarmas-parte-a` (20 commits) sobre `dev-noche`, no rebase. DECISIÓN SIN CONFIRMAR: el merge conserva la historia de la rama y es reversible con un solo `git revert -m 1`; rebasar 20 commits sobre F1 habría reescrito la rama y repetido los conflictos en cada commit. Alternativa: rebase interactivo de la rama antes de unir.
- Las copias sin seguimiento de `analisis_sistema_alarmas.md`, el plan y la spec de la Parte A se apartaron (la spec local era la versión vieja, como advertía `estado_ramas_2026-10-10.md`); entran las de la rama.
- Conflictos: 11 archivos (no 4: dev avanzó desde el 10-10 con E0/E1, autenticación y E6): `server.py`, `db_manager.py`, `control_loop.py`, `state_machine.py`, `ciclo.py`, `falla.py`, `hibernacion.py`, `preparacion.py`, `preparado.py`, `test_control_loop_set_active_cycle.py`, `test_io_test_mode_endpoints.py`.
- I18N-30: la rama no tocaba `textosJson`, `cargar_textos`, `AccionesCiclos` ni `assets/textos/es.json`; no hubo nada que rebasar sobre F1.

## 2. Resolución (semántica que se conservó de dev)

| Tema | dev conservado | Rama aplicada |
|---|---|---|
| Paro | flag `PARO_EMERGENCIA` (E1-5), `apagar_por_paro()` (A-7), RESET_FALLA descartado con paro (OPC-23) | `activar(SIS_01)`; texto de SIS-01 incluye el aviso de cableado NC |
| Sensores en PREPARACION/PREPARADO | `lectura_valida` (None/no finito = desconectado, E0-1/A-5), `sonda_instalada` (A-2), empaque por perfil (E1-2) | SEN-01 con origen legible |
| Suministros | `entrada_requerida` (E1-1), eléctrico sin entrada = sin suministro (A-9) | SUM-02…SUM-06 |
| Puertas | `numero_puertas`, `revisa_empaque`, `lectura_valida` | PUE-01/PUE-02/PUE-03 |
| `/status` | `card_connected`, `comunicacion`, `tarjeta`, `entradas_no_monitoreadas`, `sondas_no_vigiladas`, `_orden_puerta` (T-13/T-18) | contrato nuevo de alarmas, `/alarms/{clave}/acknowledge`, `/alarms/history` |
| BD | migraciones versionadas, `audit_log`, columnas de usuarios | columna `codigo_fallo`, historial de alarmas en hilo propio |

## 3. Migración de lo que E6 y dev agregaron con la API vieja

- **9 ids de la tarjeta**: entran al catálogo con su nombre (regla 8 de la tanda: ningún id se renombra). Nivel ALARMA (= "FALLA" en `/status`), `bloquea_inicio`, despeje automático: se resuelven al llegar el evento `conectada` del handshake.
- **En ciclo** (`abortar_por_falla_io`): código nuevo **COM-03** "Falla de la tarjeta de E/S durante el ciclo", FALLO_CRITICO (= "EMERGENCIA"), despeje manual, `origen` = id de la tarjeta (clave `COM-03|TARJETA_WATCHDOG`), descripción con el id y el motivo. `fase_ciclo = "FALLO_IO"` y `codigo_fallo = "COM-03"` (P5). Mismo patrón que COM-01/COM-02 de la rama. Resuelve de paso SAF-06 de E0 (la EMERGENCIA del ciclo ya no comparte id con la FALLA de fuera de ciclo).
- **`OPERANDO_SIN_BD`** y **`CONFIGURACION_INVALIDA`** (arranque): ids conservados, ALARMA, bloquean, despeje manual.
- `FALLO_CONEXION` ya estaba migrado por la rama a COM-02.
- Los ids conservados se listan en `CODIGOS_CONSERVADOS`; la prueba de formato `ÁREA-NN` del catálogo los exceptúa.

DECISIÓN SIN CONFIRMAR (D-T1-1): COM-03 en vez de reutilizar los 9 ids en ciclo con otro nivel. El catálogo fija un nivel por código; usar los mismos ids con nivel distinto exigía cambiar el modelo de la Parte A. Alternativa: 9 códigos COM-xx para ciclo, o admitir nivel por activación.

## 4. Pruebas

| Momento | Resultado |
|---|---|
| Rama `alarmas-parte-a` sola (informe de la rama) | 1799 |
| `dev` al cerrar E-0 | 2818 |
| Tras el merge, antes de migrar pruebas | 2 errores de colección; luego ~160 fallos |
| Tras migrar | 3000 passed (antes de los ajustes de revisores) |
| Final | ver `estado.md` |

Pruebas de dev escritas con la API vieja: se agregó a `tests/alarmas_helpers.py` un traductor (código, origen) → id viejo según `catalogo_alarmas.md` §9 (`ids_viejos_activados`, `ids_viejos_resueltos`, `ids_viejos_activos`) para no reescribir cada aserción. Archivos tocados: `test_e1_supply_inputs`, `test_e0_lecturas_invalidas`, `test_adenda_estados`, `test_e1_puertas_perfil`, `test_secuencia_arranque`, `test_ciclo_drenaje`, `test_arranque_sin_tarjeta`, `test_e1_integracion_inicio_ciclo`, `test_e1_paro_emergencia_nc`, `test_preparacion_alarm_wording`, `test_config_invalida_arranque`, `test_e6_control_loop_tarjeta`, `test_ciclo_alarmas_fallo`, `test_alarmas_catalogo`, `test_cycle_logger_printer`.

Cambios de comportamiento visibles en pruebas:
- `test_arranque_sin_tarjeta`: COM-01 (antes `NO_HAY_CONEXION`) con la tarjeta que nunca conectó aparece al agotar la tolerancia de 5 s (fix `a2dcbc7` de la rama), no de inmediato.
- `_verificar_puertas` devuelve 4 valores (código de alarma y valores); las pruebas de E1 comparan los dos primeros.

## 5. Revisores

`safety-reviewer`: sin Crítico ni Alto. Bajos: SAF-01 (orden alarma/acción) **corregido**: en `_procesar_evento_tarjeta` el `solicitar_handshake()` va antes de `activar`, `activar(COM_01)` protegido, y prueba nueva de que todo id que emite `serial_link.py` está en el catálogo. Pendientes (Bajo): SAF-02 CIC-07/CIC-08 quedan activas si el operador confirma antes de la apertura automática; SAF-03 `OPERANDO_SIN_BD` desaparece de `/status` tras el primer reinicio FALLA→PREPARACION (se ve en T8); SAF-04 `/alarms/{clave}/acknowledge` sin sesión ni `audit_log` (decidir contra spec §7.2; Parte C).

`timing-auditor`: sin Crítico ni Alto. Corregidos (Medio): TMG-02 `ControlLoop.stop()` ahora detiene el lazo y espera el hilo **antes** del ALL_OFF (también TMG-11 de E0); TMG-03 `cycle_logger` mide el intervalo de lecturas y el tiempo relativo del ticket con el reloj monotónico. Pendientes: TMG-01 reconocimiento por clave y no por ocurrencia (Medio); TMG-04 el lifespan no detiene el historial ni cierra la BD (se ve en §16 Apagar, T7); TMG-05..TMG-10 (Bajo).

## 6. PENDIENTES

- Textos i18n de las alarmas del catálogo (hoy en Python); la UI QML sigue leyendo `titulo`/`descripcion` de `/status`.
- Partes B y C del sistema de alarmas (no forman parte de la tanda).

## 7. Comprobaciones manuales de Cristian

- Con el equipo sin tarjeta: a los ~5 s debe aparecer COM-01 "Sin comunicación con la tarjeta".
- Pulsar el paro en PREPARADO: SIS-01 con el texto del cableado NC; al soltarlo, desaparece.
- Provocar un fallo de ciclo y revisar en el historial de alarmas (`GET /alarms/history`) la fila con su ciclo.
