# O2d — Información del sistema (solo lectura, todos)

## Qué se hizo
- `GET /system/info` (lectura libre): `equipo` (modelo, serie, instalación, fuente de vapor del perfil), `software` (versión del paquete, firmware e ID de la tarjeta del último handshake), `uso` (ciclos = mayor número de ciclo, resumen de mantenimiento) y `configuracion` (idioma, unidades, estado de la impresora —`deshabilitada` o el de Windows—, red `conectada`/`sin_red` según haya una IPv4 distinta del loopback). Cada dato se lee por separado: uno que falla queda en `null` ("—") sin afectar a los demás.
- Sección `info_sistema` para admin, técnico e ingeniero, sin aviso de edición bloqueada.
- `OpcionesInfoSistema.qml` (mockup 8): cuatro grupos de clave–valor; impresora y red como chips (verde si lista/conectada, naranja si no); mantenimiento vencido en rojo. Textos `info_sistema.*` (es/en); fuente de vapor, idioma y estados por catálogo.
- **Menú principal:** `info_equipo.py` ya no marca "No disponible" el último mantenimiento ni los ciclos restantes (la fuente existe); mientras no llega el dato se ve "—".

## Pruebas
`tests/test_o2d_info_sistema.py` (7): datos completos, un dato que falla, presentación por grupos, visibilidad por rol, pantalla offscreen. `test_info_equipo.py` actualizado. Suite completa: 4836 passed / 2 skipped / 3 xfailed.

## Captura
`O2d_1_info_sistema.png`.
