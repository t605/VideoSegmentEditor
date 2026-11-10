# Draft: post for Facebook groups about Claude / building tools with AI (English)

DRAFT ONLY. Nothing has been posted. The link to https://github.com/t605/VideoSegmentEditor is already in the text. Post only after the repository is PUBLIC and the Release with the zip is published (open the link in a private window to check).
This is the English version of `facebook-claude-groups-post.he.md` (same structure and content).

## Text to paste

I built a small Windows tool with Claude Code and I would love some feedback on it.

**Video Segment Editor**: you load a video, play it, press Mark Start and Mark End to choose up to 10 segments, put them in the order you want, click one button, and get ONE new MP4 file that contains only those segments.

[Screenshot 1: the main window with a neutral video and a few segments marked in the table]

Why I built it: I wanted exact cuts without learning a full video editor.
- Up to 10 segments, in any order
- Every segment is re-encoded (H.264 / AAC), so the cut is exact and not "close to the nearest keyframe"
- The original file is never changed, moved or deleted. The result is saved next to it under a new name and never overwrites a file
- The program checks the finished file (length, picture, sound) before it says "Done"
- English and Russian interface

[Screenshot 2: the finished state: the Done message and the new file]

How to install: download VideoSegmentEditor.zip from the Releases section of the GitHub page, unzip it into a folder of your own and double-click VideoSegmentEditor.bat. The launcher checks what is missing (Python, FFmpeg, VLC), shows everything on one screen and asks ONE question before it installs anything (through winget; it needs internet and can take a few minutes). The files are not digitally signed, so Windows may show a blue "Windows protected your PC" window: click More info and then Run anyway (only if you downloaded the file from a source you trust). A Setup (.exe) installer exists too, but I have not tested it enough yet, so it is not published.

Limits, honestly:
- Windows only. You need internet if FFmpeg, VLC or Python are missing
- It cuts segments; it is not a video editor: no transitions, text or filters
- The output is always MP4 (H.264 + AAC). HDR is converted to SDR
- Without VLC there is no preview, but you can type the times by hand
- I measured speed on one laptop only: 1080p about 3.4 times faster than the video's length, 4K slower than the video's length
- The window itself, real VLC playback and the launcher's install steps were tested by hand on my own computer only (it already had Python, FFmpeg and VLC). There are 444 automated tests (all pass, one is skipped)

How it was built: written with Claude Code, with automated tests and several review rounds. I set the rules (the original is read-only, always re-encode, verify before Done) and Claude wrote most of the code. I read the results, not every line.

Please try it: https://github.com/t605/VideoSegmentEditor
Tell me what broke, what was unclear, and which one feature you would add. Bug reports go in Issues on the GitHub page.

## Screenshots to attach (outside the pasted text)

Both screenshots already exist in the project folder `docs\launch\screenshots`. Attach them to the post yourself, in this order:

1. `screenshot-1-main.png`: the main window with a neutral or free-to-use video and 3 segments marked in the table.
2. `screenshot-2-done.png`: the finished state, the Done message and the new file beside the original.

Before posting: open each image and check the title bar, the folder path, the taskbar (user name) and the video content itself. If a local path or a user name is visible, take the screenshot again.

## Group-rule reminders

- Read the group rules first. Many groups forbid self-promotion, or require a certain day or tag. If you are not sure, ask an admin before posting.
- Say clearly that it is your own project and that it was built with Claude Code.
- Do not post the same text in many groups at once. Adjust it a little for each group.
- Answer comments politely and honestly, and write "not tested" where that is true.
- Do not share other people's private videos or screenshots.
- No personal details (email, phone, local folder paths) in the text or in the images.
- After posting: click the link once, logged out, to check that it opens.
