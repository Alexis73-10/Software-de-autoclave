# Instalador tipo Setup (Inno Setup 6)

`autoclave.iss` arma un solo `.exe` de instalación a partir de una carpeta `Autoclave\` **ya compilada y verificada** (la de una entrega, p. ej. `entrega/2026-10-23_d/Autoclave/`). No recompila el programa.

## GUID (AppId)

```
{81C9DAB1-5CF8-4AD2-A7BE-15053E6ED43F}
```

Se generó una sola vez el 2026-10-22. **No se cambia nunca.** Gracias a él, Windows reconoce el Setup de una versión nueva como el mismo producto que la anterior y la actualiza en su lugar, en vez de instalar una segunda copia al lado.

## Cómo compilar

1. Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e --source winget`). En el PC de desarrollo quedó instalado por usuario en `%LOCALAPPDATA%\Programs\Inno Setup 6\`.
2. Verificar la carpeta `Autoclave\` de la entrega:
   - contra su `MANIFIESTO_CARPETA_Autoclave.sha256`;
   - `python tools/verificar_entrega_neutra.py <entrega>\Autoclave` debe decir `OK` (correo sin remitente ni destinatarios, solo `cycles/factory` y calibración neutra; D9-7 y D8-3.18).
3. Compilar:

   ```
   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DEntrega=C:\ruta\a\entrega\2026-10-23_d tools\instalador\autoclave.iss
   ```

   Sin `/DEntrega`, usa `entrega\2026-10-23_d` del repositorio. El Setup sale en esa misma carpeta: `Autoclave_Setup_<versión>.exe` (con `/O<carpeta>` sale en otra).
4. Calcular el SHA-256 del Setup y agregarlo a `SHA256SUMS.txt` de la entrega.
5. **No ejecutar el Setup en el PC de desarrollo**: instalaría el programa ahí y, con la casilla de la estación marcada, cambiaría la configuración de Windows de ese PC.

## Qué hace el Setup

- Instala `Autoclave.exe` y `_internal\` juntos en `C:\Program Files\Especifika\Autoclave` (64 bits). La carpeta no se puede elegir: el programa solo guarda sus datos en `C:\ProgramData\Especifika\Autoclave` cuando corre bajo `%ProgramFiles%` (`utils/resources.raiz_datos_exe`). Además, solo se reconoce como instalado en esa ruta exacta (`instalador_exe.esta_instalado_aqui`); en otra, vuelve a ofrecer instalarse.
- Al actualizar, borra antes `_internal\` de la instalación, para no mezclar archivos de dos compilaciones.
- Crea accesos directos "Autoclave" en el menú Inicio y en el Escritorio común.
- `C:\ProgramData\Especifika\Autoclave`: crea la carpeta si falta y da permiso de Modificar a Usuarios (también si ya existía), para que el programa escriba sus datos con una cuenta sin privilegios. **Nunca** copia, sobrescribe ni borra archivos ahí (perfil, calibración, base de datos, usuarios), **salvo la Instalación limpia** (ver abajo), que se elige a mano, con doble confirmación y respaldo previo. El desinstalador no la toca y avisa que los datos se conservan.
- Al actualizar, **no hace falta copiar nada a mano**: al arrancar, la versión nueva del programa refresca sola sus archivos de configuración de fábrica (`instances\*.yaml` y `global_params.json` de `ProgramData\...\programa\autoclave\config\`), con copia de respaldo con fecha en `ProgramData\...\programa\respaldos_configuracion\<fecha>\` (D9-13.1). Nunca toca la calibración del equipo, el correo, la asignación de E/S vigente, el perfil, la base de datos ni los programas de usuario.
- No incluye `GeneradorCodigos.exe`, el perfil de instalación ni `data/`.
- Pide administrador. El asistente está en español, con inglés disponible.

### Casillas (página "Tareas adicionales")

| Casilla | Por defecto | Qué hace |
|---|---|---|
| Iniciar Autoclave automáticamente al iniciar sesión en Windows | marcada | Tarea programada `Especifika Autoclave - Arranque` (mismo nombre y mecanismo que `tools/estacion/03_tarea_autoclave.ps1`; si después se ejecuta ese script, la reemplaza y nunca quedan dos arranques). Es de la cuenta del inicio automático si se marca la estación; si no, de la cuenta con la sesión abierta. El desinstalador la borra. |
| Configurar este PC como estación del autoclave | **marcada** | Pasos 01, 04 y 05 de `tools/estacion/` (D9-11): inicio de sesión automático con la cuenta que instala (no se crea ninguna cuenta), sin notificaciones, Windows Update solo avisa y se difiere (no se desactiva), sin gestos de borde, sin suspensión ni hibernación y botón de encendido sin acción. Pide usuario y contraseña en la página siguiente. Al terminar, el Setup pide reiniciar. |
| ↳ Asociar cada pantalla táctil con su monitor | marcada (solo con 2 o más monitores) | Paso 06 (tanda 11, D11-5): abre `MultiDigitizer.exe` para tocar cada pantalla una vez. Ver "Pantallas táctiles" abajo. |
| Arranque sin logo de Windows y sin pantalla de bloqueo | **desmarcada** | Paso 02: `bcdedit /set {current} bootux disabled` (con copia previa del BCD), sin pantalla de bloqueo ni contraseña al reanudar. |

Detalles de la estación:
- **Página "Inicio de sesión automático"** (solo con la casilla de la estación): usuario (viene escrito el de la sesión abierta, `EQUIPO\usuario`; para una cuenta de dominio, `DOMINIO\usuario`), contraseña y repetición. No deja seguir sin contraseña o si las dos no coinciden. **No comprueba que la contraseña sea la correcta**: si es incorrecta, Windows mostrará la pantalla de inicio de sesión al reiniciar (sin otro efecto).
- La contraseña pasa al script por una variable de entorno del proceso, nunca por la línea de comandos, y queda en el registro de Windows (`Winlogon\DefaultPassword`), como exige el inicio automático (riesgo aceptado en el plan de la estación, §3.1). El log nunca la muestra.
- Los scripts se instalan en `C:\Program Files\Especifika\Autoclave\estacion\` (solo administradores pueden cambiarlos) y los ejecuta `estacion_setup.ps1` sin interacción. El log y los respaldos de los valores originales quedan en `C:\ProgramData\Especifika\Autoclave\estacion\`, carpeta que los scripts restringen a Administradores y SYSTEM (la de datos tiene Modificar para Usuarios).
- Si un paso falla, el Setup lo avisa al final con la lista de pasos y la ruta del log; Autoclave queda instalado igual.
- El Setup anota en `HKLM\SOFTWARE\Especifika\Autoclave\Estacion` los pasos que aplicó. **El desinstalador revierte solo esos**, en orden inverso (06, 05, 04, 02, 01), con los scripts de reversión, y borra esa clave. Si una reversión falla, lo avisa: entonces hay que correr a mano, como administrador, el script `0X_revertir_...ps1` de `tools/estacion/` (desde la USB o el repositorio, porque el desinstalador ya borró la copia instalada).
- Si en una actualización se desmarca la casilla de la estación, no se revierte nada (eso lo hace el desinstalador o los scripts de reversión). Si se deja marcada, vuelve a pedir la contraseña y vuelve a aplicar los pasos (los scripts son idempotentes).

## Setup sobre una instalación existente (Actualizar / Reparar / Instalación limpia / Desinstalar)

El Setup compara su versión (`AppVerNum`) con la instalada, que anota en `HKLM\SOFTWARE\Especifika\Autoclave\Instalacion\VersionNum` (la borra el desinstalador). Las instalaciones 1.0.0-a a 1.0.0-d no tienen ese valor: se comparan por `DisplayVersion`. Si es la misma, se tratan como iguales; si es distinta, como más viejas.

| Instalada | Qué hace el Setup |
|---|---|
| Ninguna | Instalación normal. |
| Más vieja | Página "Actualizar Autoclave": **Actualizar (conserva los datos)**, marcada por defecto (el flujo de siempre), o **Instalación limpia** (tanda 11, D11-4). |
| **La misma** | Página "Autoclave ya está instalado": **Reparar** (por defecto), **Instalación limpia** o **Desinstalar**. La antigua opción "Reinstalar" ya no existe. |
| Más nueva | Se niega a instalar y pide desinstalar primero (no se baja de versión). |

- **Actualizar** (versión más vieja): el asistente normal. Conserva los datos de `C:\ProgramData\Especifika\Autoclave`.
- **Reparar** (misma versión): vuelve a copiar el programa y los scripts (borra antes `_internal\`). Recrea la tarea de arranque si estaba elegida y vuelve a aplicar los pasos 04, 05 y 02 que estaban anotados en `...\Estacion`, incluidos los que fallaron, porque se anotan antes de aplicarse. No muestra las tareas ni la página de la cuenta, y **no reaplica los pasos 01 ni 06** (el 01 pediría la contraseña; el 06 abre la herramienta de los táctiles): el inicio automático y la asociación de los táctiles quedan como estaban, y la tarea se recrea para la cuenta del inicio automático (`Winlogon\DefaultUserName`). Un Setup silencioso (`/SILENT`, `/VERYSILENT`) de la misma versión hace Reparar; uno de una versión más nueva hace Actualizar. **Un Setup silencioso nunca hace una instalación limpia.**
- **Desinstalar**: abre el desinstalador normal (con su confirmación) y cierra el Setup.
- **Instalación limpia** (versión más vieja o la misma):
  1. Al pulsar Siguiente pide **dos confirmaciones**, las dos con "No" por defecto. La segunda dice que se borran los ciclos registrados, los usuarios, el perfil de instalación y la calibración.
  2. No se borra nada hasta pulsar **Instalar**. Hasta entonces, Atrás y otra opción la deshace.
  3. Al instalar, si Autoclave está abierto, se detiene sin tocar nada ("ciérrelo y vuelva a ejecutar este instalador").
  4. **Respaldo completo** de `C:\ProgramData\Especifika\Autoclave` en `C:\ProgramData\Especifika\Autoclave_respaldos\AAAAMMDD-HHMMSS\` (fuera de la carpeta que se borra). La carpeta `Autoclave_respaldos` queda solo para Administradores y SYSTEM, porque el respaldo incluye la base con los usuarios y la carpeta `estacion\`. El Setup verifica el respaldo (mismo número de archivos y de bytes que el original).
  5. **Si el respaldo falla o no coincide, no se borra nada** y el Setup se detiene sin instalar (avisa que la carpeta de respaldo puede estar incompleta).
  6. Con el respaldo verificado, borra todo el contenido de la carpeta de datos (perfil de instalación, calibración, base de datos, usuarios, programas de usuario, configuración, tickets, logs…) **salvo `estacion\`**. Esa carpeta tiene los valores de Windows anteriores a la estación, que necesita el desinstalador para revertirla. Si algo no se pudo borrar, se detiene sin instalar e indica dónde está el respaldo.
  7. Sigue con el asistente completo (tareas y cuenta, como una instalación nueva).
  8. Al abrir Autoclave no hay perfil: se abre el menú de instalación del equipo.
  - Para recuperar los datos: con Autoclave cerrado, copiar como administrador el contenido de la carpeta del respaldo a `C:\ProgramData\Especifika\Autoclave`.
  - Los respaldos no se borran solos (ni el desinstalador los toca). Borrar a mano los que ya no hagan falta.

## Pantallas táctiles (paso 06, D11-5)

- Subcasilla de la estación **"Asociar cada pantalla táctil con su monitor"**, marcada por defecto. **Solo aparece si el PC tiene 2 o más monitores** conectados al ejecutar el Setup.
- Al instalar, abre la herramienta de Windows `MultiDigitizer.exe` (Configuración de Tablet PC › Configurar › Entrada táctil). Pide tocar la pantalla que muestra el mensaje y pasar a la siguiente (Enter salta una pantalla). Si nadie la cierra en 10 minutos, el Setup la cierra y sigue.
- Al terminar, cuenta las asociaciones de `HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon` y las escribe en `estacion.log`. Si quedan menos de 2, avisa al final: "Repita la asociación de pantallas táctiles". La instalación no falla.
- El desinstalador borra las asociaciones que creó el paso (y devuelve su valor a las que cambió).
- **Windows guarda la asociación por puerto USB: marcar los puertos de cada táctil.** Cambiar un cable de puerto la deshace (ver `tools/estacion/LEEME.md`).

## Lista de verificación en el PC de prueba (D9-11)

**Antes de usarlo en el equipo del autoclave.** En un PC de prueba con Windows 10/11 de 64 bits, preferiblemente una máquina virtual con instantánea, sin datos importantes. Anotar la edición de Windows: ________

Antes de instalar, anotar el estado original (para comparar con la reversión):
- [ ] `reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon` (y `DefaultUserName`, `DefaultDomainName`, `DefaultPassword`): ________
- [ ] `powercfg /getactivescheme` y `powercfg /a` (hibernación): ________
- [ ] `bcdedit /enum {current}` (¿hay línea `bootux`?): ________
- [ ] `icacls C:\ProgramData\Especifika\Autoclave` (si ya existe): ________

Instalar:
- [ ] Doble clic en `Autoclave_Setup_1.0.0-d.exe` con una cuenta administradora (la que va a quedar con inicio automático). Aceptar el UAC.
- [ ] Página "Tareas adicionales": aparecen las tres casillas; "Configurar este PC como estación del autoclave" **marcada** y "Arranque sin logo" **desmarcada**.
- [ ] Página "Inicio de sesión automático": el usuario viene escrito con la cuenta de la sesión. Probar: contraseña vacía → no deja seguir; contraseñas distintas → no deja seguir. Escribir la contraseña correcta dos veces.
- [ ] La instalación termina sin mensajes de error y ofrece reiniciar.
- [ ] Sin reiniciar todavía, revisar `C:\ProgramData\Especifika\Autoclave\estacion\estacion.log`: líneas `Setup: Aplicar paso 01/04/05 ... terminado`, ninguna `FALLO`, y la contraseña aparece como `********`.
- [ ] `icacls C:\ProgramData\Especifika\Autoclave`: `BUILTIN\Usuarios:(OI)(CI)(M)` (o `BUILTIN\Users`).
- [ ] `icacls C:\ProgramData\Especifika\Autoclave\estacion`: solo `BUILTIN\Administradores` y `NT AUTHORITY\SYSTEM`, sin `Usuarios`.
- [ ] `reg query HKLM\SOFTWARE\Especifika\Autoclave\Estacion`: `Paso01`, `Paso04`, `Paso05` (y `Paso02` solo si se marcó la casilla del logo).

Reiniciar:
- [ ] Windows entra solo con la cuenta indicada, sin pedir contraseña.
- [ ] Autoclave se abre solo (asistente de instalación del equipo si no hay perfil).
- [ ] No aparecen notificaciones de Windows; en Configuración › Windows Update se ven las horas activas 6 a 23 (en Windows Home las directivas pueden ignorarse: anotarlo).
- [ ] Sin suspensión ni apagado de pantalla tras 30 min sin uso; `powercfg /a` dice que la hibernación no está disponible.
- [ ] Con la casilla del logo desmarcada, el arranque sigue mostrando el logo de Windows (no se aplicó el paso 02).
- [ ] (Opcional, segunda pasada con la casilla del logo marcada, sobre la instantánea limpia) el arranque no muestra el logo ni la pantalla de bloqueo.
- [ ] Probar con la cuenta del operador (sin privilegios), si existe: Autoclave guarda datos (por ejemplo, entrar al asistente y avanzar un paso) sin error de permisos.

Mantenimiento (Setup de la misma versión sobre la instalación ya hecha):
- [ ] Aparece la página "Autoclave ya está instalado" con Reparar marcado y las opciones Instalación limpia y Desinstalar (no hay "Reinstalar").
- [ ] Reparar: no pide tareas ni contraseña; `estacion.log` muestra `Setup: Aplicar paso 04/05 ... terminado` (y 02 si estaba); el inicio automático sigue igual; la tarea de arranque existe.
- [ ] Instalación limpia: casos A-N11-02 y A-N11-03 de la hoja de pruebas de banco (`docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`).
- [ ] Desinstalar: se abre el desinstalador (pide confirmación) y el Setup se cierra sin preguntar.
- [ ] Setup de una versión **más vieja** que la instalada: se niega y no cambia nada.

Desinstalar (Configuración › Aplicaciones › Autoclave Especifika › Desinstalar):
- [ ] Muestra "Restaurando la configuración de Windows..." y termina sin mensaje de error; avisa que los datos se conservan.
- [ ] `estacion.log`: líneas `Setup: Revertir paso 05/04/(02)/01 ... terminado`.
- [ ] `reg query HKLM\SOFTWARE\Especifika\Autoclave\Estacion` ya no existe.
- [ ] Winlogon (`AutoAdminLogon`, `DefaultUserName`, `DefaultDomainName`, `DefaultPassword`) quedó como antes de instalar (`DefaultPassword` ya no está si no existía).
- [ ] `powercfg /getactivescheme` es un plan con el nombre del original (GUID nuevo: el modificado sigue en `powercfg /list`, se puede borrar con `powercfg /delete`) y la hibernación volvió a su estado.
- [ ] `schtasks /Query /TN "Especifika Autoclave - Arranque"` dice que no existe.
- [ ] `C:\ProgramData\Especifika\Autoclave` sigue ahí con sus datos.
- [ ] Reiniciar: Windows pide iniciar sesión (ya no entra solo) y Autoclave no se abre solo.

Resultado: ☐ apto para el equipo del autoclave ☐ no apto (anotar qué falló y adjuntar `estacion.log`). Fecha y firma: ________

## Cómo hacer la versión siguiente

1. Compilar la carpeta nueva, verificarla (manifiesto y `tools/verificar_entrega_neutra.py`) y generar su manifiesto.
2. Compilar pasando la versión, sin editar el `.iss`:
   `ISCC.exe /DEntrega=<entrega> /DAppVer=1.0.0-e /DAppVerNum=1.0.0.5 tools\instalador\autoclave.iss`
   (la letra de la compilación es el último número: b = 2, c = 3, d = 4, e = 5), o cambiar los valores por defecto de `AppVer`, `AppVerNum` y `Entrega` en el `.iss`.
3. **No tocar `AppId`.** Calcular el SHA-256 y agregarlo a `SHA256SUMS.txt`.
4. En la estación, el Setup nuevo se ejecuta con doble clic sobre la versión ya instalada. La actualiza en el mismo lugar y conserva los datos de `ProgramData`. Si Autoclave está abierto, el Setup ofrece cerrarlo.

## Lo que el Setup no hace

- Crear la cuenta `operador` (paso 01 con `-Usuario operador` a mano) ni la tarea del script 03 con esa cuenta: decisión de Cristian del 23-oct, el inicio automático es con la cuenta que instala.
- Lo que tampoco hacen los scripts de la estación (AnyDesk, Shell Launcher, BIOS, antivirus...): ver `tools/estacion/LEEME.md`.
