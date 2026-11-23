# Planeación — Modo fábrica y liberación del equipo

Proyecto: Software de Autoclave — Especifika S.A.S.
Archivo: `docs\mis_plans\planeacion_modo_fabrica.md`
Versión: v2 (borrador para aprobación) — 22-nov-2026
Clasificación de seguridad del software: Clase C (NTC-IEC 62304)
Base revisada: código local, rama `dev`, 22-nov-2026 (solo lectura). La v2 reemplaza a la v1 (redactada sin revisar el código).

---

## 1. Objetivo

Cada equipo fabricado pasa por calibración de sensores, ajuste de parámetros y ciclos de prueba antes de entregarse. Lo que se ajusta en esa etapa (parámetros, programas y calibración) debe quedar como base de fábrica de ese equipo. Los ciclos de prueba, la bitácora y todo registro generado durante las pruebas deben desaparecer del equipo, que se entrega limpio, como nuevo. La evidencia de las pruebas se conserva fuera del equipo, en un paquete de liberación que archiva Especifika.

---

## 2. Decisiones aprobadas (21 y 22-nov-2026)

- D-01. No es un usuario ni una firma, sino un estado del equipo: FÁBRICA → ENTREGADO, en un solo sentido. No existe transición de ENTREGADO a FÁBRICA.
- D-02. Solo un usuario con rol ingeniero (Especifika) opera las funciones de fábrica y ejecuta el cierre.
- D-03. El modo fábrica es independiente de la licencia o activación por pago. Ninguno de los dos lee ni modifica el estado del otro.
- D-04. Antes del borrado se exporta un paquete de liberación con todo, incluida la bitácora completa.
- D-05. Los programas creados en FÁBRICA son programas de fábrica, en el rango 1–10, con un máximo de 10.
- D-06. En FÁBRICA se pueden borrar programas de fábrica que el cliente no necesita (por ejemplo, B&D en laboratorios que no ejecutan esa prueba).
- D-07. La numeración de fábrica es fija: borrar un programa deja su número vacío, sin correr los demás. Un programa nuevo toma el primer número libre entre 1 y 10.
- D-08. Los parámetros y la calibración ajustados en FÁBRICA reemplazan a los valores de fábrica genéricos. En campo, "restaurar valores de fábrica" vuelve a los valores ajustados de ese equipo.
- D-09. El cierre borra ciclos y gráficas, bitácora, PDFs y tickets, cola de correo, mantenimiento, alarmas y fallos, logs, y los usuarios y operadores creados en las pruebas.
- D-10. Todos los contadores vuelven a cero.
- D-11. Las cuentas semilla `Admin` e `Ingeniero` quedan con la contraseña inicial y cambio obligatorio en el primer ingreso (ver FAB-11).
- D-12. Tras el cierre queda un único registro en la bitácora: que el equipo fue liberado de fábrica y la fecha.
- D-13. Mientras el equipo esté en FÁBRICA, la pantalla muestra una franja fija con el texto "MODO FÁBRICA", sin más texto.
- D-14. Un equipo entra en FÁBRICA solo en la primera instalación. Reinstalar o actualizar conserva el estado. El reacondicionamiento de un equipo devuelto a planta queda fuera de esta spec.

---

## 3. Lo que hay hoy en el código (relevante para esta spec)

