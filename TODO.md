# Audio Recognition Evaluation TODO

This is the working checklist derived from the repository review on 2026-07-31. Tick an item only when the implementation, verification evidence, and documentation update are complete.

## Current assessment

Strict evidence-based score at review time: **5/9**.

| Area | Current score | Main reason |
|---|---:|---|
| Correctness | 1.5/3 | Recognition works through provider integrations, but accuracy is unmeasured and several runtime paths are fragile. |
| Engineering | 2/3 | The module split and basic CI are good, but production hardening and deeper browser-state coverage remain open. |
| Documentation | 1/2 | The structure is strong, but the documents mix planned product architecture with implemented functionality. |
| Distinctiveness | 0.5/2 | The project is a capable Shazam-style integration, not yet a novel recognition system. |

Do not raise these scores based on screenshots or placeholder metrics alone. Update them only after the evidence gates below are satisfied.

## Ordered repository-polishing roadmap

Complete these main tasks in order. A main task may be ticked only after its subtasks have implementation or evidence support. The detailed P0/P1/P2 checklists below remain the source of implementation detail; this section is the execution order.

### Main task 1 — Real-world benchmark

- [ ] Provide 30 licensed/source tracks across multiple genres and eras, with stable identifiers, title, artist, duration, source, and provenance notes.
- [ ] Add `ACOUSTID_API_KEY` and `AUDD_API_TOKEN` locally without committing or exposing secrets.
- [ ] Record 90 speaker-to-microphone clips: 4s, 8s, and 15s per source.
- [ ] Include clean, partial, re-encoded, noisy, volume-changed, and live/microphone conditions where legally practical.
- [ ] Cache raw provider responses or normalized results to avoid unnecessary API quota use.
- [ ] Run RapidAPI/Shazam, AcoustID, AudD, and the local fingerprint backend independently.
- [ ] Report top-1 accuracy using stable identifiers, with exact denominators overall and by clip length.
- [ ] Report no-match, false-positive, provider-error, timeout, and unusable-input rates.
- [ ] Report mean, median, and p95 latency per backend.
- [ ] Record dataset size, clip length, hardware, operating system, network region, provider plan, date, and warm/cold conditions.
- [ ] Explain confidence-interval limitations if the dataset is too small.
- [ ] Replace README placeholder accuracy and timing values with generated, reviewable results.
- [ ] Tick Main task 1 only after the benchmark can be reproduced from a clean checkout.

### Main task 2 — Audio-pipeline validation

- [x] Decide and document that FFT is diagnostic only; spectrogram peaks and constellation hash pairs perform local recognition.
- [x] Document the shared CLI/web normalization contract and intentional CLI-WAV versus web-multi-format difference.
- [x] Validate empty audio, invalid sample rates, malformed WAV headers, unsupported encodings, and extreme durations.
- [x] Add mono/stereo, supported sample-width, unsupported 24-bit, malformed-header, and very-short-clip tests.
- [x] Decide that non-WAV CLI input is unsupported while the web path converts documented formats through FFmpeg.
- [x] Complete Main task 2 validation behavior and documentation with the Prompt 3 test evidence below.

### Main task 3 — Authoritative web application

- [x] Decide that Flask `web/` is the supported browser application.
- [x] Retire the unused second browser implementation.
- [x] Document `python web/app.py` as the canonical development command and describe the served UI and API.
- [x] Ensure the README architecture diagram describes the actual Flask runtime path.
- [x] Tick Main task 3 after the reviewer can identify and run the supported web path unambiguously.

### Main task 4 — Production configuration and security

- [ ] Reconcile `SUPABASE_KEY` with service-role-key naming and the intended security model.
- [ ] Decide whether `INTERNAL_API_SECRET` is required for the supported browser flow.
- [ ] Standardize response fields and statuses across providers and the CLI/browser consumers.
- [ ] Add a startup/health check for provider, Supabase, FFmpeg, and `fpcalc` configuration.
- [ ] Make quota checks and increments atomic, and define fail-closed behavior for Supabase failures.
- [ ] Bound cooldown/IP state and document the trusted proxy model.
- [ ] Add `Retry-After` headers and disable debug mode outside explicit local development.
- [ ] Add a production WSGI/server configuration and tests for authorization, limits, concurrency, and Supabase failures.
- [ ] Tick Main task 4 only after the security/configuration review has evidence and no undocumented production assumptions.

