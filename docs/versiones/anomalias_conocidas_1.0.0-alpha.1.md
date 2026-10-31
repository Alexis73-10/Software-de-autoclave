# Anomalías residuales conocidas — 1.0.0-alpha.1

NTC-IEC 62304 §5.8.2 y §5.8.3. Fecha: 25-oct-2026. Base: `dev` después de la etapa VER (tanda 15 + versionado).

**Uso previsto de esta versión:** equipo de pruebas de laboratorio (puertas manuales), en verificación de banco y validación del proceso. **No se libera carga para uso clínico** con esta versión.

Ninguna de estas anomalías anula las protecciones independientes del software: el enclavamiento mecánico de la puerta por presión (D-02), las válvulas de alivio mecánicas de cámara y chaqueta, y el paro de emergencia por hardware.

| ID | Anomalía | Efecto / riesgo | Mitigación en esta versión | Se corrige en |
|---|---|---|---|---|
| AN-01 | SAF-04: a 134 °C con `presion_add_esterilizacion` = 9, `Tsat(P_control_max)` ≈ 135,0 °C queda por debajo del umbral de salida de RECUPERACION (135,3 °C): ESTERILIZACION no pasa a PWM_ACTIVO. | El vapor trabaja todo/nada contra el techo de presión. No es inseguro: el techo y las fallas se respetan. | Observarlo en el banco (temperatura real con la presión en el techo). | Tanda 14, P1 |
| AN-02 | Los programas de usuario conservan `brecha_segura_temperatura` = 0,3 K, menor que la incertidumbre de la PT100 (±0,4 K). | RECUPERACION puede activarse tarde. | Los programas de fábrica ya usan 1,0 K. | Tanda 14, P2 |
| AN-03 | La ventana de estabilidad de CALENTAMIENTO exige `T_ref ≥ T_obj` a cada Referencia; ESTERILIZACION admite `T_est − brecha_error_temperatura`. | Una Referencia 0,1–0,2 K más fría que el Principal puede fallar el ciclo con `cal_no_sostuvo`. | Ninguna (fallo hacia el lado seguro). | Tanda 14, P3 |
| AN-04 | SAF-02: la marca NO CONFORME (Referencia sin lectura) va al ticket y al registro, pero la pantalla final muestra COMPLETADO. | Con la impresora desconectada, el operador podría no enterarse. | Revisar el ticket o el historial antes de dar por buena una carga. | Tanda 14, P4 |
| AN-05 | No hay tope de reinicios de la exposición por excursiones repetidas de una Referencia (sin F0). | El ciclo puede alargarse sin límite; queda acotado por CIC-14 en cada excursión. | Supervisión del operador. | Tanda 14, P5 |
| AN-06 | El debounce de 5 s continuos se reinicia con cada lectura dentro de rango. | Una señal que oscila alrededor del umbral (ruido de la PT100 frente a 0,1 K) puede no confirmar la falla. | Registrar en el banco la oscilación pico a pico. | Tanda 14, P6 |
| AN-07 | Una lectura fuera del rango físico (temperatura fuera de 0–200 °C) hace lanzar `t_saturacion_c` en cada tick. | El equipo termina en estado seguro (apagado tras 3 excepciones y watchdog), pero el motivo solo queda en el log. | Revisar `backend.log` ante un paro sin motivo en pantalla. | Tanda 14, P7 |
| AN-08 | SAF-05: al perder la lectura no se descuenta de la exposición el intervalo desde la última lectura válida. SAF-09: `vapor_chaqueta` no tiene corte independiente en `alivio − 10 kPa`. | Margen menor del deseado (defensa en profundidad). | Válvula de alivio mecánica de chaqueta. | Tanda 14, P8 |
| AN-09 | Programa Líquidos: implementación de la tanda 11 con valores PROVISIONALES (HAZ-LIQ-01); el control de dos lazos (C-11/C-12) no está implementado. | Despresurización o apertura con el líquido sobre su punto de ebullición si la sonda no está dentro del líquido. | Sonda Principal dentro del recipiente de referencia; contrapresión, rápida solo bajo 80 °C, sin apertura automática. | Tanda posterior (preguntas §10 de `planeacion_liquidos_dos_lazos.md`) |
| AN-10 | PRG-01: no se valida que cada rol de sensor corresponda a una sonda cableada en el perfil. | Un rol asignado a una sonda inexistente se detecta solo como sensor ausente al iniciar. | Solo técnico e ingeniero asignan roles; auditoría `ROLES_SENSOR`. | Pendiente |
| AN-11 | DEU-01: los límites de presión (fondo de escala 400, suministro 350, alivio 385 kPa abs) son constantes en código, calculados para Bogotá y para este equipo. | En otro sitio u otro equipo los rechazos y advertencias podrían ser incorrectos. | Esta versión solo se instala en el equipo de pruebas en Bogotá. | Pendiente |
| AN-12 | Las compilaciones B a I no registraban la versión del software (`?`, `v?`, `—`, `0`). | Los registros de ciclo previos no identifican el software. Los respaldos de la I no se pueden restaurar en esta versión (`version_mayor` 0 ≠ 1). | Corregido desde esta versión. Cristian confirmó (25-oct) que no hay respaldos de la I que conservar. | — (histórico) |
| AN-13 | La prueba de humo con capturas no forma parte del script de entrega (VER D9); `AutoclaveBackend.exe` y `AutoclaveSettings.exe` no se ejecutaron en la verificación posterior a la tanda 15. | Un defecto de empaquetado podría pasar a la entrega. | Prueba de humo manual en el equipo después de instalar (§ siguiente). | Pendiente |

## Prueba de humo en el equipo (después de instalar la alpha.1)
1. El Setup actualiza sobre la I y conserva el perfil de instalación, la calibración, los usuarios y la base de datos.
2. Información del sistema, el ticket de arranque y la primera línea de los logs muestran `1.0.0-alpha.1 (<commit>)`.
3. Login, Preciclo, modo prueba de E/S, Parámetros del ciclo y del equipo, historial, exportar respaldo y apagar equipo.
4. Las lecturas de los sensores coinciden con las de la I.
5. Un ciclo en seco termina con la versión en el ticket y en el historial.
