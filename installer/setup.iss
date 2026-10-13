#define AppName "PT2VHF Sat Tool"
#define AppVersion "1.1.0"
#ifndef BuildFlavor
  #define BuildFlavor "Win11-x64"
#endif
#ifndef MinTarget
  #define MinTarget "10.0.22000"
#endif
#ifndef TargetArch
  #define TargetArch "x64compatible"
#endif
[Setup]
; Win7 and Win11 have separate install identities to prevent overwriting
; an older (legacy Qt5) edition with a Qt6 executable by accident.
#if BuildFlavor == "Win7-x86"
AppId={{733AA8A2-ABBD-41FA-8D26-BDE04044D23B}
#else
AppId={{833AA8A2-ABBD-41FA-8D26-BDE04044D23B}
#endif
AppName={#AppName} ({#BuildFlavor})
AppVersion={#AppVersion}
AppPublisher=PT2VHF
AppPublisherURL=https://github.com/alexpmr/PT2VHF-Sat-Tool
DefaultDirName={localappdata}\Programs\PT2VHF Sat Tool {#BuildFlavor}
DefaultGroupName=PT2VHF Sat Tool {#BuildFlavor}
OutputDir=..\dist
OutputBaseFilename=PT2VHF-Sat-Tool-v{#AppVersion}-{#BuildFlavor}-Setup
SetupIconFile=..\assets\branding\app-icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed={#TargetArch}
#if BuildFlavor == "Win11-x64"
ArchitecturesInstallIn64BitMode=x64compatible
#endif
MinVersion={#MinTarget}
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\PT2VHF-Sat-Tool.exe
CloseApplications=yes
RestartApplications=no
[Files]
Source: "..\dist\PT2VHF-Sat-Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\PT2VHF Sat Tool"; Filename: "{app}\PT2VHF-Sat-Tool.exe"
Name: "{autodesktop}\PT2VHF Sat Tool {#BuildFlavor}"; Filename: "{app}\PT2VHF-Sat-Tool.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"
[Run]
Filename: "{app}\PT2VHF-Sat-Tool.exe"; Description: "Executar PT2VHF Sat Tool"; Flags: nowait postinstall skipifsilent
