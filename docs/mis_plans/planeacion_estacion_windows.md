# Planeación — Estación Windows (quiosco) del PC industrial

Estado: documento de planeación (W1, tanda 2, 20-oct-2026). **Solo diseño: no se ejecutó ningún cambio de sistema.** Los pasos de configuración los hace Cristian en el PC industrial; lo que depende de la edición de Windows se marca como tal.

## 1. Objetivo

Que el PC industrial arranque directo en el software del autoclave, sin escritorio, sin login visible ni logo de Windows que distraiga, que el operador no pueda salir de la aplicación, y que el soporte remoto y las actualizaciones sean controlados. **El PC no debe ser un riesgo para el ciclo:** una actualización o un reinicio automático de Windows nunca puede ocurrir con un ciclo en curso.

## 2. Punto de partida (lo que ya hace el software)

- **Ejecutable único** `Autoclave.exe` (`exe_unico.py` + `Autoclave.spec`): lanza el backend como subproceso supervisado y las dos pantallas QML (puerta 1 y 2, un monitor cada una) con relanzamiento automático (hasta 3 veces). Si el equipo no está instalado, ofrece copiarse a `%ProgramFiles%\Especifika\Autoclave`; los datos van en `%ProgramData%\Especifika\Autoclave`.
- **Oculta la barra de tareas** de Windows mientras corren las pantallas y la restaura al terminar (`ui_qml/barra_tareas.py`).
- **Apagado desde el software** ("Apagar equipo", solo desde la puerta 1 y con la cámara segura): apaga salidas, cierra la base y el puerto serial y ejecuta `shutdown /s` (solo con el ejecutable o `AUTOCLAVE_APAGADO_REAL=1`).
- **Cierre ordenado** de las pantallas: apaga salidas y detiene el backend, salvo con un ciclo en curso.
- **Latido de apagado** y ticket de arranque: el ticket informa la hora aproximada del último apagado.

## 3. Arranque sin logo ni login

1. **Inicio de sesión automático** de una cuenta local restringida (`netplwiz` o la clave de registro de Winlogon `AutoAdminLogon`). La contraseña queda guardada en el registro (riesgo aceptado: la cuenta no tiene privilegios y el equipo es físico, no expuesto).
2. **Arranque del software:** tarea programada "al iniciar sesión" de esa cuenta que lanza `Autoclave.exe`, con reintento si falla. Preferible a la carpeta Inicio porque se puede reintentar y registrar. Variante más robusta: **Shell Launcher / Assigned Access**, que reemplaza el escritorio por la aplicación (**requiere Windows 10/11 Pro, Enterprise o Education: no funciona en Home**; verificar la edición del PC industrial).
3. **Sin logo de arranque ni mensajes:** configurar el arranque silencioso (`bcdedit /set bootux disabled`, ocultar la pantalla de bienvenida) y quitar el fondo del login. Cuidado: es cosmético y puede dificultar el diagnóstico; probar con una copia de seguridad del BCD.
4. **Sin pantalla de bloqueo ni contraseñas de reposo:** desactivar el bloqueo al reanudar; el reposo del software (standby) ya es propio.

## 4. Cuenta restringida y bloqueo de la salida

- Cuenta local **estándar** (sin permisos de administrador) para el operador; una cuenta de administrador distinta, con contraseña fuerte, solo para el técnico.
- Directivas de grupo (o Registro), en Pro: ocultar el administrador de tareas, el menú Inicio y el acceso a `cmd`, PowerShell y el Explorador; bloquear Alt+Tab y las teclas de Windows (Keyboard Filter, solo Enterprise/Education) o con un hook propio.
- El software está pensado para que no haya salida a Windows desde la UI. Falta decidir cómo entra el técnico: **combinación de teclas del técnico** o un interruptor físico, con contraseña. Sin definirlo, la restricción puede dejar al técnico fuera del equipo.
- Permisos de carpeta: `%ProgramData%\Especifika\Autoclave` con escritura solo para el software y administradores (contiene la base, la calibración y los respaldos).

## 5. Control de actualizaciones

