# Anomalías residuales conocidas — 1.0.0-alpha.2

NTC-IEC 62304 §5.8.2 y §5.8.3. Fecha: 26-oct-2026. Base: `dev` después de la tanda 16 (pendientes de la tanda 14 + control de vapor por chaqueta VCH + PRG-01 + DEU-01). Parte de `anomalias_conocidas_1.0.0-alpha.1.md`.

**Uso previsto de esta versión:** igual que la alpha.1. Equipo de pruebas de laboratorio (puertas manuales), en verificación de banco y validación del proceso. **No se libera carga para uso clínico** con esta versión.

Ninguna de estas anomalías anula las protecciones independientes del software: el enclavamiento mecánico de la puerta por presión (D-02), las válvulas de alivio mecánicas de cámara y chaqueta, y el paro de emergencia por hardware.

## Corregidas en esta versión (tanda 16)

| ID | Anomalía de la alpha.1 | Corrección |
|---|---|---|
| AN-01 | SAF-04: a 134 °C con `presion_add_esterilizacion` = 9 no se salía de RECUPERACION. | P1: regla de coherencia al guardar y cargar (mínimo en el mensaje); programas de fábrica y de usuario de 134 °C con 15 kPa. |
| AN-02 | Programas de usuario con `brecha_segura_temperatura` = 0,3 K. | P2: migración 0,3 → 1,0 con auditoría, SIS-06 y `.bak`; sube `presion_add_esterilizacion` al mínimo de P1 si hace falta, con salvaguarda del alivio. |
| AN-03 | Ventana de CALENTAMIENTO con `T_ref ≥ T_obj`. | P3: `T_ref ≥ T_obj − brecha_error_temperatura`, igual que ESTERILIZACION. |
| AN-04 | NO CONFORME solo en el ticket. | P4: franja roja en la pantalla final, reconocimiento explícito auditado antes de CONFIRMAR, «NO CONFORME» en historial, ticket, PDF y correo. |
| AN-05 | Sin tope de reinicios de la exposición. | P5: `max_reinicios_exposicion` (defecto 3); la siguiente excursión confirmada falla con CIC-17. |
| AN-06 | Debounce de 5 s continuos. | P6: `DebounceAcumulado`, 5 s acumulados en una ventana de 10 s (fallas, C-03 y excursiones). |
| AN-07 | Lecturas fuera del rango físico. | P7: temperatura fuera de 0–200 °C y presión fuera de −10–450 kPa se publican sin lectura, con log del valor crudo. |
| AN-08 | SAF-05 y SAF-09. | P8: el tramo sin lectura se descuenta desde la última lectura válida; corte único de chaqueta (`presion_max_chaqueta_control`, 375 kPa abs). |
| AN-10 | PRG-01. | Roles de sensor validados contra las sondas activas del perfil, al asignar y al iniciar el ciclo. |
| AN-11 | DEU-01: límites de presión como constantes. | Fondo de escala, suministro y alivios en Parámetros del equipo (submenú Chaqueta), con auditoría y regla de coherencia. |

## Vigentes

| ID | Anomalía | Efecto / riesgo | Mitigación en esta versión | Se corrige en |
|---|---|---|---|---|
| VCH-01 | **ALTA.** Los parámetros de CALENTAMIENTO y ESTERILIZACION (intervalos, factores, tasas, rangos) se ajustaron para `vapor_camara`. Con la chaqueta como válvula de control (equipos de piso) hay más retardo y más riesgo de sobrepaso. | Sobrepaso de temperatura o presión, aislamientos frecuentes (CIC-15/16). | **Antes de liberar, reajustarlos en el banco con la chaqueta.** Aislamiento por sobrepresión, fallas de la fase y alivio mecánico. | Banco (hoja de pruebas, sección VCH) |
| VCH-02 | Golpe inicial de vapor al abrir `vapor_camara` después del prevacío (D5, aceptado). | Pico de presión al inicio del calentamiento. | Aislamiento VCH-AIS y fallas de la fase. Verificar en el banco que no dispare sobrepresión ni CIC-12/13. | Banco |
| AN-09 | Líquidos: implementación provisional de la tanda 11; C-11/C-12 sin implementar. | Igual que en la alpha.1. | Igual que en la alpha.1. | Tanda posterior |
| AN-13 | Prueba de humo fuera del script de entrega. | Igual que en la alpha.1. | Prueba de humo manual (§ siguiente). | Pendiente |
| AN-14 | DECISIONES SIN CONFIRMAR de P1 (margen 0,3 K e histéresis 0,3 K), P3 (`brecha_error_temperatura` = 0,1) y P6 (5 s de 10 s), aplicadas sin los datos del banco (D-14.1, D-14.3, D-14.6). | Puede haber falsos FALLO o una confirmación más lenta que la deseada. | Valores configurables; registrar en el banco la temperatura real con la presión en el techo, la diferencia Principal–Referencia y la oscilación pico a pico. | Banco |
| AN-15 | Los límites de presión que se cambian en Parámetros del equipo se aplican a los programas en la carga y al cambiar el límite, pero la migración P2 del arranque se evalúa con los valores de fábrica, antes de leer los del sitio (V16-s4-02). | En un sitio con un alivio distinto de 385 kPa, un programa puede quedar dañado tras migrarse en memoria, o válido de más hasta revalidar. | Esta versión solo se instala en el equipo de pruebas en Bogotá, con los límites de fábrica. | Tanda posterior |
| AN-16 | El fondo de escala configurable (100–1000 kPa) no se ata al rango real del transductor (0–400 kPa) ni a la plausibilidad P7 (450 kPa) (V16-s4-03, s2-02). | Con un fondo y un alivio por encima de 400, el corte de chaqueta podría quedar por encima de lo que el transductor mide. | No cambiar los límites de fábrica en el equipo de pruebas. | Decisión de Cristian |
| AN-17 | SIS-06 dice «kPa» y «sobre el máximo» también para la migración de `brecha_segura_temperatura` (°C) de P2. | Texto del aviso impreciso. | El registro de auditoría lleva el parámetro, el valor anterior y el nuevo. | Tanda posterior |
| AN-18 | El reconocimiento de carga NO CONFORME no exige sesión (se audita sin usuario si no la hay; V16-s5-01). | Trazabilidad incompleta del reconocimiento. | Queda en la bitácora con el operador del ciclo en el detalle. | Decisión de Cristian |
| AN-19 | El corte de chaqueta y CIC-18 no tienen histéresis (V16-s3-05). | Con la chaqueta oscilando en 375 kPa, la válvula y el aviso conmutan en ticks alternos. | Suministro regulado a 40 psig (no debería llegar al corte, VCH-04). | Tanda posterior |

## Prueba de humo en el equipo (después de instalar la alpha.2)
1. El Setup actualiza sobre la alpha.1 y conserva el perfil de instalación, la calibración, los usuarios y la base de datos.
2. Información del sistema, el ticket de arranque y la primera línea de los logs muestran `1.0.0-alpha.2 (<commit>)`.
3. Login, Preciclo, modo prueba de E/S, Parámetros del ciclo (`histeresis_cierre_camara`, `max_reinicios_exposicion`) y del equipo (submenú Chaqueta: corte, aislamientos y límites de presión), historial, exportar respaldo y apagar equipo.
4. Las lecturas de los sensores coinciden con las de la alpha.1.
5. Un ciclo en seco termina con la versión en el ticket y en el historial; el log de CALENTAMIENTO indica el modo de vapor (chaqueta en el equipo de piso).
6. Los programas de usuario cargan sin quedar dañados; si se migraron, aparece SIS-06 y hay `.bak`.
