# B9 — registro de órdenes durante el paro (planta simulada)

## PREPARACION, puerta avanzada=True

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO22 OFF | — |
| 0.0 | SET DO11 OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO22 OFF | DO24 |
| 0.5 | SET DO11 OFF | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | SET DO22 OFF | DO24 |
| 1.0 | SET DO11 OFF | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO22 OFF | — |
| 1.5 | SET DO11 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | SET DO22 OFF | DO24 |
| 2.0 | SET DO11 OFF | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO22 OFF | — |
| 2.5 | SET DO11 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | SET DO22 OFF | DO24 |
| 3.0 | SET DO11 OFF | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO22 OFF | — |
| 3.5 | SET DO11 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | SET DO22 OFF | DO24 |
| 4.0 | SET DO11 OFF | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO22 OFF | — |
| 4.5 | SET DO11 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | SET DO22 OFF | DO24 |
| 5.0 | SET DO11 OFF | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO22 OFF | DO24 |
| 5.5 | SET DO11 OFF | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | SET DO22 OFF | — |
| 6.0 | SET DO11 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO22 OFF | DO24 |
| 6.5 | SET DO11 OFF | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | SET DO22 OFF | — |
| 7.0 | SET DO11 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO22 OFF | DO24 |
| 7.5 | SET DO11 OFF | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | SET DO22 OFF | — |
| 8.0 | SET DO11 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO22 OFF | DO24 |
| 8.5 | SET DO11 OFF | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | SET DO22 OFF | — |
| 9.0 | SET DO11 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO22 OFF | DO24 |
| 9.5 | SET DO11 OFF | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | SET DO22 OFF | DO24 |
| 10.0 | SET DO11 OFF | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO22 OFF | — |
| 10.5 | SET DO11 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | SET DO22 OFF | DO24 |
| 11.0 | SET DO11 OFF | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO22 OFF | — |
| 11.5 | SET DO11 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | SET DO22 OFF | DO24 |
| 12.0 | SET DO11 OFF | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO22 OFF | — |
| 12.5 | SET DO11 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | SET DO22 OFF | DO24 |
| 13.0 | SET DO11 OFF | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO22 OFF | — |
| 13.5 | SET DO11 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | SET DO22 OFF | DO24 |
| 14.0 | SET DO11 OFF | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO22 OFF | DO24 |
| 14.5 | SET DO11 OFF | DO24 |
| 14.5 | SET DO24 OFF | — |

## PREPARADO, puerta avanzada=True

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO22 OFF | — |
| 0.0 | SET DO11 OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO22 OFF | DO24 |
| 0.5 | SET DO11 OFF | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | SET DO22 OFF | DO24 |
| 1.0 | SET DO11 OFF | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO22 OFF | — |
| 1.5 | SET DO11 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | SET DO22 OFF | DO24 |
| 2.0 | SET DO11 OFF | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO22 OFF | — |
| 2.5 | SET DO11 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | SET DO22 OFF | DO24 |
| 3.0 | SET DO11 OFF | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO22 OFF | — |
| 3.5 | SET DO11 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | SET DO22 OFF | DO24 |
| 4.0 | SET DO11 OFF | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO22 OFF | — |
| 4.5 | SET DO11 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | SET DO22 OFF | DO24 |
| 5.0 | SET DO11 OFF | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO22 OFF | DO24 |
| 5.5 | SET DO11 OFF | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | SET DO22 OFF | — |
| 6.0 | SET DO11 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO22 OFF | DO24 |
| 6.5 | SET DO11 OFF | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | SET DO22 OFF | — |
| 7.0 | SET DO11 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO22 OFF | DO24 |
| 7.5 | SET DO11 OFF | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | SET DO22 OFF | — |
| 8.0 | SET DO11 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO22 OFF | DO24 |
| 8.5 | SET DO11 OFF | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | SET DO22 OFF | — |
| 9.0 | SET DO11 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO22 OFF | DO24 |
| 9.5 | SET DO11 OFF | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | SET DO22 OFF | DO24 |
| 10.0 | SET DO11 OFF | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO22 OFF | — |
| 10.5 | SET DO11 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | SET DO22 OFF | DO24 |
| 11.0 | SET DO11 OFF | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO22 OFF | — |
| 11.5 | SET DO11 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | SET DO22 OFF | DO24 |
| 12.0 | SET DO11 OFF | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO22 OFF | — |
| 12.5 | SET DO11 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | SET DO22 OFF | DO24 |
| 13.0 | SET DO11 OFF | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO22 OFF | — |
| 13.5 | SET DO11 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | SET DO22 OFF | DO24 |
| 14.0 | SET DO11 OFF | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO22 OFF | DO24 |
| 14.5 | SET DO11 OFF | DO24 |
| 14.5 | SET DO24 OFF | — |

