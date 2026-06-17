# Worker3 Prep: Vibe Design RSI Technical Review

Role: Worker3(Codex), code review / bug detection / security checks.
Master: 마스터님.
Prepared: 2026-06-17.
Status: Worker3 각성 완료.

## Research Summary

- Vibe design / web vibe coding: 2026 research warns that LLM-generated web UI tends toward design homogenization unless workflows add productive friction, explicit constraints, and human review. Source: https://arxiv.org/abs/2603.13036
- Design tokens: DTCG Format Module 2025.10 is a 2026-06-13 draft for JSON token exchange. Use it directionally, not as an authoritative compatibility target. Source: https://www.designtokens.org/tr/drafts/format/
- Token automation: Style Dictionary parses, merges, resolves references, transforms tokens, and emits CSS variables and other platform outputs. Source: https://styledictionary.com/getting-started/installation/
- AI-driven UI generation: 2026 Figma2Code and UIPress research show visual fidelity can be strong, but responsiveness, maintainability, and generation cost remain weak spots. Sources: https://arxiv.org/abs/2604.13648 and https://arxiv.org/abs/2604.09442
- Design-agent integration: Figma MCP-style workflows reduce guessing by exposing structured design context, but third-party MCP tooling has shown command-injection risk. Sources: https://www.theverge.com/news/679439/figma-dev-mode-mcp-server-beta-release and https://www.techradar.com/pro/security/worrying-figma-mcp-security-flaw-could-let-hackers-execute-code-remotely-heres-how-to-stay-safe

## DESIGN.md Criteria

Worker1 output should include or imply a repo-level DESIGN.md with:
- Product feel: density, typography, color posture, motion, interaction tone.
- Token map: primitive, semantic, component, state, density, and motion tokens.
- Component rules: variants, states, accessibility behavior, and composition limits.
- AI instructions: how agents modify UI without inventing one-off styles.
- Anti-patterns: banned tropes, raw colors, nested cards, weak contrast, arbitrary spacing.
- Review checklist: visual, code, accessibility, responsive, performance, and security gates.
- Ownership: who changes tokens, versioning, deprecation, and migration policy.

Red flags: vague mood-board language, screenshot-only guidance, no semantic tokens, no generated-code review policy, no migration path.

## Design Token Automation Criteria

Must have:
- Single source of truth, for example design/tokens.
- Schema validation for token files.
- Deterministic token build with stable ordering.
- Reference resolution and circular-reference detection.
- Clear generated output boundary.
- Semantic tokens used by components instead of direct palette tokens.
- Theme/mode structure if light/dark or density variants are required.

Should have:
- Lint rule blocking raw colors, ad hoc spacing, arbitrary shadows.
- Token docs or gallery generated from descriptions.
- Migration script for renamed/deprecated tokens.
- Visual regression coverage for core components.

Reject or revise if outputs are manually edited, token names encode current values instead of purpose, or state/focus/disabled/density tokens are missing.

## AI Component Generation Criteria

Acceptable pipeline:
1. Agent reads DESIGN.md, token schema, and component examples.
2. Agent generates with existing primitives and semantic tokens.
3. Automated checks run: typecheck, lint, unit tests, a11y, visual regression, responsive screenshots.
4. Reviewer verifies API surface, state coverage, and design-system consistency.
5. Component docs list variants and usage constraints.

Quality checks: existing styling conventions; full interaction states; no arbitrary colors; deliberate responsive behavior; keyboard navigation, labels, contrast, reduced motion; no runtime JS for purely presentational token mapping.

Security checks:
- No prompt-derived remote scripts, fonts, or unsafe image URLs.
- No shell execution based on design text.
- MCP/design tools must be allowlisted and least-privilege.
- Use argument-array execution, not shell interpolation.
- No secrets in examples, screenshots, docs, or generated files.
- New dependencies require license, maintenance, and supply-chain review.

## Performance Criteria

Evaluate CSS bundle growth, duplicate rules, runtime theming cost, hydration cost, layout stability, expensive effects, font loading, generated asset size, and cacheability.
Thresholds: no large runtime styling library without proof; token CSS should be small/static/cacheable; no per-render token computation on common paths; visual regression should cover mobile and desktop.

## Worker1 Review Rubric

Score 0-3 each: feasibility, determinism, coverage, AI usability, maintainability, performance, accessibility, security, and testability.

Immediate rejection triggers:
- Interpolates untrusted design input into shell commands.
- Stores agent credentials or API keys in repo.
- Requires manual editing of generated token files.
- Introduces global CSS resets or theme mutations without migration.
- Skips accessibility or visual regression checks for generated components.

## Review Plan When Ordered

1. Read Worker1 report and extract implementation claims.
2. Compare claims against current cmux-win frontend/design-system structure.
3. Identify unsupported assumptions, missing migrations, runtime risks, and test gaps.
4. Check proposed MCP, shell, or AI automation paths for security hazards.
5. Report findings ordered by severity with concrete recommendations.
