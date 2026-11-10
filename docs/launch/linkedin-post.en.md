# Draft: LinkedIn post (English)

DRAFT ONLY. Nothing has been posted. The link to https://github.com/t605/VideoSegmentEditor is already in the text. Post only after the repository is PUBLIC and the Release with the zip is published (open the link in a private window to check).

## Text to paste

I just published my first open-source tool, built with Claude Code: Video Segment Editor, a free Windows-only video segment cutter.

The problem: you have a long recording and want only a few parts of it as one clean video, without learning a full editor.

What it does:
- Load a video, play it, mark up to 10 start/end segments
- Reorder them and create ONE MP4 with a single click
- Cuts are exact (every piece is re-encoded), the original file is never touched, and the result is checked before the program says "Done"
- English and Russian interface
- Install from a zip: a launcher checks for Python, FFmpeg and VLC, lists what is missing on one screen, asks one question and installs it (a Setup .exe exists but is not published until I have tested it more)

What I learned building it with an AI coding tool:
1. Write the rules first (original is read-only, never overwrite, verify the result). The tool followed them well.
2. Tests matter more than speed: 444 automated tests found problems a quick look never would.
3. Some things only a human can check: real video playback, screen scaling, the launcher paths. I tested those by hand, and the project states plainly what I did not test.

Honest limits: Windows only; a segment cutter, not a video editor; MP4 output only; speed measured on one laptop.

Try it and tell me what breaks: https://github.com/t605/VideoSegmentEditor

## Hashtag options (pick one set)

- A: #ClaudeCode #OpenSource #Python
- B: #AIAssistedDevelopment #VideoEditing #BuildInPublic
- C: #Windows #FFmpeg #SideProject

## Screenshots (two; they already exist in `docs\launch\screenshots`)

1. `screenshot-1-main.png`: main window with a neutral test clip and 3 segments. Use this one first: LinkedIn shows the first image large.
2. `screenshot-2-done.png`: the "Done" state with the new file beside the original.
Before posting, open both and check that no folder path, Windows user name or private footage is visible. Add alt text describing each image.

## Reminders

- Say "built with Claude Code" and keep the limits line.
- LinkedIn cuts text after about 3 lines: the first two sentences must carry the point.
- The link can go in the post or in the first comment; either is fine.
- Do not tag people or companies without their agreement.
- No personal data or private footage in text or images.
