; ============================================================
;  Inno Setup script - tao file cai dat HP Cons PDF
;  Bien dich: chay build_installer.bat  (hoac ISCC.exe installer.iss)
;  Ket qua:   Output\HPConsPDF_Setup_1.0.0.exe
; ============================================================

#define AppName "HP Cons PDF"
#define AppVersion "1.0.11"
#define AppPublisher "Cong ty CP Xay dung Cong nghiep Hung Phuoc"
#define AppExe "HPConsPDF.exe"

[Setup]
AppId={{8F2A6C10-4B7E-4E2A-9C31-2B7A9D4E6F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\HP Cons PDF
DefaultGroupName=HP Cons PDF
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=HPConsPDF_Setup_{#AppVersion}
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Cai theo tung nguoi dung (khong can quyen Administrator) -> hop may cong ty
PrivilegesRequired=lowest
; Tu dong dong app dang chay khi cap nhat (auto-update) de khong ket file
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
en.LaunchApp=Mo HP Cons PDF ngay bay gio
en.CreateDesktop=Tao bieu tuong ngoai Man hinh (Desktop)
en.AssocOpenWith=Cho phep mo file PDF bang HP Cons PDF (them vao menu chuot phai "Open with")
en.SetDefault=Dat HP Cons PDF lam ung dung mo PDF mac dinh

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktop}"; GroupDescription: "Bieu tuong:"
Name: "assoc"; Description: "{cm:AssocOpenWith}"; GroupDescription: "Lien ket file PDF:"
Name: "setdefault"; Description: "{cm:SetDefault}"; GroupDescription: "Lien ket file PDF:"; Flags: unchecked

[Files]
Source: "dist\HPConsPDF\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "HUONG-DAN.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "logo.png"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; ---- Dinh danh loai tai lieu (ProgID) cua app ----
Root: HKA; Subkey: "Software\Classes\HPConsPDF.Document"; ValueType: string; ValueData: "Tai lieu PDF"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\HPConsPDF.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\logo.ico"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\HPConsPDF.Document\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "HP Cons PDF"; Tasks: assoc
; ---- Them vao danh sach "Open with" cua .pdf (KHONG xoa lien ket dang co) ----
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "HPConsPDF.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
; ---- Dang ky vao Windows "Default apps" (de nguoi dung chon trong Settings) ----
Root: HKA; Subkey: "Software\HP Cons\HP Cons PDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "HP Cons PDF"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\HP Cons\HP Cons PDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Cong cu xu ly PDF cho team dau thau HP Cons"; Tasks: assoc
Root: HKA; Subkey: "Software\HP Cons\HP Cons PDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "HPConsPDF.Document"; Tasks: assoc
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "HP Cons PDF"; ValueData: "Software\HP Cons\HP Cons PDF\Capabilities"; Flags: uninsdeletevalue; Tasks: assoc
; ---- Tuy chon: dat lam mac dinh (chi hieu luc neu may chua khoa lua chon khac) ----
Root: HKA; Subkey: "Software\Classes\.pdf"; ValueType: string; ValueData: "HPConsPDF.Document"; Flags: uninsdeletevalue; Tasks: setdefault

[Icons]
Name: "{group}\HP Cons PDF"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\logo.ico"
Name: "{group}\Huong dan"; Filename: "{app}\HUONG-DAN.md"
Name: "{group}\Go cai dat HP Cons PDF"; Filename: "{uninstallexe}"
Name: "{autodesktop}\HP Cons PDF"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
