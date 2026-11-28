; Inno Setup 6 script for FlightLink Desktop 1.0 (Windows x64)
; Builds a single-file user-level Windows installer with Desktop/Start Menu shortcuts and clean uninstaller.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#ifndef MyReleaseTag
  #define MyReleaseTag "FlightLinkDesktop-v1.0"
#endif

#define MyAppName "FlightLink Desktop"
#define MyAppPublisher "FlightLink"
#define MyAppExeName "FlightLinkDesktop.exe"

[Setup]
AppId={{7F4D1B82-2C9E-4C19-9A61-0C4E2E7A1001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\release
OutputBaseFilename={#MyReleaseTag}-Setup
SetupIconFile=..\src\flightlink_desktop\assets\flightlink.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
Source: "..\dist\FlightLinkDesktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