- Base de datos: SQLite (`data/autoclave.db`, en el compilado `datos\` del registro `HKLM\SOFTWARE\Especifika\Autoclave\RutaDatos`), con migraciones por `PRAGMA user_version` en `services/domain/logging/db_manager.py`. Tablas: `ciclos`, `lecturas`, `lecturas_grafica`, `ciclo_fases`, `alarmas_historial`, `audit_log`, `mantenimientos`, `system_params`, `operadores`, `usuarios`, `catalogo_carga`, `ciclo_carga`, `cycle_params_audit`, `sensor_calibration_audit`.
- Triggers de solo anexar: `audit_log`, `mantenimientos`, `operadores`, `usuarios` y `catalogo_carga` tienen triggers que impiden DELETE (y UPDATE en algunos casos). Hay además triggers que protegen las cuentas del sistema.
- Programas, como archivos JSON:
  - `cycles/factory/`: los genéricos que vienen con el .exe (6: B&D, Instrumental 121, Instrumental 134, Líquidos, Prion, Textiles).
  - `cycles/user/`: las copias de trabajo del equipo, más `numeros_usados.json` (números retirados, que nunca se reutilizan) y `fabrica_vistos.lst` (programas de fábrica ya sembrados, para no recrear los que se borren).
  - `cycles/defecto/`: "defectos" propios del equipo, que mandan sobre los de fábrica (`CycleManager.defecto(n)`).
  - Una actualización de software siembra en `cycles/user` los programas de fábrica nuevos (PRI-05).
- Parámetros del sistema: tabla `system_params`. El valor de fábrica sale de `config/global_params.json` (`ConfigManager._fabrica`). "Restaurar" usa ese valor.
- Calibración: `calibration_modbus.yaml` (copia de trabajo en `data/`). `POST /calibration/{tipo}/{sensor}/restaurar` admite dos destinos: `"defecto"` (neutro: ganancia 1,0, offset 0,0) y `"ultimo"` (el valor anterior, leído de `audit_log`).
- Contadores y mantenimiento: `data/ciclo_contador.json` (`{"ultimo": N}`), `data/mantenimiento.json` y `data/mantenimiento_base.json`.
- Respaldo por ciclo: `data/respaldo_ciclos/<uuid>.jsonl` y `importados/`. Al arrancar, los pendientes se reimportan a la base. La regla vigente dice "nunca se borra un respaldo".
- Respaldo por USB (`core/runtime/respaldo.py`): ZIP con `manifiesto.json`, SHA-256 por archivo y hash del manifiesto. Ya resuelve la escritura, el hash y la validación en USB.
- Instalación: el asistente exige el código de instalación (`activacion_v2.verificar_codigo_instalacion`, con doble autorización en el generador), fija las contraseñas de las dos cuentas del sistema (LIC-02, `fijar_claves_instalacion`) y escribe una sola fila `equipo_instalado` (serie, modelo, versión, zona horaria). Antes de eso no se escribe nada en la bitácora (`SupresionInstalacion`).
- Número de serie: existe en el perfil y en la fila `equipo_instalado`.

---

## 4. Hallazgos

- FAB-01 (crítico). Una función que borra la bitácora y los ciclos sirve, en campo, para falsificar registros de esterilización. Mitigación: el borrado solo existe en FÁBRICA. El backend rechaza la operación en ENTREGADO para todos los roles, y la interfaz no la muestra.
- FAB-02 (alto). Los registros de calibración y de los ciclos de prueba son el registro de liberación del dispositivo, y la ISO 13485 exige conservarlos. Mitigación: el paquete de liberación se genera y verifica antes de borrar. Si falla, no se borra nada.
- FAB-03 (alto). Riesgo de que un equipo entregado vuelva a FÁBRICA si en campo se borra o se daña la base de datos. Mitigación: FÁBRICA solo se activa al terminar el asistente de instalación, y el asistente exige el código de instalación con doble autorización de Especifika. Una base recreada por cualquier otra vía (corrupción, modo sin base, borrado manual) nace en ENTREGADO. Ver P-02.
- FAB-07 (crítico de diseño). Los triggers de solo anexar impiden el DELETE de la bitácora, el mantenimiento, los operadores y los usuarios. El cierre NO debe desactivar triggers: un camino de código que los quite es justo la puerta que FAB-01 quiere cerrar. Mitigación: el cierre no borra filas. Crea una base nueva desde cero (esquema vigente, semillas y triggers), importa solo lo que debe quedar (sección 6.4) y reemplaza el archivo de forma atómica. El archivo viejo se sobrescribe con ceros y se elimina (mejor esfuerzo: en SSD la sobrescritura no está garantizada a nivel físico; se acepta). Con esto ya no hace falta `VACUUM`: la v1 de FAB-04 queda reemplazada.
- FAB-08 (alto). "Restaurar calibración" hoy no tiene un destino de fábrica del equipo. `"defecto"` lleva el sensor a neutro (1,0 / 0,0), lo que en un equipo calibrado deja una lectura sin corregir. `"ultimo"` depende de `audit_log`, que queda vacío tras el cierre. Mitigación (D-08): el cierre guarda la calibración de fábrica del equipo en un archivo aparte, y `"defecto"` pasa a restaurar esa calibración. El neutro solo se usa si el archivo no existe (equipos anteriores a esta función). Tras el cierre, `"ultimo"` responde 409 `sin_calibracion_previa` hasta el primer cambio en campo. Ese comportamiento es correcto.
- FAB-09 (medio). La numeración de programas no coincide con D-05 y D-07. `numero_nuevo()` asigna mayor + 1 (no reserva 1–10 para fábrica ni arranca los de usuario en 11), y todo número borrado va a `numeros_usados.json`, que impide reutilizarlo. En FÁBRICA, crear y borrar programas necesita reglas propias (sección 5.3). Ver P-07.
- FAB-10 (crítico). Si el cierre borra la base pero deja `data/respaldo_ciclos/`, en el siguiente arranque los ciclos de prueba se reimportan a la base nueva. Mitigación: el cierre borra `respaldo_ciclos/` completo (pendientes e `importados/`). La regla "nunca se borra un respaldo" recibe una única excepción documentada: el cierre de fabricación.
- FAB-11 (medio). D-11 contradice LIC-02. Hoy el asistente obliga a fijar contraseñas propias para las cuentas del sistema, y el aviso SIS-07 se dispara si alguna conserva la contraseña semilla. Si el cierre devuelve las semillas, el equipo llega al cliente con contraseñas públicas hasta el primer ingreso (con SIS-07 activo). Ver P-06.
- FAB-12 (bajo). D-12 deja una sola fila, pero hoy existe la fila `equipo_instalado` con la serie, el modelo, la versión y la zona horaria, que da trazabilidad del equipo. Ver P-08.
- FAB-05 (medio). Un corte de energía a mitad del cierre puede dejar el equipo a medio limpiar. Mitigación: secuencia por etapas con marca de progreso (sección 6.3).
- FAB-06 (bajo). En ENTREGADO, la base de fábrica del equipo (defectos de programas, parámetros y calibración de fábrica) es de solo lectura para todos los roles.
- FAB-13 (bajo). Una actualización futura que traiga un programa de fábrica genérico nuevo lo siembra en equipos entregados (PRI-05). Si su número coincide con un programa de fábrica del equipo, PRI-06 hace que el genérico ceda el número y quede sin número. Se acepta, con aviso en el log. Lo que no se acepta es que una actualización recree un programa borrado en FÁBRICA: los borrados deben quedar en `fabrica_vistos.lst`.

---

## 5. Estados y comportamiento en FÁBRICA

### 5.1 Persistencia

Una tabla nueva de una sola fila, `estado_fabrica` (migración numerada), con estos campos:

- `estado`: 'FABRICA' | 'ENTREGADO'
- `fecha_liberacion`: nula en FÁBRICA
- `etapa_cierre`: entero, nulo si no hay cierre en curso
- `hash_paquete`: SHA-256 global del paquete (no se muestra en la bitácora)

El backend es la única fuente de verdad. `/status` publica `modo_fabrica: true/false` y la interfaz QML nunca lo deduce por su cuenta.

### 5.2 Entrada y determinación del estado

- El asistente de instalación, al terminar con éxito, escribe `estado = 'FABRICA'` en la misma transacción que `equipo_instalado`.
- Una base creada por cualquier otra vía nace con `estado = 'ENTREGADO'`: arranque sin base, recuperación, migración de una base existente sin la tabla, o recreación por corrupción.
- Migración de equipos ya instalados: la tabla se crea con ENTREGADO. Los equipos actuales no entran en FÁBRICA con la actualización.
- Si `etapa_cierre` no es nula al arrancar, se reanuda el cierre antes de mostrar el menú principal.
- No existe ningún endpoint, rol, parámetro, archivo ni instalador que pase de ENTREGADO a FÁBRICA.

### 5.3 Funciones exclusivas de FÁBRICA (solo rol ingeniero)

Programas:
- Crear un programa de fábrica: número = primer libre del 1 al 10, sin consultar `numeros_usados.json`. Con 10 ocupados, rechazo 409 `maximo_programas_fabrica`. El archivo va a `cycles/user/` con la marca `"fabrica_equipo": true` y sin `"personalizado"`.
- Borrar un programa de fábrica (genérico sembrado o creado en FÁBRICA): borrado físico del archivo de `cycles/user/` y de su defecto. El número NO se registra en `numeros_usados.json`. El `cycle_id` del genérico se conserva en `fabrica_vistos.lst` (FAB-13).
- Mientras el equipo esté en FÁBRICA no se crean programas de usuario. Duplicar en FÁBRICA crea un programa de fábrica.
- Editar parámetros de programas: igual que hoy.

Cierre de fabricación: sección 6.

### 5.4 Operación en FÁBRICA

- Ciclos, calibración, modo prueba, mantenimiento y reportes funcionan igual que en ENTREGADO, y todo se registra con normalidad, porque alimenta el paquete.
- Ninguna protección de seguridad cambia: enclavamientos, modo prueba, paro de emergencia, cámara segura.
- La licencia sigue su propia spec (D-03).
- Franja "MODO FÁBRICA" fija en todas las pantallas, incluida la de ciclo. Su ubicación se valida con la skill revision-visual-pantallas.

---

## 6. Cierre de fabricación

### 6.1 Precondiciones (las verifica el backend)

- Estado FÁBRICA y sesión con rol ingeniero.
- Estado operativo PREPARADO o PREPARACION, sin FALLA, sin paro, sin confirmación pendiente y sin modo prueba.
- Cámara sin presión.
- USB conectada, con escritura disponible y espacio suficiente (se reutiliza la detección de `respaldo.py`).
- Pantalla de resumen de lo que se borra y lo que queda, seguida de reautenticación con la contraseña del ingeniero (mecanismo `reautenticacion_requerida` existente).

### 6.2 Secuencia

1. Validar las precondiciones.
2. Generar el paquete de liberación en la USB (sección 7), releerlo y verificar los hashes. Si algo falla: abortar, sin cambios.
3. Consolidar la base de fábrica del equipo, en archivos temporales:
   - Programas: escribir en `cycles/defecto/<id>.json` los valores vigentes de cada programa que queda, y borrar los defectos de programas que ya no existen.
   - Parámetros: escribir `datos\parametros_fabrica_equipo.json` (clave → valor vigente). `ConfigManager` lo carga sobre `global_params.json` como valor de fábrica.
   - Calibración: copiar la calibración vigente a `datos\calibracion_fabrica_equipo.yaml` (FAB-08).
4. Construir la base nueva en un archivo temporal: esquema vigente, triggers, semillas (D-11, sujeto a P-06), `system_params` con los valores vigentes, `estado_fabrica` con ENTREGADO, `fecha_liberacion` y `hash_paquete`, y la única fila de bitácora (D-12, sujeto a P-08). Nada más se importa.
5. Guardar `etapa_cierre` en la base vieja (punto de no retorno).
6. Reemplazar de forma atómica los archivos consolidados (paso 3) y la base (paso 4), con `os.replace` y los `-wal`/`-shm` cerrados.
7. Sobrescribir con ceros la base vieja y eliminarla (FAB-07).
8. Borrar los archivos de registro (sección 6.4) y poner los contadores en cero.
9. Vaciar `numeros_usados.json` (salvo P-07).
10. Reiniciar el software (mecanismo de reinicio existente, con todo apagado).

### 6.3 Reanudación (FAB-05)

- Corte antes del paso 5: el equipo sigue en FÁBRICA, intacto. Se borran los temporales en el siguiente arranque y el cierre se repite completo.
- Corte después del paso 5: en el siguiente arranque, la pantalla de arranque completa los pasos pendientes, del 6 al 10, antes de mostrar el menú principal. Cada paso es idempotente.

### 6.4 Qué se borra y qué se conserva

Se borra (base vieja completa, más estos archivos en `datos\`):
- `respaldo_ciclos\` completo, con `importados\` (FAB-10).
- Tickets, PDFs y exportaciones generadas.
- Cola de correo pendiente (ubicación por confirmar en la Etapa 0).
- Logs: `ui_puerta*.log`, `lanzador.log`, el log de desarrollo y los demás `*.log` del software.
- `ciclo_contador.json`, que vuelve a `{"ultimo": 0}`.
- `mantenimiento.json`, que se reinicia (contadores de servicio en cero).
- `last_shutdown.json` y los respaldos locales de la base (`autoclave.db.bak*`).
- `.bak` de configuración generados durante las pruebas (`asignacion_io.json.bak`, `cycles/user/*.bak`).

Se conserva:
- Perfil de instalación, identidad, serie y modelo; estado de licencia y activación (no se tocan, D-03).
- `asignacion_io.json`, la configuración del módulo E/S y la red.
- La calibración vigente y la calibración de fábrica del equipo.
- Los programas consolidados y sus defectos; `fabrica_vistos.lst`.
- Idioma, unidades, tema, impresora y configuración de correo del equipo.
- `mantenimiento_base.json` (intervalos de servicio), si la Etapa 0 confirma que es configuración y no registro.
- `datos\estacion\` (respaldos de la configuración de Windows de la estación).

---

## 7. Paquete de liberación

Se reutiliza el formato de `core/runtime/respaldo.py` (ZIP, `manifiesto.json`, SHA-256 por archivo y hash del manifiesto), en una carpeta propia: `<USB>\Especifika_liberaciones\liberacion_<serie>_<AAAAMMDD-HHMM>.zip`.

Contenido (D-04, "todo"):
- `informe_liberacion.pdf`: equipo (serie, modelo, versión del software), fecha, ingeniero que liberó, calibración final por sensor, parámetros finales, programas de fábrica con sus parámetros, resumen de los ciclos de prueba (resultado, fallos, alarmas) y contadores al cierre.
- `ciclos\`: PDF de cada ciclo de prueba con su gráfica.
- `historial.db`: copia completa de la base, con la columna `hash_pw` de `usuarios` en NULL dentro de la copia.
- `bitacora.csv`: bitácora completa en formato legible.
- `calibracion.yaml`, `parametros.json`, `programas\*.json`, `asignacion_io.json`.
- `respaldo_ciclos\` y `logs\`.
- `manifiesto.json` (con formato, versión, serie, fecha, usuario y hashes).

En el equipo solo queda el hash global (`hash_paquete`). Especifika archiva el ZIP según su sistema de calidad.

Este paquete no se puede restaurar con "Restaurar respaldo": tiene otra carpeta y otro tipo en el manifiesto, y se rechaza si se intenta.

---

## 8. Estado del equipo tras el cierre

- ENTREGADO, sin franja.
- Programas de fábrica consolidados, con numeración fija y huecos donde se borraron.
- Parámetros y calibración vigentes, iguales a la base de fábrica del equipo. "Restaurar" vuelve a esos valores.
- Solo las cuentas `Admin` e `Ingeniero` (según P-06), sin operadores ni catálogo de carga.
- Sin ciclos, gráficas, alarmas, mantenimientos, tickets, PDFs, respaldos de ciclo ni logs. Contadores en cero.
- Bitácora: "Equipo liberado de fábrica — [fecha]" (más `equipo_instalado` si P-08 lo aprueba).

---

## 9. Riesgos (entradas propuestas para `docs/riesgos/registro_riesgos.md`)

- HAZ-FAB-01: borrado de registros clínicos en campo. Controles: FAB-01, FAB-03, FAB-07. Verificación: P-05, P-06 y P-11.
- HAZ-FAB-02: base de fábrica con valores intermedios o erróneos. Control: consolidación única en el cierre y revisión del informe antes de entregar. Verificación: P-03.
- HAZ-FAB-03: equipo entregado en FÁBRICA por olvido. Control: franja permanente (D-13).
- HAZ-FAB-04: reimportación de ciclos de prueba tras el cierre. Control: FAB-10. Verificación: P-04.
- HAZ-FAB-05: calibración restaurada a neutro en un equipo calibrado. Control: FAB-08. Verificación: P-03.
- HAZ-FAB-06: pérdida de la evidencia de liberación. Control: FAB-02. Verificación: P-07 y P-09.

---

## 10. Pruebas de aceptación

- P-01: una instalación limpia termina el asistente en FÁBRICA, con la franja visible. Una base existente migrada queda en ENTREGADO.
- P-02: en FÁBRICA se crean programas hasta 10 y el undécimo se rechaza. Borrar el 1 lo deja libre y el siguiente programa toma el 1. Tras una actualización simulada, el programa borrado no reaparece.
- P-03: tras el cierre, restaurar parámetros y calibración ("defecto") da los valores consolidados, no el neutro ni los genéricos.
- P-04: tras el cierre y dos reinicios, la base contiene solo las filas de la sección 8. `respaldo_ciclos\` no existe o está vacío. Contadores en cero.
- P-05: en ENTREGADO, todos los endpoints de fábrica responden con rechazo para todos los roles, incluido ingeniero.
- P-06: reinstalar el Setup sobre un equipo ENTREGADO lo deja en ENTREGADO, con sus datos.
- P-07: sin USB, o con una USB llena o protegida, el cierre se rechaza y no cambia nada.
- P-08: corte simulado antes y después del paso 5, con los resultados de la sección 6.3.
- P-09: el manifiesto verifica y `historial.db` del paquete no tiene hashes de contraseña.
- P-10: búsqueda binaria de una cadena conocida de un ciclo de prueba en `datos\` tras el cierre: sin coincidencias.
- P-11: borrar a mano la base en un equipo ENTREGADO: arranca en ENTREGADO, nunca en FÁBRICA.
- P-12: ningún camino del código ejecuta `DROP TRIGGER` sobre los triggers de solo anexar (prueba por AST o búsqueda en el código).

---

## 11. Preguntas abiertas (responder antes de la Etapa 1)

- P-01. Durante FÁBRICA, ¿los tickets y PDFs se generan como siempre? Recomendación: sí, sin marca, porque la franja basta y se borran al cerrar.
- P-02. ¿Aceptas FAB-03 tal como está (FÁBRICA solo al terminar el asistente, que ya exige el código de instalación con doble autorización), sin la marca externa en el registro de Windows que propuse en la v1? Recomendación: sí. La marca externa no agrega nada que el código de instalación no cubra ya.
- P-03. ¿El informe de liberación lleva espacio de firma física (ingeniero y aprobador)?
- P-04. ¿Se permite un ciclo con carga real en FÁBRICA? Recomendación: no bloquearlo, porque la franja cumple ese papel.
- P-06 (FAB-11). Contraseñas al cerrar, elige una:
  - a) Semillas públicas con cambio obligatorio y SIS-07 activo hasta que el cliente las cambie (tu decisión D-11).
  - b) El cierre pide al ingeniero fijar las contraseñas de entrega de `Admin` e `Ingeniero`, como hace hoy el asistente (LIC-02), y se las comunica al cliente al entregar.
  Recomendación: b. Mantiene LIC-02 y evita que el equipo viaje con contraseñas públicas.
- P-07 (FAB-09). En ENTREGADO, ¿los programas de usuario arrancan en 11, como decidiste en el plan del Menú Principal, aunque hoy el código asigna mayor + 1? Recomendación: sí, corregirlo en esta misma tanda, porque con programas de fábrica fijos del 1 al 10 un duplicado no puede caer en el 7.
- P-08 (FAB-12). ¿Se conserva también la fila `equipo_instalado` (serie, modelo, versión y zona horaria) junto a "Equipo liberado de fábrica"? Recomendación: sí. No describe pruebas y es la identidad del equipo.
- P-09. `catalogo_carga` (catálogo de elementos del lector de códigos de barras): ¿se borra al cerrar? Recomendación: sí, porque el catálogo es del cliente y lo cargado en fábrica es de prueba.

---

## 12. Etapas para Claude Code

- Etapa 0 (solo lectura, informe en español): confirmar la ubicación de la cola de correo, los tickets, los PDFs y los logs en el compilado; qué es `mantenimiento_base.json`; el orden de creación de triggers y semillas para construir la base nueva; cómo se cierran los handles de SQLite antes del reemplazo; y cualquier contradicción con esta spec.
- Etapa 1: tabla `estado_fabrica` y migración; `/status.modo_fabrica`; protección de los endpoints; franja QML.
- Etapa 2: programas de fábrica en FÁBRICA (crear, borrar, numeración 1–10, `fabrica_vistos`) y P-07.
- Etapa 3: base de fábrica del equipo (`parametros_fabrica_equipo.json`, `calibracion_fabrica_equipo.yaml`, restaurar "defecto") y solo lectura en ENTREGADO.
- Etapa 4: paquete de liberación.
- Etapa 5: cierre (base nueva, reemplazo atómico, borrado, reanudación) y pantalla de cierre.
- Etapa 6: pruebas P-01 a P-12, riesgos y CLAUDE.md.
