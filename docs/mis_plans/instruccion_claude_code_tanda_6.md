# Instrucción maestra para Claude Code — Tanda 6 (20/21-oct-2026, nocturna, ~8 h)

Objetivo: dejar el software completo para la instalación del equipo de pruebas (lunes 26-oct-2026).
- Cerrar lo que quedó pendiente de la tanda 5.
- Aplicar las respuestas de Cristian a las preguntas de T1.
- Terminar Opciones completo y el inglés.
- Cerrar los hallazgos Medios y Bajos de los revisores.
- Preparar los scripts de la estación Windows y la documentación 62304.

Es una tanda LARGA y sin supervisión: trabaja de corrido, etapa por etapa, sin detenerte a preguntar. Cristian no está presente: ante ambigüedad aplica la regla 4.

## 0. Reglas generales
Aplican TODAS las de la sección 0 de las instrucciones de las tandas noche, 3, 4 y 5, con estos cambios:
1. **Rama y archivos.** Rama `tanda-6`, creada desde `dev` DESPUÉS de E0. Estado en `docs/informes/tanda6/estado.md`; informes en `docs/informes/tanda6/<id>_<nombre>.md`; índice en `docs/informes/informe_tanda_2026-10-21_t6.md`; decisiones en `docs/informes/tanda6/DECISIONES_PARA_REVISAR.md`. Si existe `estado.md`, REANUDA. Si se corta por límites de uso, continúa cuando se restablezcan.
2. **Git.** Autorizado commit en `tanda-6`, unir a `dev` con `--no-ff` (suite verde) y `git push origin dev tanda-6`. NUNCA `main`, nunca `--force`, nunca `git add -A`; no agregues `data/`, `.claude/`, `*.db`, fotos ni logs. Si el push falla, anota el error exacto y sigue.
3. **Prohibido** compilar el ejecutable, tocar hardware, cargar firmware, EJECUTAR scripts `.ps1` o instalar software del sistema. Sí puedes ESCRIBIR scripts `.ps1` (W1).
4. **Ante ambigüedad,** elige lo más seguro y reversible, márcalo "DECISIÓN SIN CONFIRMAR" y regístralo. En la lógica de transiciones de ciclo y puertas, lo que no esté definido en la sección 1 NO se cambia salvo que sea inseguro: va como "PREGUNTA PARA CRISTIAN".
5. **Textos e invariantes.** Todo texto visible nuevo va en i18n es/en y todo valor de presión o temperatura visible pasa por el módulo de unidades de U1 (salvo E/S y calibración). Nada nuevo puede bloquear un ciclo ni alterar la lógica de seguridad, salvo donde se indique.
6. **Agentes.** Son obligatorios en las etapas ★: `safety-reviewer` y `timing-auditor` (y `sensor-role-auditor` si toca sondas o roles) sin hallazgos Altos/Críticos abiertos antes del commit. Suite completa en verde en cada commit. Anota la línea base al inicio (tanda 5: 4379/1/3).
7. **Orden y prioridad.**
   - **Bloque 1 (sin UI nueva):** E0, T2, C1, X1, I4 (parte de backend y salidas), R1, W1, D1.
   - **Bloque 2 (UI nueva):** B1, O3, O2a–O2h, I4 (parte QML), H1.
   - El Bloque 2 SOLO se ejecuta si existe `docs/mockups/tanda6/APROBADO.md`; los mockups aprobados que debes seguir están en `docs/mockups/tanda6/`. Antes de empezar el Bloque 2, vuelve a comprobar si el archivo existe (Cristian puede aprobarlo mientras trabajas en el Bloque 1). Si no existe, sáltalo entero, anótalo y ve a Z.
   - Z se ejecuta SIEMPRE.
8. **Árbol de trabajo.** No hay otra sesión activa. Si durante la tanda aparece un cambio en el árbol que no hiciste tú, no lo commitees: anótalo y sigue.

