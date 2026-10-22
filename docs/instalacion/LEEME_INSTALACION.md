# LEEME — Instalación en el equipo de pruebas (jueves 22-oct-2026)

Lista de comprobación para Cristian. Hoy solo se hace:
1. la instalación con el asistente;
2. la verificación de Entradas/Salidas;
3. la calibración de sensores.

Los ciclos NO se corren hasta el lunes 26-oct.

Lo marcado **[verificar en sitio]** no se pudo comprobar sin el equipo: se revisó en el código y con el simulador, sin tarjeta ni PC industrial.

Versión de este documento: P1 de la tanda 7, completada por la sesión principal en K2 (22-oct, 08:10) con la sección "A frente a B". **Se instala la B.**

---

## 0. Antes de salir (en el PC de la oficina)

- [ ] **Generar el código de activación del día** (sección 2). Solo vale el día en que se genera.
- [ ] Copiar a la USB la carpeta de la entrega que se va a instalar (ver "A frente a B"): `Autoclave/` completa, o el `.zip`, más `SHA256SUMS.txt`.
- [ ] **NO copiar `GeneradorCodigos.exe` al PC del equipo.** Contiene los secretos de activación y corre solo en el PC de Especifika.
- [ ] Llevar el número de serie exacto del equipo, tal como va a quedar en el perfil.

## 1. Qué copiar y dónde

Contenido de la entrega (`entrega/2026-10-22_a/`; la B tiene la misma forma):

| Archivo | Para qué |
|---|---|
| `Autoclave/` | El programa: `Autoclave.exe` y `_internal/`. Hay que copiar la carpeta **completa**; el `.exe` solo no arranca. |
| `Autoclave_2026-10-22_a.zip` | La misma carpeta comprimida. |
| `SHA256SUMS.txt` | Huellas para comprobar que la copia llegó bien. |
| `MANIFIESTO_CARPETA_Autoclave.sha256` | Huella de cada archivo de la carpeta. |
| `GeneradorCodigos.exe` | Generador de códigos. Solo para el PC de Especifika. |
| `entorno_build.txt` | Versiones exactas con las que se compiló (trazabilidad). |

### 1.1 Comprobar la copia
En el PC del equipo, abrir una consola (`cmd`) en la carpeta de la USB:

```
certutil -hashfile Autoclave_2026-10-22_a.zip SHA256
certutil -hashfile Autoclave\Autoclave.exe SHA256
```

El resultado debe ser igual a la línea del mismo archivo en `SHA256SUMS.txt`. `certutil` imprime la huella con espacios o en mayúsculas según la versión de Windows: compare solo los caracteres. Si no coincide, vuelva a copiar.

Si llevó el zip, descomprímalo antes. **No ejecute el programa desde dentro del zip.**

### 1.2 Instalar (lo recomendado)
1. Ajustar primero en Windows la **fecha, la hora y la zona horaria (Bogotá, UTC-5)** del PC del equipo. Ver el aviso de la sección 3.
2. Doble clic en `Autoclave\Autoclave.exe`, desde la USB o desde la carpeta copiada.
3. Pregunta **"¿Instalar Autoclave en este PC?"**. Responder **Sí** y aceptar el aviso de permisos de administrador (UAC).
4. El programa queda en `C:\Program Files\Especifika\Autoclave` y crea accesos directos "Autoclave" en el Escritorio público y en el menú Inicio. Se abre solo, ya desde la copia instalada. En la USB no se escribe nada.
5. Los datos quedan en `C:\ProgramData\Especifika\Autoclave` (carpeta oculta: escriba la ruta en la barra de direcciones del Explorador):

