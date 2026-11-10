@echo off
rem ======================================================================
rem  Video Segment Editor - launcher
rem
rem  What it does, in order:
rem    1. Looks at the whole computer FIRST: Python 3.11 or newer (with
rem       tkinter), FFmpeg + FFprobe, and the VLC player.
rem    2. If something is missing it shows ONE screen that lists everything
rem       missing with its approximate size and asks ONE question (Y/N).
rem       On Y it installs all of it with winget, without further questions,
rem       and then checks again by itself (no need to close this window and
rem       start again, also not after Python was installed).
rem    3. Creates a private Python environment in
rem       %LOCALAPPDATA%\VideoSegmentEditor\venv and installs the packages
rem       from requirements.txt (again only when requirements.txt changed).
rem    4. Starts the program (no console window) and closes this window.
rem  Saying N, or having no winget: Python is required (the launcher stops
rem  with plain instructions); without FFmpeg or VLC the program still starts
rem  and explains in its own window what is missing.
rem
rem  Test switch (safe: installs nothing, creates nothing, starts nothing):
rem      VideoSegmentEditor.bat /check
rem  It only prints what it found: Python, tkinter, the private environment,
rem  the packages, FFmpeg, FFprobe and VLC, and what a normal start would
rem  install. Its only file write is a small temporary text file in %TEMP%,
rem  which it deletes again. Any other argument prints a short help text and
rem  does nothing.
rem
rem  Developer test switches (environment variables, not for users). They
rem  all work ONLY together with VSE_DRYRUN=1, so they can never change what
rem  a normal start does:
rem      VSE_DRYRUN=1               winget commands are only printed, and the
rem                                 launcher stops before the environment and
rem                                 program steps.
rem      VSE_FAKE_MISSING=python,ffmpeg,vlc   pretends these are missing on
rem                                 the first check (any combination).
rem      VSE_FAKE_FAIL=ffmpeg,vlc   pretends these are STILL missing after the
rem                                 (printed) install, to test the failure text.
rem      VSE_FAKE_WINGET=1 or 0     pretends winget exists (1) or not (0).
rem ======================================================================
setlocal EnableExtensions
title Video Segment Editor
pushd "%~dp0"

set "CHECK=0"
set "RESUMED=0"
if /i "%~1"=="/check" set "CHECK=1"
if not "%~1"=="" if /i not "%~1"=="/check" goto usage
if not defined LOCALAPPDATA goto no_localappdata
set "NOTE=0"

set "DATA=%LOCALAPPDATA%\VideoSegmentEditor"
set "VENV=%DATA%\venv"
set "VPY=%VENV%\Scripts\python.exe"
set "VPYW=%VENV%\Scripts\pythonw.exe"
set "STAMP=%VENV%\requirements.installed.txt"
set "TMPV=%TEMP%\vse_launcher_version.txt"

echo.
echo  Video Segment Editor
if "%CHECK%"=="1" echo  CHECK ONLY: nothing will be installed or started.
echo.

if not exist "%~dp0main.py" goto no_main
if not exist "%~dp0requirements.txt" goto no_main

rem ----------------------------------------------------------------------
rem  Step 1 - look at the whole computer (also run again after installing)
rem ----------------------------------------------------------------------
:detect
set "PY="
set "FOUND="
set "VENVOK=0"
set "NEEDPY=0"
set "NEEDFF=0"
set "NEEDVLC=0"
if "%RESUMED%"=="0" echo  Checking this computer...
if "%RESUMED%"=="1" echo  Checking this computer again...

if not exist "%VPY%" goto d_py_find
call :test_exe "%VPY%"
if errorlevel 1 goto d_py_broken
if not exist "%VPYW%" goto d_py_broken
set "VENVOK=1"
set PY="%VPY%"
call :show_version "%VPY%"
echo          Python:  OK  (%PYVER%, tkinter works, private environment exists)
goto d_ff

