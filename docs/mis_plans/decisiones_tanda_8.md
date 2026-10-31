# Decisiones para la tanda 8 (en curso, 22-oct-2026)

Las fue tomando Cristian en el chat del 22-oct, a partir de las preguntas de la tanda 7. Esta es la fuente de verdad para la instrucción de la tanda 8.

## D8-0. Nombres de familia: Hospitalario y Laboratorio
- Ya no hay equipos de mesa, así que las dos familias se llaman así en la interfaz:
  - `piso` → "Hospitalario" (en inglés "Hospital");
  - `piso_lab` → "Laboratorio" (en inglés "Laboratory").
- Aplica al asistente, al ticket de arranque, a Información del sistema, al PDF y a cualquier otro lugar donde se muestre la clase. Corrige además "Clase: piso_lab" sin traducir en el ticket de arranque (pregunta de M1).
- SOLO cambia el texto visible, por catálogo i18n. Los valores internos `piso` y `piso_lab` del perfil, la validación y la lógica NO cambian.
- El nombre del modelo sigue siendo `SPK-SAT …[-LAB]`.

## D8-1. SEN-01: transductor de presión sin señal ★
Contexto: `hal/measures/converters.py::convert_pressures` recorta con `max(0.0, valor)`, así que un lazo abierto lee 0,0 kPa y el ciclo y el protocolo de fallo lo toman como lectura válida (el protocolo lo interpreta como vacío). Los transmisores de presión son de 4-20 mA y la tarjeta convierte la señal (`planeacion_arranque_y_modo_sin_bd.md` §SEN-02).
1. **Detección, sobre la señal cruda, ANTES de calibrar y recortar.**
   - Criterio NAMUR NE43: por debajo de 3,6 mA o por encima de 21 mA el sensor está en falla.
   - Se traduce a cuentas ADC con la calibración de fábrica del canal (`adc_min` = 4 mA y `adc_max` = 20 mA):
     - umbral bajo = `adc_min − 0,025·(adc_max − adc_min)`;
     - umbral alto = `adc_max + 0,0625·(adc_max − adc_min)`.
   - Los dos márgenes son parámetros de configuración, porque se ajustan con la prueba de banco del 22-oct (abajo). Si la tarjeta satura en 4095 antes de los 21 mA, la detección alta queda inactiva y se documenta.
   - Hacen falta 3 lecturas seguidas fuera de rango para declarar la falla, y 3 dentro para volver.
   - El canal entrega "sin lectura" (`None`), NUNCA 0. La UI muestra "—".
2. **Con ciclo en curso**, mismo criterio que P-2:
   - el ciclo falla con un código propio, "Sensor de presión de cámara sin lectura", con textos en es/en en el catálogo de alarmas;
   - se corta el vapor y se ventea SOLO por la lenta;
   - el protocolo de fallo NUNCA interpreta "sin lectura" como vacío ni abre el aire atmosférico por ese motivo.
3. **Fuera de ciclo:**
   - el inicio queda bloqueado con "Sensor de presión de cámara sin lectura: llame a servicio";
   - "NO ABRIR" se mantiene, porque sin presión no se puede confirmar que la cámara esté segura.

   Que el sensor dañado requiera servicio no contradice D-06 (mismo criterio que P-2).
4. **Alcance:**
   - la misma detección y el mismo comportamiento aplican al sensor de presión de chaqueta: en ciclo, FALLO; fuera de ciclo, bloquea el inicio;
   - se aplica solo a los canales de presión habilitados en el perfil o en `io_enabled`. El equipo de pruebas no tiene sensor de empaque.
5. **Verificación:**
   - pruebas unitarias del convertidor (bajo, alto, debounce, recuperación) y de las transiciones con la planta simulada;
   - entrada en el registro de riesgos;
   - casos en la hoja de banco;
   - revisores safety, timing y sensor-role sin Altos.

### Prueba de banco para HOY, en el equipo (la hace Cristian; alimenta D8-1)
Con el software en Opciones › Entradas/Salidas › Presión, que muestra las cuentas ADC:
1. Anota las cuentas del sensor de cámara y del de chaqueta a presión atmosférica.
2. Con el equipo sin presión, desconecta el lazo de cada transmisor y anota las cuentas: es el caso de lazo abierto.
3. Si es posible y seguro, haz un corto del lazo a la alimentación y anota las cuentas: es el caso de sobrecorriente.

