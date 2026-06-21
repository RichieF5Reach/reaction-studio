; ============================================================
;  REACTION STUDIO — NSIS Installer Script
;  Compile with: makensis ReactionStudio.nsi
;  Output: ReactionStudio-Setup.exe
; ============================================================

Unicode True

; ── App metadata ─────────────────────────────────────────────────────────────
!define APPNAME        "Reaction Studio"
!define APPVERSION     "5.0"
!define APPEXE         "ReactionStudio.exe"
!define PUBLISHER      "Reaction Studio"
!define INSTALL_DIR    "$LOCALAPPDATA\ReactionStudio"
!define UNINSTALLER    "Uninstall.exe"
!define REGKEY         "Software\Microsoft\Windows\CurrentVersion\Uninstall\ReactionStudio"

Name          "${APPNAME} ${APPVERSION}"
OutFile       "ReactionStudio-Setup.exe"
InstallDir    "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\ReactionStudio" "InstallDir"
RequestExecutionLevel user
SetCompressor  /SOLID lzma
SetDatablockOptimize on

; ── MUI2 settings ────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!define MUI_ICON              "..\assets\icon.ico"
!define MUI_UNICON            "..\assets\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\assets\sidebar.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP  "..\assets\header.bmp"
!define MUI_HEADERIMAGE_RIGHT
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN           "$INSTDIR\${APPEXE}"
!define MUI_FINISHPAGE_RUN_TEXT      "Launch Reaction Studio now"
!define MUI_FINISHPAGE_SHOWREADME    "$INSTDIR\README.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"
!define MUI_WELCOMEPAGE_TITLE        "Welcome to Reaction Studio v5"
!define MUI_WELCOMEPAGE_TEXT         "Reaction Studio is a 100% free, fully local AI reaction video generator.$\r$\n$\r$\nNo subscriptions. No API keys. No cloud. Runs on your machine forever.$\r$\n$\r$\nThis installer will:$\r$\n  • Copy all app files to your machine$\r$\n  • Install required Python packages$\r$\n  • Create a Desktop shortcut$\r$\n  • Add to Start Menu$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_TITLE         "Reaction Studio is installed!"
!define MUI_FINISHPAGE_TEXT          "Reaction Studio has been installed successfully.$\r$\n$\r$\nLaunch it from your Desktop shortcut or Start Menu.$\r$\n$\r$\nOptional next steps:$\r$\n  1. Install Ollama: https://ollama.com$\r$\n     Then run: ollama pull llama3$\r$\n  2. Install ffmpeg: https://ffmpeg.org/download.html$\r$\n$\r$\nThese are optional — the app runs without them.$\r$\n(Script writing and video export require them)"

; ── Pages ─────────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE      "..\..\LICENSE.txt"
Page custom CheckPythonPage CheckPythonLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Custom Python check page ─────────────────────────────────────────────────
Var PythonOK
Var Dialog
Var PyLabel
Var PyStatusLabel
Var PyInstallBtn

Function CheckPythonPage
    nsDialogs::Create 1018
    Pop $Dialog
    ${If} $Dialog == error
        Abort
    ${EndIf}

    ${NSD_CreateLabel} 0 0 100% 24u "Checking system requirements..."
    Pop $PyLabel
    ${NSD_SetText} $PyLabel "Python 3.10+ is required to run Reaction Studio."

    ${NSD_CreateLabel} 0 28u 100% 16u ""
    Pop $PyStatusLabel

    ; Check Python
    nsExec::ExecToStack 'python --version'
    Pop $0  ; exit code
    Pop $1  ; output

    ${If} $0 == 0
        ${NSD_SetText} $PyStatusLabel "✓  Python found: $1"
        SetCtlColors $PyStatusLabel 0x22c55e 0x0f0f0f
        StrCpy $PythonOK "1"
    ${Else}
        ${NSD_SetText} $PyStatusLabel "✗  Python not found — click below to download"
        SetCtlColors $PyStatusLabel 0xef4444 0x0f0f0f
        StrCpy $PythonOK "0"
    ${EndIf}

    ${NSD_CreateButton} 0 52u 180u 20u "Download Python 3.12 (free)"
    Pop $PyInstallBtn
    ${NSD_OnClick} $PyInstallBtn DownloadPython

    nsDialogs::Show
FunctionEnd

Function DownloadPython
    ExecShell "open" "https://www.python.org/downloads/"
FunctionEnd

