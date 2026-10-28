; installer.iss — установщик barcodeGen (Inno Setup 6)
;
; Собирается из build_installer.bat, который сначала делает сборку
; PyInstaller в папку dist\barcodeGen\ и передаёт сюда номер версии
; из version.py (/DMyAppVersion=...).
;
; Ставится без прав администратора — в папку пользователя; при желании
; можно выбрать установку для всех. Настройки и история в %APPDATA%
; при удалении программы не трогаются.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "barcodeGen"
#define MyAppExe "barcodeGen.exe"

[Setup]
; AppId не менять: по нему установщик находит прошлую версию для обновления
AppId={{6E3B2C1A-4F7D-4B8E-9C52-1D0A7E5F3B91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Zikizik15
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist\installer
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-setup
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"

[Files]
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent runasoriginaluser
; При обновлении из программы (тихая установка с /UPDATE=1) — запустить её снова
; runasoriginaluser — без прав администратора, даже если установщик их получил
Filename: "{app}\{#MyAppExe}"; Flags: nowait runasoriginaluser; Check: IsUpdate

[Code]
function IsUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;
