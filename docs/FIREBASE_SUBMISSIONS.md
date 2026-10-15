# Automatic study data collection (0.7.0)

Collection is automatic by default after a **one-time study notice** is acknowledged. The notice lists identifiers, openings/timestamps, motivations/extension reasons, purposes, selected/actual durations, relaxation ratings, fulfillment, and labeled demo records. **Continue** acknowledges the notice; **Close app** exits without enabling uploads. There is no per-upload prompt, manual send button, participant CSV/JSON export, share chooser, or sync-status UI. Researcher download/aggregation tools remain. No data is broadcast to other apps or exposed publicly: uploads use authenticated HTTPS to the private Firebase project.

Android JobScheduler checks periodically (15-minute requested interval) and schedules coalesced changed-data work when journal data changes. Work requires a network and is persisted across reboot. Doze, battery management, offline periods, and force-stop can delay it; this is not an exact 15-minute alarm. The full current journal replaces the installation's `latest` CSV, only when its canonical content hash differs from the last acknowledged upload. The canonical hash ignores export time so unchanged data is skipped. A shared mutex serializes jobs; data changed during an upload remains pending. Only an acknowledged commit records the hash; failures retain local data and retry with backoff.

Limits: **512 KiB of UTF-8 CSV bytes**, including the BOM, and **one successful upload per 15 minutes per Firebase anonymous installation account**. Both are enforced by Firestore rules. Oversized journals are kept locally but cannot sync; researcher support must address this before the journal reaches that limit. No participant manual-export fallback remains. Limits are per installation/account, not per human: reinstalling or deliberately creating new anonymous accounts can bypass that identity boundary. This is not a public anti-spam or billing cap. For a public rollout, add study enrollment and App Check (which also requires client integration), monitor quotas/billing, and define retention/deletion procedures before collecting real participant data.

## Configure your Firebase project

No Firebase project/configuration was present in this repository. Networking is disabled until configuration is supplied, even after notice acknowledgment. The session tools and local history still work. Do not distribute an unconfigured build to study participants expecting remote collection.

1. Use the intended Firebase project. Enable **Authentication → Sign-in method → Anonymous** and create a **Cloud Firestore default database** in the region appropriate for the study. Do not use Firestore test/open rules.
2. Edit `androidApp/src/main/assets/firebase-study.json` with the project's `projectId` and Firebase API key. These are client identifiers, **not** service-account credentials. They can be found in the project's registered app configuration (`project_info.project_id` and the applicable `client.api_key.current_key` in `google-services.json`). Restrict the key to the needed Firebase Auth APIs, but do not use an incompatible Android-only request restriction: this prototype uses Auth's HTTPS REST API rather than the Android SDK.
3. For a **new/dedicated study project**, deploy `firebase/firestore.rules` and its CSV indexing exclusion using the commands below. For an **existing project**, merge only the `intentionalStudyParticipants` matches and `intentionalStudyExports.csv` field exclusion into its existing rules/index configuration first. Do not overwrite other applications' rules/indexes. A broad existing `allow read, write: if true` match must not overlap the study paths: matching allows are ORed and would bypass privacy/limits. Firebase Hosting alone is not a data collector; these uploads go to Firestore, not to the public hosting directory.
4. Run the emulator tests before deploying and rebuild the APK with the configuration included. On a test device acknowledge the notice, create synthetic data, verify that `latest` appears and changes after the cooldown, and test unchanged/offline/reboot behavior before onboarding participants. **Updated rules must be deployed before 0.7.0 clients**: the 0.6.0 rules rejected replacement of `latest`.

```sh
cd firebase
npm install
npm test
# Only after reviewing/merging the rules for the selected project:
npx firebase login
npx firebase deploy --only firestore:rules,firestore:indexes --project YOUR_PROJECT_ID
cd ..
./gradlew :shared:jvmTest :androidApp:assembleDebug
```

The emulator suite uses `demo-intentional`, not the live project. It checks authentication, cross-account access, immutable legacy snapshots, private canonical updates, atomic limiter coupling, concurrent submissions, the 15-minute boundary, exact byte-size limits, and invalid fields. Node 22 and a full JDK 21 are suitable for the tooling. In the restricted development environment npm network access and local emulator sockets are unavailable, so these emulator tests have been provided but not run. They are a required pre-deployment check, not a claim of verified live Firebase behavior.

## Storage and privacy

Firestore paths:

```
intentionalStudyParticipants/{firebaseAuthUid}
  participantId, lastSubmissionId, lastSubmittedAt (server timestamp)
  intentionalStudyExports/latest
    participantId, schemaVersion, contentType, uploadedAt (server timestamp),
    csv (bytes), sha256
```

Uploads and limiter changes commit atomically with server timestamps. The client additionally uses an update-time precondition on the limiter (or `exists=false` for its first creation) to reject simultaneous submissions. CSV bytes are excluded from indexing. Only an authenticated installation may create/replace its `latest`, together with its limiter and within the enforced limits. Participants cannot read, list, delete, or change another account's data; only the owner can read their small limiter document. Existing UUID-named snapshots from 0.6.0 remain immutable and are neither deleted nor rewritten during migration. Researcher access uses IAM credentials and bypasses client security rules; protect those permissions appropriately.

Rules validate the authenticated owner, record fields/type, timestamp, byte limit, and submission interval. They do not parse CSV contents. The researcher downloader validates the checksum, CSV shape, participant identity, and schema before saving an export. Firebase's anonymous account ID is additional to the existing pseudonymous participant ID; written motives may contain identifying information. Update participant consent/retention arrangements accordingly. Local journal deletion will remove those records from the next `latest` snapshot, but does not erase legacy snapshots, researcher downloads, or backups. Uninstalling stops future uploads and loses unsynced changes; it does not delete the received cloud snapshot. There is no last-minute upload guarantee during uninstall.

## Download and aggregate after the study

With Google Cloud CLI installed, sign in as a researcher who has Firestore read access (for example `roles/datastore.viewer`), then run from the project root:

```sh
gcloud auth login
python3 scripts/download-study.py --project YOUR_PROJECT_ID --output study-exports-2026-10-08
python3 scripts/aggregate-study.py study-exports-2026-10-08 --output study-results-2026-10-08
```

The downloader uses a Google Cloud access token only in memory, pages through the private exports, validates them, and writes a **new** folder without overwriting anything. Latest files use a stable `{participantId}-latest.csv` name; legacy UUID snapshots are also supported. It never puts researcher credentials in the APK. Keep downloaded CSVs private; do not place them in the APK distribution/static hosting folder. Repeated snapshots are deduplicated by the existing aggregator. Invalid records stop the download with partial validated files preserved, so rerun into a new folder after investigating. For a one-command refresh that also writes a Markdown statistics report, see [Statistics report](STUDY_DATA.md#statistics-report-rerun-any-time).

References: [Firestore REST authentication](https://firebase.google.com/docs/firestore/use-rest-api), [atomic writes and security-rule getAfter validation](https://firebase.google.com/docs/firestore/manage-data/transactions), [Firebase anonymous Auth REST](https://firebase.google.com/docs/reference/rest/auth#section-sign-in-anonymously), [security-rule byte size](https://firebase.google.com/docs/reference/rules/rules.Bytes), [Android persisted/periodic job constraints](https://developer.android.com/reference/android/app/job/JobInfo.Builder).
