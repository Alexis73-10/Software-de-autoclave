# Planeación: Pantalla de ciclo en curso (QML)

Destino: `docs\mis_plans\planeacion_pantalla_ciclo_en_curso.md`
Rama de trabajo: `dev`
Fecha: 2026-10-01
Estado: borrador. Los puntos abiertos de la sección 14 que estén marcados como BLOQUEANTE deben resolverse antes de la Fase 1.
Referencia visual: `pantalla_ciclo_con_grafica_editada.png` (1200 x 1920 aprox., vertical). Los valores numéricos del mockup son ilustrativos.

---

## 1. Objetivo y alcance

Implementar en QML la pantalla que se muestra después de iniciar el ciclo y mientras este se ejecuta. Debe replicar el mockup de forma visual exacta y ser funcional desde el primer día, conectada al backend real.

Dentro del alcance:
- Pantalla completa de ciclo en curso (variante con gráfica), con todos los elementos del mockup.
- Cambios de backend necesarios para alimentarla: datos de progreso, lecturas completas e incrementales, duraciones por fase y tiempo restante.
- Cancelación del ciclo con diálogo de confirmación.
- Navegación de entrada y de salida.
- Renombrar la pantalla QML previa al inicio del ciclo (hoy llamada "ciclo") para evitar confusión con esta.

Fuera del alcance (se definen después):
- Estados distintos de "En ejecución" (alarma, finalizado, cancelado, falla) y su apariencia.
- Pantallas de resultado y confirmación de estados terminales.
- Apariencia de una fase completada en la barra de fases (ver 14.3).
- Configuración QML (se sigue abriendo la de PySide).
- Login QML (se sigue usando el login de PySide).
- Despliegue en equipos de campo: solo PC de desarrollo con backend real.

Esta pantalla NO incluye el botón de abrir/cerrar puerta ni "Iniciar ciclo" (pertenecen a la pantalla previa al inicio). "Pausar ciclo" no existe.

---

## 2. Reglas de trabajo para Claude Code

1. No asumir. Si algo no está en este documento o no es evidente en el código, detenerse y preguntar a Cristian antes de implementarlo.
2. Fase 0 es solo lectura. No modificar nada hasta que Cristian apruebe el informe de verificación.
3. tkinter está retirado: no importar ni reutilizar código tkinter. `cycle_window.py`, `cycle_buffer.py` y `ui_service_backend.py` se consultan solo como referencia de lógica.
4. Nada de reloj de pared para tiempos de proceso. Los tiempos del ciclo los calcula el backend con `time.monotonic()`; la UI solo los muestra (hallazgo C-01 del proyecto).
5. Los commits se hacen solo después de que Cristian confirme visualmente el resultado de cada fase.
6. Los textos visibles van en `ui_qml/assets/textos/es.json`, no en el QML. Los íconos son SVG Tiny 1.2 (presentation attributes en línea, texto convertido a trazos; sin CSS embebido, filtros ni degradados complejos).
7. Todo valor que no tenga lectura válida se muestra con el texto `sistema.sin_lectura` ("—") de `es.json`.

---

## 3. Fase 0: verificación (solo lectura)

Claude Code debe leer, resumir y reportar a Cristian, sin modificar nada:

1. `backend/server.py`: confirmar que existen y cómo funcionan `/status`, `/cycle`, `/cycle/current/readings`, `/cycle/abort`, `/cycle/acknowledge` y los endpoints de historial. Confirmar qué hace exactamente `/cycle/abort` (¿activa `CICLO_CANCELADO` y el protocolo de fallo de `CicloState`?).
2. Esquema de la tabla de lecturas: ¿guarda `temp_ref`? Hoy el endpoint solo devuelve `temp_camara` y `pres_camara`. ¿Cuál es la frecuencia real de muestreo en BD (el logger tiene intervalos de impresión de 60 a 180 s, pero eso puede ser solo para tickets)? ¿`timestamp_rel` proviene de reloj monotónico o de `time.time()`?
3. ¿Se guarda hoy la duración por fase de cada ciclo? Dónde, con qué esquema y desde qué momento. ¿Se guarda el identificador de programa y sus parámetros por ciclo?
4. Las fases del backend (`fase_ciclo`: PRECALENTAMIENTO, PURGA, PRE_VACIO, CALENTAMIENTO, ESTERILIZACION, SECADO, DESCOMPRESION, COMPLETADO, FALLO_*, CANCELADO, EMERGENCIA) frente a los códigos de `fase_codigo` de las lecturas (W, H, S, E u otros). Documentar el mapeo real hacia las 6 fases de la UI.
5. Qué dato exacto es el "ciclo activo" (el que el operador ve en historial y ticket: `numero_ciclo` frente al `id` de BD). Si hay duda, preguntar.
6. Pantallas QML existentes (espera, previa al inicio, login): cómo obtienen datos del backend (puente Python-QML, polling), cómo resuelven la responsividad, cómo implementan la campana de alarmas y su listado, el engranaje, el avatar y el banner de "sin conexión". Se reutiliza ese mecanismo; no se duplica.
7. Dónde se obtienen Modelo, Serie y versión ("V: 1.0") en la pantalla previa al inicio. Misma fuente aquí.
8. Parámetros del programa seleccionado en `/cycle`: nombres reales de temperatura de esterilización, tiempo de esterilización y tiempo de secado.
9. Inventario de assets (SVG y tipografías) disponibles frente a los que requiere la sección 5. Reportar los faltantes; no inventar íconos.
10. Versión de Qt/PySide en uso (condiciona la técnica de la gráfica, sección 8).
11. Cómo se lanzan las dos UI independientes (una por pantalla) y cómo se comporta esta pantalla en cada una.

Entregable de Fase 0: informe breve con hallazgos numerados `PCE-xx` y la lista de qué existe, qué falta y qué se propone crear. PARADA: esperar aprobación de Cristian.

---

## 4. Estructura general de la pantalla (de arriba a abajo)

Encabezado, tarjeta de ciclo, barra de fases, tarjeta de parámetros, gráfica, relojes con barra de progreso, barra inferior. Fondo azul con degradado y tarjetas blancas redondeadas, tal como el mockup. Colores, radios, sombras y espaciados se extraen del PNG. Tipografía: la del proyecto (Claude Code verifica cuál es).

---

## 5. Componentes: aspecto y comportamiento

### 5.1 Encabezado
- Logo e-specifika a la izquierda (asset existente).
- Hora grande al centro (HH:mm) y debajo la fecha con formato "12 oct - 2026" (mes abreviado en español, minúscula). Fuente: reloj del sistema.
- Campana con badge numérico de alarmas activas (de `/status` → `alarms`). Sin alarmas, el badge se comporta igual que en la pantalla previa al inicio. Al tocarla, mismo comportamiento y mismo componente de alarmas que esa pantalla.
- Engranaje: abre la configuración de PySide (temporal), igual que en la pantalla previa al inicio.

### 5.2 Tarjeta de ciclo
- CICLO ACTIVO: identificador del ciclo (ver Fase 0, punto 5), con al menos 2 dígitos ("03").
- PROGRAMA: nombre del programa seleccionado (`/cycle` → `name`), tal como venga del programa (el mockup muestra "BOWE & DICK").
- ESTADO: ícono `engranaje.svg` en círculo verde-turquesa y texto "En ejecución". Es el único estado del alcance. Actualizar `es.json` (hoy dice "Ejecutando").

### 5.3 Barra de fases
- Máximo 6 fases, en este orden: Precalentamiento, Vacío, Calentamiento, Esterilización, Descompresión, Secado. Ícono SVG gris y nombre debajo.
- Las fases que no aplican al programa se ocultan. El backend sabe cuáles aplican; hay que exponerlo en la API (sección 6). Si se ocultan fases, la distribución horizontal se recalcula.
- Estados visuales: activa (círculo azul con degradado y línea conectora azul hasta la siguiente, como el mockup), pendiente (gris) y completada (PENDIENTE de definir; ver 14.3).
- La fase activa viene del backend mapeado a la UI (ver 14.1). La UI no deduce la fase por tiempo.