| Ruta dentro de `C:\ProgramData\Especifika\Autoclave` | Contenido |
|---|---|
| `installation_profile.json` | Perfil de instalación (bloqueado) |
| `data\autoclave.db` | Base de datos: usuarios, historial, bitácora, presión atmosférica calibrada |
| `data\calibration.yaml` | Calibración de sensores (ganancia y offset por canal) |
| `programa\autoclave\config\` | Parámetros del equipo y lista de canales de E/S (`instances\ACV-2026-001.yaml`) |
| `programa\autoclave\cycles\` | Programas de ciclo de usuario y de fábrica |
| `data\*.log` | Registros: `lanzador.log`, `backend.log`, `ui_puerta1.log`, `ui_puerta2.log` |

### 1.3 Alternativa portátil (sin instalar)
Para correr en sitio sin copiar a Archivos de programa, cree un acceso directo a `Autoclave.exe` con el argumento `--portable`. En modo portátil, los datos quedan **junto al `.exe`** (`installation_profile.json` y `data\`). La carpeta tiene que ser escribible: no sirve desde una USB protegida contra escritura (sin poder escribir `data\calibration.yaml`, el backend no arranca).

### 1.4 Reinstalar o actualizar el programa: ¿qué pasa con los datos?
- Abrir otra versión de `Autoclave.exe` desde fuera de Archivos de programa pregunta **"Ya hay un Autoclave instalado en este PC. ¿Actualizarlo con esta versión?"**. Al responder Sí, se reemplaza solo `C:\Program Files\Especifika\Autoclave`.
- **Los datos se conservan**: perfil, base de datos (usuarios, historial), calibración, presión atmosférica, parámetros y ciclos de usuario. Esto está comprobado con una prueba que simula el ejecutable instalado.
- Los ciclos de **fábrica** sí se refrescan desde el programa nuevo.
- Los archivos de configuración que ya existen en `programa\` (parámetros globales, lista de canales de E/S) **no** se reemplazan. Si una versión nueva trae cambios en ellos, no llegan a un equipo ya instalado.
- Antes de actualizar, **cierre Autoclave** (todas las ventanas). Si está abierto, la copia falla con un aviso y deja la versión anterior.

### 1.5 Una pantalla o dos
El acceso directo abre **las dos pantallas**: puerta 1 en el monitor 0 y puerta 2 en el monitor 1. Si el PC del equipo tiene **un solo monitor**, la ventana de la puerta 2 se abre a pantalla completa encima de la de la puerta 1.

Rodeo: cree un acceso directo con el argumento `--una-pantalla`:

```
"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla
```

**[verificar en sitio]** cuántos monitores tiene el PC y cuál es el 0.

## 2. Código de activación del día (`GeneradorCodigos.exe`, en el PC de Especifika)

1. Doble clic en `GeneradorCodigos.exe` (no abre consola). Arranca un servidor local y abre el navegador en `http://localhost:8080`. Si ya estaba abierto, solo abre el navegador.
2. **Primera vez en ese PC:** se crea el usuario `admin` con una contraseña temporal. Está en `C:\ProgramData\Especifika\Generador\CLAVE_INICIAL_ADMIN.txt`. El generador la pide cambiar en el primer ingreso y entonces borra el archivo.
3. Ingrese y escriba el **número de serie del equipo** en "Número de serie del equipo". Pulse **Generar**.
4. Resultado:
   - **Serie nueva:** muestra el "Código de instalación" (12 caracteres) y la "Clave de fábrica". Para el asistente se usa el **Código de instalación**.
   - **Serie a la que ya se le generó un código** (por ejemplo, en una prueba anterior): muestra solo la "Clave de fábrica" y el botón **"Solicitar reinstalación"**. Púlselo para obtener el "Código de reinstalación". El asistente lo acepta igual: es el mismo código.
5. Los códigos son **válidos solo el día de hoy**: lo dice la página ("Válidos solo el día de hoy: AAAA-MM-DD"). El equipo los valida contra **su propia fecha local**. Si el PC del equipo tiene otra fecha, el código se rechaza ("Código de activación incorrecto o expirado").
6. Las mayúsculas y los espacios de los extremos no importan, ni en la serie ni en el código. Un espacio o un guion **dentro** de la serie sí importa: debe escribirse igual en el generador y en el asistente.

