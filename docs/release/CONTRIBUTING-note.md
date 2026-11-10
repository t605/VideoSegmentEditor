# Contributing (minimal note)

Thank you for your interest in Video Segment Editor. This is a small personal project; replies may take a few days.

## Reporting a bug
Use the "Bug report" form on the Issues page. Include the program version (README.txt header), your Windows version, whether FFmpeg and VLC are installed, the steps you took, and the last lines of `app.log` from `%LOCALAPPDATA%\VideoSegmentEditor` (remove anything private first). Do NOT attach videos that are private or belong to other people.

## Asking for a feature
Use the "Feature request" form. The project is deliberately a segment cutter, not a full video editor, so requests for transitions, effects or text are likely to be declined.

## Code changes
Open an issue first so we can agree on the idea. In short:
- Run `python -m unittest discover -s tests`; all tests must pass.
- Every visible text goes through `i18n.py` with keys in both English and Russian.
- Long work never runs on the GUI thread.
- The source video must never be modified.
- Keep the existing structure (one shared segment logic in `segment_manager.py`).

## Security
If you find a problem that could harm users, please do not post details publicly; open an issue asking for a private way to report it, without the details.

## Licence
By contributing you agree that your contribution is under the MIT licence of this project.