### Main task 5 — Test-depth expansion

- [ ] Test rate-limit responses and quota accounting through public routes.
- [ ] Test configuration loading, missing keys, invalid `FP_CALC_PATH`, and provider combinations.
- [ ] Add mocked microphone tests for invalid duration/sample rate, capture failure, and cleanup.
- [ ] Add browser/component tests for recording, upload, loading, matched, no-match, unauthorized, rate-limited, and network-error states.
- [ ] Test microphone permission denial and unsupported `MediaRecorder` behavior.
- [ ] Test that audio streams, visualizers, and other recording resources are released.
- [ ] Test safe rendering when album, artwork, genre, release date, or links are missing.
- [ ] Tick Main task 5 only after the important failure states are covered without real provider credentials.

### Main task 6 — Dependency, CI, and repository hygiene

- [x] Run pytest and coverage in GitHub Actions on every push and pull request.
- [x] Verify the remote PR workflow: 65 tests pass and the 50% coverage gate passes.
- [ ] Enable Codecov for this repository; the current upload reports `Repository not found`, so integration is deferred to CI hardening while `coverage.xml` remains an artifact.
- [x] Verify Python tests in a clean supported environment.
- [ ] Pin or constrain Python dependencies and add Python lint/static checks to CI.
- [ ] Add dependency/security scanning and secret scanning.
- [ ] Keep generated screenshots/test artifacts out of the source tree and remove stale or duplicate scaffold files.
- [ ] Tick Main task 6 only after remote CI and repository hygiene checks are evidenced.

### Main task 7 — Documentation reconciliation

- [ ] Split documentation into Implemented, Known limitations, Planned, and Evaluation evidence sections.
- [ ] Mark unsupported Supabase/auth/history/RLS/account/settings claims as planned or remove them.
- [x] Reconcile README content with the actual Flask source tree.
- [ ] Reconcile documented 8-second CLI, 5-second RapidAPI trim, and 10-second browser-recording behavior.
- [ ] Document the exact source and command for each screenshot, and add failure-state screenshots where useful.
- [x] Remove unsupported platform claims and document API statuses, backend order, environment variables, and security boundaries.
- [ ] Tick Main task 7 only after documentation describes shipped behavior rather than aspiration.

### Main task 8 — Distinctiveness and technical contribution

- [ ] Evaluate the offline/local fingerprinting path against provider-backed baselines.
- [ ] Measure robustness under noise, re-encoding, volume changes, pitch changes, and partial clips.
- [ ] Add confidence-aware matching or provider consensus with an honest no-match threshold.
- [ ] Explain the constellation-map/hash-pair contribution in the README and benchmark it against external APIs.
- [ ] Update the distinctiveness score only after the capability is evaluated with real evidence.
- [ ] Tick Main task 8 only after the local contribution is reproducibly benchmarked and explained.

## P0 — correctness and evaluation blockers

### Benchmark execution prerequisites

- [ ] Provide 30 known source tracks covering the requested genre and era spread, with title/artist ground truth and source/license notes.
- [ ] Add `ACOUSTID_API_KEY` and `AUDD_API_TOKEN` to the local `.env` without committing or pasting secrets into chat.
- [ ] Record the 30 source tracks from speakers through the microphone into 90 clips: 4s, 8s, and 15s per source.
- [ ] Run all three backends against every recorded clip; do not count missing credentials or missing clips as accuracy results.
- [ ] Publish the exact overall and per-length denominators, plus one-line explanations for every failure.

### Reproducible recognition benchmark

- [ ] Define a fixed benchmark manifest with stable track identifiers, title, artist, source, duration, and license/provenance.
- [ ] Include clean clips, short partial clips, re-encoded clips, noisy clips, volume changes, and live microphone samples where legally and practically possible.
- [x] Add a reproducible benchmark command, `scripts/benchmark.py`, with documented setup and provider configuration. It produces overall, per-length, latency, and failure summaries.
- [ ] Cache raw provider responses or normalized results so repeated evaluation does not unnecessarily consume API quota.
- [ ] Measure each backend independently: RapidAPI/Shazam, AcoustID, and AudD.
- [ ] Report top-1 accuracy using stable identifiers where possible, rather than loose title-string comparisons.
- [ ] Report no-match rate, false-positive rate, provider errors, timeouts, and unusable-input failures.
- [ ] Report median, p95, and average recognition latency separately for each backend.
- [ ] Record dataset size, clip length, hardware, operating system, network region, date, provider plan, and warm/cold conditions.
- [ ] Add confidence intervals or an explicit limitation explaining why the benchmark is too small for them.
- [x] Implement a fourth local constellation-map/hash-pair backend over a small library, with an index builder and benchmark integration. Real-world accuracy and speed comparison remain open until the corpus is recorded.
- [ ] Replace `Test set accuracy | X / Y songs matched correctly` in `readme.md` with generated, reviewable results.
- [ ] Remove or substantiate the existing `~2.1 s` and `~3.4 s` performance values.

