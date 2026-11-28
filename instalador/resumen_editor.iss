; Instalador de Resumen Editor (App 2). Lo compila GitHub Actions; Jhon solo lo ejecuta.
; Instala sin permisos de administrador en la carpeta del usuario, crea los accesos directos
; y, si falta, descarga e instala Ollama (el cerebro local).

#define Nombre "Resumen Editor"
#ifndef Version
  #define Version "0.1.0"
#endif

[Setup]
AppId={{8C1B2E57-4E8B-4C55-9A2C-5E1D2B7F0A11}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher=Resumen Labs
DefaultDirName={localappdata}\Programs\ResumenEditor
DefaultGroupName={#Nombre}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ResumenEditor-Instalador
Compression=lzma2/ultra64
SolidCompression=yes
DiskSpanning=no
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName={#Nombre}
SetupIconFile=compiler:SetupClassicIcon.ico

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\build\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs ignoreversion
Source: "..\build\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion
Source: "..\build\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: recursesubdirs ignoreversion
Source: "..\build\rhubarb\*"; DestDir: "{app}\rhubarb"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m resumen_editor.lanzador"; WorkingDir: "{app}\app"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m resumen_editor.lanzador"; WorkingDir: "{app}\app"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m resumen_editor.lanzador"; WorkingDir: "{app}\app"; Description: "Abrir {#Nombre}"; Flags: postinstall nowait skipifsilent

[Code]
function OllamaInstalado(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
         or FileExists(ExpandConstant('{pf}\Ollama\ollama.exe'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  { Si la app sigue abierta (corre en segundo plano), se cierra antes de reemplazar sus archivos. }
  Exec('powershell.exe', '-NoProfile -WindowStyle Hidden -Command "Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ''' + ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Sleep(1000);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Codigo: Integer;
begin
  if (CurStep = ssPostInstall) and (not OllamaInstalado()) then
  begin
    WizardForm.StatusLabel.Caption := 'Descargando Ollama (el cerebro de la app)...';
    try
      DownloadTemporaryFile('https://ollama.com/download/OllamaSetup.exe', 'OllamaSetup.exe', '', nil);
      WizardForm.StatusLabel.Caption := 'Instalando Ollama...';
      Exec(ExpandConstant('{tmp}\OllamaSetup.exe'), '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
    except
      MsgBox('No se pudo descargar Ollama. La app te avisará y podrás instalarlo luego desde ollama.com.', mbInformation, MB_OK);
    end;
  end;
end;
