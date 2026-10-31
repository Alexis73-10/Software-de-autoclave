# Decisiones — Tanda 19: enlace Modbus TCP con los módulos M31-U (27-oct)

Fuente de verdad de la tanda: este archivo y `docs/mis_plans/planeacion_enlace_modbus.md` (MOD-01 a MOD-17), que se leen completos. Si chocan, prevalece este archivo.

## Decisiones de Cristian (27-oct, no reabrir)

1. **Migrar ya a Modbus TCP** con los módulos Ebyte M31-U. No se harán pruebas de banco con la ESP32: la validación es con Modbus.
2. **El enlace serial (ESP32) se conserva como alternativa**, seleccionable por configuración (MOD-01). Su retiro es una tanda posterior.
3. **Sondeo cada 100 ms** de todas las entradas. Las salidas se escriben solo cuando cambian. El tiempo de desconexión del módulo es **1,0 s** y el software lo verifica en cada conexión. Queda como DECISIÓN SIN CONFIRMAR hasta la prueba de banco M-1.
4. **El buzzer es de 24 VDC y pasa a DO 25** (MOD-05), para no compartir común con las cargas de otra tensión del grupo 17–24.
5. **Todas las sondas de temperatura, incluida la Principal, van al módulo de PT100.**
6. **Los transmisores de presión son de 0–4 bar abs (4–20 mA)**, es decir, 0–400 kPa abs.
7. **Orden en el riel:** principal (16 AI) → 16 DI → 16 DO n.º 1 (DO 01–16) → 16 DO n.º 2 (DO 17–32) → 6 PT100.
8. **La asignación de fábrica** conserva los números actuales:
   - DI 01–14;
   - DO 01–23 (la DO 13 libre) y el buzzer en DO 25;
   - temperatura en los canales 1, 2, 3 y 5 del módulo de PT100;
   - presión en AI 1–4 del principal (puertos 09–12).

## Precondición

Si la tanda 18 ya está unida a `dev`, la rama sale de `dev`. Si no, sale de `tanda-18` y la unión a `dev` de K lleva las dos. Urgencia de Cristian: que el software reconozca los módulos hoy mismo.

## Riesgos que se registran (MOD-16)

MED-01 (exactitud de las PT100), MED-02 (exactitud de las AI) y MED-03 (configuración en el módulo) van al registro de riesgos y a las anomalías conocidas. No bloquean esta tanda. Se cierran con las mediciones M-4 del banco y la decisión de Cristian.
