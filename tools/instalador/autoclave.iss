; tools/instalador/autoclave.iss
;
; Setup único (un solo .exe) a partir de una compilación YA HECHA y verificada
; de la carpeta Autoclave\ (build "onedir": Autoclave.exe + _internal\). No
; compila el programa. Cómo compilar, el GUID y cómo hacer la versión
; siguiente: ver tools/instalador/LEEME.md.
;
;   ISCC.exe /DEntrega=<carpeta de la entrega> tools\instalador\autoclave.iss
;
; Reglas (prompt del 22-oct, docs/mis_plans/prompt_claude_code_instalador_usb.md):
;   - instala en {autopf}\Especifika\Autoclave en modo 64 bits: Autoclave.exe
;     solo usa %ProgramData%\Especifika\Autoclave para sus datos si corre bajo
;     %ProgramFiles% (utils/resources.raiz_datos_exe), y solo se reconoce como
;     instalado en esa ruta exacta (instalador_exe.esta_instalado_aqui); en
;     Program Files (x86) volvería a ofrecer instalarse;
;   - Autoclave.exe y _internal\ siempre juntos, con la estructura de la entrega;
;   - NUNCA copia, sobrescribe ni borra archivos en %ProgramData%\Especifika\,
;     salvo la "Instalación limpia" (D11-4, tanda 11), elegida a mano con doble
;     confirmación y con respaldo completo previo en Autoclave_respaldos\.
;     Solo crea la carpeta de datos si falta y le da Modificar a Usuarios (igual
;     que instalador_exe.instalar; decidido con Cristian el 22-oct), porque el
;     programa corre sin administrador. El desinstalador no la toca. (Al
;     actualizar, el propio programa refresca sus archivos de configuración de
;     fábrica, con respaldo: D9-13.1, utils/resources.py.);
;   - no incluye GeneradorCodigos.exe, el perfil de instalación ni data/.
;
; E9 (tanda 9, D9-11): tarea "Configurar este PC como estación del autoclave"
; (marcada) que aplica los pasos 01, 04 y 05 de tools\estacion con la cuenta que
; instala, y tarea aparte "Arranque sin logo" (desmarcada) para el paso 02. Los
; scripts se instalan en {app}\estacion (los necesita el desinstalador, que
; revierte lo que el Setup aplicó). VALIDAR PRIMERO EN UN PC DE PRUEBA: lista de
; verificación en tools/instalador/LEEME.md.
;
; N11 (tanda 11):
;   - D11-4: con una versión instalada igual o más vieja, página de opciones:
;     más vieja = Actualizar (por defecto) / Instalación limpia; misma = Reparar
;     (por defecto) / Instalación limpia / Desinstalar (la limpia ocupa el lugar de la antigua opción de reinstalar).
;     La limpia se confirma dos veces en la página y se hace en
;     PrepareToInstall: respaldo completo y verificado de la carpeta de datos en
;     {commonappdata}\Especifika\Autoclave_respaldos\AAAAMMDD-HHMMSS\ y, solo si
;     el respaldo salió bien, la carpeta de datos se aparta entera con un solo
;     renombrado (atómico) y se borra; vuelve solo estacion\. Si algo falla,
;     el Setup se detiene sin instalar. Más nueva: se sigue negando.
;   - D11-5: subtarea "estacion\tactiles" (marcada, solo con 2 o más monitores):
;     paso 06 de tools\estacion (MultiDigitizer.exe); al terminar cuenta las
;     asociaciones de HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon y, si quedan
;     menos de 2, avisa al final sin fallar. El desinstalador lo revierte.

; Carpeta de la entrega que contiene Autoclave\ (se puede pasar con /DEntrega=...)
#ifndef Entrega
  #define Entrega AddBackslash(SourcePath) + "..\..\entrega\2026-10-23_d"
#endif
#define Programa Entrega + "\Autoclave"
#if !FileExists(Programa + "\Autoclave.exe")
  #error No se encuentra Autoclave.exe en la carpeta de la entrega (definir /DEntrega=...)
#endif

#ifndef AppVer
  #define AppVer "1.0.0-d"
#endif
; VersionInfoVersion exige 4 números: la letra de la compilación es el último
; (b = 2, c = 3, d = 4, ...)
#ifndef AppVerNum
  #define AppVerNum "1.0.0.4"
#endif
; Mismo nombre que tools\estacion\03_tarea_autoclave.ps1: un solo arranque
#define NombreTarea "Especifika Autoclave - Arranque"
; Pasos de la estación aplicados por el Setup (los lee el desinstalador)
#define ClaveEstacion "SOFTWARE\Especifika\Autoclave\Estacion"
; Versión numérica instalada (AppVerNum): la compara el Setup para elegir entre
; mantenimiento (misma), actualizar (la instalada es más vieja) o negarse (la
; instalada es más nueva)
#define ClaveInstalacion "SOFTWARE\Especifika\Autoclave\Instalacion"
; Mismo GUID que AppId, sin la llave escapada: clave de desinstalación de Inno
#define AppGuid "{81C9DAB1-5CF8-4AD2-A7BE-15053E6ED43F}"

