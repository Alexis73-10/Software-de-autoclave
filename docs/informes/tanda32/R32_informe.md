# Tanda 32: informe (7-nov-2026)

Rama `tanda32` desde `dev`. Entrega NO compilada. Plan: `docs/mis_plans/prompt_claude_code_tanda32.md`. Commit de código: 63dd5a33.

## Resultado por LIQ
| LIQ | Resultado |
|---|---|
| LIQ-01 | Componente puro `cycle_phases/enfriamiento_contrapresion.py` (`EnfriamientoContrapresion`, `ResultadoTick`), usado por `DescompresionFase._tick_sub_enfriamiento` y `ProtocoloFallo._tick_enfriamiento` (`solo_aviso=True`). Aire en pulsos de 3 s, lenta desde el primer tick en modo 5, `descompresion_chaqueta` abierta fija, condiciones enclavadas (a) presión de cámara y (b) chaqueta despresurizada, `agua_chaqueta` solo con (a) y (b). Topes CIC-22 y CIC-23 (bloqueantes, despeje manual). Parámetros nuevos en modo_4 y modo_5 (`presion_despresurizacion_chaqueta`, `timeout_despresurizacion_chaqueta`, `timeout_presurizacion_enfriamiento`); retirados `tiempo_apertura_chaqueta`/`tiempo_cierre_chaqueta`; migración `_migrar_t32`. |
| LIQ-02 | `P_min = Psat(T_Principal) + 30 kPa`, armado al cumplirse (a); 10 s → CIC-25 (aviso no bloqueante, hasta 5 líneas de ticket por aparición); 60 s → FALLO CIC-24 y protocolo de fallo de líquidos; en el protocolo solo aviso. Sin lectura = bajo el mínimo. |
| LIQ-03 | Modo 5: `descompresion_lenta_rapida` y `presion_cambio`; coherencia `COHERENCIA_DESCOMPRESION` al guardar y cargar; los 5 parámetros en la pantalla de Parámetros del ciclo (es/en). |
| LIQ-04 | `presion_camara_enfriamiento` 300 kPa abs en modo_4 y modo_5 de `cycles/{factory,user}/liquidos.json`; el resto sin cambio. |

## Pruebas
Nuevas: `tests/test_t32_enfriamiento_contrapresion.py`, `tests/test_t32_catalogo_migraciones.py`, `tests/test_t32_integracion_descompresion.py`, `tests/test_t32_integracion_protocolo.py`. El texto de progreso T30-02 sigue correcto (sin cambios).

Suite completa: (se completa al cerrar)
Revisor: (se completa al cerrar)

## Riesgos
HAZ-T32-01 (ebullición por pérdida de contrapresión), HAZ-T32-02 (golpe de ariete / choque térmico en la chaqueta) y HAZ-T32-03 (aguja del modo 5 mal ajustada, residual de puesta en marcha) en `docs/riesgos/registro_riesgos.md`. Trazabilidad REQ-82..REQ-85. Banco: bloque T32 (T32-01..06). Renumerados en la revisión de seguridad (antes HAZ-LIQ-01..03, que chocaban con HAZ-LIQ-01 de la T11 y HAZ-LIQ-02 de D-19, que no cambian).

## Correcciones de la revisión de seguridad
| Hallazgo | Corrección |
|---|---|
| ALTO, tope de LIQ-01 en el protocolo | Decisión del director («lo seguro»). Con `solo_aviso=True` el componente ya no da FALLO en un tope: lo enclava en `tope` y sigue (aire según la regla de reposición, `descompresion_chaqueta` abierta, `agua_chaqueta` y lenta cerradas). `ProtocoloFallo._registrar_tope` lo registra una vez (log y línea de ticket, sin segundo fallo, sin escalar) y la sub-etapa sigue en `enfriamiento`: sale por carga enfriada solo con el Principal en o bajo `temp_max_apertura` (la del programa, `_temp_max_sellado`), o por el sellado D8-2.10 si el Principal falta. Un tope (a) con la cámara en o bajo atm + `rango_presion_atm` sella (D8-2.10) en lugar de ventear, y tras el sellado solo la lenta (`solo_lenta`). El protocolo fuerza agua y lenta cerradas tras el tope aunque el componente se recree. |
| M1, falsos CIC-24/25 | El aire repone mientras `p < max(presion_camara_enfriamiento, P_min + HISTERESIS_REPOSICION_AIRE_KPA)` (2 kPa), acotado por `presion_max_reposicion` = alivio de cámara − 10 kPa (`limites_equipo`, mismo margen que el corte de chaqueta); sin ese dato, objetivo + 30. Sin P_min calculable, solo el objetivo. |
| M2, equipos sin `pres_chaqueta` o `agua_chaqueta` | NO implementado. Hay un patrón (`installation/profile.modo_vapor`/`vacio_instalado` con `io_enabled`), pero rechazar o avisar al guardar/iniciar exige código de error nuevo, textos es/en, mapeo en `sesion_backend`/`parametros_ciclo_controller`, chequeo en `rutas/programas.py` y en `/cycle/start`, y decidir qué pasa con los programas de fábrica y los instalados (Líquidos trae modo 4). Queda como DECISIÓN SIN CONFIRMAR (15). |
| M3, ID duplicado | HAZ-LIQ-01..03 de la tanda → HAZ-T32-01..03 en el registro, la matriz (REQ-82..85), la hoja de banco (bloque T32), CLAUDE.md y este informe. REQ-82 y HAZ-T32-01 describen el tope del protocolo. |
| Atmosférica por defecto | `descompresion.presion_atm_configurada(config)`: solo con `presion_admosferica` y `rango_presion_atm` válidos (como `_referencia_atm_configurada`); si no, None y (b) no se cumple. Lo usan la fase y el protocolo. Reemplaza la decisión 7. |
| B1, LIQ-03 en la fase | El cambio lenta → rápida exige trama AI vigente (`vigencia_ai.leer`) y presión > 0. |
| B4, CIC-25 tras el sellado | `_cerrar_todo_sellado` descarta el componente y resuelve CIC-25 (también en el debounce del Principal). |
| B2, B3, B5 | Sin cambio de código; decisiones 16 a 18. |