## 1. Decisiones de Cristian (20-oct, noche) — fuente de verdad
1. **Preguntas de T1.** Acepta TODAS las recomendaciones del chat:
   - **P-1:** el reconocimiento de COMPLETADO pasa a estado seguro y "NO ABRIR" si la cámara no está segura. Es lo mismo que tras una falla o una cancelación: tras cualquier fin, "NO ABRIR" hasta cámara segura y sin ciclo nuevo hasta entonces.
   - **P-2:** sonda Principal perdida en ciclo. NO se continúa con la Referencia. El ciclo falla, ventea por la LENTA y el operador reconoce y vuelve a PREPARACION sin técnico. Mientras la Principal no tenga lectura válida, el inicio de ciclo queda bloqueado con el mensaje "Sonda principal sin lectura: llame a servicio". El estado seguro se libera solo por los caminos de CIC-10 vigentes. Que la sonda dañada requiera servicio no contradice D-06.
   - **P-3:** una trama DI vencida en ciclo tiene una tolerancia de hasta 5 s y se registra como fallo de comunicación, no como EMERGENCIA. CONDICIÓN: la tolerancia nunca puede ser mayor que el tiempo en que el watchdog del firmware (`Hardware/Comunicacion_esclava_ESP32_V3`) apaga las salidas al perder el latido. Lee ese tiempo del `.ino`. Si es menor de 5 s, usa ese valor menos 1 s y anótalo. Si no puedes determinarlo, deja la tolerancia en 0 (comportamiento actual) y pregunta.
   - **P-4:** PREPARADO consulta `has_blocking_alarm()` según el campo `bloquea_inicio` del catálogo.
   - **P-5:** COM-02 y COM-03 NO se resuelven al salir de FALLA; requieren despeje manual.
   - **P-6:** el diálogo de reconocimiento que también confirma el estado seguro muestra el texto de §15.2 de la spec.
   - **P-7:** `/cycle/abort` responde 409 con motivo cuando no tiene efecto (resultado pendiente o paro).
   - **P-8:** retira los estados HIBERNACION y EMERGENCIA si son inalcanzables. Antes, verifica que la Suspensión (`ui_qml/bridge/standby.py` y el backend) no use HIBERNACION. Si la usa, consérvalo y anótalo.
   - **P-9:** se puede reimprimir desde el Historial el ticket de un ciclo INTERRUMPIDO.
   - **P-10:** queda para la prueba de banco C-05; no hay cambio.
   - **P-11:** sin cambio.
   - **P-12:** en Líquidos, D-19 se aplica también en el drenaje a presión atmosférica: se ventea por la LENTA mientras la temperatura Principal sea mayor que `temp_max_apertura`, y por la rápida solo por debajo de ese valor. En Bogotá el agua hierve a ~92 °C; una descompresión rápida con líquido caliente produce ebullición violenta.
2. **Sensor de chaqueta: es ABSOLUTO.** `presion_chaqueta` y toda lectura de chaqueta se tratan como presión absoluta en U1, con psig = (P_abs − P_atm)/6,894757. Quita la pregunta 1 de U1 y deja una prueba que lo fije.
3. **Cambio de `bowe_dick.json` (fábrica y usuario): fue intencional.** Se commitea tal cual, incluido el máximo de 1800 s de `tiempo_estable_preesterilizacion`.
4. **Conectividad entra en esta tanda (O2g).**
5. **Admin y Parámetros del equipo.** El admin VE Parámetros del equipo en solo lectura (revierte P2-1 de la tanda 5). Es la decisión vigente desde el 7-oct.
6. **Parámetros del equipo (respuestas del 20-oct, 22:38):**
   - Van TODOS los parámetros de la tabla §3.2 de `planeacion_opciones.md` v4, con esos defectos y rangos, pero AGRUPADOS en submenús, no en una lista corrida. Submenús: Puerta, Impresión, Drenaje, Empaque, Chaqueta, Sistema y Configuración de la máquina (detalle en O2a).
   - Los contadores de servicio (ciclos y días) quedan SOLO en Mantenimiento (B3); no se duplican aquí.
   - Idioma y unidades van en el submenú "Configuración de la máquina" de Parámetros del equipo, con los permisos de la decisión 1.9.
   - Número de serie y nombre de modelo NO son editables: solo lectura (en Configuración de la máquina y en Información del sistema). Se cambian reinstalando el perfil.
   - La inactividad de sesión queda FIJA en 5 min; no es parámetro.
