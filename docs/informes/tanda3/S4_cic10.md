# S4 — CIC-10: estado seguro detenido (opciones A + B; nunca C)

## Hecho
- **A.** Texto de CIC-10 en el catálogo: "Revise la sonda Principal o asigne otra sonda como Principal en OPCIONES › Parámetros del ciclo › Sensores (técnico o ingeniero)…". El aviso de la UI (`SeccionEstadoSeguro.qml`) muestra el motivo + esa instrucción (`sistema.estado_seguro_detenido_accion`, es/en). El catálogo de alarmas es solo en español (sin versión en inglés hoy).
- **B.** Botón "Asignar sonda Principal" en el aviso: abre OPCIONES (con su login; el endpoint de roles exige técnico/ingeniero y verifica que la sonda elegida tenga lectura, `SENSOR_NO_DISPONIBLE`). "NO ABRIR" sigue vigente. `/status.estado_seguro.bloqueado_motivo` expone el motivo.
- **C no implementada.**

## Verificación pedida: ¿un cambio de rol libera el estado seguro detenido?
Hallazgo: NO lo liberaba. El protocolo (`ProtocoloFallo`), `_programa_ultimo_ciclo` y `_recuperacion_pendiente` guardan una COPIA del programa con la asignación vieja; `put_sensor_roles` solo actualizaba el programa almacenado. Corrección: `ControlLoop.aplicar_roles_sensores()` actualiza esas copias bajo `_sm_lock`, nunca durante CICLO (la instantánea del ciclo se conserva), solo para el mismo programa y solo tras la verificación de lectura del nuevo Principal. Pruebas (`tests/test_s4_cic10.py`): Principal sin lectura detiene; el cambio de rol libera; un nuevo Principal caliente NO libera la cámara segura; no toca la instantánea en CICLO ni otros programas.

## DECISIONES SIN CONFIRMAR
1. El botón se muestra a cualquier usuario y lleva al login (no se oculta por rol); el backend impone el rol. Alternativa: ocultarlo sin sesión técnica.
2. El botón solo abre OPCIONES; el técnico navega a Parámetros del ciclo › Sensores (no se salta directo a esa sección).
3. Riesgo aceptado ya descrito en la propuesta: la sonda de reemplazo puede ser menos representativa (HAZ-LIQ-01 en líquidos).

## Revisión (safety-reviewer) y correcciones
- SAF-01 (Alta): el cambio de rol podía liberar el estado seguro con una sonda más fría que la carga. Corregido: `aplicar_roles_sensores` solo propaga si el nuevo Principal tiene lectura válida y NO es menor que ninguna otra sonda con lectura menos 2 °C; si no, el estado seguro sigue detenido y el endpoint devuelve `estado_seguro_propagado: false` (auditado con `motivo_propagacion`).
- SAF-02 (Media): ya no se muta la instantánea del ciclo terminado; el protocolo/último ciclo/recuperación usan una copia superficial con la nueva asignación.
- SAF-03 (Media): la actualización va por `id` del programa (no por identidad de objeto), saltando solo `control_loop.cycle`, que ya actualiza el endpoint.
- SAF-04 (Baja): el botón solo aparece cuando el motivo es el sensor Principal (no con el timeout líquido).
- Nota: el aviso de "freno por paro" de `abrirConfiguracion` sigue (decisión U4-3 previa).
- Las claves i18n retiradas por U5 (`menu.secado_*`) van en el mismo commit que las de S4 (mismo archivo).
