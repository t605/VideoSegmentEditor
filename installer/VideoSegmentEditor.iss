; Inno Setup script for the Video Segment Editor Setup program.
; Do not compile this by hand: build_installer.ps1 builds the PyInstaller folder first and
; passes the three defines below.
;   /DAppVer=1.0                     version (same as APP_VER in main.py)
;   /DSourceDir=<folder>             the PyInstaller one-folder output (contains VideoSegmentEditor.exe)
;   /DProjectDir=<folder>            the project folder (LICENSE, README.txt, assets\logo.ico)
;
; What the Setup does:
;   - installs the program for the CURRENT USER only (no administrator rights needed)
;     into %LOCALAPPDATA%\Programs\Video Segment Editor, with Start menu entry (and optional desktop icon)
;   - ONE extra screen lists FFmpeg and VLC when they are missing, with approximate sizes. It has NO
;     tick box and asks no question: it states that after copying the program, Setup installs them
;     with winget, without further questions. (VLC is installed for all users by its own installer:
;     Windows may show one permission window for it; the page says to click Yes.) The page also says
;     that this step can take several minutes and the window may look frozen.
;     Nothing is downloaded when nothing is missing.
;   - without winget the same screen only shows the missing list and the steps to install FFmpeg
;     and VLC by hand (same steps as the launcher). Nothing is installed.
;   - silent installs (/VERYSILENT) ALSO install what is missing, by default. /NOINSTALLMISSING skips
;     that (program only, winget is not run). /INSTALLMISSING=1 is still accepted and changes nothing.
;   - the uninstaller removes the program only. Settings, log and temporary work files in
;     %LOCALAPPDATA%\VideoSegmentEditor stay.
#ifndef AppVer
  #error AppVer is not defined. Build with build_installer.ps1.
#endif
#ifndef SourceDir
  #error SourceDir is not defined. Build with build_installer.ps1.
#endif
#ifndef ProjectDir
  #error ProjectDir is not defined. Build with build_installer.ps1.
#endif

