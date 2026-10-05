# Documentation verification record

Snapshot: `2671ccab1802f330083f122561e7ab6c2718dd9f`. Checks observed on 2026-10-03 in this isolated feature-branch copy.

| Acceptance check | Observed evidence |
| --- | --- |
| Source and diagram links | 21 case-study/diagram references resolve; 8 root-embedded diagram click targets checked. |
| Root diagram fidelity | Embedded Mermaid equals overview.mmd after adapting relative source URLs to the root README location. |
| Tracked-file accounting | 69 snapshot paths assigned exactly once; no missing or duplicate paths. |
| Detail graph structure | 10 functional groups have diagram nodes; no dangling endpoints. |
| Preview rendering | Overview and detail Mermaid rendered successfully; separate output PNG previews inspected previously. No new PNG is proposed for this repository. |
| Previously truncated source | 11 contiguous redacted fragments cover all lines of 4 previously truncated files; each was sent in a successful Jev helper call. |
| Application behavior | Application runtime was not exercised in this documentation task. |

These checks verify documentation structure and recorded review coverage. Inventory accounting does not establish every execution path, source conformance or hosted behavior. Fragment reviews retain their individual uncertainty; successful transmission is not approval. Jev thresholds remain unchanged. Integration remains pending unresolved warnings. No application code, dependency, schema, deployment or user data is changed.

## Reproduce structural checks

With Node.js and Git installed, run from the repository root:

```sh
node docs/architecture/verify.mjs --self-test
```

The checker reads the explicitly pinned source snapshot, not the current HEAD, so a later documentation commit does not invalidate inventory accounting. It checks source paths, snapshot pinning, inventory equality, graph endpoints, Mermaid embed consistency and documentation links. Seven base structural failure cases cover inventory, paths, embeds, links and snapshot identity. The current checker has 10 intended-failure cases in total, including source-map checks; each must fail at its intended check. No files are changed by the checker. Node is an optional documentation-checking tool; this adds no application dependency.

This checker does not parse the full Mermaid language, verify arrow semantics, access hosted services or prove all application behavior. Rendering was checked separately. A passing structural check does not replace source-conformance review.

## Bounded source-claim review

On 2026-10-04, jev-1.13.0 evaluated four critical source-behavior claims against selected implementation files or exact contiguous source fragments from this snapshot. Observed call usage: 7761 input tokens and 179 output tokens. All four typed results selected supported.

| Claim | Typed result | Confidence |
| --- | --- | ---: |
| match_audio attempts RapidAPI, AcoustID, AudD, then the local matcher in that order. | supported | 1 |
| The dispatcher normalizes input, skips missing configuration, and stops after a matched response or another terminal status. | supported | 0.91 |
| The local matcher calls match_local_index and does not make a network request in match_audio_local. | supported | 1 |
| FFT analysis is a separate diagnostic/visualization module rather than the matching dispatcher. | supported | 1 |

Source evidence: [shazam_project/matcher.py](../../shazam_project/matcher.py), [shazam_project/fingerprint.py](../../shazam_project/fingerprint.py), [shazam_project/fft_analyze.py](../../shazam_project/fft_analyze.py). Long-file fragments were reviewed with their original source path, commit and line ranges; this is bounded evidence, not a claim that every source file was supplied in one call.

These semantic checks supplement the structural checker. They cover only the four claims listed, not every diagram arrow or execution path, and do not replace the complete-diff or plan approval gates. Integration remains blocked while those required gates are unresolved.

## Complete diagram relationship source map

Observed 2026-10-04: all **27 diagram arrows** have selected source ranges at pinned commit 2671ccab1802f330083f122561e7ab6c2718dd9f. Latest judgments support 26 arrows; W-to-N remains insufficient. Fourteen bounded calls used jev-1.13.0 with 47985 input/1318 output tokens, including historical additional-context and alternative-label judgments. Each call used at most six redacted excerpts, at most 10,000 characters each. Narrow judgments are separate from whole-diff approval and runtime/hosting evidence.

The FFT labels were corrected: CLI main.py calls analyze_audio before match_audio and exits on diagnostic error, while the web route omits FFT. Both diagrams now show the additional optional artwork network boundary. No runtime, provider, quota schema, dependency or original checkout was changed.

### Entry-helper disagreement

The latest original W-to-N judgment is insufficient despite selected source showing main.py calls load_audio_file/record_microphone, web/app.py calls load_audio_file, and both recorder helpers return normalize_audio results. An alternative direct-helper wording received contradicted; it was not adopted. The typed responses provide no textual rationale, so no specific defect can be attributed to them. The original relationship is retained with this disagreement disclosed, rather than counted as Jev-supported. Direct static checks of pinned source are recorded separately; they do not manufacture a Jev approval. Integration remains held.

### Source keys

