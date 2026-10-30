# Instrucción maestra para Claude Code — Tanda 14-oct-2026 (noche del 14 al 17)

Objetivo: dejar el software listo para la instalación del 19-oct-2026 en el equipo de pruebas (autoclave de laboratorio, 2 puertas abatibles manuales, generador interno, sondas Cámara 1, Cámara 2, Referencia y drenaje) con al menos un ciclo ejecutable y seguro, y avanzar en lo necesario para la entrega como demo. Cristian NO estará presente: nadie responderá preguntas durante la tanda.

## 0. Reglas generales (obligatorias)

1. Informes y comentarios de commit en español. Lenguaje técnico, directo.
2. Primero lee este documento completo y `docs/informes/tanda/estado.md` si existe. Si existe, REANUDA desde la primera etapa no terminada (puede ser una continuación tras un corte o un límite de uso: no repitas lo ya commiteado).
3. Rama: la Etapa 0 se hace en `dev`. Después crea `dev-noche` desde `dev` y trabaja ahí todas las demás etapas. Un commit (o varios) por etapa, solo con los archivos de esa etapa: NUNCA `git add -A` ni `git add .`. No hagas `git push`. No toques `.claude/settings.local.json` ni `.claude/worktrees`.
4. Pruebas primero: toda funcionalidad nueva con pruebas que se vean fallar antes. Registra la línea base de `python -m pytest -q -p no:cacheprovider` al inicio (se espera ~2808 tras F1) y al final de cada etapa. Una etapa solo se commitea con la suite en verde.
5. Si una etapa deja la suite en rojo y no la corriges en 2 intentos: revierte los cambios de esa etapa (sin tocar commits previos), anótalo en el informe como BLOQUEADA y pasa a la siguiente etapa que no dependa de ella.
6. Ambigüedad: no te detengas. Elige el camino más seguro y reversible, anótalo en el informe de la etapa como "DECISIÓN SIN CONFIRMAR" (con alternativa) y sigue. Si una decisión afecta seguridad y no puedes resolverla con lo escrito aquí, deja esa parte sin implementar, anótala como PENDIENTE y continúa.
7. Revisores: al terminar cada etapa de seguridad (Parte A, sensores, E2, E3, E4, E5, modo sin BD, Líquidos) ejecuta los agentes `safety-reviewer` y `timing-auditor` del proyecto. Corrige los hallazgos Alto y Crítico antes del commit; si no puedes, deja la etapa BLOQUEADA y documenta.
8. Tiempos con `time.monotonic()`. Ningún id de alarma existente se renombra. Ninguna acción sobre hardware; no compiles ni cargues firmware.
9. Todo texto nuevo de UI va en `src/autoclave/i18n/es.json` y `en.json` y se lee con `i18n.t` / `I18n.t`. Las traducciones al inglés nuevas se anotan en `docs/mis_plans/revision_traducciones.md` como "sin revisar".
10. Estado y continuidad: después de CADA etapa actualiza `docs/informes/tanda/estado.md` (etapa actual, hecho, pendiente, bloqueadas, commit hash) y escribe `docs/informes/tanda/<id>_<nombre>.md` con: archivos modificados, conteos de pruebas antes/después, hallazgos de los revisores y cómo se resolvieron, DECISIONES SIN CONFIRMAR, PENDIENTES y comprobaciones manuales que debe hacer Cristian. Al final escribe `docs/informes/informe_tanda_2026-10-14.md` (índice).
11. Si una decisión de este documento contradice un borrador de spec en `docs/mis_plans/` (planeacion_endurecimiento_backend_parametros rev 3, planeacion_sensores_ciclo rev 2, planeacion_opciones_parametros_ciclo rev 3.1, planeacion_fin_de_ciclo_y_puertas §17), PREVALECE ESTE DOCUMENTO. Al terminar cada etapa deja una nota "Adenda 2026-10-14" al inicio del borrador afectado indicando qué cambió (sin reescribirlo).
12. Prioridad si el tiempo no alcanza: se completan las etapas en el orden dado; lo último cae primero. Cada etapa terminada debe quedar commiteada.

