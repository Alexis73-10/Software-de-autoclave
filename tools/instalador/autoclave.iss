; tools/instalador/autoclave.iss
;
; Setup único (un solo .exe) a partir de una compilación YA HECHA y verificada
; de la carpeta Autoclave\ (build "onedir": Autoclave.exe + _internal\). No
; compila el programa. Cómo compilar, el GUID y cómo hacer la versión
; siguiente: ver tools/instalador/LEEME.md.
;
;   ISCC.exe /DEntrega=<carpeta de la entrega> tools\instalador\autoclave.iss
;
; Reglas (prompt del 22-oct, docs/mis_plans/prompt_claude_code_instalador_usb.md,
; y tanda 17, INS-01/INS-02, docs/mis_plans/decisiones_tanda_17.md):
;   - INS-02: disposición única en la unidad fija que se elige en la página
;     "Unidad de instalación" (cualquier unidad, incluso C:):
;       X:\Especifika\Autoclave\programa = {app} (Autoclave.exe y _internal\)
;       X:\Especifika\Autoclave\datos    = perfil, BD, logs, tickets, estacion\...
;     y escribe HKLM64\SOFTWARE\Especifika\Autoclave (RutaPrograma, RutaDatos):
;     con esa clave el programa resuelve su carpeta de datos
;     (utils/resources.raiz_datos_exe) y se reconoce como instalado
;     (instalador_exe.esta_instalado_aqui). Permisos explícitos sin herencia
;     (PrepararCarpetas): programa = Administradores y SYSTEM control total,
;     Usuarios lectura y ejecución; datos = además Usuarios Modificar; si icacls
;     falla, el Setup se detiene sin instalar (falla cerrada). Una instalación
;     con la disposición anterior (Archivos de programa) detiene el Setup: hay
;     que desinstalarla primero (sin migración de datos);
;   - INS-01: página "Zona horaria" (también al actualizar o reparar); se
;     aplica con tzutil /s y se verifica con tzutil /g; /ZONA=<id> sin asistente;
;   - Autoclave.exe y _internal\ siempre juntos, con la estructura de la entrega;
;   - NUNCA copia, sobrescribe ni borra archivos en la carpeta datos, salvo la
;     "Instalación limpia" (D11-4, tanda 11), elegida a mano con doble
;     confirmación y con respaldo completo previo en
;     X:\Especifika\Autoclave_respaldos\. Solo crea la carpeta de datos si
;     falta y fija sus permisos, porque el programa corre sin administrador.
;     El desinstalador no la toca. (Al actualizar, el propio programa refresca
;     sus archivos de configuración de fábrica, con respaldo: D9-13.1,
;     utils/resources.py.);
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
;     X:\Especifika\Autoclave_respaldos\AAAAMMDD-HHMMSS\ y, solo si
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
; INS-02 (tanda 17): clave con RutaPrograma y RutaDatos (vista de 64 bits). Los
; mismos nombres usan utils/resources.py (CLAVE_REGISTRO, VALOR_RUTA_*) y
; tools/estacion/_comun.ps1. Ya tiene las subclaves Instalacion y Estacion.
#define ClaveAutoclave "SOFTWARE\Especifika\Autoclave"

; INS-02: tamaño del programa (Autoclave.exe + _internal\) calculado AL COMPILAR
; recorriendo la carpeta de la entrega (cola de carpetas, sin recursión: ISPP
; no la admite con un solo manejador de búsqueda). En KB redondeados hacia
; arriba por archivo; el espacio libre mínimo es este tamaño + 2 GB.
#define TamKB 0
#define TamCola Programa + "|"
#define TamDir ""
#define TamNombre ""
#define TamH 0
#define TamR 0
#define TamVueltas 0
#sub TamSumarEntrada
  #expr TamNombre = FindGetFileName(TamH)
  #if TamNombre != "." && TamNombre != ".."
    #if DirExists(TamDir + "\" + TamNombre)
      #expr TamCola = TamCola + TamDir + "\" + TamNombre + "|"
    #else
      #expr TamKB = TamKB + FileSize(TamDir + "\" + TamNombre) / 1024 + 1
    #endif
  #endif
#endsub
#sub TamProcesarDir
  #expr TamDir = Copy(TamCola, 1, Pos("|", TamCola) - 1)
  #expr TamCola = Copy(TamCola, Pos("|", TamCola) + 1, Len(TamCola))
  #for {TamH = TamR = FindFirst(TamDir + "\*", faAnyFile); TamR; TamR = FindNext(TamH)} TamSumarEntrada
  #if TamH
    #expr FindClose(TamH)
  #endif
#endsub
#for {TamVueltas = 0; TamCola != "" && TamVueltas < 100000; TamVueltas++} TamProcesarDir
#if TamCola != ""
  #error No se pudo recorrer la carpeta del programa para calcular su tamaño
