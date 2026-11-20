; Bộ cài Windows cho "Tách văn bản công chứng" (Inno Setup 6)
; Dựng bằng: ISCC.exe /DMyAppVersion=0.3.1 packaging\TachVanBan.iss   (sau khi build_windows.ps1 đã tạo dist\TachVanBan)
; - Nén LZMA2 dạng khối (solid) để file tải về nhỏ nhất
; - Mặc định cài cho người dùng hiện tại vào %LOCALAPPDATA%\Programs, KHÔNG cần quyền quản trị

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Tách văn bản công chứng"
#define MyAppExe "TachVanBan.exe"
#define MyAppUrl "https://github.com/phamngocson6596/tach-file-hoso"

[Setup]
AppId={{CA779A67-20BA-447D-A9DC-D1FBECAC0C30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Dự án tach-file-hoso (mã nguồn mở)
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}/issues
AppUpdatesURL={#MyAppUrl}/releases
DefaultDirName={autopf}\TachVanBan
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
; Python 3.13 chỉ chạy trên Windows 10 trở lên: chặn ngay từ bộ cài thay vì báo lỗi khó hiểu khi mở
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=TachVanBan-CaiDat
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
CloseApplications=yes

[Languages]
#if FileExists(CompilerPath + "Languages\Vietnamese.isl")
Name: "vi"; MessagesFile: "compiler:Languages\Vietnamese.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\TachVanBan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autoprograms}\Hướng dẫn sử dụng (Tách văn bản công chứng)"; Filename: "{app}\HUONG_DAN.md"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
