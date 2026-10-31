# Prompts para Claude Code — barra de arranque real

Plan de referencia: `planeacion_barra_arranque_real.md` (§13). Orden: P1 → P2 → P2b → P3 → P4 → P5. P2b, P3 y P4 son independientes entre sí. P4 (sin BD) debe estar antes del 19-oct (D-H). Cada prompt termina esperando aprobación antes de implementar o hacer commit.

---

## P1 — Commits de la fase B (F0)

```
Contexto: fase B (arranque por etapas, GET /arranque) y cierre de ARR-01 implementados, sin commit. Lee docs/informes/informe_fase_b_arranque_backend.md y docs/informes/informe_fase_b_cierre.md.

Prepara los commits, sin hacer push:

1. Commits separados, en este orden: (a) E0/E1 + buzer.py; (b) fase B (arranque por etapas, /arranque, build_serial, middleware 503, códigos ARR_*, test_arranque_sin_tarjeta.py); (c) renombrado ARR-01 (Arranque → Reposo); (d) documentación (planes, informes y catálogo de alarmas).
2. En context.py, server.py, catalogo_alarmas.md y planeacion_arranque_y_modo_sin_bd.md, separa los bloques de E0/E1 de los de la fase B con git add -p.
3. Después de CADA commit, corre la suite completa con ese commit solo (git stash --keep-index para dejar fuera lo no incluido). Debe pasar sin fallos. Si un commit intermedio falla porque los bloques no se pueden separar, no lo fuerces: para y dime cuáles son, para decidir si se unen.
4. Mensajes de commit en español, con el hallazgo o la decisión que cubren (ARR-01, D-E, etc.).

Antes del primer commit, muéstrame el plan: qué bloques de cada archivo mixto van en cuál commit. Espera mi aprobación.
```

---

## P2 — Lanzador único y cliente de progreso real (F1 + F2)

```
Lee docs/mis_plans/planeacion_barra_arranque_real.md completo (§4, §5, §6, §13) y docs/mis_plans/planeacion_animacion_arranque.md (§5 y §6).

Objetivo: que la barra de la intro siga el arranque real, sin cambiar IntroArranque.qml.

Alcance F1 (lanzador único, sin heartbeat, ticket ni retiro de tkinter):
- Nuevo modo del lanzador (en ui_qml/lanzar.py o un módulo propio) que: comprueba perfil de instalación y reloj (ARR_PERFIL, ARR_RELOJ), libera procesos previos (backend_guard.cleanup_stale_backend), abre las dos pantallas primero y luego lanza el backend como subproceso independiente.
- Publica cada etapa en data/arranque_lanzador.json (escritura atómica: temporal, fsync, os.replace) con etapa, estado y codigo.
- Espera el backend con GET /arranque, no con /status (BAR-08). Si el backend termina, lo informa en el archivo (ARR_SIN_BACKEND) y no lo reinicia.
- Si una pantalla se cierra, la relanza hasta 3 veces con 5 s de espera. El backend nunca se reinicia por eso.
- Si falta el perfil, invoca el asistente tkinter solo de forma transitoria; se reemplaza en P2b (D-F). No lo modifiques.

Alcance F2 (ProgresoArranqueReal):
- Clase con la misma interfaz QML que SimuladorProgresoArranque: fraccion, proceso, terminado, falloBloqueante.
- Fuente: GET /arranque cada 200-250 ms cuando responde; si no, data/arranque_lanzador.json. fraccion = max(anterior, nueva): nunca retrocede.
- Etapa 9 (preparando_interfaz): la completa cada UI localmente. terminado de /arranque excluye esa etapa; la UI lo combina con la suya.
- Sin respuesta de ninguna fuente durante 20 s: falloBloqueante con ARR_SIN_BACKEND.
- Textos arranque.<clave> de las 9 etapas en es.json, reemplazando las 4 claves del simulador (conserva fallo_titulo, fallo_bloqueante y sin_progreso). No hay en.json: no lo crees (BAR-09).
- app.py usa el cliente real; AUTOCLAVE_INTRO_SIMULACION se conserva solo para pruebas.
- Etapa 8 (D-G, oculta hasta F3): no la muestres en la barra ni en ningún texto. Debe quedar en el registro marcada como oculta, sin peso y sin texto, y reactivable con un solo cambio cuando F3 la haga real. Propón cómo ocultarla sin alterar el contrato de /arranque ni la monotonía de la barra.

Reglas: tiempos con time.monotonic(); no toques el control, los sensores ni el backend de arranque salvo lo estrictamente necesario; nada de commit.

Primero entrégame, en español, una propuesta con: diseño de las clases y del archivo de estado, cómo manejas el relanzado y la salida del lanzador, qué pruebas escribes (incluye fallo bloqueante inducido en cada etapa, backend caído, sin tarjeta y puerto 8000 ocupado) y qué riesgos ves. Espera mi aprobación antes de escribir código.
```

