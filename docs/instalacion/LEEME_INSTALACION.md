# LEEME — Instalación en el equipo de pruebas (jueves 22-oct-2026)

Lista de comprobación para Cristian. Hoy solo se hace:
1. la instalación con el asistente;
2. la verificación de Entradas/Salidas;
3. la calibración de sensores.

Los ciclos NO se corren hasta el lunes 26-oct.

Lo marcado **[verificar en sitio]** no se pudo comprobar sin el equipo: se revisó en el código y con el simulador, sin tarjeta ni PC industrial.

Versión de este documento: P1 de la tanda 7, completada en K2 (22-oct, 08:10) con la sección "A frente a B", en K8 de la tanda 8 (22/23-oct) con las secciones "Actualizar un equipo ya instalado (B → C)" (8b) y "B frente a C", y en K9 de la tanda 9 (23-oct) con "B frente a D" y la sección 8c (B → D con el Setup).

> **Tanda 9 (23-oct): la C NO se instala. El equipo de pruebas pasa de la B a la compilación D (`entrega/2026-10-23_d/`) con el Setup `Autoclave_Setup_1.0.0-d.exe`: siga la sección 8c («Actualizar B → D»), sin copiar archivos a mano.** En un PC nuevo, la D se instala con el mismo Setup (secciones 1 a 6, usando el Setup en lugar de abrir `Autoclave.exe`).

## B frente a D

**Instale la D** (`entrega/2026-10-23_d/`, etiqueta `inst-2026-10-23-d`, `dev` 4357217) antes de los ciclos del lunes 26-oct. La D incluye todo lo de la C (tabla «B frente a C», más abajo) y además:

| | Compilación B (`2026-10-22_b`) | Compilación D (`2026-10-23_d`) |
|---|---|---|
| Suite en ese código | 5405 passed, 3 skipped, 3 xfailed | **6606 passed, 10 skipped, 3 xfailed** |
| Arranque con la cámara no segura (D9-1) | Pide «Confirmar y llevar a estado seguro» con el texto «paro liberado» aunque no hubo paro; sin presión de cámara bloquea modo prueba, cambio de programa y apagado, y saca del inicio de sesión | El estado seguro corre solo, sin confirmación (solo la lenta con presión; aire atmosférico con vacío). La confirmación se pide solo tras un paro real. Sin presión de cámara: CIC-10 + SEN-06 y NO ABRIR, sin bloquear inicio de sesión, modo prueba, cambio de programa ni apagado |
| Puerta abierta con presión fuera de la atmosférica (D9-1.6) | — | Alarma nueva SEN-10, bloquea el inicio de ciclo |
| Modo prueba con el estado seguro activo o la cámara no segura | — | **No deja abrir ni desbloquear puertas** desde Entradas/Salidas (ni rápida, chaqueta, vapor de cámara, aire comprimido de cámara ni vapor de generador o caldera con el estado seguro). En el equipo sin sensores la cámara nunca es segura: las puertas no se accionan desde Entradas/Salidas |
| Paro de emergencia y zumbador (D9-9) | Se encienden un instante salidas activas al pulsar el paro | ALL_OFF inmediato con ACK; con el paro, el PC no ordena encender nada salvo el zumbador (caso de banco B-13) |
| Niveles de alarma (D9-2) | SEN-01/03/06/07 y CIC-10 como aviso | Como alarma (requieren reconocimiento) |
| Bitácora (D9-6) | Rechazos, suspensión, órdenes de puerta, selección de programa, pruebas de correo e impresora | Solo seguridad, configuración y sesión |
| Puertas simples (D9-3) | Muestra apertura automática y grupos Puerta y Empaque | Los oculta; grupo nuevo «Cámara segura» |
| Entradas NC (D9-5) | Nivel crudo | Estado interpretado (paro y atrapamiento) y nivel crudo al lado |
| Manejo de ciclos (D9-10) | En Parámetros del ciclo | En Opciones avanzadas (técnico e ingeniero) |
| Ticket y motivos de fallo en inglés (D9-13.4) | En español | En el idioma vigente |
| Actualización | (C: copia a mano de 2 archivos) | **Sin copias a mano** (D9-13.1): el programa refresca sus archivos de fábrica con respaldo |
| Entrega | Correo y programas de usuario del banco | Correo neutro y solo programas de fábrica (D9-7) |