:d_py_broken
echo          The private Python environment exists but does not work.
echo          It will be rebuilt on a normal start.

:d_py_find
call :find_python
if defined FOUND goto d_py_sys
set "NEEDPY=1"
echo          Python:  MISSING  (Python 3.11 or newer with tkinter)
goto d_ff

:d_py_sys
set PY=%FOUND%
echo          Python:  OK  (%FOUNDVER%, tkinter works)

:d_ff
call :find_ffmpeg
if "%FFOK%"=="1" if "%FPOK%"=="1" goto d_ff_ok
set "NEEDFF=1"
if "%FFOK%"=="1" echo          FFmpeg:  found, but FFprobe is MISSING
if "%FFOK%"=="0" if "%FPOK%"=="1" echo          FFprobe: found, but FFmpeg is MISSING
if "%FFOK%"=="0" if "%FPOK%"=="0" echo          FFmpeg:  MISSING  (FFmpeg and FFprobe)
goto d_vlc

:d_ff_ok
echo          FFmpeg:  OK  (FFmpeg and FFprobe found)

:d_vlc
call :find_vlc
if "%VLCOK%"=="1" goto d_vlc_ok
set "NEEDVLC=1"
echo          VLC:     MISSING  (needed for the video preview only)
goto d_fakes

:d_vlc_ok
echo          VLC:     OK  (found)

:d_fakes
if not "%VSE_DRYRUN%"=="1" goto d_summary
if "%RESUMED%"=="1" goto d_fail
if not defined VSE_FAKE_MISSING goto d_summary
if /i not "%VSE_FAKE_MISSING:python=%"=="%VSE_FAKE_MISSING%" set "NEEDPY=1"
if /i not "%VSE_FAKE_MISSING:ffmpeg=%"=="%VSE_FAKE_MISSING%" set "NEEDFF=1"
if /i not "%VSE_FAKE_MISSING:vlc=%"=="%VSE_FAKE_MISSING%" set "NEEDVLC=1"
echo          [test] VSE_FAKE_MISSING is set: pretending something is missing.
goto d_summary

:d_fail
if not defined VSE_FAKE_FAIL goto d_summary
if /i not "%VSE_FAKE_FAIL:python=%"=="%VSE_FAKE_FAIL%" set "NEEDPY=1"
if /i not "%VSE_FAKE_FAIL:ffmpeg=%"=="%VSE_FAKE_FAIL%" set "NEEDFF=1"
if /i not "%VSE_FAKE_FAIL:vlc=%"=="%VSE_FAKE_FAIL%" set "NEEDVLC=1"
echo          [test] VSE_FAKE_FAIL is set: pretending the install failed.

:d_summary
if not "%NEEDPY%%NEEDFF%%NEEDVLC%"=="000" goto something_missing
echo.
echo          Everything the program needs is installed.
goto ready

rem ----------------------------------------------------------------------
rem  Something is missing: ONE screen, ONE question, then install it all
rem ----------------------------------------------------------------------
:something_missing
if "%CHECK%"=="1" goto check_missing
if "%RESUMED%"=="1" goto still_missing
echo.
echo  ----------------------------------------------------------------------
echo   Missing on this computer (all free):
echo.
if "%NEEDPY%"=="1"  echo     - Python 3.12   about  25 MB   runs the program
if "%NEEDFF%"=="1"  echo     - FFmpeg        about 100 MB   creates the new video
if "%NEEDVLC%"=="1" echo     - VLC player    about  40 MB   shows the video preview
echo.
call :have_winget
if errorlevel 1 goto no_winget
echo   The launcher can install all of it now with winget, the Windows
echo   package manager. It needs an internet connection and asks nothing
echo   more after this question. Then the program starts by itself.
if "%NEEDVLC%"=="1" echo.
if "%NEEDVLC%"=="1" echo   Windows may show a permission window for VLC. Click Yes.
if "%NEEDVLC%"=="1" echo   If you click No, VLC is not installed.
echo.
echo   Press Y to install, N to skip. Do not close this window while it installs.
echo  ----------------------------------------------------------------------
echo.
choice /C YN /M "  Install everything listed above now"
if errorlevel 2 goto declined
goto do_install

