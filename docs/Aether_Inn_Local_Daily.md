# Aether Inn Local Daily Worker

## Purpose

The daily Aether/YouTube operations path must not depend on a scheduled ChatGPT
turn successfully dispatching a Remote Desktop terminal command. Scheduled tool
orchestration can reject a terminal call before it reaches the worker Mac even
when Desktop Commander, the repository, Keychain, and the same command are healthy.

The root architecture therefore separates execution from reporting:

1. macOS `launchd` starts `scripts/aether_daily_local.py` locally each morning.
2. The local worker owns operations that require the Mac user session, Keychain,
   Google ADC, MYBOX, ffmpeg, or the durable Aether queues.
3. The scheduled ChatGPT task reads the worker's durable result and handles
   GitHub-hosted source refreshes, store-review policy, and final `/ops/`
   reconciliation/deployment. It does not dispatch the local Aether shell path.

This is an execution-boundary fix, not a relaxation of any safety gate.

## Local schedule and result

The installed user LaunchAgent is `com.onnellab.aether-daily-local` and starts at
06:20 Asia/Seoul so the 07:00 operations pass can consume its result while leaving
time for the fail-closed 09:00 Tuesday/Saturday publication boundary.

The durable local result is:

    ~/Library/Application Support/ONNELLAB/content-engine/daily-aether/result.json

The result contains status, safe worker outputs, exact blockers, and timestamps.
It must never contain OAuth tokens, client secrets, refresh/access tokens,
authorization headers, Keychain payloads, service-account JSON, or private keys.

## Local responsibilities

Every normal run uses current `main` only after a clean fast-forward check. A dirty,
diverged, or locally-ahead content-engine checkout fails closed rather than using
unknown code. The worker then:

- refreshes ONNELLAB and Aether Inn private YouTube reports independently;
- refreshes the public-safe YouTube ops snapshot and AI-provider pricing status;
- commits and pushes only those expected local operational snapshots;
- dispatches and waits for the canonical `Sync app operational status`,
  `Refresh AI Operations Sources`, and `Sync Store Reviews` GitHub Actions in
  that order, then fast-forwards local `main`; the final review workflow rebuilds
  and deploys `/ops/` from the combined hosted and local snapshots;
- reconciles existing durable Aether single and compilation jobs;
- synchronizes the six canonical Aether playlists idempotently;
- on Tuesday/Saturday before 09:00 KST, processes the first actually-missing
  canonical backlog WAV, or uses the canonical Lyria worker only after backlog
  exhaustion and readiness checks;
- on every other Sunday beginning 2026-09-27, invokes at most one canonical
  existing-track compilation worker.

All music generation, cover, render, upload, thumbnail, publishAt, public-inventory
cross-check, same-video reconciliation, rights gates, and playlist classification
remain owned by the canonical repository workers. The daily wrapper does not
reimplement or weaken those contracts.

## Failure behavior

The worker is single-instance. It records a blocker and stops or skips the affected
stage when repository state, credentials, source WAVs, publication timing, worker
readiness, or canonical worker results are unsafe. It never compensates for a stale
09:00 single slot by publishing immediately, never creates a replacement upload to
escape an uncertain durable session, and never launches interactive authorization.

`--probe` performs a non-paid connectivity/readiness check. It may refresh read-only
YouTube reports but never generates music, renders media, or publishes a video.
