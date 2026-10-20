# Instrucción maestra para Claude Code — Tanda 5 (20-oct-2026)

Objetivo: dejar el software listo para la instalación del equipo de pruebas (lunes 26-oct-2026). Hay que integrar el trabajo de la otra sesión, cerrar los pendientes de la tanda 4, terminar Opciones (prioridad: Parámetros del ciclo), auditar las transiciones de ciclo, agregar el cambio de unidades y retomar el inglés (F2–F4). Cristian puede no estar presente: ante ambigüedad aplica la regla 4.

## 0. Reglas generales
Aplican TODAS las de la sección 0 de `instruccion_claude_code_tanda_noche.md`, `instruccion_claude_code_tanda_3.md` e `instruccion_claude_code_tanda_4.md`, con estos cambios:
1. Rama `tanda-5` creada desde `dev` (ea91725 o posterior). Estado en `docs/informes/tanda5/estado.md`; informes `docs/informes/tanda5/<id>_<nombre>.md`; índice final `docs/informes/informe_tanda_2026-10-20_t5.md`; decisiones en `docs/informes/tanda5/DECISIONES_PARA_REVISAR.md` (decisión, motivo, alternativa, commit, cómo revertir). Si existe `estado.md`, REANUDA.
2. GIT: autorizado commit en `tanda-5`, unir a `dev` con `--no-ff` (suite verde) y `git push origin dev tanda-5`. NUNCA `main`, nunca `--force`, nunca `git add -A`; no agregues `data/`, `.claude/`, `*.db`, fotos ni logs. Si el push falla, anótalo y sigue.
3. Prohibido compilar el ejecutable, tocar hardware, cargar firmware, ejecutar `.ps1` o instalar software del sistema.
4. Ante ambigüedad: elige lo más seguro y reversible, márcalo "DECISIÓN SIN CONFIRMAR" y regístralo. EXCEPCIÓN (T1): en la lógica de transiciones de ciclo y puertas NO cambies un comportamiento cuando la spec sea ambigua, salvo que el comportamiento actual sea inseguro; regístralo como "PREGUNTA PARA CRISTIAN".
5. Todo texto visible nuevo en i18n es/en. Nada nuevo puede bloquear un ciclo ni alterar la lógica de seguridad existente, salvo donde se indique.
6. Los agentes de revisión vuelven a ser obligatorios: en las etapas ★, `safety-reviewer` y `timing-auditor` sin hallazgos Altos/Críticos abiertos antes del commit (y `sensor-role-auditor` cuando la etapa toque sondas o roles). Suite completa en verde en cada commit. Anota la línea base al inicio.
7. Prioridad por si no alcanza el tiempo: E0, R0, P1, P2, P3, O1, T1, U1, I1, I2, I3, O2, H1. La etapa Z se ejecuta siempre con lo terminado; lo no hecho queda listado como pendiente.

## 1. Decisiones de Cristian (20-oct) — fuente de verdad
1. La otra sesión terminó: sus cambios sin commit se integran (E0).
2. Modo prueba de Entradas/Salidas: termina SOLO con cerrar su ventana, sea por Atrás, por elegir otro menú, por Home, por salir de todos los menús o por cierre de sesión, además del botón normal "Salir del modo prueba". Sustituye al botón de salida forzada en pantalla de B8 (el endpoint de B8 se conserva).
3. `impresora.habilitada`: interruptor en Parámetros del equipo, editable por técnico e ingeniero, con auditoría; NO en el asistente de instalación. El equipo de pruebas SÍ lleva impresora.
4. PySide renueva el token mientras la ventana esté en uso y, ante un 401, pide login sin perder lo editado.
5. Permisos de puertas por rol (B9b): siguen DIFERIDOS.
6. Unidades (reemplaza la D-23 de `planeacion_i18n.md`):
   - Temperatura: °C o °F.
   - Presión: kPa, bar o mbar, siempre ABSOLUTOS; o psi, siempre MANOMÉTRICO (psig) y, por debajo de la atmosférica, pulgadas de mercurio de vacío (inHg). No existen psi negativos. El usuario no elige entre absoluta y manométrica: va ligada a la unidad.
   - Control, BD, calibración, JSON de ciclos y API siguen internamente en °C y kPa absolutos. La conversión es SOLO de presentación y de entrada de datos; un valor editado se convierte y se valida en la unidad interna.
   - Aplica a pantallas, parámetros de ciclo, gráficas, historial, ticket, PDF y correo.
   - La cambian técnico e ingeniero, solo fuera de ciclo, con auditoría. Es independiente del idioma.