Pruebas nuevas o ajustadas: `test_t32_enfriamiento_contrapresion.py` (tope en `solo_aviso`, M1), `test_t32_integracion_protocolo.py` (tope con contrapresión en modos 4 y 5, carga bajo temperatura de enfriamiento pero sobre `temp_max_apertura`, sellado sin Principal, sellado por tope (a) sin contrapresión, CIC-25 al sellar, (b) sin atmosférica), `test_t32_integracion_descompresion.py` ((b) sin atmosférica, LIQ-03 con AI vencida y p = 0, M1 con el Principal 1 °C sobre T_est).

## DECISIÓN SIN CONFIRMAR (lista completa)
1. `timeout_presurizacion_enfriamiento` y CIC-23.
2. Los 10 s y 60 s de LIQ-02 (`TIEMPO_AVISO_CONTRAPRESION_S`, `TIEMPO_FALLO_CONTRAPRESION_S`) hasta el banco.
3. Dentro del protocolo de fallo un tope de LIQ-01 no da segundo fallo: log y una línea de ticket. Revisado (hallazgo 1, decisión del director): no ventea con la carga caliente; mantiene la contrapresión (aire según la presión, chaqueta abierta) con agua de chaqueta y lenta cerradas, sin escalar, hasta carga enfriada con el Principal en o bajo `temp_max_apertura`; sin Principal, sellado D8-2.10. Sin agua de chaqueta la carga enfría lento.
3b. Tope (a) «sin contrapresión que mantener» = presión de cámara en o bajo atm + `rango_presion_atm` en el tick del tope (se evalúa solo entonces); en ese caso, sellado D8-2.10 y después solo la lenta. El texto de bloqueo y el log de `_iniciar_sellado` hablan de «Principal sin lectura» aunque la causa sea el tope (no se cambió el texto).
4. En LIQ-02 dentro del protocolo solo hay aviso.
5. Con LIQ-03 activo en la fase, si la presión llega al fin de la despresurización antes de `presion_cambio`, la fase termina igual.
6. Hasta 5 líneas de ticket por aparición de CIC-25.
7. ~~Presión atmosférica 101,3 kPa por defecto~~ Revisado: (b) solo se cumple con la presión atmosférica y su brecha configuradas; sin ellas todo ciclo 4/5 termina en CIC-22 (falla cerrada). El resto de la fase sigue usando 101,3/20 por defecto.
8. Tras `reanudar()` el protocolo crea un componente nuevo: (a), (b) y topes desde cero.
9. La regla de coherencia de LIQ-03 rige para cualquier carga y modo.
10. Los retiros de la migración se auditan con causa «migracion_parametro_nuevo».
11. El JSON del modo 5 trae `presion_cambio` con min 0 / max 500, pero rige 1–400.
12. `presion_cambio` siempre visible en la UI (descripción «Solo con … activa»); no verificado en pantalla real.
13. En un FALLO del componente todas las salidas quedan en False.
14. El suministro `aire_comprimido` no se vigila durante CICLO ni el protocolo (solo SUM-05 en PREPARACION/PREPARADO); se detecta indirectamente por CIC-23/24/25.
15. (M2) Equipos sin `pres_chaqueta` o sin `agua_chaqueta` en `io_enabled`: (b) no se cumple nunca y todo ciclo líquido modo 4/5 termina en CIC-22. No se rechaza ni avisa al guardar o iniciar; pendiente de decisión de Cristian (rechazo con código propio, aviso, o variante sin chaqueta).
16. (B2) Los relojes del componente (topes de LIQ-01 y conteo de LIQ-02) siguen corriendo durante una pausa por desconexión del módulo E/S dentro de CICLO (monotonic; las salidas no se reafirman en la pausa).
17. (B3) `ProtocoloFallo.reanudar()` crea un componente nuevo: (a), (b), topes y conteo de LIQ-02 desde cero (el tope ya registrado en el protocolo se conserva).
18. (B5) El aire comprimido se reafirma (ON) cada 3 s mientras corresponde, sin ciclo ON/OFF propio.
19. (M1) `HISTERESIS_REPOSICION_AIRE_KPA` = 2 kPa y el tope de reposición alivio de cámara − 10 kPa (sin dato, objetivo + 30) hasta el banco.

## No se compiló
Para compilar: `python tools/entrega/compilar_entrega.py` desde `dev` limpio.
