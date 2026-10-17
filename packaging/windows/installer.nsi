Unicode true
!include "MUI2.nsh"

; STAGE is passed from CI as an absolute path to the staged portable folder.
!ifndef STAGE
  !define STAGE "portable"
!endif

Name "Bravo"
OutFile "Bravo-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Bravo"
InstallDirRegKey HKCU "Software\Bravo" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${STAGE}\*.*"

  CreateDirectory "$SMPROGRAMS\Bravo"
  CreateShortCut "$SMPROGRAMS\Bravo\Bravo.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\launcher.py"' "$INSTDIR\runtime\pythonw.exe" 0
  CreateShortCut "$SMPROGRAMS\Bravo\Stop Bravo.lnk" "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" '-ExecutionPolicy Bypass -WindowStyle Hidden -File "$INSTDIR\Stop-Bravo.ps1"'
  CreateShortCut "$DESKTOP\Bravo.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\launcher.py"' "$INSTDIR\runtime\pythonw.exe" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Bravo" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Bravo" "DisplayName" "Bravo"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Bravo" "DisplayVersion" "1.0.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Bravo" "Publisher" "Bravo"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Bravo" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Bravo.lnk"
  Delete "$SMPROGRAMS\Bravo\Bravo.lnk"
  Delete "$SMPROGRAMS\Bravo\Stop Bravo.lnk"
  RMDir "$SMPROGRAMS\Bravo"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Bravo"
  DeleteRegKey HKCU "Software\Bravo"
  RMDir /r "$INSTDIR"
SectionEnd
