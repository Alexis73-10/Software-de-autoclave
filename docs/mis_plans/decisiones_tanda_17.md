# Decisiones — Tanda 17: hallazgos de la instalación I (26-oct)

Origen: primeras pruebas tras instalar `entrega\2026-10-24_i\Autoclave_Setup_1.0.0-i.exe` (compilación I, anterior a la etapa VER) en el equipo de pruebas. Este archivo es la fuente de verdad de la tanda y prevalece sobre specs anteriores donde choque (en particular O11/D11-7 y SAF-01 de S9).

Contexto heredado de la tanda 16: unida a `dev` (be70836) pero **sin entrega**. `compilar_entrega.py` quedó bloqueado por la falla preexistente `tests/test_ver_entrega.py::test_historial_entrada_debajo_de_la_marca` (R16 §8). La entrega de esta tanda será la **1.0.0-alpha.2** e incluye la 16.

## Decisiones de Cristian (no reabrir)

### INS-01 · Zona horaria en el Setup
- El **Setup** (Inno, `tools/instalador/autoclave.iss`), no el asistente QML, tiene una página para elegir la zona horaria de Windows.
- La lista sale de `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Time Zones` (nombre visible, ordenado por desfase). Preseleccionada: la zona actual de Windows (`tzutil /g`). La página muestra también la fecha y hora locales como referencia.
- Se aplica en `ssPostInstall` con `tzutil /s "<id>"` y se verifica con `tzutil /g`. Si falla, se muestra un mensaje con el procedimiento manual, sin abortar la instalación. Parámetro de instalación silenciosa `/ZONA=<id>`.
- La página aparece también al actualizar o reinstalar.
- La instalación no deja nada en la bitácora (BIT-02). La zona solo queda en el log del Setup y en la fila `equipo_instalado`.

