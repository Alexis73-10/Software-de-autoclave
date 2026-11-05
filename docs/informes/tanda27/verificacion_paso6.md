# Tanda 27, paso 6: verificación de equivalencia tras la depuración

Fecha: 5-nov. Probador. Sin cambios en `src/` ni commits.

- **Base:** `af2a3fb0` («docs(tanda27): parte A»), worktree `C:\tmp_t27\base_wt`.
- **Actual:** `7f7100ba` (HEAD de `tanda27` al empezar), worktree `C:\tmp_t27\now_wt`. Ojo: mientras corría la verificación, `tanda27` avanzó a `3f5e8c41`. Ese commit **no** se verificó.
- Cada lado se corrió con `PYTHONPATH=<worktree>\src`, `QT_QPA_PLATFORM=offscreen` y `PYTHONUTF8=1`. Los dos worktrees ya se eliminaron (`git worktree remove --force`).

## 1. Pantallas QML (arneses y pruebas)

### Arneses de `tests/banco`

Se corrieron en los dos árboles. Las salidas quedaron en `C:\tmp_t27\out_{base,now}\`.

| Arnés | Argumentos | base | actual |
|---|---|---|---|
| osc_capturas.py | `--temas claro oscuro --destino …` | rc=0, 40 PNG | rc=0, 40 PNG |
| t21_capturas_fin_ciclo.py | — | rc=0 | rc=0 |
| rep_capturas_reportes.py | `--plataforma offscreen` | rc=0, «avisos QML: []» ×4 | rc=0, «avisos QML: []» ×4 |
| opciones_qml_banco.py | — | rc=0 | rc=0 |
| p9_capturas_banco.py | — | rc=0 | rc=0 |
| u10a_capturas.py | `despues` | rc=0 | rc=0 |
| v8b_capturas.py | — | rc=0 | rc=0 |
| m1_asistente_banco.py | — | rc=0 | rc=0 |
| llf_capturas_barra_fases.py | — | rc=0 | rc=0 |
| cap9_capturas_banco.py | — | rc=0 | rc=0 |
| i4_truncado_banco.py | — | rc=0 | rc=0 |

En los registros (stdout y stderr juntos) se buscó con:

```
grep -i -E "ReferenceError|is not a type|not installed|unavailable|Unable to assign|TypeError|is not defined|QML .*(error|warn)"
```

El resultado fue **0 coincidencias en base y 0 en actual**. Las únicas líneas que no son «captura …» son las de «avisos QML: []» de rep y las de «simples/automaticas es/en ok» de p9. Son iguales en los dos lados.

### Pruebas pytest que cargan QML

Se corrieron `tests/*qml*.py`, `tests/test_tema_oscuro.py` y `tests/test_intro_arranque_qml.py` con `-s`, en los dos árboles:

- base: `891 passed in 1408.23s`, rc=0
- actual: `891 passed in 1403.88s`, rc=0

El mismo `grep`, más `\.qml:[0-9]+` y `qrc:`, dio 0 coincidencias en los dos lados.

Límites de esta parte:
- El tema oscuro solo se recorrió con `osc_capturas.py`, que cubre 10 pantallas en los dos temas y a dos resoluciones, y con `test_tema_oscuro.py`. Los demás arneses y pruebas corren en tema claro.
- 78 archivos de prueba o ayudantes instalan su propio manejador de mensajes. En ellos una advertencia se ve como fallo, y no hubo ninguno.
- `osc_capturas`, `t21`, `p9`, `u10a` y `v8b` no instalan manejador, así que sus advertencias de Qt saldrían por stderr. Ese stderr quedó capturado en los registros y no trajo advertencias.

## 2. Simulador

Se arrancó a mano desde el árbol actual, en el puerto 8001 (el 8000 no se usó):

```
python -m autoclave.simulador --puerto 8001 --velocidad 200 --bd C:\Users\tecni\Documents\codigo_autoclave\data\autoclave.db
```

La base se abre en solo lectura. La primera vez falló con `sqlite3.OperationalError: unable to open database file` porque el worktree no tiene `data/`. Con `--bd` arrancó bien:
`BACKEND SIMULADO — ciclo #5353 (liquidos), 78.0 min reales a 200x = 0.4 min`.

Pasos y respuestas:

| Paso | Petición | Respuesta |
|---|---|---|
| Login | `POST /auth/login` con tec1 | `{"token":"sim-tec1-1",…,"rol":"tecnico","debe_cambiar_clave":false}` |
| Inicio de ciclo | `POST /cycle/start` | `{"ok":true,"action":"START_CICLO"}` |
| Progreso | `GET /cycle/current/progress` | fases PRE_VACIO → CALENTAMIENTO → ESTERILIZACION → DESCOMPRESION → **COMPLETADO, resultado `exitoso`** |
| Reportes | `GET /report/dashboard?periodo=anio` | HTTP 200, `indicadores: total 135, completados 122, fallos 7, cancelados 6, exito_pct 90` |
| | `GET /report/calendar?periodo=mes` | HTTP 200, días 2026-11-01… en `sin_operacion` |
| | `GET /report/day-cycles` sin `programa` | 422 `Field required` (el parámetro es obligatorio: así está definida la ruta, no es una regresión) |
| | `GET /cycle/history?limite=2` | 200, ciclo 5353 Liquidos A, COMPLETADO |

Al terminar se cerró el proceso del simulador (`Stop-Process`, PID 29240). Comprobado después: ni el 8000 ni el 8001 quedan en LISTENING.

**Límites:** no se manejó la UI QML contra el simulador, porque no hay forma de interactuar sin pantalla. El simulador reproduce un ciclo grabado y no ejecuta la máquina de estados real.

Pruebas automáticas del simulador, en el árbol actual (`test_simulador_reportes`, `test_simulador_repeticion`, `test_contrato_autenticacion_simulador`, `test_e1/q1/s1/s2b_ensayo_simulador`):
`113 passed, 4 skipped in 55.98s`.

## 3. Conclusión

Entre `af2a3fb0` y `7f7100ba` no aparecen advertencias ni errores de QML nuevos: hay cero en ambos lados. Los 11 arneses terminan con rc=0, las 891 pruebas QML pasan, y el simulador completa un ciclo y sirve Reportes. No se verificó `3f5e8c41`.