7. Inglés: en esta tanda F2 + F3 + F4 de `planeacion_i18n.md`. F5 y la voz (F6) quedan para después. R-06 se mantiene (no habilitar inglés en campo hasta cerrar la voz): no lo cambies.
8. Opciones: prioridad Parámetros del ciclo.
9. Transiciones: matriz contra la spec, corrige donde la spec sea explícita y deja las ambiguas para Cristian (regla 4).

## 2. Etapas (en este orden)

**E0. Integrar el trabajo de la otra sesión.** El árbol tiene 29 archivos modificados y ~30 sin seguimiento (teclados QML, Entradas/Salidas, calibración por sensor, barra inferior flotante, iconos, `io_names.py`, `server.py`, `sesion_backend.py`, `es.json`/`en.json`, pruebas).
- Antes de commitear, mide el ruido de saltos de línea (`git diff --stat` contra `git diff --ignore-space-at-eol --stat`: hoy ~11 800 líneas frente a ~1 600 reales). Si es churn CRLF/LF, normaliza al estilo que ya tiene cada archivo en `HEAD` para que el commit lleve solo cambios reales. Si conviene, propone un `.gitattributes` en commit aparte y regístralo como decisión; no renormalices el repositorio entero.
- Commits por tema (teclados, E/S y calibración, barra flotante, iconos, i18n), por ruta explícita. NO incluyas `docs/catalogo_alarmas.2026-09-18.bak.md` ni `src/autoclave/images/icono autoclave.jpg` (con espacio en el nombre): lístalos en el informe para que Cristian decida.
- Verifica que sigue el `renovar=False` de `_caducar_momentanea` y `_salir_por_inactividad` en `server.py` (nota de la tanda 4).
- Suite completa en verde (la tanda 4 reportó 4008/1/3 con estos cambios). Si algo de esa sesión está incompleto o rompe pruebas, no lo arregles a ciegas: déjalo fuera, explícalo y sigue.

**R0. Revisión de agentes de la tanda 4.** Cristian lanzó por separado `safety-reviewer`/`timing-auditor` sobre B5, B7, B8 y B9a.
- Busca sus resultados en `docs/informes/tanda4/` u otro lugar evidente. Si no existen o están incompletos, ejecútalos tú.
- Corrige todo hallazgo Alto o Crítico con prueba; los Medios y Bajos van al informe.
- Comprobación obligatoria de B7: la caducidad del token no puede impedir ninguna acción de seguridad (cancelar ciclo, confirmar estado seguro, reconocer falla, apagar equipo, paro) ni dejar salidas sin supervisión. Si alguna depende del token, documenta cómo se comporta con el token vencido.

**P1. Modo prueba: termina al cerrar su ventana** ★.
- Al salir de `OpcionesEntradasSalidas.qml` por cualquier camino (Atrás, otra entrada del cajón, Home, salida de Opciones, cierre de sesión por inactividad, cambio a pantalla de ciclo o falla), la UI llama a la salida normal del modo prueba antes de navegar, con las mismas garantías que el botón: salidas en seguro y estado seguro respetado. Centraliza la salida en un único punto (p. ej. `Component.onDestruction`/`StackView` más el controlador) para que ningún camino quede sin cubrir.
- Si la llamada falla o la UI se cae, el respaldo es el keepalive del backend (`/io/test/keepalive`, plazo de inactividad): confirma con prueba que el modo termina solo en ese caso.
- Se conserva el botón "Salir del modo prueba". El endpoint `/io/test/force-exit` de B8 se queda; no se agrega botón de salida forzada.
- Pruebas: una por cada camino de salida, más UI caída (sin keepalive) y fallo de la llamada de salida.

