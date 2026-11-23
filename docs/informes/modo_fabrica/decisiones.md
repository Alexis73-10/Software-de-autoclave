# Modo fábrica: decisiones tomadas para ejecutar sin supervisión

Fecha: 22-nov-2026. Cristian ordenó ejecutar la planeación «de forma autónoma» sin responder antes las preguntas abiertas.

Cada decisión de este archivo es una `DECISIÓN SIN CONFIRMAR`. Se tomó la recomendación del plan o de la revisión (`R_revision_plan.md`). Donde ya había una decisión aprobada (D-xx), manda esa.

## Preguntas abiertas del plan (sección 11, renombradas PA-xx)

| Pregunta | Decisión tomada |
|---|---|
| PA-01 | Tickets y PDF se generan como siempre en FÁBRICA, sin marca. |
| PA-02 | Sin marca externa en el registro de Windows. Se acepta FAB-03, reforzado con DF-02. |
| PA-03 | El informe de liberación lleva espacio de firma para el ingeniero que libera y para quien aprueba. |
| PA-04 | El ciclo con carga real en FÁBRICA no se bloquea. |
| PA-06 | **Rige D-11** (decisión aprobada): al cerrar, las cuentas semilla quedan con la contraseña inicial y cambio obligatorio, con SIS-07 activo. La opción b) (fijar las contraseñas en el cierre) queda pendiente de Cristian; cambiar a ella cuesta poco (`fijar_claves_instalacion` sobre la base nueva). |
| PA-07 | Sí. En ENTREGADO, un programa de usuario nuevo toma el número `max(11, mayor de usuario + 1)`. Los programas existentes no se renumeran. |
| PA-08 | Sí. La fila `equipo_instalado` se copia a la base nueva junto con «Equipo liberado de fábrica». |
| PA-09 | Sí. El catálogo de carga se borra en el cierre. |

## Diseño (DF-xx)

- **DF-01. Persistencia.**
  - Tabla `estado_fabrica` (migración v16) de una fila: `id = 1`, `estado` ('FABRICA' | 'ENTREGADO'), `fecha_liberacion`, `hash_paquete`, `creado`.
  - **Sin fila = ENTREGADO**: toda lectura que falle o no encuentre la fila da ENTREGADO.
  - Triggers: la fila no se borra, y una fila en ENTREGADO no se modifica.
  - La migración inserta ENTREGADO si la base ya tiene ciclos o una fila `equipo_instalado` (equipos ya instalados, P-01). Una base nueva y vacía queda sin fila.
  - `etapa_cierre` no va en la base (R-02).
- **DF-02. Entrada a FÁBRICA (R-01).**
  - Solo la escribe el asistente al terminar, y solo si se cumplen tres condiciones:
    1. El código es de primera instalación: v2 de tipo `INS` (un `REI` nunca). **Corrección SAF-04** (revisión de seguridad, 22-nov): un v1 ya no cuenta; antes «v1, o v2 de tipo `INS`».
    2. La tabla no tiene fila.
    3. La base no tiene ciclos ni una fila `equipo_instalado` anterior.
    4. **Corrección SAF-04:** no hay evidencia de ENTREGADO fuera de la base (`parametros_fabrica_equipo.json` o `calibracion_fabrica_equipo.yaml` en la carpeta de datos).
  - La fila FÁBRICA y `equipo_instalado` se escriben en la misma transacción.
  - Si falla, el equipo queda en ENTREGADO, la dirección segura frente a FAB-01, y queda en el log.
- **DF-03. Lectura.**
  - El backend lee el estado al abrir el contexto y lo publica en `/status.modo_fabrica` (bool).
  - Sin base o con un error, `false`.
  - La interfaz nunca lo deduce.
- **DF-04. Protección.**
  - Toda ruta de fábrica exige el rol ingeniero y el estado FÁBRICA, y responde 409 `solo_modo_fabrica` en ENTREGADO, para todos los roles.
  - La interfaz no muestra esas funciones en ENTREGADO.
- **DF-05. Cierre en dos tiempos (R-02).**
  - **Con el equipo en marcha:** validar las precondiciones, generar el paquete en la USB y verificarlo, consolidar en temporales (`*.fab_nuevo`) y construir `autoclave.db.nueva`. Luego escribir la marca `cierre_fabrica.json` junto a la base (punto de no retorno) y reiniciar el software.
  - **Al arrancar, antes de abrir cualquier `DbManager`:**
    - Con marca: reemplazar los archivos, sobrescribir con ceros y eliminar la base vieja, borrar los registros, poner los contadores en cero y borrar la marca. Cada paso es idempotente.
    - Sin marca: borrar los temporales que hayan quedado.
  - Se rechaza en modo sin base o con `BD_BLOQUEADA`.
- **DF-06. Lista de programas borrados (R-03).** `cycles/user/fabrica_borrados.lst` (un `cycle_id` por línea). El cargador no carga desde `factory/` un programa que esté en esa lista, tampoco los cinco heredados, y la siembra no lo recrea.
- **DF-07. Calibración del equipo (R-05).**
  - `calibracion_fabrica_equipo.yaml` guarda la sección `user` vigente por función de sensor.
  - «defecto» restaura ese valor y solo usa el neutro si el archivo no existe o no tiene ese sensor.
- **DF-08. Manifiesto con tipo (R-06).** `tipo` vale «respaldo» o «liberacion». Un manifiesto sin `tipo` se trata como «respaldo». La restauración rechaza todo lo que no sea «respaldo» con 422 `paquete_no_restaurable`.
- **DF-09. Mantenimiento (R-04).** El cierre deja `mantenimiento_base.json` en `{"ciclos_instalacion": 0}` y conserva `mantenimiento.json` (los intervalos).
- **DF-10. Numeración (FAB-09).** El cierre quita del 1 al 10 de `numeros_usados.json` y conserva los mayores.