- **Windows Update nunca debe reiniciar el equipo solo.** Fijar las horas activas más amplias, directivas "no reiniciar automáticamente con usuarios conectados" y, en Pro, **diferir** las actualizaciones de calidad y de características (hasta 30 y 365 días), con instalación manual en ventana de mantenimiento.
- **Idealmente**, una conexión de red de **uso medido** o sin acceso a Internet salvo cuando se hace mantenimiento.
- **Actualizaciones del software** (Autoclave.exe): por ahora manuales (copiar el `.exe` nuevo). Pendiente un procedimiento: copia de seguridad de `%ProgramData%`, reemplazo, verificación del firmware emparejado y del perfil.
- **Controladores y firmware** de la tarjeta de E/S: solo por mantenimiento (compilar y cargar firmware está fuera del alcance del software).
- Antivirus: excluir `%ProgramData%\Especifika\Autoclave` del análisis en tiempo real si el fsync del respaldo resulta lento (medir primero; ver la hoja de banco).

## 6. Soporte remoto (AnyDesk)

- Instalar AnyDesk **sin acceso desatendido por defecto**: el técnico en sitio acepta cada sesión, o el acceso desatendido se habilita con contraseña fuerte, lista blanca de ID y **solo mientras dure el mantenimiento**.
- La sesión remota no debe poder iniciar ni detener ciclos sin que alguien presente lo sepa: el equipo es un dispositivo médico con riesgo físico. Para el expediente: documentar que el soporte remoto es solo de diagnóstico y de archivos, no de operación.
- Registro de las sesiones (quién, cuándo) en la bitácora de mantenimiento.

## 7. Apagado y energía

- Apagado normal: **solo con "Apagar equipo"** del software; Windows no debe ofrecer apagar desde un menú.
- Botón de encendido físico: configurar la acción "no hacer nada" (o "apagar" solo si el software soportara el cierre ordenado a partir de ese evento, hoy no lo hace).
- **Corte de energía:** el equipo debe arrancar solo al volver la energía (BIOS: "restaurar tras pérdida de energía = encendido"). Considerar un **UPS** con apagado ordenado por señal (diseño aparte).
- Desactivar hibernación y suspensión (`powercfg`): el software maneja su propio reposo y HIBERNACION no está activa (OPC-25).

## 8. Tareas programadas

| Tarea | Cuándo | Qué hace |
|---|---|---|
| Arranque del software | Al iniciar sesión | `Autoclave.exe`, con reintento (3 veces, 1 min) |
| Respaldo de datos | Diaria, fuera de horario | Copia de `%ProgramData%\Especifika\Autoclave\data` (base, respaldos JSONL, calibración) a otro disco o carpeta de red; verificación; retención |
| Limpieza de registros | Semanal | Rotar `logs` y los registros del lanzador |
| Revisión de espacio en disco | Diaria | Aviso si queda poco espacio (la base y los respaldos crecen) |

Todas con cuenta del sistema y sin ventanas. **No se crearon**: se describen para que Cristian las cree.

## 9. Qué se prueba en el PC industrial

1. **Arranque en frío:** de encendido a pantallas en < 90 s, sin intervención, sin logo ni login visibles.
2. **Corte de energía** en preciclo y en ciclo (hoja de banco C-03 y F-03): el equipo arranca solo, apaga salidas, pide el estado seguro si corresponde.
3. **Cierre de pantallas** con el administrador de tareas (cuenta restringida: no debe ser posible) y con una pantalla muerta (se relanza).
4. **Dos monitores** y la barra de tareas oculta en ambos (incluida la del segundo monitor).
5. **Windows Update:** que no reinicie con el software abierto; forzar una actualización pendiente y verificar que queda diferida.
6. **Alt+Tab, Win, Ctrl+Alt+Supr** y el acceso del técnico (§4).
7. **AnyDesk:** que una sesión remota no pueda operar ciclos sin presencia, y que quede registrada.
8. **Apagar equipo** y el botón físico de encendido.
9. **Rendimiento del fsync** del respaldo con el antivirus activo (relacionado con S3d).
10. **Respaldo diario:** que se cree, se verifique y se pueda restaurar.

## 10. Decisiones pendientes de Cristian

1. Edición de Windows del PC industrial (Pro o Enterprise para Shell Launcher y Keyboard Filter; con Home, solo la tarea programada y las directivas básicas).
2. Cómo entra el técnico a Windows (§4).
3. Política de actualizaciones de Windows (§5) y de acceso remoto (§6).
4. Si se compra un UPS (§7).
5. Si el PC se aísla de Internet o se deja en red de uso medido.

## 11. Riesgos a registrar (ISO 14971 / IEC 62304)

- Una actualización o reinicio automático durante un ciclo (controlado por §5).
- Un acceso remoto que opera el equipo sin presencia (§6).
- Una cuenta con privilegios que permite salir de la aplicación y manipular los datos (§4).
- Un corte de energía sin UPS (§7): el ciclo queda INTERRUMPIDO y la cámara requiere estado seguro al volver.