## FALLA, puerta avanzada=True

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO22 OFF | — |
| 0.0 | SET DO11 OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO22 OFF | DO24 |
| 0.5 | SET DO11 OFF | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | SET DO22 OFF | DO24 |
| 1.0 | SET DO11 OFF | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO22 OFF | — |
| 1.5 | SET DO11 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | SET DO22 OFF | DO24 |
| 2.0 | SET DO11 OFF | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO22 OFF | — |
| 2.5 | SET DO11 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | SET DO22 OFF | DO24 |
| 3.0 | SET DO11 OFF | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO22 OFF | — |
| 3.5 | SET DO11 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | SET DO22 OFF | DO24 |
| 4.0 | SET DO11 OFF | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO22 OFF | — |
| 4.5 | SET DO11 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | SET DO22 OFF | DO24 |
| 5.0 | SET DO11 OFF | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO22 OFF | DO24 |
| 5.5 | SET DO11 OFF | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | SET DO22 OFF | — |
| 6.0 | SET DO11 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO22 OFF | DO24 |
| 6.5 | SET DO11 OFF | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | SET DO22 OFF | — |
| 7.0 | SET DO11 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO22 OFF | DO24 |
| 7.5 | SET DO11 OFF | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | SET DO22 OFF | — |
| 8.0 | SET DO11 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO22 OFF | DO24 |
| 8.5 | SET DO11 OFF | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | SET DO22 OFF | — |
| 9.0 | SET DO11 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO22 OFF | DO24 |
| 9.5 | SET DO11 OFF | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | SET DO22 OFF | DO24 |
| 10.0 | SET DO11 OFF | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO22 OFF | — |
| 10.5 | SET DO11 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | SET DO22 OFF | DO24 |
| 11.0 | SET DO11 OFF | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO22 OFF | — |
| 11.5 | SET DO11 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | SET DO22 OFF | DO24 |
| 12.0 | SET DO11 OFF | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO22 OFF | — |
| 12.5 | SET DO11 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | SET DO22 OFF | DO24 |
| 13.0 | SET DO11 OFF | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO22 OFF | — |
| 13.5 | SET DO11 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | SET DO22 OFF | DO24 |
| 14.0 | SET DO11 OFF | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO22 OFF | DO24 |
| 14.5 | SET DO11 OFF | DO24 |
| 14.5 | SET DO24 OFF | — |

## PREPARACION, puerta avanzada=False

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO24 OFF | — |

## PREPARADO, puerta avanzada=False

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO24 OFF | — |

## FALLA, puerta avanzada=False

| t desde el paro (s) | orden | pines encendidos tras la orden |
|---|---|---|
| 0.0 | SET DO3 ON | DO3 |
| 0.0 | SET DO6 ON | DO3, DO6 |
| 0.0 | SET DO17 ON | DO3, DO6, DO17 |
| 0.0 | SET DO14 ON | DO3, DO6, DO14, DO17 |
| 0.0 | --- PARO PULSADO --- | — |
| 0.0 | ALL_OFF | — |
| 0.0 | SET DO24 ON | DO24 |
| 0.5 | SET DO24 ON | DO24 |
| 1.0 | ALL_OFF | — |
| 1.0 | SET DO24 OFF | — |
| 1.5 | SET DO24 ON | DO24 |
| 2.0 | ALL_OFF | — |
| 2.0 | SET DO24 OFF | — |
| 2.5 | SET DO24 ON | DO24 |
| 3.0 | ALL_OFF | — |
| 3.0 | SET DO24 OFF | — |
| 3.5 | SET DO24 ON | DO24 |
| 4.0 | ALL_OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.0 | SET DO24 OFF | — |
| 4.5 | SET DO24 ON | DO24 |
| 5.0 | ALL_OFF | — |
| 5.0 | SET DO24 ON | DO24 |
| 5.5 | SET DO24 OFF | — |
| 6.0 | ALL_OFF | — |
| 6.0 | SET DO24 ON | DO24 |
| 6.5 | SET DO24 OFF | — |
| 7.0 | ALL_OFF | — |
| 7.0 | SET DO24 ON | DO24 |
| 7.5 | SET DO24 OFF | — |
| 8.0 | ALL_OFF | — |
| 8.0 | SET DO24 ON | DO24 |
| 8.5 | SET DO24 OFF | — |
| 8.5 | SET DO24 OFF | — |
| 9.0 | ALL_OFF | — |
| 9.0 | SET DO24 ON | DO24 |
| 9.5 | SET DO24 ON | DO24 |
| 10.0 | ALL_OFF | — |
| 10.0 | SET DO24 OFF | — |
| 10.5 | SET DO24 ON | DO24 |
| 11.0 | ALL_OFF | — |
| 11.0 | SET DO24 OFF | — |
| 11.5 | SET DO24 ON | DO24 |
| 12.0 | ALL_OFF | — |
| 12.0 | SET DO24 OFF | — |
| 12.5 | SET DO24 ON | DO24 |
| 13.0 | ALL_OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.0 | SET DO24 OFF | — |
| 13.5 | SET DO24 ON | DO24 |
| 14.0 | ALL_OFF | — |
| 14.0 | SET DO24 ON | DO24 |
| 14.5 | SET DO24 OFF | — |

