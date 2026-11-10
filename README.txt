Video Segment Editor - version 1.0
==================================

CONTENTS
--------
  1. What it does
  2. What you need
  3. Installation, updating and removing
  4. How to use it, step by step (with a first-run walkthrough)
  5. The new video: name, quality and what is converted
  6. FFmpeg and VLC: how they are found and installed
  7. Fast cut or exact cut? (copying versus re-creating the picture)
  8. Troubleshooting, by symptom
  9. What it cannot do, and its measured limits
 10. Cancelling, and closing the window while a video is being created
 11. Questions and answers, glossary, privacy
 12. For developers, files in this package, and the licence
 13. Kratko po-russki (short guide in Russian, see the end of this file)

Quick start in five lines (details follow):
  1. Unzip the package into a folder, double-click VideoSegmentEditor.bat
     (or run VideoSegmentEditor-Setup.exe if you were given that file).
  2. Answer Y once if it offers to install missing programs.
  3. Press "Load Video", then "Mark Start" and "Mark End" for each part.
  4. Press "Create Video" and confirm.
  5. The new file appears next to the original, named "<name> (segmented).mp4".


1. WHAT IT DOES
---------------
Video Segment Editor cuts the parts you want out of a video and joins them
into one new video. You load a video, play it, press "Mark Start" and
"Mark End" to select up to 10 segments, put the segments in the order
you want, and press one button. The result is a new MP4 file with only
those segments, one after the other.

Your original video is never changed, moved, renamed or deleted. The program
only reads it.

It is a segment cutter, not a full video editor: no transitions, no text, no
filters, no audio-only editing.

Typical uses: keep the three good minutes of a long recording, cut the
boring parts out of a lecture or a match, make a short clip from a phone
video, put the best moments of one video in a new order.

The program is free (MIT licence, section 12). Nothing you do in it is sent
anywhere (section 11, "Privacy").


2. WHAT YOU NEED
----------------
- A Windows 10 or 11 computer (64-bit).
- An internet connection the FIRST time you start it (to install what is
  missing: Python, the python-vlc package, FFmpeg, VLC; you are asked once).
  Afterwards the program works offline.
- FFmpeg (with FFprobe). It does the real cutting. REQUIRED to create a video.
- VLC media player. It shows the video preview inside the window. OPTIONAL:
  without VLC you can still type the start and end times by hand.
- Python 3.11 or newer (the normal installer from python.org includes the
  window part, "tkinter", that the program needs). The launcher installs it
  (after your one Y/N) if it is missing. Not needed at all if you use the
  Setup program (section 3, way A).
- Free disk space: see "Disk space" in section 8 and the limits in section 9.
- A computer with at least 8 GB of memory is advisable for 4K video (see the
  limits in section 9).
- A screen of 1366 x 768 or larger is advisable; the window is designed for
  1920 x 1080 (see "Window size" in section 4).

You do NOT need: an account, a licence key, a graphics card, or any
knowledge of video formats.


3. INSTALLATION, UPDATING AND REMOVING
--------------------------------------
There are two ways. Way B (this zip) is the one this package contains.
Which one should you choose?
  - Way A (Setup program) if you were given VideoSegmentEditor-Setup.exe and
    want an ordinary Windows installation with a Start-menu entry. No Python
    is needed.
  - Way B (zip and launcher) if you have only this zip. You can keep the
    program in any folder, even on a USB stick (the settings and the private
    Python environment stay on the computer, section 3, "Removing").

