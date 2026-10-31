# B9b — Permisos por rol de las puertas en la ruta HTTP (S3e): DIFERIDO

El equipo de pruebas tiene 2 puertas manuales (sin actuador), así que no se implementa. Hoy: cada pantalla opera solo su puerta (`source_door`, 409 `puerta_ajena`), declarada por el cliente y sin sesión (S3e, D-S3e-1).

Contrato esperado para equipos con puertas automáticas (descrito en `tests/test_b9b_puertas_permisos_por_rol_diferido.py`, 3 pruebas `xfail(strict=True)` que fallan hoy por las razones correctas —409 en vez de 200; sin fila de auditoría con usuario— y una prueba verde que fija el comportamiento actual sin sesión):
- con sesión de técnico o ingeniero (rol de servicio) se puede operar la otra puerta;
- la orden queda en `audit_log` con el usuario;
- un operador con sesión sigue limitado a su puerta.

Al implementarlo, las `xfail strict` pasarán a XPASS y fallarán: quitar la marca. (Ver también la memoria del proyecto: el backend ignora hoy `source_door` para permisos por rol.)