**P2. Interruptor `impresora.habilitada`.** En Parámetros del equipo, editable por técnico e ingeniero; admin solo lectura. Auditoría en `audit_log`. Usa la bandera y los endpoints existentes de B5 (`/printer/config`). Texto i18n es/en. El valor por defecto para el equipo de pruebas es habilitada. Pruebas de permisos y de que el aviso SIS-05 desaparece o aparece según el valor.

**P3. Renovación del token en PySide** ★(`safety-reviewer`).
- Las vistas PySide que usan token (calibración, ajustes, secado) lo renuevan con `GET /auth/sesion` cada 30 s mientras la ventana esté abierta y con actividad, igual que la UI QML (B7).
- Ante un 401, muestra un diálogo de login con el teclado existente y, si la autenticación es correcta, reintenta el guardado pendiente sin perder lo editado. Si se cancela, no se guarda y el motivo se muestra claramente.
- Pruebas con reloj inyectable: inactividad mayor al plazo, renovación en uso, 401 con reintento exitoso y 401 cancelado.

**O1. Opciones › Parámetros del ciclo completo** ★(`safety-reviewer`; `sensor-role-auditor` en sensores).
- Primero, inventario actualizado de Opciones pantalla por pantalla (Listo / Parcial / Falta / "Próximamente") en `docs/informes/tanda5/O1_inventario_opciones.md`. Reemplaza `docs/mis_plans/informe_estado_opciones.md` del 7-oct, que está desactualizado.
- Luego completa Parámetros del ciclo según `planeacion_opciones.md` v4, que es la vigente y reemplaza la rev. 3.1:
  - Flujo programa → fase → lista de parámetros de la fase → ventana de ajuste. La ventana muestra valor actual, por defecto (la tarjeta "Por defecto" es el botón para usarlo), mínimo, máximo, usuario y fecha del último cambio, y un campo con el teclado numérico que solo aparece al tocarlo.
  - Lectura de los parámetros de cualquier programa, no solo del seleccionado. Si hace falta endpoint, añádelo con token.
  - Modelo de defectos: `cycles/factory/` (solo fábrica), `cycles/defecto/<id>.json` (creados en el hospital) y `cycles/user/` (perfil completo). El defecto de un ciclo duplicado son los valores del origen al duplicar.
  - Sensores por programa: Principal (exactamente 1), Referencia (0–2) y No en uso, listando solo las sondas conectadas.
  - Entradas mostradas por programa (1 a 3).
  - Gestión de programas para técnico e ingeniero: habilitar/deshabilitar, duplicar y borrar personalizados. Los de fábrica no se borran.
  - Permisos: técnico e ingeniero editan; el técnico NO con ciclo en curso, el ingeniero sí; admin no ve las secciones técnicas.
- Corrige lo que el inventario de la tanda anterior marcó en el backend de parámetros de ciclo: coerción de booleanos (`bool("false")`), rechazo de NaN/inf y escritura atómica del JSON.
- Los valores se muestran en las unidades seleccionadas cuando U1 esté hecha. Si O1 va antes, deja el punto de enganche al formateador único.
- Pruebas: flujo completo, defecto, rangos, permisos por rol y estado, duplicar/borrar, sensores con reglas de cardinalidad, ciclo en curso.

**T1. Auditoría de transiciones de ciclo** ★(los tres agentes).
- Construye la matriz estado × evento desde el CÓDIGO (máquina de estados, `ControlLoop`, fin de ciclo, puertas, estado seguro) y compárala con `planeacion_fin_de_ciclo_y_puertas.md` y con las decisiones de la memoria del proyecto.
  - Estados: PREPARACION, PREPARADO, CICLO por fase, COMPLETO, CANCELADO, FALLA, NO ABRIR/cámara segura, estado seguro pendiente y modo prueba.
  - Eventos: inicio, fin normal, cancelación del operador, fallo de cada fase, paro de emergencia (pulsado y soltado), corte de energía o reinicio del PC en ciclo, tarjeta desconectada y reconectada, datos inválidos, puerta abierta en ciclo, sensor Principal perdido, caducidad de sesión en ciclo, apagado solicitado y cambio de programa.
