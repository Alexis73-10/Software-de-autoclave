Tanda 16: pendientes 14 + VCH + PRG-01 + DEU-01 — suite 8234 passed (base 7908), unida a dev: sí, entrega: no.

# Índice — tanda 16 (26-oct-2026)

- Recolectadas: 8251 (base 7922 + 329 nuevas). En `dev` tras la unión: 8234 pasan en paralelo; 3 fallan solo en paralelo y pasan en serie; 1 falla preexistente de `dev` (`test_ver_entrega::test_historial_entrada_debajo_de_la_marca`, desde la entrega alpha.1).
- Entrega: **no**. `compilar_entrega.py` exige la suite en verde y la falla preexistente lo bloquea; ver R16 §8 (qué corregir para sacar la `1.0.0-alpha.2`).
- Informe completo: `docs/informes/tanda16/R16_informe.md`.
- Estado por etapa: `docs/informes/tanda16/estado.md`. Línea base: `docs/informes/tanda16/base_suite.txt`.
- Anomalías de la próxima entrega: `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md` (VCH-01 ALTA: reajustar en el banco los parámetros de CALENTAMIENTO y ESTERILIZACION con la chaqueta antes de liberar).
- Hoja de banco: bloque H en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`.
- Push: solo la rama `tanda-16`; `dev` y las etiquetas `archivo/*` quedan locales (las sube Cristian: `git push origin dev` y `git push origin --tags` si lo decide).