#endif
#define TamProgramaMB TamKB / 1024 + 1
#pragma message "INS-02: tamaño del programa = " + Str(TamProgramaMB) + " MB"

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
; INS-02 (tanda 17): X:\Especifika\Autoclave\programa, con X la unidad de la
; página "Unidad de instalación" (DirProgramaParam; la página fija además
; WizardForm.DirEdit y PrepareToInstall comprueba que {app} sea esa ruta)
DefaultDirName={code:DirProgramaParam}
; la carpeta no se escribe a mano: solo se elige la unidad en la página propia
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
es.ReversionFallo=No se pudo restaurar parte de la configuración de Windows:%n%1%nDetalle en:%n%2%n%nLos valores originales están en:%n%3%nSe conservan en el registro RutaDatos y los pasos pendientes (HKLM\SOFTWARE\Especifika\Autoclave) para que los scripts de reversión de tools\estacion los encuentren. Restáurela a mano con esos scripts (como administrador).
en.ReversionFallo=Part of the Windows settings could not be restored:%n%1%nDetails in:%n%2%n%nThe original values are in:%n%3%nRutaDatos and the pending steps are kept in the registry (HKLM\SOFTWARE\Especifika\Autoclave) so that the reversal scripts in tools\estacion find them. Restore it by hand with those scripts (as administrator).
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
es.TactilesRepetir=Repita la asociación de pantallas táctiles: quedaron %1 asociaciones y se necesitan 2.%n%nAutoclave quedó instalado. Para repetirla, ejecute como administrador:%n"%2\Autoclave.exe" --rol asociar-tactiles%no el script:%n%2\estacion\06_asociar_tactiles.ps1
en.TactilesRepetir=Repeat the touch screen association: %1 associations were made and 2 are needed.%n%nAutoclave was installed. To repeat it, run as administrator:%n"%2\Autoclave.exe" --rol asociar-tactiles%nor the script:%n%2\estacion\06_asociar_tactiles.ps1
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
; INS-02 (tanda 17): unidad de instalación y disposición
es.UnidadTitulo=Unidad de instalación
en.UnidadTitulo=Installation drive
es.UnidadSubtitulo=Disco donde se instalan el programa y sus datos.
en.UnidadSubtitulo=Disk where the program and its data are installed.
es.UnidadExplicacion=Se crearán X:\Especifika\Autoclave\programa (el programa) y X:\Especifika\Autoclave\datos (perfil, base de datos, registros, tickets). Solo se muestran discos fijos. Se necesitan al menos %1 MB libres. Se recomienda una unidad distinta de la de Windows.
en.UnidadExplicacion=X:\Especifika\Autoclave\programa (the program) and X:\Especifika\Autoclave\datos (profile, database, logs, tickets) will be created. Only fixed disks are shown. At least %1 MB of free space is needed. A drive other than the Windows drive is recommended.
es.UnidadFijaExplicacion=Autoclave ya está instalado en la unidad %1 (%2). La unidad no se puede cambiar al actualizar o reparar; para cambiarla, desinstale Autoclave e instálelo de nuevo.
en.UnidadFijaExplicacion=Autoclave is already installed on drive %1 (%2). The drive cannot be changed when updating or repairing; to change it, uninstall Autoclave and install it again.
es.UnidadElemento=%1  %2  (%3, %4 GB libres)
en.UnidadElemento=%1  %2  (%3, %4 GB free)
es.UnidadSinEtiqueta=Sin etiqueta
en.UnidadSinEtiqueta=No label
es.UnidadSinEspacio=La unidad %1 tiene %2 MB libres y se necesitan %3 MB (programa + 2 GB). Elija otra unidad o libere espacio.
en.UnidadSinEspacio=Drive %1 has %2 MB free and %3 MB are needed (program + 2 GB). Choose another drive or free up space.
es.UnidadSinPermisos=La unidad %1 usa el sistema de archivos %2, que no admite los permisos que protegen el programa. Elija una unidad NTFS.
en.UnidadSinPermisos=Drive %1 uses the %2 file system, which does not support the permissions that protect the program. Choose an NTFS drive.
es.DisposicionAnterior=Hay una instalación de Autoclave con la disposición anterior (en Archivos de programa):%n%1%n%nEsta versión instala el programa y los datos en otra carpeta y no los traslada. Desinstale primero Autoclave desde Configuración > Aplicaciones (los datos anteriores quedan en C:\ProgramData\Especifika\Autoclave) y vuelva a ejecutar este instalador para instalar en limpio.%n%nSi Autoclave no aparece en Aplicaciones, borre esa carpeta como administrador.
en.DisposicionAnterior=There is an Autoclave installation with the previous layout (in Program Files):%n%1%n%nThis version installs the program and the data in another folder and does not move them. First uninstall Autoclave from Settings > Apps (the previous data stay in C:\ProgramData\Especifika\Autoclave) and run this installer again for a clean installation.%n%nIf Autoclave is not listed in Apps, delete that folder as administrator.
es.RegistroInvalido=La instalación anotada en el registro de Windows no tiene la forma esperada:%n%1%n%nNo se instaló nada. Desinstale Autoclave desde Configuración > Aplicaciones y vuelva a ejecutar este instalador.
en.RegistroInvalido=The installation recorded in the Windows registry does not have the expected form:%n%1%n%nNothing was installed. Uninstall Autoclave from Settings > Apps and run this installer again.
es.ProgramaExistente=La carpeta del programa ya existe y no está vacía, pero no hay ninguna instalación anotada:%n%1%n%nPor seguridad no se instaló nada (podría contener archivos ajenos). Bórrela o cámbiele el nombre como administrador y vuelva a ejecutar este instalador.
en.ProgramaExistente=The program folder already exists and is not empty, but no installation is recorded:%n%1%n%nFor safety nothing was installed (it could contain foreign files). Delete or rename it as administrator and run this installer again.
es.CarpetaEnlace=Una carpeta de la instalación es un enlace o una unión de Windows:%n%1%n%nPor seguridad no se instaló nada. Llame a servicio técnico.
en.CarpetaEnlace=An installation folder is a Windows link or junction:%n%1%n%nFor safety nothing was installed. Call technical service.
es.PermisosFallo=No se pudieron fijar los permisos de:%n%1%n%nPor seguridad no se instaló nada: el programa no puede quedar modificable por un usuario sin privilegios. Detalle en el log del instalador.
en.PermisosFallo=The permissions of this folder could not be set:%n%1%n%nFor safety nothing was installed: the program must not be modifiable by a user without privileges. Details in the installer log.
es.CarpetaNoCreada=No se pudo crear la carpeta:%n%1%n%nNo se instaló nada.
en.CarpetaNoCreada=The folder could not be created:%n%1%n%nNothing was installed.
es.RutaInesperada=La carpeta de instalación no es la esperada:%n%1%n(se esperaba %2)%n%nNo se instaló nada.
en.RutaInesperada=The installation folder is not the expected one:%n%1%n(expected %2)%n%nNothing was installed.
es.EstacionNoApartada=Ya existe una carpeta de la estación que no creó este instalador y no se pudo apartar:%n%1%n%nPor seguridad no se instaló nada. Muévala o bórrela como administrador y vuelva a ejecutar este instalador.
en.EstacionNoApartada=A station folder not created by this installer already exists and could not be moved aside:%n%1%n%nFor safety nothing was installed. Move or delete it as administrator and run this installer again.
; INS-01 (tanda 17): zona horaria de Windows
es.ZonaTitulo=Zona horaria
en.ZonaTitulo=Time zone
es.ZonaSubtitulo=Zona horaria de Windows con la que el equipo registra la hora de los ciclos.
en.ZonaSubtitulo=Windows time zone the equipment uses to record the time of the cycles.
es.ZonaExplicacion=Fecha y hora actuales de este PC: %1 (zona actual: %2). La zona elegida se aplica al terminar la instalación. Revise también la hora del PC después de instalar.
en.ZonaExplicacion=Current date and time of this PC: %1 (current zone: %2). The chosen zone is applied when the installation finishes. Also check the PC time after installing.
es.ZonaInvalida=La zona horaria indicada con /ZONA= no existe en este Windows:%n%1%n%nNo se instaló nada. Use el identificador que muestra "tzutil /l" (por ejemplo, SA Pacific Standard Time).
en.ZonaInvalida=The time zone given with /ZONA= does not exist in this Windows:%n%1%n%nNothing was installed. Use the identifier shown by "tzutil /l" (for example, SA Pacific Standard Time).
es.ZonaFallo=No se pudo fijar la zona horaria "%1" (%2).%n%nAutoclave quedó instalado. Fíjela a mano: Configuración > Hora e idioma > Fecha y hora > Zona horaria, o como administrador:%ntzutil /s "%1"
en.ZonaFallo=The time zone "%1" could not be set (%2).%n%nAutoclave was installed. Set it by hand: Settings > Time & language > Date & time > Time zone, or as administrator:%ntzutil /s "%1"

[Tasks]
Name: "autoarranque"; Description: "{cm:TareaAutoarranque}"
Name: "estacion"; Description: "{cm:TareaEstacion}"
; D11-5: subtarea de la estación, marcada; solo aparece con 2 o más monitores
Name: "estacion\tactiles"; Description: "{cm:TareaTactiles}"; Check: HayDosMonitores
Name: "sinlogo"; Description: "{cm:TareaSinLogo}"; Flags: unchecked

[InstallDelete]
; al actualizar, _internal\ se reemplaza entero: nunca se mezclan archivos de
; dos compilaciones (mismo criterio que instalador_exe._copiar_programa).
; Solo la carpeta del programa, nunca la carpeta datos.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; INS-02 (tanda 17): la carpeta datos (X:\Especifika\Autoclave\datos) la crea
; PrepararCarpetas en PrepareToInstall, con permisos explícitos sin herencia
; (Usuarios Modificar: el programa corre sin administrador). Aquí solo se
; declara que el desinstalador nunca la borra. La subcarpeta estacion\ la
; protegen los propios scripts (solo Administradores y SYSTEM, _comun.ps1).
Name: "{code:DatosParam}"; Flags: uninsneveruninstall

[Registry]
Root: HKLM64; Subkey: "{#ClaveInstalacion}"; ValueType: string; ValueName: "VersionNum"; ValueData: "{#AppVerNum}"; Flags: uninsdeletekey
; INS-02 (tanda 17): rutas de la instalación (las lee el programa y
; tools/estacion/_comun.ps1). Solo los valores: la clave tiene además las
; subclaves Instalacion y Estacion. Inno escribe [Registry] antes de
; ssPostInstall, así que los pasos de la estación ya encuentran RutaDatos.
Root: HKLM64; Subkey: "{#ClaveAutoclave}"; ValueType: string; ValueName: "RutaPrograma"; ValueData: "{app}"; Flags: uninsdeletevalue
Root: HKLM64; Subkey: "{#ClaveAutoclave}"; ValueType: string; ValueName: "RutaDatos"; ValueData: "{code:DatosParam}"; Flags: uninsdeletevalue

