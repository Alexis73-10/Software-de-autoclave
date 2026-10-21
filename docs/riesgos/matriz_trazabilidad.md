# Matriz de trazabilidad requisito – riesgo – prueba (D1, tanda 6, 21-oct-2026)

Estado: BORRADOR para pasar a xlsx. Los requisitos salen de las specs citadas. Los IDs REQ-xx son propios de esta matriz, salvo donde la spec ya trae uno. Las pruebas son archivos de `tests/`, verificados por nombre el 21-oct.

| Requisito | Fuente | Riesgo(s) | Prueba |
|---|---|---|---|
| REQ-01 Ninguna apertura ni inicio con la cámara no segura (falla cerrada: sensor ausente = no segura) | `planeacion_fin_de_ciclo_y_puertas.md`; CLAUDE.md (apertura automática) | HAZ-FC-01, HAZ-SEN-01, HAZ-SEN-05 | `test_t4_camara_segura.py`, `test_ciclo_apertura_automatica.py`, `test_e1_apertura_automatica_sin_actuador.py` |
| REQ-02 Estado seguro tras cualquier fin de ciclo hasta que la cámara sea segura (P-1) | `instruccion_claude_code_tanda_6.md` §1 | HAZ-T2-01, HAZ-FC-06 | `test_t2_p1_completado_estado_seguro.py`, `test_t5_estado_seguro.py`, `test_s4_cic10.py` |
| REQ-03 Pérdida del Principal = FALLO, venteo por la lenta, inicio bloqueado (P-2) | tanda 6 §1 | HAZ-T2-02, HAZ-SEN-04 | `test_t2_p2_principal_perdido.py` |
| REQ-04 Trama DI vencida: tolerancia ≤ WD del firmware − 1 s, después FALLO_CONEXION (P-3) | tanda 6 §1 | HAZ-T2-03, HAZ-TAR-01 | `test_t2_p3_di_vencida.py` |
| REQ-05 PREPARADO respeta `bloquea_inicio`; COM-02/03 requieren despeje manual (P-4/P-5) | tanda 6 §1 | HAZ-T2-04 | `test_t2_p4_bloquea_inicio.py`, `test_t2_p5_despeje_manual_com.py` |
| REQ-06 Líquidos: venteo por la lenta mientras el Principal > temp_max_apertura (P-12/D-19) | tanda 6 §1 | HAZ-T2-05, HAZ-LIQ-01, HAZ-LIQ-02 | `test_t2_p12_drenaje_liquidos.py`, `test_t5_protocolo_liquidos.py`, `test_t11_programas_integracion.py` |
| REQ-07 El ticket marca la carga no estéril (P-9) | tanda 6 §1 | HAZ-T2-06, HAZ-FC-07 | `test_t2_p9_reimprimir_interrumpido.py` |
| REQ-08 Nunca reanudar un ciclo tras un corte de energía | `planeacion_arranque_y_modo_sin_bd.md`; tanda 3 A2 | HAZ-FC-05 | `test_a2_corte_de_energia.py`, `test_t6_arranque_seguro.py` |
| REQ-09 Modo sin BD | `planeacion_arranque_y_modo_sin_bd.md` | HAZ-BD-01 | `test_t8_modo_sin_bd.py` |
| REQ-10 Tarjeta desconectada detectada y salidas a 0 | `instruccion_claude_code_u4_tarjeta_desconectada.md`, `planeacion_protocolo_serial_esp32.md` | HAZ-TAR-01, HAZ-FC-04 | `test_u4_tarjeta_desconectada.py`, `test_arranque_sin_tarjeta.py`, `test_e6_control_loop_tarjeta.py`; banco: por completar |
| REQ-11 Las unidades son solo de presentación | tanda 5 U1 | HAZ-UNI-01 | `test_u1_unidades.py`, `test_u1_unidades_qml.py`, `test_flujo_unidades.py` |
| REQ-12 Textos en el idioma seleccionado, con respaldo | `planeacion_i18n.md` | HAZ-I18N-01 | `test_i18n.py`, `test_i18n_linea_base.py`, `test_i1_i18n_backend.py` |
| REQ-13 Salida forzada del modo prueba | tanda 4 B8, tanda 5 P1 | HAZ-PRU-01 | `test_b8_salida_forzada_modo_prueba.py`, `test_p1_salida_modo_prueba.py` |
| REQ-14 Caducidad de sesión y tokens | `planeacion_backend_autenticacion.md`; tanda 4 B7 | HAZ-SES-01 | `test_b7_caducidad_tokens.py`, `test_p3_renovacion_pyside.py`, `test_sesion_backend.py` |
| REQ-15 Nunca se comanda una fuente de vapor ausente | tanda noche T2 | HAZ-VAP-01 | `test_t2_vapor_source.py` |
| REQ-16 Roles de sensores y alerta de uniformidad CIC-09 | `planeacion_sensores_ciclo.md` | HAZ-SEN-02, HAZ-SEN-03 | `test_t3_sensores_ciclo.py`, `test_t3_endpoints_sensores.py` |
| REQ-17 ESTERILIZACION: fallas contra t_est fija, debounce de 3 lecturas, F0 opcional | `planeacion_fase_esterilizacion.md`, `planeacion_f0.md` | HAZ-SEN-02 | `test_esterilizacion_fase.py`, `test_control_loop_f0.py`, `test_ciclos_f0_objetivo.py` |
| REQ-18 Puerta con sensor inválido = abierta | `docs/superpowers/specs/2026-05-25-door-type-from-profile-design.md`, fin de ciclo §10 | HAZ-FC-02, HAZ-FC-03 | `test_servicio_puertas.py`, `test_puertas_fallas_endpoints.py`, `test_e1_puertas_perfil.py` |

Por completar: los requisitos de las specs de 2026-05 en `docs/superpowers/specs/` (precalentamiento, purga, fases críticas, suministro eléctrico, perfiles de equipo) siguen sin riesgo asignado. También faltan los ids de la hoja de banco por fila y los requisitos de calentamiento, prevacío y secado.
