#define MyAppName "SpaceMedic"
#define MyAppVersion "3.6.0"
#define MyAppExeName "SpaceMedic.exe"

[Setup]
AppId={{9EBC791F-1A5A-4D65-AB61-4DF5414E3A6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\SpaceMedic
DefaultGroupName=SpaceMedic
OutputDir=dist
OutputBaseFilename=SpaceMedic-Setup-x64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Files]
Source: "dist\SpaceMedic.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "WINDOWS_TEST_CHECKLIST.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "MEMORY_RESEARCH_REVIEW.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CONTRIBUTING.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "SUPPORT.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CODE_OF_CONDUCT.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SpaceMedic"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SpaceMedic"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SpaceMedic"; Flags: nowait postinstall skipifsilent