[Files]
Source: "{#Programa}\Autoclave.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Programa}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; solo para crear la tarea; se extrae a {tmp} y se borra al terminar el Setup
Source: "tarea_arranque.ps1"; Flags: dontcopy
; D9-11: scripts de la estación (en {app}: solo administradores los cambian,
; INS-02). Se instalan siempre: el desinstalador necesita los inversos.
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
  // INS-02 (tanda 17)
  DRIVE_FIXED = 3;
  // tamaño del programa calculado al compilar (ver TamProcesarDir arriba)
  TamProgramaMB = {#TamProgramaMB};
  // espacio libre mínimo de la unidad: programa + 2 GB para los datos
  MinimoMB = {#TamProgramaMB} + 2048;
  // ACL explícitas (SID: el nombre de los grupos cambia con el idioma):
  // Administradores (S-1-5-32-544, BA) y SYSTEM (S-1-5-18, SY) control total;
  // Usuarios (S-1-5-32-545, BU) lectura y ejecución en programa\ y en las
  // carpetas de arriba, Modificar en datos\; datos\estacion\ y los respaldos,
  // solo Administradores y SYSTEM. R1 (V17-s1-01): la DACL se REEMPLAZA entera
  // y protegida (SDDL "D:P", sin herencia y sin ninguna otra entrada explícita,
  // p. ej. un Todos:F que dejara quien creó antes la carpeta) y después se
  // VERIFICA leyéndola (dueño, protegida y exactamente estas entradas).
  // Máscaras: FA = 2032127 (control total), 0x1200a9 = 1179817 (lectura y
  // ejecución), 0x1301bf = 1245631 (modificar); todas (OI)(CI).
  // Forma icacls (paso previo que corta la herencia de inmediato; AplicarAcl
  // reemplaza después la DACL entera y la verifica)
  PermisosPrograma = '*S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F *S-1-5-32-545:(OI)(CI)RX';
  PermisosDatos = '*S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F *S-1-5-32-545:(OI)(CI)M';
  PermisosSoloAdmin = '*S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F';
  SddlPrograma = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)';
  SddlDatos = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1301bf;;;BU)';
  SddlSoloAdmin = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)';
  AclPrograma = 'S-1-5-32-544:2032127;S-1-5-18:2032127;S-1-5-32-545:1179817';
  AclDatos = 'S-1-5-32-544:2032127;S-1-5-18:2032127;S-1-5-32-545:1245631';
  AclSoloAdmin = 'S-1-5-32-544:2032127;S-1-5-18:2032127';
  // INS-02 R1 (V17-s1-04): buses de disco que no se ofrecen aunque Windows
  // diga "fijo" (discos USB externos, lectores de tarjetas)
  BusesExcluidos = '|USB|SD|MMC|';
  // INS-01 (tanda 17)
  ClaveZonas = 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Time Zones';
  ClaveZonaActual = 'SYSTEM\CurrentControlSet\Control\TimeZoneInformation';

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
  // INS-02: unidad de instalación ('D:'); fija si ya hay RutaPrograma
  PaginaUnidad: TInputOptionWizardPage;
  Unidad: String;
  UnidadFija: Boolean;
  UnidadesLetra, UnidadesEtiqueta, UnidadesFS: TArrayOfString;
  UnidadesLibreMB: array of Int64;
  // índice en Unidades* de cada opción de la página
  OpcionesUnidad: array of Integer;
  // INS-01: zonas horarias de Windows ordenadas por desfase
  PaginaZona: TInputOptionWizardPage;
  ZonaIds, ZonaNombres: TArrayOfString;
  ZonaDesfase: array of Integer;
  ZonaActual, ZonaElegida: String;
  // R1 (V17-s1-04): letras de unidades en bus USB/SD/MMC ('EF...'); si la
  // consulta falla, no se excluye ninguna pero solo se preselecciona la del sistema
  LetrasExcluidas: String;
  ConsultaBusFallida: Boolean;
  // R1 (V17-s1-05): desinstalación con alguna reversión fallida
  ReversionFallida: Boolean;
  RutaProgramaDesinstalada, RutaDatosDesinstalada: String;

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

// ── INS-02 (tanda 17): disposición X:\Especifika\Autoclave\{programa,datos} ──

// X:\Especifika\Autoclave. En el desinstalador sale de {app} (= ...\programa);
// en el Setup, de la unidad elegida (la del sistema mientras no hay otra).
function RaizAutoclave: String;
var
  U: String;
begin
  if IsUninstaller then
    Result := ExtractFileDir(RemoveBackslashUnlessRoot(ExpandConstant('{app}')))
  else
  begin
    U := Unidad;
    if U = '' then
      U := ExpandConstant('{sd}');
    Result := U + '\Especifika\Autoclave';
  end;
end;

// {app}: el .exe y _internal\
function DirPrograma: String;
begin
  Result := RaizAutoclave + '\programa';
end;

// Perfil, BD, logs, tickets, estacion\... (antes %ProgramData%\Especifika\Autoclave)
function CarpetaDatos: String;
begin
  Result := RaizAutoclave + '\datos';
end;

// Respaldos de la instalación limpia: X:\Especifika\Autoclave_respaldos, fuera
// de la carpeta que se borra y del árbol de Autoclave (que sí ve Usuarios), en
// la misma unidad (el vaciado es un renombrado atómico)
function RaizRespaldos: String;
begin
  Result := ExtractFileDir(RaizAutoclave) + '\Autoclave_respaldos';
end;

// Para {code:...} en [Setup], [Dirs] y [Registry]
function DirProgramaParam(Param: String): String;
begin
  Result := DirPrograma;
end;

function DatosParam(Param: String): String;
begin
  Result := CarpetaDatos;
end;

function ArchivoLogEstacion: String;
begin
  Result := CarpetaDatos + '\estacion\estacion.log';
end;

function GetDriveType(lpRootPathName: String): Cardinal;
  external 'GetDriveTypeW@kernel32.dll stdcall';
function GetVolumeInformation(lpRootPathName: String; lpVolumeNameBuffer: String;
  nVolumeNameSize: Cardinal; var lpVolumeSerialNumber: Cardinal;
  var lpMaximumComponentLength: Cardinal; var lpFileSystemFlags: Cardinal;
  lpFileSystemNameBuffer: String; nFileSystemNameSize: Cardinal): BOOL;
  external 'GetVolumeInformationW@kernel32.dll stdcall';

// Texto hasta el primer #0 (búfer de la API de Windows)
function HastaNulo(Texto: String): String;
var
  P: Integer;
