#define MyAppName "Peaceful Poker"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\dist\Peaceful Poker"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist\installer"
#endif
#ifndef MyIconFile
  #define MyIconFile "..\src\poker_trainer\resources\peaceful_poker.ico"
#endif

[Setup]
AppId={{7D832454-8318-4A63-90D9-E1447366E8DF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Peaceful Poker Contributors
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename=Peaceful-Poker-Setup-{#MyAppVersion}
SetupIconFile={#MyIconFile}
UninstallDisplayIcon={app}\Peaceful Poker.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription={#MyAppName} installer

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Peaceful Poker.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Peaceful Poker.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Peaceful Poker.exe"; Description: "Open {#MyAppName}"; Flags: nowait postinstall skipifsilent
