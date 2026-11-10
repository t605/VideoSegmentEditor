# Builds the Windows installer of the Video Segment Editor: a PyInstaller ONE-FOLDER build of main.py,
# wrapped by an Inno Setup Setup program.
# Command: powershell -NoProfile -ExecutionPolicy Bypass -File build_installer.ps1 [-Dest <folder>] [-Work <folder>]
# Output:  <Dest>\VideoSegmentEditor-Setup.exe   (default Dest: the folder 'Finished tools\VideoSegmentEditor'
#          two folders above this project folder, next to 'Work In Progress')
#
# Needs on this PC: Python 3.11+ on PATH (with pip and internet, to fetch PyInstaller and python-vlc into a
# private build environment) and Inno Setup 6 (ISCC.exe). Inno Setup: winget install -e --id JRSoftware.InnoSetup --scope user
# Nothing is installed system-wide by this script. The release zip (build_release.ps1) is a separate product.
#
# Steps (any failure stops the build and leaves an existing Setup file untouched):
#   1. python -m unittest discover -s tests must pass
#   2. README.txt "version X.Y" must equal APP_VER in main.py
#   3. ISCC.exe is found; the installer script and this script are ASCII + CRLF
#   4. a private build environment is created in the work folder; PyInstaller and python-vlc are installed
#   5. PyInstaller builds the one-folder program (windowed, with the assets, the logo icon, python-vlc)
#   6. the built folder is checked (exe, assets, no private/development file in it)
#   7. Inno Setup compiles VideoSegmentEditor-Setup.exe
#   8. the Setup file is checked and moved to <Dest>
#
# -Work <folder>: keep the work folder (build environment, PyInstaller output) there and reuse it next time
# (faster). Without it a temporary folder is used and deleted at the end.
param(
    [string]$Dest = "",
    [string]$Work = ""
)

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$setupName = "VideoSegmentEditor-Setup.exe"
$pyInstallerVersion = "6.22.3"

if (-not $Dest) {
    $up2 = Split-Path (Split-Path $src)
    if (-not $up2 -or -not (Test-Path -LiteralPath $up2)) {
        Write-Host "BUILD FAILED: cannot work out the default output folder. Pass -Dest <folder>." -ForegroundColor Red
        exit 1
    }
    $Dest = Join-Path $up2 "Finished tools\VideoSegmentEditor"
}

# Files and folders that must never end up inside the built program folder.
$privateNames = @("CLAUDE.md", "README.md", "app.log", "settings.json", "build_release.ps1", "build_installer.ps1",
                  ".gitignore", ".gitattributes", "prompt.txt", "mock screen.png")
$privateDirs = @("tests", "docs", ".superpowers", ".git", "venv", ".venv", "installer")

function Test-AsciiCrlf([string]$path, [string]$label) {
    $problems = @()
    $b = [System.IO.File]::ReadAllBytes($path)
    for ($i = 0; $i -lt $b.Length; $i++) {
        if ($b[$i] -gt 127) { $problems += "$label has a non-ASCII byte at offset $i"; break }
    }
    for ($i = 0; $i -lt $b.Length; $i++) {
        if ($b[$i] -eq 10 -and ($i -eq 0 -or $b[$i - 1] -ne 13)) {
            $problems += "$label has a line end without CR (not CRLF) at offset $i"; break
        }
        if ($b[$i] -eq 13 -and ($i + 1 -ge $b.Length -or $b[$i + 1] -ne 10)) {
            $problems += "$label has a lone CR at offset $i"; break
        }
    }
    return $problems
}

# Runs a native command through cmd so that stderr text does not become a PowerShell error in 5.1.
function Invoke-Native([string]$commandLine, [string]$failMessage) {
    cmd /c "$commandLine 2>&1" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw $failMessage }
}