## 1. Decisiones aprobadas por Cristian (14-oct) — fuente de verdad

### 1.1 Modelo de sensores de temperatura (reemplaza S-1, S-8 y la sección 17 de fin de ciclo)
- Roles por programa (JSON del programa): `principal` (exactamente 1), `referencia` (0 a 2), `no_en_uso` (el resto). Cualquier sensor (`temp_camara`, `temp_2_camara`, `temp_ref`) puede tener cualquier rol. Los nombres visibles son SOLO ubicación física: "Cámara 1", "Cámara 2", "Referencia" (`temp_ref` está abajo de la cámara, lejos de la carga: es el punto más frío). En equipos de laboratorio las dos de cámara son sondas flexibles que se colocan en un líquido o soporte; en equipos normales es PT100 fija.
- Asignación de fábrica en TODOS los programas: Principal = `temp_camara`; `temp_2_camara` y `temp_ref` = no_en_uso.
- El Principal hace todo en sólidos y líquidos: control de vapor, fallas de temperatura, saturación de calentamiento, ticket, F0, enfriamiento (modos 4/5 de descompresión), temperatura de apertura (`temp_max_apertura`), "cámara segura", "NO ABRIR" y apertura automática. Usa el Principal del programa SELECCIONADO en ese momento; si no hay programa seleccionado, el del último ciclo ejecutado; si no hay ninguno, `temp_camara`. Lectura `None` del Principal = cámara NO segura. Registrar en el archivo de riesgos (ISO 14971) que si el técnico asigna como Principal una sonda fría (p. ej. `temp_ref`) el aviso "NO ABRIR" puede ser optimista; sin advertencia en UI.
- Las Referencias no se comparan con el Principal ni entre sí. Solo: (a) condición de ENTRADA a esterilización: todas las sondas en uso (Principal + Referencias) deben estar en la consigna de esterilización, sostenido `tiempo_estable_preesterilizacion` (10 s en Líquidos); (b) durante la esterilización, si una Referencia cae fuera de rango NO se falla: el control sigue solo con el Principal, el tiempo de esterilización cuenta mientras el Principal esté en rango, y se emite una alerta de uniformidad térmica NO bloqueante que queda en el registro. Las temperaturas se evalúan contra la presión de la cámara (saturación) como ya hace el código para el Principal; no se comparan entre sí.
- F0 usa solo la sonda Principal. F0 existe únicamente en equipos de laboratorio (capacidad por clase de equipo: verifica el flag existente, p. ej. `has_liquid_sensor` o clase `*_lab`; si no existe, créalo en `EquipmentCapabilities`): en lab se puede activar/desactivar por ciclo, DESACTIVADO por defecto; en equipos no lab no se ofrece y el backend rechaza activarlo.
- Un sensor en `no_en_uso` NO se lee ni se vigila: no genera SENSOR_AUSENTE, ni alarma bloqueante, ni bloquea nada. Se elimina la vigilancia permanente de `temp_camara` (antiguo S-8). Un sensor EN USO (Principal o Referencia) con lectura `None` durante un ciclo dispara `SENSOR_AUSENTE` → FALLO con el flujo actual (DECISIÓN SIN CONFIRMAR para líquidos con Referencia caída: se aplica el mismo FALLO).
- PREPARACION/PREPARADO: un sensor desconectado genera ALERTA no bloqueante (también `None`, no solo 0; solo sensores declarados por la instalación). El bloqueo ocurre al INICIAR un programa que use ese sensor sin lectura (RS-06). Corrige el TypeError por `None` en las comparaciones de banda (OPC-29).
- Instalar `catalogo_sensores`, `GET /cycle/sensors?programa=N`, `PUT /cycle/sensor-roles` (todo o nada, concurrencia por `asignacion_anterior_esperada`, auditoría `ROLES_SENSOR`), códigos `ASIGNACION_INVALIDA`, `SENSOR_NO_DISPONIBLE`, `ASIGNACION_SENSORES_INVALIDA`, migración perezosa del formato antiguo, columnas nuevas en `ciclos` (asignación JSON canónica, F0 final, número de programa) y `temp_principal` en `lecturas`, ticket con la temperatura del Principal, según planeacion_sensores_ciclo.md RS-01 a RS-10 EXCEPTO lo que este documento cambia. C-2, C-5, C-6, C-7 con la recomendación del documento. Permisos para asignar roles y para calibración: técnico e ingeniero (se quita biomédico; admin no).
- La rama `feature/roles-sensor-temperatura` NO se integra (solo referencia).