WAY A - Setup program (VideoSegmentEditor-Setup.exe, a separate file, if
you were given one). No Python is needed.
  1. Double-click VideoSegmentEditor-Setup.exe.
     Windows may now show a BLUE window titled "Windows protected your PC".
     This is normal for a program that is not digitally signed. In that
     window click the small words "More info", then click the button
     "Run anyway" that appears. Only do this if you got the file from a
     source you trust.
  2. Setup installs the program for your Windows user only (no
     administrator rights needed), into
     %LOCALAPPDATA%\Programs\Video Segment Editor. It shows the licence, the
     folder, and one optional tick box for a desktop icon (empty by default).
     In the Start menu it creates two entries: "Video Segment Editor" and
     "Video Segment Editor - Read me" (this guide).
  3. Setup checks whether FFmpeg and VLC are installed. If one or both are
     missing, ONE page, titled "Programs the editor needs", lists them with
     their approximate sizes and says that Setup will install them for you.
     The page has no tick box and asks nothing: click Next, then Install.
     After copying the program, Setup installs the missing programs with
     winget (the Windows program installer), with no further questions. It
     needs an internet connection. THIS STEP CAN TAKE SEVERAL MINUTES, and
     the Setup window may look frozen while it says "Installing FFmpeg. This
     can take several minutes and this window may look frozen. Do not close
     it." Wait; do not close it.
     Windows may show one permission window for VLC. Click "Yes". If you
     click "No", VLC is not installed (the program still works, but without
     the video preview).
     If both are already installed, this page does not appear and nothing
     is downloaded.
     If your computer has no winget, the page says so, installs nothing,
     and gives the web addresses for installing by hand.
     If something could not be installed, a message box at the end lists it
     and the addresses. The program is installed in any case and tells you
     in its own window what is missing.
  4. Start "Video Segment Editor" from the Start menu (or tick "Start Video
     Segment Editor now" on the last Setup page).
  For administrators: "VideoSegmentEditor-Setup.exe /VERYSILENT" installs
  the program and, by default, also installs a missing FFmpeg and VLC with
  winget. Adding /NOINSTALLMISSING installs the program only (winget is not
  run). The old switch /INSTALLMISSING=1 is still accepted and changes
  nothing. Even in silent mode someone must click "Yes" in VLC's Windows
  permission window, or VLC is not installed.

WAY B - this zip and the launcher.
1. Unzip VideoSegmentEditor.zip into a folder of your own, for example
   "Documents\Video Segment Editor". Do not run it from inside the zip file
   (right-click the zip, "Extract All...", finish, then open the new folder).
2. Double-click  VideoSegmentEditor.bat
   Windows may now show a BLUE window titled "Windows protected your PC".
   This is normal for a launcher that is not digitally signed. In that window
   click the small words "More info", then click the button "Run anyway" that
   appears. Only do this if you got the zip from a source you trust.
3. The launcher works in a black window:
   a. It first looks at the whole computer ("Checking this computer...") and
      prints one line each for Python 3.11 or newer (with tkinter), FFmpeg
      with FFprobe, and VLC, ending in "OK" or "MISSING".
   b. If anything is missing it shows ONE screen headed "Missing on this
      computer (all free):" that lists everything missing with its
      approximate size (Python 3.12 about 25 MB, FFmpeg about 100 MB, VLC about
      40 MB) and asks ONE question: "Press Y to install, N to skip." On Y it
      installs all of it with winget, one after the other ("Installing 1 of
      2: FFmpeg. Please wait, do not close this window..."), with no further
      questions. This can take several minutes. Windows may show one
      permission window for VLC: click "Yes" (if you click "No", VLC is not
      installed). Then the launcher checks again by itself ("Installation
      finished. Checking again by itself (nothing to close or restart)..."):
      you do NOT need to close the window and start it again, also not after
      Python was installed.
   c. A private Python environment is created (first start only) in
      %LOCALAPPDATA%\VideoSegmentEditor\venv and the package listed in
      requirements.txt (python-vlc) is installed into it ("Creating the
      private Python environment. This happens only once..."). This needs
      the internet.
   d. The program starts ("Starting Video Segment Editor...").
   If you answer N, or your computer has no winget: the launcher prints plain
   instructions for installing each missing item by hand. Python is required,
   so without it the launcher stops; without FFmpeg or VLC the program still
   starts and tells you in its own window what is missing.
4. When everything went well, the program window opens and the black window
   closes by itself. The black window stays open and says "press any key"
   in these cases: you answered N; your computer has no winget; or something
   could not be installed (the program still starts, without FFmpeg or VLC).
   It also stays open when Python is missing and cannot be installed, and
   when the launcher finds a real problem (most of these messages begin with
   the word PROBLEM). Read the notes, then press a key.
   The next start takes a few seconds.

To see what is installed without installing or starting anything, open a
Command Prompt or PowerShell window in the program folder and run
    .\VideoSegmentEditor.bat /check
(in a Command Prompt the leading  .\  is optional; in PowerShell it is
required). It lists what is missing and what a normal start would install,
and ends with "Check finished. Nothing was installed or started."
(Tip: in File Explorer, click the address bar of the program folder, type
cmd and press Enter: a Command Prompt opens in that folder.)

UPDATING TO A NEWER VERSION
  The version number is in the first line of this file (and, for way A, in
  the Windows list of installed apps). To update:
  - Way A: run the newer VideoSegmentEditor-Setup.exe. It installs over the
    old program; your settings are kept.
  - Way B: unzip the newer VideoSegmentEditor.zip into the SAME folder and
    say yes when Windows asks to replace files (or unzip it into a new
    folder and delete the old one). The launcher notices a changed
    requirements.txt and updates the private environment by itself.
  Nothing is lost: your videos are never touched, and your language choice is
  kept in settings.json. The program does not check for updates by itself
  (it never connects to the internet, section 11).

REMOVING THE PROGRAM (UNINSTALL)
  Way A: Windows Settings > Apps > Installed apps (Windows 10: Apps &
  features) > Video Segment Editor > Uninstall. This removes the program,
  the Start-menu entries and the desktop icon. It leaves the folder
  %LOCALAPPDATA%\VideoSegmentEditor (see below).
  Way B: delete the folder into which you unzipped the program. There is no
  installer, no registry entry and no Start-menu entry to remove. Then delete
  the folder %LOCALAPPDATA%\VideoSegmentEditor (see below).
  Where the program keeps its own data (both ways): the folder
      %LOCALAPPDATA%\VideoSegmentEditor
  (type that into the File Explorer address bar; it is normally
  C:\Users\<your name>\AppData\Local\VideoSegmentEditor). It holds:
      venv\          the private Python environment (Way B only), safe to
                     delete: it is rebuilt at the next start
      settings.json  your language choice (very small)
      app.log        the log, with app.log.1 as the previous one (at most
                     about 2 MB together)
      work\          temporary folders of failed or cancelled runs (can be
                     large: delete them if you do not need them)
  Deleting this folder removes everything the program ever stored on your
  computer apart from the program itself and the videos it made. The
  videos it made ("<name> (segmented).mp4" next to your originals) are yours:
  uninstalling never deletes them.
  The helper programs are separate. The launcher and Setup install them with
  winget; they stay when you remove Video Segment Editor, because other
  programs may use them. If you want them gone, and nothing else needs
  them: Windows Settings > Apps > Installed apps, choose FFmpeg (it appears
  as "FFmpeg" from Gyan), VLC media player or Python 3.12, and Uninstall.
  Or in a Command Prompt:
      winget uninstall Gyan.FFmpeg
      winget uninstall VideoLAN.VLC
      winget uninstall Python.Python.3.12


4. HOW TO USE IT, STEP BY STEP
------------------------------
FIRST RUN - WHAT EACH SCREEN SHOWS
  Screen 1 (Way B only), the black launcher window. Lines like
  "Python:  OK", "FFmpeg:  OK", "VLC:     OK" mean all is well; MISSING means
  the launcher will offer to install it (section 3). When all is well the
  black window closes by itself after a few seconds.
  Screen 2, the main window opens, dark grey, with the panda logo and the
  title "Video Segment Editor" in the header, and a small button "RU" at the
  top right (section 4, "The language button"). In the middle is a big dark
  area where the video will play. The line under the header says
  "No video loaded." The status line at the bottom says "Load a video to
  begin." The table "Selected Segments" shows "Marked segments appear here."
  The button "Create Video" at the bottom is greyed out.
  If FFmpeg is not found, the status line says "FFmpeg is not installed."
  and a window "FFmpeg is missing" shows what to do (section 6).
  If VLC is not found, the video area shows "VLC is not installed, so the
  video preview is switched off." with a download link, and a small form
  with two time boxes and the button "Add segment" appears instead of the
  Mark buttons (see the end of this section).
  Screen 3, after "Load Video" and choosing a file: the status line says
  "Reading <file name> ..." for a moment, then "Video loaded." The line
  above the video shows the file name, its length and its picture size (for
  example "holiday.mp4 - 00:03:20.000 - 1920x1080"), the video is ready to
  play in the video area, and you can use the Mark buttons.
  Screen 4, after the first "Mark Start": the Mark Start button turns green
  and shows the time you marked, and the status line says "Start marked at
  00:00:05.000. Move to the end point and press Mark End."
  Screen 5, after "Mark End": a row appears in the table, the counter shows
  "1 / 10", "Total selected" shows the length of the new video, and the
  status line says "Segment 1 added: 00:00:05.000 - 00:00:12.000". The
  "Create Video" button is now active.
  Screen 6, after "Create Video": a question window "Create Video" shows
  the number of segments, the total length, the output file name and its
  folder, and (when needed) the list "What will change in the new video:".
  After you confirm, a progress bar with a percent number appears, with the
  words "Cutting segment 1 of 3", then "Joining the segments", then
  "Checking the finished video".
  Screen 7, the result: "Done." with a green check mark, and below it the
  line "Saved to: <full path>". Open that folder in File Explorer; the new
  video is next to the original.

THE STEPS IN DETAIL
1. Press "Load Video" and choose a video file. The file window offers
   MP4, MOV, AVI and MKV files, or "All files" if you want to try another
   type. Above the video you see: file name - length - width x height
   (for a phone video that is stored rotated, the size as you see it).
2. Watch the video. Buttons: Play, Pause, Stop (Stop goes back to the
   start). These three buttons show only a symbol; hold the mouse over one
   for half a second and its name appears (Play, Pause, Stop). The long
   slider under the video seeks to any point; the numbers next to it show
   the current time and the total length. The small slider is the volume.
3. Move to the point where a segment should BEGIN and press "Mark Start". The
   button turns green and shows the time you marked. (To change the start
   point, just press Mark Start again.)
4. Move to the point where the segment should END and press "Mark End" (its
   second line reads "Set end point"). The segment is added to the table
   "Selected Segments" at once.
   Rules: the end must be after the start; the end cannot be past the end
   of the video (a time marked after "play to the end" is set to the end
   of the video); Mark End without Mark Start is refused ("Press Mark Start
   first, then Mark End.").
   Segments may overlap, and you may use the same footage twice.
5. Repeat for the next segments. The counter shows how many you have, for
   example "3 / 10". The maximum is 10 segments. When the table holds 10,
   the line above the Mark buttons says "Limit of 10 segments reached.
   Delete one to add another."; if you still try to add an 11th, a message
   box "Segment limit reached" says "You can have at most 10 segments.
   Delete one to add another." and nothing is added.
6. Change the list with the buttons under the table:
   - Move Up / Move Down: change the order. The new video follows the
     order of the table, not the order in the original video.
   - Edit: opens a small window to type the Start and End times yourself.
   - Delete: removes the selected row (the Delete key does the same when
     the table has the focus).
   - Clear All: removes every segment (asks first: "Remove all 3 segments
     from the list?").
   "Edit" also opens when you press Enter or double-click a row. In the
   small window Enter means OK and Esc means Cancel.
   Times are written as hours:minutes:seconds, for example 00:01:05.250 (the
   last three digits are thousandths of a second). When typing you may use
   short forms: 1:05 means 1 minute 5 seconds, and 65 means 65 seconds.
   A time that cannot be read gets a message such as "'abc' is not a valid
   time. Use hours:minutes:seconds, for example 00:01:05.250. ...", and
   seconds or minutes of 60 or more are refused ("Seconds must be below 60
   in '1:75'.").
7. "Total selected" shows the length of the new video.
8. Press the big button at the bottom. Its label is "Create Video". It is
   greyed out until the table has at least one segment. A question window
   opens. It shows the number of segments, the total length, the name of the
   new file, its folder and, when the source needs it, the list "What will
   change in the new video:" (see section 5). Its two buttons are "Create
   Video" and "Cancel". Press "Create Video". A progress bar with a percent
   number and a line of text show what is happening ("Cutting segment 2 of
   3", "Joining the segments", "Checking the finished video"). The window
   does not freeze. All other controls are locked until it ends, except the
   language button, which stays enabled.
9. A "Cancel" button appears to the right of the progress bar while the
   video is being created. See section 10.
10. When it ends, the status line shows "Done." with a green check mark and a
   box below it shows "Saved to: <path>" (you can select and copy the path).

Messages in the status line (under the video area) have a small symbol and a
colour so you can tell them apart: a dot = information, a green check mark =
it worked, an orange triangle = a warning (for example "Press Mark Start
first, then Mark End."), a red cross = an error. Warnings about marking and
typing vanish by themselves after 8 seconds, or as soon as you do something
else. A failure or a cancel shows one short sentence in the status line; the
folder with the kept temporary files is named in the box below it, next to an
"Open folder" button that opens that folder in Windows Explorer. The button
disappears when you load another video or start another run.

Other questions the program asks (load another video, clear the list, stop
and close) have "Yes" and "No" buttons in the language of the program.
Loading another video while you have segments asks "Replace the video?"
because the segment list is cleared.

The language button (top right of the window): the interface starts in
English. The button shows the OTHER language: "RU" while the window is in
English, "EN" while it is in Russian. One click switches every text at once,
without restarting and without losing your video or segments. The choice is
saved in settings.json in %LOCALAPPDATA%\VideoSegmentEditor and used the
next time. Times are always written the same way (00:01:05.250).

Without VLC the video area shows a message with the VLC download link, the
playback controls are switched off, and a small form appears in place of
Mark Start / Mark End: type the start and end times and press "Add segment".
If VLC fails three times in a row while you work, the program switches to the
same typing mode and tells you so; your list is kept.

Keyboard: the Delete key removes the selected row of the table, Enter or a
double-click on a row opens "Edit", and in the small Edit window Enter means
OK and Esc means Cancel. (Moving between the other controls with the Tab key
was not checked for every control.)

Window size: the window opens at 1100 x 840 pixels and cannot be made smaller
than 900 x 760 (at the normal 100% Windows display scaling). With a larger
Windows display scaling the program makes the window larger by the same
factor (for example the minimum is 1126 x 951 at 125%) but never larger than
the usable part of your screen, and it opens centred. On a small screen with
150% scaling (for example a 1080p laptop) the video area gets less height
and the table shows two rows with a scroll bar; nothing is cut off.


5. THE NEW VIDEO: NAME, QUALITY AND WHAT IS CONVERTED
-----------------------------------------------------
- Where: in the same folder as the original video.
- Name: <original name> (segmented).mp4
  If that name already exists, the program uses  (segmented 2).mp4, then
  (segmented 3).mp4 and so on. It never overwrites a file. If the original
  name is extremely long, the new name is shortened so Windows accepts it.
- Format: MP4, video H.264, audio AAC. The frame rate of the original is
  kept. The picture size is kept (see "odd sizes" below). If the original
  has no sound, the new video has no sound, and that is not an error.
- Quality: very high. The picture looks almost the same as the original,
  the file starts playing quickly when it is streamed, and you can jump to
  any point of the new video without delay. The sound quality depends on the
  number of sound channels: mono 96 kb/s, stereo 192 kb/s, 5.1 384 kb/s,
  7.1 512 kb/s. (For the curious: H.264 with CRF 18, encoder preset
  "medium", "faststart", a complete picture, a "keyframe", about every
  2 seconds, and AAC sound.)
- Before it says "Done", the program checks the new file: it exists, it is
  not empty, it has a picture (and sound if the original had it), the number
  of audio tracks is the same as in the original, picture and sound end at
  about the same time, the number of frames is what the segments should
  give, and its length matches the sum of your segments (allowed
  difference: 0.5 second plus 0.1 second per segment). If a check fails you
  get an error message, never a false "Done". Every segment is also checked
  right after it is cut, so a damaged source is stopped early.
- The work is done in a temporary folder:
      %LOCALAPPDATA%\VideoSegmentEditor\work\job_...
  It is deleted automatically after a verified success. After a failure or
  a cancel it is KEPT, and the status box shows its path (and the "Open
  folder" button), so nothing is lost. You can delete such a folder yourself
  when you no longer need it. Folders named job_... that are older than 7
  days are removed automatically the next time the program starts.

What is converted (the question window lists each item that applies, under
"What will change in the new video:"):
- HDR video (the extra-bright, high-contrast kind that many new phones and
  cameras record) is converted to normal video (SDR), so the colours look
  right on an ordinary screen instead of grey and washed out. The program
  assumes a typical brightness of the original, so the very brightest
  highlights of unusually bright videos can be flattened. The HDR
  information is not kept. Some Dolby Vision files carry no standard HDR
  information and are not recognised as HDR.
- Video with extra colour depth or colour detail ("10-bit", "4:4:4"), and
  full-range or RGB video, is converted to the normal kind that every
  player understands, with smoothing so that no colour bands appear. The
  right colour information is written into the new file so players show the
  colours correctly.
- Interlaced video (the old TV style, where the picture is made of two
  sets of alternating lines) is made into normal full pictures. The number
  of pictures per second stays the same.
- Odd picture sizes (for example 321 x 241) are cut by one pixel to the next
  even size, because the video format needs even sizes.
- Every audio track of the original is kept, in the same order, with its
  language tag. The question window says "all N audio tracks are kept;
  nothing is lost" when there is more than one.
- NOT kept: subtitle tracks and chapters. The question window says so when
  the original has them ("N subtitle track(s) not kept; the new video has no
  subtitles", "chapters not kept; the new video has no chapter marks").
- Videos with a variable frame rate (some phone and screen recordings) are
  accepted; for them the check of the number of pictures is relaxed.
- Phone videos stored rotated are turned the right way up.

For the curious (technical details of the list above): HDR10 / PQ and HLG
are tone-mapped to SDR BT.709 with the "mobius" curve, assuming a 1000-nit
master (the brightness peak of the source is not read, so a 4000-nit master
can be clipped). 10-bit, 4:4:4, full-range and RGB sources become 8-bit
4:2:0 limited-range, with dithering and colour tags. Interlaced video goes
through the "bwdif" filter.


6. FFMPEG AND VLC: HOW THEY ARE FOUND AND INSTALLED
---------------------------------------------------
FFmpeg is not included in the zip.
The program looks for ffmpeg.exe and ffprobe.exe in this order:
  1. the folders in the Windows PATH (the list of folders in which Windows
     looks for programs),
  2. the winget package folders of your user account
     (%LOCALAPPDATA%\Microsoft\WinGet\Packages\...FFmpeg...),
  3. the winget "Links" folder (%LOCALAPPDATA%\Microsoft\WinGet\Links),
  4. C:\Program Files\ffmpeg\bin and C:\Program Files (x86)\ffmpeg\bin,
  5. C:\ffmpeg\bin.
The launcher looks in PATH, then C:\ffmpeg\bin, the Program Files folders
from item 4 and the winget "Links" folder (it does not search the winget
package folders; winget normally puts its link there). If the launcher finds
FFmpeg in one of these folders it passes it to the program.
If they are not found, the launcher lists FFmpeg on its one "missing" screen
and installs it with winget when you answer Y (the Setup program does the
same on its "Programs the editor needs" page).

To install FFmpeg by hand, choose ONE of these:
  Way 1 (easiest, needs winget):
    a. Press the Windows key, type  cmd  and press Enter. A Command Prompt
       window opens.
    b. Type   winget install Gyan.FFmpeg   and press Enter. Wait until it
       says it is finished.
    c. Close the Command Prompt window, then start the program again.
  Way 2 (download it yourself):
    a. Open  https://www.gyan.dev/ffmpeg/builds/  in your browser and download
       "ffmpeg-release-essentials.zip" (the same file the launcher names). The
       HDR conversion was tested with the winget build (Way 1); if the HDR
       conversion fails with the zip build, use Way 1.
    b. In File Explorer right-click the downloaded zip, choose "Extract All"
       and finish. Open the new folder, then the folder  bin  inside it. It
       holds ffmpeg.exe and ffprobe.exe (and ffplay.exe).
    c. In File Explorer open the C: drive, create a folder named  ffmpeg ,
       and inside it a folder named  bin .
    d. Copy ffmpeg.exe and ffprobe.exe from step b into  C:\ffmpeg\bin .
    e. Start the program again.
The HDR conversion in section 5 needs an FFmpeg build with the "zscale" and
"tonemap" filters. The winget build (Gyan.FFmpeg) has them; a build without
them was not tested.

VLC is looked for in the standard folders "Program Files\VideoLAN\VLC".
If it is missing, the launcher lists it on the same screen and installs it with
winget when you answer Y. Windows may show one permission window for VLC:
click "Yes". If you click "No", VLC is not installed and the program has no
video preview (you can still type the times by hand).
By hand: download it from  https://www.videolan.org/vlc/  (or run
winget install VideoLAN.VLC in a Command Prompt).
The python-vlc package that the launcher installs is only the connection
to VLC; it does not contain VLC itself.
Python and VLC must be the same kind (both 64-bit, which is normal on a
64-bit Windows). A 32-bit VLC is found by the launcher, but a 64-bit Python
cannot use it: install the 64-bit VLC from the website above.

winget is part of Windows 10 (recent versions) and Windows 11. If your
computer has no winget, the launcher says so and prints the web addresses and
steps for installing by hand. To get winget, update "App Installer" in the
Microsoft Store.


7. FAST CUT OR EXACT CUT? (COPYING VERSUS RE-CREATING THE PICTURE)
-----------------------------------------------------------------
There are two ways to cut a video:
  - Fast cut: the program copies the existing picture data without
    recalculating it. It is very fast and loses no quality. But a video is
    stored as a series of complete pictures with small changes in between,
    and a copy can only start at a complete picture. So the cut lands
    slightly EARLY or LATE, and the first moments of a segment can show a
    frozen, grey or black picture.
  - Exact cut: the program re-creates the picture of the segment. It is
    slower (see the speeds in section 9) and the picture is compressed once
    more, although at a very high quality. But each segment starts at the
    frame you chose, and picture and sound stay in sync within the limits
    given in section 9.

Version 1.0 ALWAYS makes exact cuts, because an exact cut matters more than
speed. There is no switch for the fast cut. (The segments are joined at the
end by a lossless copy: that is safe because all segments are created in
exactly the same way. The joins are not perfect; section 9 gives the
measured size of the effect.)
For the curious: the fast cut is "stream copy", the exact cut is
"re-encoding" (H.264, CRF 18), and the complete pictures are called
"keyframes".


8. TROUBLESHOOTING, BY SYMPTOM
------------------------------
Messages are quoted exactly as the program shows them (English interface;
the Russian interface shows the same message in Russian).

A. Starting the program
-----------------------
Nothing happens when I double-click VideoSegmentEditor.bat
  - A blue window "Windows protected your PC" may be waiting: click "More
    info", then "Run anyway" (section 3).
  - You may be running it from inside the zip. Unzip it first.
  - The black window may have opened and closed at once. Open a Command
    Prompt in the program folder and run  VideoSegmentEditor.bat  there to
    keep the messages on the screen.

"PROBLEM: main.py or requirements.txt was not found."
  - The launcher must stay in the same folder as the other program files.
    Unzip the whole package into one folder and start it from there.

"PROBLEM: the private Python environment could not be created."
  - Start the file again. If it keeps failing, reinstall Python from
    https://www.python.org/downloads/windows/ and keep "tcl/tk and IDLE"
    ticked.

"PROBLEM: the program packages could not be installed."
  - The first start needs the internet (to fetch python-vlc). Check the
    connection (and any proxy or firewall) and start the file again.

"PROBLEM: the old private environment could not be removed."
  - Close any open Video Segment Editor window and start the file again. If
    it keeps failing, delete the folder it names
    (%LOCALAPPDATA%\VideoSegmentEditor\venv) by hand and start again.

"PROBLEM: the program files did not pass a quick self-test, so it was not
started."
  - A file of the package may be missing or damaged. Copy the whole package
    into a fresh folder (unzip it again) and start it. app.log (below) may
    explain the problem.

"PROBLEM: Windows did not provide the LOCALAPPDATA folder."
  - Sign in to a normal Windows user account and start the file again.

"Nothing was installed." / "winget (the Windows package manager) was not
found on this computer ..." / "These could not be installed: ..."
  - Follow the by-hand steps the launcher prints (they are the same as in
    section 6). If winget is missing, update "App Installer" in the
    Microsoft Store.
  - If you clicked "No" in a Windows permission window, that program was
    not installed. Start the launcher again; it will offer it again.

The program does not open, or closes at once
  - Look for the file app.log in
        %LOCALAPPDATA%\VideoSegmentEditor
    (type that path into the Windows Explorer address bar). It lists what
    went wrong, with the date and time of each line. The program has no
    console window, so errors go there. If the program cannot start at all,
    it also shows one message box that points to this file. app.log is
    renamed to app.log.1 when it reaches 1 MB, so it never grows without
    limit.
  - Start VideoSegmentEditor.bat again and read the messages in the black
    window; it says what is missing. If the window closes too fast to read,
    run the launcher from a Command Prompt or PowerShell window (section 3).

Antivirus or "Windows protected your PC"
  - The .bat launcher and the Setup program are not digitally signed, so
    Windows shows a blue window "Windows protected your PC" the first time
    (see section 3, way A step 1 and way B step 2: click "More info", then
    "Run anyway"). Only do that for a file from a source you trust.
  - Some antivirus programs also warn about unsigned files. If yours blocks
    the file, check where you got it before you allow it.

The window is too big or too small for my screen
  - See "Window size" in section 4. The window is designed for a screen of
    1920 x 1080; it scales with the Windows display scaling and is limited
    to the usable part of the screen.

B. Loading a video
------------------
"FFmpeg is not installed." (status line) and the window "FFmpeg is missing"
("FFmpeg was not found on this computer. It is needed to read and cut
videos. ...")
  - Install it (section 6) and close and reopen the program. Loading and
    creating videos need both ffmpeg.exe and ffprobe.exe.

"This file could not be read as a video."
  - The file is damaged, is not a video, or FFprobe cannot read it. Try
    playing it in VLC. If VLC cannot play it either, the file is the
    problem.

"Reading this video took too long, so it was stopped. Please try again or
choose a different file."
  - Reading a file takes at most 60 seconds. A file on a slow network drive
    or a very large file can exceed that. Copy the file to your own disk and
    load it from there.

"The video file is in use by another program or access is denied. Close the
other program and try again."
  - Another program has the file open. Close it and try again.

"The original video file was not found any more. Was it moved or deleted?"
  - The file was moved, renamed or deleted after you loaded it.

"FFprobe could not be started. Please check the FFmpeg installation."
  - FFmpeg is installed incompletely (ffprobe.exe is missing or blocked).
    Reinstall it (section 6).

C. Preview and marking
----------------------
No video preview, a message about VLC ("VLC is not installed, so the video
preview is switched off.")
  - VLC is not installed, or it is the wrong bit-version for Python (64-bit
    Python needs the 64-bit VLC). Install it from https://www.videolan.org/vlc/
    and restart the program. Until then you can type times by hand and
    press "Add segment"; creating the video works without VLC.

"The preview could not start for this file. You can still type start and
end times by hand."
  - The file may use a format VLC cannot play. Type the times by hand.

"Press Mark Start first, then Mark End."
  - You pressed Mark End before Mark Start. Press Mark Start first.

"The end time must be after the start time."
  - Move the end point later than the start point (or press Mark Start
    again to set a new start).

"The end time is past the end of the video (...)." and "The start time must
be before the end of the video (...)."
  - A typed time is outside the video. The length of the video is given in
    the message.

"You can have at most 10 segments. Delete one to add another."
  - The limit is 10 (section 9). Delete or edit a segment instead.

D. Creating the video
---------------------
Disk space ("There is not enough free space on drive C:. About 1200 MB is
needed but only 800 MB is free. Free up some space on that drive and try
again.")
  - Before it starts, the program estimates the size of the new video as the
    size of the selected part of the original times 1.5. It needs free
    space of twice that estimate (at least 200 MB) for the temporary folder,
    and the estimate itself (at least 200 MB) for the output folder. If both
    are on the same drive, the two needs are added: three times the
    estimate in all. If there is less, it stops and tells you how many MB
    are needed and how many are free. Free some space and try again.
  - Measured: the temporary folder holds about two times the size of the
    new video at its peak, and the finished file is then copied next to the
    original, so about three times the size of the new video is in use at
    once.
  - "The disk is full. Free up some space and try again." and "The disk is
    full, so the finished video could not be saved." mean the space ran out
    during the work in spite of the check (another program may have used
    it).
  - "The free space on the drive of the folder could not be checked. ..."
    means the folder of the original no longer exists or cannot be opened.

"Cannot save in this folder: it is read-only or not allowed. Choose a video
in a folder you can write to."
  - The new video is saved next to the original, so that folder must be
    writable. Copy the video to a normal folder (for example Documents or
    Desktop) and load it from there. This often happens with files on a
    write-protected drive, a network folder, or a disk in the CD/DVD drive.
  - Also: "Windows did not allow writing there. Please check that the
    folder is not read-only." and "The finished video could not be saved:
    Windows did not allow writing there." Some antivirus programs and
    "controlled folder access" in Windows Security block writing in
    Documents, Pictures or Desktop; allow the program there or choose
    another folder.

"The video was not created" (window title) / "FFmpeg could not process this
video. Try again. If it happens again, try a different video file."
  - The message tells you what failed. The temporary folder with the work so
    far is kept, and its path is in the box below the status line (and in the
    file app.log). Press "Open folder" to see it. Your original is untouched.
    You can start again.

"The finished video has the wrong length (X s instead of Y s). ..." and
messages about frames ("Frames in the finished video: X, expected about
Y. Part of the picture may be missing."), audio tracks ("Audio tracks in
the finished video: X, expected: Y."), "The picture and the sound of the
finished video have different lengths ...", "The picture of the finished
video starts X s late ...", "The finished video has no picture.", "The
finished video has lost its sound. ..."
  - The final check failed, so the file is NOT reported as done. Try again;
    if it repeats, the source file may be damaged or have a broken
    timeline. Test with another file.

"Segment N of M could not be cut correctly: the result is empty or has the
wrong length. The video file may be damaged, ..." and "Segment N produced no
video. Its times may be past the end of the file."
  - A segment that was just cut is shorter than it should be. Check the
    times of that segment (Edit); the length shown for some files is
    wrong, so try cutting a little earlier than the very end.

"Temporary files were kept in: <folder>. They are deleted automatically
after 7 days."
  - This is not an error by itself: it tells you where the work of a failed
    or cancelled run is. You may delete that folder.

The new video is much bigger than the selected part of the original
  - The quality setting (CRF 18) asks for high quality. A low-bitrate
    original (for example an old phone clip) can GROW (section 9). There is
    no switch for a smaller file in version 1.0.

The picture or sound of the new video looks or sounds different
  - Section 5 lists what is converted (HDR, 10-bit, interlaced, odd sizes)
    and section 9 gives the small sound shift at each junction.

The program says "Done." but I cannot find the file
  - Read the line "Saved to: ..." below the status line: it is the full path.
    The file is in the folder of the ORIGINAL video, not in the program's
    folder. If the name existed, it is "(segmented 2)" and so on.


9. WHAT IT CANNOT DO, AND ITS MEASURED LIMITS
---------------------------------------------
What it cannot do:
- More than 10 segments in one video.
- Transitions, effects, filters, text, titles, several video tracks.
- Edit only the sound, or save audio only.
- Fast cut (copying without re-creating the picture): version 1 always
  makes exact cuts.
- Keep subtitles or chapters of the original (they are dropped; the
  question window tells you).
- Keep HDR: HDR video is converted to SDR.
- Save the new video in another folder or under another name from inside the
  program (copy or rename it afterwards in Explorer).
- Choose another quality, codec or container: the output is always MP4,
  H.264, AAC.
- Work on macOS or Linux. Windows only.
- Edit several videos at once, or combine segments of different videos.
- Save the segment list for later. When you load another video, the list is
  cleared (after asking you).
- Play files that VLC or FFmpeg cannot read.
- Stop FFmpeg instantly: Cancel usually works in about a second; closing the
  window can take up to 5 seconds (section 10).

Measured limits. These numbers were measured on one development laptop (an
8-core, 15 W AMD Ryzen 7 laptop with 15 GB of memory, FFmpeg 9.0.1) with
generated test videos. Your computer will differ; a faster desktop can be 2
to 3 times quicker, a 4-core computer 2 to 3 times slower. They are
measurements, not promises.
- Join accuracy. Each segment is encoded on its own and the segments are
  then joined without re-encoding (section 7). At each junction the sound drifts
  about 13 ms later than the picture. After 10 segments the sound is about
  120 ms late, which is at the edge of what people notice; with 3 segments
  (two junctions, about 27 ms) it is not noticeable.
  The measurement was made before the last round of fixes and has NOT been
  repeated since.
- Short sound gaps. At each junction a sine-tone test showed a sound gap of
  21 to 39 ms and a picture timestamp gap of 21 to 61 ms. With speech or
  music this can be heard as a faint tick at a cut; that was not tested with
  real speech or music.
- The new video is checked and rejected when picture and sound end more than
  100 ms (plus 30 ms per segment) apart.
- Speed. The work is almost all video encoding. 1080p at 25 fps takes about
  0.3 s per second of new video (about 3.4 times faster than real time):
  ten 10-second segments took about 30 s. 4K at 30 fps takes about 1.3 s per
  second of new video (slower than real time): ten 10-second segments take
  about 2 minutes. The length of the original and the position of a segment
  in it do not matter. HDR conversion is about 2 times slower than normal
  (measured on a short 1080p clip; 4K HDR will be slower still). Each segment
  adds about a quarter of a second of start-up time.
- Memory. FFmpeg uses about 1 GB for 1080p and about 3.6 GB (4.4 GB peak) for
  4K. It does not grow with the number of segments. A computer with 4 GB of
  memory may fail with 4K video; this was not tested.
- Disk space. See section 8: about three times the size of the new video
  must be free. High-bitrate sources give a new video about as big as the
  selected part of the original. Low-bitrate sources can GROW: in a test, the segments
  of a 0.8 Mbit/s original (about 5 MB) became about 17 MB, because CRF 18
  asks for high quality.
- Time stamps. Cuts are exact to the chosen millisecond only as far as the
  video frames allow: the cut can fall up to one frame (for example 40 ms at
  25 fps) from the time you typed.
- Log and leftovers. app.log is limited to about 1 MB (plus app.log.1).
  Old temporary folders (older than 7 days) are removed at each start.

What was NOT tested (so you know the edges): real HDR footage from a phone
or camera; a real 125% or 150% display; Windows Media Player playback of
the result; the Russian wording by a native reader; a clean computer with no
Python, FFmpeg, VLC or winget (Setup and launcher); speech or music at the
junctions. The manual checklist of the project lists the details.


10. CANCELLING, AND CLOSING THE WINDOW WHILE A VIDEO IS BEING CREATED
---------------------------------------------------------------------
Cancel button. While a video is being created, a "Cancel" button is shown to
the right of the progress bar (it is not there at other times). When you
press it, the program asks "Stop creating the video? Temporary files are
kept and deleted automatically after 7 days." If you answer Yes, the status
line shows "Stopping... please wait.", FFmpeg is stopped (usually within a
second), the status line shows "Cancelled." and the box below it names the
kept temporary folder, with the "Open folder" button. If you answer No,
nothing happens and the work goes on. If the work finishes while the
question is open, the result is shown after you answer.
Your original is never touched. No half-finished file is left next to it.

Closing the window. If you close the window during the work, the program
asks "Stop and close?" ("A video is being created. Stop and close?"). If you
agree, the status line shows "Stopping... please wait." and the program
closes as soon as FFmpeg has stopped, but not later than 5 seconds after you
agreed. The window keeps responding during this time. The temporary folder is
kept. Your original is not touched.

In rare cases, if you close the window at the moment when the finished file
is being copied next to the original, a half-written file named
    <name> (segmented).mp4.part
can remain in the folder of the original video. It is not a usable video and
you can safely delete it.

If the computer loses power or the program is killed in the Task Manager
during the work, the same applies: the original is untouched, the temporary
folder remains (and is removed after 7 days), and a ".part" file may remain.


11. QUESTIONS AND ANSWERS, GLOSSARY, PRIVACY
--------------------------------------------
FREQUENTLY ASKED QUESTIONS

Q1. Does the program change or delete my original video?
A.  No. It only reads it. The new video is a separate file next to it.

Q2. Why is creating the video slower than I expected?
A.  Because it always re-creates the picture (exact cut, section 7). On the
    development laptop 1080p video takes about 0.3 seconds per second of
    new video and 4K about 1.3 seconds (section 9). Close other heavy
    programs to speed it up.

Q3. Can I cut in one go from several different video files?
A.  No. One video at a time. Make one new video per file, then join the
    results in another program if you need to.

Q4. Can I keep more than 10 segments?
A.  Not in one run. Make a first video from 10 segments, then load that
    video and add more, or make several videos.

Q5. Can I choose where the new video is saved or what it is called?
A.  Not inside the program: it is saved next to the original as
    "<name> (segmented).mp4". Move or rename it afterwards in File Explorer.

Q6. Why does the new video have a different size (in MB) from my original?
A.  It is encoded again at a fixed high quality. A high-bitrate original
    gives a file about as big as the selected part; a low-bitrate original
    can give a bigger file (section 9).

Q7. Do I need VLC?
A.  No, but without it there is no preview. You can type the start and end
    times by hand and still create the video.

Q8. Does it work offline?
A.  Yes, after the first start. Only installing Python, FFmpeg, VLC and the
    python-vlc package needs the internet (section 11, Privacy).

Q9. Windows says "Windows protected your PC". Is the file dangerous?
A.  Windows shows that for every program that is not digitally signed (a
    signature costs money). It does not mean the file is a virus. Open it
    only if you got it from a source you trust (section 3).

Q10. The sound is slightly late after a few segments. Why?
A.   Each junction shifts the sound by about 13 ms (section 9). With 3
     segments this is not noticeable; with 10 it can be about 120 ms.
     Fewer, longer segments give less shift.

Q11. My phone video is HDR and the colours look different. Why?
A.   HDR is converted to normal video (SDR) so it looks right on an ordinary
     screen (section 5). The HDR information is not kept.

Q12. Where are the subtitles of my film?
A.   Subtitle tracks and chapters are not kept (section 5). The question
     window tells you before you start.

Q13. Can I stop it while it is working? Is anything damaged if I do?
A.   Yes: press "Cancel" (section 10). The original is untouched and the
     temporary files are kept and removed after 7 days.

Q14. The program asked me to install Python, FFmpeg and VLC. Is that safe?
A.   They are free programs from their official sources, installed by
     winget, the installer that is part of Windows. You are asked once, and
     you can answer N and install them yourself (section 6).

Q15. How do I change the language?
A.   Click the button at the top right ("RU" or "EN"). It switches at once
     and is remembered (section 4).

Q16. Where does the program keep its files?
A.   In the program folder (the program itself) and in
     %LOCALAPPDATA%\VideoSegmentEditor (settings, log, temporary work,
     private Python environment). See "Removing the program" in section 3.

Q17. Can the program cut a video exactly at a given frame?
A.   Within one frame: the cut can fall up to one frame (40 ms at 25 fps)
     from the typed time (section 9).

Q18. How do I report a problem?
A.   Note the program version (first line of this file), your Windows
     version, the exact message, and the last lines of app.log. Do not send
     the video itself. Use the "Issues" page of the project on GitHub if
     you have the link.

GLOSSARY (the few technical words)
  Segment       A part of the video that you mark with a start time and an end
                time.
  FFmpeg        A free program that cuts and converts video. It does the work
                behind the scenes. FFprobe is its companion that reads
                information (length, picture size) about a file.
  VLC           A free video player. The program uses it to show the preview.
  Python        The programming language the program is written in. You do
                not need to know it; the launcher installs it if needed.
  python-vlc    A small helper package that connects the program to VLC.
  winget        The Windows program installer (the "Windows Package
                Manager"), part of Windows 10 and 11.
  Launcher      The file VideoSegmentEditor.bat: it checks the computer,
                installs what is missing and starts the program.
  Re-encode     Create the picture again instead of copying it (exact cut).
  CRF 18        The quality setting. Lower means better; 18 is very high.
  Keyframe      A complete picture in a video; the pictures between keyframes
                store only the changes.
  H.264, AAC    The usual picture and sound formats inside an MP4 file.
  HDR / SDR     High dynamic range (extra-bright video) / standard dynamic
                range (normal video).
  Frame rate    How many pictures per second a video has (for example 25).
  Bit rate      How much data per second a video or sound needs (kb/s or
                Mbit/s).
  Temporary folder  The folder %LOCALAPPDATA%\VideoSegmentEditor\work where
                the program does its work before saving the result.
  PATH          The list of folders in which Windows looks for programs.

PRIVACY
  - Nothing is uploaded. Your videos, the segment list and the new video stay
    on your computer. The program has no account, no tracking, no
    statistics and no advertising, and it does not send any data anywhere.
  - The program itself never connects to the internet. The only network use
    is by other programs, when you agree: winget downloads and installs
    Python, FFmpeg and VLC; pip downloads python-vlc (way B, first start).
    If you click the VLC download link in the program, your web browser
    opens that page (https://www.videolan.org/vlc/).
  - What is stored on your computer: your language choice (settings.json),
    the log (app.log: dates, times, program messages and error details; it
    can contain the path of a video you loaded), and temporary files of
    failed or cancelled runs. All of it is in
    %LOCALAPPDATA%\VideoSegmentEditor and nothing leaves it. Look at
    app.log before you send it to anyone.
  - Nothing is installed or changed anywhere else except what you approve
    (Python, FFmpeg, VLC via winget) and, with Setup, the program itself and
    its Start-menu entries.


12. FOR DEVELOPERS, FILES IN THIS PACKAGE, AND THE LICENCE
----------------------------------------------------------
THE STANDALONE EXE AND THE SETUP PROGRAM
Besides this zip there is a Setup program, VideoSegmentEditor-Setup.exe. It
is NOT inside this zip. It holds a PyInstaller ONE-FOLDER build of the
program (its own Python, tkinter, python-vlc and the assets), wrapped by an
Inno Setup installer that also installs a missing FFmpeg and VLC with winget
(see section 3, way A). It is built from the project folder (the GitHub
repository), not from this zip, with:

    powershell -NoProfile -ExecutionPolicy Bypass -File build_installer.ps1

You need Python 3.11+ and Inno Setup 6 (winget install -e --id
JRSoftware.InnoSetup --scope user). The script runs the tests first, builds
in a private environment and writes VideoSegmentEditor-Setup.exe.

Notes:
  - The EXE does NOT contain VLC and FFmpeg. VLC must still be installed on
    the computer (64-bit, like the EXE), and FFmpeg must still be found
    (section 6). The Setup program takes care of both by itself.
  - The EXE has no console; its log is %LOCALAPPDATA%\VideoSegmentEditor\app.log
    as before.
  - The Setup and the EXE were tested on the development computer only
    (silent install, start, uninstall). Test them on a clean computer, with
    and without FFmpeg, VLC and winget, before giving them to anyone.

FILES IN THIS PACKAGE
The package has 14 files:
  VideoSegmentEditor.bat   Launcher: checks the computer, installs what is
                           missing (Python, FFmpeg, VLC; one question), sets
                           up python-vlc, then starts the program.
  README.txt               This file.
  LICENSE                  The MIT licence (the terms of use).
  requirements.txt         The Python package list (python-vlc).
  main.py                  Start of the program, version number, log file.
  gui.py                   The window and all its controls.
  i18n.py                  English and Russian texts, saved language choice.
  create_flow.py           Small helper for the "Create Video" progress and
                           for removing old temporary folders.
  segment_manager.py       The segment list, its rules, time reading/writing.
  video_player.py          The VLC player connection.
  video_processor.py       Finding FFmpeg, cutting, joining, checking.
  assets\logo.png          Logo (source copy).
  assets\logo.ico          Logo in the title bar and taskbar.
  assets\logo_header.png   Logo at the exact size shown next to the title.

Created while it runs (not in the package), all under
%LOCALAPPDATA%\VideoSegmentEditor :
  venv\          the private Python environment
  settings.json  your language choice
  app.log        log with time stamps (and app.log.1, the previous one)
  work\          temporary folders; empty after a successful run

THIRD-PARTY PROGRAMS (not part of this package)
  FFmpeg (https://ffmpeg.org) does the cutting; it is installed separately
  and is licensed under the LGPL or GPL depending on the build (the Gyan
  "full" build is GPL). VLC media player (https://www.videolan.org) is
  licensed under the GPL, and its engine libVLC under the LGPL. python-vlc
  is licensed under the LGPL (check upstream licence). Python is under the
  PSF licence. The Setup program is built with PyInstaller (GPL with an
  exception that allows bundling any program) and Inno Setup (its own free
  licence). Their licences apply to them, not to this program; check the
  upstream licence of each before you redistribute them.

LICENCE
Licence: MIT License. Copyright (c) 2026 Michael Yeruhimovich. You may use,
copy, change and share the program under the terms in the file LICENSE. The
program is provided "as is", without warranty.

This program was built with the help of Claude Code (an AI coding assistant
by Anthropic) and was tested by its owner.


13. KRATKO PO-RUSSKI (КРАТКОЕ РУКОВОДСТВО НА РУССКОМ)
----------------------------------------------------
Что это. Video Segment Editor вырезает нужные фрагменты из видео и склеивает
их в один новый файл MP4. Исходное видео никогда не меняется.

Как переключить язык. В правом верхнем углу окна есть кнопка "RU" (пока
интерфейс английский). Нажмите её - весь интерфейс станет русским, а кнопка
покажет "EN". Видео и список фрагментов при этом не теряются. Выбор языка
сохраняется и действует при следующем запуске.

Быстрый порядок работы:
  1. Запустите VideoSegmentEditor.bat (при первом запуске он покажет одним списком
     всё недостающее - Python, FFmpeg, VLC - и задаст один вопрос: установить ли).
     Если Windows покажет синее окно "Windows protected your PC", нажмите
     "More info", затем "Run anyway" (файл не имеет цифровой подписи). То же
     относится к программе установки VideoSegmentEditor-Setup.exe (отдельный
     файл): ей не нужны Python и права администратора.
  2. Нажмите "Загрузить видео" и выберите файл (MP4, MOV, AVI, MKV).
  3. Найдите начало фрагмента и нажмите "Отметить начало".
  4. Найдите конец и нажмите "Отметить конец" - фрагмент появится в списке.
     Всего можно выбрать не более 10 фрагментов.
  5. Кнопками "Вверх" и "Вниз" задайте порядок, "Изменить" - введите время
     вручную (например 1:05 или 00:01:05.250), "Удалить" и "Очистить список".
  6. Нажмите "Создать видео" (кнопка активна, когда в списке есть
     хотя бы один фрагмент) и в окне вопроса нажмите "Создать видео". Новый
     файл появится в той же папке: "имя (segmented).mp4", затем
     "(segmented 2)" и т.д. Путь к файлу показан под строкой состояния.
  7. Пока видео создаётся, справа от полосы прогресса есть кнопка "Отмена".
     Она спрашивает подтверждение и останавливает работу (обычно за секунду).
     Временные файлы сохраняются, кнопка "Открыть папку" покажет их папку.

Без VLC предпросмотра нет, но время начала и конца можно ввести вручную и
нажать "Добавить фрагмент"; видео создаётся и без VLC. FFmpeg нужен обязательно.
Если что-то не работает, смотрите файл app.log в папке
%LOCALAPPDATA%\VideoSegmentEditor и английский текст выше (раздел 8).
Программа всегда перекодирует видео (H.264, CRF 18, звук AAC; для стерео
192 kb/s): это медленнее, зато разрез точный. Склейка не идеальна: на каждом
стыке звук сдвигается примерно на 13 мс (около 120 мс после 10 фрагментов).
Видео HDR преобразуется в обычное SDR, 10-битное и чересстрочное видео
приводится к обычному, все звуковые дорожки сохраняются; субтитры и главы не
сохраняются. Для 4K-видео нужно много памяти (до 4,4 ГБ) и места на диске
(примерно втрое больше размера нового видео). Подробности, измеренные
пределы и условия лицензии (MIT) - в английском тексте выше (разделы 5, 9, 12).