Datos del generador: `C:\ProgramData\Especifika\Generador\` (base, `config.json` con el puerto, respaldos y log).

## 3. Primer arranque y asistente de instalación

> **Fecha y hora primero.** El perfil guarda la fecha de instalación. Si se instala con el reloj del PC **adelantado** y luego se corrige, el programa no vuelve a arrancar: muestra el fallo de reloj ARR_RELOJ hasta que llegue esa fecha. Para salir de eso hay que reinstalar el perfil (sección 7). Ajuste fecha, hora y zona antes de abrir el asistente.

Sin perfil, el programa abre **solo el asistente**, en la pantalla de la puerta 1 y sin backend: es normal que todavía no haya lecturas. La compilación A tiene **7 pasos**.

| Paso | Qué pide | Qué poner en este equipo |
|---|---|---|
| 1. Activación | Número de serie + código de 12 caracteres | La serie exacta y el código del día (sección 2) |
| 2. Tipo de equipo | Clase | **Piso** o **Piso Laboratorio**, según el equipo. **[verificar en sitio]** En la A también aparecen las clases de Mesa: no elegirlas. |
| 3. Puertas | Número de puertas, tipo de puerta y puerta que gestiona este PC | Según el equipo. Con 2 puertas, este PC gestiona la **Puerta 1**. El tipo (Simple / Motorizada / Con bloqueo / Motorizada con bloqueo / Avanzada) define si el software controla el cerrojo y vigila el empaque; el resumen lo advierte. **[verificar en sitio]** |
| 4. Enfriamiento | Nivel | **0** (sin enfriamiento), salvo que el equipo lo tenga |
| 5. Fuente de vapor | Generador / Caldera / Mixto | **Generador interno**. Con esta opción, las salidas DO1 y DO2 quedan bloqueadas en E/S: el generador tiene su propio control. |
| 6. Datos del equipo | Modelo (texto libre, solo en la A), entradas de suministro y sondas | **Suministros:** activar **solo "Aire comprimido"** y desactivar los demás (agua de la bomba, agua del generador, presostato de vapor, suministro eléctrico). Una entrada desactivada no se vigila: no da alarma ni bloqueo. **Sondas:** Cámara 1 (fija, no se puede quitar), **Cámara 2**, **Referencia** y **Drenaje**, las cuatro activas. **Modelo (A):** escribir el nombre con la nomenclatura oficial, p. ej. `SPK-SAT 80H2` (máximo 18 caracteres para el ticket). |
| 7. Resumen | Revisión | Revise todo. Al instalar, el perfil queda **bloqueado**: solo se cambia reinstalando el perfil (sección 7). |

Al confirmar, aparece **"Instalación completada"**. Pulse **Continuar**. El texto dice "Reinicie el software", pero **no hace falta**: el programa sigue solo con el arranque normal (backend y pantallas). Esto está comprobado con prueba.

**Compilación B (solo si entró la etapa M1 de esta noche).** El asistente cambia así:
- en el paso 2 aparecen solo **Piso** y **Piso laboratorio**;
- después de Puertas hay un paso nuevo, **Cámara**: capacidad nominal en litros (entero de 20 a 2000) y tipo de carga **Vertical (V)** u **Horizontal (H)**;
- el nombre del modelo **se calcula solo**, como `SPK-SAT <litros><V|H>[2][-LAB]`: el `2` va si tiene 2 puertas y `-LAB` si es Piso laboratorio. Ejemplos: `SPK-SAT 45V`, `SPK-SAT 45V2-LAB`;
- el campo libre "Modelo" desaparece del paso de datos;
- el resto es igual.

## 4. Arranque con perfil

- Se ve la intro "del vapor a la precisión" y luego la pantalla principal.
- **Con la tarjeta desconectada**, el equipo debe mostrar **"tarjeta desconectada"** (alarma COM-01 "Tarjeta de E/S desconectada"). **No** debe decir "paro de emergencia" ni mostrar valores inventados: temperatura y presión salen como "—"/"---". Se puede ingresar y navegar igual.
- El backend espera la tarjeta 15 s y da el arranque por terminado igual (ARR_SIN_ES); reintenta solo cuando se conecta.
- Si la intro muestra un fallo de arranque porque el backend tardó más de 20 s la primera vez (antivirus, PC lento), **ya no queda trabada**: sigue en cuanto el backend responde (cambio P1). Si el fallo no se retira en un minuto, cierre y vuelva a abrir, y revise `data\backend.log`.
- Los fallos bloqueantes de verdad (reloj alterado, calibración ilegible, perfil inválido) dejan la intro detenida con la alarma. Ver la sección 7 y los logs.

## 5. Primer usuario

La base nueva trae dos usuarios semilla. Los dos exigen cambiar la contraseña en el primer ingreso (8 a 64 caracteres, distinta de la actual):

| Usuario | Contraseña inicial | Rol |
|---|---|---|
| `ingeniero` | `ingeniero1234` | ingeniero |
| `admin` | `admin1234` | administrador |

1. Toque el avatar e ingrese como **`ingeniero` / `ingeniero1234`**. **No use `admin`:** el administrador no ve Entradas/Salidas, calibración ni Mantenimiento.
2. El sistema lleva a **cambiar la contraseña**. Anote la nueva en un lugar seguro.
3. En OPCIONES › Usuarios › Nuevo usuario, cree su usuario **técnico** (o ingeniero). Comprobado con prueba: ingeniero semilla → cambio de clave → crea técnico → el técnico entra al modo prueba.
4. Cinco intentos fallidos bloquean ese usuario 5 minutos.
5. Cambie también la contraseña de `admin` antes de entregar el equipo.

## 6. Orden de verificación

### 6.1 Entradas/Salidas (OPCIONES › Entradas / Salidas)
Requisitos:
- usuario técnico o ingeniero;
- equipo en PREPARACIÓN, PREPARADO o FALLA;
- **tarjeta conectada**;
- **paro de emergencia liberado.** Con el paro activo, OPCIONES no abre y el modo prueba se rechaza.

Orden sugerido:
1. **Entradas:** cada una muestra Activa / Inactiva, o "Sin datos" si no hay enlace. Accione cada sensor físico (puerta cerrada/abierta, atrapamiento, aire comprimido, paro…) y vea el cambio.
2. **Temperatura** y **Presión:** valores vivos y cuentas ADC. Sin tarjeta muestran "---" y "Sin enlace con la tarjeta de E/S".
3. **Salidas:** pulse **Habilitar modo prueba** y acepte el aviso. Al entrar, todas las salidas se apagan.
   - **Salidas sostenidas** (válvulas): un toque las activa y otro las apaga. Verifique cada una en campo.
   - **Salidas momentáneas** (abrir/cerrar puerta 1 y 2, bomba de vacío): se activan **mientras se mantiene pulsado** "Mantener pulsado" y se apagan al soltar. Si la orden se pierde, el backend las apaga solo a los 1,5 s. **Corregido en P1:** antes la pulsación se cortaba a los 1-2 s.
   - `aire_atmosferico_camara` antes respondía error y no se movía. **Corregido en P1.**
   - Con generador interno, `vapor_generador` sale como **bloqueada**: es lo esperado.
4. **Salida del modo prueba.** Pruebe todos los caminos; en cada uno las salidas deben quedar apagadas:
   - botón **Salir del modo prueba**;
   - cambiar a otro segmento (Entradas / Temperatura / Presión);
   - salir de la pantalla (Atrás o Inicio);
   - cerrar sesión;
   - 5 minutos sin tocar la sección;
   - sesión vencida o cerrada en otra parte. **Corregido en P1:** el vigilante de este caso moría a los pocos segundos.
   - El backend también sale solo tras 90 s sin órdenes ni avisos (por ejemplo, si la pantalla se cierra de golpe).
5. **Desconexión de la tarjeta durante el modo prueba:** las salidas no se pueden accionar ("rechazó la orden") y "Salir" sigue funcionando. Salga y vuelva a entrar al reconectar.

**PROBLEMA CONOCIDO — canales que no aparecen en E/S.** La lista sale de `io_enabled` del archivo del equipo (`ACV-2026-001.yaml`). Hoy **no** incluye:
- en salidas: `descompresion_lenta`, `vapor_caldera`, `aire_comprimido_chaqueta`, `aire_comprimido_camara`, `agua_chaqueta` ni `buzer_alarma`;
- en temperatura: la sonda **`temp_2_camara` (Cámara 2)**;
- en entradas: `suministro_electrico`.

Así, desde la pantalla no se pueden probar ni calibrar. Rodeo, con Autoclave **cerrado**:
1. Edite `C:\ProgramData\Especifika\Autoclave\programa\autoclave\config\instances\ACV-2026-001.yaml` (en portátil: `<carpeta del exe>\programa\autoclave\config\instances\`).
2. Agregue los nombres que el equipo tenga cableados bajo `io_enabled:` → `DO:` / `AI:` / `DI:`, con la misma sangría que los demás. Por ejemplo, `    - descompresion_lenta` bajo `DO:` y `    - temp_2_camara` bajo `AI:`.
3. Vuelva a abrir Autoclave.

En el modo prueba, el backend ya acepta cualquier salida del mapa: solo cambia lo que muestra la pantalla. **[verificar en sitio]** qué salidas y sondas tiene cableadas el equipo.

### 6.2 Calibración de sensores (Temperatura / Presión › Calibrar)
- **Orden: primero presión, después temperatura.** La presión atmosférica (6.3) se calcula con la presión de cámara calibrada: si recalibra la presión después, repita la 6.3.
- Requisitos: técnico (fuera de ciclo) o ingeniero, y **tarjeta conectada**. Sin lectura válida, el botón "Calibrar" está deshabilitado.
- **Dos puntos.** En cada punto, "lo que muestra el equipo" contra "lo que marca el patrón". La lectura del equipo se puede **capturar** del valor vivo o **escribir a mano**; la bitácora guarda cuál de las dos fue. Luego **Aplicar**.
- **Límites que conviene conocer:**

| | Temperatura | Presión |
|---|---|---|
| Separación mínima entre puntos (en lo mostrado Y en el patrón) | 20 °C | **50 kPa** |
| Rango de los 4 valores | 0–200 °C | −10 a 450 kPa (absolutos) |
| Corrección máxima (cámara, cámara 2 y referencia / cámara) | 10 °C | 50 kPa |

  Una corrección grande pide confirmación y queda auditada. Una imposible se rechaza con el motivo. Ejemplo práctico: la atmósfera en Bogotá (~75 kPa abs) y 120 kPa están a solo 45 kPa y **se rechazan**. El punto alto debe estar a ≥ 125 kPa abs. **[verificar en sitio]** cómo se obtiene ese punto hoy (calibrador de presión o chaqueta presurizada).
- **La sonda de Referencia** antes no se podía calibrar desde la pantalla (error). **Corregido en P1.**
- **La calibración que trae el programa** (`data\calibration.yaml` de un equipo nuevo) **no es neutra**: lleva los valores del banco de Especifika (julio/agosto), por ejemplo presión de cámara con ganancia 1,364 y offset −75,35. **[verificar en sitio]** si son de este mismo equipo. Si las lecturas no cuadran o la corrección se rechaza por desviación acumulada, use primero **"Restaurar por defecto"** en ese sensor (ganancia 1, offset 0) y calibre desde ahí.
- **Guardar y comprobar que se conserva:**
  1. aplique la calibración;
  2. cierre Autoclave;
  3. ábralo de nuevo;
  4. en E/S › Calibrar del mismo sensor, la ganancia y el offset deben ser los nuevos (con fecha y usuario de la última calibración).

  Se guarda en `C:\ProgramData\Especifika\Autoclave\data\calibration.yaml`, con un `.bak` del anterior. Comprobado con prueba (reinicio y actualización).
- **Rodeo si la pantalla táctil no deja calibrar:** el menú de ajustes PySide (`"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --rol ajustes`, con el programa principal abierto) tiene calibración con valores escritos, para todos los sensores del mapa. El engrane de la pantalla ya no lo abre. **[verificar en sitio]**. Ese menú corta la espera a 0,8 s: si dice "No se pudo guardar", **revise la ganancia y el offset vigentes antes de reintentar**, porque pudo haberse guardado.