:do_install
echo.
set "TOTAL=0"
if "%NEEDPY%"=="1" set /a TOTAL+=1
if "%NEEDFF%"=="1" set /a TOTAL+=1
if "%NEEDVLC%"=="1" set /a TOTAL+=1
set "N=0"
if "%NEEDPY%"=="1" set /a N+=1
if "%NEEDPY%"=="1" echo  Installing %N% of %TOTAL%: Python 3.12. Please wait, do not close this window...
if "%NEEDPY%"=="1" set "WGLABEL=Python 3.12"
if "%NEEDPY%"=="1" call :wg install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
if "%NEEDFF%"=="1" set /a N+=1
if "%NEEDFF%"=="1" echo  Installing %N% of %TOTAL%: FFmpeg. Please wait, do not close this window...
if "%NEEDFF%"=="1" set "WGLABEL=FFmpeg"
if "%NEEDFF%"=="1" call :wg install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
if "%NEEDVLC%"=="1" set /a N+=1
if "%NEEDVLC%"=="1" echo  Installing %N% of %TOTAL%: VLC player. Please wait, do not close this window...
if "%NEEDVLC%"=="1" set "WGLABEL=VLC player"
if "%NEEDVLC%"=="1" call :wg install -e --id VideoLAN.VLC --accept-package-agreements --accept-source-agreements
echo.
echo  Installation finished. Checking again by itself (nothing to close or restart)...
echo.
call :refresh_path
set "RESUMED=1"
goto detect

:declined
echo.
echo  Nothing was installed.
call :make_list
echo  Still missing: %LIST%. Install them by hand with the steps below,
echo  then start this file again.
set "NOTE=1"
goto byhand

:no_winget
echo  winget (the Windows package manager) was not found on this computer, so
echo  the launcher cannot install anything by itself. winget is normally part
echo  of Windows 10 and 11. To get it, update "App Installer" in the Microsoft
echo  Store, then start this file again. Or install by hand, as follows.
set "NOTE=1"
goto byhand

:still_missing
echo.
call :make_list
echo  These could not be installed: %LIST%.
echo  Install them by hand with the steps below, then start this file again.
echo  (winget may have shown a message above, or an installation was cancelled.)
set "NOTE=1"
goto byhand

rem  Plain by-hand instructions for each item that is still missing.
:byhand
echo.
if "%NEEDPY%"=="1" call :text_python
if "%NEEDFF%"=="1" call :text_ffmpeg
if "%NEEDVLC%"=="1" call :text_vlc
if "%NEEDPY%"=="1" goto python_fatal
set "NOTE=1"
echo  The program will still open now. It explains in its own window what
echo  it cannot do until the missing item is installed.
goto ready

:python_fatal
echo  The program cannot start without Python. After installing it, start
echo  this file again.
echo.
pause
popd
exit /b 1

:check_missing
echo.
echo  [check only] A normal start would list this and ask ONE question:
if "%NEEDPY%"=="1"  echo     - Python 3.12   about  25 MB
if "%NEEDFF%"=="1"  echo     - FFmpeg        about 100 MB
if "%NEEDVLC%"=="1" echo     - VLC player    about  40 MB
where winget >nul 2>&1
if errorlevel 1 echo  [check only] winget was NOT found: nothing could be installed automatically.
if not errorlevel 1 echo  [check only] winget was found.
goto ready

rem ----------------------------------------------------------------------
rem  Step 2 - private environment and packages, then start
rem ----------------------------------------------------------------------
:ready
if "%CHECK%"=="1" goto check_packages
if "%VSE_DRYRUN%"=="1" goto dryrun_done
if "%VENVOK%"=="1" goto step_packages
if "%VENVOK%"=="0" if defined PY goto make_venv
rem  An existing but broken environment is rebuilt only when a system Python exists.
goto venv_failed

