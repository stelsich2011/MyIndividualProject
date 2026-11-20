#define AppVersion "0.6.0"
[Setup]
AppId={{5E98F298-9E0D-41C2-B11E-9ADB09F07A75}
AppName=Проверка бланков ОГЭ
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\OGEChecker
DefaultGroupName=Проверка бланков ОГЭ
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=OGEChecker-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\OGEChecker.exe
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; Flags: unchecked

[Files]
Source: "..\dist\windows\OGEChecker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Проверка бланков ОГЭ"; Filename: "{app}\OGEChecker.exe"
Name: "{userdesktop}\Проверка бланков ОГЭ"; Filename: "{app}\OGEChecker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OGEChecker.exe"; Description: "Открыть приложение"; Flags: nowait postinstall skipifsilent
