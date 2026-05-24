; Скрипт сборки инсталлятора Inno Setup под структуру SPORTGUI
[Setup]
AppName=SportsInventory
AppVerName=SportsInventory v1.0.0
AppVersion=1.0.0
; По умолчанию предлагает установить в Program Files, но пользователь может выбрать любую папку
DefaultDirName={autopf}\SportsInventory
DefaultGroupName=SportsInventory
UninstallDisplayIcon={app}\SportsInventory.exe
OutputDir=.
OutputBaseFilename=SportsInventorySetup
Compression=lzma2
SolidCompression=yes
; Требуются права администратора при установке для безопасной настройки прав на папку
PrivilegesRequired=admin

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
; Настройка прав доступа на изменение папки приложения.
; Это позволит программе создавать новые файлы (логи, базы пользователей) без прав администратора.
Name: "{app}"; Permissions: users-modify

[Files]
; 1. Копируем исполняемый файл и все системные DLL из папки сборки PyInstaller
Source: "dist\SportsInventory\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

; 2. Копируем ваши готовые иконки, темы и языковые файлы из папок проекта
Source: "assets\icons\*"; DestDir: "{app}\assets\icons"; Flags: recursesubdirs createallsubdirs
Source: "local\*"; DestDir: "{app}\local"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SportsInventory"; Filename: "{app}\SportsInventory.exe"
Name: "{autodesktop}\SportsInventory"; Filename: "{app}\SportsInventory.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SportsInventory.exe"; Description: "{cm:LaunchProgram,SportsInventory}"; Flags: nowait postinstall skipifsilent
