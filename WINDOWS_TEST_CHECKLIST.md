# SpaceMedic 2.1 — Windows Performance Test Checklist

Thank you for testing. Start with read-only checks. Do not remove real data until scan accuracy is confirmed.

## 1. Launch and baseline

1. Extract the ZIP to a normal folder.
2. Double-click `SpaceMedic.bat`.
3. Confirm **Installed apps** loads without freezing the interface.
4. Select your user folder, for example `C:\Users\YourName`.
5. Click **Analyze** and record the duration shown in the status line.
6. Confirm Largest items, Projects, Treemap, Changes and Junk tabs open normally.

Expected: the first scan says the Changes tab is a baseline. Protected/inaccessible paths may increment the error count but must not stop the scan.

## 2. Change tracking

1. Create a temporary 20–100 MB file inside a test folder under your user profile.
2. Scan the same root again.
3. Open **Changes**.
4. Confirm total-size growth and the new/grown item are reasonable.
5. Delete the temporary test file yourself and scan once more.

Do not expect Changes to be a forensic full index: it compares retained top results and total scan size.

## 3. Treemap

1. Open **Treemap**.
2. Click a folder block to zoom.
3. Use **Back**.
4. Double-click a block to reveal it in Explorer.
5. Switch between **Folders** and **File types**.

Expected: no external graphics libraries or network access are required.

## 4. Fast scan

1. Select the same location used for the baseline.
2. Click **Fast scan**—no extra application is required.
3. Record duration, total size, file count and folder count.
4. Compare the figures and largest folders with the standard **Analyze** result.

Expected: without an optional MFT provider, the status line says `parallel-native` and SpaceMedic scans independent top-level branches concurrently. Totals should match the standard scan, subject to files changing while the scans run.

Optional: if you already use WizTree, independently installed it from its official source after reviewing its licence, and run SpaceMedic as Administrator, SpaceMedic can detect it and use documented CSV/MFT export. It validates and removes the temporary CSV. SpaceMedic does not redistribute or license WizTree for you.

## 5. Controlled duplicate test

1. Create a test folder.
2. Put three copies of the same 2–10 MB non-important file in it.
3. Add another file of the same size but different content.
4. Select the test folder and click **Find duplicates**.
5. Confirm only byte-identical copies are grouped.
6. Try selecting every copy: SpaceMedic should block deletion.
7. If desired, recycle one test copy and confirm at least one remains.

## 6. Scan cancellation and responsiveness

1. Start a large built-in scan.
2. Click **Stop**.
3. Confirm the UI remains responsive and scanning stops safely.
4. Start a new scan afterward.

## 7. Diagnostic bundle

1. Click **Test diagnostics** at the bottom.
2. Save the ZIP.
3. Open it and manually review `diagnostics.json`.
4. Confirm it contains versions, platform information and redacted action timings only.
5. Confirm it does **not** contain file contents, project source, browser history, app inventory, credentials or a Registry dump.

Share the diagnostic ZIP only after your own review. Helpful screenshots: main metrics after built-in scan, after Fast NTFS scan, Changes tab and any error dialog.

## Bug report template

- Windows version:
- SpaceMedic version:
- Standard user or Administrator:
- Scan root and filesystem (you may redact the username):
- Built-in duration/counts:
- Fast NTFS duration/counts (if tested):
- Expected behavior:
- Actual behavior:
- Reproduction steps:
- Screenshot attached: yes/no
- Reviewed diagnostic bundle attached: yes/no
