# Paquetes de instrucciones para Claude Code — Fase 3 (auditoría NTC-IEC 62304)

Repo: `C:\Users\tecni\Documents\codigo_autoclave\` — rama `dev`.
Se entregan **uno por vez**, en el orden indicado. Cristian pega la respuesta de cada paquete en el chat para su análisis antes de enviar el siguiente.

## Encabezado común (pegar al inicio de cada paquete)

```
CONTEXTO: auditoría de cumplimiento contra NTC-IEC 62304 (Clase C). Tarea de SOLO LECTURA.

REGLAS:
1. No modifiques, crees ni borres archivos dentro del repositorio.
2. No hagas commit, checkout, stash, merge ni push. Solo comandos git de lectura (log, status, branch, tag, show, ls-files, blame).
3. No instales nada en el entorno del proyecto. Si una herramienta (radon, pip-audit, etc.) no está disponible, dilo y no la instales; yo decidiré.
4. Responde en ESPAÑOL, en la terminal (no generes archivos de informe).
5. Toda afirmación debe llevar evidencia: ruta de archivo, número de línea, hash de commit o salida de comando. Si no puedes verificar algo, escribe "NO VERIFICADO" en vez de suponer.
6. No propongas ni apliques correcciones. Solo reporta lo observado.
7. Si algo es ambiguo, detente y pregúntame.
```

---

## Paquete 3.1 — Inventario estructural (cláusulas 5.3.1, 5.4.1, 8.1.1, 8.3)

```
Entrega:
A. Árbol de directorios a 3 niveles (excluye .git, __pycache__, node_modules, venv).
B. Tabla de módulos Python: ruta | líneas | responsabilidad en una frase | si contiene lógica de seguridad (puertas, presión, temperatura, alarmas, esterilización).
C. Componentes por tecnología: Python backend, HAL/serial, firmware ESP32 (ruta y archivos), QML, launcher. Indica qué carpeta corresponde a cada uno.
D. Git: ramas, tags (¿existe alguno de versión?), cantidad de commits en dev, últimos 20 commits (hash corto, fecha, mensaje). ¿Cuántos mensajes referencian un identificador de cambio o hallazgo (p. ej. C-01, H-03, LIQ-xx, UI-xx, V-xx)?
E. ¿Existe archivo de versión del software (constante, __version__, archivo VERSION)? Dónde y qué valor.
F. Documentos presentes: lista de .md/.docx/.pdf en docs\ y en la raíz, con ruta.
```

## Paquete 3.2 — SOUP (5.3.3, 5.3.4, 7.1.3, 8.1.2)

```
Entrega:
A. Dependencias Python con versión exacta, tomadas de requirements.lock.txt (UTF-16: decodifícalo antes de leerlo). Verifica si coinciden con lo que importa el código (busca imports de terceros no listados y entradas listadas no usadas).
B. Para cada dependencia directa: nombre, versión, para qué se usa en el proyecto (módulo y línea de ejemplo).
C. Si pip-audit está disponible, ejecútalo en modo solo reporte y muestra la salida completa. Si no está disponible, dilo.
D. Versión de Python y de Qt/PySide6 requeridas o detectadas.
E. Firmware ESP32: framework/core, versión y librerías declaradas (platformio.ini, includes, comentarios). Si la versión no está fijada, dilo.
F. Assets y herramientas de build que sean software de terceros (Piper, modelos de voz, etc.): dónde se declaran y con qué versión.
G. ¿Las versiones están fijadas (pin exacto) o con rangos?
```

## Paquete 3.3 — Criterios de 5.5.4, por unidad crítica

Cristian debe confirmar los nombres de módulo antes de enviarlo; si no coinciden, Claude Code los localiza con el paquete 3.1.

```
Para cada una de estas unidades: ControlLoop (incluye _tick), máquina de estados global, fases de calentamiento, esterilización, descompresión y secado, enclavamiento de puertas, HAL/serial con ESP32 (incluye CRC y pérdida de comunicación), calibración, y gestión de alarmas.

Responde, por unidad y con ruta:línea, a cada criterio:
a) Secuencia de eventos: orden de ejecución y transiciones de estado permitidas; ¿hay transiciones ilegales posibles o no controladas?
b) Flujo de datos/control: qué hilos/procesos leen o escriben estado compartido; ¿hay protección (locks, colas)?
c) Recursos: hilos, puertos, archivos, handles abiertos; ¿se liberan siempre?
d) Manejo de fallos: busca try/except amplios, excepciones tragadas, pass, valores por defecto ante error. Describe qué hace cada unidad ante: pérdida de comunicación serial, trama con CRC inválido, sensor fuera de rango o desconectado, excepción inesperada en el lazo de control. ¿A qué estado deja las salidas?
e) Inicialización: estado inicial de salidas (válvulas, relés, bomba) al arrancar y tras reinicio; ¿variables sin inicializar o dependientes del orden de arranque?
f) Autodiagnóstico: verificaciones al arranque, watchdog (PC y ESP32), diagnóstico I2C.
g) Memoria: listas/buffers/logs que crezcan sin límite durante un ciclo largo.
h) Condiciones límite: validación de rangos de parámetros, saturaciones, divisiones por cero, valores por defecto.

