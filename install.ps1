#Requires -Version 5.1
# ============================================================
#  REACTION STUDIO v5 — Windows Installer
#  Run: Right-click -> "Run with PowerShell"
#  Or:  powershell -ExecutionPolicy Bypass -File install.ps1
# ============================================================

$ErrorActionPreference = "SilentlyContinue"
$AppName    = "Reaction Studio"
$AppVersion = "5.0"
$AppDir     = "$env:LOCALAPPDATA\ReactionStudio"
$DesktopLnk = "$env:USERPROFILE\Desktop\Reaction Studio.lnk"
$StartDir   = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Reaction Studio"
$IconSrc    = "$PSScriptRoot\assets\icon.ico"
$IconDst    = "$AppDir\icon.ico"

# ── Load WPF for GUI ──────────────────────────────────────────────────────────
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms

# ── XAML layout ──────────────────────────────────────────────────────────────
[xml]$XAML = @'
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Reaction Studio — Installer"
    Width="600" Height="500"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize"
    Background="#0f0f0f">

  <Grid>
    <!-- Sidebar -->
    <Border Width="180" HorizontalAlignment="Left"
            Background="#1a0a2e" BorderBrush="#7c3aed"
            BorderThickness="0,0,2,0">
      <StackPanel VerticalAlignment="Center" Margin="0,-40,0,0">
        <TextBlock Text="⚡" FontSize="48" HorizontalAlignment="Center"
                   Foreground="#fbbf24" Margin="0,0,0,4"/>
        <TextBlock Text="REACTION" FontSize="16" FontWeight="Bold"
                   HorizontalAlignment="Center" Foreground="#fbbf24"/>
        <TextBlock Text="STUDIO" FontSize="16" FontWeight="Bold"
                   HorizontalAlignment="Center" Foreground="White"/>
        <TextBlock Text="v5" FontSize="11" HorizontalAlignment="Center"
                   Foreground="#a78bfa" Margin="0,2,0,20"/>
        <TextBlock Text="Local AI Video" FontSize="10"
                   HorizontalAlignment="Center" Foreground="#c4b5fd"/>
        <TextBlock Text="Generator" FontSize="10"
                   HorizontalAlignment="Center" Foreground="#c4b5fd"
                   Margin="0,0,0,12"/>
        <TextBlock Text="· No API keys" FontSize="9"
                   HorizontalAlignment="Center" Foreground="#7c3aed"/>
        <TextBlock Text="· No subscriptions" FontSize="9"
                   HorizontalAlignment="Center" Foreground="#7c3aed"/>
        <TextBlock Text="· Runs forever" FontSize="9"
                   HorizontalAlignment="Center" Foreground="#7c3aed"/>
      </StackPanel>
    </Border>

    <!-- Main panel -->
    <Grid Margin="196,0,0,0">
      <StackPanel Margin="24,24,24,0">

        <TextBlock Name="TitleText"
                   Text="Installing Reaction Studio"
                   FontSize="18" FontWeight="Bold"
                   Foreground="White" Margin="0,0,0,4"/>
        <TextBlock Name="SubText"
                   Text="Please wait while files are copied and packages installed."
                   FontSize="11" Foreground="#888" TextWrapping="Wrap"
                   Margin="0,0,0,20"/>

        <!-- Steps list -->
        <StackPanel Name="StepPanel" Margin="0,0,0,16">
          <TextBlock Name="Step1" Text="○  Checking Python"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
          <TextBlock Name="Step2" Text="○  Copying app files"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
          <TextBlock Name="Step3" Text="○  Installing Python packages"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
          <TextBlock Name="Step4" Text="○  Creating desktop shortcut"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
          <TextBlock Name="Step5" Text="○  Adding to Start Menu"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
          <TextBlock Name="Step6" Text="○  Registering in Add/Remove Programs"
                     Foreground="#555" FontSize="11" Margin="0,3"/>
        </StackPanel>

        <!-- Progress bar -->
        <ProgressBar Name="ProgBar" Height="8" Minimum="0" Maximum="100"
                     Value="0" Margin="0,4,0,8"
                     Foreground="#7c3aed" Background="#2a2a2a"/>
        <TextBlock Name="ProgLabel" Text="Starting..."
                   Foreground="#888" FontSize="10" Margin="0,0,0,12"/>

        <!-- Log box -->
        <Border BorderBrush="#2a2a2a" BorderThickness="1"
                Background="#0a0a0a" Height="110" Margin="0,0,0,12">
          <ScrollViewer Name="LogScroll" VerticalScrollBarVisibility="Auto">
            <TextBlock Name="LogText" Foreground="#00ff88"
                       FontFamily="Consolas" FontSize="9"
                       Padding="8" TextWrapping="Wrap"/>
          </ScrollViewer>
        </Border>

        <!-- Buttons -->
        <StackPanel Orientation="Horizontal">
          <Button Name="InstallBtn"
                  Content="  ⚡  Install Now  "
                  Background="#7c3aed" Foreground="White"
                  FontSize="13" FontWeight="Bold" Padding="16,8"
                  BorderThickness="0" Cursor="Hand"/>
          <Button Name="SkipBtn"
                  Content="  Already installed — Skip  "
                  Background="#222" Foreground="#888"
                  FontSize="11" Padding="12,8" Margin="12,0,0,0"
                  BorderThickness="0" Cursor="Hand"/>
          <Button Name="CancelBtn"
                  Content="Cancel"
                  Background="#222" Foreground="#ef4444"
                  FontSize="11" Padding="12,8" Margin="12,0,0,0"
                  BorderThickness="0" Cursor="Hand"/>
        </StackPanel>

      </StackPanel>
    </Grid>
  </Grid>
