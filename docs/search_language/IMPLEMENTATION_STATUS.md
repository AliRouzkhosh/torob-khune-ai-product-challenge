# Search Language Implementation Status

This file is cumulative. New implementation batches must start from the immediately previous version, not from the original repository snapshot.

## v0.9-A — Language foundation

Implemented:

- Persian normalization and common colloquial spelling variants;
- rental money aliases (`رهن`, `پول پیش`, `کرایه`);
- richer bedroom exact/minimum/allowed parsing;
- colloquial parking/elevator/storage requirements and negation;
- quality wording for light/quietness/building age;
- stronger PATCH preservation and query-dimension detection.

Validation at creation: Python compile + 18 direct parser/state assertions.

## v0.9-B — Structured housing constraints

Baseline: **v0.9-A**, cumulative.

Implemented:

- area min/max/range;
- floor exact/min/max/allowed and ground/basement exclusions;
- explicit minimum construction year from age wording;
- unconditional renovation requirement;
- maximum-bedroom constraint;
- SearchIntent session-schema migration;
- SQL + deterministic eligibility enforcement;
- interpretation labels, refinement diffs, and zero-result recovery.

Validation at creation: Python compile + 33 direct parser/state/eligibility assertions. Full Django suite deferred to the user's normal environment/Codex verification.

## Next planned batch — v0.9-C

Text-evidence concepts with YES/NO/UNKNOWN semantics, prioritizing demo value:

1. pets allowed / forbidden / unknown;
2. parking count and non-tandem/dedicated parking;
3. furnishing;
4. HVAC;
5. low-unit / single-unit-floor building;
6. security;
7. transport evidence;
8. selected view/privacy/accessibility signals.

Compound conditional/fallback grammar remains a separate later batch so it is not mixed with evidence extraction.

## v0.9-C — Evidence-aware housing criteria

Baseline: **v0.9-B**, cumulative.

Implemented with conservative seller/ad-text evidence and explicit `YES / NO / UNKNOWN` semantics:

- pet policy: allowed / forbidden / unknown;
- parking count, non-tandem and dedicated parking;
- furnished / unfurnished;
- HVAC evidence (package, radiator, split AC, water cooler, fan coil, chiller);
- single-unit / low-density buildings;
- security (24h guard, CCTV, concierge/lobby-man, lobby);
- transport evidence (metro, BRT, road access);
- selected view/privacy signals;
- selected accessibility signals.

Hard requirements exclude `UNKNOWN`; soft preferences give a ranking bonus only when the ad explicitly supports the feature. Missing wording is never converted to a false claim.

New canonical state:

- hard evidence requirements live under `SearchIntent.constraints`;
- soft text-evidence preferences live under `SearchIntent.evidence_preferences`;
- v0.9-B session dictionaries migrate automatically with safe defaults.

Validation at creation: Python compile + 37 direct parser/state/evidence assertions + ranking-evidence smoke test. Full Django suite remains deferred to the user's normal environment/Codex verification.

## Next planned batch — v0.9-D

Compound housing logic and controlled fallback plans:

1. relative priorities (`نور از متراژ مهم‌تره`);
2. conditional requirements (`طبقه بالا فقط با آسانسور`);
3. conditional relaxations (`پارکینگ مهم نیست اگر نزدیک محل کار باشه`);
4. exceptions (`نوساز بهتره ولی قدیمی بازسازی‌شده هم قبوله`);
5. progressive fallbacks (`اول ونک؛ اگر نبود اطرافش`).

The compound layer must preserve the evidence semantics introduced in v0.9-C rather than flattening conditions into global filters.

## v0.9-D — Conditional, Relative-Priority & Fallback Engine

Baseline: **v0.9-C**, cumulative. No v0.9-A/B/C language, structured constraints, or evidence semantics were replaced.

Implemented:

- explicit compound state under `SearchIntent.logic`;
- relative priorities across structured and text-evidence criteria;
- superlative priorities (`رفت‌وآمد از همه چیز مهم‌تره`);
- conditional floor/elevator rules without turning the floor clause into a global filter;
- old-building exceptions requiring renovation or elevator only when the building is old;
- conditional preference relaxation for close commute / explicit listing evidence;
- conditional hard-area relaxation when a prior concrete minimum exists;
- conditional rent-cap expansion for very-close commute;
- progressive fallback plans for exact→nearby location, rent cap, bedroom sets, parking, and new→renovated-old stock;
- ordered multi-stage fallback composition;
- stale compound-rule cleanup under “latest explicit action wins”;
- user-facing compound-logic labels, conditional explanations, and fallback-stage notices;
- v0.9-C session dictionaries migrate with an empty logic group without losing state.

Important semantics:

- conditions stay conditional rather than becoming global filters;
- fallback stages run only when the strict stage is below the user-implied result threshold;
- `اگر نبود` / `پیدا نشد` means zero-result fallback; `اگر کم بود` uses a deterministic 3-result threshold;
- direct hard evidence still follows v0.9-C `YES / NO / UNKNOWN` rules;
- unknown values in a conditional antecedent do not fabricate that the condition holds; they remain review-worthy uncertainty;
- no hidden fallback is invented when the user did not state one.

Validation at creation: full Python compile + **85 direct parser/state/eligibility/ranking assertions**, real-data sanity audit against the included 3,000 rows, and **167 statically discovered Django `test_*` methods**. Full Django execution remains deferred to the user's normal environment/Codex because Django is not installed in this execution environment.

## Next planned batch — v0.9-E

Verification and demo hardening rather than another architecture expansion:

1. run the complete Django suite in the normal virtual environment;
2. activate parameterized subsets of the 320-case language regression corpus;
3. audit false positives/negatives on real Divar descriptions;
4. verify fallback/conditional UI in browser on the strongest demo scenarios;
5. have Codex independently review rule precedence, stale-rule cleanup, and regression coverage when its usage limit resets.

Arbitrary free-form Boolean constraint solving remains intentionally out of scope; v0.9-D uses controlled, inspectable rule families suitable for the hiring demo.

## v0.9-D.1 — Search engine stabilization & regression closure

Baseline: **v0.9-D**, cumulative.

Triggered by the first complete Django execution and manual real-data testing.

Fixed:

- real-ad parking phrase `2پارکینگ سندی غیر مزاحم` now confirms non-tandem parking rather than UNKNOWN;
- superlative discourse scoping no longer lets a previous parking clause steal `رفت‌وآمد از همه چیز مهم‌تره`;
- bedroom removal no longer constructs invalid exact-0 state;
- `یک خوابه هم اوکیه` PATCH expands an existing 2BR constraint to allowed `[1,2]` instead of replacing it;
- bare `بازسازی` remains a literal neutral-Browse text search while explicit renovation requirements still enter smart search;
- canonical-state regression expectation now includes intentional `evidence_preferences` and `logic` groups.

Added four targeted regression tests. Static discovered Django `test_*` methods: **171**.

Container validation: Python compile, direct parser/evidence/ranking assertions, and real SQLite evidence audit passed. Full Django execution must be rerun in the user's normal virtual environment; v0.9-E remains blocked until that suite is green.
