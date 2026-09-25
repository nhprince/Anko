; Anko installer script — build with Inno Setup (https://jrsoftware.org/isinfo.php)
;
; 1. Build the app first:            pyinstaller anko.spec --noconfirm --clean
;    (this must produce dist\Anko\Anko.exe — the folder build, NOT the one-file build)
; 2. Open this file in Inno Setup Compiler and click Build, or from the command line:
;       "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\anko.iss
; 3. Output: installer\output\AnkoSetup-<version>.exe

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "Anko"
#define MyAppPublisher "Anko"
#define MyAppExeName "Anko.exe"
#define MyAppURL "https://github.com/nhprince/Anko"

[Setup]
AppId={{B7E2B6C2-6B0B-4C7E-9C9E-0B7E6B0B4C7E}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Installs for all users under Program Files; Windows will show one UAC prompt.
; For a no-admin-prompt install instead, change to PrivilegesRequired=lowest and
; DefaultDirName={autopf}\{#MyAppName}  ->  DefaultDirName={userpf}\{#MyAppName}
PrivilegesRequired=admin
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=output
OutputBaseFilename=AnkoSetup-{#MyAppVersion}
SetupIconFile=..\anko\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; pulls in the whole PyInstaller output folder (exe + all its bundled DLLs/Qt plugins)
Source: "..\dist\Anko\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; removes the saved session file on uninstall (comment this out to keep user data)
Type: filesandordirs; Name: "{userappdata}\Anko"