$keepWork = [bool]$Work
if (-not $Work) {
    $Work = Join-Path $env:TEMP ("VideoSegmentEditor_installer_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
}
$tmpSetup = $null

try {
    # ---- 1. tests
    Write-Host "[1/8] Running the tests..."
    Push-Location $src
    try {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python was not found on PATH - installer not built." }
        cmd /c "python -m unittest discover -s tests 2>&1" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Tests failed - installer not built." }
    } finally { Pop-Location }

    # ---- 2. version
    Write-Host "[2/8] Checking the version..."
    $mainText = [System.IO.File]::ReadAllText((Join-Path $src "main.py"))
    $m = [regex]::Match($mainText, 'APP_VER\s*=\s*"([^"]+)"')
    if (-not $m.Success) { throw "APP_VER not found in main.py." }
    $appVer = $m.Groups[1].Value
    $readmeLines = [System.IO.File]::ReadAllLines((Join-Path $src "README.txt"), [System.Text.Encoding]::UTF8)
    $readmeVer = $null
    foreach ($line in ($readmeLines | Select-Object -First 5)) {
        $mm = [regex]::Match($line, '\bversion\s+(\d+(?:\.\d+)+)')
        if ($mm.Success) { $readmeVer = $mm.Groups[1].Value; break }
    }
    if (-not $readmeVer) { throw "README.txt has no 'version X.Y' in its first lines." }
    if ($readmeVer -ne $appVer) { throw "Version mismatch: README.txt says $readmeVer, main.py APP_VER is $appVer." }
    Write-Host "      version $appVer in code and README.txt"

    # ---- 3. Inno Setup and byte checks
    Write-Host "[3/8] Looking for Inno Setup and checking the script files..."
    $iscc = $null
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
    if (-not $iscc) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
        foreach ($c in $candidates) { if ($c -and (Test-Path -LiteralPath $c)) { $iscc = $c; break } }
    }
    if (-not $iscc) {
        throw "Inno Setup 6 (ISCC.exe) was not found. Install it for your user with:  winget install -e --id JRSoftware.InnoSetup --scope user"
    }
    Write-Host "      $iscc"
    $iss = Join-Path $src "installer\VideoSegmentEditor.iss"
    if (-not (Test-Path -LiteralPath $iss)) { throw "installer\VideoSegmentEditor.iss is missing." }
    $byteProblems = @()
    $byteProblems += Test-AsciiCrlf $iss "installer\VideoSegmentEditor.iss"
    $byteProblems += Test-AsciiCrlf (Join-Path $src "build_installer.ps1") "build_installer.ps1"
    if ($byteProblems.Count -gt 0) { throw ("Byte check failed:`r`n  " + ($byteProblems -join "`r`n  ")) }
    foreach ($f in @("assets\logo.ico", "assets\logo.png", "assets\logo_header.png", "LICENSE", "README.txt")) {
        if (-not (Test-Path -LiteralPath (Join-Path $src $f) -PathType Leaf)) { throw "Required file is missing: $f" }
    }

    # ---- 4. build environment
    Write-Host "[4/8] Preparing the private build environment (PyInstaller $pyInstallerVersion, python-vlc)..."
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    $envDir = Join-Path $Work "buildenv"
    $bpy = Join-Path $envDir "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $bpy)) {
        Invoke-Native "python -m venv `"$envDir`"" "Could not create the build environment."
    }
    Invoke-Native "`"$bpy`" -m pip install --disable-pip-version-check -q pyinstaller==$pyInstallerVersion -r `"$(Join-Path $src 'requirements.txt')`"" `
        "pip could not install PyInstaller and python-vlc (internet needed)."
    Invoke-Native "`"$bpy`" -c `"import tkinter, vlc`"" "The build environment cannot import tkinter and python-vlc."

    # ---- 5. PyInstaller
    Write-Host "[5/8] Building the program folder with PyInstaller (a few minutes)..."
    $dist = Join-Path $Work "dist"
    $pwork = Join-Path $Work "pybuild"
    $spec = Join-Path $Work "spec"
    foreach ($d in @($dist, $pwork, $spec)) { if (Test-Path $d) { Remove-Item $d -Recurse -Force } }
    $assets = Join-Path $src "assets"
    $ico = Join-Path $assets "logo.ico"
    $pyArgs = "-m PyInstaller --noconfirm --clean --windowed --onedir --name VideoSegmentEditor " +
            "--icon `"$ico`" --add-data `"$assets;assets`" " +
            "--hidden-import vlc --hidden-import gui --hidden-import i18n --hidden-import create_flow " +
            "--hidden-import segment_manager --hidden-import video_player --hidden-import video_processor " +
            "--paths `"$src`" --distpath `"$dist`" --workpath `"$pwork`" --specpath `"$spec`" `"$(Join-Path $src 'main.py')`""
    Invoke-Native "`"$bpy`" $pyArgs" "PyInstaller failed."

    # ---- 6. check the built folder
    Write-Host "[6/8] Checking the built program folder..."
    $app = Join-Path $dist "VideoSegmentEditor"
    $exe = Join-Path $app "VideoSegmentEditor.exe"
    if (-not (Test-Path -LiteralPath $exe)) { throw "PyInstaller did not produce VideoSegmentEditor.exe." }
    $logo = Get-ChildItem -LiteralPath $app -Recurse -File -Filter "logo_header.png" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $logo) { throw "The assets folder is not inside the built program." }
    $problems = @()
    $appFull = (Resolve-Path $app).Path.TrimEnd('\')
    foreach ($file in (Get-ChildItem -LiteralPath $app -Recurse -Force -File)) {
        $rel = $file.FullName.Substring($appFull.Length + 1)
        $parts = $rel.Split('\')
        if ($privateNames -contains $file.Name) { $problems += "private/development file in the program folder: $rel" }
        if ($parts.Length -gt 1) {
            foreach ($p in $parts[0..($parts.Length - 2)]) {
                if ($privateDirs -contains $p) { $problems += "development folder in the program folder: $rel"; break }
            }
        }
    }
    if ($problems.Count -gt 0) { throw ("Unsafe program folder content:`r`n  " + ($problems -join "`r`n  ")) }
    $count = (Get-ChildItem -LiteralPath $app -Recurse -File).Count
    $mb = [math]::Round(((Get-ChildItem -LiteralPath $app -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
    Write-Host "      $count files, $mb MB; exe and assets present, no private file"

    # ---- 7. Inno Setup
    Write-Host "[7/8] Compiling the Setup program with Inno Setup..."
    $outDir = Join-Path $Work "setup"
    if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
    New-Item -ItemType Directory -Path $outDir | Out-Null
    Invoke-Native "`"$iscc`" /Qp `"/O$outDir`" `"/DAppVer=$appVer`" `"/DSourceDir=$app`" `"/DProjectDir=$src`" `"$iss`"" "Inno Setup failed."

    # ---- 8. check and move
    Write-Host "[8/8] Checking and writing the Setup file..."
    $built = Join-Path $outDir $setupName
    if (-not (Test-Path -LiteralPath $built)) { throw "Inno Setup did not produce $setupName." }
    $size = (Get-Item -LiteralPath $built).Length
    if ($size -lt 1MB) { throw "The Setup file is suspiciously small ($size bytes)." }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $final = Join-Path (Resolve-Path $Dest).Path $setupName
    $tmpSetup = $final + ".tmp"
    Copy-Item -LiteralPath $built -Destination $tmpSetup -Force
    if (Test-Path $final) { Remove-Item $final -Force }
    Move-Item -LiteralPath $tmpSetup -Destination $final
    $tmpSetup = $null
    Write-Host ""
    Write-Host "Installer built: $final"
    Write-Host ("  {0:N1} MB, version {1}" -f ($size / 1MB), $appVer)
}
catch {
    Write-Host ""
    Write-Host "BUILD FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($tmpSetup -and (Test-Path $tmpSetup)) { Remove-Item $tmpSetup -Force -ErrorAction SilentlyContinue }
    $failed = $true
}
finally {
    if (-not $keepWork -and (Test-Path $Work)) { Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue }
}
if ($failed) { exit 1 }