Pásame los valores para fijar los umbrales.

## D8-2. Transiciones del ciclo ★ (aceptadas las recomendaciones, 22-oct 10:38)
Base: el informe de Q1 y el índice de la tanda 7, sección "PREGUNTAS PARA CRISTIAN".
- **D8-2.6 (`permite_salir_de_falla` + R1-P4):** se mantiene la regla de P-2. Una vez el protocolo está en `solo_lenta`, se sale de FALLA sin técnico, aunque se haya llegado ahí con el protocolo ya en marcha. "NO ABRIR" sigue hasta que la cámara esté segura.
- **D8-2.7 (T2-a ampliado):** la desconexión total de la tarjeta de menos de 5 s (antes de COM-02) y la ventana después de reconectar también pausan la exposición en ESTERILIZACION. Principio: los segundos sin datos válidos nunca cuentan como esterilización. El F0 tampoco se acumula en esos segundos.
- **D8-2.8 (tope de pausa):** si en una misma exposición las pausas suman más de `pausa_max_esterilizacion_s` (parámetro del equipo, 30 s por defecto, rango 5–120), el ciclo falla con un código propio, "Comunicación inestable en esterilización", con textos en es/en.
- **D8-2.9 (TMG-04):** DESPEJAR de COM-02/03 y la salida de la tolerancia exigen 3 tramas DI DISTINTAS y nuevas (por número de secuencia o marca de tiempo de la trama), no 3 ticks.
- **D8-2.10 (líquidos, modos 4/5, se pierde el Principal durante el enfriamiento con contrapresión):**
  - NO se ventea de inmediato;
  - la cámara queda sellada con la contrapresión y el vapor cortado mientras alguna otra sonda válida (Referencia o drenaje) esté por encima de `temp_max_apertura`; cuando todas las válidas estén en o por debajo de ese valor (3 lecturas), se ventea por la lenta;
  - si no queda ninguna sonda válida, se espera sellado `espera_sellado_sin_sonda_min` (parámetro, 30 min por defecto, rango 10–240) y luego se ventea por la lenta;
  - el ciclo termina en FALLO y "NO ABRIR" sigue según la cámara segura.

  Antes de implementarlo, Code revisa que la contrapresión pueda mantenerse con las salidas existentes (qué válvulas quedan en qué estado). Si eso no está claro en el código, se implementa solo la espera sellada con TODAS las salidas cerradas, y lo deja como PREGUNTA.
- **D8-2.11 (Q1-P1):** si la tarjeta no confirma el ALL_OFF al salir del modo prueba, se reintenta 3 veces. Si sigue sin confirmar, sale la alarma "Salidas sin confirmar" (catálogo, bloquea el inicio) hasta que llegue una confirmación. Se registra en la bitácora.
- **D8-2.12 (Q1-P2):** durante la tolerancia por DI vencida se pausan las ventanas de estabilidad de todas las fases; los timeouts de fase siguen corriendo, porque son límites de seguridad.
- **D8-2.13 (Q1-P4):** con la tarjeta totalmente desconectada (antes de COM-02), `/cycle/abort` también se acepta como "cancelación en espera", igual que en R1-P5.
- **D8-2.14 (Q1-P5):** columna JSON nueva en `ciclos` (migración), con las líneas de aviso del ticket ("Sin datos de la tarjeta: n s", avisos de uniformidad y similares), para que la reimpresión sea idéntica al ticket original.
- **D8-2.15 (Q1-P6):** la QML muestra, con textos del catálogo, la "cancelación en espera" y el motivo del rechazo de DESPEJAR, en lugar del texto de la excepción HTTP.
- **D8-2.16 (Q1-P7):** la pantalla de resultado del ciclo también muestra "CARGA NO ESTÉRIL" en todo ciclo que no termine COMPLETADO.