### 5.4 Tarjeta de parámetros (5 valores)
- Temp est: temperatura de esterilización del programa (parámetro, fijo durante el ciclo), en °C, 1 decimal, sin cero a la izquierda.
- Tiempo Est.: tiempo de esterilización del programa, en min.
- Tiempo Sec.: tiempo de secado del programa, en min.
- Temp 1: temperatura de referencia en vivo (`sensors.temperature.ref`), °C, 1 decimal, sin cero a la izquierda.
- Presión: presión absoluta de cámara en vivo (`sensors.pressure.camara`), unidad "kPa" (no "°Kpa"), 1 decimal.
- Los sensores en vivo salen de una lista declarativa única en el código, con comentario: "Los sensores mostrados serán configurables desde configuración en el futuro". Por ahora solo estos (ver 14.4).
- Formato de Tiempo Est. y Tiempo Sec.: ver 14.6.

### 5.5 Gráfica
Ver sección 8.

### 5.6 Relojes y progreso
- "Tiempo transcurrido" (izquierda) y "Tiempo restante" (derecha), formato HH:MM:SS, tipografía grande como el mockup.
- Barra de progreso azul con degradado: transcurrido / (transcurrido + restante). Ancho completo bajo los relojes.
- Ambos tiempos vienen del backend (sección 7); la UI solo los refresca.
- Si el tiempo restante no se puede estimar (ver 14.3), mostrar "—" y la barra sin progreso estimado.

### 5.7 Barra inferior
- Izquierda: imagen del equipo (solo imagen, sin estado de puerta) y debajo "Modelo: ..." y "Serie: ..." (perfil de instalación/backend, misma fuente que la pantalla previa al inicio).
- Centro: avatar de usuario del login. Al tocarlo abre la ventana de login (PySide, por ahora).
- Derecha: botón rojo "CANCELAR CICLO" con ícono de stop (ver sección 10).
- "V: 1.0" abajo a la derecha (misma fuente que la pantalla previa al inicio).

---

## 6. Backend: cambios necesarios

Principio: la UI no calcula tiempos ni deduce fases. El backend expone todo.

B1. Nuevo endpoint `GET /cycle/current/progress` (separado de `/status` para no cargarlo, que se consulta cada 200 ms). Debe devolver, sin ciclo activo, un cuerpo vacío o explícito, y con ciclo activo:
- Identificador del ciclo (ver Fase 0, punto 5).
- Lista de fases de la UI que aplican al programa y fase de UI activa.
- Tiempo transcurrido total (monotónico), en segundos.
- Tiempo restante estimado (sección 7), en segundos, o nulo si no se puede estimar.
- Duración por fase del ciclo actual: fases completadas con duración final, fase activa con duración en curso, fases pendientes sin dato.
- Parámetros del programa necesarios para la tarjeta (temp est, tiempo est, tiempo sec), o confirmar que `/cycle` ya los entrega.

B2. Lecturas de la gráfica:
- Verificar si `/cycle/current/readings` alcanza. Hoy faltan `temp_ref` y existe el riesgo de devolver la lista completa en cada consulta.
- Agregar `temp_ref` (si la BD no lo guarda, requiere cambio de esquema: ver 14.5, necesita autorización de Cristian) y soporte incremental (parámetro tipo `desde` con `timestamp_rel`), de modo que la UI pida el histórico completo una vez al entrar y luego solo los puntos nuevos.
- Por instrucción de Cristian: si no hay forma de recrear la gráfica tras reiniciar la UI con los endpoints existentes, crear el endpoint necesario.
- Confirmar que la resolución de muestreo en BD sea suficiente para una gráfica en vivo (objetivo orientativo: 1 punto por segundo o mejor). Si no lo es, reportarlo; no cambiar la frecuencia de logging sin aprobación.