### INS-02 · Unidad de instalación (partición del SO aparte de la del software)
- El Setup pregunta la unidad. Lista solo **discos fijos** (`GetDriveType = DRIVE_FIXED`), con etiqueta y espacio libre; quedan fuera los USB, los removibles y las unidades de red.
- Preseleccionada: el primer disco fijo distinto de `%SystemDrive%`; si no hay otro, la del sistema.
- Exige un mínimo de espacio libre: tamaño del programa + 2 GB. Code calcula la cifra.
- Disposición única, en cualquier unidad, incluso C: (D-17.2a, recomendación aceptada: programa y datos juntos en la unidad elegida):
  - `X:\Especifika\Autoclave\programa` es `{app}`: el .exe y `_internal\`;
  - `X:\Especifika\Autoclave\datos`: perfil, base de datos, logs, tickets, respaldos, `estacion\` y todo lo que hoy va a `%ProgramData%\Especifika\Autoclave`.
- **ACL explícitas, sin herencia** de la raíz. La raíz de D: por defecto da "crear/modificar" a Usuarios autenticados, y en un software Clase C el programa no puede quedar modificable por un usuario estándar.
  - `programa`: Administradores y SYSTEM con control total; Usuarios con lectura y ejecución.
  - `datos`: Usuarios con modificar.
  - `datos\estacion`: solo Administradores y SYSTEM, como hoy (`_comun.ps1`).
- El Setup escribe `HKLM\SOFTWARE\Especifika\Autoclave` con `RutaPrograma` y `RutaDatos`, en la vista de 64 bits.
- Orden para resolver la carpeta de datos en tiempo de ejecución (`utils/resources.raiz_datos_exe`):
  1. `RutaDatos` del registro, si `RutaPrograma` coincide con la carpeta del .exe en ejecución;
  2. la regla actual (Archivos de programa → `%ProgramData%`);
  3. la carpeta del .exe (copia portátil).
- Toda ruta que hoy apunte a `%ProgramData%\Especifika\Autoclave` (el Setup, `estacion_setup.ps1`, los scripts de `tools/estacion`, la tarea de arranque, el log de la estación, la "instalación limpia", el desinstalador, los respaldos, la USB de recuperación, el generador y AutoclaveSettings si aplica) pasa a usar la ruta resuelta.
- Actualización:
  - Si existe una instalación con la disposición nueva (clave de registro), el Setup reutiliza su unidad y la página la muestra fija, sin poder cambiarla.
  - Si existe una instalación con la disposición anterior (Archivos de programa, compilación I o anterior), el Setup **se detiene**: pide desinstalarla primero e instalar en limpio (D-17.2b). No hay migración de datos.
- Desinstalar: hace lo mismo que hoy con `%ProgramData%`, aplicado a la carpeta `datos` nueva. Los datos se conservan salvo la opción explícita de la "instalación limpia" que ya existe.

### SON-01 · Sondas "No en uso" visibles (revierte O11, D11-7.1 a 7.5)
- Una sonda **instalada** (perfil) con rol No en uso se vuelve a leer y a publicar en `/status`.
- Se puede elegir en Entradas mostradas (Preciclo, Ciclo en curso y gráfica). El máximo sigue siendo 3.
- Se muestra con el rótulo **"(monitoreo)"** (es) / **"(monitoring)"** (en).
- **Se registra** en el registro del ciclo (lecturas guardadas, gráfica del historial, PDF y correo). **No va en el ticket.**
- No participa en control, fallas, F0, uniformidad, entrada a esterilización, cámara segura, SENSOR_AUSENTE ni SEN-11. Sin lectura se muestra "—", sin alarma ni aviso.
- Al pasar una sonda a No en uso ya no se quita de las Entradas mostradas: retirar `entradas_tras_cambio_de_rol` y el evento `entradas_mostradas`. Se retira también el rechazo `SENSOR_NO_EN_USO` al guardar entradas.
- Una sonda **no instalada** sigue oculta.

### PRC-01 · Selector de programas
- En Opciones › Parámetros del ciclo, la cuadrícula (`Flow`) de programas se reemplaza por un **desplegable**: un botón con el programa vigente que abre una lista **vertical con desplazamiento**, con número y nombre de cada programa. Debe funcionar bien con 15 o más programas.
- El mismo componente reutilizable va en Opciones avanzadas › Manejo de ciclos, para uniformidad (DECISIÓN SIN CONFIRMAR).

### ESG-01 · Estado seguro sin sensor de presión de cámara
- Si el estado seguro no puede avanzar porque la presión de cámara no tiene lectura, **no se activa CIC-10**; si estaba activa por ese motivo, se resuelve.
- Solo se ve la alarma del sensor: desconectado o sin lectura (SEN-04), y presión baja o alta si existe.
- El protocolo sigue pausado: requisito del 23-oct, sin presión no se lleva la cámara a estado seguro.
- "NO ABRIR" y el bloqueo del inicio de ciclo **se mantienen**, porque sin presión la cámara no puede declararse segura (falla cerrada).
- CIC-10 se conserva para los demás motivos.
- El motivo va al log de desarrollo.

### ESG-02 · Modo prueba con el estado seguro activo (corregido por Cristian, 26-oct 16:46)
- Con **lectura vigente de presión de cámara**, el modo prueba pausa el protocolo (ya es así) y retira los bloqueos **propios del estado seguro** (`salida_prueba_estado_seguro`). Quedan libres: descompresión rápida, descompresión de chaqueta, aire comprimido de cámara, vapor de generador y de caldera, y vapor de cámara salvo la protección 3.
- Sin lectura vigente de presión se mantienen todos los bloqueos actuales.
- Al salir del modo prueba el protocolo se reanuda solo (sin cambios).
- **Protecciones del modo prueba que rigen SIEMPRE**, con o sin estado seguro activo. Fallan cerradas: sin dato no se permite. Rechazo con código y texto propios (es/en), sin entrada en la bitácora (BIT-01).
  1. **Puerta con la cámara presurizada:** `abrir_puerta_N` se rechaza si la cámara no es segura según el criterio de `camara_segura`, es decir, presión fuera de `presion_atmosferica ± rango_presion_atm`, o si no hay lectura. El criterio actual cubre también el vacío; se conserva así, como DECISIÓN SIN CONFIRMAR avisada a Cristian.
  2. **Vacío a los empaques con la cámara presurizada:** `desbloqueo_puerta_N`, que aplica vacío al empaque para retraerlo (`AdvancedDoor`, `desbloquear_on` + `vacio_empaque`), se rechaza con la misma condición que 1. Si el código tiene otra salida que lleve vacío al empaque, V-03 la identifica y queda con la misma protección.
  3. **Vapor a la cámara con una puerta abierta:** `vapor_camara` se rechaza si alguna puerta instalada no está confirmada cerrada (`puerta_N_cerrada` falso o sin lectura). Si `vapor_camara` está encendida en modo prueba y una puerta deja de estar cerrada, se apaga en el mismo tick y se avisa en la pantalla de Entradas/Salidas.
  - La protección 3 aplica también si hay una puerta abierta o sin lectura con la orden ya dada. Las protecciones 1 y 2, si la cámara se presuriza con la orden ya dada (salida encendida antes de la presurización), apagan la salida.
- Se conserva el corte de `aire_atmosferico_camara` de D8-3.19.
- `bloqueo_puerta_N` (presión al empaque / cerrojo) y `descompresion_lenta` no se tocan.
- Riesgo residual registrado (ISO 14971): sin datos de presión o de puerta, el modo prueba queda más restringido, y el técnico debe resolver el sensor antes de probar esas salidas.

### MPR-01 · Presión en el modo prueba
- En Opciones › Entradas/Salidas, con el modo prueba activo, la parte superior muestra la **presión de cámara** en la unidad vigente, refrescada con el estado; "—" sin lectura.

### ALM-01 · Listas de alarmas, alertas y fallos
- En toda lista (tarjeta de Preciclo, panel de la campana, Ciclo en curso y cualquier otra), cada fila muestra **solo el nombre** con el color o icono de nivel.
- Al tocarla se abre una **ventana emergente** con el detalle: nombre, nivel, código, hora de activación, descripción, causa o acción y estado, y las acciones que hoy están en la fila (reconocer o despejar). Botón cerrar.
- "Confirmar y llevar a estado seguro" se queda visible en la tarjeta y en el panel, fuera de la ventana emergente, porque es una acción de seguridad de acceso directo (DECISIÓN SIN CONFIRMAR).

### VER-08 · Versión en Información del equipo y del sistema
- En la compilación I no aparecía porque es anterior a VER. Se verifica en la alpha.2: las dos pantallas muestran `version_completa()`.
- Se agrega una prueba que falla si la fila `version_software` sale vacía o como "—" con `_build_info` presente, con `sys.frozen` simulado.

### UI-VER · Quitar "V:1.0"
- Se elimina la clave `app.version` y su uso en la barra inferior de todas las pantallas QML (`BarraInferior`, `BarraInferiorMenu` y cada pantalla), en `ui_pyside/main_window.py` (`lbl_ver`) y en las galerías de `Pruebas/`.
- La versión solo se muestra en Información del equipo y del sistema.

### BIT · Bitácora (`audit_log`)
Causa: con 10 minutos de instalado ya había 3 páginas.
- **BIT-01:** del modo prueba se registran solo `modo_prueba_entra`, `modo_prueba_salida_forzada` y `aire_atmosferico_cortado_prueba`. Ya no se registran `salida_prueba` ni `modo_prueba_sale`.
- **BIT-02:** mientras la instalación no esté terminada (asistente en curso o perfil no finalizado) no se escribe nada en la bitácora: `contrasena_fijada_instalacion`, `idioma_configurado`, `unidades_configuradas`, `impresora_configurada`, `param_*`, programas y cualquier otro evento. Al terminar el asistente se escribe **una sola fila `equipo_instalado`** con serie, modelo, versión y zona horaria de Windows.
- **BIT-03:** ya no se registran `login_fallido` ni `logout`. Siguen `login_bloqueado` y `login_ok`.
  - **Verificar antes:** que el contador de intentos que bloquea al usuario no dependa de las filas `login_fallido` de `audit_log`. Si depende, el contador pasa a su propio almacenamiento y el bloqueo queda idéntico. Prueba obligatoria.
- **BIT-04:**
  - Los eventos retirados se escriben en el log de desarrollo (logger) en lugar de `audit_log`, como en D9-6.
  - El filtro es **central**, en el escritor de auditoría, con una lista de eventos permitidos. No se toca cada llamada.
  - Las filas ya guardadas no se borran (`audit_log` solo admite agregar); la vista oculta las de eventos retirados.
- **BIT-05:** filtros de Opciones › Bitácora.
  - **Usuario:** desplegable con "Todos" y los usuarios distintos presentes en la bitácora.
  - **Tipo:** desplegable por categorías: Seguridad, Configuración, Usuarios y sesión, Mantenimiento y calibración, Sistema. Code asigna cada evento de `EVENTOS` a una categoría y deja la tabla en el informe.
  - **Fecha:** rango Desde–Hasta. Cada campo abre un **calendario** táctil (mes con flechas, día por toque, sin teclado). Por omisión Hasta = hoy, y Desde conserva el defecto actual.
  - Si el backend no filtra por rango, se agrega.

### EST-06 · Asociación de pantallas táctiles (falló en el equipo)
Log: `Setup: paso 06 (Aplicar) FALLO: No se encuentra C:\WINDOWS\System32\MultiDigitizer.exe`.
1. Se conserva el camino actual si `MultiDigitizer.exe` existe (System32 o Sysnative).
2. Si no existe, se usa una **herramienta propia**: `Autoclave.exe --rol asociar-tactiles`.
   - Muestra "Toque esta pantalla" a pantalla completa en cada monitor, uno a la vez.
   - Identifica el digitalizador con Raw Input (página HID 0x0D) y el monitor con `EnumDisplayDevices`/`EDD_GET_DEVICE_INTERFACE_NAME`.
   - Escribe los valores en `HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon` con el mismo formato que deja MultiDigitizer. Code documenta el formato con la fuente.
   - Respaldo y reversión compatibles con `06_revertir_asociar_tactiles.ps1`.
   - Avisa si hace falta reiniciar.
3. El mensaje `TactilesRepetir` deja de remitir a "Configuración de Tablet PC" cuando esa herramienta no existe.
4. El fallo del paso 06 no interrumpe los demás pasos de la estación.

No se puede probar en CI: va a la lista de **pruebas manuales en el PC de prueba**.

### EST-07 · El escritorio de Windows queda expuesto unos 30 s al iniciar sesión
- La tarea de arranque pasa de `Delay = PT10S` a `PT0S` (`tools/instalador/tarea_arranque.ps1` y `tools/estacion/03_tarea_autoclave.ps1`).
- **Cubierta inmediata:** lo primero que hace `exe_unico.py` en el rol lanzador, antes de importar PySide o arrancar el backend, es abrir una ventana Win32 nativa con ctypes.
  - Una por monitor, sin borde, siempre encima, del tamaño completo del monitor (cubre la barra de tareas), fondo negro con "Iniciando…" bilingüe o solo el logotipo de texto.
  - Absorbe los toques y clics, para que no se pueda usar el escritorio.
  - Se cierra cuando las pantallas QML avisan que mostraron su primer cuadro (evento con nombre o archivo de señal en `datos`) o tras un tope de 180 s.
  - Si falla, solo se registra en el log y el arranque sigue.
- Queda el hueco entre el autologon y el disparo de la tarea (explorer cargando): se mide y se informa.
- Reemplazar el shell (modo quiosco) queda para después (Shell Launcher exige ciertas ediciones de Windows; ver `03_tarea_autoclave.ps1`).

Todo EST-07 es DECISIÓN SIN CONFIRMAR, con validación manual en el PC de prueba.

### Ejecución
- Sin supervisión, con `lanzar_tanda.ps1 -Tanda 17`.
- **Hasta 4 subagentes a la vez.**
- Cierra con **K**: entrega 1.0.0-alpha.2.