</Window>
'@

# Parse XAML and get window
$reader  = New-Object System.Xml.XmlNodeReader $XAML
$Window  = [Windows.Markup.XamlReader]::Load($reader)

# Get controls
$TitleText  = $Window.FindName("TitleText")
$SubText    = $Window.FindName("SubText")
$ProgBar    = $Window.FindName("ProgBar")
$ProgLabel  = $Window.FindName("ProgLabel")
$LogText    = $Window.FindName("LogText")
$LogScroll  = $Window.FindName("LogScroll")
$InstallBtn = $Window.FindName("InstallBtn")
$SkipBtn    = $Window.FindName("SkipBtn")
$CancelBtn  = $Window.FindName("CancelBtn")
$Steps      = @(
    $Window.FindName("Step1"),
    $Window.FindName("Step2"),
    $Window.FindName("Step3"),
    $Window.FindName("Step4"),
    $Window.FindName("Step5"),
    $Window.FindName("Step6")
)

# ── UI helpers (must run on dispatcher) ──────────────────────────────────────
function UI-Log($msg) {
    $Window.Dispatcher.Invoke({
        $ts = Get-Date -Format "HH:mm:ss"
        $LogText.Text += "[$ts]  $msg`n"
        $LogScroll.ScrollToBottom()
    })
}

function UI-Progress($pct, $label) {
    $Window.Dispatcher.Invoke({
        $ProgBar.Value  = $pct
        $ProgLabel.Text = $label
    })
}

function UI-StepRunning($i, $text) {
    $Window.Dispatcher.Invoke({
        $Steps[$i].Text       = "▶  $text"
        $Steps[$i].Foreground = "#fbbf24"
    })
}

function UI-StepDone($i, $text) {
    $Window.Dispatcher.Invoke({
        $Steps[$i].Text       = "●  $text"
        $Steps[$i].Foreground = "#22c55e"
    })
}

function UI-StepWarn($i, $text) {
    $Window.Dispatcher.Invoke({
        $Steps[$i].Text       = "!  $text"
        $Steps[$i].Foreground = "#fbbf24"
    })
}

function UI-StepFail($i, $text) {
    $Window.Dispatcher.Invoke({
        $Steps[$i].Text       = "✗  $text"
        $Steps[$i].Foreground = "#ef4444"
    })
}

