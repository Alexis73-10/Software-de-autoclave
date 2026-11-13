# Tanda 35: cascada de chaqueta con reposición integral y recuperación sobre Psat (CRI-01..04) (9-nov-2026)

Responde e informa SOLO en español. Especificación: `docs/mis_plans/planeacion_cascada_integral.md` (aprobada por Cristian el 9-nov); léela completa antes de empezar y síguela. Ante ambigüedad, lo más simple y `DECISIÓN SIN CONFIRMAR` en el informe. Máximo 4 subagentes a la vez, sin suite completa en los subagentes. Revisor de seguridad obligatorio al terminar CRI-01/02 (lazo de control de presión, clase C).

## Requisito previo
- Parte de `dev` (alpha.26, incluye CAS y PAM). Verifica que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los de `docs/`, `AJUSTES.md`, `Hadware/`, los `.log` y `habblaud/` de Cristian no cuentan; no los toques). Si los hay, escribe `docs/informes/tanda35/CERRADO.txt` con `BLOQUEADO: árbol con cambios pendientes` y termina.
- Crea la rama `tanda35` desde `dev`. Lleva `docs/informes/tanda35/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Pasos
1. Línea base: corre el escenario de planta de §1.4 y §6.3 de la especificación sobre `dev` sin cambios y guarda la tabla en `docs/informes/tanda35/base_planta.md`. Debe reproducir los 7 fallos de 16; si no los reproduce, detente y explícalo en el informe antes de seguir.
2. CRI-01 en `cascada_chaqueta.py` y su uso en `esterilizacion.py` (`_aplicar_cascada`) y `calentamiento.py` (`_decision_cascada`), con la herencia de `dp` de CALENTAMIENTO a ESTERILIZACION y el congelamiento de la integral.
3. CRI-02 (RECUPERACION en los dos modos y umbral «baja» de la cascada en ESTERILIZACION).
4. CRI-03 (retiro de PAM-06 con todos sus usos y regla nueva) y CRI-04 (auditoría única, rótulo y ayuda es/en).
5. Pruebas de §6.2 y planta de §6.3. Actualiza las pruebas existentes que fijaban el comportamiento anterior (tope `techo - 2` en banda, `p_ref - 2` en ESTERILIZACION, PAM-06, RECUPERACION bajo Psat) y lista en el informe cada una que cambiaste y por qué.
6. Revisión de seguridad (subagente revisor) sobre CRI-01/02: sobreimpulso, antiembalamiento, CIC-16, falla cerrada sin lecturas. Corrige lo ALTA y MEDIA; lo BAJA al informe.

## Cierre
- Suite completa en verde.
- `CLAUDE.md`: sección corta «Tanda 35: cascada integral (CRI)» y una línea en «Tanda 33» que diga que el tope de banda `techo - 2` y el umbral `p_ref - 2` de ESTERILIZACION quedaron reemplazados; en PAM, que PAM-06 se retiró.
- Riesgos HAZ-CRI-01 y HAZ-CRI-02 en `docs/riesgos/registro_riesgos.md`; trazabilidad con los siguientes REQ libres (uno por CRI-01..04); bloque CRI en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` con las mediciones de CRI-H1 (subida de chaqueta con `vapor_camara` cerrada y caída de cámara sin vapor con el escape lento abierto, carga de líquidos).
- Informe `docs/informes/tanda35/R_informe.md`: cambios, tabla de planta antes y después (16 combinaciones y ciclos completos), pruebas modificadas, hallazgos del revisor, `DECISIÓN SIN CONFIRMAR`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda35/CERRADO.txt` (fecha, commit del merge, resultado de la suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.
