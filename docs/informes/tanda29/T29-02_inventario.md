# T29-02: inventario de avisos durante el ciclo y hasta 5 min después

Herramienta: `tests/banco/t29_inventario_avisos.py` (planta simulada de
`tests/test_t11_programas_integracion.py`, valores provisionales; StateMachine
real; drenaje que sigue a la cámara; puertas cerradas con DI vigentes; el
CICLO se confirma solo al terminar y se sigue 5 min en el estado siguiente).
Se registra cada activación nueva del `AlarmManager` (bandeja y campana usan
las activas; `alarmas_ciclo` y las observaciones del fin de ciclo toman las que
aparecen con la máquina en CICLO).

## Antes del cambio (HEAD 4f1d3f98)

| Programa | Durante CICLO (irían a `alarmas_ciclo`) | Tras el ciclo (≤ 5 min) |
|---|---|---|
| 2 Instrumental 134 (sólido, prevacío y secado) | PRE-06 ×5 (PRE_VACIO, CALENTAMIENTO) | ninguna |
| 4 Líquidos, modo 4 | PRE-06 ×9 (CALENTAMIENTO) | PRE-04 en PREPARADO en el primer tick (temporizador compartido de `generar_alarma_temporizada` viejo, sin reiniciar) |

`terminacion.observaciones`: solo lleva la observación de Referencia sin
lectura; ninguna PRE. Pero en un ciclo exitoso cualquier fila de
`alarmas_ciclo` lleva el panel a «Observaciones (N)» (`fin_de_ciclo.py`), y
por eso PRE-06 aparecía ahí.

Revisión de código (todas las `activar` que pueden correr en CICLO):
PRE-06 era la única PRE activada dentro de CICLO (`CicloState._mantener_drenaje`).
PRE-01..PRE-05 solo se activan en PREPARACION, PREPARADO y FALLA (esta vía
`nivelar_presion_camara`). Los demás avisos no bloqueantes de CICLO (SUM-06,
CIC-07, CIC-08, CIC-09, CIC-18, CIC-21, SEN-03, SEN-11) describen una falta
de suministro, un sensor o una desviación del proceso, no una condición
normal: no se tocan. No se encontró otro aviso «de cámara con presión o con
vacío» en CICLO; los vistos en el equipo serían PRE-03/PRE-04 tras el ciclo
(PREPARADO/PREPARACION/FALLA).

## Después del cambio

| Programa | Durante CICLO | Tras el ciclo (≤ 5 min) |
|---|---|---|
| 2 | ninguna | ninguna |
| 4 (modo 4) | ninguna | PRE-04 en PREPARADO a los ~5 s: la planta simulada ventea la carga líquida por la lenta muy despacio y la sobrepresión dura más que `tiempo_estable_alarma` (5 s) |

Pendiente de decisión: con carga líquida el venteo por la lenta tras un
COMPLETADO puede durar más de 5 s, así que PRE-04 seguirá apareciendo tras
esos ciclos mientras `tiempo_estable_alarma` sea 5 s. La planta tiene valores
provisionales; confirmar en banco cuánto dura el igualado real.
