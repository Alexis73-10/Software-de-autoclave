# Tanda 9 — Decisiones sin confirmar y preguntas para Cristian

Recopiladas de los informes de cada etapa (el detalle y el porqué están en cada informe). Ninguna está confirmada: todas son reversibles.

## Lo más importante para el lunes 26-oct (leer primero)

1. **S9, decisión 1 (SAF-01, Crítico de la revisión):** en modo prueba, con el estado seguro activo, la recuperación de arranque pendiente o la cámara no segura, Entradas/Salidas **rechaza abrir o desbloquear puertas** (y, con el estado seguro, también la descompresión rápida, la de chaqueta, el vapor de cámara, el aire comprimido de cámara y el vapor de generador/caldera). **En el equipo de pruebas sin sensores la cámara nunca es segura: las puertas no se pueden accionar desde Entradas/Salidas** (pregunta S9-10).
2. **S9, pregunta 18 (Alto anterior a la tanda 9, no corregido):** en CICLO, si la tarjeta sigue mandando entradas digitales pero deja de mandar analógicas, ESTERILIZACION puede terminar COMPLETADO y el F0 acumular con valores congelados. Corregirlo cambia una transición de ciclo no definida en las decisiones: no se tocó.
3. **B9, pregunta 1:** el equipo de pruebas tiene puertas simples. La causa que B9 confirmó (puertas avanzadas reenviando órdenes durante el paro) no aplica a puertas simples. La D asegura que el PC no ordena encender nada salvo el buzzer durante el paro: si en banco algo se enciende igual (caso B-13), la causa está en la tarjeta, el firmware cargado o el cableado.
4. **E9-P1:** el equipo de pruebas conserva sus programas de usuario de la B (el Bowie & Dick tiene modo 4, 134,5 °C, etc., residuos del banco). La actualización a la D no los toca (D9-13.1 nunca toca `cycles/user`).
5. **P9, pregunta 1:** un programa que ya tenga `apertura_automatica = true` en un equipo de puertas simples no se corrige. Al terminar el ciclo esperaría sin fin a que la puerta se mueva (aviso `APERTURA_AUTOMATICA_DENEGADA`).

## S9 ★ — Estado seguro al arrancar y bloqueos (D9-1)
Informe: `S9_estado_seguro_arranque.md` (§5 y §6). Revisión ★ en 4 pasadas (safety, timing y sensor-role); sin Altos ni Críticos propios abiertos.

Decisiones sin confirmar:
1. SAF-01: bloqueo de salidas en modo prueba (arriba, punto 1).
2. (Reemplazada por la 7.)
3. La recuperación de arranque espera la primera trama analógica hasta 1,5 s antes de decidir.
4. En vacío, las descompresiones se cierran en el acto y el aire atmosférico abre tras 3 lecturas.
5. SEN-10 confirmada se reafirma mientras no se pueda evaluar (puerta cerrada, sin datos): solo la despejan 3 lecturas coherentes con la puerta ABIERTA.
6. Arranque sin presión con la cámara a presión real: no se ventea a ciegas.
7. Trama analógica vencida = datos no vigentes: no se abre nada nuevo, lo abierto se mantiene, el aire comprimido se cierra, no enclava «solo la lenta», CIC-10 informativo.
8. P-a: también se bloquean `aire_comprimido_camara`, `vapor_generador` y `vapor_caldera` en modo prueba con el estado seguro; `vapor_chaqueta` queda permitida.
9. DESCOMPRESION modos 4/5: sin aire comprimido con la trama analógica vencida.
10. Sin el lazo de control construido, la presión no es vigente y las puertas no abren por software.
11. El plazo de escalada se arma al tomar la decisión inicial diferida, no al disparo.
12. Sin la presión atmosférica de referencia configurada, el protocolo no abre el aire atmosférico.

Preguntas (19, numeradas como en el informe): bloqueo físico de puerta por presión (1); antirretorno del aire atmosférico (2); paro visto antes del protocolo (3); estado de bloqueo y empaque al apagar (4); líquido presurizado al arrancar venteado por la lenta (5); periodo real de las tramas AI/DI del ESP32 (6, 16); CIC-10 al encender (7); ¿se cierran la lenta o el aire ya abiertos al detenerse? (8); modo prueba con la cámara sellada (9); excepción para probar puertas en el banco sin sensores (10); vacío y agua de chaqueta en modo prueba (11); vapor de chaqueta (12); retención de la puerta sin `cerrar`/`bloquear` en modo prueba (13); empaque desinflado por vacío (14); SEN-10 solo en memoria (15); texto propio del CIC-10 por trama vencida (17); **CICLO con trama analógica vencida (18, Alto anterior)**; Bajos varios (19).

## B9 ★ — Buzzer y paro (D9-9)
Informe: `B9_buzzer_paro.md`. Altos abiertos aceptados por el revisor como decisión del dueño o anteriores: SAF-01/HAZ-B9-02 (con el paro, la puerta avanzada ya no repone el empaque ni mantiene `cerrar_on`, como pide D9-9) y SAF-02/HAZ-B9-03 (una puerta en movimiento reanuda sola al soltar el paro, anterior).