9. **Permisos por rol (20-oct, 22:54; reemplaza lo anterior en estos puntos).** El rol TÉCNICO NO puede:
   - cambiar unidades;
   - cambiar idioma;
   - modificar destinatarios de correo;
   - crear ni modificar usuarios ni operadores.

   Queda así:
   - Idioma: admin e ingeniero.
   - Unidades: solo ingeniero.
   - Destinatarios de correo: admin e ingeniero; el técnico ve Conectividad en solo lectura.
   - Usuarios y operadores (crear, desactivar, restablecer contraseña, agregar operador): admin e ingeniero, respetando `ROLES_CREABLES`.

   El técnico ve esos controles deshabilitados, con el motivo. El backend rechaza con 403 aunque la UI falle. Pruebas de la matriz completa por rol.
10. **Fecha y hora (O2c):** por ahora es SOLO LECTURA, con la hora del PC (Windows). No implementes el ajuste. Muestra fecha, hora y zona, y avisa si el reloj es anterior a la instalación (M1-01). Si Cristian decide otra cosa durante la noche, lo dirá `docs/mockups/tanda6/APROBADO.md`.
11. **Pendientes que NO se tocan en esta tanda** (solo para el informe final, sección "Recordatorios"):
    - (a) El correo solo llega a los destinatarios guardados: a un correo escrito a mano no llega nada, aunque el software diga que se envió.
    - (b) El asistente de instalación debe pedir información y calcular el modelo del equipo.
7. **Barra inferior flotante en TODAS las pantallas.** Incluye Preciclo y Ciclo en curso, y reemplaza la exclusión por D-19 de `instruccion_claude_code_barra_inferior_flotante.md` (B1).
8. **Respaldo de la UI de Opciones** (decisiones ya tomadas, para referencia):
   - Opciones en QML puro, con cajón lateral de hamburguesa y barra inferior flotante de tres secciones.
   - Roles: admin, técnico e ingeniero. Admin: Usuarios, Conectividad y Bitácora (lectura), más Parámetros del equipo (lectura). Técnico e ingeniero: secciones técnicas. Fecha y hora e Información del sistema, para todos.
   - Cambios de parámetros del equipo solo en reposo y aplicados sin reiniciar.

## 2. Etapas (en este orden)

**E0. Cierre de la tanda 5 (antes de crear `tanda-6`).**
1. Commitea en `tanda-5`, por tema y por ruta explícita: los teclados (`teclado_alfanumerico_controller.py`, `teclado_numerico_controller.py` y sus 3 pruebas) y los dos `bowe_dick.json` (decisión 1.3). Primero verifica que la suite pase con ellos. Si una prueba de teclados falla, arréglala o deja ese archivo fuera con explicación.
2. Une `tanda-5` a `dev` con `--no-ff`. VERIFICA con `git merge-base --is-ancestor tanda-5 dev`; en la tanda 5 la etapa Z dijo que unió y no lo hizo.
3. `git push origin dev tanda-4 tanda-5`. Anota el resultado exacto.
4. Deja `data/unidades.json` en °C/kPa y `data/idioma.json` en "es" (archivos de estado local; edítalos pero NO los commitees).
5. Crea `tanda-6` desde `dev` e incluye en el primer commit `docs(tanda6)` los dos documentos de esta tanda.

