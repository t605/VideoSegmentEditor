# Builds the release zip of the Video Segment Editor from a WHITELIST of files.
# Command: powershell -NoProfile -ExecutionPolicy Bypass -File build_release.ps1 [-Dest <folder>]
# Output:  <Dest>\VideoSegmentEditor.zip   (default Dest: the folder 'Finished tools\VideoSegmentEditor'
#          two folders above this project folder, next to 'Work In Progress')
#
# Steps (any failure stops the build and leaves an existing zip untouched):
#   1. python -m unittest discover -s tests must pass
#   2. README.txt "version X.Y" must equal APP_VER in main.py
#   3. every whitelisted file must exist; they are copied to a staging folder
#   4. nothing outside the whitelist and no private/development file may be in staging
#   5. every local module imported by a shipped .py file must be shipped
#   6. every shipped .py must compile (python -I -W error, no files written)
#   7. byte checks: .bat ASCII + CRLF; README.txt CRLF, ASCII except the Russian section
#   8. a flat zip (no top-level folder, forward slashes) is written and re-read
#
# -Inject <names> is for testing the safety checks only: it drops empty files with
# those names into staging before check 4. Give ONE file name per run, e.g.  -Inject CLAUDE.md
# The build must then FAIL.
param(
    [string]$Dest = "",
    [string[]]$Inject = @()
)

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$zipName = "VideoSegmentEditor.zip"

if (-not $Dest) {
    $up2 = Split-Path (Split-Path $src)
    if (-not $up2 -or -not (Test-Path -LiteralPath $up2)) {
        Write-Host "BUILD FAILED: cannot work out the default output folder. Pass -Dest <folder>." -ForegroundColor Red
        exit 1
    }
    $Dest = Join-Path $up2 "Finished tools\VideoSegmentEditor"
}

# The only files that may be in the release (paths relative to the project folder).
# 14 files: 7 runtime .py files, requirements.txt, the launcher, README.txt, LICENSE, 3 asset files.
$whitelist = @(
    "main.py", "gui.py", "i18n.py", "create_flow.py", "segment_manager.py",
    "video_player.py", "video_processor.py", "requirements.txt",
    "VideoSegmentEditor.bat", "README.txt", "LICENSE",
    "assets\logo.png", "assets\logo.ico", "assets\logo_header.png"
)

# Names that must never be packaged (checked in addition to the whitelist).
$privateNames = @("CLAUDE.md", "README.md", "app.log", "settings.json", "build_release.ps1", "build_installer.ps1",
                  "VideoSegmentEditor.iss", ".gitignore", ".gitattributes", "prompt.txt", "mock screen.png")
$privateDirs = @("tests", "docs", ".superpowers", ".git", "venv", ".venv", "__pycache__",
                 "scripts", "dist", "build", "installer")
$privateExts = @(".zip", ".pyc", ".pyo", ".skill", ".log")

function Read-AllBytes([string]$path) { return [System.IO.File]::ReadAllBytes($path) }