Decisiones: el bloqueo rige también con «paro sin datos» fuera de CICLO; las órdenes bloqueadas salen como `SET DOn OFF`; se bloquean también la apertura por atrapamiento y la orden invertida de modo prueba durante el paro; firmware sin cambios.

Preguntas: tipo de puerta del equipo (1); ¿el paro corta por hardware?, ¿retienen las válvulas de cierre/bloqueo?, ¿se exceptúa `bloqueo_puerta_N`? (2); atrapamiento con el paro (3); puertas en movimiento al soltar el paro (4).

## A9 — Niveles de alarma y bitácora (D9-2, D9-6)
Informe: `A9_niveles_bitacora.md`. Decisiones: las filas viejas de eventos retirados se muestran con texto genérico; se retiran todos los `rechazo_*` (también 422/503); SEN-01/03/06/07 y CIC-10 resueltas sin reconocer quedan en la lista hasta reconocerlas. Pregunta: la orden de puerta de servicio con sesión de técnico (permisos por rol diferidos), ¿vuelve a la bitácora?

## P9 — Puertas simples, refresco y entradas NC (D9-3, D9-4, D9-5)
Informe: `P9_opciones_puertas_nc.md`. Decisiones: puertas simples = solo `door_type: simple`; `timeout_temperatura` sigue visible; una entrada NC sin lectura muestra «Sin datos»; los parámetros ocultos siguen modificables por la API (solo se rechaza activar la apertura automática); sin perfil se muestra todo. Preguntas: programa con apertura automática en puertas simples (1, arriba); duplicar o importar sin revisar la apertura automática (2); grupo Empaque en `motorized`/`locking` (3).

## C9 — Manejo de ciclos (D9-10)
Informe: `C9_manejo_ciclos.md`. Decisiones: habilitar/deshabilitar y duplicar valen también para los 4 programas estándar (solo borrar está prohibido para ellos); «fuera de ciclo» = cualquier estado distinto de CICLO (se quitó la excepción del ingeniero en CICLO); crear = duplicar con una base elegida; no se listan los de `cycles/factory`; diseño provisional sin maqueta; textos de bitácora con campos crudos; claves i18n viejas sin uso conservadas.

## E9 — Entrega y Setup (D9-7, D9-11, D9-8, D9-13.1)
Informe: `E9_entrega_setup.md`. Decisiones: E9-1 en la primera instalación los programas de usuario se siembran como copia de fábrica; E9-2 el refresco de la configuración de fábrica lo hace el programa al arrancar (no el Setup), con respaldo; E9-3 el Setup no valida la contraseña del inicio automático contra Windows. Preguntas: E9-P1 programas de usuario de la B (arriba, punto 4); E9-P2 la rama `instalador-setup` queda superada y no debe unirse.

## X9 ★ — Pendientes de la tanda 8 (D9-13.3, D9-13.4)
Informe: `X9_pendientes_t8.md`. Decisiones: abreviaturas solo en el ticket; resultado en inglés como «FAILED (STERILIZATION)»; motivos viejos no se migran; prefijo `ESTERILIZACION_TIMEOUT_F0:` conservado en español; programa con marca «sin bitácora» se carga como dañado; cambio que llega con la fase ya iniciada rige desde el siguiente ciclo. Preguntas: ancho del ticket (la decisión dice 32 columnas, el código usa 24) (1); acción en la aplicación para quitar la marca «sin bitácora» (2); corte de energía entre JSON y bitácora (3, Medio anterior); alarma ante la doble falla (4, Medio).

## K9 — Compilación D
Informe: `K9_compilacion_d.md`. Decisión K9-1: en el equipo de pruebas el LEEME (8c) pide DESMARCAR la casilla «Configurar este PC como estación» hasta validarla en un PC de prueba (en el Setup sigue marcada por defecto, como pide D9-11). Pendiente: `entrega/drivers/` está vacía.

## Después de K9 (no están en la compilación D)
- **D9-12 (`L9_login_recordar_olvido.md`):** «Recordar usuario» guarda solo el nombre en `data/login_recordado.json` (local y compartido por todos los usuarios del equipo, no en el registro de Windows); «¿Olvidó su contraseña?» muestra un texto que pide a un administrador o ingeniero restablecerla en OPCIONES › Usuarios (sin canal de recuperación nuevo); la ayuda es un texto sin diseño; se recuerda el nombre también cuando hay que cambiar la contraseña al entrar. Preguntas: conservar «Recordar usuario» en un equipo compartido; nombrar al técnico en la ayuda; diseño; borrar el nombre al desactivar al usuario.
- **D9-13.5 (`CAP9_capturas.md`):** 102 capturas es/en. Muestran que, con la interfaz en inglés, las filas de alarma de Preciclo (CIC-10, SEN-06) salen en español, y que el motivo largo de CIC-10 se corta (no corregido; está en la D).

## Arrastradas de la tanda 8 (D9-13, no entran en la tanda 9)
D-38 (cuentas ADC de banco); presión de tara de las válvulas de seguridad mecánicas; preguntas de S1, S2a, S2b, R8 (incluida SAF-04: estado seguro con la asignación de E/S dañada), V8a, E1 y E2; limpieza de worktrees con `--force`. Ver `docs/informes/informe_tanda_2026-10-23_t8.md` y `docs/informes/tanda8/DECISIONES_PARA_REVISAR.md`.