### 1.2 Tipo de carga y Líquidos
- Nuevo parámetro `globals.tipo_carga` (enumerado `solido` | `liquido`, por defecto `solido`). Con `liquido`: la descompresión debe ser modo 4 o 5 (validación en el backend) y la descompresión RÁPIDA queda prohibida mientras la carga esté caliente: en el protocolo de fallo, en el estado seguro del §15 y en la válvula de reposo se usa enfriamiento/lenta, nunca la rápida. El modo 4/5 conserva su despresurización final con chaqueta + rápida, pero SOLO cuando el Principal ya esté en o por debajo de `temperatura_enfriamiento`. Corrige PF-10/PF-19: el protocolo de fallo con modos 4/5 debe hacer el enfriamiento/contrapresión antes de despresurizar.
- `descompresion.modo = 0` SE CONSERVA como función soportada (enfriamiento natural, puede durar horas, por eso sin timeout). NO lo prohíbas. Solo documenta en el informe cómo lo tratan `valvula_reposo.py` y `protocolo_fallo.py` (hoy como modo 2) y verifica que el estado seguro no dependa de un timeout inexistente.
- Programas de fábrica (numeración): 1 Bowie & Dick, 2 Instrumental 134, 3 Instrumental 121, 4 Líquidos. Crear `instrumental_121.json` derivado del 134: 121 °C, esterilización 15 min, mismo prevacío, `cycle_number` 3. Crear `liquidos.json`, `cycle_number` 4: sin prevacío (conteos 0), sin secado (verifica cómo se omite la fase; si no se puede con `tiempo_secado=0`, impleméntalo), `tasa_presion` 10 kPa/min, `tiempo_estable_preesterilizacion` 10 s, esterilización 121 °C / 15 min, `tipo_carga=liquido`, descompresión modo 4 (enfriamiento con contrapresión de aire comprimido hasta 80 °C medido con el Principal; la despresurización final con rápida solo después de enfriar, según la regla de arriba), F0 desactivado. Valores PROVISIONALES por validar en banco con vidrio real. El choque térmico (L3) queda fuera de esta versión; se cubre con las tasas.
- Un quinto programa NO se crea.

### 1.3 Estado seguro, puertas y fin de ciclo
- Se implementa planeacion_fin_de_ciclo_y_puertas.md completo (§4 a §9, §15, §16) con sus decisiones D-01 a D-23. La observación del §15 ya está incorporada en el texto.
- Paro de emergencia NC con lógica invertida (paro = entrada en 0 o sin datos). Tras liberarlo: "Confirmar y llevar a estado seguro" (cualquier operador, sin rol).
- Apagar equipo (§16): ALL_OFF, `DbManager.close()`, cerrar puerto serial y `shutdown /s`; solo con cámara segura y estado distinto de CICLO/§15; solo el proceso de la ventana principal.
- Fuente de vapor del equipo de pruebas: SOLO generador interno. El selector (generador interno / caldera externa / mixto) existe en el menú de instalación para cualquier equipo.

### 1.4 Firmware / enlace serial (E6, respuestas a sus preguntas)
- P1: bloque `alarmas.<ID>.{titulo, accion}` en `es.json` y `en.json` con los 9 ids nuevos. P2: `rechazados` y `rx_largas` quedan internos, sin cambiar la `ST`. P3: tarjeta no emparejada = log + `audit_log` + Información del sistema, sin alarma propia. P4: los 1–2 s de re-handshake en ciclo son aceptables (la tarjeta queda en 0xFFFF); E3 lo contempla. P5: el resultado `FALLO_IO` se conserva, con el `alarm_id` como causa.