# Returns a list of problems (empty list = file is ASCII only with CRLF line ends).
function Test-AsciiCrlf([string]$path, [string]$label) {
    $problems = @()
    $b = Read-AllBytes $path
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

$stage = Join-Path $env:TEMP ("VideoSegmentEditor_release_" + [guid]::NewGuid().ToString("N").Substring(0, 8))

try {
    # ---- 1. tests
    Write-Host "[1/8] Running the tests..."
    Push-Location $src
    try {
        # run through cmd: Windows PowerShell 5.1 turns the test runner's stderr into errors
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python was not found on PATH - release not built." }
        cmd /c "python -m unittest discover -s tests 2>&1" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Tests failed - release not built." }
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
    if ($readmeVer -ne $appVer) {
        throw "Version mismatch: README.txt says $readmeVer, main.py APP_VER is $appVer."
    }
    Write-Host "      version $appVer in code and README.txt"

    # ---- 3. whitelist exists, copy to staging
    Write-Host "[3/8] Copying the whitelisted files to staging..."
    foreach ($f in $whitelist) {
        if (-not (Test-Path -LiteralPath (Join-Path $src $f) -PathType Leaf)) {
            throw "Whitelisted file is missing: $f"
        }
    }
    New-Item -ItemType Directory -Path $stage | Out-Null
    foreach ($f in $whitelist) {
        $target = Join-Path $stage $f
        $dir = Split-Path $target -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
        Copy-Item -LiteralPath (Join-Path $src $f) -Destination $target
    }
    foreach ($name in $Inject) {   # test hook, see header
        $target = Join-Path $stage $name
        $dir = Split-Path $target -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
        Set-Content -LiteralPath $target -Value "injected for testing" -Encoding ASCII
        Write-Host "      (test) injected into staging: $name"
    }

    # ---- 4. nothing outside the whitelist, nothing private
    Write-Host "[4/8] Checking that only whitelisted files are packaged..."
    $problems = @()
    $stageFull = (Resolve-Path $stage).Path.TrimEnd('\')
    $staged = Get-ChildItem -LiteralPath $stage -Recurse -Force -File
    $wl = $whitelist | ForEach-Object { $_.ToLowerInvariant() }
    foreach ($file in $staged) {
        $rel = $file.FullName.Substring($stageFull.Length + 1)
        $relLower = $rel.ToLowerInvariant()
        $parts = $rel.Split('\')
        if ($privateNames -contains $file.Name) { $problems += "private/development file in release: $rel" }
        if ($privateExts -contains $file.Extension.ToLowerInvariant()) { $problems += "private/development file type in release: $rel" }
        $dirParts = @()
        if ($parts.Length -gt 1) { $dirParts = $parts[0..($parts.Length - 2)] }
        foreach ($p in $dirParts) {
            if ($privateDirs -contains $p) { $problems += "development folder in release: $rel"; break }
        }
        if ($wl -notcontains $relLower) { $problems += "file is not on the whitelist: $rel" }
    }
    if ($problems.Count -gt 0) { throw ("Unsafe release content:`r`n  " + ($problems -join "`r`n  ")) }
    Write-Host "      $($staged.Count) files, all whitelisted"

    # ---- 5. every imported local module is shipped
    Write-Host "[5/8] Checking that every imported local module is shipped..."
    $localModules = Get-ChildItem -LiteralPath $src -Filter *.py -File |
        ForEach-Object { $_.BaseName }
    $shippedModules = $whitelist | Where-Object { $_ -like "*.py" } |
        ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_) }
    $missing = @()
    foreach ($pyName in ($whitelist | Where-Object { $_ -like "*.py" })) {
        $lines = [System.IO.File]::ReadAllLines((Join-Path $stage $pyName))
        foreach ($line in $lines) {
            $names = @()
            $fm = [regex]::Match($line, '^\s*from\s+([A-Za-z_]\w*)')
            $im = [regex]::Match($line, '^\s*import\s+([A-Za-z_][\w\s,]*)')
            if ($fm.Success) { $names += $fm.Groups[1].Value }
            elseif ($im.Success) {
                foreach ($n in ($im.Groups[1].Value -split ',')) {
                    $first = $n.Trim() -split '\s+' | Select-Object -First 1
                    if ($first) { $names += $first }
                }
            }
            foreach ($n in $names) {
                if (($localModules -contains $n) -and ($shippedModules -notcontains $n)) {
                    $missing += "$pyName imports '$n' ($n.py) which is not in the release"
                }
            }
        }
    }
    if ($missing.Count -gt 0) { throw ("Missing runtime module:`r`n  " + ($missing -join "`r`n  ")) }
    Write-Host "      ok (shipped modules: $($shippedModules -join ', '))"

    # ---- 6. compile every shipped .py (no files are written)
    Write-Host "[6/8] Compiling every shipped .py file (python -I -W error)..."
    $compileCode = "import sys; f = open(sys.argv[1], 'rb'); data = f.read(); f.close(); compile(data, sys.argv[1], 'exec')"
    foreach ($pyName in ($whitelist | Where-Object { $_ -like "*.py" })) {
        & python -I -W error -c $compileCode (Join-Path $stage $pyName)
        if ($LASTEXITCODE -ne 0) { throw "Compile check failed for $pyName" }
    }

    # ---- 7. byte checks
    Write-Host "[7/8] Byte checks (ASCII, CRLF)..."
    $byteProblems = @()
    $byteProblems += Test-AsciiCrlf (Join-Path $stage "VideoSegmentEditor.bat") "VideoSegmentEditor.bat"
    $byteProblems += Test-AsciiCrlf (Join-Path $src "build_release.ps1") "build_release.ps1"
    # README.txt: UTF-8, CRLF, and Cyrillic allowed only in the Russian section at the end
    $rb = Read-AllBytes (Join-Path $stage "README.txt")
    for ($i = 0; $i -lt $rb.Length; $i++) {
        if ($rb[$i] -eq 10 -and ($i -eq 0 -or $rb[$i - 1] -ne 13)) { $byteProblems += "README.txt has a line end without CR at offset $i"; break }
        if ($rb[$i] -eq 13 -and ($i + 1 -ge $rb.Length -or $rb[$i + 1] -ne 10)) { $byteProblems += "README.txt has a lone CR at offset $i"; break }
    }
    $rtext = [System.Text.Encoding]::UTF8.GetString($rb).TrimStart([char]0xFEFF)   # UTF-8 BOM allowed
    $cut = $rtext.IndexOf("13. KRATKO PO-RUSSKI")
    if ($cut -lt 0) { $byteProblems += "README.txt: heading '13. KRATKO PO-RUSSKI' not found" }
    else {
        $head = $rtext.Substring(0, $cut)
        for ($i = 0; $i -lt $head.Length; $i++) {
            if ([int][char]$head[$i] -gt 127) {
                $byteProblems += "README.txt has a non-ASCII character before the Russian section (index $i)"; break
            }
        }
    }
    if ($rtext.Contains([string][char]0xFFFD)) { $byteProblems += "README.txt contains a garbled character (U+FFFD)" }
    if ($byteProblems.Count -gt 0) { throw ("Byte check failed:`r`n  " + ($byteProblems -join "`r`n  ")) }
    Write-Host "      ok"

    # ---- 8. zip
    Write-Host "[8/8] Writing the zip..."
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $zip = Join-Path (Resolve-Path $Dest).Path $zipName
    $tmpZip = $zip + ".tmp"
    if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::Open($tmpZip, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($f in $whitelist) {
            $entryName = $f.Replace('\', '/')
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, (Join-Path $stage $f), $entryName, [System.IO.Compression.CompressionLevel]::Optimal)
        }
    } finally { $archive.Dispose() }
    # re-read the zip and compare with the whitelist
    $check = [System.IO.Compression.ZipFile]::OpenRead($tmpZip)
    try {
        $entries = $check.Entries | ForEach-Object { $_.FullName }
        $wantList = $whitelist | ForEach-Object { $_.Replace('\', '/') }
        $diff = Compare-Object ($entries | Sort-Object) ($wantList | Sort-Object)
        if ($diff) { throw "The zip content does not match the whitelist." }
    } finally { $check.Dispose() }
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Move-Item -LiteralPath $tmpZip -Destination $zip
    Write-Host ""
    Write-Host "Release built: $zip"
    $final = [System.IO.Compression.ZipFile]::OpenRead($zip)
    try { $final.Entries | ForEach-Object { Write-Host ("  {0,9} bytes  {1}" -f $_.Length, $_.FullName) } }
    finally { $final.Dispose() }
}
catch {
    Write-Host ""
    Write-Host "BUILD FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path variable:tmpZip) { if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue } }
    $failed = $true
}
finally {
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue }
}
if ($failed) { exit 1 }