- [S1](../../main.py)
- [S2](../../web/static/app.js)
- [S3](../../web/app.py)
- [S4](../../shazam_project/recorder.py)
- [S5](../../shazam_project/matcher.py)
- [S6](../../shazam_project/display.py)
- [S7](../../shazam_project/config.py)
- [S8](../../scripts/build_fingerprint_index.py)
- [S9](../../shazam_project/fingerprint.py)
- [S10](../../Dockerfile)
- [S11](../../tests/test_web_pipeline.py)
- [S12](../../tests/test_display.py)

O/D mean overview/detail. S ranges are inclusive pinned Git lines. The checker validates exactly one mapping per arrow and source range bounds. Ten intended-failure fixtures include a missing mapping, unknown source key and invalid range; these structural checks do not judge semantics.

| Arrow | Source ranges | Latest typed judgment (confidence) |
| --- | --- | --- |
| O I --> W | S1:27-50, S2:550-583 | supported (0.97) |
| O W --> N | S1:27-50, S3:453-483, S4:81-127, S4:147-203, S4:205-258 | insufficient (0.46) |
| O N --> D | S1:62-72, S3:569-593, S5:184-215 | supported (0.96) |
| O N -.-> F | S1:51-72, S3:569-593 | supported (0.92) |
| O D --> L | S5:199-244, S5:447-457 | supported (0.99) |
| O D -.-> P | S5:78-98, S5:246-307, S5:364-395 | supported (0.96) |
| O L --> R | S5:447-457, S1:64-72, S6:11-45 | supported (0.96) |
| O P -.-> R | S5:209-244, S3:584-594, S2:584-619 | supported (0.97) |
| O N --> R | S1:43-50, S3:497-503, S5:184-198 | supported (0.99) |
| D UI --> API | S2:550-583, S3:546-569 | supported (1) |
| D UI --> NORM | S1:27-42, S4:193-203, S4:243-258 | supported (0.94) |
| D API --> CONVERT | S3:453-495, S4:299-363 | supported (1) |
| D CONVERT --> NORM | S3:474-483, S4:193-203 | supported (0.8) |
| D NORM --> MATCH | S5:184-215 | supported (0.99) |
| D CONFIG --> API | S3:568-578, S7:26-59 | supported (0.95) |
| D CONFIG --> MATCH | S5:78-90, S5:246-254, S5:364-374, S5:447-457 | supported (1) |
| D API --> QUOTA | S3:364-390, S3:410-436, S3:546-589 | supported (0.99) |
| D TOOLS --> FP | S8:10-27, S8:45-67, S9:154-189 | supported (0.99) |
| D RUN .-> API | S10:1-45, S3:24-32 | supported (0.99) |
| D UI .-> DIAG | S1:51-72, S3:569-593 | supported (0.93) |
| D MATCH .-> FP | S5:447-457, S9:201-239 | supported (1) |
| D MATCH .-> REMOTE | S5:199-215, S5:78-98, S5:291-307, S5:364-395 | supported (0.9) |
| D MATCH --> RESULT | S5:184-244 | supported (0.85) |
| D RESULT --> UI | S1:64-72, S6:11-45, S2:584-619 | supported (0.99) |
| D SUPPORT .-> UI | S11:1-80, S12:1-42 | supported (0.88) |
| O R .-> ART | S6:46-50, S2:619-633 | supported (0.92) |
| D UI .-> ART | S6:46-50, S2:619-633 | supported (0.82) |

## Specific source-concern diagnosis

A subsequent bounded diagnostic on 2026-10-04 used jev-1.13.0 with 5693 input/147 output tokens and redacted pinned source. The three separately judged call chains (CLI file, CLI microphone and web upload to shared normalization) each returned yes probability 0.96. No listed concrete contradiction was selected (confidence 0.99). This supports those individual facts, not a new whole-arrow or complete-diff approval. Earlier insufficient judgments remain disclosed above; the full-review gates and integration condition are unchanged.

## Focused local execution evidence

On 2026-10-04, all 44 existing tests in [test_recorder.py](../../tests/test_recorder.py), [test_audio_pipeline.py](../../tests/test_audio_pipeline.py) and [test_web_pipeline.py](../../tests/test_web_pipeline.py) passed against this pinned source. A disposable Python environment supplied pytest 8.4.2, NumPy 2.5.3, SciPy 1.18.1 and Flask 3.1.3. The workspace harness blocked socket connections, disabled dotenv loading, removed credential environment variables and used workspace fixture/cache paths. Microphone and provider boundaries were mocked. Earlier fixture setup errors were caused by an inaccessible system temp folder and resolved by changing only the harness paths. This is focused local input/normalization/upload evidence, not full-suite, device, FFmpeg-installation, dependency-lock, live provider, quota database, deployment or Jev gate clearance.
