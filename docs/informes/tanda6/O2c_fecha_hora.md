# O2c — Fecha y hora (SOLO LECTURA, decisión 1.10)

## Qué se hizo
- `GET /system/time` (lectura libre): hora local del PC con su desfase, zona (`UTC-05:00 (nombre de Windows)`), fecha de instalación del perfil (`created_at`) y `reloj_anterior_instalacion` (mismo criterio que `clock_guard`, M1-01). `ajuste_habilitado: false`. No existe ningún endpoint de escritura (405).
- Sección `fecha_hora` de OPCIONES para admin, técnico e ingeniero, sin aviso de "edición bloqueada" (no hay nada que editar), también con ciclo en curso.
- `OpcionesFechaHora.qml` (mockup 7 con el cambio aprobado): hora grande que avanza cada segundo con el reloj del PC, fecha larga en el idioma vigente, zona, fecha ISO, fecha de instalación, origen ("Reloj del PC (Windows)"), explicación y aviso rojo si el reloj es anterior a la instalación. Sin campos ni botón Aplicar.
- Textos `fecha_hora.*` y nombres de sección `opciones.secciones.{fecha_hora,info_sistema,bitacora}` (es/en).

## Mecanismo en Windows (para que Cristian lo verifique; NO implementado)
Cambiar la hora requiere el privilegio `SeSystemtimePrivilege` ("Cambiar la hora del sistema"), que por defecto solo tienen Administradores y LOCAL SERVICE; la zona, `SeTimeZonePrivilege`. Habilitarlo sería: conceder ese privilegio a la cuenta local del quiosco por directiva local (secpol.msc › Asignación de derechos de usuario) o un servicio auxiliar con privilegios, y llamar `SetLocalTime`/`Set-Date`. Queda fuera por la decisión 1.10.

## Auditoría
Sin ajuste no hay evento de cambio de hora. El aviso M1-01 se ve en pantalla; el arranque ya lo maneja `clock_guard`.

## Pruebas
`tests/test_o2c_fecha_hora.py` (9): zona y aviso con instalación futura/pasada, sin perfil, endpoint sin escritura, visibilidad por rol, controlador y pantalla offscreen (admin sin aviso, técnico con aviso). Suite completa: 4820 passed / 2 skipped / 3 xfailed.

## Capturas
`O2c_1_fecha_hora_admin.png`, `O2c_2_aviso_tecnico.png`.
