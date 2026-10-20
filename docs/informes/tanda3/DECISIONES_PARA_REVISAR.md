# Decisiones para revisar (tandas 2 y 3) — leer primero

## Resumen: qué mirar primero y qué hacer antes del lunes 26-oct (10 líneas)
1. **Compilar `Autoclave.exe` y probar el engrane**: `Autoclave.spec` excluye `scipy` y `qfluentwidgets` lo importa → el menú de ajustes (calibración, E/S) probablemente NO abre en el exe. Quitar `scipy` de `excludes` y probar (D-07 de la hoja).
2. **Reinstalar el perfil del equipo de pruebas con el asistente QML** (fuente de vapor = generador interno) y comprobar A-01/A-04.
3. **Cargar el firmware 1.0.0** a la tarjeta y comprobar A-02/A-03.
4. **Teléfono y Wi-Fi para F1:** abrir `http://<ip>:8090` desde el Android en el Wi-Fi del banco (¿el AP aísla clientes?), ejecutar `abrir_firewall.ps1` como administrador, crear los 2 usuarios y probar foto, firma y corte de Wi-Fi (README de `tools/registro_pruebas`).
5. **Dar los intervalos definitivos de mantenimiento** (hoy provisionales: 180 días, sin límite de ciclos).
6. **Apagado de Windows (A1):** ya permite FALLA, paro, sin tarjeta y cámara no segura; solo se rechaza en ciclo. Confirmar el criterio de "estado seguro actuando" (decisión 1 de A1) y probar B-07 con el exe.
7. **El login del menú PySide estaba roto** (SHA-256 vs PBKDF2, sin token): corregido en C1; probar con técnico e ingeniero (D-07).
8. **`git push`**: lo bloqueó el clasificador de permisos de la sesión; hacerlo tú (ver "Entrega" en el informe índice). `main` NO se tocó.
9. Revisar las 3 decisiones de seguridad marcadas ★ abajo (apagado en modo prueba, sonda de reemplazo en CIC-10, modo prueba huérfano).
10. Pendientes sin hacer: secado.py guarda en una ruta inexistente (SAF-04 de C1), reloj adelantado en mantenimiento (M1-01), caducidad de tokens (no existe).

Cómo revertir: cada decisión está en su commit; `git revert <hash>` (o pide que lo revierta). Orden: impacto en seguridad/instalación.

## Tanda 3 (rama `tanda-3`)

