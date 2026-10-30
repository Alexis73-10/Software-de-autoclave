# Tanda 5: estado final (20-oct-2026)

Rama `tanda-5`, creada desde `dev` (a563a06) y unida a `dev` con `--no-ff`.

| Etapa | Estado | Commit |
|---|---|---|
| E0 | Hecha (en `dev`) | b33b9cf, daabc7c, a5695fe, 8d5ddce, 06b7ef4, 4ccd2d1, a563a06 |
| R0 | Hecha | informe en 747e203 |
| P1 ★ | Hecha | 747e203 |
| P2 | Hecha | 9681aee |
| P3 ★ | Hecha | 2030a81 |
| O1 ★ | Hecha | 3f551ed |
| T1 ★ | Hecha | 2ad78b6 |
| U1 ★ | Hecha | a78bdee |
| I1 ★ | Parcial | 2ecb0e3 |
| I2 | Parcial | 3d5f50b |
| I3 | Parcial | 5fe777c |
| O2 | **No hecha** | — |
| H1 | Hecha | 42e831b |
| Z | Hecha | ver abajo |

**Suite:** línea base 4045/1/3. Al cerrar, **4379 pasan, 1 omitida, 3 xfail**. Hubo fallos intermitentes cuando el árbol cambiaba durante una corrida; el último fue una fuga de estado global entre pruebas, ya corregida en `conftest.py`.

**Revisores en las etapas ★:** se corrigieron todos los Altos (TMG-01 de P1, SAF-01 de O1, T1-01-A de T1). No queda ningún Alto ni Crítico abierto. Los Medios y Bajos pendientes están en cada informe.

**Árbol compartido:** otra sesión tiene cambios sin commit en `teclado_alfanumerico_controller.py`, `teclado_numerico_controller.py`, sus pruebas y los dos `bowe_dick.json`. No se incluyeron. Además, `data/unidades.json` del equipo quedó en **°F / psi**, escrito a las 16:44 fuera de las pruebas (uso manual de la app u otra sesión). **Antes del lunes, volverlo a °C/kPa desde Opciones o borrarlo.**

**Push:** ver la última línea (la agrega el cierre).
