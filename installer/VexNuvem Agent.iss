#define AppName "VexNuvem Agent"
#define AppPublisher "VexNuvem"
#define AppExeName "VexNuvem Agent.exe"

#ifndef AppVersion
	#define AppVersion "1.0.0"
#endif

#ifndef OutputBaseFilename
	#define OutputBaseFilename "VexNuvem-Agent-Setup"
#endif

[Setup]
AppId={{B4CCAC22-416F-4D85-996A-67AE34C36E46}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
WizardStyle=modern
WizardImageFile=..\build_assets\installer_wizard.png
WizardSmallImageFile=..\build_assets\installer_small.png
SetupIconFile=..\build_assets\vexnuvem.ico
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist\installer
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
UsedUserAreasWarning=no
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "..\dist\VexNuvem Agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Executar {#AppName}"; Flags: nowait postinstall skipifsilent