**X1. Solapamiento en Entradas/Salidas.** Cristian vio, por primera vez, la lista de Entradas dibujada debajo de la de Salidas (rótulos "Aire comprimido DI 01", "Presión de agua DI 02" y "○ INACTIVO" bajo los botones Activar). Ejecutaba desde consola (`python -m autoclave.backend.main` y `python -m autoclave.ui_qml.lanzar real`) con las dos ventanas abiertas en el mismo PC, y la ventana 2 estaba en otra pantalla.
- Investiga la causa: delegados de `Repeater` no destruidos al cambiar el modelo con la actualización de 1 s, instancia duplicada de `OpcionesEntradasSalidas` en el `Loader` o el `StackView`, o fondo transparente entre ventanas.
- Reprodúcelo con una prueba QML offscreen: cambio rápido Entradas↔Salidas mientras llegan lecturas, entrada al modo prueba y vuelta a Opciones.
- Corrige con una estructura que no pueda solapar (p. ej. un `Repeater` por segmento con `visible`, o `StackLayout`) y verifica que exista una sola instancia de la pantalla por ventana.
- Revisa el mismo patrón en Temperatura/Presión y en Parámetros del ciclo.
- Pruebas y captura antes/después.

**B1. Barra inferior flotante en todas las pantallas** (Bloque 2; sigue el mockup).
- Aplica `BarraInferiorMenu` flotante, fuera de la tarjeta, en Preciclo, Ciclo en curso y en toda pantalla con navegación que aún no la tenga. Con Login, CambioClave y NuevoUsuario ya hechos, verifícalos.
- Preciclo y Ciclo conservan sus funciones actuales en la barra: login en el lugar de Home en Preciclo, Menú, Atrás y Home según las reglas de navegación del 19-oct. La exclusión por D-19 queda sin efecto para la barra; no refactorices el resto de esas pantallas.
- La pantalla de Instalación conserva su barra de acciones (Atrás/Siguiente/Instalar).
- Pruebas: la barra no es hija de la tarjeta y queda por debajo de ella; cada botón emite su señal; ningún contenido queda tapado.
- Capturas 1200×1920 de todas las pantallas en `docs/informes/tanda6/capturas/`.

**T2. Aplicar las respuestas de T1** ★ (los tres agentes).
- Implementa P-1 a P-9 y P-12 (decisión 1.1), cada uno en su propio commit con pruebas.
- Actualiza `T1_matriz_transiciones.md` (copia a `docs/informes/tanda6/T2_matriz_actualizada.md`) marcando cada celda resuelta.
- Repite con la planta simulada de E1 las celdas afectadas, en los 4 programas.
- Agrega las entradas correspondientes al fichero de riesgos (`docs/riesgos/`) o, si no tiene formato, al informe.

**C1. Correcciones de la tanda 5.**
- **a) Reingreso táctil en PySide (P3-1)** ★(`safety-reviewer`). `QInputDialog` es inutilizable en el equipo, que es táctil y no tiene teclado físico. Implementa en PySide un diálogo de credenciales con teclado en pantalla. Úsalo también en cualquier otro lugar de PySide que pida texto. Debe tener:
  - alfanumérico con mayúsculas y números, y numérico;
  - tamaño de tecla igual al de los teclados QML;
  - estilo de `qfluentwidgets`.

  Reutiliza la lógica de los controladores de teclado si es posible.
- **b) Admin en solo lectura en Parámetros del equipo** (decisión 1.5). Los campos se muestran deshabilitados, con el motivo. Pruebas de permisos.
- **c) Clase explícita de parámetro en U1** ★(`safety-reviewer`).
  - Agrega `"clase": "absoluto" | "diferencia" | "sin_conversion"` a cada hoja de presión o temperatura en `cycles/factory/`, `cycles/defecto/`, `cycles/user/`, `global_params.json` y el catálogo.
  - El módulo de unidades usa ese campo y NO los prefijos. Los prefijos quedan solo como migración al cargar archivos viejos sin `clase`, y en ese caso se registra una advertencia.
  - Resuelve explícitamente `rango_calentamiento` (hoy es contradictorio). Mira su uso en el control: si es un margen, es "diferencia"; si su unidad real no es presión, es "sin_conversion". Documenta la decisión.
  - Prueba que falla si alguna hoja con unidad de presión o temperatura no tiene `clase`.
- **d) Chaqueta absoluta** (decisión 1.2). Prueba que lo fije.

