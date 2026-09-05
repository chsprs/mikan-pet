#define MyAppName "Mikan Pet"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.12"
#endif
#ifndef MyArchitecture
  #define MyArchitecture "x64"
#endif
#if MyArchitecture == "arm64"
  #define MyAllowedArchitecture "arm64"
#else
  #define MyAllowedArchitecture "x64compatible"
#endif
#define MyAppPublisher "Mikan Pet"
#define MyAppExeName "MikanPet.exe"
#ifndef MyAppId
  #define MyAppId "{{8BC15C2A-D035-4EE2-A984-39137E4294E1}"
#endif
#ifndef MyOutputBaseFilename
  #if MyArchitecture == "arm64"
    #define MyOutputBaseFilename "MikanPet-Setup-arm64"
  #else
    #define MyOutputBaseFilename "MikanPet-Setup-x64"
  #endif
#endif
#ifndef MySmokeBuild
  #define MySmokeBuild 0
#endif
#ifndef MyAppMutex
  #define MyAppMutex "Local\MikanPet"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Mikan Pet
DefaultGroupName=Mikan Pet
DisableProgramGroupPage=yes
ArchitecturesAllowed={#MyAllowedArchitecture}
ArchitecturesInstallIn64BitMode={#MyAllowedArchitecture}
MinVersion=10.0
PrivilegesRequired=lowest
AppMutex={#MyAppMutex}
OutputDir=..\dist
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile=..\assets\MikanPet.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut tambahan:"; Flags: unchecked

[Files]
Source: "..\dist\MikanPet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

#if Int(MySmokeBuild) == 0
[Icons]
Name: "{group}\Mikan Pet"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Mikan Pet"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan Mikan Pet"; Flags: nowait postinstall skipifsilent
#endif