## D8-3. Instalación, equipo y pendientes menores (aceptadas las recomendaciones, 22-oct 10:43)
- **D8-3.17 (`io_enabled`):** los canales habilitados se derivan del perfil de instalación, sin editar YAML a mano.
  - Fuentes: `temperature_probes`, `supply_inputs`, `door_count`/`door_type` y `vapor_source`.
  - El YAML de la instancia queda solo como el máximo físico posible, y un canal que el perfil no declara no aparece.
  - Pruebas con el perfil del equipo de pruebas: cámara 1, cámara 2, referencia y drenaje; solo aire comprimido; generador interno; 2 puertas abatibles simples.
- **D8-3.18 (calibración en la entrega):** la entrega lleva una calibración NEUTRA, no los valores del banco. La etapa de compilación verifica que el `calibration.yaml` empaquetado sea igual a la plantilla neutra y falla si no lo es.
- **D8-3.19 (modo prueba, `aire_atmosferico_camara`):** es la ÚNICA excepción a "el modo prueba permite todas las salidas" (D-ES-15). Esa salida se rechaza si la presión de cámara es mayor que la atmosférica de referencia más la brecha, o si no hay lectura de presión (D8-1). El motivo se muestra con texto del catálogo.
- **D8-3.20 (un monitor):** sin detección automática. Se conserva `--una-pantalla`, documentado en el LEEME, con un acceso directo de ejemplo.
- **D8-3.21 (apagado rechazado por Windows):** si Windows rechaza el apagado, la pantalla muestra, con texto del catálogo, "Windows no permitió apagar el equipo: apáguelo manualmente". Se registra en la bitácora.
- **D8-3.22 (texto final del asistente):** "Instalación completada" con el botón Continuar, en lugar de "Reinicie el software".
- **D8-3.23 (capacidad y carga):** en el ticket va solo el nombre del modelo. La capacidad y el tipo de carga van en la cabecera del PDF y en Información del sistema (ya están).
- **D8-3.24 (correo):** se mantiene lo de C2: un rechazo parcial se muestra en rojo con las direcciones rechazadas, más el paso de confirmación.
- **D8-3.25 (mantenimiento):**
  - "Último mantenimiento" pasa a llamarse "Último preventivo";
  - se elimina el tipo `otro` (P-3); las filas históricas se muestran como "Otro (histórico)", con el mismo criterio que MNT-05;
  - MNT-04: el admin consulta el historial (`GET /maintenance/records`).
- **D8-3.26 (dependencias):**
  - `requirements.lock.txt` con SOLO las dependencias del producto, generado desde un entorno virtual limpio creado para eso;
  - `requirements-dev.txt` aparte (pytest y herramientas);
  - en `pyproject.toml`, quitar `pyqtgraph`, `tk` y `SQLAlchemy` y agregar `fastapi`, `uvicorn`, `requests`, `psutil` y `python-escpos`;
  - actualizar la lista SOUP.