| # | Decisión | Por qué | Alternativa | Commit | Revertir |
|---|---|---|---|---|---|
| ★1 | **A1** "estado seguro en curso" = protocolo activo Y no pausado (sin paro, sin confirmación pendiente, con datos vigentes); pausado SÍ permite apagar | Con el paro/sin tarjeta/confirmación pendiente el equipo ya está quieto y el técnico debe poder apagar | Rechazar siempre que `estado_seguro.activo` | b3bddfd | `_estado_seguro_en_marcha()` → `estado_seguro.activo` |
| ★2 | **A1** el modo prueba NO bloquea el apagado | un técnico reparando suele estar en modo prueba | Rechazar (como antes) | b3bddfd | restaurar la condición `test_mode_active` |
| 3 | **A1** `iniciar_apagado()` manda ALL_OFF de inmediato; pasos con tope de 8 s; hilo de respaldo | revisión (SAF-01, TMG-01..04) | — | b3bddfd | — |
| ★4 | **S4** el cambio de rol libera un estado seguro detenido solo si el nuevo Principal tiene lectura y no es más frío que otra sonda (-2 °C); copia superficial, no muta la instantánea | revisión SAF-01/02 (sonda fría con carga caliente) | exigir ingeniero o confirmación | c0abe29 | quitar `aplicar_roles_sensores` |
| 5 | **S4** el botón "Asignar sonda Principal" lo ve cualquiera y lleva al login; solo aparece si el motivo es el sensor Principal | el backend impone el rol | ocultarlo sin sesión técnica | c0abe29 | — |
| 6 | **A2** `quick_check` (no `integrity_check`) y `synchronous=FULL`; la calibración corrupta NO se restaura sola del `.bak` | rapidez / no restaurar calibraciones viejas en silencio | integrity_check; restaurar .bak con aviso | 83048c3 | — |
| ★7 | **C1** login PySide vía `/auth/login` (token en el proceso); cambio de clave pendiente = sin acceso al menú PySide; NO se cambió la regla "solo el dueño sale del modo prueba" (decisión 30) | el login estaba roto; token por entorno sería visible | pasar el token de QML; permitir al ingeniero forzar la salida de un modo prueba huérfano | fb83d22 | revertir el commit |
| 8 | **C2** sin cambios de código (ya hecho por la otra sesión); un programa de usuario corrupto cae al de FÁBRICA con aviso | usabilidad; nunca un ciclo inválido | dejarlo no ejecutable | 2aefcc7 | — |
| 9 | **M1** intervalos PROVISIONALES 180 días / sin ciclos; config en `data/mantenimiento.json`; solo API para editarlos; sin observaciones en la pantalla | no hay valores documentados | pedirlos a Cristian (hazlo) | 44132ac | — |
| 10 | **M1-01** un reloj adelantado puede sellar un mantenimiento con fecha futura (tabla de solo anexar) | sin referencia de tiempo independiente | fila de anulación / confirmar fecha lejana | 44132ac | — |
| 11 | **O1** se guarda el `usuario` (no el nombre); sin sesión queda vacío ("—"); sin BD se conserva la leyenda de T8 en el respaldo; reportes por periodo no se desglosan por operador | mínimo y reversible | guardar "SIN SESIÓN"; agregar "por operador" | 368b68c | — |
| 12 | **U5** tarjeta de secado retirada junto con `menu.secado_*` y `ResumenSistema.tiempoSecado` | pedido | — | bbcea43 | revertir |
| 13 | **F1** firma por prueba (y final); puerto 8090; sesión 10 h; cierre con pruebas sin resultado permitido con confirmación; el admin no edita registros ajenos; REG-03/04/09 aceptados | lo pidió el documento | firma por bloque | bde6e41 | — |
| 14 | **E1** el simulador del repo no sirve para fallas: se usó la planta provisional de T11 | — | ensayo con el ControlLoop y la tarjeta | 8d3a8fb | — |
| 15 | **H1** B-06 reescrita, nuevas B-07, C-04, D-06..D-09 y E-06 | cubrir A1, A2, M1, C1, C2, S4, U5, O1 | — | 09f4726 | — |

## Tanda 2 (sin confirmar; ver el informe de cada etapa)
Aprobadas por Cristian el 20-oct: S4 = A+B, S3c (base en falla permanente), D-U2-3, D-U2-5, D-S2-1, valores de plausibilidad de S3a, apagado no permitido en ciclo, retirar la tarjeta de secado.
Siguen sin confirmar (detalle en `docs/informes/tanda2/`): U1 (D-U1-0 a D-U1-5: panel no se puede cerrar con paro, NO ABRIR como fila media, MODO PRUEBA como fila baja, sin login con paro, avisos de conexión fuera de la campana; commit `9fba067`), U2 (D-U2-1, D-U2-2, D-U2-4; `1c778c7`), U4 (U4-2 y U4-3; `f6d55e6`), S1 (D-S1-1: generador interno = sin DO1/DO2 en todo equipo con `vapor_source=generator`; D-S1-2; `5aa6f92`), S2 (D-S2-2 modo prueba no permite cambiar programa; `7b8d44a`), G1 (D-G1-1 a D-G1-4: tarea SYSTEM, clave inicial en ProgramData, 15 min/5 intentos, sesiones en memoria; `2ce4e98`), P1 (D-P1-1: HTML imprimible, sin xlsx; `382e672`), R1 (D-R1-1 a D-R1-3; `ece51e9`, `7669c1b`).
