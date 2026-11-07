# Tanda 29: informe (6-nov-2026)

Rama `tanda29` desde `dev` (9775fc68). Entrega NO compilada.

## Resultado por paso
| Paso | Resultado |
|---|---|
| T29-01 | No se reproduce en el backend. Hipótesis descartadas: `set_active_cycle` no copia el programa; `reset()` copia el mismo objeto que edita `PATCH /cycle/parameter`; `PrevacioFase` lee los parámetros en cada tick; `load_all_cycles` solo al arrancar; Preciclo no guarda copia; sin carrera con el inicio. Causa probable en la pantalla: Parámetros del ciclo abría siempre en `programas[0]` (Bowie & Dick, que también tiene pulsos B). Cerrada con T29-06. Pruebas: `tests/test_t29_01_parametros_aplican_al_ciclo.py` (7). Riesgo visto y no corregido: con el teclado numérico, si lo último tecleado queda fuera de rango se conserva el último valor intermedio válido (teclear «12» con máximo 10 guarda 1). |
| T29-02 | PRE-01..06 fuera de CICLO; PRE-03/04 con `tiempo_estable`. Inventario en `T29-02_inventario.md`. |
| T29-03 | `descompresion.presion_fin_descompresion`. |
| T29-04 | Rige la temperatura del programa (techo 120 °C). |
| T29-05 | Sólidos solo modos 0 a 3. |
| T29-06 | Abre en el programa seleccionado; nombre en todas las vistas. |
| T29-07 | Línea «F0 activo · objetivo N min». |
| T29-08 | Aire atmosférico abierto fuera de ciclo. |

## DECISIÓN SIN CONFIRMAR
1. T29-03: defecto 10 kPa, rango 2–20; sin parámetro válido rige el criterio anterior; la migración no emite SIS-06 (copia de A12; el encargo lo pedía, pero A12 tampoco lo emite y añadirlo exige tocar `backend/context.py`).
2. T29-05: el arrastre a sólido con defecto 4/5 pasa al modo 1; la migración no actúa sobre la copia del programa ni sobre la instantánea de un ciclo interrumpido; el JSON de usuario de Bowie & Dick se corrigió a mano (4 → 1).
3. T29-04: en CICLO `temp_max_tras_ciclo` devuelve el valor del programa; techo de 120 °C aplicado en `camara_segura`.
4. T29-08: en PREPARADO exige trama AI vigente; se cierra el aire al entrar a CICLO; al pasar de sobrepresión a vacío se resuelve el aviso contrario.
5. T29-02: PRE-04 tras un ciclo de líquidos en modo 4 sigue saliendo a los ~5 s porque el venteo por la lenta dura más. Pendiente de Cristian: subir `tiempo_estable`, espera propia tras COMPLETADO, o aceptarlo. PRE-01, PRE-02 y PRE-06 de PREPARADO conservan el temporizador compartido.
6. T29-07: la línea de F0 mide 27 caracteres y el ticket 24 columnas; se dejó con el texto pedido.

## Pruebas
Nuevas: `test_t29_descompresion_fin_modo_solido.py`, `test_t29_preparacion_aire_avisos_apertura.py` (39), `test_t29_01_...`, `test_t29_06_...`, `test_t29_07_...`. Ajustadas (asumían el comportamiento anterior): `test_v8a_tipo_carga_modos`, `test_t10_endurecimiento`, `test_ciclo_drenaje`, `test_preparacion_presion_camara`, `test_q1_r1p2_preparado_un_lazo_por_tick`, `test_t26b_respuestas_cristian`, `test_ciclo_apertura_automatica`. Resultado de la suite completa: ver `CERRADO.txt`.