begin
  P := Pos(#0, Texto);
  if P > 0 then
    Texto := Copy(Texto, 1, P - 1);
  Result := Trim(Texto);
end;

// Agrega una unidad ('D:') con etiqueta, sistema de archivos y MB libres
procedure AgregarUnidad(Letra: String);
var
  Raiz, Etiqueta, Sistema: String;
  Serie, LargoMaximo, Banderas: Cardinal;
  Libre, Total: Int64;
  N: Integer;
begin
  Raiz := Letra + '\';
  Etiqueta := StringOfChar(' ', 261);
  Sistema := StringOfChar(' ', 261);
  if GetVolumeInformation(Raiz, Etiqueta, 261, Serie, LargoMaximo, Banderas, Sistema, 261) then
  begin
    Etiqueta := HastaNulo(Etiqueta);
    Sistema := HastaNulo(Sistema);
  end else
  begin
    Etiqueta := '';
    Sistema := '?';
  end;
  if not GetSpaceOnDisk64(Raiz, Libre, Total) then
    Libre := 0;
  N := GetArrayLength(UnidadesLetra);
  SetArrayLength(UnidadesLetra, N + 1);
  SetArrayLength(UnidadesEtiqueta, N + 1);
  SetArrayLength(UnidadesFS, N + 1);
  SetArrayLength(UnidadesLibreMB, N + 1);
  UnidadesLetra[N] := Letra;
  UnidadesEtiqueta[N] := Etiqueta;
  UnidadesFS[N] := Sistema;
  UnidadesLibreMB[N] := Libre div 1048576;
end;

// R1 (V17-s1-04): un disco USB externo (o un lector de tarjetas) puede decir
// DRIVE_FIXED. Se pregunta el bus de cada partición con letra (Get-Partition y
// Get-Disk, BusType; solo lectura) y se guardan las letras en USB/SD/MMC. Si
// la consulta falla: ConsultaBusFallida (no se excluye ninguna, pero solo se
// preselecciona la unidad del sistema; DECISIÓN SIN CONFIRMAR).
procedure ConsultarBuses;
var
  Codigo, I: Integer;
  Salida: TExecOutput;
  Linea, Letra, Bus: String;
  Correcto: Boolean;
begin
  LetrasExcluidas := '';
  ConsultaBusFallida := True;
  Codigo := -1;
  try
    Correcto := ExecAndCaptureOutput(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$ErrorActionPreference=''Stop''; ' +
      'try { Get-Partition | Where-Object { [string]$_.DriveLetter -match ''^[A-Za-z]$'' } | ' +
      'ForEach-Object { Write-Output (''L='' + [string]$_.DriveLetter + '':'' + ' +
      '[string](Get-Disk -Number $_.DiskNumber).BusType) }; exit 0 } catch { exit 5 }"',
      '', SW_HIDE, ewWaitUntilTerminated, Codigo, Salida) and (Codigo = 0);
  except
    Correcto := False;
    Log('INS-02: no se pudo consultar el bus de los discos: ' + GetExceptionMessage);
  end;
  if not Correcto then
  begin
    Log(Format('INS-02: consulta del bus de los discos fallida (código %d): solo se preselecciona la unidad del sistema', [Codigo]));
    exit;
  end;
  ConsultaBusFallida := False;
  for I := 0 to GetArrayLength(Salida.StdOut) - 1 do
  begin
    Linea := Trim(Salida.StdOut[I]);
    if (Length(Linea) >= 5) and (Copy(Linea, 1, 2) = 'L=') and (Copy(Linea, 4, 1) = ':') then
    begin
      Letra := Uppercase(Copy(Linea, 3, 1));
      Bus := Uppercase(Copy(Linea, 5, Length(Linea)));
      Log('INS-02: unidad ' + Letra + ': bus ' + Bus);
      if Pos('|' + Bus + '|', BusesExcluidos) > 0 then
        LetrasExcluidas := LetrasExcluidas + Letra;
    end;
  end;
end;

// Solo discos fijos: quedan fuera USB, removibles, CD y unidades de red; y
// (R1) los "fijos" en bus USB/SD/MMC
procedure CargarUnidades;
var
  L: Integer;
begin
  ConsultarBuses;
  for L := Ord('A') to Ord('Z') do
    if GetDriveType(Chr(L) + ':\') = DRIVE_FIXED then
    begin
      if Pos(Chr(L), LetrasExcluidas) > 0 then
        Log('INS-02: unidad ' + Chr(L) + ': fija pero en bus USB/SD/MMC: no se ofrece')
      else
        AgregarUnidad(Chr(L) + ':');
    end;
end;

function IndiceUnidad(Letra: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(UnidadesLetra) - 1 do
    if CompareText(UnidadesLetra[I], Letra) = 0 then
    begin
      Result := I;
      exit;
    end;
end;

// '' si la unidad sirve; si no, el mensaje (NTFS o ReFS para las ACL, y espacio)
function ValidarUnidad(I: Integer): String;
begin
  Result := '';
  if (CompareText(UnidadesFS[I], 'NTFS') <> 0) and (CompareText(UnidadesFS[I], 'ReFS') <> 0) then
    Result := FmtMessage(CustomMessage('UnidadSinPermisos'), [UnidadesLetra[I], UnidadesFS[I]])
  else if UnidadesLibreMB[I] < MinimoMB then
    Result := FmtMessage(CustomMessage('UnidadSinEspacio'), [UnidadesLetra[I],
      IntToStr(UnidadesLibreMB[I]), IntToStr(MinimoMB)]);
end;

// Preselección: el primer disco fijo distinto de %SystemDrive% que sirva; si no
// hay, el del sistema. Si no se pudo saber el bus de los discos, siempre el
// del sistema (sin asistente nunca se elige así un disco USB)
procedure PreseleccionarUnidad;
var
  I: Integer;
begin
  Unidad := ExpandConstant('{sd}');
  if ConsultaBusFallida then
    exit;
  for I := 0 to GetArrayLength(UnidadesLetra) - 1 do
    if (CompareText(UnidadesLetra[I], ExpandConstant('{sd}')) <> 0) and (ValidarUnidad(I) = '') then
    begin
      Unidad := UnidadesLetra[I];
      exit;
    end;
end;

function TextoUnidad(I: Integer): String;
var
  Etiqueta: String;
begin
  Etiqueta := UnidadesEtiqueta[I];
  if Etiqueta = '' then
    Etiqueta := CustomMessage('UnidadSinEtiqueta');
  Result := FmtMessage(CustomMessage('UnidadElemento'), [UnidadesLetra[I], Etiqueta,
    UnidadesFS[I], IntToStr(UnidadesLibreMB[I] div 1024)]);
end;

// ── INS-01 (tanda 17): zona horaria ───────────────────────────────────────────

// Desfase en minutos desde el nombre visible: '(UTC-05:00) Bogotá...' -> -300,
// '(UTC) ...' -> 0
function DesfaseZona(Nombre: String): Integer;
var
  Signo: String;
begin
  Result := 0;
  if CompareText(Copy(Nombre, 1, 4), '(UTC') <> 0 then
    exit;
  Signo := Copy(Nombre, 5, 1);
  if (Signo = '+') or (Signo = '-') then
  begin
    Result := StrToIntDef(Copy(Nombre, 6, 2), 0) * 60 + StrToIntDef(Copy(Nombre, 9, 2), 0);
    if Signo = '-' then
      Result := -Result;
  end;
end;

// ¿La zona I va antes que la J? (por desfase y luego por nombre)
function ZonaAntes(I, J: Integer): Boolean;
begin
  if ZonaDesfase[I] <> ZonaDesfase[J] then
    Result := ZonaDesfase[I] < ZonaDesfase[J]
  else
    Result := CompareText(ZonaNombres[I], ZonaNombres[J]) < 0;
end;

procedure IntercambiarZonas(I, J: Integer);
var
  Texto: String;
  Numero: Integer;
begin
  Texto := ZonaIds[I];
  ZonaIds[I] := ZonaIds[J];
  ZonaIds[J] := Texto;
  Texto := ZonaNombres[I];
  ZonaNombres[I] := ZonaNombres[J];
  ZonaNombres[J] := Texto;
  Numero := ZonaDesfase[I];
  ZonaDesfase[I] := ZonaDesfase[J];
  ZonaDesfase[J] := Numero;
end;

// Zonas de HKLM\...\Time Zones (Display = nombre visible) y la zona actual
procedure CargarZonas;
var
  Claves: TArrayOfString;
  I, J, N: Integer;
  Nombre: String;
begin
  ZonaActual := '';
  if RegQueryStringValue(HKLM64, ClaveZonaActual, 'TimeZoneKeyName', ZonaActual) then
    ZonaActual := HastaNulo(ZonaActual);
  if not RegGetSubkeyNames(HKLM64, ClaveZonas, Claves) then
  begin
    Log('Zona horaria: no se pudo leer la lista de zonas de Windows.');
    exit;
  end;
  for I := 0 to GetArrayLength(Claves) - 1 do
    if RegQueryStringValue(HKLM64, ClaveZonas + '\' + Claves[I], 'Display', Nombre) and
        (Trim(Nombre) <> '') then
    begin
      N := GetArrayLength(ZonaIds);
      SetArrayLength(ZonaIds, N + 1);
      SetArrayLength(ZonaNombres, N + 1);
      SetArrayLength(ZonaDesfase, N + 1);
      ZonaIds[N] := Claves[I];
      ZonaNombres[N] := Trim(Nombre);
      ZonaDesfase[N] := DesfaseZona(Trim(Nombre));
    end;
  // inserción (unas 140 zonas)
  for I := 1 to GetArrayLength(ZonaIds) - 1 do
  begin
    J := I;
    while (J > 0) and ZonaAntes(J, J - 1) do
    begin
      IntercambiarZonas(J, J - 1);
      J := J - 1;
    end;
  end;
end;

function IndiceZona(Id: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(ZonaIds) - 1 do
    if CompareText(ZonaIds[I], Trim(Id)) = 0 then
    begin
      Result := I;
      exit;
    end;
end;

function NombreZona(Id: String): String;
var
  I: Integer;
begin
  I := IndiceZona(Id);
  if I >= 0 then
    Result := ZonaNombres[I]
  else
    Result := Id;
end;

function TextoZonaExplicacion: String;
begin
  // ISCC toma como sección una línea que empieza con '[': no partir antes del arreglo
  Result := FmtMessage(CustomMessage('ZonaExplicacion'), [GetDateTimeString('yyyy-mm-dd hh:nn',
    '-', ':'), NombreZona(ZonaActual)]);
end;

// tzutil /g devuelve '<id>_dstoff' si el horario de verano está desactivado
function SinDstOff(Id: String): String;
begin
  Result := Trim(Id);
  if (Length(Result) > 7) and (CompareText(Copy(Result, Length(Result) - 6, 7), '_dstoff') = 0) then
    Result := Copy(Result, 1, Length(Result) - 7);
end;

// ssPostInstall: tzutil /s y comprobación con tzutil /g. Si falla, avisa con el
// procedimiento manual y la instalación sigue (no se aborta).
procedure AplicarZona;
var
  Codigo: Integer;
  Salida: TExecOutput;
  Leida, Detalle: String;
  Correcto: Boolean;
begin
  if ZonaElegida = '' then
  begin
    Log('Zona horaria: ninguna elegida; no se cambia (actual "' + ZonaActual + '").');
    exit;
  end;
  Correcto := Exec(ExpandConstant('{sys}\tzutil.exe'), '/s "' + ZonaElegida + '"', '', SW_HIDE,
    ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  Log(Format('Zona horaria: tzutil /s "%s" -> código %d (antes "%s")', [ZonaElegida, Codigo, ZonaActual]));
  Detalle := 'tzutil /s: ' + IntToStr(Codigo);
  if Correcto then
  begin
    Leida := '';
    try
      Correcto := ExecAndCaptureOutput(ExpandConstant('{sys}\tzutil.exe'), '/g', '', SW_HIDE,
        ewWaitUntilTerminated, Codigo, Salida) and (Codigo = 0);
      if Correcto and (GetArrayLength(Salida.StdOut) > 0) then
        Leida := Trim(Salida.StdOut[0]);
    except
      Correcto := False;
      Log('Zona horaria: no se pudo ejecutar tzutil /g: ' + GetExceptionMessage);
    end;
    Correcto := Correcto and (CompareText(SinDstOff(Leida), ZonaElegida) = 0);
    Log(Format('Zona horaria: tzutil /g -> "%s"', [Leida]));
    Detalle := 'tzutil /g: "' + Leida + '"';
  end;
  if Correcto then
    Log('Zona horaria aplicada y verificada: ' + ZonaElegida + ' (' + NombreZona(ZonaElegida) + ')')
  else
    SuppressibleMsgBox(FmtMessage(CustomMessage('ZonaFallo'), [ZonaElegida, Detalle]),
      mbError, MB_OK, IDOK);
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

// Carpeta de la instalación anotada por Inno en su clave de desinstalación
function RutaInstalacionPrevia: String;
begin
  Result := '';
  if not RegQueryStringValue(HKLM64, ClaveDesinstalar, 'Inno Setup: App Path', Result) then
    RegQueryStringValue(HKLM64, ClaveDesinstalar, 'InstallLocation', Result);
  Result := RemoveBackslashUnlessRoot(Trim(Result));
end;

function InitializeSetup: Boolean;
var
  VersionNum, RutaRegistro, Previa, Anterior, ZonaParametro: String;
  Comparacion: Integer;
  HayInstalacion, TieneRuta: Boolean;
begin
  Result := True;
  Modo := ModoNuevo;
  ModoBase := ModoNuevo;
  AsociacionesTactiles := -1;
  VersionInstalada := '';
  HayInstalacion := RegQueryStringValue(HKLM64, ClaveDesinstalar, 'DisplayVersion', VersionInstalada);
  // INS-02: disposición anterior (Archivos de programa, compilación I o
  // anterior, o una copia de instalador_exe): el Setup se detiene; hay que
  // desinstalarla e instalar en limpio (D-17.2b, sin migración de datos)
  RutaRegistro := '';
  TieneRuta := RegQueryStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaPrograma', RutaRegistro) and
    (Trim(RutaRegistro) <> '');
  RutaRegistro := RemoveBackslashUnlessRoot(Trim(RutaRegistro));
  Anterior := ExpandConstant('{commonpf64}\Especifika\Autoclave');
  if HayInstalacion then
  begin
    Previa := RutaInstalacionPrevia;
    if (not TieneRuta) or (Previa = '') or (CompareText(Previa, RutaRegistro) <> 0) then
    begin
      if Previa = '' then
        Previa := Anterior;
      Log('INS-02: instalación con la disposición anterior en ' + Previa + ': el Setup se detiene.');
      SuppressibleMsgBox(FmtMessage(CustomMessage('DisposicionAnterior'), [Previa]), mbError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
  end;
  if FileExists(Anterior + '\Autoclave.exe') then
  begin
    Log('INS-02: hay un Autoclave.exe en ' + Anterior + ': el Setup se detiene.');
    SuppressibleMsgBox(FmtMessage(CustomMessage('DisposicionAnterior'), [Anterior]), mbError, MB_OK, IDOK);
    Result := False;
    exit;
  end;
  // INS-02: unidad (la de la instalación anotada, sin poder cambiarla)
  CargarUnidades;
  UnidadFija := TieneRuta;
  if UnidadFija then
  begin
    Unidad := ExtractFileDrive(RutaRegistro);
    if (Length(Unidad) <> 2) or
        (CompareText(RutaRegistro, Unidad + '\Especifika\Autoclave\programa') <> 0) then
    begin
      SuppressibleMsgBox(FmtMessage(CustomMessage('RegistroInvalido'), [RutaRegistro]), mbError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
    if IndiceUnidad(Unidad) < 0 then
      AgregarUnidad(Unidad);
  end else
    PreseleccionarUnidad;
  if UnidadFija then
    Log('INS-02: unidad fija (instalación anotada): ' + Unidad)
  else
    Log('INS-02: unidad preseleccionada: ' + Unidad);
  Log(Format('INS-02: programa %d MB, mínimo libre %d MB', [TamProgramaMB, MinimoMB]));
  // INS-01: zona horaria (la actual, o la de /ZONA=<id> si existe en la lista)
  CargarZonas;
  ZonaParametro := Trim(ExpandConstant('{param:ZONA|}'));
  if ZonaParametro <> '' then
  begin
    if IndiceZona(ZonaParametro) < 0 then
    begin
      Log('Zona horaria: /ZONA=' + ZonaParametro + ' no existe en este Windows: el Setup se detiene.');
      SuppressibleMsgBox(FmtMessage(CustomMessage('ZonaInvalida'), [ZonaParametro]), mbError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
    ZonaElegida := ZonaIds[IndiceZona(ZonaParametro)];
  end else if IndiceZona(ZonaActual) >= 0 then
    ZonaElegida := ZonaIds[IndiceZona(ZonaActual)]
  else
    ZonaElegida := '';
  Log('Zona horaria: actual "' + ZonaActual + '", preseleccionada "' + ZonaElegida + '"');
  if not HayInstalacion then
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

// ── INS-02 R1 (V17-s1-01): permisos con verificación ─────────────────────────

// icacls sobre una ruta; True solo con código 0 (sin /C: se detiene en el
// primer error y devuelve distinto de 0)
function Icacls(Ruta, Argumentos: String): Boolean;
var
  Codigo: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\icacls.exe'), '"' + Ruta + '" ' + Argumentos, '', SW_HIDE,
    ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  Log(Format('Permisos: icacls "%s" %s -> código %d', [Ruta, Argumentos, Codigo]));
end;

// True si la carpeta no existe o no tiene nada
function CarpetaVacia(Ruta: String): Boolean;
var
  Busqueda: TFindRec;
  Hay: Boolean;
begin
  Result := True;
  if FindFirst(Ruta + '\*', Busqueda) then
  try
    Hay := True;
    while Hay and Result do
    begin
      if (Busqueda.Name <> '.') and (Busqueda.Name <> '..') then
        Result := False;
      Hay := FindNext(Busqueda);
    end;
  finally
    FindClose(Busqueda);
  end;
end;

// Reemplaza la DACL de la carpeta, de una sola vez, por Sddl (protegida: sin
// herencia y sin ninguna otra entrada explícita) y la VERIFICA leyéndola:
// protegida, dueño Administradores (S-1-5-32-544) y exactamente las entradas
// de Esperado ('SID:máscara;...', permitir, (OI)(CI), explícitas). Las rutas
// y valores pasan por el entorno del proceso (sin comillas en la línea de
// comandos). Se usa SetAccessControl con solo la sección de acceso (Set-Acl
// pediría SeSecurityPrivilege). Cualquier diferencia o error: False.
function AplicarAcl(Ruta, Sddl, Esperado: String): Boolean;
var
  Codigo, I: Integer;
  Salida: TExecOutput;
  Texto: String;
begin
  Codigo := -1;
  Texto := '';
  SetEnvironmentVariable('AUTOCLAVE_ACL_RUTA', Ruta);
  SetEnvironmentVariable('AUTOCLAVE_ACL_SDDL', Sddl);
  SetEnvironmentVariable('AUTOCLAVE_ACL_ESPERADO', Esperado);
  try
    Result := ExecAndCaptureOutput(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$ErrorActionPreference=''Stop''; ' +
      'try { $p=$env:AUTOCLAVE_ACL_RUTA; ' +
      '$s=New-Object System.Security.AccessControl.DirectorySecurity; ' +
      '$s.SetSecurityDescriptorSddlForm($env:AUTOCLAVE_ACL_SDDL, ' +
      '[System.Security.AccessControl.AccessControlSections]::Access); ' +
      '(Get-Item -LiteralPath $p -Force).SetAccessControl($s); ' +
      '$a=Get-Acl -LiteralPath $p; $t=[System.Security.Principal.SecurityIdentifier]; ' +
      '$o=$a.GetOwner($t).Value; ' +
      '$r=@($a.GetAccessRules($true,$true,$t) | ForEach-Object { $_.IdentityReference.Value+'':''+' +
      '[int]$_.FileSystemRights+'':''+[int]$_.AccessControlType+'':''+[int]$_.InheritanceFlags+'':''+' +
      '[int]$_.PropagationFlags+'':''+$_.IsInherited } | Sort-Object); ' +
      '$e=@($env:AUTOCLAVE_ACL_ESPERADO.Split('';'') | ForEach-Object { $_+'':0:3:0:False'' } | Sort-Object); ' +
      'Write-Output (''dueno=''+$o+'' protegida=''+$a.AreAccessRulesProtected+'' reglas=''+($r -join ''|'')); ' +
      'if (-not $a.AreAccessRulesProtected) { exit 2 }; ' +
      'if (($r -join ''|'') -ne ($e -join ''|'')) { exit 4 }; ' +
      'if ($o -ne ''S-1-5-32-544'') { exit 3 }; exit 0 } ' +
      'catch { Write-Output $_.Exception.Message; exit 5 }"',
      '', SW_HIDE, ewWaitUntilTerminated, Codigo, Salida) and (Codigo = 0);
    for I := 0 to GetArrayLength(Salida.StdOut) - 1 do
      Texto := Texto + Salida.StdOut[I] + ' ';
  except
    Result := False;
    Texto := GetExceptionMessage;
  end;
  SetEnvironmentVariable('AUTOCLAVE_ACL_RUTA', '');
  SetEnvironmentVariable('AUTOCLAVE_ACL_SDDL', '');
  SetEnvironmentVariable('AUTOCLAVE_ACL_ESPERADO', '');
  Log(Format('Permisos: DACL %s en "%s" -> código %d: %s', [Sddl, Ruta, Codigo, Texto]));
end;

// Dueño Administradores (icacls /setowner, que usa el privilegio de
// restaurar: también si la carpeta la creó y la cerró un usuario estándar),
// DACL reemplazada y verificada (AplicarAcl) y, con Recursivo, todo lo de
// adentro con dueño Administradores y solo la ACL heredada (/reset /T).
// La raíz de una unidad de datos da crear/modificar a Usuarios autenticados.
function ProtegerCarpeta(Ruta, Permisos, Sddl, Esperado: String; Recursivo: Boolean): Boolean;
begin
  if Recursivo then
    Result := Icacls(Ruta, '/setowner *S-1-5-32-544 /T /Q')
  else
    Result := Icacls(Ruta, '/setowner *S-1-5-32-544 /Q');
  // corta la herencia ya (no quita otras entradas explícitas: eso lo hace AplicarAcl)
  if Result then
    Result := Icacls(Ruta, '/inheritance:r /grant:r ' + Permisos + ' /Q');
  if Result then
    Result := AplicarAcl(Ruta, Sddl, Esperado);
  if Result and Recursivo and not CarpetaVacia(Ruta) then
    Result := Icacls(Ruta + '\*', '/reset /T /Q');
end;

// ── Instalación limpia (D11-4) ────────────────────────────────────────────────
//
// Orden (EjecutarLimpia, desde PrepareToInstall; cualquier fallo antes del
// paso 6 deja los datos intactos y detiene el Setup sin instalar):
//   1. nunca sin asistente; ruta de datos con la forma esperada;
//   2. Autoclave cerrado (si no se puede comprobar, se trata como abierto);
// (INS-02, tanda 17: la carpeta de datos es X:\Especifika\Autoclave\datos y los
// respaldos van a X:\Especifika\Autoclave_respaldos, misma unidad.)
//   3. ningún enlace/unión en Especifika\, Autoclave\, datos\ ni Autoclave_respaldos\;
//   4. Autoclave_respaldos\ con dueño Administradores y solo Administradores
//      y SYSTEM (contiene la base de usuarios y estacion\);
//   5. copia completa a Autoclave_respaldos\AAAAMMDD-HHMMSS\ y verificación
//      (archivos y bytes del original antes y después, iguales a la copia);
//   6. UN solo renombrado de datos\ (X:\Especifika\Autoclave\datos) entera a
//      X:\Especifika\Autoclave_respaldos\AAAAMMDD-HHMMSS_borrar\ (misma
//      unidad): atómico, o se mueve todo (perfil incluido) o nada. Falla si
//      hay algo abierto;
//   7. se crea datos\ vacía y se devuelve estacion\ (si falla, se deshace
//      el renombrado y se detiene); PrepareToInstall le vuelve a fijar sus
//      permisos (ProtegerDatos);
//   8. se borra la carpeta _borrar (sin seguir enlaces). Si algo queda, solo
//      se anota: la carpeta de datos ya está limpia y lo que queda está en la
//      carpeta protegida.
// Tras un corte de energía, ver la tabla del informe N11 (§ Revisión de seguridad).

function GetFileAttributes(lpFileName: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall';
function SetFileAttributes(lpFileName: String; dwFileAttributes: Cardinal): BOOL;
  external 'SetFileAttributesW@kernel32.dll stdcall';

// CarpetaDatos y RaizRespaldos: ver INS-02 arriba (X:\Especifika\Autoclave\datos
// y X:\Especifika\Autoclave_respaldos)

// ¿La ruta existe y es un punto de reanálisis (enlace simbólico o unión)?
function EsEnlace(Ruta: String): Boolean;
var
  Atributos: Cardinal;
begin
  Atributos := GetFileAttributes(Ruta);
  Result := (Atributos <> $FFFFFFFF) and ((Atributos and FILE_ATTRIBUTE_REPARSE_POINT) <> 0);
end;

// INS-02: exactamente X:\Especifika\Autoclave\datos (sin '..' posible)
function RutaDatosValida(Datos: String): Boolean;
var
  Letra: String;
begin
  Result := False;
  Letra := Uppercase(Copy(Datos, 1, 1));
  if (Letra < 'A') or (Letra > 'Z') or (Copy(Datos, 2, 2) <> ':\') then
    exit;
  Result := CompareText(Copy(Datos, 3, Length(Datos)), '\Especifika\Autoclave\datos') = 0;
end;

// ¿Ruta está dentro de Carpeta (o es ella)?
function EstaDentro(Ruta, Carpeta: String): Boolean;
begin
  Result := (CompareText(Ruta, Carpeta) = 0) or
    (Pos(Uppercase(AddBackslash(Carpeta)), Uppercase(Ruta)) = 1);
end;

// Dueño Administradores y solo Administradores y SYSTEM, sin herencia (la de
// X:\Especifika da lectura a Usuarios; un usuario estándar puede haber creado
// la carpeta antes, ser su dueño y dejar entradas propias). R1 (V17-s1-01):
// /setowner *S-1-5-32-544 en todo el árbol, DACL reemplazada entera por
// SddlSoloAdmin y verificada (AplicarAcl) y lo de adentro con la ACL heredada
// (/reset /T). Antes, icacls /inheritance:r corta la herencia de inmediato;
// AplicarAcl quita además cualquier otra entrada explícita. Los archivos
// copiados después heredan.
function ProtegerRespaldos: Boolean;
begin
  Result := Icacls(RaizRespaldos, '/setowner *S-1-5-32-544 /T /Q');
  if Result then
    Result := Icacls(RaizRespaldos, '/inheritance:r /grant:r *S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F /Q');
  if Result then
    Result := AplicarAcl(RaizRespaldos, SddlSoloAdmin, AclSoloAdmin);
  if Result and not CarpetaVacia(RaizRespaldos) then
    Result := Icacls(RaizRespaldos + '\*', '/reset /T /Q');
  if Result then
    Log('Instalación limpia: ' + RaizRespaldos + ' protegida y verificada.')
  else
    Log('Instalación limpia: no se pudo proteger ' + RaizRespaldos + ': no se borra nada.');
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
  if EsEnlace(ExtractFileDir(ExtractFileDir(Datos))) or EsEnlace(ExtractFileDir(Datos)) or
      EsEnlace(Datos) or EsEnlace(RaizRespaldos) then
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

// ── INS-02: carpetas y permisos, ANTES de copiar el programa ─────────────────
// (Icacls, CarpetaVacia, AplicarAcl y ProtegerCarpeta: arriba, antes de la
// instalación limpia, que los usa para Autoclave_respaldos.)

// '' = bien; si no, el mensaje con el que el Setup se detiene sin instalar
function ProtegerDatos: String;
begin
  Result := '';
  if not ProtegerCarpeta(CarpetaDatos, PermisosDatos, SddlDatos, AclDatos, False) then
    Result := FmtMessage(CustomMessage('PermisosFallo'), [CarpetaDatos]);
end;

// R1 (V17-s1-06): datos\estacion solo para Administradores y SYSTEM desde que
// la crea el Setup. En una instalación nueva (sin RutaPrograma), una estacion\
// que ya exista con algo dentro NO la creó este Setup (o es de una
// instalación ya desinstalada): sus respaldo_<paso>.json los restauraría el
// desinstalador como administrador. Se protege y se aparta con su contenido a
// datos\estacion_anterior_AAAAMMDD-HHMMSS (nada se borra; DECISIÓN SIN
// CONFIRMAR) y se crea una vacía. Con la instalación anotada se conserva
// (tiene los respaldos de los pasos ya aplicados) y solo se protege.
function PrepararEstacion: String;
var
  Estacion, Apartada: String;
begin
  Result := '';
  Estacion := CarpetaDatos + '\estacion';
  if EsEnlace(Estacion) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaEnlace'), [Estacion]);
    exit;
  end;
  if (not UnidadFija) and not CarpetaVacia(Estacion) then
  begin
    Apartada := CarpetaDatos + '\estacion_anterior_' + GetDateTimeString('yyyymmdd-hhnnss', '-', ':');
    if not ProtegerCarpeta(Estacion, PermisosSoloAdmin, SddlSoloAdmin, AclSoloAdmin, True) then
    begin
      Result := FmtMessage(CustomMessage('PermisosFallo'), [Estacion]);
      exit;
    end;
    if DirExists(Apartada) or not RenameFile(Estacion, Apartada) then
    begin
      Result := FmtMessage(CustomMessage('EstacionNoApartada'), [Estacion]);
      exit;
    end;
    Log('INS-02: estacion\ preexistente apartada en ' + Apartada);
  end;
  if not ForceDirectories(Estacion) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaNoCreada'), [Estacion]);
    exit;
  end;
  if EsEnlace(Estacion) then
    Result := FmtMessage(CustomMessage('CarpetaEnlace'), [Estacion])
  else if not ProtegerCarpeta(Estacion, PermisosSoloAdmin, SddlSoloAdmin, AclSoloAdmin, True) then
    Result := FmtMessage(CustomMessage('PermisosFallo'), [Estacion]);
end;

function PrepararCarpetas: String;
var
  Especifika, Raiz, Programa, Datos: String;
begin
  Result := '';
  Raiz := RaizAutoclave;
  Especifika := ExtractFileDir(Raiz);
  Programa := DirPrograma;
  Datos := CarpetaDatos;
  // 1. ningún enlace/unión en el camino (icacls y la copia lo seguirían)
  if EsEnlace(Especifika) or EsEnlace(Raiz) or EsEnlace(Programa) or EsEnlace(Datos) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaEnlace'), [Raiz]);
    exit;
  end;
  // 2. crear
  if not ForceDirectories(Programa) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaNoCreada'), [Programa]);
    exit;
  end;
  if not ForceDirectories(Datos) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaNoCreada'), [Datos]);
    exit;
  end;
  if EsEnlace(Especifika) or EsEnlace(Raiz) or EsEnlace(Programa) or EsEnlace(Datos) then
  begin
    Result := FmtMessage(CustomMessage('CarpetaEnlace'), [Raiz]);
    exit;
  end;
  // 3. permisos de arriba abajo, verificados; cualquier fallo detiene el Setup
  // (falla cerrada)
  if not ProtegerCarpeta(Especifika, PermisosPrograma, SddlPrograma, AclPrograma, False) then
    Result := FmtMessage(CustomMessage('PermisosFallo'), [Especifika])
  else if not ProtegerCarpeta(Raiz, PermisosPrograma, SddlPrograma, AclPrograma, False) then
    Result := FmtMessage(CustomMessage('PermisosFallo'), [Raiz])
  else if not ProtegerCarpeta(Programa, PermisosPrograma, SddlPrograma, AclPrograma, True) then
    Result := FmtMessage(CustomMessage('PermisosFallo'), [Programa]);
  if Result <> '' then
    exit;
  // 4. R1 (V17-s1-02): DESPUÉS de proteger (nadie más puede escribir ya ahí),
  // en una instalación nueva (sin RutaPrograma) programa\ debe estar vacía; lo
  // que hubiera (p. ej. una DLL) se cargaría con el programa
  if (not UnidadFija) and not CarpetaVacia(Programa) then
  begin
    Result := FmtMessage(CustomMessage('ProgramaExistente'), [Programa]);
    exit;
  end;
  // 5. datos\ y datos\estacion\
  Result := ProtegerDatos;
  if Result = '' then
    Result := PrepararEstacion;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  I: Integer;
begin
  Result := '';
  // {app} debe ser exactamente X:\Especifika\Autoclave\programa
  if CompareText(RemoveBackslashUnlessRoot(WizardDirValue), DirPrograma) <> 0 then
  begin
    Result := FmtMessage(CustomMessage('RutaInesperada'), [WizardDirValue, DirPrograma]);
    Log('INS-02: ' + Result);
    exit;
  end;
  // la unidad vuelve a validarse (sin asistente no hay página)
  I := IndiceUnidad(Unidad);
  if I < 0 then
    Result := FmtMessage(CustomMessage('CarpetaNoCreada'), [DirPrograma])
  else
    Result := ValidarUnidad(I);
  if Result <> '' then
    exit;
  Result := PrepararCarpetas;
  if Result <> '' then
    exit;
  if Modo = ModoLimpia then
  begin
    Result := EjecutarLimpia;
    if Result <> '' then
      exit;
    // la limpia recrea datos\ vacía (hereda solo lectura): vuelve a sus permisos
    Result := ProtegerDatos;
  end;
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

// INS-02: página "Unidad de instalación" (con la unidad fija, solo esa)
procedure CrearPaginaUnidad(Despues: Integer);
var
  I, N: Integer;
  Explicacion: String;
begin
  if UnidadFija then
    Explicacion := FmtMessage(CustomMessage('UnidadFijaExplicacion'), [Unidad, RaizAutoclave])
  else
    Explicacion := FmtMessage(CustomMessage('UnidadExplicacion'), [IntToStr(MinimoMB)]);
  PaginaUnidad := CreateInputOptionPage(Despues, CustomMessage('UnidadTitulo'),
    CustomMessage('UnidadSubtitulo'), Explicacion, True, True);
  for I := 0 to GetArrayLength(UnidadesLetra) - 1 do
    if (not UnidadFija) or (CompareText(UnidadesLetra[I], Unidad) = 0) then
    begin
      N := PaginaUnidad.Add(TextoUnidad(I));
      SetArrayLength(OpcionesUnidad, N + 1);
      OpcionesUnidad[N] := I;
      if CompareText(UnidadesLetra[I], Unidad) = 0 then
        PaginaUnidad.Values[N] := True;
    end;
end;

// INS-01: página "Zona horaria" (también al actualizar o reparar)
procedure CrearPaginaZona(Despues: Integer);
var
  I: Integer;
begin
  PaginaZona := CreateInputOptionPage(Despues, CustomMessage('ZonaTitulo'),
    CustomMessage('ZonaSubtitulo'), TextoZonaExplicacion, True, True);
  for I := 0 to GetArrayLength(ZonaIds) - 1 do
  begin
    PaginaZona.Add(ZonaNombres[I]);
    if CompareText(ZonaIds[I], ZonaElegida) = 0 then
      PaginaZona.Values[I] := True;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // la hora de referencia, al momento de mostrar la página
  if (PaginaZona <> nil) and (CurPageID = PaginaZona.ID) then
    PaginaZona.SubCaptionLabel.Caption := TextoZonaExplicacion;
end;

procedure InitializeWizard;
var
  Despues: Integer;
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
  // INS-02 e INS-01: después de las opciones (o de la bienvenida)
  Despues := wpWelcome;
  if PaginaOpciones <> nil then
    Despues := PaginaOpciones.ID;
  CrearPaginaUnidad(Despues);
  CrearPaginaZona(PaginaUnidad.ID);
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
  // INS-02: la unidad se muestra siempre (fija al actualizar o reparar)
  else if (PaginaUnidad <> nil) and (PageID = PaginaUnidad.ID) then
    Result := False
  // INS-01: también al actualizar o reparar; sin lista de zonas no hay qué elegir
  else if (PaginaZona <> nil) and (PageID = PaginaZona.ID) then
    Result := GetArrayLength(ZonaIds) = 0
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
  Mensaje: String;
begin
  Result := True;
  // INS-02: unidad elegida (sin asistente, la preseleccionada); fija {app}
  if (PaginaUnidad <> nil) and (CurPageID = PaginaUnidad.ID) then
  begin
    Indice := PaginaUnidad.SelectedValueIndex;
    if Indice < 0 then
    begin
      Result := False;
      exit;
    end;
    Indice := OpcionesUnidad[Indice];
    Mensaje := ValidarUnidad(Indice);
    if Mensaje <> '' then
    begin
      Log('INS-02: ' + Mensaje);
      SuppressibleMsgBox(Mensaje, mbError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
    Unidad := UnidadesLetra[Indice];
    WizardForm.DirEdit.Text := DirPrograma;
    Log('INS-02: unidad de instalación ' + Unidad + ': programa en ' + DirPrograma +
      ', datos en ' + CarpetaDatos);
    exit;
  end;
  // INS-01: zona elegida (sin asistente, la actual o la de /ZONA=)
  if (PaginaZona <> nil) and (CurPageID = PaginaZona.ID) then
  begin
    Indice := PaginaZona.SelectedValueIndex;
    if Indice >= 0 then
      ZonaElegida := ZonaIds[Indice]
    else
      ZonaElegida := '';
    Log('Zona horaria elegida: "' + ZonaElegida + '"');
    exit;
  end;
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
  // hecha se conserva; para repetirla: {app}\Autoclave.exe --rol asociar-tactiles
  // o {app}\estacion\06_asociar_tactiles.ps1, como administrador.
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
    // INS-01: en todos los modos (también Reparar); un fallo solo avisa
    AplicarZona;
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
      // EST-06 (tanda 17): remite a "Autoclave.exe --rol asociar-tactiles" o al script 06
      SuppressibleMsgBox(FmtMessage(CustomMessage('TactilesRepetir'), [IntToStr(AsociacionesTactiles),
        ExpandConstant('{app}')]), mbInformation, MB_OK, IDOK);
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
  // R1 (V17-s1-05): con alguna reversión fallida se conservan los pasos
  // anotados y (en usPostUninstall) RutaDatos/RutaPrograma, para que los
  // scripts de reversión encuentren los respaldos de datos\estacion
  ReversionFallida := Fallas <> '';
  if not ReversionFallida then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM64, '{#ClaveEstacion}');
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika\Autoclave');
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika');
  end;
  if Fallas <> '' then
    SuppressibleMsgBox(FmtMessage(CustomMessage('ReversionFallo'), [Fallas, ArchivoLogEstacion,
      CarpetaDatos + '\estacion']), mbError, MB_OK, IDOK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // usUninstall: antes de borrar archivos ({app}\estacion sigue ahí) y antes
  // de que Inno borre RutaPrograma/RutaDatos (uninsdeletevalue)
  if CurUninstallStep = usUninstall then
  begin
    ReversionFallida := False;
    RutaProgramaDesinstalada := '';
    RutaDatosDesinstalada := '';
    RegQueryStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaPrograma', RutaProgramaDesinstalada);
    RegQueryStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaDatos', RutaDatosDesinstalada);
    RevertirEstacion;
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    // R1 (V17-s1-05): reversión incompleta -> se vuelven a escribir las rutas
    // que Inno acaba de borrar (los scripts y un Setup posterior las usan)
    if ReversionFallida then
    begin
      if RutaDatosDesinstalada <> '' then
        RegWriteStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaDatos', RutaDatosDesinstalada);
      if RutaProgramaDesinstalada <> '' then
        RegWriteStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaPrograma', RutaProgramaDesinstalada);
      Log('Desinstalación: reversión incompleta; se conservan RutaDatos, RutaPrograma y los pasos de la estación.');
    end;
    // {#ClaveInstalacion} la borra Inno (uninsdeletekey); quedan los padres vacíos
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika\Autoclave');
    RegDeleteKeyIfEmpty(HKLM64, 'SOFTWARE\Especifika');
    // INS-02: X:\Especifika\Autoclave\datos (sale de {app}); RutaPrograma y
    // RutaDatos los borra Inno (uninsdeletevalue), salvo lo de arriba
    SuppressibleMsgBox(FmtMessage(CustomMessage('DatosConservados'), [CarpetaDatos]),
      mbInformation, MB_OK, IDOK);
  end;
end;
