# Round 2 Worker3 Research: 2026 Vibe Design Tools and Methods

Reviewer: Worker3(Codex)
Role: code review / bug detection / security checks
Date: 2026-06-17
Goal: find approaches better than Round 1 findings for cmux-win RSI Vibe Design.

## Executive Verdict

Round 2 should move away from unverified DESIGN.md-standard claims and toward a measurable pipeline: canonical JSON design tokens, generated CSS, agent-readable DESIGN.md guidance, accessibility gates, visual regression, and performance budgets. The strongest 2026 evidence favors structured metadata plus rendered-browser evaluation, not trust in one document format or one AI tool.

Best improved approach for cmux-win:
1. Keep DESIGN.md as agent/human policy, not the token source of truth.
2. Use design/tokens/*.tokens.json or *.json as canonical machine data, with schema versioning.
3. Generate CSS variables deterministically and block manual edits to generated files.
4. Require Playwright + axe-style automated checks + keyboard/focus behavioral tests for generated UI.
5. Add local CSS/runtime benchmarks because public AI-CSS-vs-hand-CSS benchmarks are not yet strong enough.
6. Treat Figma/v0/AI-generated code as draft input behind security and performance review gates.

## 1. AI-Native Design System Frameworks and Tools in 2026

### Figma MCP / Figma Make / Code Connect direction

The strongest industry direction is not screenshot-to-code. Figma MCP-style workflows expose structured design data and, increasingly, code context from Figma Make files to coding agents. Reports from 2025-2026 describe remote MCP access, integrations with IDEs and coding agents, and Code Connect improvements that can give agents component locations and usage guidance.

Why this is better than Round 1: Round 1 treated DESIGN.md as the central breakthrough. The better pattern is multi-source grounding: design tokens + component metadata + actual code context + rendered verification.

cmux-win implication: do not adopt Figma MCP now unless the repo gains a design source in Figma. But borrow the principle: agents should never infer from screenshots alone; they should receive structured tokens, component APIs, usage rules, and current code references.

Sources:
- https://www.theverge.com/news/783828/figma-make-ai-app-coding-mcp-server-update
- https://www.theverge.com/news/679439/figma-dev-mode-mcp-server-beta-release
- https://www.techradar.com/pro/figma-is-making-its-ai-agents-smarter-and-more-connected-to-help-boost-your-designs

### v0 / prompt-to-frontend tools

2026 vibe-coding tool coverage consistently places v0 near the top for React component generation, visual refinement, and design-to-code workflows. The useful lesson is not vendor adoption; it is workflow shape: generate a live preview plus code, then refine visually while preserving component structure.

cmux-win implication: do not route production UI through a SaaS generator by default. Instead, copy the local workflow pattern: generate component, render it, inspect screenshots, run tests, then accept. For an Electron app, local reproducibility matters more than generation speed.

Source: https://www.techradar.com/pro/best-vibe-coding-tools

### Research frameworks: Figma2Code, CoGen, DesignBench, Vibe Code Bench

2026 research gives a more sober view than vendor marketing. Figma2Code shows that metadata-rich Figma inputs improve visual fidelity, but generated code still struggles with responsiveness and maintainability. CoGen focuses on reusable atomic components in Figma using structured JSON plus prompts. DesignBench and Vibe Code Bench show that real frontend generation must be evaluated across frameworks, editing/repair, browser workflows, cost, latency, and human alignment, not just static screenshots.

Better-than-Round-1 rule: require generated UI to survive edit/repair tasks and real workflows. A component that looks right once is not accepted until it remains maintainable after a change.

Sources:
- https://arxiv.org/abs/2604.13648
- https://arxiv.org/abs/2601.10536
- https://arxiv.org/abs/2506.06251
- https://arxiv.org/abs/2603.04601

## 2. Automated Accessibility Testing for AI-Generated UI

### Baseline standard: WCAG 2.2, not vague AA claims

WCAG 2.2 is the stable reference point. W3C states that WCAG 2.2 success criteria are testable statements and recommends using WCAG 2.2 for updated accessibility efforts. It adds important generated-UI concerns such as Focus Not Obscured, Focus Appearance, Dragging Movements, and Target Size Minimum.

Better-than-Round-1 rule: DESIGN.md must name exact success criteria for generated UI acceptance rather than saying WCAG AA/AAA generally.

Source: https://www.w3.org/TR/WCAG22/

### 2026 generated-accessibility methodology

2026 LLM accessibility research emphasizes model-driven and oversight-by-design pipelines. One approach combines structured user profiles, declarative adaptation rules, validated prompt templates, and traceability to WCAG 2.2 / EN 301 549. Another argues that human oversight should be embedded into the pipeline with escalation policies, risk signalling, thresholds, review feedback, and audit logs.

Better-than-Round-1 approach: generated UI should produce an accessibility evidence packet: automated results, keyboard trace, focus screenshots, contrast pairs, and any required human review notes.

Sources:
- https://arxiv.org/abs/2601.06616
- https://arxiv.org/abs/2602.13745

### Practical automated test stack

Use layered testing, because automated accessibility tools cannot prove full accessibility. For cmux-win, the minimum gate should be:
- static lint: accessible names, no aria-hidden focusables, no raw color additions without token pair checks
- DOM scan: axe-core style rules in Playwright after each generated screen renders
- behavioral tests: Tab order, focus-visible, modal focus trap, Escape behavior, keyboard activation
- visual checks: focus ring not obscured, target size, zoom/reflow, high-contrast mode if supported
- human checkpoint: semantic appropriateness of labels, destructive actions, and keyboard ergonomics

Better-than-Round-1 rule: never accept AI-generated UI based only on lint or only on screenshots. Accessibility acceptance must combine rule checks with behavior checks.

Supporting sources:
- https://www.w3.org/TR/WCAG22/
- https://arxiv.org/abs/2502.10884
- https://arxiv.org/abs/2602.24067

## 3. Performance Benchmarks: AI-Generated CSS vs Hand-Coded CSS

### Current evidence gap

I did not find a strong 2026 benchmark that directly compares AI-generated CSS against hand-coded CSS under the same app, same design, and same runtime constraints. Existing 2026 evidence is adjacent: end-to-end web app generation accuracy, frontend code generation quality, energy-aware AI-assisted frontend optimization, and visual-critic iterative refinement.

Conclusion: do not cite public evidence to claim AI CSS is faster/slower than hand-coded CSS. Build a local benchmark harness for cmux-win.

### Useful adjacent evidence

Vibe Code Bench evaluates end-to-end web app generation with 964 browser workflows and 10,131 substeps. The best model reached only 58.0% accuracy on the held-out test split, and self-testing during generation correlated strongly with performance. This supports mandatory self-test loops for generated UI.

EcoAssist benchmarks 500 websites and reports that an energy-aware assistant reduced per-website energy by 13-16% on average. This supports adding sustainability/performance review to AI-generated frontend code instead of optimizing only visual fidelity.

Vision-Guided Iterative Refinement reports that a rendered-page visual critic improved frontend generation quality up to 17.8% over three refinement cycles. This supports screenshot-based critique, but only as one loop in addition to code and accessibility checks.

DesignBench evaluates generation, edit, and repair across React, Vue, Angular, and HTML/CSS. This supports testing maintainability after edits, not only initial render.

Sources:
- https://arxiv.org/abs/2603.04601
- https://arxiv.org/abs/2604.04332
- https://arxiv.org/abs/2604.05839
- https://arxiv.org/abs/2506.06251

### cmux-win local benchmark proposal

For each candidate AI-generated design change, compare against a hand-coded or baseline implementation using:
- CSS size: raw bytes, gzip bytes, number of rules, duplicate declarations, unused selectors
- runtime cost: renderer startup time, first paint, React commit time, xterm typing latency
- layout cost: panel split/resize latency, layout shift, long animation frames
- interaction cost: command palette open/close, sidebar toggle, drag divider, terminal focus switching
- accessibility cost: contrast pairs, focus-visible screenshots, target size failures
- maintainability cost: number of touched files, raw colors added, inline styles added, generated dead code

Acceptance budgets for cmux-win:
- no new runtime styling library without explicit approval
- no global reset or global theme mutation without visual regression
- no per-render token computation on hot paths
- no backdrop-filter/blur-heavy UI in terminal surfaces unless benchmarked
- CSS output must be deterministic and cacheable
- generated UI must pass mobile-ish narrow window and wide desktop Electron screenshots

Better-than-Round-1 rule: performance must be measured on Electron renderer workflows, not inferred from web-page benchmarks.

## 4. Best Practices for DESIGN.md Schema Evolution

### Correct standard posture

The Design Tokens Community Group Format Module 2025.10 is a 13 June 2026 Draft Community Group Report. It explicitly says the current preview should not be implemented or referenced as authoritative. It is not a W3C Standard and not on the W3C Standards Track.

However, it is still useful directionally. It defines stable design-token concepts such as JSON token files, $value, $type, $description, $extensions, $deprecated, groups, aliases/references, JSON Pointer references, chained references, and circular-reference detection.

Better-than-Round-1 rule: do not call DESIGN.md a Google/industry standard. Use DTCG concepts for internal schema design, with a repo-owned version and migration policy.

Sources:
- https://www.designtokens.org/tr/drafts/format/
- https://styledictionary.com/getting-started/installation/

### Better schema architecture

Recommended split:
- design/tokens/schema.json: repo-owned JSON Schema for tokens and metadata
- design/tokens/v1/*.tokens.json: canonical token sources
- src/renderer/styles/generated/tokens.css: generated CSS variables, never edited manually
- DESIGN.md: human/agent policy, token naming rules, anti-patterns, accessibility contract, examples
- design/components/*.component.json: optional metadata for high-value components only
- docs/design/migrations/*.md: migration notes and deprecation windows

Do not put canonical token values in DESIGN.md frontmatter. That creates doc/code drift and weak validation. DESIGN.md should reference the token package and explain how agents should use it.

### Schema evolution rules

- Every schema has schemaVersion and generatedAt/build metadata where appropriate.
- Token files allow $extensions for cmux-specific metadata, but extension keys must be namespaced.
- Deprecated tokens use $deprecated plus replacement, removal target, and reason.
- Aliases are allowed only through validated references; circular references fail CI.
- New token categories require examples and generated CSS snapshots.
- Breaking changes require a migration note and compatibility aliases for at least one release window.
- Generated CSS must include a header warning that it is generated.
- Agents may propose schema changes, but cannot apply them without human approval.

### Style Dictionary / build tool role

Style Dictionary remains a practical build-system option because it parses and transforms design tokens to CSS, JS, iOS, Android, docs, and other outputs, and is forward-compatible with DTCG concepts. It also demonstrates deep merging, reference resolution, and platform-specific transforms.

For cmux-win, use it only if the build cost is acceptable. A small custom TypeScript generator may be better initially because this Electron app only needs renderer CSS variables and possibly TypeScript constants.

Better-than-Round-1 rule: choose the smallest deterministic generator that enforces schema, references, sorted output, and generated-file boundaries.

## 5. Approaches Better Than Round 1

### A. Contract stack instead of DESIGN.md-only

Round 1 over-weighted DESIGN.md. Better stack:
1. JSON token contract: canonical values and references.
2. Generated CSS: runtime consumption.
3. Component metadata: only for components where AI confusion is likely.
4. DESIGN.md: agent policy and examples.
5. Test evidence: screenshots, accessibility results, performance metrics.

### B. Evidence packet for every AI-generated UI change

A generated UI PR should include:
- token diff
- component/API diff
- generated CSS diff
- Playwright screenshots
- accessibility scan output
- keyboard/focus trace
- CSS/runtime budget result
- manual review notes for semantics and destructive actions

### C. Agent trust levels with hard boundaries

Allow: suggest tokens, draft components, propose metadata, generate screenshots, write tests.
Require approval: schema changes, dependency additions, global CSS changes, MCP integration, generated-file changes.
Block: shell execution from design text, autonomous merge, secret access, runtime remote asset injection, prompt-derived package install.

### D. Local benchmark before tool adoption

Before adopting v0, Figma MCP, Storybook, Style Dictionary, or a metadata generator, run a cmux-win spike with one component group. Candidate group: buttons + command palette + panel tabs. Measure output quality, accessibility, latency, CSS size, and maintenance burden.

## 6. Round 2 Implementation Candidate for cmux-win

Phase 1: Baseline inventory
- Extract current design/prototype.html tokens.
- Scan src/renderer for raw colors and inline style hotspots.
- Map resources/themes/themes.json and xterm theme usage.

Phase 2: Minimal token contract
- Add design/tokens/schema.json.
- Add design/tokens/base.tokens.json.
- Generate src/renderer/styles/generated/tokens.css.
- Add npm script: design:tokens.

Phase 3: DESIGN.md as policy
- Document product feel, token usage, anti-patterns, accessibility gates, performance budgets, and AI instructions.
- Do not duplicate token values except short examples.

Phase 4: Test gates
- Add lint or script to flag new raw hex colors in src/renderer.
- Add Playwright screenshot checks for main shell, sidebar, command palette, panel tabs.
- Add accessibility checks for labels, contrast, keyboard navigation, focus visibility.

Phase 5: Component metadata pilot
- Create metadata only for Button/IconButton, PanelTab, CommandPaletteItem, and Modal/Dialog if present.
- Track whether metadata reduces AI errors before expanding.

## 7. Security and Performance Risk Register

- Figma/MCP risk: third-party MCP bridges have had command-injection class failures. Mitigation: official/allowlisted tools only, no shell interpolation, least privilege.
- Token generator risk: compromised or overbroad dependency can mutate build output. Mitigation: lockfile review, deterministic snapshots, minimal dependencies.
- Generated UI risk: visually correct but inaccessible. Mitigation: evidence packet and human review.
- CSS bloat risk: AI adds duplicate classes and inline styles. Mitigation: raw-color lint, CSS byte budget, duplicate declaration scan.
- Electron risk: expensive effects hurt terminal latency. Mitigation: benchmark xterm typing and panel resize after design changes.
- Schema drift risk: DESIGN.md and generated CSS diverge. Mitigation: tokens are canonical; DESIGN.md references generated docs.

## Source Index

- DTCG Design Tokens Format Module 2025.10: https://www.designtokens.org/tr/drafts/format/
- Style Dictionary overview: https://styledictionary.com/getting-started/installation/
- WCAG 2.2 Recommendation: https://www.w3.org/TR/WCAG22/
- Figma Make/MCP reporting: https://www.theverge.com/news/783828/figma-make-ai-app-coding-mcp-server-update
- Figma Dev Mode MCP reporting: https://www.theverge.com/news/679439/figma-dev-mode-mcp-server-beta-release
- Figma MCP security flaw reporting: https://www.techradar.com/pro/security/worrying-figma-mcp-security-flaw-could-let-hackers-execute-code-remotely-heres-how-to-stay-safe
- Vibe tools 2026 overview: https://www.techradar.com/pro/best-vibe-coding-tools
- Figma2Code 2026: https://arxiv.org/abs/2604.13648
- CoGen 2026: https://arxiv.org/abs/2601.10536
- LLM accessible interface 2026: https://arxiv.org/abs/2601.06616
- Human oversight for accessible generative IUIs 2026: https://arxiv.org/abs/2602.13745
- Vibe Code Bench 2026: https://arxiv.org/abs/2603.04601
- EcoAssist 2026: https://arxiv.org/abs/2604.04332
- Vision-guided frontend refinement 2026: https://arxiv.org/abs/2604.05839
- DesignBench 2025/2026-relevant: https://arxiv.org/abs/2506.06251