B3. Registro de duración por fase:
- Si hoy no se guarda por ciclo y por fase (inicio, fin, duración), crearlo (por ejemplo una tabla `ciclo_fases` con ciclo, fase UI, inicio relativo, fin relativo y duración), escrito por `CycleLogger` al detectar cada cambio de fase (ya detecta `_ultima_fase_codigo`). Requiere migración de esquema (ver 14.5).
- Guardar también si el ciclo terminó en COMPLETADO, para elegir referencias válidas.

B4. Fase de UI y fases aplicables: función del backend que traduzca `fase_ciclo` a las 6 fases de la UI y determine cuáles aplican al programa, con el mapeo aprobado en 14.1.

---

## 7. Estimador de tiempo restante (en el backend)

Módulo puro (sin acceso a hardware), con pruebas unitarias.

Referencia: duraciones por fase del último ciclo COMPLETADO del mismo tipo (mismo programa; ver 14.3 para casos especiales). Ejemplo de Cristian: instrumental 134 duro, 45 min.

Reglas:
1. Al iniciar el ciclo, tiempo restante inicial = suma de las duraciones de referencia de las fases que aplican.
2. Durante la fase k, con `e` = tiempo transcurrido en la fase y `d_k` = duración de referencia:
   - Mientras `e < d_k`: restante de la fase = `d_k - e`.
   - Cuando `e >= d_k` (la fase se alarga respecto al ciclo de referencia): el restante de la fase pasa a ser 5 min y se renueva con 5 min más cada vez que se agota, hasta que cambie de fase. Formalmente, restante de la fase = `5 min - ((e - d_k) mod 5 min)`. Ejemplo de Cristian: si la fase de calentamiento duró 15 min antes y ya pasaron 15 min, se suman 5 min al restante. (Interpretación a confirmar: 14.3.)
3. Tiempo restante total = restante de la fase activa + suma de las duraciones de referencia de las fases siguientes que aplican.
4. Al cambiar de fase se vuelve a calcular el restante con la nueva fase activa (por construcción de la regla 3).
5. Constante `EXTENSION_MIN = 5` en un solo lugar, documentada.
6. Sin referencia disponible: ver 14.3 (no inventar valor).

La UI nunca suma ni resta tiempos por su cuenta.

---

## 8. Gráfica

Decisión (delegada a Claude): dibujo propio con QtQuick (`Shapes`, con `PathPolyline` si la versión de Qt lo soporta; `Canvas` como respaldo), sin QtCharts ni QtGraphs. Justificación: evita un módulo Qt adicional (menos SOUP y sin implicaciones de licencia), da control total para replicar el mockup (dos ejes, cursor, divisores) y el volumen de puntos es manejable con decimación. Claude Code confirma con la versión de Qt (Fase 0) y reporta si algo lo impide.

Elementos:
- Título "GRÁFICA DEL CICLO", leyenda de 3 series con colores del PNG: Temp Cámara (azul), Temp Ref (morado), Presión (turquesa).
- Series (lista declarativa única, con comentario de que serán configurables): `temp_camara` y `temp_ref` en el eje izquierdo (°C), `pres_camara` absoluta en el eje derecho (kPa).
- Ejes autoajustables:
  - Eje X (tiempo, min): desde 0 hasta el tiempo actual redondeado al siguiente paso de marca; la curva solo existe hasta el instante actual, no hay curva futura. Paso de marcas elegido de forma "limpia" (1, 2, 5, 10, 15, 30, 60 min) para no pasar de unas 8 a 9 etiquetas.
  - Ejes Y: mínimo 0, máximo autoajustado con margen sobre el dato máximo, mismo número de divisiones (5) en ambos ejes para que las líneas de cuadrícula coincidan, con pasos "limpios" en cada eje de forma independiente. Etiquetas "°C" y "Kpa/kPa" como el mockup, con unidad correcta "kPa".
