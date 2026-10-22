# Tanda 7 — Decisiones para revisar

Formato: decisión, motivo, alternativa, commit, cómo revertir.

## Sesión principal (A0, K1)

### SP-1. Tanda 6 tratada como cerrada aunque su `estado.md` dice Z "En curso"
- **Decisión (DECISIÓN SIN CONFIRMAR):** no se aplicó la regla 10 (tanda 6 activa).
- **Motivo:** `tanda-6` contenida en `dev`; commits de cierre f631f35/1d6cf98 empujados (dev = origin/dev); árbol sin cambios rastreados; el lanzador registró "Tanda 6 cerrada" a las 23:46. Los archivos con fecha reciente eran los del propio cierre, ya commiteados.
- **Alternativa:** trabajar solo en worktrees desde `tanda-6` hasta las 12:30.
- **Commit:** 0cfb4cc. **Revertir:** no aplica (solo se creó `tanda-7` desde `dev`).

### SP-2. Specs compilados: `Autoclave.spec` y `GeneradorCodigos.spec`
- **Decisión:** no se compilaron `AutoclaveBackend.spec` ni `AutoclaveSettings.spec`.
- **Motivo:** el ejecutable único (`exe_unico.py`, tanda 2 R1 / tanda 4) los reemplazó; el generador hace falta para el código de activación del día.
- **Alternativa:** compilar también los viejos (no se usan en la instalación).
- **Revertir:** compilar el spec adicional.

### SP-3. Prueba de humo con `--portable`
- **Decisión:** se respondió "No" a "¿Instalar Autoclave en este PC?" y se probó con `--portable`, para no instalar software en el PC de desarrollo (regla 3).
- **Alternativa:** instalar en Archivos de programa (prohibido en esta tanda).

### SP-4. M2 se ejecuta
- **Decisión:** la decisión 1.4 decía que el Mantenimiento E1 no entraba; Cristian corrigió la instrucción a las 00:30 (sin commit, en el árbol) para que E1 entre. Se commiteó su corrección (e8e42d7) y se lanzó M2.