**O3. Entradas mostradas en Preciclo, Ciclo y gráfica.** O1 dejó sin usar la selección de 1 a 3 entradas por programa. Conéctala:
- Preciclo y la pantalla de ciclo muestran las entradas elegidas del programa seleccionado, en la unidad vigente.
- La gráfica del ciclo dibuja esas mismas entradas.
- Al cambiar de programa, cambian.
- Si una entrada elegida está en "No en uso" o sin lectura, se muestra "—" y no rompe la pantalla.

Pruebas y capturas.

**O2. Resto de Opciones** (una subetapa por commit, en este orden; usa el inventario `docs/informes/tanda5/O1_inventario_opciones.md`).
- **O2a. Parámetros del equipo completo** ★. Pantalla de entrada con 7 submenús (tarjetas); cada uno abre su lista de parámetros y cada parámetro abre la ventana de ajuste:
  - **Puerta:** tiempo límite de puerta, temperatura segura de apertura, brecha de presión atmosférica (±).
  - **Impresión:** impresora habilitada (ya existe), tasa de impresión general, tasa de impresión en esterilización.
  - **Drenaje:** temperatura segura de drenaje, rango de temperatura de drenaje.
  - **Empaque:** presión de empaque, vacío de empaque.
  - **Chaqueta:** tiempo límite de chaqueta (`timeout_chaqueta`, nuevo: 60 min, 10–180; NO lo conectes a la lógica del ciclo en esta tanda; anota dónde se usaría como PREGUNTA PARA CRISTIAN).
  - **Sistema:** suspensión, tiempo de estabilidad para alarma, presión atmosférica de referencia (solo lectura, con fecha y usuario de la última calibración).
  - **Configuración de la máquina:** idioma, unidades de temperatura, unidades de presión, número de serie y nombre de modelo (estos dos, solo lectura).

  Los contadores de servicio NO van aquí (siguen en Mantenimiento). Lo que sigue define el backend y las reglas:
  - Tabla `system_params` en la BD (migración v2 reservada en `db_manager.py`), con `global_params.json` como valores de fábrica. Cada parámetro guarda valor, defecto, mínimo, máximo, usuario y fecha del último cambio.
  - Endpoints `GET`/`PATCH /global_params/{clave}` y `POST .../reset` con token, rol y auditoría (`param_sistema_cambio`). Cambios solo en reposo (409 en ciclo) y aplicados sin reiniciar.
  - Resuelve OPC-11: `ServicioPuertas` y cualquier otro servicio que copie parámetros en `__init__` deben leer el valor vigente.
  - Rangos y defectos según `planeacion_opciones.md` v4 y la memoria del proyecto:
    - Suspensión: 0–60 min, defecto 10, 0 = desactivada. Corrige el puente que convierte 0 en 5.
    - `temp_max_apertura`: defecto 80 °C, techo 120 °C.
    - Presión de empaque 100–400 kPa; vacío de empaque 0–100 kPa.
    - Contadores de servicio con 0 = desactivado.
    - `timeout_puerta` e intervalos de impresión sin 0.
  - Elimina `temp_max` y `tipo_puerta`. Corrige las erratas (`presion_admosferica`, `intervalo_imprecion_*`) con alias de compatibilidad.
  - La presión atmosférica de referencia NO es editable a mano (solo por O2f).
  - En esta pantalla van también los selectores de **idioma** (cualquier rol con sesión, permitido en ciclo) y de **unidades** (técnico e ingeniero, fuera de ciclo). Si U1 los dejó en otra pantalla, muévelos aquí y deja allí un acceso.
  - Ventana de ajuste igual a la de Parámetros del ciclo.
- **O2b. Usuarios.**
  - Listar usuarios, desactivar y reactivar (nunca borrar: trazabilidad) y restablecer contraseña, con cambio obligatorio en el siguiente login.
  - Gestionar operadores (los que se eligen al iniciar ciclo; ver `O1_operador_ciclo.md` de la tanda 3).
  - Matriz de quién crea a quién: la vigente en `ROLES_CREABLES`.
  - Nadie puede desactivarse a sí mismo ni dejar el equipo sin ningún ingeniero activo.
  - Auditoría.