> **Tanda 8 (23-oct): el equipo de pruebas ya tiene la B. Para pasarlo a la compilación C (`entrega/2026-10-23_c/`), siga la sección 8b, no la 1.2.** En un PC nuevo, la C se instala igual que la B (secciones 1 a 6).

## B frente a C

**Instale la C** (`entrega/2026-10-23_c/`, etiqueta `inst-2026-10-23-c`, `dev` 5a4b0df) antes de los ciclos del lunes 26-oct. La B queda de respaldo (vuelta atrás en la sección 8b).

| | Compilación B (`2026-10-22_b`) | Compilación C (`2026-10-23_c`) |
|---|---|---|
| Suite en ese código | 5405 passed, 3 skipped, 3 xfailed | **6201 passed, 7 skipped, 3 xfailed** |
| Transductor de presión sin señal (SEN-01, D8-1) | Lee 0,0 kPa como lectura válida | Detecta el lazo abierto o en corto: «—», FALLO propio en ciclo con venteo solo por la lenta, inicio bloqueado y «NO ABRIR» |
| Transiciones del ciclo (D8-2.6 a 2.16) | Preguntas abiertas de la tanda 7 | Pausa de la exposición sin datos, tope de pausas (CIC-11), 3 tramas DI distintas, líquidos sellados al perder el Principal, ALL_OFF con reintentos, reimpresión idéntica, «CARGA NO ESTÉRIL» en la pantalla de resultado |
| Canales de E/S | Del YAML (había que agregar a mano Cámara 2, `descompresion_lenta`…) | Del perfil de instalación (D8-3.17) |
| Aire atmosférico en modo prueba | Se abre con la cámara presurizada | Rechazado con presión en la cámara o sin lectura (D8-3.19) |
| Calibración que viaja con el programa | Valores del banco | **Neutra** (D8-3.18), verificada en el build |
| Interfaz | — | Hospitalario/Laboratorio, Atrás con historial en Opciones, Cerrar sesión lleva a Login, tipo de carga Sólido/Líquido, modos en lista, sin abreviaturas ni mezcla de idiomas, Reportes por tipo de fallo |
| Opciones avanzadas | Técnico e ingeniero | Solo ingeniero: reasignación de E/S |
| Mantenimiento | «Último mantenimiento» | «Último preventivo»; sin tipo «Otro»; historial para el administrador |
| Dependencias | Entorno completo del PC (2942 archivos) | Entorno limpio solo del producto (2297 archivos; D8-3.26) |
| Prueba de humo en el PC de la oficina | Asistente, paso 1 de 8 | Asistente, paso 1 de 8, sin errores en los registros |

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

El programa **no detecta** cuántos monitores hay (decisión D8-3.20 de la tanda 8): en un PC con un solo monitor hay que usar el argumento `--una-pantalla`, que abre solo la pantalla de la puerta 1 (con el backend, como siempre).

Acceso directo de ejemplo (un solo monitor):

1. Clic derecho en el escritorio > **Nuevo** > **Acceso directo**.
2. En "Escriba la ubicación del elemento" pegue, **con las comillas**:
   ```
   "C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla
   ```
3. **Siguiente**; nombre: `Autoclave (una pantalla)`; **Finalizar**.
4. Use ese acceso directo en lugar del normal (puede borrar el otro para no confundirse). Para arrancar solo al encender el PC, copie el acceso directo a la carpeta que abre `Win + R` > `shell:startup`.

Variantes del mismo destino:

| Caso | Destino del acceso directo |
|---|---|
| Un monitor, programa instalado | `"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla` |
| Un monitor, modo portátil (1.3) | `"<carpeta>\Autoclave.exe" --portable --una-pantalla` |
| Un monitor que Windows no numera 0 | `"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla --monitor-puerta1 1` |

Notas:
- Con `--una-pantalla` no se abre la pantalla de la puerta 2. En un equipo de dos puertas, la puerta 2 queda sin pantalla en este PC.
- Si hay dos monitores y las ventanas salen cambiadas, use `--monitor-puerta1 1 --monitor-puerta2 0` en el acceso directo normal (sin `--una-pantalla`).
- El asistente de instalación (sección 3) siempre se abre solo en la pantalla de la puerta 1; el argumento no cambia nada ahí.

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

## 8b. Actualizar un equipo ya instalado (B → C)

> **La C no se instala (tanda 9). Para la D use la sección 8c, sin copias a mano.** Esta sección queda como referencia.