- Divisores de fase: línea vertical punteada que se dibuja cuando comienza cada fase (coincide con el fin de la anterior), con el ícono SVG de la fase arriba del segmento. No se muestran nombres de fases dentro de la gráfica. Los límites de fase salen del backend (cambios en la fase de las lecturas o del endpoint de progreso), no de un reloj de la UI.
- Cursor interactivo: al tocar o arrastrar sobre el área de la gráfica aparece una línea vertical con un punto sobre cada serie y un tooltip con el tiempo (mm:ss) y los valores de las 3 series con su unidad y 1 decimal, como el mockup. El tooltip no se sale del área visible. Se oculta solo tras 5 s sin interacción (constante configurable; valor por defecto elegido por Claude, a validar visualmente).
- Rendimiento: decimación (por ejemplo mínimo y máximo por columna de píxeles) para dibujar un tope de puntos razonable, sin perder picos.
- Carga: al entrar a la pantalla, pedir el histórico completo del ciclo actual y luego solo lecturas incrementales. Si la UI se reinicia a mitad de ciclo, la gráfica se reconstruye con el histórico.
- Desplegable "Tiempos": lista de las fases que aplican con el tiempo individual de cada una (por ejemplo cuánto tardó el vacío o la esterilización). Fases completadas muestran su duración final; la activa, su duración en curso con actualización en vivo; las pendientes, "—". Los datos vienen de B1.
- Botón de pantalla completa (esquina superior derecha): muestra solo la gráfica (con su leyenda y ejes) a pantalla completa y un botón de cerrar. El cursor interactivo y la actualización en vivo continúan mientras está abierta. Sin otros elementos de la pantalla.

---

## 9. Navegación y ciclo de vida

- Entrada: la pantalla se activa cuando el backend reporta estado de máquina CICLO (no por la pulsación local de "Iniciar ciclo"). Si la UI arranca o se reinicia con la máquina ya en CICLO, abre directamente esta pantalla y reconstruye la gráfica.
- Dos UI independientes (una por pantalla/monitor): ambas muestran esta pantalla, sin compartir estado entre procesos; la coherencia viene del backend. Cancelar desde cualquiera produce el mismo efecto.
- Salida: al terminar o cancelar el ciclo, vuelve a la pantalla previa al inicio del ciclo. Los estados terminales y su confirmación están fuera del alcance (ver 14.2 sobre la confirmación `/cycle/acknowledge`).
- Mientras esta pantalla esté activa no aplica la transición de la pantalla de espera por inactividad (si existe en el flujo, Claude Code lo verifica en Fase 0 y reporta).
- Engranaje y avatar abren las ventanas de PySide indicadas en 5.1 y 5.7 sin interrumpir el ciclo ni el polling.

---

## 10. Cancelación del ciclo

- Se puede cancelar en cualquier momento y en cualquier fase.
- Flujo: toque en "CANCELAR CICLO" abre un diálogo de confirmación (solo confirmación, sin credencial ni rol). Confirmar envía `POST /cycle/abort`.
- Textos del diálogo (propuesta, en `es.json`): mensaje que indique que el ciclo se cancelará, botones "Confirmar" y "Cancelar" (claves existentes en `acciones`).
- Anti doble toque: tras confirmar, deshabilitar el botón hasta recibir respuesta.
- Si el envío falla (`abort_cycle` devuelve False o no hay conexión): mostrar un aviso claro y permanecer en la pantalla; no navegar ni dar el ciclo por cancelado.
- El backend ejecuta el protocolo de fallo/cancelación (`CicloState` → CICLO_CANCELADO → protocolo). Verificar en Fase 0 que `/cycle/abort` lo dispara; si no existe o no hace eso, reportar y crear el endpoint correcto.
- Esta es una acción de seguridad (Clase C): no se agregan atajos ni comportamientos no especificados.

---

## 11. Responsividad

- Base de diseño: 1200 x 1920. Debe adaptarse a otras pantallas, incluyendo 9:16 o similares. Aplica a todas las pantallas del software.
- Reutilizar el mecanismo de escalado que ya usen las pantallas QML existentes (Fase 0, punto 6). Si no existe uno común, proponerlo a Cristian antes de implementarlo; no inventar uno por pantalla.
- Criterios mínimos: ningún elemento recortado ni superpuesto en 1200x1920 ni en 1080x1920 (9:16); textos legibles; la gráfica absorbe el espacio vertical sobrante o faltante.