- **O2c. Fecha y hora (todos los usuarios; SOLO LECTURA por la decisión 1.10, lo que sigue sobre el ajuste NO aplica salvo que `APROBADO.md` diga lo contrario).**
  - Ajuste de fecha y hora del sistema con confirmación; solo fuera de ciclo.
  - En el informe va el mecanismo en Windows (permiso necesario) para que Cristian lo verifique.
  - Si no se puede ajustar sin privilegios, deja la pantalla con la hora actual, la zona horaria y la explicación.
  - Auditoría con hora anterior y nueva.
  - Rechazar fechas anteriores a `installed_at` (coherente con M1-01).
- **O2d. Información del sistema (todos, lectura).**
  - Versión del software, versión e ID de la tarjeta (firmware 1.0.0), número de serie y modelo del perfil, fecha de instalación.
  - Próximo mantenimiento (días y ciclos), contador de ciclos, idioma y unidades vigentes, estado de impresora y de red.
  - Quita los "No disponible" del panel del Menú principal donde el dato exista.
- **O2e. Bitácora de auditoría.**
  - `GET /audit_log` con paginación y filtros por fecha, usuario y tipo de evento.
  - Pantalla de solo lectura; textos resueltos por código en el idioma vigente y valores en la unidad vigente.
  - La ven admin, técnico e ingeniero; nadie edita ni borra.
  - Agrega los eventos que falten: `falla_reconocida`, `param_sistema_cambio`, `calibracion_atm_*`, `suspension_*`, usuarios, fecha y hora.
- **O2f. Mantenimiento: calibración de presión atmosférica** ★.
  - Precondiciones: puerta abierta, temperatura de cámara < 80 °C y fuera de ciclo.
  - Ventana continua de 2 min con muestreo cada 5 s. Si se pierde una precondición, ABORTA sin reintentar. UI bloqueada salvo Cancelar.
  - Aceptación (DECISIÓN SIN CONFIRMAR), porque el equipo puede instalarse a cualquier altitud:
    - promedio entre 60 y 105 kPa abs;
    - dispersión (máx − mín) ≤ 1,5 kPa;
    - si difiere más de 5 kPa del valor anterior, pide confirmación explícita.
  - Auditoría `calibracion_atm_ok`/`_abortada`/`_rechazada`.
  - Agrega también lo que falta según el inventario: página de prueba de la impresora e impresión de ganancias de calibración.
- **O2g. Conectividad** (admin, técnico e ingeniero; decisión 1.4).
  - Estado de red en solo lectura: adaptadores, IP, Wi-Fi conectado e intensidad.
  - Configuración del correo de ciclos según `docs/mis_plans/` y la decisión de envío de correo: destinatarios, activar/desactivar y "Enviar correo de prueba". La contraseña del relay no se muestra nunca.
  - Cambiar Wi-Fi o IP desde el software queda en solo lectura (DECISIÓN SIN CONFIRMAR: requiere privilegios de Windows y puede dejar el equipo sin soporte remoto). Documenta qué haría falta para habilitarlo.
- **O2h. Respaldo y restauración** (técnico e ingeniero, solo fuera de ciclo).
  - Exportar a USB: perfil, calibración, parámetros del equipo, programas `user`/`defecto`, usuarios sin hashes en claro e historial opcional. Incluye un manifiesto con hash.
  - Restaurar valida el manifiesto, la versión y el número de serie del equipo antes de aplicar, y pide confirmación. Restaurar calibración o perfil de OTRO equipo se rechaza.
  - Conecta con la idea de USB de recuperación del perfil del arranque si encaja. Si no, déjalo documentado.

