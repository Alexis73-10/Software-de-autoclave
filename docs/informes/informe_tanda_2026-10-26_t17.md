Tanda 17: hallazgos instalación I — suite 8488 passed (base 8234), unida a dev: sí, entrega: 1.0.0-alpha.2.

# Índice — tanda 17 (26-oct-2026)

- Recolectadas: 8501 (base 8251 + 250 nuevas). En `tanda-17` (árbol idéntico a `dev` tras la unión `584aa7a`): 8486 pasan en paralelo; 2 fallan solo en paralelo y pasan en serie. La falla preexistente de la tanda 16 (`test_ver_entrega::test_historial_entrada_debajo_de_la_marca`) quedó corregida en A1.
- Entrega: **`1.0.0-alpha.2`** (`61f06fa`, etiqueta `v1.0.0-alpha.2`), en `entrega/v1.0.0-alpha.2_2026-10-26/`. Setup SHA-256 `46b1525ff8c30605384e5ec1b1b951f5b4c29fbfc49ab1f35126288ce018cd4d`. El primer intento lo detuvo el sistema por memoria baja; se relanzó con orden de Cristian (suite del script: 8488 passed). Publicar: `git push origin dev v1.0.0-alpha.2` (R17 §8).
- **La alpha.2 no actualiza la compilación I ni la alpha.1**: desinstalar e instalar en limpio, sin migración de datos (INS-02, D-17.2b).
- Informe completo: `docs/informes/tanda17/R17_informe.md`. Estado: `docs/informes/tanda17/estado.md`. Línea base: `docs/informes/tanda17/base_suite.txt`. V, P y R: `V_resumen.md`, `P_resumen.md`, `R_hallazgos.md`.
- Anomalías de la próxima entrega: `docs/versiones/anomalias_conocidas_1.0.0-alpha.2.md` (en `dev`, `a51a120`).
- Hoja de banco: bloque I en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (pruebas manuales del PC de prueba: zona horaria, unidad D:, ACL, actualización, bloqueo de la disposición anterior, táctiles, cubierta de arranque, SON-01, ESG-01/02, pantallas, bitácora).
- Para confirmar con Cristian: V17-s3-03 (`salida_prueba_cortada` fuera de la bitácora), la clave huérfana `bitacora.desde_formato` (D-19) y las DECISIONES SIN CONFIRMAR (R17 §11).
- Push: solo la rama `tanda-17`; `dev` y la etiqueta quedan locales (los sube Cristian: `git push origin dev v1.0.0-alpha.2`).
