# Worker3 Review: Round 1 Worker1 Vibe Design Report

Reviewer: Worker3(Codex)
Role: code review / bug detection / security checks
Reviewed: 2026-06-17
Input: javis/rsi/vibe-design/round1_worker1.md
Prep notes: javis/rsi/vibe-design/worker3_prep.md

## Verdict

Do not implement Worker1 Round 1 recommendations as written. The direction is useful, but the report overstates several external spec claims, evaluates a non-existent CLAUDE.md design section, and proposes architecture without migration, validation, performance, or security boundaries. Treat it as a concept brief, not an implementation plan.

## Findings

### Critical: DESIGN.md spec claims are not sufficiently verified

Worker1 states that Google open-sourced a DESIGN.md specification in 2026-04 and that an industry standard is forming (round1_worker1.md:12, 27, 32). This is presented as a settled standard, but the cited source is a secondary news/blog link, not an official Google specification repository or standards body. The report also claims Apache-2.0 licensing, YAML frontmatter shape, Markdown parser preference, and unresolved alpha gaps (lines 27, 32-64) without primary-source evidence in the report.

Required correction: downgrade these claims to unverified/secondary-source observations unless Worker1 supplies an official spec URL, repository, license file, version tag, and schema. For implementation, DESIGN.md should be an internal contract owned by this repo, not a presumed Google-compatible standard.

### Critical: Current-system assessment is factually wrong for this repo

Worker1 evaluates a CLAUDE.md design section and assigns high grades for spacing, radius, opacity, duration, shadows, color, typography, glassmorphism, animation, and accessibility (lines 202-213). The actual root CLAUDE.md is 184 lines and contains no design-token section. It documents cmux-win architecture, terminal control, socket API, and build usage.

The real style surface is split between design/prototype.html CSS variables and inline React styles in src/renderer/App.tsx. Examples: design/prototype.html defines :root tokens at line 14 and --bg-* / --fg-* variables around lines 21-38, while App.tsx contains hard-coded colors and inline hover mutations around lines 280-329, 451, 527, 557, 587, 617, 645, 675, 828, and 849.

Required correction: remove the A/A+ scoring and redo the gap analysis from actual files. The true baseline is not a mature design system; it is a prototype CSS token file plus scattered inline styles.

### High: Proposed DESIGN.md structure mixes human narrative and token source of truth incorrectly

The suggested YAML-frontmatter-in-Markdown pattern can help agents, but it is a poor primary token source if adopted literally. YAML frontmatter inside DESIGN.md lacks strong schema enforcement, stable transforms, circular-reference detection, and deterministic platform output. The prep criteria require a single source such as design/tokens with schema validation and generated CSS boundaries.