[Setup]
; AppId FIJO, generado una vez el 2026-10-22. NO CAMBIAR: es lo que hace que el
; Setup de una versión nueva actualice la instalación anterior en vez de
; instalarse al lado. ({{ escapa la llave de apertura en Inno Setup.)
AppId={{81C9DAB1-5CF8-4AD2-A7BE-15053E6ED43F}
AppName=Autoclave Especifika
AppVersion={#AppVer}
AppVerName=Autoclave Especifika {#AppVer}
AppPublisher=Especifika S.A.S.
VersionInfoVersion={#AppVerNum}
VersionInfoCompany=Especifika S.A.S.
VersionInfoProductName=Autoclave Especifika
VersionInfoProductTextVersion={#AppVer}
DefaultDirName={autopf}\Especifika\Autoclave
; la ruta la fija el programa (ver arriba): no se deja cambiar
DisableDirPage=yes
DefaultGroupName=Autoclave
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=yes
LanguageDetectionMethod=none
UninstallDisplayName=Autoclave Especifika
UninstallDisplayIcon={app}\Autoclave.exe
CloseApplications=yes
RestartApplications=no
OutputDir={#Entrega}
OutputBaseFilename=Autoclave_Setup_{#AppVer}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
; el primero es el predeterminado
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
es.TareaAutoarranque=Iniciar Autoclave automáticamente al iniciar sesión en Windows
en.TareaAutoarranque=Start Autoclave automatically when signing in to Windows
es.CreandoTarea=Creando la tarea de arranque automático...
en.CreandoTarea=Creating the automatic start task...
es.TareaFallo=No se pudo crear la tarea de arranque automático (código %1).%n%nAutoclave quedó instalado. Para el arranque automático ejecute tools\estacion\03_tarea_autoclave.ps1.
en.TareaFallo=The automatic start task could not be created (code %1).%n%nAutoclave was installed. For automatic start run tools\estacion\03_tarea_autoclave.ps1.
es.DatosConservados=Autoclave se desinstaló.%n%nLos datos (perfil de instalación, calibración, base de datos, usuarios) se conservan en:%n%1%n%nNo se borraron.
en.DatosConservados=Autoclave was uninstalled.%n%nThe data (installation profile, calibration, database, users) are kept in:%n%1%n%nThey were not deleted.
es.TareaEstacion=Configurar este PC como estación del autoclave (inicio de sesión automático, sin notificaciones, Windows Update solo avisa y se difiere, sin suspensión)
en.TareaEstacion=Set up this PC as the autoclave station (automatic sign-in, no notifications, Windows Update only notifies and is deferred, no sleep)
es.TareaSinLogo=Arranque sin logo de Windows y sin pantalla de bloqueo
en.TareaSinLogo=Start without the Windows logo and without the lock screen
es.CuentaTitulo=Inicio de sesión automático
en.CuentaTitulo=Automatic sign-in
es.CuentaSubtitulo=Cuenta de Windows con la que el equipo iniciará sesión solo al encenderse.
en.CuentaSubtitulo=Windows account the PC will sign in with by itself when it is switched on.
es.CuentaExplicacion=Es la cuenta con la que se está instalando. La contraseña se guarda en el registro de Windows para el inicio automático. Si la cuenta es de dominio, escriba DOMINIO\usuario.
en.CuentaExplicacion=It is the account used for this installation. The password is stored in the Windows registry for automatic sign-in. For a domain account, type DOMAIN\user.
es.CuentaUsuario=Usuario:
en.CuentaUsuario=User:
es.CuentaClave=Contraseña:
en.CuentaClave=Password:
es.CuentaClaveRepetir=Repita la contraseña:
en.CuentaClaveRepetir=Repeat the password:
es.CuentaFaltaUsuario=Escriba el usuario de Windows.
en.CuentaFaltaUsuario=Type the Windows user.
es.CuentaFaltaClave=Escriba la contraseña de la cuenta. Si la cuenta no tiene contraseña, desmarque "Configurar este PC como estación del autoclave" en la página anterior.
en.CuentaFaltaClave=Type the account password. If the account has no password, clear "Set up this PC as the autoclave station" on the previous page.
es.CuentaClavesDistintas=Las dos contraseñas no coinciden.
en.CuentaClavesDistintas=The two passwords do not match.
es.AplicandoEstacion=Configurando este PC como estación del autoclave...
en.AplicandoEstacion=Setting up this PC as the autoclave station...
es.RevirtiendoEstacion=Restaurando la configuración de Windows anterior a la estación...
en.RevirtiendoEstacion=Restoring the Windows settings from before the station setup...
es.EstacionFallo=Autoclave quedó instalado, pero no se pudo aplicar parte de la configuración de la estación:%n%1%nDetalle en:%n%2
en.EstacionFallo=Autoclave was installed, but part of the station setup could not be applied:%n%1%nDetails in:%n%2
es.EstacionSinClave=No se configuró el inicio de sesión automático: falta la contraseña (instalación sin asistente).
en.EstacionSinClave=Automatic sign-in was not set up: the password is missing (installation without wizard).
es.ReversionFallo=No se pudo restaurar parte de la configuración de Windows:%n%1%nDetalle en:%n%2%n%nRestáurela a mano con los scripts de reversión de tools\estacion (como administrador).
en.ReversionFallo=Part of the Windows settings could not be restored:%n%1%nDetails in:%n%2%n%nRestore it by hand with the reversal scripts in tools\estacion (as administrator).
es.Paso01=inicio de sesión automático (paso 01)
en.Paso01=automatic sign-in (step 01)
es.Paso02=arranque sin logo (paso 02)
en.Paso02=start without logo (step 02)
es.Paso04=notificaciones, Windows Update y gestos de borde (paso 04)
en.Paso04=notifications, Windows Update and edge gestures (step 04)
es.Paso05=plan de energía (paso 05)
en.Paso05=power plan (step 05)
es.Paso06=asociación de las pantallas táctiles (paso 06)
en.Paso06=touch screen association (step 06)
es.TareaTactiles=Asociar cada pantalla táctil con su monitor (pide tocar cada pantalla una vez)
en.TareaTactiles=Associate each touch screen with its monitor (asks to touch each screen once)
es.TactilesRepetir=Repita la asociación de pantallas táctiles: quedaron %1 asociaciones y se necesitan 2.%n%nAutoclave quedó instalado. Para repetirla: Panel de control > Configuración de Tablet PC > Configurar, o ejecute como administrador tools\estacion\06_asociar_tactiles.ps1.
en.TactilesRepetir=Repeat the touch screen association: %1 associations were made and 2 are needed.%n%nAutoclave was installed. To repeat it: Control Panel > Tablet PC Settings > Setup, or run tools\estacion\06_asociar_tactiles.ps1 as administrator.
es.MantTitulo=Autoclave ya está instalado
en.MantTitulo=Autoclave is already installed
es.MantSubtitulo=Está instalada la versión %1. Elija qué hacer.
en.MantSubtitulo=Version %1 is installed. Choose what to do.
es.MantExplicacion=Reparar y Desinstalar conservan los datos (perfil de instalación, calibración, base de datos, usuarios). La instalación limpia los borra, con un respaldo completo previo.
en.MantExplicacion=Repair and Uninstall keep the data (installation profile, calibration, database, users). The clean installation deletes them, after a full backup.
es.MantReparar=Reparar (conserva los datos): vuelve a copiar el programa, recrea la tarea de arranque y vuelve a aplicar la configuración de la estación que ya estaba aplicada (no cambia el inicio de sesión automático)
en.MantReparar=Repair (keeps the data): copies the program again, recreates the start task and re-applies the station settings already applied (automatic sign-in is not changed)
es.MantDesinstalar=Desinstalar: abre el desinstalador y cierra este asistente
en.MantDesinstalar=Uninstall: opens the uninstaller and closes this wizard
es.MantSinDesinstalador=No se encontró el desinstalador de la versión instalada:%n%1
en.MantSinDesinstalador=The uninstaller of the installed version was not found:%n%1
es.ActTitulo=Actualizar Autoclave
en.ActTitulo=Update Autoclave
es.ActSubtitulo=Está instalada la versión %1. Este instalador es la versión %2. Elija cómo instalar.
en.ActSubtitulo=Version %1 is installed. This installer is version %2. Choose how to install.
es.ActExplicacion=Actualizar conserva los datos (perfil de instalación, calibración, base de datos, usuarios). La instalación limpia los borra, con un respaldo completo previo.
en.ActExplicacion=Update keeps the data (installation profile, calibration, database, users). The clean installation deletes them, after a full backup.
es.ActActualizar=Actualizar (conserva los datos)
en.ActActualizar=Update (keeps the data)
es.OpcionLimpia=Instalación limpia: borra todos los datos del equipo (perfil de instalación, calibración, base de datos con los ciclos registrados, usuarios) después de respaldarlos. Al abrir Autoclave se pide de nuevo la instalación del equipo.
en.OpcionLimpia=Clean installation: deletes all the data of the equipment (installation profile, calibration, database with the recorded cycles, users) after backing them up. When Autoclave is opened, the equipment installation is requested again.
es.LimpiaConfirmar1=La instalación limpia borra los datos de:%n%1%n%nAntes se hace un respaldo completo. ¿Desea continuar?
en.LimpiaConfirmar1=The clean installation deletes the data in:%n%1%n%nA full backup is made first. Do you want to continue?
es.LimpiaConfirmar2=SEGUNDA CONFIRMACIÓN%n%nSe borrarán los ciclos registrados, los usuarios, el perfil de instalación y la calibración del equipo. Solo quedará el respaldo en:%n%2%n%n¿Borrar los datos de %1?
en.LimpiaConfirmar2=SECOND CONFIRMATION%n%nThe recorded cycles, the users, the installation profile and the calibration of the equipment will be deleted. Only the backup will remain, in:%n%2%n%nDelete the data in %1?
es.LimpiaProgramaAbierto=Autoclave está abierto. Ciérrelo (Apagar equipo o cerrar sus ventanas) y vuelva a ejecutar este instalador. No se borró nada.
en.LimpiaProgramaAbierto=Autoclave is open. Close it (Shut down equipment or close its windows) and run this installer again. Nothing was deleted.
es.LimpiaRespaldoFallo=No se pudo hacer el respaldo completo de los datos en:%n%1%n%nNo se borró nada y no se instaló. La carpeta de respaldo puede estar incompleta: no la use para restaurar.
en.LimpiaRespaldoFallo=The full backup of the data could not be made in:%n%1%n%nNothing was deleted and nothing was installed. The backup folder may be incomplete: do not use it to restore.
es.LimpiaSilenciosa=La instalación limpia no se puede hacer sin el asistente. No se borró nada.
en.LimpiaSilenciosa=The clean installation cannot be done without the wizard. Nothing was deleted.
es.LimpiaRutaInvalida=La carpeta de datos no tiene la forma esperada:%n%1%n%nNo se borró nada y no se instaló.
en.LimpiaRutaInvalida=The data folder does not have the expected form:%n%1%n%nNothing was deleted and nothing was installed.
es.LimpiaSinComprobar=No se pudo comprobar si Autoclave está abierto. Ciérrelo, reinicie el PC si hace falta y vuelva a ejecutar este instalador. No se borró nada.
en.LimpiaSinComprobar=It could not be checked whether Autoclave is open. Close it, restart the PC if needed and run this installer again. Nothing was deleted.
es.LimpiaEnlace=La carpeta de datos, su carpeta superior o la de respaldos es un enlace o una unión de Windows:%n%1%n%nPor seguridad no se borró nada y no se instaló. Llame a servicio técnico.
en.LimpiaEnlace=The data folder, its parent folder or the backup folder is a Windows link or junction:%n%1%n%nFor safety nothing was deleted and nothing was installed. Call technical service.
es.LimpiaMoverFallo=No se pudieron apartar los datos (algún archivo está abierto). No se borró nada y no se instaló. Cierre los programas que usen la carpeta de datos y vuelva a ejecutar este instalador.
en.LimpiaMoverFallo=The data could not be moved aside (a file is open). Nothing was deleted and nothing was installed. Close the programs using the data folder and run this installer again.
es.LimpiaDeshacerFallo=Los datos quedaron apartados en:%n%1%ny no se pudieron devolver a:%n%2%n%nNo se borró nada y no se instaló. Llame a servicio técnico: para recuperarlos, mueva esa carpeta de vuelta (como administrador).
en.LimpiaDeshacerFallo=The data were moved aside to:%n%1%nand could not be moved back to:%n%2%n%nNothing was deleted and nothing was installed. Call technical service: to recover them, move that folder back (as administrator).
es.VersionDesconocida=No se pudo saber qué versión está instalada (%1). Para instalar esta versión (%2), desinstale primero Autoclave desde Configuración > Aplicaciones.
en.VersionDesconocida=The installed version (%1) could not be determined. To install this version (%2), first uninstall Autoclave from Settings > Apps.
es.TactilesTocar=Asociación de pantallas táctiles: toque cada pantalla cuando se le indique...
en.TactilesTocar=Touch screen association: touch each screen when asked...
es.LimpiaHecha=Instalación limpia: respaldo completo de los datos anteriores en:%n%1
en.LimpiaHecha=Clean installation: full backup of the previous data in:%n%1
es.VersionMasNueva=Está instalada la versión %1, más nueva que la de este instalador (%2).%n%nPara instalar esta versión, desinstale primero Autoclave desde Configuración > Aplicaciones.
en.VersionMasNueva=Version %1 is installed, newer than this installer (%2).%n%nTo install this version, first uninstall Autoclave from Settings > Apps.

[Tasks]
Name: "autoarranque"; Description: "{cm:TareaAutoarranque}"
Name: "estacion"; Description: "{cm:TareaEstacion}"
; D11-5: subtarea de la estación, marcada; solo aparece con 2 o más monitores
Name: "estacion\tactiles"; Description: "{cm:TareaTactiles}"; Check: HayDosMonitores
Name: "sinlogo"; Description: "{cm:TareaSinLogo}"; Flags: unchecked

[InstallDelete]
; al actualizar, _internal\ se reemplaza entero: nunca se mezclan archivos de
; dos compilaciones (mismo criterio que instalador_exe._copiar_programa).
; Solo la carpeta del programa, nunca %ProgramData%.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; D9-11: escritura para la cuenta del operador (sin privilegios). Inno aplica el
; permiso aunque la carpeta ya exista; la subcarpeta estacion\ la protegen los
; propios scripts (solo Administradores y SYSTEM, tools/estacion/_comun.ps1).
Name: "{commonappdata}\Especifika\Autoclave"; Permissions: users-modify; Flags: uninsneveruninstall

[Registry]
Root: HKLM64; Subkey: "{#ClaveInstalacion}"; ValueType: string; ValueName: "VersionNum"; ValueData: "{#AppVerNum}"; Flags: uninsdeletekey

[Files]
Source: "{#Programa}\Autoclave.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Programa}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; solo para crear la tarea; se extrae a {tmp} y se borra al terminar el Setup
Source: "tarea_arranque.ps1"; Flags: dontcopy
; D9-11: scripts de la estación (Archivos de programa: solo administradores los
; cambian). Se instalan siempre: el desinstalador necesita los inversos.
Source: "estacion_setup.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\_comun.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\01_cuenta_autologon.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\01_revertir_cuenta_autologon.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\02_arranque_silencioso.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\02_revertir_arranque_silencioso.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\04_notificaciones_actualizaciones_gestos.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\04_revertir_notificaciones_actualizaciones_gestos.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\05_plan_energia.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\05_revertir_plan_energia.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\06_asociar_tactiles.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion
Source: "..\estacion\06_revertir_asociar_tactiles.ps1"; DestDir: "{app}\estacion"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""{#NombreTarea}"" /F"; Flags: runhidden; RunOnceId: "BorrarTareaArranque"

[Code]
const
  VarClave = 'AUTOCLAVE_CLAVE_AUTOLOGON';
  ClaveDesinstalar = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#AppGuid}_is1';
  // Modo del Setup, fijado en InitializeSetup y por la página de opciones
  ModoNuevo = 0;          // no hay instalación
  ModoActualizar = 1;     // instalada una versión más vieja (silencioso = Actualizar)
  ModoMantenimiento = 2;  // misma versión, todavía sin elegir (silencioso = Reparar)
  ModoReparar = 3;
  ModoLimpia = 4;         // D11-4: respaldo + borrado de datos + asistente completo
  ClaveDigimon = 'SOFTWARE\Microsoft\Wisp\Pen\Digimon';
  SM_CMONITORS = 80;
  // FILE_ATTRIBUTE_REPARSE_POINT y FILE_ATTRIBUTE_DIRECTORY ya los define Inno

var
  PaginaCuenta: TInputQueryWizardPage;
  // D11-4: opciones con versión igual (Reparar/Limpia/Desinstalar) o más vieja (Actualizar/Limpia)
  PaginaOpciones: TInputOptionWizardPage;
  IndiceLimpia, IndiceDesinstalar: Integer;
  ReiniciarAlFinal: Boolean;
  Modo, ModoBase: Integer;
  VersionInstalada: String;
  CerrarSinConfirmar: Boolean;
  CarpetaRespaldo: String;
  // D11-5: -1 = no se corrió el paso 06
  AsociacionesTactiles: Integer;

// La contraseña del inicio automático pasa al script por el entorno del
// proceso (lo hereda powershell.exe), nunca por la línea de comandos.
function SetEnvironmentVariable(lpName: String; lpValue: String): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function GetSystemMetrics(nIndex: Integer): Integer;
  external 'GetSystemMetrics@user32.dll stdcall';

// D11-5: la subtarea de los táctiles solo existe con 2 o más monitores
function HayDosMonitores: Boolean;
begin
  Result := GetSystemMetrics(SM_CMONITORS) >= 2;
end;

// Asociaciones táctil-monitor que guarda Windows (un valor por táctil)
function ContarAsociacionesTactiles: Integer;
var
  Nombres: TArrayOfString;
begin
  Result := 0;
  if RegGetValueNames(HKLM64, ClaveDigimon, Nombres) then
    Result := GetArrayLength(Nombres);
end;

function ArchivoLogEstacion: String;
begin
  Result := ExpandConstant('{commonappdata}\Especifika\Autoclave\estacion\estacion.log');
end;

// Cuenta con la sesión abierta en la consola (DOMINIO\usuario). El Setup corre
// elevado: {username} podría ser el administrador que autorizó el UAC.
function UsuarioConsola: String;
var
  Localizador, Servicio, Resultado, Equipo: Variant;
begin
  Result := '';
  try
    Localizador := CreateOleObject('WbemScripting.SWbemLocator');
    Servicio := Localizador.ConnectServer('.', 'root\CIMV2');
    Resultado := Servicio.ExecQuery('SELECT UserName FROM Win32_ComputerSystem');
    if Resultado.Count > 0 then
    begin
      Equipo := Resultado.ItemIndex(0);
      if not VarIsNull(Equipo.UserName) then
        Result := Equipo.UserName;
    end;
  except
    Result := '';
  end;
  if Result = '' then
    Result := GetComputerNameString + '\' + GetUserNameString;
end;

procedure SepararCuenta(Texto: String; var Dominio, Usuario: String);
var
  P: Integer;
begin
  Texto := Trim(Texto);
  P := Pos('\', Texto);
  if P > 0 then
  begin
    Dominio := Copy(Texto, 1, P - 1);
    Usuario := Copy(Texto, P + 1, Length(Texto));
  end else
  begin
    Dominio := GetComputerNameString;
    Usuario := Texto;
  end;
  if (Dominio = '') or (Dominio = '.') then
    Dominio := GetComputerNameString;
end;

// ── Página de opciones: Reparar / Actualizar / Instalación limpia / Desinstalar

// Primer número de Texto (separado por '.') y lo quita de Texto
function SegmentoVersion(var Texto: String): Integer;
var
  P: Integer;
begin
  P := Pos('.', Texto);
  if P = 0 then
  begin
    Result := StrToIntDef(Texto, 0);
    Texto := '';
  end else
  begin
    Result := StrToIntDef(Copy(Texto, 1, P - 1), 0);
    Delete(Texto, 1, P);
  end;
end;

// < 0 si A es más vieja que B, 0 si iguales, > 0 si más nueva (formato AppVerNum)
function CompararVersiones(A, B: String): Integer;
var
  I, NA, NB: Integer;
begin
  Result := 0;
  for I := 1 to 4 do
  begin
    NA := SegmentoVersion(A);
    NB := SegmentoVersion(B);
    if NA <> NB then
    begin
      Result := NA - NB;
      exit;
    end;
  end;
end;

// AppVer ('1.0.0-d') -> AppVerNum ('1.0.0.4'): la letra es el último número
// (a = 1, b = 2, ...). '' si no tiene esa forma.
function VersionNumDesdeTexto(Texto: String): String;
var
  P: Integer;
  Base, Letra: String;
begin
  Result := '';
  Texto := Lowercase(Trim(Texto));
  P := Pos('-', Texto);
  if P = 0 then
    exit;
  Base := Copy(Texto, 1, P - 1);
  Letra := Copy(Texto, P + 1, Length(Texto));
  if (Length(Letra) <> 1) or (Letra < 'a') or (Letra > 'z') then
    exit;
  if (Base = '') or (Pos('..', Base) > 0) then
    exit;
  Result := Base + '.' + IntToStr(Ord(Letra[1]) - Ord('a') + 1);
end;

function InitializeSetup: Boolean;
var
  VersionNum: String;
  Comparacion: Integer;
begin
  Result := True;
  Modo := ModoNuevo;
  ModoBase := ModoNuevo;
  AsociacionesTactiles := -1;
  VersionInstalada := '';
  if not RegQueryStringValue(HKLM64, ClaveDesinstalar, 'DisplayVersion', VersionInstalada) then
    exit;
  if not RegQueryStringValue(HKLM64, '{#ClaveInstalacion}', 'VersionNum', VersionNum) then
    // instalaciones anteriores a este registro (1.0.0-a .. 1.0.0-d): se
    // compara su DisplayVersion; si no tiene la forma conocida, se niega
    // (nunca se baja de versión a ciegas)
    VersionNum := VersionNumDesdeTexto(VersionInstalada);
  if VersionNum = '' then
  begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('VersionDesconocida'), [VersionInstalada,
      '{#AppVer}']), mbError, MB_OK, IDOK);
    Result := False;
    exit;
  end;
  Comparacion := CompararVersiones(VersionNum, '{#AppVerNum}');
  if Comparacion < 0 then
    Modo := ModoActualizar
  else if Comparacion = 0 then
    Modo := ModoMantenimiento
  else
  begin
    // ISCC toma como sección una línea que empieza con '[': no partir antes del arreglo
    SuppressibleMsgBox(FmtMessage(CustomMessage('VersionMasNueva'), [VersionInstalada,
      '{#AppVer}']), mbError, MB_OK, IDOK);
    Result := False;
  end;
  ModoBase := Modo;
end;

function RutaDesinstalador: String;
begin
  Result := '';
  if RegQueryStringValue(HKLM64, ClaveDesinstalar, 'UninstallString', Result) then
    Result := RemoveQuotes(Result);
  if (Result <> '') and not FileExists(Result) then
  begin
    MsgBox(FmtMessage(CustomMessage('MantSinDesinstalador'), [Result]), mbError, MB_OK);
    Result := '';
  end else if Result = '' then
    MsgBox(FmtMessage(CustomMessage('MantSinDesinstalador'), ['-']), mbError, MB_OK);
end;

// ── Instalación limpia (D11-4) ────────────────────────────────────────────────
//
// Orden (EjecutarLimpia, desde PrepareToInstall; cualquier fallo antes del
// paso 6 deja los datos intactos y detiene el Setup sin instalar):
//   1. nunca sin asistente; ruta de datos con la forma esperada;
//   2. Autoclave cerrado (si no se puede comprobar, se trata como abierto);
//   3. ningún enlace/unión en Especifika\, Autoclave\ ni Autoclave_respaldos\;
//   4. Autoclave_respaldos\ con dueño Administradores y solo Administradores
//      y SYSTEM (contiene la base de usuarios y estacion\);
//   5. copia completa a Autoclave_respaldos\AAAAMMDD-HHMMSS\ y verificación
//      (archivos y bytes del original antes y después, iguales a la copia);
//   6. UN solo renombrado de Autoclave\ entera a
//      Autoclave_respaldos\AAAAMMDD-HHMMSS_borrar\ (misma unidad): atómico,
//      o se mueve todo (perfil incluido) o nada. Falla si hay algo abierto;
//   7. se crea Autoclave\ vacía y se devuelve estacion\ (si falla, se deshace
//      el renombrado y se detiene);
//   8. se borra la carpeta _borrar (sin seguir enlaces). Si algo queda, solo
//      se anota: la carpeta de datos ya está limpia y lo que queda está en la
//      carpeta protegida.
// Tras un corte de energía, ver la tabla del informe N11 (§ Revisión de seguridad).

function GetFileAttributes(lpFileName: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';
function SetFileAttributes(lpFileName: String; dwFileAttributes: Cardinal): BOOL;
  external 'SetFileAttributesW@kernel32.dll stdcall';

function CarpetaDatos: String;
begin
  Result := ExpandConstant('{commonappdata}\Especifika\Autoclave');
end;

// Fuera de la carpeta que se borra
function RaizRespaldos: String;
begin
  Result := ExpandConstant('{commonappdata}\Especifika\Autoclave_respaldos');
end;

// ¿La ruta existe y es un punto de reanálisis (enlace simbólico o unión)?
function EsEnlace(Ruta: String): Boolean;
var
  Atributos: Cardinal;
begin
  Atributos := GetFileAttributes(Ruta);
  Result := (Atributos <> $FFFFFFFF) and ((Atributos and FILE_ATTRIBUTE_REPARSE_POINT) <> 0);
end;

// X:\...\Especifika\Autoclave, sin '..'
function RutaDatosValida(Datos: String): Boolean;
var
  Unidad: String;
begin
  Result := False;
  if Length(Datos) < 24 then
    exit;
  Unidad := Uppercase(Copy(Datos, 1, 1));
  if (Unidad < 'A') or (Unidad > 'Z') or (Copy(Datos, 2, 2) <> ':\') then
    exit;
  if Pos('..', Datos) > 0 then
    exit;
  Result := CompareText(Copy(Datos, Length(Datos) - 20, 21), '\Especifika\Autoclave') = 0;
end;

// ¿Ruta está dentro de Carpeta (o es ella)?
function EstaDentro(Ruta, Carpeta: String): Boolean;
begin
  Result := (CompareText(Ruta, Carpeta) = 0) or
    (Pos(Uppercase(AddBackslash(Carpeta)), Uppercase(Ruta)) = 1);
end;

// Dueño Administradores y solo Administradores y SYSTEM, sin herencia de
// ProgramData (que da lectura a Usuarios; un usuario estándar puede haber
// creado la carpeta antes y ser su dueño). Los archivos copiados heredan.
function ProtegerRespaldos: Boolean;
var
  Codigo: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\icacls.exe'), '"' + RaizRespaldos +
    '" /setowner *S-1-5-32-544 /C /Q', '', SW_HIDE, ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  Log(Format('Instalación limpia: icacls /setowner sobre %s -> código %d', [RaizRespaldos, Codigo]));
  if not Result then
    exit;
  Result := Exec(ExpandConstant('{sys}\icacls.exe'), '"' + RaizRespaldos +
    '" /inheritance:r /grant:r *S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F /C /Q',
    '', SW_HIDE, ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  Log(Format('Instalación limpia: icacls /inheritance:r sobre %s -> código %d', [RaizRespaldos, Codigo]));
end;

// Autoclave_respaldos\AAAAMMDD-HHMMSS (con sufijo si ya existe, también su _borrar)
function NuevaCarpetaRespaldo: String;
var
  Base: String;
  I: Integer;
begin
  Base := RaizRespaldos + '\' + GetDateTimeString('yyyymmdd-hhnnss', '-', ':');
  Result := Base;
  I := 2;
  while DirExists(Result) or FileExists(Result) or DirExists(Result + '_borrar') or
      FileExists(Result + '_borrar') do
  begin
    Result := Base + '_' + IntToStr(I);
    I := I + 1;
  end;
end;

// 0 = cerrado, 1 = abierto, 2 = no se pudo comprobar (se trata como abierto).
// Todas las funciones del exe único (backend, pantallas, asistente) corren
// como Autoclave.exe (exe_unico._cmd_propio); los otros dos nombres son los de
// los .spec separados, por si alguno quedara en el PC.
function EstadoAutoclave: Integer;
var
  Localizador, Servicio, Resultado: Variant;
begin
  Result := 2;
  try
    Localizador := CreateOleObject('WbemScripting.SWbemLocator');
    Servicio := Localizador.ConnectServer('.', 'root\CIMV2');
    Resultado := Servicio.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE ' +
      'Name = ''Autoclave.exe'' OR Name = ''AutoclaveBackend.exe'' OR Name = ''AutoclaveSettings.exe''');
    if Resultado.Count > 0 then
      Result := 1
    else
      Result := 0;
  except
    Log('Instalación limpia: no se pudo consultar WMI por Autoclave.exe: ' + GetExceptionMessage);
    Result := 2;
  end;
end;

// Copia recursiva de Origen en Destino (que no debe existir). False ante
// cualquier error, una carpeta que no se puede listar o un enlace/unión
// (nunca se siguen enlaces fuera de la carpeta de datos).
function CopiarArbol(Origen, Destino: String): Boolean;
var
  Busqueda: TFindRec;
  Hay: Boolean;
begin
  Result := CreateDir(Destino) and not EsEnlace(Destino);
  if not Result then
  begin
    Log('Instalación limpia: no se pudo crear ' + Destino);
    exit;
  end;
  // una carpeta que existe siempre lista al menos '.': False = error
  if not FindFirst(Origen + '\*', Busqueda) then
  begin
    Log('Instalación limpia: no se pudo listar ' + Origen);
    Result := False;
    exit;
  end;
  try
    Hay := True;
    while Hay and Result do
    begin
      if (Busqueda.Name <> '.') and (Busqueda.Name <> '..') then
      begin
        if (Busqueda.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) <> 0 then
        begin
          Log('Instalación limpia: enlace no admitido en los datos: ' + Origen + '\' + Busqueda.Name);
          Result := False;
        end else if (Busqueda.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          Result := CopiarArbol(Origen + '\' + Busqueda.Name, Destino + '\' + Busqueda.Name)
        else
        begin
          Result := CopyFile(Origen + '\' + Busqueda.Name, Destino + '\' + Busqueda.Name, True);
          if not Result then
            Log('Instalación limpia: no se pudo copiar ' + Origen + '\' + Busqueda.Name);
        end;
      end;
      if Result then
        Hay := FindNext(Busqueda);
    end;
  finally
    FindClose(Busqueda);
  end;
end;

// Suma archivos y bytes de un árbol. False si una carpeta no se puede listar
// o hay un enlace. (FindNext no distingue "fin" de "error": un error a mitad
// de una lista se detecta porque los dos conteos del original y el de la
// copia deben coincidir.)
function ContarArbol(Carpeta: String; var Archivos: Integer; var Bytes: Extended): Boolean;
var
  Busqueda: TFindRec;
  Hay: Boolean;
begin
  Result := FindFirst(Carpeta + '\*', Busqueda);
  if not Result then
  begin
    Log('Instalación limpia: no se pudo listar ' + Carpeta);
    exit;
  end;
  try
    Hay := True;
    while Hay and Result do
    begin
      if (Busqueda.Name <> '.') and (Busqueda.Name <> '..') then
      begin
        if (Busqueda.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) <> 0 then
          Result := False
        else if (Busqueda.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          Result := ContarArbol(Carpeta + '\' + Busqueda.Name, Archivos, Bytes)
        else
        begin
          Archivos := Archivos + 1;
          Bytes := Bytes + Busqueda.SizeHigh * 4294967296.0 + Busqueda.SizeLow;
        end;
      end;
      if Result then
        Hay := FindNext(Busqueda);
    end;
  finally
    FindClose(Busqueda);
  end;
end;

// Borra un árbol SIN seguir enlaces: de un enlace/unión se borra solo el
// enlace (RemoveDir/DeleteFile), nunca su destino. True si no quedó nada.
function BorrarArbol(Carpeta: String): Boolean;
var
  Busqueda: TFindRec;
  Hay: Boolean;
  Ruta: String;
begin
  if FindFirst(Carpeta + '\*', Busqueda) then
  try
    Hay := True;
    while Hay do
    begin
      if (Busqueda.Name <> '.') and (Busqueda.Name <> '..') then
      begin
        Ruta := Carpeta + '\' + Busqueda.Name;
        if (Busqueda.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) <> 0 then
        begin
          if (Busqueda.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            RemoveDir(Ruta)
          else
            DeleteFile(Ruta);
        end else if (Busqueda.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          BorrarArbol(Ruta)
        else if not DeleteFile(Ruta) then
        begin
          // solo lectura: se quita el atributo y se reintenta
          SetFileAttributes(Ruta, FILE_ATTRIBUTE_NORMAL);
          DeleteFile(Ruta);
        end;
      end;
      Hay := FindNext(Busqueda);
    end;
  finally
    FindClose(Busqueda);
  end;
  RemoveDir(Carpeta);
  Result := not DirExists(Carpeta);
  if not Result then
    Log('Instalación limpia: no se pudo borrar todo ' + Carpeta);
end;

// Pasos 6 y 7: la carpeta de datos pasa entera, de una vez, a CarpetaBorrar;
// se crea vacía y vuelve estacion\. '' = bien; si no, el mensaje (los datos
// quedan donde estaban, o se informa dónde quedaron si deshacer falla).
function VaciarDatos(Datos, CarpetaBorrar: String): String;
begin
  Result := '';
  if not RenameFile(Datos, CarpetaBorrar) then
  begin
    Log('Instalación limpia: no se pudo mover ' + Datos + ' (¿algo abierto?): no se borró nada.');
    Result := CustomMessage('LimpiaMoverFallo');
    exit;
  end;
  Log('Instalación limpia: ' + Datos + ' movida a ' + CarpetaBorrar);
  if CreateDir(Datos) then
  begin
    if not DirExists(CarpetaBorrar + '\estacion') then
      exit;
    if RenameFile(CarpetaBorrar + '\estacion', Datos + '\estacion') then
      exit;
    Log('Instalación limpia: no se pudo devolver estacion\: se deshace.');
    RemoveDir(Datos);
  end else
    Log('Instalación limpia: no se pudo crear ' + Datos + ' vacía: se deshace.');
  // deshacer: los datos vuelven a su lugar, sin borrar nada
  if RenameFile(CarpetaBorrar, Datos) then
    Result := CustomMessage('LimpiaMoverFallo')
  else
    Result := FmtMessage(CustomMessage('LimpiaDeshacerFallo'), [CarpetaBorrar, Datos]);
end;

// Se llama desde PrepareToInstall: '' = bien; si no, el mensaje con el que el
// Setup se detiene sin instalar.
function EjecutarLimpia: String;
var
  Datos, CarpetaBorrar: String;
  ArchivosAntes, ArchivosCopia, ArchivosDespues: Integer;
  BytesAntes, BytesCopia, BytesDespues: Extended;
  Correcto: Boolean;
begin
  Result := '';
  Datos := CarpetaDatos;
  // 1. Nunca sin asistente (las dos confirmaciones son del técnico)
  if WizardSilent then
  begin
    Result := CustomMessage('LimpiaSilenciosa');
    exit;
  end;
  if not RutaDatosValida(Datos) then
  begin
    Result := FmtMessage(CustomMessage('LimpiaRutaInvalida'), [Datos]);
    exit;
  end;
  // 2. Con el programa abierto (o sin poder comprobarlo) no se toca nada
  case EstadoAutoclave of
    1: begin
         Result := CustomMessage('LimpiaProgramaAbierto');
         exit;
       end;
    2: begin
         Result := CustomMessage('LimpiaSinComprobar');
         exit;
       end;
  end;
  if not DirExists(Datos) then
  begin
    Log('Instalación limpia: no existe ' + Datos + ': nada que respaldar ni borrar.');
    exit;
  end;
  // 3. Sin enlaces en el camino
  if EsEnlace(ExtractFileDir(Datos)) or EsEnlace(Datos) or EsEnlace(RaizRespaldos) then
  begin
    Result := FmtMessage(CustomMessage('LimpiaEnlace'), [Datos]);
    exit;
  end;
  // 4. y 5. Respaldo completo, protegido y verificado (pasos separados: no
  // depender de la evaluación en cortocircuito)
  CarpetaRespaldo := '';
  Correcto := ForceDirectories(RaizRespaldos);
  if Correcto then
    Correcto := not EsEnlace(RaizRespaldos);
  if Correcto then
    Correcto := ProtegerRespaldos;
  if Correcto then
  begin
    CarpetaRespaldo := NuevaCarpetaRespaldo;
    CarpetaBorrar := CarpetaRespaldo + '_borrar';
    Correcto := not EstaDentro(CarpetaRespaldo, Datos) and not EstaDentro(CarpetaBorrar, Datos);
  end;
  ArchivosAntes := 0;
  ArchivosCopia := 0;
  ArchivosDespues := 0;
  BytesAntes := 0;
  BytesCopia := 0;
  BytesDespues := 0;
  if Correcto then
    Correcto := ContarArbol(Datos, ArchivosAntes, BytesAntes);
  if Correcto then
    Correcto := CopiarArbol(Datos, CarpetaRespaldo);
  if Correcto then
    Correcto := ContarArbol(CarpetaRespaldo, ArchivosCopia, BytesCopia);
  if Correcto then
    Correcto := ContarArbol(Datos, ArchivosDespues, BytesDespues);
  // ISCC toma como sección una línea que empieza con '[': no partir antes del arreglo
  Log(Format('Instalación limpia: respaldo en %s (%d archivos; original %d antes y %d después)', [
    CarpetaRespaldo, ArchivosCopia, ArchivosAntes, ArchivosDespues]));
  if Correcto then
    Correcto := (ArchivosAntes = ArchivosCopia) and (ArchivosDespues = ArchivosCopia) and
      (BytesAntes = BytesCopia) and (BytesDespues = BytesCopia);
  if not Correcto then
  begin
    Log('Instalación limpia: respaldo fallido o distinto del original: no se borra nada.');
    Result := FmtMessage(CustomMessage('LimpiaRespaldoFallo'), [CarpetaRespaldo]);
    exit;
  end;
  // 6. y 7. Vaciado atómico (o deshecho)
  Result := VaciarDatos(Datos, CarpetaBorrar);
  if Result <> '' then
    exit;
  // 8. Borrado de lo movido (no es condición: los datos ya están limpios)
  if not BorrarArbol(CarpetaBorrar) then
    Log('Instalación limpia: quedan restos en ' + CarpetaBorrar + ' (carpeta protegida): borrarlos a mano.');
  Log('Instalación limpia: datos borrados de ' + Datos + ' (se conserva estacion\).');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if Modo = ModoLimpia then
    Result := EjecutarLimpia;
end;

// Dos confirmaciones, las dos con "No" por defecto
function ConfirmarLimpia: Boolean;
begin
  Result := False;
  if MsgBox(FmtMessage(CustomMessage('LimpiaConfirmar1'), [CarpetaDatos]), mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2) <> IDYES then
    exit;
  if MsgBox(FmtMessage(CustomMessage('LimpiaConfirmar2'), [CarpetaDatos, RaizRespaldos + '\AAAAMMDD-HHMMSS']),
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) <> IDYES then
    exit;
  Result := True;
end;

// Desinstalar: abre el desinstalador normal (con su confirmación) y cierra el Setup
procedure AbrirDesinstalador;
var
  Desinstalador: String;
  Codigo: Integer;
begin
  Desinstalador := RutaDesinstalador;
  if Desinstalador = '' then
    exit;
  Exec(Desinstalador, '', '', SW_SHOW, ewNoWait, Codigo);
  CerrarSinConfirmar := True;
  WizardForm.Close;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if CerrarSinConfirmar then
    Confirm := False;
end;

procedure InitializeWizard;
begin
  IndiceLimpia := -1;
  IndiceDesinstalar := -1;
  if Modo = ModoMantenimiento then
  begin
    PaginaOpciones := CreateInputOptionPage(wpWelcome, CustomMessage('MantTitulo'),
      FmtMessage(CustomMessage('MantSubtitulo'), [VersionInstalada]),
      CustomMessage('MantExplicacion'), True, False);
    PaginaOpciones.Add(CustomMessage('MantReparar'));
    PaginaOpciones.Add(CustomMessage('OpcionLimpia'));
    PaginaOpciones.Add(CustomMessage('MantDesinstalar'));
    IndiceLimpia := 1;
    IndiceDesinstalar := 2;
    PaginaOpciones.Values[0] := True;
  end else if Modo = ModoActualizar then
  begin
    PaginaOpciones := CreateInputOptionPage(wpWelcome, CustomMessage('ActTitulo'),
      FmtMessage(CustomMessage('ActSubtitulo'), [VersionInstalada, '{#AppVer}']),
      CustomMessage('ActExplicacion'), True, False);
    PaginaOpciones.Add(CustomMessage('ActActualizar'));
    PaginaOpciones.Add(CustomMessage('OpcionLimpia'));
    IndiceLimpia := 1;
    PaginaOpciones.Values[0] := True;
  end;
  PaginaCuenta := CreateInputQueryPage(wpSelectTasks, CustomMessage('CuentaTitulo'),
    CustomMessage('CuentaSubtitulo'), CustomMessage('CuentaExplicacion'));
  PaginaCuenta.Add(CustomMessage('CuentaUsuario'), False);
  PaginaCuenta.Add(CustomMessage('CuentaClave'), True);
  PaginaCuenta.Add(CustomMessage('CuentaClaveRepetir'), True);
  PaginaCuenta.Values[0] := UsuarioConsola;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // la página de opciones nunca se salta: hasta "Instalar" nada está hecho
  if (PaginaOpciones <> nil) and (PageID = PaginaOpciones.ID) then
    Result := False
  // Reparar usa las tareas anteriores (UsePreviousTasks) y no reaplica el paso 01
  else if (Modo = ModoReparar) and ((PageID = wpSelectTasks) or
      ((PaginaCuenta <> nil) and (PageID = PaginaCuenta.ID))) then
    Result := True
  else
    Result := (PaginaCuenta <> nil) and (PageID = PaginaCuenta.ID) and
      not WizardIsTaskSelected('estacion');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Indice: Integer;
begin
  Result := True;
  if (PaginaOpciones <> nil) and (CurPageID = PaginaOpciones.ID) then
  begin
    // se vuelve a decidir cada vez (Atrás y otra opción deshace la anterior)
    Modo := ModoBase;
    if ModoBase = ModoMantenimiento then
      Modo := ModoReparar;
    Indice := PaginaOpciones.SelectedValueIndex;
    if Indice = IndiceLimpia then
    begin
      // Inno también llama a NextButtonClick sin asistente (/SILENT): ahí la
      // limpia nunca se acepta (queda Actualizar o Reparar)
      if WizardSilent then
        Log('Instalación limpia rechazada: instalación sin asistente.')
      else
      begin
        Result := ConfirmarLimpia;
        if Result then
          Modo := ModoLimpia;
      end;
    end else if Indice = IndiceDesinstalar then
    begin
      Result := False;
      AbrirDesinstalador;
    end;
    exit;
  end;
  if (PaginaCuenta <> nil) and (CurPageID = PaginaCuenta.ID) then
  begin
    if Trim(PaginaCuenta.Values[0]) = '' then
    begin
      MsgBox(CustomMessage('CuentaFaltaUsuario'), mbError, MB_OK);
      Result := False;
    end else if PaginaCuenta.Values[1] = '' then
    begin
      MsgBox(CustomMessage('CuentaFaltaClave'), mbError, MB_OK);
      Result := False;
    end else if PaginaCuenta.Values[1] <> PaginaCuenta.Values[2] then
    begin
      MsgBox(CustomMessage('CuentaClavesDistintas'), mbError, MB_OK);
      Result := False;
    end;
  end;
end;

// Ejecuta tools\estacion (instalados en {app}\estacion) a través del puente
// estacion_setup.ps1: 0 = bien.
function EjecutarPaso(Paso, Accion, Extra: String): Boolean;
var
  Codigo: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\estacion\estacion_setup.ps1') + '" -Paso ' + Paso +
    ' -Accion ' + Accion + Extra, '', SW_HIDE, ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  Log(Format('Estación: paso %s (%s) -> código %d', [Paso, Accion, Codigo]));
end;

// Se marca ANTES de aplicar: aunque falle a medias, el desinstalador lo revierte
// (los inversos solo restauran lo que el paso alcanzó a respaldar).
procedure MarcarPaso(Paso: String);
begin
  RegWriteDWordValue(HKLM64, '{#ClaveEstacion}', 'Paso' + Paso, 1);
end;

procedure AplicarEstacion(var Usuario, Dominio: String);
var
  Fallas: String;
begin
  Fallas := '';
  WizardForm.StatusLabel.Caption := CustomMessage('AplicandoEstacion');
  if WizardIsTaskSelected('estacion') then
  begin
    if (PaginaCuenta.Values[1] <> '') and (Trim(PaginaCuenta.Values[0]) <> '') then
    begin
      SepararCuenta(PaginaCuenta.Values[0], Dominio, Usuario);
      MarcarPaso('01');
      SetEnvironmentVariable(VarClave, PaginaCuenta.Values[1]);
      if not EjecutarPaso('01', 'Aplicar', ' -Usuario "' + Usuario + '" -Dominio "' + Dominio + '"') then
        Fallas := Fallas + '- ' + CustomMessage('Paso01') + #13#10;
      SetEnvironmentVariable(VarClave, '');
      ReiniciarAlFinal := True;
    end else
      Fallas := Fallas + '- ' + CustomMessage('EstacionSinClave') + #13#10;
    MarcarPaso('04');
    if not EjecutarPaso('04', 'Aplicar', '') then
      Fallas := Fallas + '- ' + CustomMessage('Paso04') + #13#10;
    MarcarPaso('05');
    if not EjecutarPaso('05', 'Aplicar', '') then
      Fallas := Fallas + '- ' + CustomMessage('Paso05') + #13#10;
    ReiniciarAlFinal := True;
    // D11-5: abre MultiDigitizer.exe (interactivo): nunca sin asistente
    if WizardIsTaskSelected('estacion\tactiles') then
    begin
      if WizardSilent then
        Log('Estación: paso 06 omitido (instalación sin asistente).')
      else
      begin
        MarcarPaso('06');
        WizardForm.StatusLabel.Caption := CustomMessage('TactilesTocar');
        if not EjecutarPaso('06', 'Aplicar', '') then
          Fallas := Fallas + '- ' + CustomMessage('Paso06') + #13#10;
        WizardForm.StatusLabel.Caption := CustomMessage('AplicandoEstacion');
        AsociacionesTactiles := ContarAsociacionesTactiles;
        Log(Format('Estación: asociaciones táctiles en Digimon = %d', [AsociacionesTactiles]));
      end;
    end;
  end;
  if WizardIsTaskSelected('sinlogo') then
  begin
    MarcarPaso('02');
    if not EjecutarPaso('02', 'Aplicar', '') then
      Fallas := Fallas + '- ' + CustomMessage('Paso02') + #13#10;
    ReiniciarAlFinal := True;
  end;
  if Fallas <> '' then
    SuppressibleMsgBox(FmtMessage(CustomMessage('EstacionFallo'), [Fallas, ArchivoLogEstacion]),
      mbError, MB_OK, IDOK);
end;

procedure CrearTareaArranque(Usuario, Dominio: String);
var
  Codigo: Integer;
  ParamUsuario: String;
begin
  WizardForm.StatusLabel.Caption := CustomMessage('CreandoTarea');
  ExtractTemporaryFile('tarea_arranque.ps1');
  ParamUsuario := '';
  // con la estación, la tarea es de la misma cuenta del inicio automático
  if Usuario <> '' then
    ParamUsuario := ' -Usuario "' + Dominio + '\' + Usuario + '"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{tmp}\tarea_arranque.ps1') + '" -Ejecutable "' +
      ExpandConstant('{app}\Autoclave.exe') + '" -NombreTarea "{#NombreTarea}"' + ParamUsuario,
      '', SW_HIDE, ewWaitUntilTerminated, Codigo) or (Codigo <> 0) then
    SuppressibleMsgBox(FmtMessage(CustomMessage('TareaFallo'), [IntToStr(Codigo)]),
      mbError, MB_OK, IDOK);
end;

// Reparar: vuelve a aplicar solo los pasos ya marcados en {#ClaveEstacion}
// (incluye los que fallaron: se marcan antes de aplicarse). Son idempotentes.
procedure ReaplicarPaso(Paso, Nombre: String; var Fallas: String);
begin
  if RegValueExists(HKLM64, '{#ClaveEstacion}', 'Paso' + Paso) then
  begin
    ReiniciarAlFinal := True;
    if not EjecutarPaso(Paso, 'Aplicar', '') then
      Fallas := Fallas + '- ' + CustomMessage(Nombre) + #13#10;
  end;
end;

procedure RepararEstacion;
var
  Fallas, Usuario, Dominio: String;
begin
  Fallas := '';
  Usuario := '';
  Dominio := '';
  WizardForm.StatusLabel.Caption := CustomMessage('AplicandoEstacion');
  // El paso 01 no se reaplica (pide la contraseña): queda como estaba y la
  // tarea de arranque se recrea para la misma cuenta del inicio automático.
  if RegValueExists(HKLM64, '{#ClaveEstacion}', 'Paso01') then
  begin
    RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon',
      'DefaultUserName', Usuario);
    RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon',
      'DefaultDomainName', Dominio);
    if (Dominio = '') or (Dominio = '.') then
      Dominio := GetComputerNameString;
  end;
  ReaplicarPaso('04', 'Paso04', Fallas);
  ReaplicarPaso('05', 'Paso05', Fallas);
  ReaplicarPaso('02', 'Paso02', Fallas);
  // El paso 06 tampoco se reaplica: abre una herramienta que pide tocar las
  // pantallas (y un Setup silencioso quedaría esperando). La asociación ya
  // hecha se conserva; para repetirla: tools\estacion\06_asociar_tactiles.ps1.
  if Fallas <> '' then
    SuppressibleMsgBox(FmtMessage(CustomMessage('EstacionFallo'), [Fallas, ArchivoLogEstacion]),
      mbError, MB_OK, IDOK);
  if WizardIsTaskSelected('autoarranque') then
    CrearTareaArranque(Usuario, Dominio);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Usuario, Dominio: String;
begin
  if CurStep = ssPostInstall then
  begin
    Usuario := '';
    Dominio := '';
    // ModoMantenimiento sin elegir = instalación silenciosa de la misma versión
    if (Modo = ModoReparar) or (Modo = ModoMantenimiento) then
    begin
      RepararEstacion;
      exit;
    end;
    if Modo = ModoLimpia then
      Log(FmtMessage(CustomMessage('LimpiaHecha'), [CarpetaRespaldo]));
    if WizardIsTaskSelected('estacion') or WizardIsTaskSelected('sinlogo') then
      AplicarEstacion(Usuario, Dominio);
    if WizardIsTaskSelected('autoarranque') then
      CrearTareaArranque(Usuario, Dominio);
    // D11-5: aviso al final, sin fallar la instalación
    if (AsociacionesTactiles >= 0) and (AsociacionesTactiles < 2) then
      SuppressibleMsgBox(FmtMessage(CustomMessage('TactilesRepetir'), [IntToStr(AsociacionesTactiles)]),
        mbInformation, MB_OK, IDOK);
  end;
end;

function NeedRestart(): Boolean;
begin
  Result := ReiniciarAlFinal;
end;

// Desinstalación: revierte, en orden inverso, solo los pasos que aplicó el Setup.
function EjecutarReversion(Paso, Nombre: String; var Fallas: String): Boolean;
begin
  Result := True;
  if RegValueExists(HKLM64, '{#ClaveEstacion}', 'Paso' + Paso) then
  begin
    Result := EjecutarPaso(Paso, 'Revertir', '');
    if not Result then
      Fallas := Fallas + '- ' + CustomMessage(Nombre) + #13#10;
  end;
end;

procedure RevertirEstacion;
var
  Fallas: String;
begin
  Fallas := '';
  if not RegKeyExists(HKLM64, '{#ClaveEstacion}') then
    exit;
  UninstallProgressForm.StatusLabel.Caption := CustomMessage('RevirtiendoEstacion');
  EjecutarReversion('06', 'Paso06', Fallas);
  EjecutarReversion('05', 'Paso05', Fallas);
  EjecutarReversion('04', 'Paso04', Fallas);
  EjecutarReversion('02', 'Paso02', Fallas);
  EjecutarReversion('01', 'Paso01', Fallas);
  RegDeleteKeyIncludingSubkeys(HKLM64, '{#ClaveEstacion}');
  RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika\Autoclave');
  RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika');
  if Fallas <> '' then
    SuppressibleMsgBox(FmtMessage(CustomMessage('ReversionFallo'), [Fallas, ArchivoLogEstacion]),
      mbError, MB_OK, IDOK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // usUninstall: antes de borrar archivos ({app}\estacion sigue ahí)
  if CurUninstallStep = usUninstall then
    RevertirEstacion;
  if CurUninstallStep = usPostUninstall then
  begin
    // {#ClaveInstalacion} la borra Inno (uninsdeletekey); quedan los padres vacíos
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika\Autoclave');
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika');
    SuppressibleMsgBox(FmtMessage(CustomMessage('DatosConservados'), [ExpandConstant(
      '{commonappdata}\Especifika\Autoclave')]), mbInformation, MB_OK, IDOK);
  end;
end;