### Matcher correctness

- [x] Define the backend fallback policy: distinguish provider error, transport failure, timeout, no-match, and missing configuration. The dispatcher falls through on `error`, `no_match`, and `not_configured` and returns the final status otherwise.
- [x] Update `match_audio()` so configured fallback providers are attempted after eligible provider errors instead of returning immediately.
- [x] Decide explicitly whether a provider `no_match` should trigger another provider. The current policy retries the next configured provider.
- [x] Include the selected backend and fallback history in diagnostic output without exposing credentials.
- [x] Preserve detailed provider error context in server logs while returning a stable public response schema with `error_code` plus generic safe messages.
- [x] Add tests for RapidAPI success, no-match, HTTP error, timeout, and malformed JSON.
- [x] Add tests for AudD success, no-match, HTTP error, timeout, and malformed JSON.
- [x] Add tests for AcoustID success, missing `fpcalc`, `fpcalc` failure, HTTP error, and malformed output.
- [x] Add dispatcher tests proving the intended fallback behavior.
- [x] Verify temporary WAV files are removed on success, provider error, timeout, and exception paths.

### Audio pipeline correctness

- [x] Decide that FFT is a diagnostic visualization only and state that decision clearly.
- [x] Explain that FFT does not identify songs; local recognition uses spectrogram peaks and constellation hash pairs.
- [ ] If FFT is intended to be part of recognition, implement and evaluate windowing, spectrogram/peak extraction, and a matching method.
- [ ] Make the web path run the same documented analysis steps as the CLI, or document the intentional difference.
- [x] Add input validation for empty audio, invalid sample rates, malformed WAV files, unsupported encodings, and extreme durations.
- [x] Add tests for mono/stereo WAV, supported sample widths, unsupported 24-bit WAV, invalid headers, and very short clips.
- [x] Decide that non-WAV CLI input is unsupported and make the limitation prominent and consistent with the web path.
- [x] Add explicit maximum upload size and maximum audio duration limits.
- [x] Add a timeout and bounded resource handling around FFmpeg conversion.

## P0 — web architecture and configuration blockers

### Choose one authoritative web implementation

- [x] Decide that Flask-served `web/` is the supported application.
- [x] Retire the unused second browser implementation.
- [x] Document the canonical `python web/app.py` command, served UI, API, and screenshot source.
- [x] Ensure the README architecture diagram describes the actual runtime path.

### Configuration and API contract

- [x] Load `.env` before creating the Supabase client in `web/app.py`, or use one explicit application configuration path.
- [ ] Reconcile `SUPABASE_KEY` with the documented `SUPABASE_SERVICE_ROLE_KEY` naming and security model.
- [ ] Decide whether the API requires an internal secret at all for browser clients.
- [x] Keep real server secrets out of browser configuration and static assets.
- [x] Make the Flask-served UI work when `INTERNAL_API_SECRET` is enabled, or remove that mode from the supported flow. Configured same-origin/allowlisted browser requests are accepted without exposing the secret.
- [x] Configure optional cross-origin API access from an allowlist; same-origin browser access is the default.
- [x] Add RapidAPI configuration to `/api/status`; report the actual active backend order.
- [x] Standardize response fields and statuses across all providers and the CLI/browser consumers, including local `no_match` responses.
- [x] Correct the CLI missing-configuration message so it identifies missing recognition configuration generically rather than naming AudD only.
- [ ] Add a health/startup check that clearly reports missing provider, Supabase, FFmpeg, and `fpcalc` configuration.

### Rate limiting and production safety