### 1.5 i18n (F1)
- Una clave desconocida muestra la clave (no ""). El commit de F1 incluye los archivos migrados del asistente de instalación. Textos de las 6 etapas de arranque (es): "Verificando instalación", "Liberando procesos", "Cargando configuración", "Verificando calibración", "Conectando módulos de E/S", "Preparando interfaz" (agrega su traducción en `en`). Agrega en E5 el aviso `sistema.modo_prueba` ("MODO PRUEBA ACTIVO…") visible en la UI QML cuando el backend esté en modo prueba (I18N-28).

### 1.6 Permisos y Opciones
- Editan parámetros de ciclo y roles de sensor: técnico e ingeniero (técnico solo con estado distinto de CICLO; ingeniero también en CICLO, reglas ya implementadas §5.8/T-17). Cambia `PATCH /cycle/parameter` de "solo ingeniero" a técnico+ingeniero y alinea `ESTADOS_EDICION`. Roles válidos: admin, técnico, ingeniero.
- Secciones: Usuarios para admin e ingeniero; Conectividad para admin, técnico e ingeniero (cambiar `permisos_opciones.py`); las cinco técnicas para técnico e ingeniero.
- Specs 1, 2 y 3 (endurecimiento, sensores, pantallas) se implementan según §2 de este documento; en endurecimiento ya están vigentes y vencen sus D-1, D-2, D-8 y D-11 frente a la spec de autenticación v7 (estado distinto de CICLO + excepción del ingeniero, token, copia del programa al iniciar T-17). Verifica primero qué de RB-01 a RB-09 ya existe; implementa solo lo que falta.
- Límites del catálogo (Anexo B): presión 1–400 kPa; temperatura dentro de los límites del modelo; tiempos con mínimo 1 en su unidad; NUNCA rechazar un valor actual de los programas de fábrica. Entrega `docs/informes/limites_catalogo.md` con la tabla aplicada.
- Preguntas de pantallas: Q-2 fases con parámetro de activación en 0 visibles con "No se ejecuta"; Q-3 descompresión muestra solo los parámetros del modo activo; Q-4 programa de usuario sin perfil de fábrica: por defecto "—" y botón deshabilitado; Q-6 el engranaje de la pantalla de ciclo abre login y luego OPCIONES; Q-7 el cajón NO se abre por deslizamiento; Q-8 el título es el nombre de la sección activa. Pantalla de roles de sensor según planeacion_opciones_parametros_ciclo.md §5.5 con los roles de este documento (sin advertencia de sonda fría; sin "Entradas exhibidas").

### 1.7 Modo sin base de datos y arranque
- Se aprueban D-03 (OPERANDO_SIN_BD = ALERTA no bloqueante), D-04 (relanzar UI cerrada 3 veces cada 5 s), D-06 (sensores no críticos no bloquean el paso a listo), D-07 (sin prefijo en ciclos de contingencia) de planeacion_arranque_y_modo_sin_bd.md. Objetivo: un ciclo base ejecutable sin base de datos, con alarma, confirmación explícita por ciclo y bloqueo de calibración/parámetros/altas.
- Menú de instalación: conectar el puente Python real y abrirlo en el arranque cuando no haya perfil (ARR-02/MIG-07); retirar `wizard.py` solo después de verificar que no queda referencia. NO hay diálogo de clave de fabricante. Etiquetas de tipos de puerta: se dejan provisionales. La USB de recuperación NO entra. La etapa "Verificando sensores" sigue oculta en la barra.

## 2. Etapas (ejecutar en este orden)

