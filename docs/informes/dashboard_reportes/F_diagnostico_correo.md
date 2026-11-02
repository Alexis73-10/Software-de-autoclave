# Etapa F — Diagnóstico de DR-H06 (correo escrito a mano que no llega)

Fecha: 2-nov. Rama `dashboard-reportes`. Pendiente reportado el 20-oct: «un correo escrito a mano no llega aunque el software indica enviado» (`planeacion_dashboard_reportes.md` §4, DR-H06).

## Resultado

**Con el código actual no se reproduce.** No se cambió nada del envío (`ui_qml/exportacion/correo.py` y la parte SMTP de `AccionesCiclos` quedan igual). La única modificación de `AccionesCiclos` es la de REP-13 (sin sesión se ignoran las direcciones escritas a mano), que no forma parte de este diagnóstico.

## Reproducción

`tests/test_dr_h06_correo_manual_punta_a_punta_qml.py` (3 pruebas, sin red) recorre todo el camino:

- `SelectorDestino.qml` y `PanelTeclado.qml` reales, con teclas cada 150 ms como en el equipo;
- `AccionesCiclos` real con su hilo de trabajo y un PDF lento (1 s);
- `correo.enviar` con el `smtplib` real;
- el SMTP falso local `tests/helpers/smtp_falso.py` (127.0.0.1, puerto libre). No hizo falta `aiosmtpd`.

Escenarios: Confirmar y «Solo este correo»; Ocultar el teclado y «Solo este correo»; «Este correo y los guardados». En los tres:

- mientras se escribe no sale nada al relay (`RCPT TO` vacío);
- el relay recibe **una sola vez** la dirección **completa**;
- el aviso «Se enviaron 1 ciclo(s) a Juan@gmail.com» nombra lo que el relay aceptó;
- la bitácora (`/email/sent`) queda con `resultado: enviado` y la dirección en `manuales`.

Las 3 pasan con el código actual (41 s).

## Causa probable del reporte del 20-oct

Es el mismo fallo que C2 de la tanda 7 (`docs/informes/tanda7/C2_correo_manual.md`), corregido en `6a264a0d` el **22-oct**, después del reporte. El teclado entrega lo escrito en vivo. El selector de entonces tomaba cada entrega como la elección, así que la primera dirección parcial con forma válida («Juan@gmail.c») salía al relay. Las teclas siguientes se descartaban porque la acción ya estaba ocupada, y el aviso verde nombraba la dirección parcial.

Comprobación de que la prueba distingue el fallo (corrida aparte, sin dejar archivos en el repositorio): con el `SelectorDestino.qml` de `e8e42d7` (antes de C2) en una copia de la carpeta `qml` en el scratchpad, el mismo guion da 11 avisos «Dirección de correo no válida» (uno por tecla, de «J» a «Juan@gmail.») y arranca un envío con «Juan@gmail.c». La dirección completa nunca llega al relay. Con el código actual llega una vez y completa.

Ese envío viejo no llegó a mostrar `RCPT TO` en el SMTP falso en 8 s. No se investigó más porque es código retirado. Si se quiere, queda como pregunta abierta.

## Otras hipótesis revisadas (no demostradas, sin cambios)

1. **El relay acepta y rebota después.** Gmail acepta `RCPT TO` de una dirección inexistente o mal escrita y luego devuelve el rebote al buzón del remitente. El software solo puede saber lo que el relay aceptó (C2 ya no dice «enviado» sin aceptación), y el aviso nombra la dirección aceptada, así que un error de escritura se puede ver en pantalla. Verificación en el banco: revisar el buzón del remitente del equipo por rebotes.
2. **Mayúscula inicial del teclado.** Al escribir «juan@gmail.com», el teclado en pantalla empieza con mayúscula y entrega «Juan@gmail.com» (se ve en la prueba). Gmail y los servidores habituales no distinguen mayúsculas en la parte local, así que no explica el fallo. No se cambia porque no está demostrado que cause un fallo.
3. **Filtro de spam del destinatario.** Un PDF de un remitente nuevo puede quedar en spam. Está fuera del software.

## Para Cristian (banco)

- Repetir el envío a una dirección escrita a mano con la compilación actual. Si no llega, mirar el buzón del remitente (rebote) y la carpeta de spam del destinatario, y anotar el texto exacto del aviso en pantalla.