:make_venv
if exist "%VENV%" echo  Rebuilding the private Python environment...
if exist "%VENV%" rmdir /s /q "%VENV%" >nul 2>&1
if exist "%VENV%" goto venv_stuck
echo.
echo  Creating the private Python environment. This happens only once...
if not exist "%DATA%" mkdir "%DATA%"
%PY% -m venv "%VENV%"
if errorlevel 1 goto venv_failed
call :test_exe "%VPY%"
if errorlevel 1 goto venv_failed
set "VENVOK=1"

:step_packages
echo.
echo  Checking the program packages...
fc /b "%~dp0requirements.txt" "%STAMP%" >nul 2>&1
if not errorlevel 1 goto packages_ok
echo          Installing the packages. First start only, needs internet...
"%VPY%" -m pip install --disable-pip-version-check -q -r "%~dp0requirements.txt"
if errorlevel 1 goto pip_failed
copy /y "%~dp0requirements.txt" "%STAMP%" >nul
echo          Done.
goto step_done

:packages_ok
echo          Packages: up to date.
goto step_done

:check_packages
echo.
echo  Checking the program packages...
if "%VENVOK%"=="0" echo          [check only] Skipped, because no working private environment exists yet.
if "%VENVOK%"=="0" goto check_done
fc /b "%~dp0requirements.txt" "%STAMP%" >nul 2>&1
if not errorlevel 1 echo          Packages: up to date.
if errorlevel 1 echo          [check only] Packages are new or changed. A normal start would install them now.
goto check_done

:dryrun_done
echo.
echo  [dry run] Stopping here: the environment and the program are not touched.
if "%NOTE%"=="1" echo  Read the notes above, then press any key to close this window.
if "%NOTE%"=="1" pause >nul
popd
exit /b 0

rem ----------------------------------------------------------------------
rem  Start
rem ----------------------------------------------------------------------
:step_done
"%VPY%" -c "import tkinter" >nul 2>&1
if errorlevel 1 goto selftest_failed
"%VPY%" -c "import sys; compile(open(sys.argv[1], 'rb').read(), sys.argv[1], 'exec')" "%~dp0main.py" >nul 2>&1
if errorlevel 1 goto selftest_failed
if not exist "%VPYW%" goto venv_failed
echo.
echo  Starting Video Segment Editor...
echo  If no window appears, look for a file named app.log in the folder
echo    %LOCALAPPDATA%\VideoSegmentEditor
start "" "%VPYW%" "%~dp0main.py"
if errorlevel 1 goto start_failed
if "%NOTE%"=="1" echo.
if "%NOTE%"=="1" echo  The program is starting. Read the notes above, then press any key to close this window.
if "%NOTE%"=="1" pause >nul
popd
exit /b 0

:check_done
echo.
echo  Check finished. Nothing was installed or started.
popd
exit /b 0

rem ----------------------------------------------------------------------
rem  Problem messages (the window stays open)
rem ----------------------------------------------------------------------
:no_main
echo  PROBLEM: main.py or requirements.txt was not found.
echo  This launcher must stay in the same folder as the program files.
echo  Looked in: %~dp0
echo  Unzip the whole package into one folder and start it from there.
echo.
pause
exit /b 1

:venv_stuck
echo.
echo  PROBLEM: the old private environment could not be removed.
echo  Close any open Video Segment Editor window, then start this file again.
echo  If it keeps failing, delete this folder by hand and start again:
echo    %VENV%
echo.
pause
exit /b 1

:venv_failed
echo.
echo  PROBLEM: the private Python environment could not be created.
echo  Start this file again. If it keeps failing, reinstall Python from
echo  https://www.python.org/downloads/windows/ and keep "tcl/tk and IDLE" ticked.
echo.
pause
exit /b 1

:pip_failed
echo.
echo  PROBLEM: the program packages could not be installed.
echo  Check the internet connection and start this file again.
echo.
pause
exit /b 1