- [ ] Prompt 4 blocker: the Origin/Referer same-origin path can bypass `INTERNAL_API_SECRET`; the production trust model and secret boundary need a deliberate decision.
- [ ] Prompt 4 blocker: Supabase quota reads and increments are non-atomic and can race under concurrent requests.
- [ ] Prompt 4 blocker: Supabase failures fail open by returning zero usage and continuing recognition; production behavior must be fail-closed or visibly disable quota-protected recognition.

- [ ] Make quota check and increment atomic so concurrent requests cannot bypass the limit.
- [ ] Decide whether Supabase failure should fail closed or visibly disable recognition instead of silently returning zero usage.
- [ ] Replace process-local cooldown state with a shared, bounded mechanism if multiple workers or instances are supported.
- [ ] Bound or expire the in-memory IP map if it remains in use.
- [ ] Validate proxy configuration and document the trusted proxy model.
- [ ] Add `Retry-After` headers to rate-limit responses.
- [ ] Disable `debug=True` outside an explicitly local development mode.
- [ ] Add a production WSGI/server configuration and document deployment assumptions.
- [ ] Add tests for unauthorized requests, daily limits, monthly limits, cooldowns, concurrent requests, and Supabase failures.

## P1 — engineering quality and verification

### Backend and web tests

- [x] Add Flask test-client coverage for `/`, static assets, `/api/status`, and `/api/match`.
- [x] Test missing, malformed, oversized, duration-rejected, and FFmpeg-conversion upload paths, matcher success/no-match, and API-secret origin behavior.
- [x] Test API-secret behavior in the supported browser-origin path.
- [ ] Test rate-limit responses and quota accounting through the public route.
- [ ] Add tests for `load_config()` and `missing_configuration()` including `.env`, missing keys, invalid `FP_CALC_PATH`, and provider combinations.
- [ ] Add microphone tests using a mocked `sounddevice` implementation, including invalid duration, invalid sample rate, capture failure, and cleanup. Prompt 3 now proves configured too-short/too-long requests do not start recording.
- [x] Add coverage reporting with `coverage.py`, a 50% minimum threshold, and a preserved `coverage.xml` artifact. Current measured branch coverage is 66% across `shazam_project`, `web`, and `scripts`; Codecov remains deferred because the repository is not found.

### Browser behavior quality

- [ ] Add browser tests for recording, upload, loading, matched, no-match, unauthorized, rate-limited, and network-error states.
- [ ] Test microphone permission denial and unsupported `MediaRecorder` behavior.
- [ ] Test that audio streams and visualizer resources are stopped and released after recording.
- [ ] Test safe rendering when album, artwork, genre, release date, or links are missing.
- [x] Document session history as an optional, session-only privacy feature.

### Dependency and static quality

- [ ] Pin or constrain Python dependencies to prevent unreviewed provider/library drift.
- [ ] Add a `pyproject.toml` with a formatter/linter configuration, or document the chosen tooling explicitly.
- [ ] Add Python lint/static checks to CI.
- [ ] Add dependency/security scanning to CI.
- [ ] Keep generated screenshots and test artifacts out of the source tree unless they are intentional, reproducible release artifacts.
- [ ] Remove stale `desktop.ini`, duplicate generated artifacts, and unused scaffold assets where appropriate.
- [ ] Confirm the repository contains no secrets and add secret scanning to CI.

## P1 — documentation reconciliation

- [ ] Split documentation into “Implemented”, “Known limitations”, “Planned”, and “Evaluation evidence”.
- [ ] Mark Supabase authentication, persistent user history, RLS-backed history, account deletion, settings, and protected routes as planned unless implemented.
- [x] Reconcile the README with the actual Flask source tree.
- [ ] Reconcile the documented 8-second CLI behavior, 5-second RapidAPI trim, and 10-second browser recording behavior.
- [x] Document that the current FFT is diagnostic and not used for matching.
- [x] Replace the stale README “Add CI” roadmap entry with the implemented pytest, coverage, lint, and build gates.
- [ ] Document the exact source and command used to generate each screenshot.
- [ ] Add screenshots or recordings for no-match, provider error, permission denial, rate limiting, and upload failure states.
- [x] Add a concise README Limitations section covering noise, catalog coverage, language/region differences, and live/cover/remix versions.
- [x] Remove unsupported “platforms tested” claims and state that cross-platform support is not independently verified.
- [x] Document API status values, backend selection, required environment variables, and security boundaries from the implementation.
- [ ] Add a benchmark results section generated from the evaluation output rather than hand-entered numbers.

