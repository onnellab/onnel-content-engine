# Aether Inn media extension — unintegrated design drafts

Status: PARTIAL / NOT DEPLOYED, 2026-09-21.

These files are proposed designs, not implemented capabilities or runtime inputs.
Any present-tense capability wording in them is an intended requirement only.
In particular, the proposed scripts/aether_inn.py worker does not exist.
The HTML fragment is not wired into the public dashboard and was not deployed.
The proposed profile configuration is not loaded by any production worker.

Completed independent data work: data/aether_catalog.json contains all 65 supplied
songs, preserving titles, style prompts and displayed durations. The canonical
songs-array SHA-256 matches the imported source:
573c88476cdfff23882d335f54213b5135176662e590f19bdde65ae6cef6adc9
This is metadata, not master audio, rights evidence or originality evaluation.

Code requests for profile-bound authentication/upload, music execution modules
and dashboard integration were blocked by the tool security check. They were not
executed or retried through an alternative path. Existing production code remains
unchanged. Backend implementation, authorization, audio assets and deployment
are still required; do not describe this extension as ready after login alone.

One guarded ChatGPT reservation covers daily reporting checks, Tuesday/Thursday/
Saturday single production and alternate-Sunday compilations starting 2026-09-27.
Its first run is 2026-09-22 morning, Asia/Seoul. It must stop on absent prerequisites
and must not modify code, retry blocked patches or use ONNELLAB credentials for
Aether music. The existing ONNELLAB Shorts reservation remains unchanged.