:selftest_failed
echo.
echo  PROBLEM: the program files did not pass a quick self-test, so it was
echo  not started. Start this file again. If it keeps failing, copy the whole
echo  package into a fresh folder. If a file named app.log exists in this
echo  folder, it may explain the problem:
echo    %LOCALAPPDATA%\VideoSegmentEditor
echo.
pause
exit /b 1

:usage
echo  Unknown option: %~1
echo.
echo  Usage:  VideoSegmentEditor.bat           starts the program
echo          VideoSegmentEditor.bat /check    only shows what is installed
echo  Nothing was installed or started.
echo.
pause
exit /b 1

:no_localappdata
echo  PROBLEM: Windows did not provide the LOCALAPPDATA folder.
echo  Sign in to a normal Windows user account and start this file again.
echo.
pause
exit /b 1

:start_failed
echo.
echo  PROBLEM: the program could not be started.
echo  Start this file again. If it keeps failing, delete this folder and
echo  start again:
echo    %VENV%
echo.
pause
exit /b 1

rem ----------------------------------------------------------------------
rem  Subroutines
rem ----------------------------------------------------------------------

rem  :wg <winget arguments>  - runs winget (or only prints the command in a dry run).
rem  The caller sets WGLABEL (the item name) first; a winget error is reported for that item.
:wg
if "%VSE_DRYRUN%"=="1" goto wg_dry
winget %*
if errorlevel 1 goto wg_failed
exit /b 0

:wg_failed
echo          winget reported a problem with %WGLABEL% (code %errorlevel%).
set "NOTE=1"
exit /b 0

:wg_dry
echo          [dry run] winget %*
exit /b 0

rem  :have_winget  - errorlevel 0 when winget exists. In a dry run VSE_FAKE_WINGET=1 / 0 decides.
:have_winget
if not "%VSE_DRYRUN%"=="1" goto hw_real
if "%VSE_FAKE_WINGET%"=="1" exit /b 0
if "%VSE_FAKE_WINGET%"=="0" exit /b 1
:hw_real
where winget >nul 2>&1
exit /b %errorlevel%

rem  :make_list  - sets LIST to the names of the items that are still missing
:make_list
set "LIST="
if "%NEEDPY%"=="1" call :add_list "Python"
if "%NEEDFF%"=="1" call :add_list "FFmpeg"
if "%NEEDVLC%"=="1" call :add_list "VLC player"
exit /b 0

:add_list
if defined LIST set "LIST=%LIST%, %~1"
if not defined LIST set "LIST=%~1"
exit /b 0

rem  :refresh_path  - adds the user PATH from the registry to this window, so a
rem  program that was just installed (Python) is found without a new window.
:refresh_path
if "%VSE_DRYRUN%"=="1" exit /b 0
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%PATH%;%%P"
exit /b 0

:text_python
echo  To install Python by hand:
echo    1. Open https://www.python.org/downloads/windows/
echo    2. Download the newest "Windows installer (64-bit)".
echo    3. In the installer tick "Add python.exe to PATH" and make sure
echo       "tcl/tk and IDLE" stays ticked.
echo    4. Click "Install Now", then start this file again.
echo.
exit /b 0

:text_ffmpeg
echo  To install FFmpeg by hand (the program cannot create videos without it):
echo    1. Open https://www.gyan.dev/ffmpeg/builds/ in your web browser.
echo    2. Download the file ffmpeg-release-essentials.zip.
echo    3. Unzip it. Inside the unzipped folder there is a folder named bin.
echo    4. Create a folder named C:\ffmpeg
echo    5. Copy the bin folder from the unzipped folder into C:\ffmpeg
echo       (afterwards C:\ffmpeg\bin contains ffmpeg.exe and ffprobe.exe).
echo    6. Start this file again.
echo  Or, if winget works on this computer, use the Command Prompt instead:
echo    1. Press the Windows key, type cmd and press Enter.
echo    2. In the Command Prompt window type this line and press Enter:
echo         winget install Gyan.FFmpeg
echo    3. When it has finished, start this file again.
echo.
exit /b 0

