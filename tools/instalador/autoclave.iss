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
;   - NUNCA copia, sobrescribe ni borra archivos en %ProgramData%\Especifika\.
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

[Tasks]
Name: "autoarranque"; Description: "{cm:TareaAutoarranque}"
Name: "estacion"; Description: "{cm:TareaEstacion}"
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

[Icons]
Name: "{autoprograms}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""{#NombreTarea}"" /F"; Flags: runhidden; RunOnceId: "BorrarTareaArranque"

[Code]
const
  VarClave = 'AUTOCLAVE_CLAVE_AUTOLOGON';

var
  PaginaCuenta: TInputQueryWizardPage;
  ReiniciarAlFinal: Boolean;

// La contraseña del inicio automático pasa al script por el entorno del
// proceso (lo hereda powershell.exe), nunca por la línea de comandos.
function SetEnvironmentVariable(lpName: String; lpValue: String): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

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

procedure InitializeWizard;
begin
  PaginaCuenta := CreateInputQueryPage(wpSelectTasks, CustomMessage('CuentaTitulo'),
    CustomMessage('CuentaSubtitulo'), CustomMessage('CuentaExplicacion'));
  PaginaCuenta.Add(CustomMessage('CuentaUsuario'), False);
  PaginaCuenta.Add(CustomMessage('CuentaClave'), True);
  PaginaCuenta.Add(CustomMessage('CuentaClaveRepetir'), True);
  PaginaCuenta.Values[0] := UsuarioConsola;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PaginaCuenta <> nil) and (PageID = PaginaCuenta.ID) and
    not WizardIsTaskSelected('estacion');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
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

procedure CurStepChanged(CurStep: TSetupStep);
var
  Usuario, Dominio: String;
begin
  if CurStep = ssPostInstall then
  begin
    Usuario := '';
    Dominio := '';
    if WizardIsTaskSelected('estacion') or WizardIsTaskSelected('sinlogo') then
      AplicarEstacion(Usuario, Dominio);
    if WizardIsTaskSelected('autoarranque') then
      CrearTareaArranque(Usuario, Dominio);
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
    SuppressibleMsgBox(FmtMessage(CustomMessage('DatosConservados'), [ExpandConstant(
      '{commonappdata}\Especifika\Autoclave')]), mbInformation, MB_OK, IDOK);
end;