### 6.3 Presión atmosférica (OPCIONES › Mantenimiento › Calibrar presión atmosférica)
- Requisitos:
  - tarjeta conectada con datos vigentes;
  - **una puerta ABIERTA**;
  - cámara por debajo de 80 °C;
  - fuera de ciclo;
  - base de datos disponible.
- Mide 120 s. El promedio debe quedar entre 60 y 105 kPa, con dispersión ≤ 1,5 kPa.
- Si el resultado difiere en más de 5 kPa del valor vigente (75 kPa de fábrica), pide **Confirmar** dentro de 5 minutos; si no, se descarta.
- Se guarda en la base de datos (`data\autoclave.db`) y se conserva al reiniciar y al actualizar. **Un respaldo restaurado no lo trae**: si restaura un respaldo, recalibre.

### 6.4 Información del sistema (OPCIONES › Información del sistema)
- Muestra:
  - modelo, número de serie y fecha de instalación;
  - fuente de vapor;
  - versión del software (la A dice **0.5.0**);
  - firmware e id de la tarjeta;
  - ciclos, mantenimiento, idioma, unidades, impresora y red.
- Sin tarjeta, firmware e id salen "—" y los ciclos en 0: es normal.
- El pie del asistente dice "V: 1.0" (texto fijo); no coincide con la versión real.