## P2 — distinctiveness and product value

- [ ] Choose one focused differentiator instead of adding unrelated features.
- [ ] Evaluate an offline/local fingerprinting path against the provider-backed baseline.
- [ ] Consider a constellation-map or landmark-based fingerprint implementation if local matching is selected.
- [ ] Consider privacy-first matching where audio does not leave the device.
- [ ] Consider confidence-aware provider consensus and an honest no-match threshold.
- [ ] Evaluate robustness under noise, re-encoding, volume changes, pitch changes, and partial clips.
- [ ] Explain the technical contribution in the README and benchmark it against the current external APIs.
- [ ] Update the distinctiveness score only after a real differentiating capability is implemented and evaluated.

## Release gates

- [ ] Python tests pass in a clean supported environment.
- [x] Python tests and coverage pass in CI.
- [ ] Web integration tests pass without real provider credentials.
- [ ] At least one credentialed smoke test proves the configured recognition path works.
- [ ] Benchmark results are reproducible and linked from the README.
- [ ] Security/configuration review is complete for secrets, CORS, rate limiting, uploads, FFmpeg, and debug mode.
- [ ] Documentation describes the shipped implementation rather than the aspirational plan.
- [ ] A reviewer can start the supported app from a clean checkout using only the documented steps.
- [ ] Final score is updated with evidence for correctness, engineering, documentation, and distinctiveness.

## Review notes and evidence log

Record evidence here as work lands:

| Date | Task/check | Evidence | Result |
|---|---|---|---|
| 2026-08-01 | Prompt 3 cleanup and review fixes | Flask status display restored RapidAPI and Supabase fields; local `no_match` uses the shared `result: null` shape; all providers receive normalized mono float32 audio; provider diagnostics are safe; rate limits run before upload processing; fixed 16-bit provider WAV encoding is documented; README/TODO record the validated contract and Prompt 4 production blockers. | 73 tests passed; 66% total branch coverage; compileall and diff checks passed locally; CI and `coverage.xml` artifact are pending this push; Codecov upload previously reported `Repository not found` and remains deferred |
| 2026-07-31 | Initial repository review | `main` at `77d159f`; accuracy remains `X / Y`; Python execution was unavailable locally because the existing virtualenv points to an inaccessible interpreter. | Baseline recorded |
| 2026-07-31 | P0/P1 web and matcher slice | `feature/evaluation-todo`; 10 Python unit/integration tests passed; dispatcher fallback, browser-origin auth, upload/audio limits, dotenv loading, and runtime status fields were added. | Verified; benchmark, full web coverage, and production deployment remain open |
| 2026-07-31 | Benchmark tooling slice | `scripts/record_benchmark.py`, `scripts/benchmark.py`, `evaluation/README.md`, and aggregation tests added; 13 Python tests pass. Machine has speaker/microphone devices, FFmpeg, and `fpcalc`; only RapidAPI is configured. | Tooling verified; real corpus and two provider credentials remain required |
| 2026-07-31 | Local fingerprint backend slice | `shazam_project/fingerprint.py`, local index builder, fourth-backend dispatcher wiring, README/evaluation documentation, and synthetic index tests added; 16 Python tests pass. | Algorithm path verified on synthetic tracks; real speaker/microphone accuracy and API comparison remain open |
| 2026-07-31 | Matcher correctness slice | Provider adapters now return stable `error_code` values with diagnostic detail; mocked RapidAPI, AudD, and AcoustID success/no-match/HTTP/timeout/malformed-output tests and temporary-WAV cleanup tests were added. | 36 pytest tests passed; branch coverage is 59%; real provider behavior and credentialed smoke tests remain open |
| 2026-07-31 | Polishing roadmap | Added an ordered eight-task execution roadmap covering benchmark evidence, audio validation, web ownership, production security, test depth, CI/repository hygiene, documentation reconciliation, and distinctiveness evaluation. | Roadmap recorded; complete one main task at a time |
| 2026-07-31 | CI quality-gate slice | `.github/workflows/ci.yml` runs pytest on every push and pull request across Python 3.10–3.12, enforces 50% branch coverage on Python 3.12, and uploads `coverage.xml`. | Workflow structure verified; later PR #4 evidence supersedes the pending remote/Codecov note |