Para pasar el equipo de pruebas, instalado el 22-oct con la **B**, a la **C** (`entrega/2026-10-23_c/`) sin perder nada. Se comprobó en el PC de la oficina con una copia simulada del equipo instalado: perfil del equipo de pruebas, base de datos de la B con un usuario y un parámetro cambiado, y calibración propia. El detalle está en `docs/informes/tanda8/K8_compilacion_c.md`.

**Qué hace el programa al actualizar** (leído en `instalador_exe.py`, `utils/resources.py` y `utils/paths.py`):
- reemplaza solo `C:\Program Files\Especifika\Autoclave` (`Autoclave.exe` y `_internal\`);
- en `C:\ProgramData\Especifika\Autoclave` no borra ni reemplaza nada, salvo los programas de **fábrica** (`programa\autoclave\cycles\factory\`), que siempre se refrescan;
- los archivos de configuración que ya existen en `programa\autoclave\config\` **no se reemplazan**. Por eso hay dos que se copian a mano (paso 6).

**Orden, con el software cerrado:**
1. **Cierre Autoclave por completo** (las dos pantallas). En el Administrador de tareas no debe quedar ningún `Autoclave.exe`.
2. **Respaldo:** copie la carpeta completa `C:\ProgramData\Especifika\Autoclave` a la USB (por ejemplo, `respaldo_B_2026-10-23`). Es la vuelta atrás.
3. Compruebe la copia de la C con `SHA256SUMS.txt` (sección 1.1).
4. Abra `Autoclave\Autoclave.exe` de la C desde la USB. Pregunta "Ya hay un Autoclave instalado en este PC. ¿Actualizarlo con esta versión?": responda **Sí** y acepte el aviso de administrador.
5. Al terminar, el programa se abre solo. **Ciérrelo otra vez por completo** (paso 1).
6. **Reemplace estos dos archivos** de `C:\ProgramData\Especifika\Autoclave\programa\autoclave\config\` por los de la C, que están en `C:\Program Files\Especifika\Autoclave\_internal\autoclave\config\`:

| Archivo | Por qué hay que reemplazarlo |
|---|---|
| `instances\ACV-2026-001.yaml` | En la C es la lista de **todos** los canales físicos, y el perfil decide cuáles se muestran (D8-3.17). Con el archivo de la B **no aparecen** Cámara 2, `descompresion_lenta`, el aire comprimido de chaqueta y de cámara, el agua de chaqueta ni el zumbador. Si el 22-oct se agregaron canales a mano (sección 6.1), el archivo de la C ya los trae: no hay que volver a editarlo. |
| `global_params.json` | Trae dos parámetros del equipo nuevos: pausa máxima en esterilización (30 s) y espera sellada sin sonda (30 min). Reemplazarlo es seguro: los valores vigentes de los parámetros del equipo se guardan en la base de datos, no en este archivo, y se conservan. |

7. Abra Autoclave con el acceso directo. En el primer arranque, la base de datos se actualiza sola a la versión 10.
8. Compruebe:
   - Información del sistema: versión y número de serie;
   - que los usuarios entran;
   - Parámetros del equipo: los valores de antes y los dos nuevos;
   - Entradas/Salidas: Cámara 2 y `descompresion_lenta` visibles.

**NO toque** (se conservan solos):

| Ruta en `C:\ProgramData\Especifika\Autoclave` | Contenido |
|---|---|
| `installation_profile.json` | Perfil de instalación (bloqueado) |
| `data\calibration.yaml` | **Calibración del equipo.** La C trae una calibración neutra (D8-3.18), pero solo se usa en un equipo nuevo: la del equipo no se reemplaza |
| `data\autoclave.db` | Usuarios, historial, bitácora, parámetros del equipo, presión atmosférica calibrada y mantenimiento |
| `programa\autoclave\cycles\user\` | Programas de ciclo del usuario |
| `programa\autoclave\config\serial_link.json` | Puerto de la tarjeta |
| `programa\autoclave\config\correo.json` | Correo (la contraseña está en el almacén de credenciales de Windows) |
| `programa\autoclave\config\active_instances.yaml`, `calibration.yaml` y `models\` | Sin cambios entre la B y la C |

**Volver a la B si la C falla:**
1. Cierre Autoclave.
2. Abra el `Autoclave.exe` de la B, responda Sí a "¿Actualizarlo?" y ciérrelo cuando se abra.
3. **Reemplace la carpeta completa** `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2. Es necesario porque la C deja la base de datos en la versión 10, que la B no conoce.

## 8c. Actualizar el equipo de pruebas de la B a la D (con el Setup)

Para pasar el equipo de pruebas, instalado el 22-oct con la **B**, a la **D** sin perder nada y **sin copiar archivos a mano**. La C no se instala. Se ensayó en el PC de la oficina con una copia simulada del equipo (perfil del equipo de pruebas, base de datos de la B con un usuario y un parámetro cambiado, calibración y correo propios) y el `_internal` real de la D: `docs/informes/tanda9/K9_compilacion_d.md`.

**Qué hace la D al actualizar:**
- el Setup reemplaza solo `C:\Program Files\Especifika\Autoclave` (borra antes `_internal\`);
- en `C:\ProgramData\Especifika\Autoclave` el Setup no copia ni borra nada; solo da permiso de Modificar a Usuarios;
- en el primer arranque, el programa refresca solo sus archivos de configuración **de fábrica** (`programa\autoclave\config\instances\*.yaml` y `global_params.json`), con copia de respaldo con fecha en `programa\respaldos_configuracion\<fecha>\`, y los programas de fábrica (`cycles\factory\`). Así aparecen Cámara 2, `descompresion_lenta` y los parámetros nuevos del equipo;
- la base de datos se actualiza sola a la versión 10.

**Orden:**
1. **Cierre Autoclave por completo** (las dos pantallas). En el Administrador de tareas no debe quedar ningún `Autoclave.exe`. Si queda abierto, el Setup ofrece cerrarlo.
2. **Respaldo:** copie la carpeta completa `C:\ProgramData\Especifika\Autoclave` a la USB (por ejemplo, `respaldo_B_2026-10-23`). Es la vuelta atrás.
3. Compruebe el Setup con `SHA256SUMS.txt` de la USB (PowerShell: `Get-FileHash .\Autoclave_Setup_1.0.0-d.exe` y comparar con la línea del Setup).
4. Ejecute `Autoclave_Setup_1.0.0-d.exe` y acepte el aviso de administrador.
5. En «Tareas adicionales»:
   - «Iniciar Autoclave automáticamente al iniciar sesión en Windows»: **marcada**;
   - «Configurar este PC como estación del autoclave»: **DESMÁRQUELA** en el equipo de pruebas hasta haber hecho la lista de verificación de `tools/instalador/LEEME.md` en un PC de prueba (D9-11: se valida primero en un PC de prueba). Viene marcada por defecto;
   - «Arranque sin logo de Windows…»: desmarcada.
6. Termine el Setup. Abra Autoclave con el acceso directo.
7. Compruebe:
   - Información del sistema: versión y número de serie;
   - que los usuarios entran;
   - Parámetros del equipo: los valores de antes, los dos nuevos (pausa máxima en esterilización 30 s, espera sellada sin sonda 30 min) y el grupo «Cámara segura»;
   - Entradas/Salidas: Cámara 2 y `descompresion_lenta` visibles; el paro y el atrapamiento muestran el estado interpretado;
   - sin sensores de presión: tarjeta de alarmas con SEN-06 y CIC-10 («Estado seguro detenido»), **sin** botón de confirmación ni «paro liberado»; el inicio de sesión, el modo prueba, el cambio de programa y el apagado funcionan (casos C-05 a C-05h de la hoja de banco).
8. **Programas de usuario:** la actualización no toca `programa\autoclave\cycles\user\`, así que el equipo conserva los programas de la B, que traían valores del banco (el Bowie & Dick con modo 4 y 134,5 °C, entre otros). Revíselos en Parámetros del ciclo antes de los ciclos del lunes (PREGUNTA E9-P1).

**NO toque** (se conservan solos): `installation_profile.json` (perfil), `data\calibration.yaml` (calibración del equipo), `data\autoclave.db` (usuarios, historial, bitácora, parámetros), `data\asignacion_io.json` (asignación de E/S vigente), `programa\autoclave\cycles\user\` y `cycles\defecto\`, y en `programa\autoclave\config\`: `correo.json`, `serial_link.json`, `calibration.yaml` y `active_instances.yaml`. No hace falta copiar nada desde `Program Files`.

**Volver a la B si la D falla:**
1. Cierre Autoclave.
2. Abra el `Autoclave.exe` de la B desde la USB, responda Sí a «¿Actualizarlo?» y ciérrelo cuando se abra.
3. **Reemplace la carpeta completa** `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2 (la D deja la base de datos en la versión 10, que la B no conoce).

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
