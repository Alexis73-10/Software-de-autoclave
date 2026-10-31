# I3 — i18n F4: salidas del backend, con unidades

## Hecho (ticket de ciclo)
- `ticket_formatter` arma el ticket en el **idioma** y las **unidades vigentes al generarlo** (`Presentacion`). En tiempo real se captura una vez al iniciar el ciclo; en la reimpresión, una vez por ticket. El backend registra el proveedor al arrancar (`context.registrar_presentacion_tickets`): idioma de `data/idioma.json`, unidades de `data/unidades.json` y P_atm válida.
- Español en °C y kPa: **idéntico a antes**, línea por línea.
- Inglés:
  - Rótulos traducidos, meses en inglés (JAN…DEC) y resultados traducidos (COMPLETED, CANCELLED, INTERRUPTED, EMERGENCY, FAILED…).
  - El motivo usa el título de la alarma en inglés, por su código. Un motivo en texto libre de ciclos antiguos se conserva tal cual.
- Unidades:
  - Temperatura en °C o °F (impresa como "C"/"F": el ticket es cp437).
  - Presión en kPa, bar o mbar absolutos, o en psig. Una lectura por debajo de la atmosférica se imprime en inHg con el sufijo "v".
  - Sin P_atm válida, en psi se imprime "-----", nunca un número inventado.
  - Una consigna que no se puede convertir se imprime como "---", nunca un valor en °C con símbolo F.
- **La cabecera indica las unidades usadas** cuando no son las de siempre, por ejemplo "Units: F, psig (v=inHg vacuum)" o "Unidades: C, bar abs".
- Todo el ticket se codifica en cp437 (lo verifica una prueba). Los textos en inglés no usan "°".
- Si el proveedor falla, el ticket sale en español, °C y kPa (nunca lanza).

## DECISIONES SIN CONFIRMAR
- **I3-1:** en psi, el ticket imprime el vacío como inHg con el sufijo "v" en la misma columna. Así ningún valor queda negativo y se mantiene una sola columna de ancho fijo.
- **I3-2:** el ticket en tiempo real usa la presentación vigente **al iniciar el ciclo**; un cambio de idioma durante el ciclo se ve desde el siguiente.

## PENDIENTE (no hecho en esta tanda)
- **PDF** (ciclo, resumen, consolidado) y **correo**: siguen en español, °C y kPa.
- **Ticket de resumen, de arranque y de conectividad**: sin cambios. Tampoco se hizo la separación de estado y rótulo del ticket de arranque (I18N-18).
- **Fechas según D-09** en PDF y correo.
- Verificación con la impresora simulada: se verificó la codificación cp437 del texto, no una impresión simulada completa.

## Pruebas
`tests/test_i3_ticket_idioma_unidades.py` (9).