### 6.5 Apagar el equipo (botón Apagar equipo, solo en la pantalla de la puerta 1)
- En el programa instalado **apaga Windows de verdad** (`shutdown /s /t 0`). Antes apaga las salidas, detiene el control y cierra la base de datos.
- Se rechaza con un ciclo en curso.
- Si Windows rechaza el apagado (política del PC), el control ya quedó detenido y el PC sigue encendido. Desde P1, el motivo queda en `data\backend.log` ("Windows rechazó el apagado"). En ese caso, cierre Autoclave y apague Windows a mano.
- **[verificar en sitio]** que el usuario de Windows del equipo pueda apagar.

## 7. Si el perfil queda mal: reinstalar el perfil

El perfil está bloqueado y el programa no lo sobrescribe si es válido. Para rehacerlo:
1. **Cierre Autoclave por completo**: todas las ventanas. En el Administrador de tareas no debe quedar ningún `Autoclave.exe`.
2. Abra `C:\ProgramData\Especifika\Autoclave\` (portátil: la carpeta del `.exe`).
3. **Renombre** `installation_profile.json`, p. ej. a `installation_profile.json.mal-2026-10-22`. **No lo borre**: queda como evidencia.
4. Genere un código del día para la serie. Si la serie ya tenía código, use **"Solicitar reinstalación"** (sección 2).
5. Abra Autoclave: sin perfil vuelve a abrir el asistente. Complete los pasos.
6. **Se conservan:** usuarios, historial, calibración, presión atmosférica, parámetros y ciclos. Solo cambia el perfil.

Lo mismo sirve si el arranque queda en **ARR_RELOJ** porque se instaló con el reloj adelantado: corrija primero la hora de Windows y luego reinstale el perfil.

Si el perfil está **dañado** (ilegible o inválido), el asistente se abre solo y aparta el archivo viejo como `installation_profile.json.invalido-<fecha>`.

## 8. Volver a la compilación A si la B falla

1. Cierre Autoclave por completo.
2. Desde la USB o carpeta de la **A**, abra `Autoclave\Autoclave.exe`. Pregunta "Ya hay un Autoclave instalado… ¿Actualizarlo con esta versión?": responda **Sí**.
3. Queda instalada la A **con los mismos datos**: perfil, usuarios, calibración.
   - Un perfil hecho con la B (con capacidad y tipo de carga) se lee en la A sin problema, porque la A ignora los campos que no conoce.
   - Si la B migró la base de datos a una versión más nueva, la A la abre sin bajarla de versión. **[verificar en sitio]** que la A arranque bien después de la B.
4. Si la A no arranca con esos datos, reinstale el perfil (sección 7) antes de tocar la base.

## A frente a B

**Instale la B** (`entrega/2026-10-22_b/`). La A queda solo como respaldo (sección 8).

| | Compilación A (`entrega/2026-10-22_a/`) | Compilación B (`entrega/2026-10-22_b/`) |
|---|---|---|
| Etiqueta / commit | `inst-2026-10-22-a` (18eb429) | `inst-2026-10-22-b` (23e76e2) |
| Suite en ese código | 5020 passed, 2 skipped, 3 xfailed | 5405 passed, 3 skipped, 3 xfailed |
| Asistente | 7 pasos, con clases de Mesa y campo libre "Modelo" | 8 pasos: solo Piso y Piso laboratorio, paso **Cámara** (litros y V/H) y nombre del modelo calculado (`SPK-SAT …`) (M1) |
| Correcciones de la instalación de hoy (P1) | No | Sí (lista abajo) |
| Correo a una dirección escrita a mano (C2) | Falla: dice "enviado" y no llega | Corregido: el resultado sale de lo que aceptó el servidor, por destinatario |
| Mantenimiento E1 (M2) | No | Sí: solo el preventivo reinicia el contador; la calibración deja de contar como mantenimiento |
| Decisiones 1.3 sobre el ciclo (Q1) | No | Sí, con revisión de seguridad. **No afecta lo de hoy** (no se corren ciclos hasta el lunes) |
| Lock de dependencias en UTF-8 (L1) | No | Sí (solo documentación del build) |
| Prueba de humo en el PC de la oficina | Arranca y abre el asistente (7 pasos) | Arranca y abre el asistente (8 pasos), sin traceback |
| Recomendada | Solo si la B falla al arrancar | **Sí** |

**Por qué la B:** trae las correcciones que estorbaban justo lo de hoy (E/S en modo prueba, calibración de la Referencia, la intro trabada) y el asistente con el modelo calculado que Cristian aprobó. Toda la B pasó la suite completa después de cada unión.

**Verificar en sitio con la B:** el recorrido completo del asistente en la pantalla real (en el PC de la oficina la pantalla es de 1536×864 y el teclado en pantalla queda fuera de la vista, así que la prueba de humo llegó solo al paso 1; el recorrido por los 8 pasos está cubierto por las pruebas QML de M1 y sus capturas en `docs/informes/tanda7/capturas/`).

Correcciones de P1 que **no** están en la A (afectan el trabajo de hoy):
- salidas momentáneas (puertas, bomba de vacío) que se cortaban a los 1-2 s en modo prueba;
- `aire_atmosferico_camara` que no se podía accionar;
- la sonda de Referencia que no se podía calibrar desde la pantalla táctil;
- el vigilante que saca del modo prueba cuando vence la sesión dueña, que moría a los pocos segundos;
- la intro que quedaba trabada si el backend tardaba más de 20 s;
- la tarjeta de sensor sin enlace, que culpaba al cableado.

**Rodeos en la A:**
- momentáneas: pulsar repetidamente en lugar de mantener;
- referencia: menú de ajustes (`--rol ajustes`);
- `aire_atmosferico_camara`: menú de ajustes;
- intro trabada: cerrar y volver a abrir.

## 9. Registros, por si algo falla
`C:\ProgramData\Especifika\Autoclave\data\`:
- `lanzador.log`
- `backend.log`
- `ui_puerta1.log`
- `ui_puerta2.log`
- `ajustes.log`

Si algo falla, lleve copia de esa carpeta (sin `autoclave.db` si no hace falta).
