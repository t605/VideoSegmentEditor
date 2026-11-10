# Owner checklist: first public release with GitHub Desktop

Claude does not run git commands. You do every step below. Do not make the repository public until step 8.

## 0. Check the repository visibility first
The first commit already exists and is on `origin/main`. Before anything else open the repository page on GitHub (logged in) and look at the label next to its name (Private or Public).
- [ ] Private: nothing has leaked yet; go on with step 1.
- [ ] Public: the old commit with the private files is already readable by anyone. Treat the history decision in step 4 as urgent (switch the repository to Private in Settings > General > Danger Zone while you decide).

## 1. Before you touch git
- [ ] Close any program that has the project files open.
- [ ] Make a backup copy of the whole project folder (outside the folder). Published history cannot be taken back, so a backup is cheap insurance.
- [ ] Run the tests once: `python -m unittest discover -s tests` (expect OK; about 3 minutes on the development PC).
- [ ] Look through the files that will be published for personal data (your name is meant to appear only in the LICENSE and README as the author; no local folder paths, e-mail addresses or Windows user names).

## 2. Untrack the private and scratch files (they stay on your disk)
`.gitignore` already lists `.superpowers/`, `prompt.txt` and `mock screen.png`, but ignoring does NOT remove a file that git already tracks. In GitHub Desktop:
- [ ] Open the Changes tab. If `.superpowers/...`, `prompt.txt` or `mock screen.png` appear as "modified" (not "new"), they are tracked.
- [ ] Untrack them. If your GitHub Desktop version has no menu for it: Repository menu > Open in Command Prompt, then run `git rm --cached -r ".superpowers"`, `git rm --cached prompt.txt` and `git rm --cached "mock screen.png"`. This removes them from git only, not from your disk.
- [ ] Confirm they show as deleted in the pending commit and the files still exist in the folder.
- [x] Decision on `CLAUDE.md`: DECIDED 2026-11-09, it is in `.gitignore` and stays local (it was never committed, so no `git rm --cached` is needed). Just check that it does not appear in the Changes list.
- [x] Your full name stays (licence line, README, Setup publisher): DECIDED 2026-11-09.
- [x] `VideoSegmentEditor-Setup.exe` is stored next to the zip in the Finished tools folder: DECIDED 2026-11-09.

## 3. Renormalize line endings
`.gitattributes` was changed (CRLF for .bat/.ps1). Make git apply it:
- [ ] Repository menu > Open in Command Prompt, run `git add --renormalize .`
- [ ] In GitHub Desktop check that files are not listed as changed for no reason. The warning "LF will be replaced by CRLF" is harmless.

## 4. Decide about history (decide ONCE, before going public)
The first commit already holds `.superpowers/` (with local paths), `prompt.txt` and `mock screen.png`, and it is on `origin/main`. Removing the files in a new commit does NOT remove them from that commit; anyone can read old commits. So "just untrack the files" is not enough for a public repository.

Option A - recreate the repository (recommended).
- Create a new empty GitHub repository (or delete and recreate the old one), copy the cleaned project files (NOT the `.git` folder) into a new folder, add it in GitHub Desktop, commit once as "Version 1.0", publish.
- Pros: nothing old can leak; a tidy first commit; the simplest safe way.
- Cons: you lose the old commit messages (there is only one commit, so little is lost).

Option B - rewrite history in place with `git filter-repo`.
- Removes the three paths (and `CLAUDE.md` if you decided so) from every commit, then a force push replaces `origin/main`.
- Pros: keeps the commit history.
- Cons: command line only, needs `git filter-repo` installed, a force push, and is easy to get wrong. With one commit it gives almost nothing over option A.

Option C - keep the history and only untrack: NOT recommended, because the old commit stays readable.

Recommendation: A. Your choice: ______

## 5. Commit
- [ ] Review the Changes list: no zip, no `.exe`, `app.log`, `settings.json`, venv, `__pycache__`, `.superpowers`, `prompt.txt`, `mock screen.png` (and `CLAUDE.md` if you decided to ignore it).
- [ ] Required by the project rules before the first public push: run the `senior-engineer-reviewer` (private-data check).
- [ ] Summary "Version 1.0", commit to main.
- [ ] Publish the repository with "Keep this code private" still CHECKED.

## 6. Community files
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md` are in the commit.
- [ ] Decide whether to copy `docs/release/CONTRIBUTING-note.md` to the repository root as `CONTRIBUTING.md` (GitHub then links it automatically).
- [ ] On GitHub: About (gear icon): paste the description and topics from `repo-description-and-topics.md`.

## 7. Make the Release
- [ ] Build the zip: `powershell -NoProfile -ExecutionPolicy Bypass -File build_release.ps1` (writes `VideoSegmentEditor.zip` into `Finished tools\VideoSegmentEditor`).
- [ ] Build the Setup program: `powershell -NoProfile -ExecutionPolicy Bypass -File build_installer.ps1` (needs Inno Setup 6: `winget install -e --id JRSoftware.InnoSetup --scope user`). It writes `VideoSegmentEditor-Setup.exe` into the same folder as the zip.
- [ ] Setup rehearsal: do section N of `docs/test-checklist.md` (launcher N1-N8, Setup N9-N22) on a clean PC or a clean Windows user account if you can, and fill in Result and Date. Until it is done, Setup is tested on the development PC only and the release notes say so.
- [ ] Test the zip: unzip into a new folder and run `VideoSegmentEditor.bat /check`.
- [ ] GitHub: Releases > Draft a new release. Tag `v1.0`, target main, title "Video Segment Editor 1.0".
- [ ] Paste the text of `release-notes-v1.0.md` (change the "tested only on the development PC" line if the rehearsal found more).
- [ ] Attach `VideoSegmentEditor-Setup.exe` and `VideoSegmentEditor.zip` (zips and exes are git-ignored, so they go on the Release page only).
- [ ] The release notes already explain the blue "Windows protected your PC" window (More info, then Run anyway) because the files are unsigned; keep that paragraph.
- [ ] Save as draft; publish the release after step 8.

## 8. Make the repository public
- [ ] Settings > General > Danger Zone > Change visibility > Public. Read the warning: this is the point of no return for history.
- [ ] Settings > General > Features: Issues enabled. Discussions optional.

## 9. Verify (open the repository in a private window, not logged in)
- [ ] The page opens, README.md renders, the licence shows as MIT.
- [ ] No `.superpowers`, `prompt.txt`, `mock screen.png` in the file list or in "Go to file".
- [ ] Open a few old commits (History) and look for private data.
- [ ] The Release is visible; download the zip and `VideoSegmentEditor-Setup.exe`, check sizes, run once.
- [ ] Issues > New issue shows the two templates.
- [ ] Replace every `[GITHUB RELEASE LINK]` in the launch drafts with the real release URL, then post.