A safer architecture is: design/tokens/*.json as canonical machine-readable tokens, generated CSS custom properties for renderer use, and DESIGN.md as narrative guidance that references generated token docs. If DESIGN.md embeds token values, drift between docs, generated CSS, and components becomes likely.

### High: meta.json per component is directionally useful but over-specified as mandatory

Worker1 proposes a 6-file component package including button.meta.json, button.tokens.css, stories, tests, and index.ts (lines 79-104), then treats antiPatterns as mandatory for every component (lines 169, 252). This is plausible for a design-system package, but cmux-win currently has ordinary renderer components under src/renderer/components with no Storybook dependency and no component metadata pipeline.

Adding six files per component would create large maintenance overhead before the repo has canonical tokens, a component taxonomy, or visual regression infrastructure. Start with metadata for high-risk reusable primitives only: button, input, panel/tab, modal, toast, command palette. Then prove agent usefulness before expanding.

### High: Security model for agentic tooling is incomplete

The report discusses MCP/Figma-style agent consumption and MAPE-K automation but does not define a threat model. Any future design-agent pipeline can become dangerous if prompt or design text is passed into shell commands, package installation, file writes, or MCP tools. Worker1 also proposes automatic PR generation and learning loops (lines 120-129, 258) without allowlists, credential boundaries, audit logs, or human approval mechanics.

Required gates: no shell interpolation from design content, argument-array execution only, allowlisted MCP tools, no secret access for design agents, dependency review for generated code, audit logs for automated fixes, and human review before merge. Agents may draft patches or issues; they must not autonomously merge or mutate design contracts.

### Medium: Performance risks are underdeveloped

Worker1 recommends metadata, token injection, always-on foundation context, and possible governance automation, but does not budget CSS size, context size, renderer runtime cost, or test cost. cmux-win is an Electron terminal multiplexer where startup time, renderer responsiveness, xterm performance, and split-panel layout stability matter more than ornamental UI sophistication.

Risks: duplicated token outputs, global CSS variable churn, costly theme recalculation, excessive backdrop-filter/blur/shadow styles, hydration/re-render churn from runtime token mapping, and larger agent prompts from always-on foundation docs. Any implementation must benchmark renderer startup, panel resize latency, xterm typing latency, and CSS bundle size.

### Medium: Token naming proposal is too abstract for migration

Worker1 correctly recommends semantic intent tokens over raw value tokens (lines 161-164, 221), but does not show a migration map from current names such as --bg-content, --fg-primary, --status-running, or hard-coded #272822/#0091FF values. Without aliases and deprecation policy, a rename from visual/location names to intent names will break existing UI or create duplicate token layers.

Required migration path: inventory current CSS variables and hard-coded inline values, create aliases first, migrate components in batches, add lint rules for new raw colors, then remove deprecated aliases after tests and visual screenshots pass.

### Medium: Accessibility claims need concrete enforcement

Worker1 says DESIGN.md should enforce WCAG AA/AAA (lines 58-59) and rates current accessibility B+ (line 211), but does not identify contrast tests, focus-visible rules, keyboard-state coverage, reduced-motion policy, or target-size checks in the repo. Current inline button hover handlers and custom controls need explicit keyboard/focus parity review.

Required checks: automated contrast audit for token pairs, focus-visible token, keyboard navigation tests for command palette/sidebar/panel tabs, reduced-motion handling for transitions/animations, and Playwright accessibility smoke coverage for main workflows.

### Medium: External benchmark claims are not implementation evidence

The Indeed JSON-vs-Markdown benchmark is reported as 80% token reduction and lower hallucination (lines 24, 111-116), but the report does not provide methodology details, prompts, model versions, confidence intervals, or transferability to cmux-win. It should not justify a repo-wide metadata migration by itself.

Use it only as a hypothesis: structured metadata may reduce prompt cost. Validate locally with 3-5 representative component generation tasks before expanding.

### Low: MAPE-K is premature

A MAPE-K self-healing loop (lines 120-129, 222, 258) is too heavy for round 1. The repo lacks the prerequisites: canonical tokens, generated CSS, visual regression, drift scoring, ownership rules, and safe auto-fix boundaries. Implementing this first would create automation around unstable definitions.

Defer until token validation, component metadata, visual regression, and design linting exist.

## Missing Edge Cases

- Dark/light mode and high-contrast mode are not handled in the proposed token model.
- Windows-specific font fallback, DPI scaling, and ClearType rendering are not discussed.
- xterm theme integration is not addressed; terminal colors may need separate ANSI/theme tokens.
- User-configurable themes in resources/themes/themes.json are not mapped to design tokens.
- Standalone browser mode and Electron mode may need different token loading behavior.
- i18n and Korean text layout are not covered, despite existing i18next usage.
- Reduced-motion and keyboard-only workflows are not specified.
- Generated code failure modes are missing: stale metadata, token aliases, deleted components, circular token references, schema version mismatch.
- CSS variable fallback strategy is absent for partial token loads or migration windows.
- Supply-chain review is missing for any proposed Storybook, Style Dictionary, MCP, or metadata generation dependency.

## Recommended Replacement Plan

1. Baseline actual UI architecture: inventory design/prototype.html variables, App.tsx inline styles, renderer components, xterm theme integration, and resources/themes/themes.json.
2. Create design/tokens/schema.json and design/tokens/base.json as the canonical machine-readable source.
3. Generate renderer CSS variables deterministically and mark generated files as non-editable.
4. Add DESIGN.md as human/agent guidance only: product feel, anti-patterns, examples, accessibility rules, and token usage policy.
5. Add metadata for only 3-5 core primitives first, then measure whether AI generation quality improves.
6. Add lint/test gates: no new raw colors, typecheck, unit tests, Playwright screenshots, contrast checks, reduced-motion checks.
7. Defer MAPE-K and automatic PR generation until token generation, component metadata, and visual regression are stable.

## Final Assessment

Technical accuracy: weak. Major claims about DESIGN.md standardization and current repo maturity are unsupported or factually wrong.
Architecture quality: promising direction, but too broad and not staged against the current cmux-win codebase.
Security posture: insufficient. Automation and MCP/design-agent integration need explicit boundaries before implementation.
Performance posture: insufficient. The proposal does not protect Electron renderer responsiveness or xterm latency.
Edge-case coverage: incomplete across theming, accessibility, localization, terminal-specific UI, and migration failure modes.

Worker3 recommendation: request Worker1 Round 2 to revise with primary-source verification, actual repo inventory, staged migration, and explicit security/performance gates before any implementation.