---

## P2b — Migrar el asistente de instalación a QML (F1b)

```
Aplica la skill auditor-iec62304 antes de proponer: el asistente decide el perfil de instalación del equipo (código de seguridad).

Lee installation/wizard.py, installation/profile.py, installation/storage.py y docs/mis_plans/planeacion_barra_arranque_real.md §13 (F1b, D-F).

Objetivo: reemplazar el asistente tkinter (4 pasos: serie y código de activación, perfil de equipo, puertas, suministro y sondas) por pantallas QML, sin cambiar qué perfil se escribe ni cómo se valida el código de activación.

Entrégame primero, en español, una propuesta con: inventario de cada campo y validación actual del asistente (tal como están en el código, sin suponer); diseño de las pantallas con los teclados QML existentes; cómo se integra con el lanzador (etapa 1) y con el splash; qué pasa si el usuario cierra el asistente a medias; pruebas (incluye paridad: mismas entradas deben producir el mismo perfil que el asistente tkinter); y riesgos. Espera mi aprobación antes de escribir código. Nada de commit ni de borrar wizard.py.
```

---

## P3 — Etapa 8 real: verificación de sensores (F3) — después del 19-oct

```
Antes de proponer cambios, aplica la skill auditor-iec62304 para evaluar el impacto normativo (código de seguridad: sensores, arranque).

Lee docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md §6 y docs/mis_plans/planeacion_barra_arranque_real.md §13 (F3, BAR-06).

Objetivo: que la etapa verificando_sensores compruebe de verdad los canales, con una sola validar_canal() usada en el arranque y en la supervisión continua.

Incluye: criterios a-d de §6 (None, crudo, rango de plausibilidad, 3 tramas válidas), corrección de SEN-01 y SEN-03, umbrales de crudo por canal en configuración (valores iniciales pendientes de prueba de banco), y la clasificación de canales ya aprobada (bloqueante, bloqueante si el equipo tiene puerta con empaque, bloqueante solo con F0, degradable). La etapa debe usar los códigos de fallo del catálogo de alarmas y agregar los nuevos.

Riesgo conocido: en presión, un lazo abierto puede ser indistinguible de la presión mínima hasta la prueba de banco. Documéntalo, no lo ocultes.

Entrégame primero una propuesta en español (diseño, archivos, pruebas, riesgos, impacto en la matriz 62304) y espera mi aprobación. Nada de commit.
```

---

## P4 — Modo sin base de datos (F4) — antes del 19-oct

```
Lee docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md §7 completo (7.1 a 7.8) y docs/mis_plans/planeacion_barra_arranque_real.md §13 (F4).

Objetivo: que la etapa abriendo_base_datos sea degradable de verdad: sin base, el equipo corre ciclos base con alarma OPERANDO_SIN_BD, sin operador identificado, con confirmación por ciclo y las restricciones de 7.6. Reemplaza el 409 provisional de /cycle/start y backend/arranque/sin_bd.py.

Orden sugerido: CycleLogger protegido (BD-02), respaldo por ciclo (7.4), contador y UNIQUE (7.5), marcado de ciclos interrumpidos, login sin base (7.6), base corrupta (7.7). Cada subpaso termina con suite verde.

Entrégame primero una propuesta en español dividida en subpasos, con pruebas y riesgos, y espera mi aprobación. Nada de commit.
```

---

## P5 — Pesos medidos, integración y cierre (F5)

```
Lee docs/mis_plans/planeacion_barra_arranque_real.md §10 y §13 (F5).

1. Mueve los pesos de las etapas de backend/arranque/registro.py a una tabla de configuración. Con el log de transiciones (t_inicio), entrégame un script que calcule la duración de cada etapa en N arranques y proponga pesos proporcionales.
2. Pruebas de integración: lanzador + backend + dos UI (simulador de fallos), cubriendo los criterios de §10 de este plan y de planeacion_animacion_arranque.md (§10.3 y §10.4).
3. Lista de comprobación de la prueba manual en el equipo: con y sin tarjeta, sin base de datos, puerto 8000 ocupado.
4. Actualiza la matriz de cumplimiento 62304: códigos ARR_*, GET /arranque, validar_canal(), riesgos R-ARR-01 a R-ARR-05.

Propón primero y espera mi aprobación. Nada de commit.
```