---

## 12. Textos y assets

- `es.json`: actualizar "En ejecución", agregar claves nuevas (diálogo de cancelación, "Tiempos", "Temp est", etc.). No eliminar claves que use otra pantalla. La clave `sensores[0]` actual ("precalentamiento") no coincide con el mockup ("Temp est"): ajustar con cuidado, verificando quién la usa.
- Assets requeridos: logo, campana, engranaje (`engranaje.svg`), 6 íconos de fase, termómetro, reloj, manómetro, imagen del equipo, avatar, ícono de stop, ícono de pantalla completa, flecha del desplegable. Reportar los que falten (para pedirlos al diseñador, que trabaja en Illustrator/CorelDRAW). Validar todos los SVG contra Qt SVG Tiny 1.2.

---

## 13. Hallazgos

Numeración propia de este plan (a completar en Fase 0).

- PCE-01 (ALTA, verificar): `/cycle/current/readings` no incluye `temp_ref`; sin ese dato la serie Temp Ref no se puede reconstruir tras reiniciar la UI.
- PCE-02 (ALTA, verificar): no se sabe si existe registro de duración por fase por ciclo; es requisito del estimador de tiempo restante y del desplegable "Tiempos".
- PCE-03 (ALTA): el backend deja el ciclo en `ESPERANDO_CONFIRMACION` hasta que `/cycle/acknowledge` activa `CICLO_CONFIRMADO` (mantiene drenaje y válvula de reposo). Navegar a la pantalla previa sin resolver esto puede dejar la máquina en CICLO. Ver 14.2.
- PCE-04 (MEDIA): `CycleBuffer` (tkinter) calcula tiempos con `time.time()`. No portar esa lógica; usar el tiempo monotónico del backend (C-01).
- PCE-05 (MEDIA): `/cycle/current/readings` devuelve todas las lecturas en cada consulta. Hacerlo incremental.
- PCE-06 (MEDIA, verificar): confirmar que `/cycle/abort` activa realmente el protocolo de cancelación de `CicloState`.
- PCE-07 (MEDIA): `PURGA` y `PRE_VACIO` frente a una sola fase "Vacío" en la UI; el mapeo no está definido (14.1).
- PCE-08 (MEDIA, relacionado con H-03 / UI-07): `/cycle/abort` y los endpoints de acción no tienen autenticación y el backend escucha en todas las interfaces. La cancelación desde esta pantalla queda expuesta si se habilita red. No se resuelve aquí; permanece abierto.
- PCE-09 (BAJA): el mockup muestra "°Kpa" y valores con cero a la izquierda ("085.0"); se corrigen a "kPa" y sin cero (decisión de Cristian).
- PCE-10 (BAJA): el mockup es inconsistente en formato (Tiempo Est. "10.0", Tiempo Sec. "15"). Ver 14.6.

---

## 14. Puntos abiertos

BLOQUEANTES (deben resolverse antes de la Fase 1):

14.1 Mapeo de fases backend → UI. Propuesta: PRECALENTAMIENTO → Precalentamiento; PURGA y PRE_VACIO → Vacío; CALENTAMIENTO → Calentamiento; ESTERILIZACION → Esterilización; DESCOMPRESION → Descompresión; SECADO → Secado. Cristian debe confirmar, en especial dónde cae PURGA.

14.2 Confirmación al terminar o cancelar: la salida va a la pantalla previa al inicio, pero el backend espera `/cycle/acknowledge`. ¿La UI llama `/cycle/acknowledge` automáticamente al navegar, o se deja para cuando se definan los estados terminales (y mientras tanto cómo se sale)?

14.3 Tiempo restante:
- Confirmar la interpretación de la regla de +5 min (sección 7, regla 2).
- Referencia: último ciclo COMPLETADO del mismo programa. ¿Correcto? Un ciclo cancelado o fallido no sirve como referencia.
- Sin ciclo de referencia (primer ciclo del programa): ¿qué se muestra? (propuesta: "—").
- Si el programa se editó después del ciclo de referencia, ¿esa referencia sigue valiendo?