- Para cada celda registra: estado destino, salidas, mensaje en UI, "NO ABRIR", bloqueo de nuevo ciclo, ticket/registro en BD (resultado y motivo) y si exige confirmación.
- Ejecuta cada celda con la planta simulada de E1 (tanda 3) en los 4 programas.
- Corrige con prueba toda discrepancia donde la spec sea explícita. Las ambiguas NO se cambian (regla 4, excepción); van como "PREGUNTA PARA CRISTIAN" con tu recomendación.
- Comprueba que se cumplen dos reglas: ningún fallo exige técnico para reiniciar (el operador reconoce y vuelve a PREPARACION), y tras un corte en ciclo no se reanuda, se arranca en seguro y el ciclo queda como interrumpido.
- Entregables: `docs/informes/tanda5/T1_matriz_transiciones.md` (tabla y discrepancias) y pruebas parametrizadas nuevas.

**U1. Cambio de unidades (núcleo y selector)** ★(`safety-reviewer`: un valor mal convertido en pantalla puede llevar a abrir la puerta con presión).
- Módulo único y neutral (sin Qt), p. ej. `core/runtime/unidades.py`, usado por QML (vía controlador o singleton) y por los generadores de ticket, PDF y correo. Debe tener:
  - Conversión de valores absolutos y de DIFERENCIAS. Una diferencia o tasa (histéresis, °C/min, kPa/min, la brecha ± de presión atmosférica, márgenes) se escala sin desplazamiento: Δ°F = 1,8·Δ°C, y Δpsi = ΔkPa/6,894757 sin restar la atmósfera.
  - Presión en psi: `psig = (P_abs − P_atm)/6,894757` si P_abs ≥ P_atm; si no, `inHg vac = (P_atm − P_abs)/3,386389`. Se muestra con su símbolo (`psig` o `inHg`); nunca un psi negativo.
  - `P_atm` es el parámetro calibrado del equipo (`presion_admosferica` o su nombre corregido), no 101,325. Si no hay valor vigente, en psi muestra "—", nunca un número inventado.
  - Kelvin no se ofrece.
  - Resolución de presentación (por defecto, DECISIÓN SIN CONFIRMAR): °C y °F 1 decimal; kPa 1; bar 2; mbar 0; psig 1; inHg 1. Formato numérico con el formateador único existente (`formato_numerico.py`).
  - Entrada de datos: el valor tecleado en la unidad mostrada se convierte a la interna, se redondea a la resolución interna del parámetro y se valida con los límites internos. La ventana de ajuste muestra mínimo, máximo y defecto convertidos.
  - En psi, si el rango de un parámetro cruza la atmosférica, la ventana ofrece elegir psig o inHg para ese ingreso (DECISIÓN SIN CONFIRMAR); si no lo cruza, la unidad es fija.
- Parámetros del equipo `unidades.temperatura` (`C`|`F`, defecto `C`) y `unidades.presion` (`kPa`|`bar`|`mbar`|`psi`, defecto `kPa`):
  - Editables por técnico e ingeniero, solo fuera de ciclo (409 en ciclo), con auditoría; admin solo lectura.
  - Selector en Opciones junto al selector de idioma (panel General o Parámetros del equipo, el que ya exista).
  - Cambio en caliente sin reiniciar.
  - Para el equipo de dos puertas, ambas UI comparten unidades.
- NO se convierten:
  - La lógica de control, alarmas, umbrales internos, BD, JSON ni la API (siguen en °C/kPa abs).
  - `audit_log` (guarda el valor interno con su unidad).
  - Las pantallas técnicas de Entradas/Salidas y de calibración por sensor. Siguen en °C y kPa absolutos fijos, con cuentas ADC (decisión del 20-oct sobre E/S). Es DECISIÓN SIN CONFIRMAR frente al pedido general; regístrala.
- Prueba estática: nada de `core/control`, `ControlLoop`, servicios de puertas ni alarmas importa el módulo de unidades.
- Pruebas: ida y vuelta en todas las unidades; diferencias contra valores absolutos; psig/inHg a ambos lados de la atmosférica y justo en ella; P_atm ausente; límites convertidos; edición fuera de rango; permisos; rechazo en ciclo; cambio en caliente.
- Riesgo ISO 14971: agrega la entrada "unidad o conversión de presión/temperatura mostrada errónea" con sus controles (prueba estática, conversión solo en presentación, unidad siempre visible junto al número) al fichero de riesgos si existe; si no, en el informe.

