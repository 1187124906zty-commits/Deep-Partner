Unicode true
ManifestDPIAware true
!include "MUI2.nsh"
Name "Deep partner"
OutFile "${APP_ROOT}\dist\Deep partner Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Deep partner"
InstallDirRegKey HKCU "Software\DeepPartner" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "${APP_ROOT}\icons\icon.ico"
UninstallIcon "${APP_ROOT}\icons\icon.ico"
VIProductVersion "0.4.2.0"
VIAddVersionKey /LANG=2052 "ProductName" "Deep partner"
VIAddVersionKey /LANG=2052 "FileDescription" "Deep partner 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "0.4.2"
VIAddVersionKey /LANG=2052 "ProductVersion" "0.4.2"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Deep partner"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Deep partner.exe"
!define MUI_FINISHPAGE_RUN_TEXT "运行 Deep partner"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
Section "Deep partner" SEC_MAIN
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  SetOverwrite on
  ClearErrors
  File "/oname=Deep partner.exe" "${APP_ROOT}\target\release\deep-partner.exe"
  IfErrors 0 +4
    MessageBox MB_OK|MB_ICONSTOP "请先关闭 Deep partner，再重新运行安装程序。" /SD IDOK
    SetErrorLevel 2
    Quit
  File "${APP_ROOT}\target\release\dp.exe"
  File "/oname=使用说明.txt" "${APP_ROOT}\dist\使用说明.txt"
  SetOutPath "$INSTDIR\licenses"
  File "${APP_ROOT}\licenses\Geist-OFL.txt"
  File "${APP_ROOT}\licenses\Lora-OFL.txt"
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Deep partner"
  CreateShortcut "$SMPROGRAMS\Deep partner\Deep partner.lnk" "$INSTDIR\Deep partner.exe"
  CreateShortcut "$DESKTOP\Deep partner.lnk" "$INSTDIR\Deep partner.exe"
  WriteRegStr HKCU "Software\DeepPartner" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "DisplayName" "Deep partner"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "DisplayVersion" "0.4.2"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "DisplayIcon" "$INSTDIR\Deep partner.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner" "NoRepair" 1
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  Delete "$INSTDIR\Deep partner.exe"
  Delete "$INSTDIR\dp.exe"
  Delete "$INSTDIR\使用说明.txt"
  Delete "$INSTDIR\licenses\Geist-OFL.txt"
  Delete "$INSTDIR\licenses\Lora-OFL.txt"
  RMDir "$INSTDIR\licenses"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$DESKTOP\Deep partner.lnk"
  Delete "$SMPROGRAMS\Deep partner\Deep partner.lnk"
  RMDir "$SMPROGRAMS\Deep partner"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeepPartner"
  DeleteRegKey HKCU "Software\DeepPartner"
SectionEnd
