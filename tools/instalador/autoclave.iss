; tools/instalador/autoclave.iss
;
; Setup único (un solo .exe) a partir de una compilación YA HECHA y verificada
; de la carpeta Autoclave\ (build "onedir": Autoclave.exe + _internal\). No
; compila el programa. Cómo compilar, el GUID y cómo hacer la versión C: ver
; tools/instalador/LEEME.md.
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
;     programa corre sin administrador. El desinstalador no la toca;
;   - no incluye GeneradorCodigos.exe, el perfil de instalación ni data/.

; Carpeta de la entrega que contiene Autoclave\ (se puede pasar con /DEntrega=...)
#ifndef Entrega
  #define Entrega AddBackslash(SourcePath) + "..\..\entrega\2026-10-22_b"
#endif
#define Programa Entrega + "\Autoclave"
#if !FileExists(Programa + "\Autoclave.exe")
  #error No se encuentra Autoclave.exe en la carpeta de la entrega (definir /DEntrega=...)
#endif

#define AppVer "1.0.0-b"
; VersionInfoVersion exige 4 números: la letra de la compilación es el último
; (b = 2, c = 3, ...)
#define AppVerNum "1.0.0.2"
; Mismo nombre que tools\estacion\03_tarea_autoclave.ps1: un solo arranque
#define NombreTarea "Especifika Autoclave - Arranque"

[Setup]
; AppId FIJO, generado una vez el 2026-10-22. NO CAMBIAR: es lo que hace que el
; Setup de la versión C actualice la instalación de la B en vez de instalarse al
; lado. ({{ escapa la llave de apertura en Inno Setup.)
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

[Tasks]
Name: "autoarranque"; Description: "{cm:TareaAutoarranque}"

[InstallDelete]
; al actualizar, _internal\ se reemplaza entero: nunca se mezclan archivos de
; dos compilaciones (mismo criterio que instalador_exe._copiar_programa).
; Solo la carpeta del programa, nunca %ProgramData%.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
Name: "{commonappdata}\Especifika\Autoclave"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "{#Programa}\Autoclave.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Programa}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; solo para crear la tarea; se extrae a {tmp} y se borra al terminar el Setup
Source: "tarea_arranque.ps1"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Autoclave"; Filename: "{app}\Autoclave.exe"; WorkingDir: "{app}"

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""{#NombreTarea}"" /F"; Flags: runhidden; RunOnceId: "BorrarTareaArranque"

[Code]
procedure CrearTareaArranque;
var
  Codigo: Integer;
begin
  WizardForm.StatusLabel.Caption := CustomMessage('CreandoTarea');
  ExtractTemporaryFile('tarea_arranque.ps1');
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{tmp}\tarea_arranque.ps1') + '" -Ejecutable "' +
      ExpandConstant('{app}\Autoclave.exe') + '" -NombreTarea "{#NombreTarea}"',
      '', SW_HIDE, ewWaitUntilTerminated, Codigo) or (Codigo <> 0) then
    SuppressibleMsgBox(FmtMessage(CustomMessage('TareaFallo'), [IntToStr(Codigo)]),
      mbError, MB_OK, IDOK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('autoarranque') then
    CrearTareaArranque;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    SuppressibleMsgBox(FmtMessage(CustomMessage('DatosConservados'), [ExpandConstant(
      '{commonappdata}\Especifika\Autoclave')]), mbInformation, MB_OK, IDOK);
end;
