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
| U4 Tarjeta desconectada vs. paro | hecha (insertada antes de S3 por instrucción del 19-oct); revisores sin Altos, Medias corregidas; 3 decisiones sin confirmar (U4-1..3) | (ver git log: U4) | 3498 (árbol con R1 sin commit de la otra sesión; S3a en stash) | `U4_tarjeta_desconectada.md` |
| S3 Pendientes de seguridad | en curso: S3a (plausibilidad de calibración) implementada SIN COMMIT y **apartada en `git stash`** (`stash@{0}`: "S3a tanda 2: plausibilidad de calibración (sin commit, apartada para U4)"; catalogo_parametros.py, server.py, tests/test_s3_calibracion_plausibilidad.py) para hacer U4 primero. Al retomar: `git stash pop`, suite completa, revisores, informe y commit de S3a; luego S3b–S3f | — | — | — |
| R1 Retiro de tkinter | pendiente | — | — | — |
| P1 Hoja de pruebas de banco | hecha (solo documentos) | (ver git log: P1) | — | `P1_hoja_pruebas_banco.md` |
| W1 Estación Windows (opcional) | pendiente | — | — | — |

**Bloqueadas:** ninguna.
