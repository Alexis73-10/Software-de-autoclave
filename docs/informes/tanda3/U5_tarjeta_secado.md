# U5 — Menú Principal: tarjeta "Tiempo adicional de secado" retirada

- `MenuPrincipal.qml`: se elimina la tarjeta `tarjetaSecado` (y su `TODO(MP-11)`); Reportes (x 54) e Información (x 606) quedan a 533 px de ancho cada una, en la misma fila (mismo borde derecho 1139 que Iniciar sesión + Historial; separación 19). Iniciar sesión, Historial y el Resumen del sistema no se tocaron.
- `ResumenSistema.tiempoSecado` retirada (sin uso). Se conserva `UiBridge.tiempoSecado` (lo usan Preciclo y Ciclo en curso) y el parámetro `secado.tiempo_secado` con su uso en el ciclo.
- i18n: `menu.secado_titulo` y `menu.secado_desc` eliminadas de es/en (sin uso). `GaleriaMenuPrincipal` conserva sus tarjetas de prueba de valores largos (no dependían de la clave).
- Pruebas actualizadas (geometría, tarjetas, marcadores TODO) y captura nueva: `docs/informes/tanda3/U5_menu_principal.png`.
- Iconos: en la captura offscreen los iconos monocromos (MultiEffect) no se dibujan (Iniciar sesión, Reportes, Información, mantenimiento); el de Historial (color) sí. Es una limitación del render offscreen, igual que en la captura de U3; en el equipo sí aparecen. Pendiente de verificar a ojo en pantalla real.
