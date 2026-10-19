# Estado de la tanda 2 (19-oct-2026)

Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_2.md`. Rama `tanda-2`, creada desde `dev` (d5b7afb); `dev-noche` ya es ancestro de `dev` (verificado con `git merge-base --is-ancestor`). Sin `git push`; nada se une a `dev`.

**Línea base:** 3358 pruebas en verde (`python -m pytest -q -p no:cacheprovider` en una copia limpia de `dev`, 6 min 49 s).

**Commit previo:** `49c7efa` — trabajo encontrado sin commitear al empezar (barra de tareas de Windows y simulador con historial), con sus pruebas en verde. Ver el informe de U1, §Antecedentes.

| Etapa | Estado | Commit | Pruebas al cerrar | Informe |
|---|---|---|---|---|
| U1 Alarmas fuera de la barra superior | hecha | `9fba067` | 3375 | `U1_avisos_en_campana.md` |
| U2 Navegación inferior uniforme | hecha | `1c778c7` | 3386 | `U2_navegacion_inferior.md` |
| U3 Botón de tiempo de secado | hecha (sin botón que retirar; sin código) | (este commit) | 3386 | `U3_boton_secado.md` |
| S1 DO1/DO2 | hecha | `5aa6f92` | 3394 | `S1_do1_do2.md` |
| S2 `/cycle/select` | hecha | (ver git log: S2) | 3413 | `S2_cycle_select.md` |
| S3 Pendientes de seguridad | pendiente | — | — | — |
| R1 Retiro de tkinter | pendiente | — | — | — |
| P1 Hoja de pruebas de banco | pendiente | — | — | — |
| W1 Estación Windows (opcional) | pendiente | — | — | — |

**Bloqueadas:** ninguna.
