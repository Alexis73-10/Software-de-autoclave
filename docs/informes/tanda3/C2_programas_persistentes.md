# C2 — Programas de usuario persistentes con el ejecutable (RB-04.5)

## Estado encontrado
La parte de código ya estaba resuelta por el trabajo de la otra sesión (commit 01da526, `utils/resources.py`): con el build congelado `cycles/user` y `config` se leen y escriben en `<raiz_datos_exe>/programa/autoclave/...` (instalado en Archivos de programa: `%ProgramData%\Especifika\Autoclave`; copia portátil: junto al exe), nunca en `_MEIPASS`. Se siembran desde el paquete solo si el archivo no existe (se conservan las ediciones del técnico y entran los programas nuevos); `cycles/factory` se refresca siempre desde el paquete (solo lectura: el backend rechaza editarlo con `programa_de_fabrica`). El instalador copia solo `_internal` y el exe, así que una actualización no toca `ProgramData`. Escritura de programas: atómica + `.bak` (T10). No se editó `paths.py`.

## Pruebas nuevas (`tests/test_c2_programas_persistentes.py`, 6)
Primera ejecución (siembra fuera del paquete), actualización (la edición del técnico sobrevive, entra el programa nuevo, fábrica se refresca), fábrica alterada se restaura, archivo de usuario corrupto (JSON truncado) → cae al programa de fábrica íntegro y el archivo queda en `errores_carga` (el arranque lo avisa con ARR_CICLO_CORRUPTO), valores fuera de catálogo → programa DAÑADO no ejecutable (nunca un ciclo inválido), y la ruta persistente no es la del paquete.

## Observaciones / límites (sin cambios de código)
- Un archivo de usuario corrupto hace que corra el programa de FÁBRICA del mismo id (no el del técnico), con el aviso de arranque. Alternativa: dejar el programa no ejecutable hasta que el técnico lo repare. DECISIÓN SIN CONFIRMAR (se conserva el comportamiento existente: es el más usable y el programa de fábrica es válido).
- Un cambio de valores de fábrica en una actualización NO se propaga a las copias de usuario ya sembradas (por diseño: se conservan las ediciones). Parámetros nuevos agregados al esquema en una actualización faltarían en las copias de usuario viejas: verificar al versionar.
- Comprobación manual con el exe instalado: editar un parámetro en OPCIONES, cerrar, reabrir y comprobar que se conserva; reemplazar la carpeta del programa por una versión nueva y repetir.
