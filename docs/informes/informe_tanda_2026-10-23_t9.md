**HAY COMPILACIÓN D Y SE RECOMIENDA INSTALARLA en el equipo de pruebas antes de los ciclos del lunes 26-oct: `entrega/2026-10-23_d/` (etiqueta `inst-2026-10-23-d`), con el Setup `Autoclave_Setup_1.0.0-d.exe` y la sección 8c de `entrega/LEEME_INSTALACION.md` (B → D, sin copias a mano; desmarcar la casilla de estación hasta validarla en un PC de prueba). Lo que va a la USB está en `entrega/2026-10-23_d/usb/`. La C no se instala.**

# Tanda 9 — Índice (23-oct-2026)

## Resumen (10 líneas)
1. Todas las etapas están hechas y unidas a `dev` con la suite en verde. Suite de la compilación D: **6606 passed, 10 skipped, 3 xfailed** (línea base 6201). Suite final de `dev` (con D9-12 y las capturas): **6633 passed, 10 skipped, 3 xfailed**.
2. S9 ★ (D9-1): al arrancar con la cámara no segura, el estado seguro corre solo, sin confirmación y sin «paro liberado»; sin presión de cámara da CIC-10 + SEN-06 y NO ABRIR sin bloquear login, modo prueba, cambio de programa ni apagado. Alarma nueva SEN-10 (puerta abierta con presión incoherente).
3. La revisión ★ de S9 necesitó 4 pasadas: la 1 encontró un **Crítico** (el modo prueba dejaba abrir la puerta con la cámara a presión) y Altos de vigencia de la trama analógica. Todo lo propio de S9 quedó cerrado; un Alto anterior a la tanda (CICLO con AI vencida) va como pregunta.
4. B9 ★ (D9-9): con el paro, ALL_OFF inmediato y el PC no ordena encender nada salvo el zumbador. La causa confirmada (puertas avanzadas) no aplica al equipo de pruebas (puertas simples): el caso de banco B-13 discrimina si el síntoma viene de la tarjeta.
5. A9: SEN-01/03/06/07 y CIC-10 pasan a ALARMA; la bitácora deja de registrar rechazos, suspensión, órdenes de puerta, selección de programa y pruebas de correo/impresora.
6. P9: equipos de puertas simples sin apertura automática ni grupos Puerta/Empaque; grupo «Cámara segura»; Parámetros del equipo se refresca al guardar; entradas NC interpretadas. C9: Manejo de ciclos en Opciones avanzadas.
7. E9: entrega neutra (correo sin datos, solo programas de fábrica), Setup con la casilla de estación y lista de verificación para el PC de prueba; **al actualizar, el programa refresca solo su configuración de fábrica con respaldo** (sin copias a mano).
8. X9 ★: la bitácora del cambio de parámetro se registra antes de aplicarlo y en una sola transacción; ticket y motivos de fallo en el idioma vigente.
9. K9: build limpio, verificador neutro, prueba de humo, ensayo B → D con el `_internal` real (Cámara 2 y `descompresion_lenta` sin pasos manuales) y Setup compilado (no ejecutado). Después de K9: capturas regeneradas (D9-13.5) y D9-12 («Recordar usuario» y «¿Olvidó su contraseña?»), que NO están en la D.
10. Cortes: la sesión 01 se cortó por el límite de uso a la 01:05 (subagentes perdidos); se reanudó a las 02:35 sin rehacer lo commiteado (A9 y S9 continuados en su worktree).

## Etapas
| Etapa | Estado | Informe |
|---|---|---|
| A0 | Hecha | `tanda9/estado.md` (línea base 6201 p) |
| S9 ★ | Unida (4 pasadas de revisión; sin Altos/Críticos propios abiertos) | `tanda9/S9_estado_seguro_arranque.md`, `tanda9/S9_ensayo_tabla.md` |
| B9 ★ | Unida (2 Altos aceptados por el revisor como decisión de Cristian o anteriores) | `tanda9/B9_buzzer_paro.md`, `B9_registro_ordenes*.md`, `B9_ensayo_tabla.md` |
| E9 | Unida | `tanda9/E9_entrega_setup.md` |
| A9 | Unida | `tanda9/A9_niveles_bitacora.md` |
| P9 | Unida | `tanda9/P9_opciones_puertas_nc.md` |
| C9 | Unida | `tanda9/C9_manejo_ciclos.md` |
| X9 (★ D9-13.3) | Unida (0 Altos/Críticos) | `tanda9/X9_pendientes_t8.md` |
| K9 | Hecha (compilación D) | `tanda9/K9_compilacion_d.md` |
| D9-13.5 | Unida (102 capturas es/en, después de la D) | `tanda9/CAP9_capturas.md` |
| D9-12 | Unida (después de la D; no está en la D) | `tanda9/L9_login_recordar_olvido.md` |
| Z | Hecha | este índice |

## Suites
Una por unión, en `tanda9/suites/integ_*.log`, todas en verde: E9 6236, A9 6251, P9 6284, C9 6337, X9 6391, S9 6567, S9 (revisión 3) 6575, B9 **6606** (código de la D), final (con D9-12 y capturas) **6633** (`integ_final.log`). Ninguna falla en ninguna unión. Los skipped nuevos son pruebas que solo escriben informes (variables `S9_ESCRIBIR_INFORME`, `B9_ESCRIBIR_REGISTRO`).

