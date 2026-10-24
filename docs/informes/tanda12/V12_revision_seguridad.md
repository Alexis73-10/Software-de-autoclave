# V12 — Revisión de seguridad (tanda 12)

Revisor único `safety-reviewer` de la tanda, el 24-oct, después de unir J12, P12 y E12. Alcance: `git diff dev...tanda-12 -- src`, con 24 archivos y 2538 líneas de diff.

**Resultado: no hay hallazgos BLOQUEANTES.** Ninguna ruta deja el vapor sin techo ni una salida encendida en FALLO. Hay 2 hallazgos IMPORTANTES y 7 MENORES. La sesión principal corrigió en `tanda-12` los que afectan la conformidad del ciclo y eran baratos de corregir, cada uno con su prueba. Commit `41920a5`.

## Hallazgos y qué se hizo

| Id | Severidad | Hallazgo | Estado |
|---|---|---|---|
| SAF-01 | IMPORTANTE | `esterilizacion.py`: el fin de la exposición no esperaba a una falla del Principal que estuviera en conteo (debounce de 5 s sin confirmar). Si la temperatura bajaba o aparecía aire en los últimos 4,9 s, el ciclo terminaba en COMPLETADO. C-07.2 ensanchó esta ventana, que antes eran 3 lecturas. | **Corregido.** No completa mientras `_falla_desde` tenga alguna clave: espera a que la falla se confirme (FALLO) o se despeje. Pruebas en `test_t12_v12_correcciones_esterilizacion.py`: temperatura baja, aire, y falla que se despeja. |
| SAF-02 | IMPORTANTE | La marca NO CONFORME solo llega al ticket y a `avisos_ticket` del registro. El resultado sigue siendo COMPLETADO y ninguna pantalla ni `/status` la muestra. Con la impresora desconectada, el operador confirma un ciclo que la pantalla presenta como exitoso, y la única señal es SEN-11 (no bloqueante). | **No corregido.** Cumple la letra de C-13.7b ("ticket y registro"), y mostrarlo en pantalla es un cambio de interfaz y de flujo de confirmación. Queda como PREGUNTA PARA CRISTIAN (P-V12-1). |
| SAF-03 | MENOR | Con el Principal o la presión sin lectura (defensa propia de C-10.2), la fase devolvía EN_CURSO sin tocar `vapor_camara`. Hoy esa ruta no se alcanza, porque CicloState §4 falla antes. | **Corregido.** En esa rama se apaga `vapor_camara`. Con prueba. |
| SAF-04 | MENOR | A 134 °C con brecha 1.0, la salida de RECUPERACION (135,3 °C) queda por encima de Tsat(P_control_max), que es ≈135,0 °C. El control queda en todo o nada a flujo pleno entre el techo − 2 kPa y el techo. El techo se respeta. | Sin cambio de código: es la DSC de E12. Va a la PREGUNTA P-E12-1. |
| SAF-05 | MENOR | Desde la última lectura válida hasta el primer tick sin lectura hay como máximo un tick, y ese tramo se acredita como exposición. | Sin cambio: como máximo un tick. Pendiente. |
| SAF-06 | MENOR | `no_conforme` se deducía de la lista de avisos. Si el `append` fallaba, la marca no quedaba y la apertura automática volvía a quedar habilitada. | **Corregido.** CicloState tiene la bandera propia `_no_conforme`, que se pone antes del ticket y de la alarma y se limpia en `reset()`. Prueba en `test_t12_v12_no_conforme_bandera.py`. |
| SAF-07 | MENOR | Migración correctiva: (a) un reintento de `abrir_base_datos` duplicaba las filas de auditoría y pisaba el `.bak` con el archivo ya migrado; (b) la lista nunca se vaciaba; (c) se avisaban y se reescribían programas dañados. | **Corregido.** La lista del programa se vacía cuando la auditoría sale bien, y los programas `danado` se omiten. Prueba en `test_t12_v12_migracion_reintento.py`. |
| SAF-08 | MENOR | En CALENTAMIENTO, una Referencia que lee 0 (sin señal según SEN-01) se tomaba como lectura y bloqueaba la ventana. | **Corregido.** 0 y los valores no finitos cuentan como "sin lectura", con el mismo criterio que ESTERILIZACION y CicloState. Prueba en `test_t12_v12_ventana_referencia_en_cero.py`. |
| SAF-09 | MENOR | `_mantener_chaqueta` no recorta el límite alto contra el alivio en ejecución; solo lo valida al guardar y al cargar. `_registrar_consigna_chaqueta()` corre dentro de `reset()` sin `try`. | Sin cambio: no hay ningún valor válido que lo provoque. Pendiente (defensa en profundidad). |

## Preguntas del revisor (van al índice)
1. Una Referencia con excursión ya confirmada que pierde la lectura sigue deteniendo la exposición hasta CIC-14. Es el comportamiento conservador. ¿Se confirma?
2. Sin F0 no hay límite total, así que las excursiones repetidas pueden reiniciar la exposición sin fin. ¿Hace falta un tope? Es la misma pregunta que hace E12.
3. El debounce de "5 s continuos" deja que una señal que oscila alrededor del umbral (`brecha_error_temperatura` = 0,1 K frente al ruido de la PT100) nunca se confirme. ¿Se acepta o se usa un criterio acumulado?

## Resumen del foco (del revisor)
- Exposición sin datos o con una sonda fuera de banda: C-10.1, C-10.2 y C-13 están bien, salvo SAF-01 (corregido) y SAF-05.
- FALLO nuevos (CIC-12/13/14 y los de C-07): todos pasan por `_fallo()` o `_fallo_propio()`, que apagan el vapor y las descompresiones. CicloState registra la alarma y ejecuta el protocolo.
- Techo de presión: está en todos los tramos.
- Chaqueta: tiene la banda de ±10, sin dato → OFF, secado y enfriamiento 4/5 → OFF, SUM-06, y el rechazo con consigna + 10 ≥ 385.
- Migración: un programa inválido queda dañado sin romper el arranque.
- Referencia sin lectura: marca el ciclo NO CONFORME y no hay apertura automática. Con el Principal o la presión sin lectura, el ciclo sigue fallando como antes.
- Todos los temporizadores nuevos usan `time.monotonic()`.

## Pruebas
Pruebas `test_t12_*` más las de las fases y los ensayos de simulador: **600 passed, 6 skipped** (30 s, `-n 6`, `autoclave.__file__` en el repo principal, `tanda-12` en 41920a5). La suite completa corre en la integración final.