**E-0. Commits previos (en `dev`).** (a) Ejecuta `safety-reviewer` y `timing-auditor` sobre los cambios sin commitear de E6 (firmware V3 + Fase B del enlace serial); corrige Alto/Crítico. (b) Aplica las decisiones 1.4 y 1.5 (bloque `alarmas` en es/en, textos de arranque). (c) Haz TRES commits separados en `dev`: F1 i18n (incluye los archivos migrados del asistente de instalación), E6 (firmware V3 + PC + pruebas), docs (planes e informes). NO incluyas en el commit de docs `docs/informes/analisis_sistema_alarmas.md`, el plan `docs/superpowers/plans/2026-10-07-sistema-alarmas-parte-a.md` ni la spec `docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md` (llegan con la rama `alarmas-parte-a`); tampoco `.claude/`. (d) Crea `dev-noche`.

**T1. Integrar `alarmas-parte-a`** (20 commits, 1799 pruebas en su rama) a `dev-noche`. Informe de referencia: `docs/informes/estado_ramas_2026-10-10.md`. Resolver los 4 conflictos (`backend/server.py`, `services/domain/logging/db_manager.py`, `services/domain/loop/control_loop.py`, `tests/test_io_test_mode_endpoints.py`) conservando `card_connected`/`comunicacion` de dev y el contrato nuevo de alarmas. Rebase sobre F1 (I18N-30: `textosJson`, `cargar_textos`, firma `AccionesCiclos`). Migrar al catálogo y API nuevos de alarmas todo lo que E6 agregó con la API vieja (los 9 ids de la tarjeta, `abortar_por_falla_io`, FALLO_CONEXION): nivel y bloqueo según E6 decisión 9 (fuera de ciclo FALLA bloqueante recuperable; en ciclo EMERGENCIA no auto-despejable). Suite completa en verde y revisores obligatorios.

**T2. E1b.** Campo `vapor_source` (generator | boiler | mixed) en el perfil de instalación, validación, salidas de vapor según la fuente, selector en el menú de instalación.

**T3. Sensores (backend).** Todo 1.1. Crea primero un accesor `sensor_principal(programa)` y úsalo en los puntos de §1.1.

**T4. E2.** `camara_segura` en `/status` (con el Principal, §1.1), "NO ABRIR", condición de inicio de ciclo (§5 de fin de ciclo).

**T5. E3.** Protocolo de estado seguro común (§15), matriz de fin de ciclo (§4), PF-10, TMG-04, TMG-03, corrección de SECADO sin vacío real (cita archivo y línea de lo que hacía), protocolo de fallo para `tipo_carga=liquido` (1.2).

**T6. E4.** Arranque seguro: ALL_OFF al conectar (ya hecho en E6: verifica), cierre de ciclos interrumpidos, cierre inmediato del COMPLETADO, PF-21 (paro NC), numeración de ciclos con contador persistente + índice UNIQUE + instantánea del programa (decisiones ya aprobadas).

**T7. E5 (UI).** "NO ABRIR", paro: "Confirmar y llevar a estado seguro", barra inferior del login uniforme, "Apagar equipo" (§16), aviso MODO PRUEBA (I18N-28), versión e ID de tarjeta solo en Información del sistema.

**T8. Modo sin BD** (planeacion_arranque_y_modo_sin_bd.md §7 y §9) con 1.7.

**T9. Menú de instalación conectado** (1.7).

**T10. Endurecimiento remanente.** RB faltantes, `tipo_carga`, límites del catálogo, cambio de permisos (1.6), tabla `limites_catalogo.md`.

**T11. Programas.** `instrumental_121.json`, `liquidos.json`, F0 por clase, validaciones (1.2). Prueba de integración con el simulador de un ciclo completo de cada uno de los 4 programas.

**T12. Pantallas de Opciones, Fases 2 a 4** (parámetros del ciclo en lectura y edición, roles de sensor) según planeacion_opciones_parametros_ciclo.md con 1.6. Fase 5 (retiro de vistas PySide) NO.

## 3. Fuera de alcance
Compilar/cargar firmware, pruebas en banco (E7), USB de recuperación, licencia/activación, plan de estación Windows, voz, empaquetado (.spec), recorte de L3, creación/borrado de programas, quinto programa.