:text_vlc
echo  To install VLC by hand (without it there is no video preview):
echo    Download it from https://www.videolan.org/vlc/ and run the installer.
echo    You can still type the start and end times by hand without VLC.
echo.
exit /b 0

rem  :test_exe "<python.exe>"  - errorlevel 0 when it is Python 3.11+ with tkinter
:test_exe
"%~1" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
exit /b %errorlevel%

rem  :show_version "<python.exe>"  - sets PYVER, for example "Python 3.12.4"
:show_version
set "PYVER=Python"
"%~1" --version >"%TMPV%" 2>&1
set /p PYVER=<"%TMPV%"
del "%TMPV%" >nul 2>&1
exit /b 0

rem  :find_python  - sets FOUND (and FOUNDVER) to a working system Python 3.11+
rem  with tkinter. Silent; the caller prints the result.
:find_python
set "FOUND="
call :try_cmd py -3.13
if not defined FOUND call :try_cmd py -3.12
if not defined FOUND call :try_cmd py -3.11
if not defined FOUND call :try_cmd py -3
if not defined FOUND call :try_cmd python
if not defined FOUND call :try_exe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined FOUND call :try_exe "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined FOUND call :try_exe "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
exit /b 0

:try_cmd
%* -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "FOUND=%*"
%* --version >"%TMPV%" 2>&1
set "FOUNDVER=Python"
set /p FOUNDVER=<"%TMPV%"
del "%TMPV%" >nul 2>&1
exit /b 0

:try_exe
if not exist "%~1" exit /b 0
call :test_exe "%~1"
if errorlevel 1 exit /b 0
set FOUND="%~1"
call :show_version "%~1"
set "FOUNDVER=%PYVER%"
exit /b 0

rem  :find_ffmpeg  - sets FFOK and FPOK; adds C:\ffmpeg\bin, Program Files\ffmpeg\bin
rem  or the winget links folder to PATH for this window (and so for the program) if needed.
:find_ffmpeg
set "FFOK=0"
set "FPOK=0"
where ffmpeg >nul 2>&1
if not errorlevel 1 set "FFOK=1"
where ffprobe >nul 2>&1
if not errorlevel 1 set "FPOK=1"
if "%FFOK%"=="1" if "%FPOK%"=="1" exit /b 0
if exist "C:\ffmpeg\bin\ffmpeg.exe" if exist "C:\ffmpeg\bin\ffprobe.exe" set "PATH=C:\ffmpeg\bin;%PATH%"
if exist "%ProgramFiles%\ffmpeg\bin\ffmpeg.exe" if exist "%ProgramFiles%\ffmpeg\bin\ffprobe.exe" set "PATH=%ProgramFiles%\ffmpeg\bin;%PATH%"
if exist "%ProgramFiles(x86)%\ffmpeg\bin\ffmpeg.exe" if exist "%ProgramFiles(x86)%\ffmpeg\bin\ffprobe.exe" set "PATH=%ProgramFiles(x86)%\ffmpeg\bin;%PATH%"
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe" if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\ffprobe.exe" set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where ffmpeg >nul 2>&1
if not errorlevel 1 set "FFOK=1"
where ffprobe >nul 2>&1
if not errorlevel 1 set "FPOK=1"
exit /b 0

rem  :find_vlc  - sets VLCOK when libvlc.dll exists in a standard VLC folder
:find_vlc
set "VLCOK=0"
if exist "%ProgramFiles%\VideoLAN\VLC\libvlc.dll" set "VLCOK=1"
if exist "%ProgramW6432%\VideoLAN\VLC\libvlc.dll" set "VLCOK=1"
if exist "%ProgramFiles(x86)%\VideoLAN\VLC\libvlc.dll" set "VLCOK=1"
exit /b 0