14.4 "Los 3 sensores": se interpreta como las 3 series de la gráfica (Temp Cámara, Temp Ref, Presión), con Temp 1 de la tarjeta = temperatura de referencia. Confirmar.

14.5 Cambios de esquema de BD (agregar `temp_ref` a lecturas y/o tabla de duración por fase): requieren autorización explícita de Cristian tras ver el informe de Fase 0.

14.6 Formato de Tiempo Est. y Tiempo Sec. (el mockup muestra "10.0" y "15"): ¿entero, 1 decimal o tal como esté definido el parámetro?

14.7 Nombres: se propone `PantallaPreciclo` para la pantalla actual previa al inicio y `PantallaCicloEnCurso` para la nueva. Confirmar antes de renombrar.

14.8 Apariencia de la fase completada en la barra de fases: pendiente de definición. Mientras tanto, el componente expone un estado "completada" separado, con apariencia provisional igual a la activa y marcado con comentario `TODO-DISEÑO`.

Decisiones delegadas a Claude (a validar visualmente por Cristian): polling de `/status` a 200 ms (igual al cliente existente), `/cycle/current/progress` y lecturas incrementales a 1 s; técnica de la gráfica (sección 8); auto-ocultar del cursor a 5 s; ejes con mínimo 0 y 5 divisiones; paso de marcas del eje X; fases pendientes como "—" en el desplegable "Tiempos".

---

## 15. Pruebas y criterios de aceptación

Pruebas automáticas (pytest, carpeta `tests` existente):
- Estimador de tiempo restante: ciclo normal, fase que se alarga (una y varias extensiones de 5 min), cambio de fase, sin referencia, fase omitida.
- Mapeo de fases y lista de fases aplicables.
- Endpoints nuevos o modificados: sin ciclo activo, con ciclo activo, lecturas incrementales, lecturas con `temp_ref`.
- Cancelación: éxito y fallo del envío.

Verificación manual (backend real en PC de desarrollo; Claude Code reporta exactamente qué corrió):
1. Comparar con el PNG en 1200x1920 y en 1080x1920 (9:16).
2. Iniciar un ciclo desde la pantalla previa: entra a esta pantalla sola.
3. Recorrer fases: barra de fases, divisores y desplegable "Tiempos" avanzan con el backend.
4. Gráfica: autoescala de ejes, cursor táctil, auto-ocultar, pantalla completa y cierre.
5. Reiniciar la UI a mitad de ciclo: reabre en esta pantalla con la curva reconstruida.
6. Cancelar con confirmación; cancelar con el backend caído (aviso, sin navegar).
7. Campana, engranaje y avatar abren lo mismo que en la pantalla previa al inicio.
8. Backend caído: banner de sin conexión y valores en "—".
9. Dos UI simultáneas muestran los mismos datos.

Criterio de aceptación: la pantalla replica el mockup, todos los elementos responden con datos reales, no queda ningún valor inventado ni cableado, y Cristian lo confirma visualmente.

---

## 16. Orden de ejecución y puntos de parada

- Fase 0: verificación y informe. PARADA para aprobación.
- Fase 1: backend (B1 a B4), pruebas unitarias, y migraciones solo si 14.5 fue autorizado. PARADA, confirmación de Cristian y commit.
- Fase 2: componentes QML estáticos con el aspecto exacto del mockup y datos de ejemplo claramente marcados. PARADA, confirmación visual y commit.
- Fase 3: conexión a datos reales (parámetros, sensores, fases, tiempos), gráfica en vivo, cursor, desplegable y pantalla completa. PARADA, confirmación y commit.
- Fase 4: navegación de entrada y salida, cancelación, campana, engranaje y avatar. PARADA, confirmación y commit.
- Fase 5: renombrar la pantalla previa al inicio (cambio aislado, commit propio) y pruebas finales de la sección 15.

En cualquier fase, si aparece algo no contemplado, detenerse y preguntar.