**I4. Terminar el inglés** ★ (I1 a I3 pendientes, más la parte automatizable de F5).
- Motivos de puerta con código + parámetros (`RechazoApi` en lugar de `HTTPException` con texto).
- `motivo_fallo` con parámetros en la BD (columna JSON, con migración) para renderizar ticket y PDF en ambos idiomas.
- `nombre_clave` en los ciclos de fábrica y etiquetas de roles y enums por catálogo.
- Gráficas, historial, diálogos de resultado y textos que Python entrega a QML, en idioma y unidad vigentes.
- PDF (ciclo, resumen, consolidado), correo y tickets de resumen, arranque y conectividad, con unidades en la cabecera.
- Separa estado de rótulo en el ticket de arranque (I18N-18). Verifica cp437.
- Prueba: cada código de alarma y cada motivo de puerta se dispara y tiene texto en es y en.
- Prueba: ninguna pantalla QML tiene literales visibles fuera del catálogo (lista blanca justificada).
- Revisión de truncado a 1024 px en inglés, con capturas de todas las pantallas en es y en en `docs/informes/tanda6/capturas/`.
- R-06 se mantiene.

**R1. Cerrar Medios y Bajos de los revisores.** Recorre los informes de las tandas 4, 5 y 6 y lista todos los hallazgos Medios/Bajos abiertos en una tabla (id, origen, severidad, estado).
- Corrige los que sean de bajo riesgo y no cambien la lógica de seguridad, con prueba.
- Los que toquen transiciones o seguridad van como "PREGUNTA PARA CRISTIAN" con recomendación.
- Entregable: `R1_hallazgos_pendientes.md`.

**W1. Scripts de la estación Windows (solo escribir, NO ejecutar).** Según `docs/mis_plans/planeacion_estacion_windows.md`, escribe en `tools/estacion/` los `.ps1` necesarios:
- cuenta local con inicio automático;
- arranque sin logo ni bloqueo;
- `Autoclave.exe` como shell o inicio automático, según el plan;
- desactivar notificaciones, actualizaciones automáticas en horario de uso y gestos de borde;
- plan de energía;
- AnyDesk desatendido, solo si el plan lo define.

Cada script debe ser idempotente, tener `-WhatIf` y su script inverso, y registrar en un log. Acompáñalos de un `LEEME.md` con el orden de ejecución, cómo revertir y la lista de comprobación en el PC industrial. Prueba solo estática: sintaxis con `pwsh -NoProfile -Command { [ScriptBlock]::Create(...) }` si `pwsh` está disponible; si no, revisión manual anotada.

**D1. Documentación 62304 mínima para la entrega como demo** (solo documentos).
- Fichero de riesgos actualizado (`docs/riesgos/`): las entradas acumuladas en las tandas noche a 6 (cámara segura, estado seguro, corte de energía, tarjeta desconectada, unidades, idioma, modo prueba, caducidad de sesión, D-19, etc.), con control y prueba que lo verifica.
- Matriz de trazabilidad requisito–riesgo–prueba en `.md` (Cristian la pasa a xlsx): requisitos tomados de las specs de `docs/mis_plans/`, riesgos del fichero y pruebas (nombre del test o id de la hoja de banco).
- Lista SOUP con versión exacta (de `requirements` o del entorno), uso, clase de riesgo y anomalías conocidas.
- Marca como "por completar" lo que no puedas sustentar. No inventes.

**H1. Hoja de pruebas de banco.** Agrega pruebas para T2 (cada P), C1, O3, cada subetapa de O2, I4 (recorrido en inglés, PDF, correo de prueba) y la calibración atmosférica. Ids estables, sin renumerar. Regenera `.md`/`.html`.

**Z. Cierre (OBLIGATORIO verificar).** Indica en el índice si se ejecutó el Bloque 2.
1. Suite completa en verde.
2. `git merge --no-ff tanda-6` en `dev`.
3. Comprueba con `git merge-base --is-ancestor tanda-6 dev` y anota la salida.
4. `git push origin dev tanda-6` y anota el resultado exacto.
5. Escribe el índice, `estado.md` y `DECISIONES_PARA_REVISAR.md` (resumen de 10 líneas arriba), las "PREGUNTA PARA CRISTIAN" en sección aparte, la lista de pasos manuales previos al lunes 26-oct y una lista de lo que quedó sin hacer.
6. Nada a `main`.
