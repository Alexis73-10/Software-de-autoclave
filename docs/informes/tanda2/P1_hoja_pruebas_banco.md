# P1 — Hoja de pruebas de banco (E7) del equipo de pruebas

Instrucción: `instruccion_claude_code_tanda_2.md` §2 P1.

## Entregables

- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`: lectura y revisión.
- `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.html`: versión **imprimible**, con casillas para marcar, campos de valor observado y firma por prueba, y cabecera para equipo, commit y firmware.
- Fuente única: `docs/mis_plans/hoja_pruebas_banco/pruebas.py`. Generador: `generar.py`. Para cambiar una prueba, se edita la fuente y se regenera con `python docs/mis_plans/hoja_pruebas_banco/generar.py`, así las dos versiones no divergen.

**DECISIÓN SIN CONFIRMAR D-P1-1:** la versión imprimible es HTML (se imprime desde el navegador) y no `.xlsx`. `openpyxl` no está instalado y no se instalaron paquetes. Alternativa: instalar `openpyxl` y agregar una salida `.xlsx` al generador.

## Contenido (28 pruebas, 7 bloques)

| Bloque | Modo | Pruebas |
|---|---|---|
| A. Arranque, instalación, firmware | En seco | A-01 asistente con `generator`, A-02 ALL_OFF, A-03 firmware 1.0.0 (versión e ID solo en Información), A-04 DO1/DO2 nunca |
| B. Seguridad | En seco | B-01 paro NC (pulsar/soltar/confirmar), B-02 cable cortado = paro, B-03 NO ABRIR, B-04 puertas manuales, B-05 tarjeta desconectada (U4), B-06 apagar equipo |
| C. Comunicación, energía, BD | En seco | C-01 modo sin BD, C-02 alarmas de la tarjeta, C-03 corte de energía y arranque |
| D. Sensores, parámetros, pantallas | En seco | D-01 roles Principal/Referencias/No en uso, D-02 parámetros, D-03 calibración (S3a), D-04 navegación y legibilidad, D-05 cambio de programa (S2) |
| E. Ciclos de sólidos | En operación | E-01 Instrumental 134, E-02 Instrumental 121, E-03 SECADO con bomba y válvulas cerradas, E-04 corte por calidad de vapor, E-05 NO ABRIR en las dos pantallas |
| F. Fallas en ciclo | En operación | F-01 paro en ciclo, F-02 pérdida de comunicación, F-03 corte de energía, F-04 puerta abierta en ciclo = FALLO |
| G. Líquidos | En operación (al final) | G-01 con la sonda dentro del líquido (HAZ-LIQ-01), contrapresión hasta 80 °C antes de la rápida, aire residual sin prevacío |

**Cobertura de las 11 comprobaciones de `informe_tanda_2026-10-14.md` §5:**

| Comprobación | Pruebas |
|---|---|
| 1 | A-02, C-03, F-03 |
| 2 | B-01, B-03, E-05 |
| 3 | E-01, E-02 |
| 4 | G-01 |
| 5 | D-01 |
| 6 | C-01 |
| 7 | A-01 |
| 8 | B-06 |
| 9 | D-02 |
| 10 | C-02, F-02 |
| 11 | D-04 |

Incluye el **orden seguro de ejecución**: primero en seco; no se pasa a vapor sin aprobar el paro, NO ABRIR, las puertas y DO1/DO2; F-04 solo durante PREVACIO; Líquidos al final. También la **lista de registros que se deben conservar** para el expediente IEC 62304.

## Pendientes

- B-05 depende de U4 (en curso en otra sesión) y D-03 de S3a. Ajustar el resultado esperado si cambian.
- SECADO en simulador (S3f): el simulador reproduce un ciclo grabado y no modela la bomba ni las válvulas, así que la validación queda en el banco (E-03).
