# Tanda 5 — estado

Rama: `tanda-5` (desde `dev` a563a06). Actualizado: 20-oct-2026.

| Etapa | Estado | Commit |
|---|---|---|
| E0 | HECHA (en `dev`) | b33b9cf, daabc7c, a5695fe, 8d5ddce, 06b7ef4, 4ccd2d1, a563a06 |
| R0 | HECHA | (informe en el commit de P1) |
| P1 ★ | HECHA (safety + timing sin Altos abiertos) | 747e203 |
| P2 | HECHA | 9681aee |
| P3 ★ | HECHA (safety sin Altos) | 2030a81 |
| O1 ★ | EN CURSO | — |
| T1, U1, I1, I2, I3, O2, H1 | pendientes | — |
| Z | pendiente | — |

Suite: línea base 4045/1/3; tras P1–P3, 4091/1/3. Una corrida intermedia dio 2 fallos que no se repitieron.

**Árbol compartido:** mientras corría la tanda, otra sesión empezó a modificar archivos sin commit (`teclado_*_controller.py`, sus pruebas, `cycles/factory/bowe_dick.json`, `cycles/user/bowe_dick.json`). No se incluyen en los commits de la tanda 5 ni se tocan. Probablemente causaron la variación en el conteo de pruebas y los 2 fallos intermitentes.