# ── Core install logic (runs on background thread) ────────────────────────────
function Run-Install {

    # ── STEP 1: Check Python ────────────────────────────────────────────────
    UI-StepRunning 0 "Checking Python 3.10+..."
    UI-Progress 2 "Checking Python..."
    $pyVer = (& python --version 2>&1)
    if ($LASTEXITCODE -eq 0 -and "$pyVer" -match "3\.(1[0-9]|[2-9]\d)") {
        UI-StepDone 0 "Python found: $pyVer"
        UI-Log "Python OK: $pyVer"
    } else {
        UI-StepWarn 0 "Python check inconclusive — attempting install anyway"
        UI-Log "Python not confirmed. You may need to install Python 3.10+ from python.org"
    }
    UI-Progress 10 "Python check complete"

    # ── STEP 2: Copy files ──────────────────────────────────────────────────
    UI-StepRunning 1 "Copying app files to $AppDir ..."
    UI-Progress 15 "Copying files..."
    try {
        New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
        Copy-Item -Recurse -Force "$PSScriptRoot\src\*" "$AppDir\" -ErrorAction Stop
        if (Test-Path "$PSScriptRoot\README.md") {
            Copy-Item -Force "$PSScriptRoot\README.md" "$AppDir\README.md"
        }
        if (Test-Path $IconSrc) {
            Copy-Item -Force $IconSrc $IconDst
        }
        UI-StepDone 1 "Files copied to $AppDir"
        UI-Log "Files copied OK"
    } catch {
        UI-StepFail 1 "Copy failed: $_"
        UI-Log "ERROR copying files: $_"
    }
    UI-Progress 30 "Files copied"

    # ── STEP 3: Python packages ─────────────────────────────────────────────
    UI-StepRunning 2 "Installing Python packages (1-3 min)..."
    UI-Log "Running pip install..."
    UI-Progress 35 "Installing Python packages..."

    $packages = "yt-dlp", "moviepy", "piper-tts", "openai-whisper",
                "google-auth", "google-auth-oauthlib", "google-api-python-client",
                "Pillow", "requests", "numpy"

    $i = 0
    foreach ($pkg in $packages) {
        UI-Log "  pip install $pkg ..."
        UI-Progress (35 + [int]($i / $packages.Count * 30)) "Installing $pkg..."
        & python -m pip install $pkg -q 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { UI-Log "  ✓ $pkg" }
        else                     { UI-Log "  ! $pkg (check manually if needed)" }
        $i++
    }
    UI-StepDone 2 "Python packages installed"
    UI-Progress 65 "Packages installed"

    # ── STEP 4: Desktop shortcut ────────────────────────────────────────────
    UI-StepRunning 3 "Creating Desktop shortcut..."
    UI-Progress 70 "Creating shortcut..."

    # Write a hidden-window VBS launcher (no black console box)
    $vbsPath = "$AppDir\launch.vbs"
    $vbsContent = @"
Set WshShell = WScript.CreateObject("WScript.Shell")
WshShell.Run "python """ & "$AppDir\main.py" & """", 0, False
"@
    [System.IO.File]::WriteAllText($vbsPath, $vbsContent, [System.Text.Encoding]::ASCII)

    # Also write a plain .cmd for power users
    $cmdPath = "$AppDir\launch.cmd"
    $cmdContent = "@echo off`r`ntitle Reaction Studio`r`ncd /d `"$AppDir`"`r`npython `"$AppDir\main.py`"`r`nif errorlevel 1 pause"
    [System.IO.File]::WriteAllText($cmdPath, $cmdContent, [System.Text.Encoding]::ASCII)

    try {
        $shell = New-Object -ComObject WScript.Shell
        $sc    = $shell.CreateShortcut($DesktopLnk)
        $sc.TargetPath       = "wscript.exe"
        $sc.Arguments        = "`"$vbsPath`""
        $sc.WorkingDirectory = $AppDir
        $sc.Description      = "Reaction Studio — Free Local AI Reaction Video Generator"
        if (Test-Path $IconDst) { $sc.IconLocation = "$IconDst,0" }
        else                    { $sc.IconLocation = "%SystemRoot%\System32\shell32.dll,22" }
        $sc.WindowStyle = 1
        $sc.Save()
        UI-StepDone 3 "Desktop shortcut created"
        UI-Log "Desktop shortcut: $DesktopLnk"
    } catch {
        UI-StepWarn 3 "Desktop shortcut: $_"
        UI-Log "Shortcut warning: $_"
    }
    UI-Progress 80 "Desktop shortcut created"

    # ── STEP 5: Start Menu ──────────────────────────────────────────────────
    UI-StepRunning 4 "Adding to Start Menu..."
    UI-Progress 85 "Creating Start Menu entries..."
    try {
        New-Item -ItemType Directory -Path $StartDir -Force | Out-Null

        # Main shortcut
        $sc2 = $shell.CreateShortcut("$StartDir\Reaction Studio.lnk")
        $sc2.TargetPath       = "wscript.exe"
        $sc2.Arguments        = "`"$vbsPath`""
        $sc2.WorkingDirectory = $AppDir
        $sc2.Description      = "Reaction Studio — Free Local AI Reaction Video Generator"
        if (Test-Path $IconDst) { $sc2.IconLocation = "$IconDst,0" }
        $sc2.Save()

        # Uninstall shortcut (just removes the AppDir for now)
        $sc3 = $shell.CreateShortcut("$StartDir\Uninstall Reaction Studio.lnk")
        $sc3.TargetPath       = "powershell.exe"
        $sc3.Arguments        = "-Command `"Remove-Item -Recurse -Force '$AppDir'; Remove-Item -Force '$DesktopLnk'; Remove-Item -Recurse -Force '$StartDir'; Write-Host 'Uninstalled.'; Start-Sleep 2`""
        $sc3.Description      = "Uninstall Reaction Studio"
        $sc3.Save()

        UI-StepDone 4 "Start Menu entries created"
        UI-Log "Start Menu: $StartDir"
    } catch {
        UI-StepWarn 4 "Start Menu: $_"
    }
    UI-Progress 92 "Start Menu done"

    # ── STEP 6: Registry (Add/Remove Programs) ──────────────────────────────
    UI-StepRunning 5 "Registering in Add/Remove Programs..."
    UI-Progress 96 "Writing registry..."
    try {
        $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ReactionStudio"
        New-Item -Path $regPath -Force | Out-Null
        Set-ItemProperty $regPath "DisplayName"     "Reaction Studio"
        Set-ItemProperty $regPath "DisplayVersion"  "5.0"
        Set-ItemProperty $regPath "Publisher"       "Reaction Studio"
        Set-ItemProperty $regPath "InstallLocation" $AppDir
        Set-ItemProperty $regPath "DisplayIcon"     "$IconDst,0"
        Set-ItemProperty $regPath "UninstallString" "powershell -Command `"Remove-Item -Recurse -Force '$AppDir'`""
        Set-ItemProperty $regPath "NoModify"        1 -Type DWord
        Set-ItemProperty $regPath "NoRepair"        1 -Type DWord
        UI-StepDone 5 "Registered in Add/Remove Programs"
        UI-Log "Registry written OK"
    } catch {
        UI-StepWarn 5 "Registry: $_"
        UI-Log "Registry warning (non-critical): $_"
    }
    UI-Progress 100 "Installation complete!"

    # ── Done ────────────────────────────────────────────────────────────────
    UI-Log "--- INSTALLATION COMPLETE ---"
    UI-Log "Installed to: $AppDir"
    UI-Log "Desktop shortcut: Reaction Studio"
    UI-Log "Start Menu: Start > Reaction Studio"
    UI-Log ""
    UI-Log "OPTIONAL: Install Ollama from https://ollama.com"
    UI-Log "          then run: ollama pull llama3"
    UI-Log "REQUIRED for video: Install ffmpeg from https://ffmpeg.org"

    $Window.Dispatcher.Invoke({
        $TitleText.Text          = "Installation Complete!"
        $SubText.Text            = "Reaction Studio is installed. Launch it from your Desktop or Start Menu."
        $InstallBtn.Content      = "  Launch Reaction Studio  "
        $InstallBtn.Background   = "#22c55e"
        $InstallBtn.IsEnabled    = $true
        $SkipBtn.Visibility      = "Collapsed"
    })
}

# ── Button handlers ───────────────────────────────────────────────────────────
$InstallBtn.Add_Click({
    if ($InstallBtn.Content -like "*Launch*" -and $InstallBtn.Background -like "*22c55e*") {
        # Installation is done — launch the app
        Start-Process "wscript.exe" -ArgumentList "`"$AppDir\launch.vbs`""
        $Window.Close()
        return
    }

    $InstallBtn.IsEnabled = $false
    $SkipBtn.IsEnabled    = $false

    $job = [System.Threading.Thread]::new({
        Run-Install
    })
    $job.IsBackground = $true
    $job.Start()
})

$SkipBtn.Add_Click({
    # Just create shortcuts without installing packages
    $Window.Dispatcher.Invoke({
        $TitleText.Text = "Shortcuts Created"
        $SubText.Text   = "Shortcuts added. Run 'pip install yt-dlp moviepy piper-tts ...' manually if needed."
    })

    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    Copy-Item -Recurse -Force "$PSScriptRoot\src\*" "$AppDir\" -ErrorAction SilentlyContinue
    if (Test-Path $IconSrc) { Copy-Item -Force $IconSrc $IconDst }

    $vbsPath = "$AppDir\launch.vbs"
    [System.IO.File]::WriteAllText($vbsPath,
        "Set WshShell = WScript.CreateObject(`"WScript.Shell`")`r`nWshShell.Run `"python `"`"$AppDir\main.py`"`"`", 0, False",
        [System.Text.Encoding]::ASCII)

    $shell = New-Object -ComObject WScript.Shell
    $sc    = $shell.CreateShortcut($DesktopLnk)
    $sc.TargetPath       = "wscript.exe"
    $sc.Arguments        = "`"$vbsPath`""
    $sc.WorkingDirectory = $AppDir
    $sc.Description      = "Reaction Studio"
    if (Test-Path $IconDst) { $sc.IconLocation = "$IconDst,0" }
    $sc.Save()

    UI-Log "Shortcuts created (packages not installed)"
    [System.Windows.MessageBox]::Show(
        "Desktop shortcut created!`n`nTo install packages later, run:`npython -m pip install yt-dlp moviepy piper-tts openai-whisper google-auth google-auth-oauthlib google-api-python-client Pillow requests numpy",
        "Done", "OK", "Information")
    $Window.Close()
})

$CancelBtn.Add_Click({ $Window.Close() })

# ── Show the window ───────────────────────────────────────────────────────────
$Window.Add_Loaded({
    UI-Log "Reaction Studio Installer v5 ready."
    UI-Log "Click 'Install Now' to begin."
})

$Window.ShowDialog() | Out-Null
