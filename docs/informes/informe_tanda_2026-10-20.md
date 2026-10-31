# Informe de la tanda 3 (20 de octubre de 2026, madrugada)

Instrucción: `docs/mis_plans/instruccion_claude_code_tanda_3.md`. Estado: `docs/informes/tanda3/estado.md`. **Decisiones sin confirmar y qué hacer antes del lunes 26-oct: `docs/informes/tanda3/DECISIONES_PARA_REVISAR.md` (léelo primero).**

## Resumen
- Ramas: `tanda-2` (con el trabajo de la otra sesión commiteado) → `dev` (merge `258424b`, suite 3587 verde); `tanda-3` desde `dev` → `dev` (merge al final, suite 3793 verde). `main` sin tocar.
- **`git push` NO se hizo**: el clasificador de permisos de la sesión lo denegó ("publicación fuera de lugar"). Hazlo tú: `git push origin dev tanda-2 tanda-3` (sin `--force`).
- Pruebas: 3587 → **3793 pasan**, 1 omitida, 0 fallos.

## Hallazgos que importan
1. **El menú de ajustes (engrane) estaba inutilizable** (C1): el login PySide comparaba SHA-256 contra hashes PBKDF2 y no obtenía token, así que calibración y E/S daban 401. Corregido y probado; **falta probar con el exe**.
2. **`Autoclave.spec` excluye `scipy`, pero `qfluentwidgets` lo importa**: el menú de ajustes probablemente no abrirá en el ejecutable. No se editó el spec (era de la otra sesión). Acción manual.
3. **El apagado (A1)** ahora funciona con FALLA, paro, sin tarjeta, cámara no segura y modo prueba; solo se rechaza en ciclo y con el estado seguro actuando. La revisión encontró una ventana con las salidas congeladas (corregida: ALL_OFF inmediato).
4. **CIC-10 (S4)**: un cambio de rol del Principal NO liberaba el estado seguro (las copias del programa guardaban la asignación vieja). Ahora sí, solo con una sonda con lectura y no más fría que otra.
5. **Corte de energía (A2)**: la calibración se escribía sin atomicidad (un corte la dejaba truncada y el equipo sin arrancar); ahora es atómica con `.bak`, igual que latido, PID y perfil; la BD verifica integridad al abrir.
6. Mantenimiento (M1), operador del ciclo (O1), tarjeta de secado retirada (U5), programas persistentes (C2, ya estaba hecho), app de registro F1 y ensayo E1: ver sus informes.

## Índice
| Etapa | Informe |
|---|---|
| A1, A2 | `tanda3/A1_apagado_cualquier_estado.md`, `tanda3/A2_corte_de_energia.md` |
| S4, U5 | `tanda3/S4_cic10.md`, `tanda3/U5_tarjeta_secado.md` (+ captura `U5_menu_principal.png`) |
| M1, C1, C2, O1 | `tanda3/M1_mantenimiento.md`, `C1_ajustes_pyside.md`, `C2_programas_persistentes.md`, `O1_operador_ciclo.md` |
| F1 | `tanda3/F1_registro_pruebas.md` y `tools/registro_pruebas/README.md` (comprobaciones con el teléfono) |
| E1 | `tanda3/E1_ensayo_simulador.md` (+ `E1_tabla.md`) |
| H1 | `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md/.html` (35 pruebas) |

## Comprobaciones manuales urgentes (antes del lunes 26-oct)
1. Compilar `Autoclave.exe` (quitando `scipy` de `excludes`) y probar engrane → login → calibración y E/S; B-06/B-07 (apagado).
2. Reinstalar el perfil del equipo de pruebas con el asistente QML (generador interno).
3. Cargar el firmware 1.0.0.
4. Teléfono + Wi-Fi para F1 (¿el AP aísla clientes?), `abrir_firewall.ps1` como administrador, dos usuarios, foto, firma, corte de Wi-Fi.
5. Dar los intervalos de mantenimiento definitivos.
6. Compilar también el generador de códigos (G1) si se usará.

## Entrega: unir `dev` a `main` (NO hecho; lo haces tú tras revisar)
```
git checkout main
git merge --no-ff dev -m "Integra dev (tandas 14-oct, 2 y 3) en main"
```
Entrarían TODOS los commits de `git log --oneline main..dev` (≈ 135: las tandas anteriores de `dev` que tampoco estaban en `main`, la tanda 2 y la 3). Los de la tanda 3, en orden: `b3bddfd` A1, `83048c3` A2, `c0abe29` S4, `bbcea43` U5, `44132ac` M1, `fb83d22` C1, `2aefcc7` C2, `368b68c` O1, `09f4726` H1, `bde6e41` F1, `8d3a8fb` E1 y los de documentos/cierre de esta tanda.