Function CheckPythonLeave
    ${If} $PythonOK == "0"
        MessageBox MB_YESNO|MB_ICONQUESTION \
            "Python was not found. Reaction Studio requires Python 3.10+.$\r$\n$\r$\nInstall Python, then re-run this installer.$\r$\n$\r$\nContinue anyway?" \
            IDYES +2
        Abort
    ${EndIf}
FunctionEnd

; ── Installer sections ────────────────────────────────────────────────────────
Section "Reaction Studio (required)" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"

    ; Copy all app files
    File /r "..\src\*.*"
    File "..\README.md"
    File "..\assets\icon.ico"

    ; Write the launcher .cmd
    FileOpen $0 "$INSTDIR\launch.cmd" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "title Reaction Studio$\r$\n"
    FileWrite $0 "cd /d $\"$INSTDIR$\"$\r$\n"
    FileWrite $0 "python $\"$INSTDIR\main.py$\"$\r$\n"
    FileWrite $0 "if errorlevel 1 pause$\r$\n"
    FileClose $0

    ; Write the .exe wrapper (VBScript that hides the console window)
    FileOpen $0 "$INSTDIR\launch_hidden.vbs" w
    FileWrite $0 "Set WshShell = WScript.CreateObject($\"WScript.Shell$\")$\r$\n"
    FileWrite $0 "WshShell.Run $\"python $\"$\"$INSTDIR\main.py$\"$\"$\", 0, False$\r$\n"
    FileClose $0

    ; Install Python packages
    DetailPrint "Installing Python packages..."
    nsExec::ExecToLog 'python -m pip install yt-dlp moviepy piper-tts openai-whisper google-auth google-auth-oauthlib google-api-python-client Pillow requests numpy -q'
    
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\${UNINSTALLER}"

    ; Registry for Add/Remove Programs
    WriteRegStr   HKCU "${REGKEY}" "DisplayName"     "${APPNAME}"
    WriteRegStr   HKCU "${REGKEY}" "DisplayVersion"  "${APPVERSION}"
    WriteRegStr   HKCU "${REGKEY}" "Publisher"       "${PUBLISHER}"
    WriteRegStr   HKCU "${REGKEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKCU "${REGKEY}" "UninstallString" "$\"$INSTDIR\${UNINSTALLER}$\""
    WriteRegStr   HKCU "${REGKEY}" "DisplayIcon"     "$\"$INSTDIR\icon.ico$\""
    WriteRegDWORD HKCU "${REGKEY}" "NoModify"        1
    WriteRegDWORD HKCU "${REGKEY}" "NoRepair"        1
    WriteRegStr   HKCU "Software\ReactionStudio"     "InstallDir" "$INSTDIR"
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\Reaction Studio.lnk" \
        "wscript.exe" \
        "$\"$INSTDIR\launch_hidden.vbs$\"" \
        "$INSTDIR\icon.ico" 0 \
        SW_SHOWNORMAL "" \
        "Free Local AI Reaction Video Generator"
SectionEnd

Section "Start Menu" SecStartMenu
    CreateDirectory "$SMPROGRAMS\Reaction Studio"
    CreateShortcut  "$SMPROGRAMS\Reaction Studio\Reaction Studio.lnk" \
        "wscript.exe" \
        "$\"$INSTDIR\launch_hidden.vbs$\"" \
        "$INSTDIR\icon.ico" 0 \
        SW_SHOWNORMAL "" \
        "Free Local AI Reaction Video Generator"
    CreateShortcut  "$SMPROGRAMS\Reaction Studio\Uninstall.lnk" \
        "$INSTDIR\${UNINSTALLER}"
SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"
    Delete "$INSTDIR\main.py"
    Delete "$INSTDIR\pipeline.py"
    Delete "$INSTDIR\captions.py"
    Delete "$INSTDIR\filters.py"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\launch.cmd"
    Delete "$INSTDIR\launch_hidden.vbs"
    Delete "$INSTDIR\${UNINSTALLER}"
    RMDir  "$INSTDIR"

    Delete "$DESKTOP\Reaction Studio.lnk"
    Delete "$SMPROGRAMS\Reaction Studio\Reaction Studio.lnk"
    Delete "$SMPROGRAMS\Reaction Studio\Uninstall.lnk"
    RMDir  "$SMPROGRAMS\Reaction Studio"

    DeleteRegKey HKCU "${REGKEY}"
    DeleteRegKey HKCU "Software\ReactionStudio"
SectionEnd

; ── Section descriptions ──────────────────────────────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}      "Core application files and Python packages (required)"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop}   "Add a shortcut to your Desktop"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Add Reaction Studio to your Start Menu"
!insertmacro MUI_FUNCTION_DESCRIPTION_END