## DECISIONES SIN CONFIRMAR
Todas en `tanda9/DECISIONES_PARA_REVISAR.md` (con un bloque «Lo más importante para el lunes»). Las de mayor impacto:
- **S9-1:** en modo prueba, con el estado seguro activo o la cámara no segura, Entradas/Salidas no deja abrir ni desbloquear puertas: **en el equipo sin sensores las puertas no se accionan desde Entradas/Salidas.**
- S9-7: trama analógica vencida = datos no vigentes (no abre nada nuevo, cierra el aire comprimido, no enclava «solo la lenta»).
- E9-2: el refresco de la configuración de fábrica lo hace el programa al arrancar, no el Setup.
- K9-1: en el equipo de pruebas, desmarcar la casilla de estación del Setup hasta validarla en un PC de prueba.
- X9: abreviaturas permitidas solo en el ticket.

## PREGUNTAS PARA CRISTIAN
**Para la instalación de la D y el lunes:**
- **S9-18 (Alto anterior a la tanda):** en CICLO, con la tarjeta mandando entradas digitales pero no analógicas, ESTERILIZACION puede terminar COMPLETADO y el F0 acumular con valores congelados. ¿Se trata la trama analógica vencida como la digital vencida (tolerancia y aborto)? No se cambió: transición de ciclo no definida.
- **S9-10:** ¿se acepta no poder accionar las puertas desde Entradas/Salidas en el banco sin sensores, o se quiere una excepción (perfil de banco o confirmación de ingeniero)?
- **B9-1:** el equipo de pruebas tiene puertas simples: si con la D algo se enciende durante el paro (B-13), la causa está en la tarjeta, el firmware cargado o el cableado.
- **E9-P1:** el equipo conserva los programas de usuario de la B con valores del banco (Bowie & Dick en modo 4, 134,5 °C…). Revisarlos antes de los ciclos.
- **P9-1:** un programa con `apertura_automatica = true` en un equipo de puertas simples esperaría sin fin al terminar el ciclo. ¿Se fuerza a `false` al cargar o se bloquea el inicio?
- **Interfaz en inglés (visto en las capturas, D9-13.5):** las filas de alarma de Preciclo (CIC-10, SEN-06) salen en español con la interfaz en inglés, y el motivo largo de CIC-10 se corta. No se corrigió (está en la D).

**Seguridad (de los informes ★):** S9 preguntas 1-17 y 19 (bloqueo físico de puerta por presión, antirretorno del aire atmosférico, paro visto antes del protocolo, bloqueo y empaque sin energía, líquido presurizado venteado por la lenta al arrancar, **periodo real de las tramas AI/DI del ESP32**, modo prueba con cámara sellada, vacío/agua de chaqueta/vapor de chaqueta en modo prueba, SEN-10 solo en memoria…); B9 2-4 (corte por hardware del paro, retención de las válvulas de cierre, atrapamiento con el paro, puertas en movimiento al soltar el paro).

**Otras:** A9 (orden de puerta de servicio en la bitácora); P9 2-3; X9 1-4 (**ancho del ticket: la decisión dice 32 columnas, el código usa 24**; marca «sin bitácora»; corte entre JSON y bitácora; alarma por doble falla); E9-P2 (no unir la rama `instalador-setup`); L9 1-4 (¿se conserva «Recordar usuario» en un equipo compartido?, ¿la ayuda nombra al técnico?, diseño de la ayuda, borrar el nombre al desactivar al usuario).

**Arrastradas de la tanda 8 (D9-13, no entraron):** D-38 (cuentas ADC de banco); presión de tara de las válvulas de alivio mecánicas; preguntas de S1, S2a, S2b, R8 (incluida SAF-04: estado seguro con la asignación de E/S dañada), V8a, E1 y E2; limpieza de worktrees con `--force`. Detalle en `informe_tanda_2026-10-23_t8.md` y `tanda8/DECISIONES_PARA_REVISAR.md`.

## Lo que quedó sin hacer y dónde está
- **D9-12 y las capturas no están en la compilación D** (se hicieron después de K9). Entran en la próxima compilación.
- Hallazgos Medios/Bajos abiertos de los revisores, en cada informe ★ (S9 TMG-07 y R2-B5 documentados; X9: 3 Medios como preguntas; B9: TMG-02 de fondo en `SerialLink.all_off`).
- `entrega/drivers/` está vacía desde el 22-oct: si el PC del equipo necesita el controlador del puerto serie de la tarjeta, hay que agregarlo a `usb/drivers/`.
- La tabla índice de la hoja de banco (fila C-05) no lista los casos C-05b a C-05h.
- Filas de alarma de Preciclo en español con la interfaz en inglés (arriba).
- En las capturas no hay banco con backend y datos reales, ni de la campana con las alarmas de S9.

## Push
Ver el final de `tanda9/estado.md`.

## Limpieza
- Worktrees de la sesión principal: `_suites_t9/base` y `_build_d` (se pueden quitar). Fuera del repositorio: `C:\Users\tecni\Documents\_suites_t9` (diffs de revisión, logs del build), `_t9_k9_tmp` (ensayo B → D) y `_t9_e9_tmp` (de E9). Se pueden borrar.
- Los worktrees de los subagentes (`.claude/worktrees/agent-*`, ramas `tanda-9-*` y `worktree-agent-*`, todas unidas) no se quitaron: tienen `data/` sin seguimiento y quitarlos exige `--force`.
- Un subagente de S9 ejecutó por error `git stash pop` sobre la entrada ajena `stash@{0}` («WIP on dev: 488b1cd»): el pop falló por conflictos y la entrada sigue en la pila sin cambios (comprobado), pero dejó copias sin seguimiento en `data/` de su worktree.