**I1. i18n F2 — backend y datos** ★(los tres agentes; es cambio de seguridad: alarmas y motivos de puerta). Según `planeacion_i18n.md` §5:
- Parámetro `idioma` con endpoint autenticado y auditoría (cualquier rol con sesión; permitido en ciclo).
- Catálogo de alarmas: `Alarm` con código + parámetros y unificación de familias de códigos.
- Motivos de puerta con código + parámetros (`RechazoApi`).
- `motivo_fallo` como código + parámetros y `audit_log.detalle` estructurado.
- `nombre_clave` en los ciclos de fábrica; etiquetas de roles y enums por catálogo.
- Las unidades ya no son texto incrustado: se formatean con U1.
- Compatibilidad hacia atrás: los registros históricos con texto libre se siguen mostrando.
- Regresión completa de alarmas y puertas. Prueba de que cada código de alarma y cada motivo existe en es y en.

**I2. i18n F3 — UI QML pantalla por pantalla, con unidades.**
- Orden: espera/arranque → login → preciclo/ciclo → Opciones → resto.
- Reemplaza las cadenas fijas por `I18n.t(...)` (patrón de §3.4). Incluye los literales de `Login.qml`/`NuevoUsuario.qml`, los meses de `BarraSuperior.qml`, los textos que Python entrega a QML y las etiquetas del teclado (D-18).
- En la misma pasada, todo valor de temperatura o presión visible pasa por el formateador de U1 con su símbolo, incluidas las gráficas (eje y unidad).
- Prueba automática: ninguna pantalla QML conserva literales visibles en español fuera del catálogo (lista blanca justificada).
- Capturas de preciclo, ciclo y una pantalla de Opciones en es y en, y en °F/psig, en `docs/informes/tanda5/`.
- Pantalla de 1024 px: sin textos truncados en inglés.

**I3. i18n F4 — salidas del backend, con unidades.**
- PDF (ciclo, resumen, consolidado), correo y tickets (ciclo, resumen, arranque, conectividad) en el idioma y las unidades vigentes al generar.
- Fechas según D-09.
- Separa estado de rótulo en el ticket de arranque (I18N-18).
- Ticket en cp437: verifica que `°` y los textos en inglés se imprimen (usa la impresora simulada).
- La cabecera del ticket y del PDF indica las unidades usadas.

**O2. Resto de Opciones** (según el inventario de O1, un commit por pantalla, hasta donde alcance).
- Orden: Parámetros del equipo (en lo que falte, incluidos `impresora.habilitada` y unidades), Usuarios, Fecha y hora, Información del sistema, Bitácora (solo lectura para admin), Conectividad, Respaldo/restauración.
- Opciones avanzadas (reasignación de E/S) queda FUERA de esta tanda.
- Lo que no alcance sigue en "Próximamente" y se lista.

**H1. Hoja de pruebas de banco.**
- Actualiza `hoja_pruebas_banco/pruebas.py` y regenera `.md`/`.html` con pruebas de:
  - P1: cada camino de salida del modo prueba.
  - P2 y P3.
  - O1: flujo, defecto, sensores, gestión de programas.
  - T1: las transiciones a verificar en el equipo real, sobre todo corte de energía, paro y puerta.
  - U1: cambio de unidades, psig/inHg con el equipo en vacío y en presión, ticket.
  - I2/I3: recorrido en inglés.
- Ids estables, sin renumerar.

**Z. Cierre.** Suite completa en verde; `git merge --no-ff tanda-5` en `dev`; `git push origin dev tanda-5` (si falla, anótalo). Escribe el índice, `estado.md` y `DECISIONES_PARA_REVISAR.md` con un resumen de 10 líneas arriba, y en una sección aparte todas las "PREGUNTA PARA CRISTIAN" de T1. Deja la lista de pasos manuales previos al lunes 26-oct. Nada a `main`.