Formato: una tabla por unidad con columnas Criterio | Observación | Evidencia (ruta:línea) | Estado (Cumple / Parcial / No cumple / NO VERIFICADO).
Al final, lista aparte cualquier comportamiento que te parezca inseguro, sin proponer solución.
```

## Paquete 3.4 — Calidad de código y estándar de codificación (5.1.4, 5.5.3)

```
A. ¿Existe un documento o configuración de estándar de codificación (guía de estilo, ruff/flake8/pylint/black config, pyproject, .editorconfig)? Ruta y contenido resumido.
B. Si radon está disponible: complejidad ciclomática (radon cc -s -a) y mantenibilidad (radon mi) de todo el código Python; lista las 15 funciones más complejas con rango. Si no está disponible, dilo.
C. Uso de reloj: busca time.time(), datetime.now() y time.monotonic() en código de control y temporización. Lista ruta:línea de cada uno e indica si participa en lógica de seguridad (timeouts, integración de F0, temporizadores de fase).
D. Busca: except: sin tipo, except Exception con pass, TODO/FIXME/HACK, print() en código de producción, valores numéricos de seguridad escritos en el código (límites de presión/temperatura, tiempos) en lugar de parámetros.
E. Código muerto evidente o duplicado grande (si puedes detectarlo sin instalar nada).
F. Tipado: porcentaje aproximado de funciones con anotaciones de tipo en los módulos críticos.
```

## Paquete 3.5 — Pruebas (5.5.5, 5.6, 5.7)

```
A. ¿Existe carpeta de pruebas? Ruta, framework, cantidad de archivos y de casos (pytest --collect-only solo si pytest ya está disponible; no lo instales).
B. ¿Se pueden ejecutar? Solo si pytest está disponible y las pruebas no accionan hardware ni modifican datos, ejecútalas y reporta resultado. Si hay duda de que accionen hardware, NO las ejecutes y pregúntame.
C. Clasificación de las pruebas: unitarias / integración / sistema / simulación de hardware. Qué unidades críticas (ver paquete 3.3) tienen pruebas y cuáles no.
D. ¿Hay pruebas de condiciones de fallo y de límites (CRC inválido, sensor desconectado, pérdida de comunicación, sobrepresión, puerta abierta bajo presión)? Cita archivo y nombre de la prueba.
E. ¿Las pruebas referencian algún identificador de requisito o hallazgo (en nombre, docstring o comentario)?
F. ¿Hay simulador o modo sin hardware? Dónde y cómo se activa.
G. ¿Existe algún registro de resultados de pruebas anteriores (reportes, logs)? Ruta.
```

## Paquete 3.6 — Seguridad de la información (5.2.2 e)

```
A. Estado actual de H-03: ¿los endpoints que accionan salidas/actuadores exigen autenticación? Lista cada endpoint (método, ruta, archivo:línea) indicando si requiere token o rol.
B. Interfaz/puerto en que escucha el backend (bind) y si es configurable.
C. Dónde y cómo se almacenan credenciales, tokens y hashes de contraseñas de usuarios (formato, algoritmo, ruta de archivo o tabla).
D. Registro de auditoría: ¿se registran inicios de sesión, cambios de parámetros, calibraciones y acciones manuales sobre actuadores? Con usuario y marca de tiempo. Dónde.
E. Roles de usuario existentes y qué puede hacer cada uno (cita el código que lo impone).
```

## Paquete 3.7 — Trazabilidad muestral (7.3.3)

Se envía después de los anteriores, con las funciones a trazar acordadas en el chat. Propuesta inicial:
1. Enclavamiento de puerta bajo presión.
2. Sobrepresión de cámara / aislamiento.
3. Fallo o desconexión de sensor de temperatura o presión.
4. Pérdida de comunicación con la ESP32.
5. Alarma de fallo de esterilización.

```
Para cada función de la lista, recorre en el repositorio y reporta con ruta:línea:
1. Documento donde se especifica el requisito (cita ruta y sección; si no existe, "NO ENCONTRADO").
2. Elemento de arquitectura/diseño que lo implementa.
3. Unidad de código (archivo y función/clase).
4. Prueba que lo verifica (archivo y nombre; si no existe, "NO ENCONTRADO").
5. Cualquier referencia a un riesgo o peligro en documentación o comentarios.
6. Eslabón roto de la cadena, si lo hay.
No infieras eslabones que no puedas señalar en un archivo.
```