[Setup]
AppId={{6F1D2C8B-3A47-4E59-9B0C-5D7A1E2F8C41}
AppName=Video Segment Editor
AppVersion={#AppVer}
AppVerName=Video Segment Editor {#AppVer}
AppPublisher=Michael Yeruhimovich
DefaultDirName={autopf}\Video Segment Editor
DefaultGroupName=Video Segment Editor
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=VideoSegmentEditor-Setup
SetupIconFile={#ProjectDir}\assets\logo.ico
UninstallDisplayIcon={app}\VideoSegmentEditor.exe
LicenseFile={#ProjectDir}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#ProjectDir}\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Video Segment Editor"; Filename: "{app}\VideoSegmentEditor.exe"; AppUserModelID: "MY.VideoSegmentEditor"
Name: "{autoprograms}\Video Segment Editor - Read me"; Filename: "{app}\README.txt"
Name: "{autodesktop}\Video Segment Editor"; Filename: "{app}\VideoSegmentEditor.exe"; AppUserModelID: "MY.VideoSegmentEditor"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoSegmentEditor.exe"; Description: "Start Video Segment Editor now"; Flags: nowait postinstall skipifsilent

[Code]
var
  InfoPage: TWizardPage;
  NeedFFmpeg: Boolean;
  NeedVLC: Boolean;
  HaveWinget: Boolean;

function FileInPath(const Name: string): Boolean;
begin
  Result := FileSearch(Name, GetEnv('PATH')) <> '';
end;

function BothFFmpegToolsIn(const Dir: string): Boolean;
begin
  Result := FileExists(Dir + '\ffmpeg.exe') and FileExists(Dir + '\ffprobe.exe');
end;

{ Same places the program itself searches: PATH, C:\ffmpeg\bin, Program Files, the winget links
  folder and the winget package folders. }
function HasFFmpeg: Boolean;
var
  Pkgs: string;
  Sub: string;
  R1, R2: TFindRec;
begin
  Result := (FileInPath('ffmpeg.exe') and FileInPath('ffprobe.exe'))
    or BothFFmpegToolsIn('C:\ffmpeg\bin')
    or BothFFmpegToolsIn(ExpandConstant('{commonpf64}') + '\ffmpeg\bin')
    or BothFFmpegToolsIn(ExpandConstant('{commonpf32}') + '\ffmpeg\bin')
    or BothFFmpegToolsIn(ExpandConstant('{localappdata}') + '\Microsoft\WinGet\Links');
  if Result then Exit;
  Pkgs := ExpandConstant('{localappdata}') + '\Microsoft\WinGet\Packages';
  if FindFirst(Pkgs + '\*FFmpeg*', R1) then
  begin
    try
      repeat
        Sub := Pkgs + '\' + R1.Name;
        if BothFFmpegToolsIn(Sub) or BothFFmpegToolsIn(Sub + '\bin') then
          Result := True
        else if FindFirst(Sub + '\*', R2) then
        begin
          try
            repeat
              if BothFFmpegToolsIn(Sub + '\' + R2.Name + '\bin') then Result := True;
            until Result or not FindNext(R2);
          finally
            FindClose(R2);
          end;
        end;
      until Result or not FindNext(R1);
    finally
      FindClose(R1);
    end;
  end;
end;

function HasVLC: Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}') + '\VideoLAN\VLC\libvlc.dll')
    or FileExists(ExpandConstant('{commonpf32}') + '\VideoLAN\VLC\libvlc.dll');
end;

function WingetPath: string;
begin
  Result := ExpandConstant('{localappdata}') + '\Microsoft\WindowsApps\winget.exe';
  if not FileExists(Result) then
  begin
    Result := FileSearch('winget.exe', GetEnv('PATH'));
  end;
end;

function MissingText: string;
begin
  Result := '';
  if NeedFFmpeg then
    Result := Result + '  - FFmpeg: about 100 MB. It creates the new video. Without it the program cannot create videos.' + #13#10;
  if NeedVLC then
    Result := Result + '  - VLC player: about 40 MB. It shows the video preview. Without it you can still type the times by hand.' + #13#10;
end;

{ The by-hand steps: the same wording as in VideoSegmentEditor.bat. }
function FFmpegHandSteps: string;
begin
  Result :=
    'To install FFmpeg by hand (the program cannot create videos without it):' + #13#10 +
    '  1. Open https://www.gyan.dev/ffmpeg/builds/ in your web browser.' + #13#10 +
    '  2. Download the file ffmpeg-release-essentials.zip.' + #13#10 +
    '  3. Unzip it. Inside the unzipped folder there is a folder named bin.' + #13#10 +
    '  4. Create a folder named C:\ffmpeg' + #13#10 +
    '  5. Copy the bin folder from the unzipped folder into C:\ffmpeg' + #13#10 +
    '     (afterwards C:\ffmpeg\bin contains ffmpeg.exe and ffprobe.exe).' + #13#10 +
    '  6. Start the program again.' + #13#10 +
    'Or, if winget works on this computer, use the Command Prompt instead:' + #13#10 +
    '  1. Press the Windows key, type cmd and press Enter.' + #13#10 +
    '  2. In the Command Prompt window type this line and press Enter:' + #13#10 +
    '       winget install Gyan.FFmpeg' + #13#10 +
    '  3. When it has finished, start the program again.' + #13#10;
end;

function VLCHandSteps: string;
begin
  Result :=
    'To install VLC by hand (without it there is no video preview):' + #13#10 +
    '  Download it from https://www.videolan.org/vlc/ and run the installer.' + #13#10 +
    '  You can still type the start and end times by hand without VLC.' + #13#10;
end;

function HandSteps: string;
begin
  Result := '';
  if NeedFFmpeg then Result := Result + FFmpegHandSteps + #13#10;
  if NeedVLC then Result := Result + VLCHandSteps + #13#10;
end;

{ True when the command line has the switch /Name or /Name=value (any case). }
function SwitchGiven(const Name: string): Boolean;
var
  I: Integer;
  P: string;
begin
  Result := False;
  for I := 1 to ParamCount do
  begin
    P := Uppercase(ParamStr(I));
    if (P = '/' + Uppercase(Name)) or (Pos('/' + Uppercase(Name) + '=', P) = 1) then
      Result := True;
  end;
end;

procedure InitializeWizard;
var
  Memo: TNewMemo;
  VlcNote: string;
begin
  NeedFFmpeg := not HasFFmpeg;
  NeedVLC := not HasVLC;
  HaveWinget := WingetPath <> '';
  if not (NeedFFmpeg or NeedVLC) then Exit;

  { One read-only text page, no tick box and no question. }
  InfoPage := CreateCustomPage(wpSelectTasks,
    'Programs the editor needs',
    'These free programs are not installed on this computer yet.');
  Memo := TNewMemo.Create(InfoPage);
  Memo.Parent := InfoPage.Surface;
  Memo.Left := 0;
  Memo.Top := 0;
  Memo.Width := InfoPage.SurfaceWidth;
  Memo.Height := InfoPage.SurfaceHeight;
  Memo.ScrollBars := ssVertical;
  Memo.ReadOnly := True;

  if HaveWinget and SwitchGiven('NOINSTALLMISSING') then
  begin
    Memo.Text :=
      'Missing:' + #13#10 + MissingText + #13#10 +
      'Setup was started with the switch /NOINSTALLMISSING, so it will NOT install them. ' +
      'The program is installed without them and tells you what is missing when it starts.';
  end
  else if HaveWinget then
  begin
    VlcNote := '';
    if NeedVLC then
      VlcNote := #13#10 + 'Windows may show a permission window for VLC. Click Yes. ' +
        'If you click No, VLC is not installed.' + #13#10;
    Memo.Text :=
      'Missing:' + #13#10 + MissingText + #13#10 +
      'Setup will now install them for you, after it has copied the program. It uses winget, ' +
      'the Windows package manager. It needs an internet connection. You do not need to do ' +
      'anything: click Next, then Install.' + #13#10 + #13#10 +
      'This step can take several minutes and the Setup window may look frozen. Do not close it.' + #13#10 +
      VlcNote + #13#10 +
      'If something cannot be installed, Setup tells you at the end and shows what to do by hand. ' +
      'The program is installed in any case.';
  end
  else
  begin
    { No winget: nothing can be installed, so the page only shows a text. }
    Memo.Text :=
      'Missing:' + #13#10 + MissingText + #13#10 +
      'winget (the Windows package manager) was not found on this computer, so Setup cannot ' +
      'install them for you. To get winget, update "App Installer" in the Microsoft Store and ' +
      'run Setup again. Or install them by hand after Setup, as follows. The program is ' +
      'installed anyway and tells you what is missing when it starts.' + #13#10 + #13#10 +
      HandSteps;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if (InfoPage <> nil) and (PageID = InfoPage.ID) then
    Result := not (NeedFFmpeg or NeedVLC);
end;

procedure RunWinget(const Id, Caption: string);
var
  ResultCode: Integer;
begin
  WizardForm.StatusLabel.Caption := 'Installing ' + Caption +
    '. This can take several minutes and this window may look frozen. Do not close it.';
  WizardForm.FilenameLabel.Caption := '';
  WizardForm.StatusLabel.Update;
  if not Exec(WingetPath, 'install -e --id ' + Id + ' --accept-package-agreements --accept-source-agreements',
              '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ResultCode := -1;
  Log('winget install ' + Id + ' finished with code ' + IntToStr(ResultCode));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StillMissing: string;
  Steps: string;
begin
  if CurStep <> ssPostInstall then Exit;
  if not (NeedFFmpeg or NeedVLC) then Exit;
  if not HaveWinget then Exit;
  { Installing is the default, in the wizard and in silent mode. Only /NOINSTALLMISSING skips it.
    /INSTALLMISSING=1 is an old switch: still accepted, no effect. }
  if SwitchGiven('NOINSTALLMISSING') then Exit;

  if NeedFFmpeg then RunWinget('Gyan.FFmpeg', 'FFmpeg');
  if NeedVLC then RunWinget('VideoLAN.VLC', 'VLC player');

  StillMissing := '';
  Steps := '';
  if NeedFFmpeg and not HasFFmpeg then
  begin
    StillMissing := StillMissing + 'FFmpeg';
    Steps := Steps + FFmpegHandSteps + #13#10;
  end;
  if NeedVLC and not HasVLC then
  begin
    if StillMissing <> '' then StillMissing := StillMissing + ', ';
    StillMissing := StillMissing + 'VLC player';
    Steps := Steps + VLCHandSteps + #13#10;
  end;
  if StillMissing <> '' then
    SuppressibleMsgBox('The program is installed, but these could not be installed: ' + StillMissing + '.' + #13#10 + #13#10 +
      'Install them by hand with the steps below, then start the program again. The program opens ' +
      'without them and tells you what it cannot do.' + #13#10 + #13#10 + Steps,
      mbInformation, MB_OK, IDOK);
end;
