#define AppName "PT2VHF Sat Tool"
#define AppVersion "1.8.0"
; v1.7.2: o executavel instalado leva a versao no nome (PT2VHF-Sat-Tool-v1.7.2.exe)
#define AppExe "PT2VHF-Sat-Tool-v" + AppVersion + ".exe"
#ifndef BuildFlavor
  #define BuildFlavor "Win11-x64"
#endif
#ifndef MinTarget
  #define MinTarget "10.0.17763"
#endif
#ifndef TargetArch
  #define TargetArch "x64compatible"
#endif
[Setup]
; Win7/Qt5 and modern Win10/11/Qt6 have separate install identities to prevent overwriting
; an older (legacy Qt5) edition with a Qt6 executable by accident.
#if BuildFlavor == "Win7-x86"
AppId={{733AA8A2-ABBD-41FA-8D26-BDE04044D23B}
#else
AppId={{833AA8A2-ABBD-41FA-8D26-BDE04044D23B}
#endif
#if BuildFlavor == "Win11-x64"
AppName={#AppName} (Windows 10/11 x64)
#else
AppName={#AppName} ({#BuildFlavor})
#endif
AppVersion={#AppVersion}
AppPublisher=PT2VHF
AppPublisherURL=https://www.pt2vhf.com/sat
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
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pak,*.dat,*.bin
RestartApplications=no
AppMutex=PT2VHF_Sat_Tool_Running
[InstallDelete]
; executaveis de versoes anteriores (nome fixo antigo e nomes com versao)
Type: files; Name: "{app}\PT2VHF-Sat-Tool.exe"
Type: files; Name: "{app}\PT2VHF-Sat-Tool-v*.exe"
[Files]
Source: "..\dist\PT2VHF-Sat-Tool\*"; Excludes: "\PT2VHF-Sat-Tool.exe"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\PT2VHF-Sat-Tool\PT2VHF-Sat-Tool.exe"; DestDir: "{app}"; DestName: "{#AppExe}"; Flags: ignoreversion
[Icons]
Name: "{group}\PT2VHF Sat Tool"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\PT2VHF Sat Tool {#BuildFlavor}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"
Name: "rtlsdr"; Description: "Preparar RTL-SDR (instala o driver WinUSB somente na interface 0 do dongle)"; GroupDescription: "Receptor SDR:"
[Run]
Filename: "{app}\_internal\drivers\wdi-simple.exe"; Parameters: "-n ""RTL2832U (PT2VHF Sat Tool)"" -m Realtek -v 0x0BDA -p 0x2838 -i 0 -t 0 -f rtlsdr_2838_pt2vhf.inf -d ""{tmp}\rtlsdr"" --stealth-cert -s -o 60000"; StatusMsg: "Preparando driver do RTL-SDR (WinUSB)..."; Flags: runhidden waituntilterminated skipifdoesntexist; Tasks: rtlsdr; Check: not WizardSilent and not IsOta
Filename: "{app}\_internal\drivers\wdi-simple.exe"; Parameters: "-n ""RTL2832U (PT2VHF Sat Tool)"" -m Realtek -v 0x0BDA -p 0x2832 -i 0 -t 0 -f rtlsdr_2832_pt2vhf.inf -d ""{tmp}\rtlsdr"" --stealth-cert -s -o 60000"; Flags: runhidden waituntilterminated skipifdoesntexist; Tasks: rtlsdr; Check: not WizardSilent and not IsOta
Filename: "{app}\{#AppExe}"; Description: "Executar PT2VHF Sat Tool"; Flags: nowait postinstall skipifsilent
; OTA: o atualizador antigo reabria o caminho do EXE anterior, que agora muda a cada versao; o Setup abre o novo.
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; Check: IsOta
[Code]
// v1.7.1: atualizacao automatica (OTA) passa /OTA; a etapa do driver RTL-SDR nunca roda nela.
function IsOta(): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/OTA') = 0 then
      Result := True;
end;