- **D8-3.27 (depuración, P1 a P12 de D2):** se aceptan las recomendaciones de `D2_depuracion.md`:
  - conservar los arneses QML de prueba y `ui_qml/domain/{alarmas,reconexion,telemetria}.py`;
  - retirar `ui_pyside/views/_email_dialog.py`;
  - mover los mockups y las imágenes de diseño de `src/autoclave/images/` a `docs/diseno/` para que no se empaqueten, verificando antes que nada los cargue;
  - etapa aparte con `safety-reviewer` para el posible código muerto en zonas de seguridad (P5);
  - sacar `estudio/` del repositorio: moverlo a `C:\Users\tecni\Documents\estudio_autoclave\` (fuera del repo) y dejar de versionarlo;
  - no tocar `main`;
  - P8: quitar el worktree de `alarmas-parte-a` (después de copiar `docs/informes/lotes_auditoria/` a `dev` si no está) y borrar la rama local;
  - P9: borrar la rama local `audit/62304-snapshot` (queda en `origin`);
  - P10 y P11: archivar `feature/roles-sensor-temperatura` y `worktree-anuncios-voz` con una etiqueta `archivo/<nombre>` empujada a `origin`, quitar sus worktrees y borrar las locales;
  - P12: quitar `wt_rc` después de comprobar que su `data/` no tiene nada que guardar.

  Los borrados de ramas con `-D` (P8–P11) están autorizados SOLO después de que exista la etiqueta o la rama en `origin`.

## D8-4. Navegación en Opciones y cierre de sesión (Cristian, 22-oct 11:08)
- **D8-4.1 (Atrás con historial):** Opciones lleva su propio historial de navegación: una pila que guarda sección y subnivel (por ejemplo, Parámetros del ciclo › programa › Calentamiento).
  - Cambiar de sección desde el cajón (por ejemplo, a Mantenimiento) agrega un nivel.
  - Atrás regresa exactamente al nivel anterior (de Mantenimiento a Parámetros del ciclo › Calentamiento), con el mismo programa, la misma fase y el desplazamiento de la lista conservados.
  - Si hay una ventana de ajuste abierta, Atrás la cierra primero, y pide confirmación si hay cambios sin guardar.
  - Con la pila vacía, Atrás sale de Opciones a la pantalla desde la que se entró (Menú principal, Preciclo o Ciclo).
  - Home sigue saliendo de todo a Preciclo o Ciclo (regla del 19-oct).
  - Aplica a todas las secciones y subniveles de Opciones.
  - Pruebas QML: recorridos de varias secciones de ida y vuelta, ventana de ajuste abierta y pila vacía.
- **D8-4.2 (Cerrar sesión):** el botón cierra la sesión (token invalidado en el backend) y lleva a la pantalla de LOGIN, no a Preciclo ni a Ciclo.
  - Desde ese Login, Atrás/Home lleva a Preciclo o Ciclo según corresponda.
  - Un login correcto sigue el flujo normal de login.
  - Si hay cambios sin guardar, se confirma antes de cerrar.
  - El cierre por inactividad (5 min) mantiene su comportamiento actual.
  - Prueba QML del recorrido.

## D8-5. Observaciones de Cristian sobre la UI (22-oct 11:58)
- **D8-5.1 (cambiar el ciclo tocando el número en Preciclo):** el selector existe desde la tanda 4 (B6, `zonaProgramaTocable` y `ventanaSelectorCiclo`), pero solo responde si se cumple todo esto:
  - hay datos vigentes de la tarjeta;
  - el estado es PREPARACION o PREPARADO;
  - no hay estado seguro, paro ni modo prueba;
  - la zona que se toca es el recuadro "Programa".

  **Decisión de Cristian (12:08):** el programa se puede cambiar AUNQUE la tarjeta no esté conectada ni haya datos vigentes. Seleccionar un programa no acciona nada: el inicio del ciclo sigue exigiendo datos, sensores y todas las condiciones actuales.
  - Se quita `datosVigentes` de `programaTocable`, y el backend (`POST /cycle/select`) tampoco lo exige.
  - Se conservan los bloqueos con ciclo en curso, paro, estado seguro y modo prueba.
  - En FALLA se conserva el cambio de ciclo (decisión del 19-oct).
  - Code reproduce el caso, con tarjeta simulada y sin tarjeta.
  - El número del ciclo también tiene que ser zona tocable.
  - Cuando el selector no esté disponible, al tocar se muestra el motivo, con texto del catálogo. Nunca deja de responder en silencio.
- **D8-5.2:** la barra inferior flotante tiene EXACTAMENTE el mismo ancho que la tarjeta de contenido que está encima, en todas las pantallas. Prueba de geometría por pantalla.
- **D8-5.3:** el botón de confirmación del registro de mantenimiento dice solo "Registrar" (en inglés "Register").
- **D8-5.4:** NINGÚN texto visible se abrevia ni se recorta ("Ester.", "Add" y similares): siempre la palabra completa.
  - Si no cabe, el componente se ajusta (dos líneas, fila más alta o letra un punto menor, con un mínimo legible). Nunca se recorta con puntos suspensivos ni se abrevia.
  - Prueba automática sobre los catálogos con la lista de abreviaturas conocidas, más la revisión de truncado en es y en, con capturas.
- **D8-5.5 (sin mezclar idiomas):** el catálogo en español no lleva palabras en inglés ("timeout" → "tiempo límite"; también "setpoint", "OK", "reset", "log" y similares) y el inglés no lleva palabras en español.
  - Excepciones solo para nombres propios, unidades y marcas (SPK-SAT, F0, Bowie & Dick).
  - Prueba automática con una lista de anglicismos prohibidos en `es.json` y de palabras en español en `en.json`.
  - La lista de cambios va en `revision_traducciones.md`.
- **D8-5.6 (Reportes):** en el resumen por tipo de fallo, tocar un tipo despliega el listado de los ciclos con ese fallo: número, fecha y hora, programa y operador. Tocar un ciclo abre su detalle o la reimpresión, como desde el Historial. Paginado si son muchos.
- **D8-5.7 (tipo de carga en Parámetros del ciclo, aprobado a las 12:08)** ★:
  - el tipo de carga es un selector Sólido/Líquido, sin mínimo ni máximo;
  - al pasar a Líquido, el modo de descompresión cambia a 4 y la pantalla avisa del cambio con un texto del catálogo;
  - con carga líquida solo se permiten los modos 4, 5 y 0, tanto en la UI como en el backend: cualquier otro se rechaza con su motivo, porque descomprimir rápido con líquido caliente produce ebullición violenta;
  - al volver a Sólido, el modo vuelve al valor por defecto de fábrica de ese programa; si el programa no tiene un defecto sólido, usa el modo 1 y lo anota como DECISIÓN SIN CONFIRMAR;
  - cada cambio, incluido el automático, queda en la bitácora.
- **D8-5.8:** el modo de secado se elige de una lista con los modos válidos y su descripción, no se escribe. Lo mismo aplica a cualquier parámetro "modo" de los programas, incluido el modo de descompresión.
- **D8-5.9:** la explicación de los modos se muestra como lista, una viñeta por modo con nombre y una línea de descripción, no como texto corrido.
- **D8-5.10:** TODAS las pantallas y submenús de Opciones llevan la barra inferior flotante (decisión 1.7 de la tanda 6), que no se aplicó a los menús de Opciones. Verificación pantalla por pantalla, con capturas.
- **D8-5.11:** faltan textos por traducir. Hay que hacer el barrido completo de literales QML y de cadenas que Python entrega a la UI sin pasar por el catálogo, con una prueba que falle si una clave existe en es y no en en, o al revés. Capturas de todas las pantallas en inglés.
- **D8-5.12 (Opciones avanzadas = reasignación de E/S, por ahora)** ★. Cristian (12:08): por el momento, Opciones avanzadas contiene solo la reasignación de entradas y salidas. La configuración de la máquina ya está en Parámetros del equipo y el respaldo en su propia sección. Aplica la regla R-03 de `planeacion_opciones.md` v4 y OPC-03:
  - solo el INGENIERO (§3.5). Hoy el código da la sección a técnico e ingeniero; se corrige y se marca DECISIÓN SIN CONFIRMAR;
  - solo fuera de ciclo (R-01);
  - pide reautenticación;
  - doble confirmación con alerta de criticidad;
  - detecta conflictos (dos funciones en el mismo puerto físico, o un puerto inexistente en la tarjeta) y los rechaza en el backend, no solo en la UI;
  - las funciones de interlock de puerta, el paro de emergencia y los finales de carrera llevan una confirmación reforzada: escribir el nombre de la función;
  - la tabla muestra función, puerto actual, puerto nuevo, tipo (DI/DO/AI) y si la función es crítica;
  - "Restaurar asignación de fábrica", con confirmación;
  - la asignación vigente se guarda en la carpeta de datos persistente del equipo (`ProgramData`), nunca dentro del ejecutable. La de fábrica sigue en el YAML de la instancia. Respaldo y restauración (O2h) la incluyen;
  - la bitácora registra la función, el puerto anterior, el puerto nuevo y el usuario;
  - para aplicar, se reinicia el backend con la confirmación "Se reiniciará el control"; después se verifica que la lectura de la función en su puerto nuevo responde;
  - sin mockup aprobado, sigue el estilo de la pantalla de Entradas/Salidas, con barra flotante y textos del catálogo en es y en, y deja capturas para que Cristian la revise;
  - pruebas: conflictos, permisos, cambios en ciclo, persistencia tras reiniciar, restauración, y que una función reasignada se lee y se acciona en su puerto nuevo con la planta simulada.
