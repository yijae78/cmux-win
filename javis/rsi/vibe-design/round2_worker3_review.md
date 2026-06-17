# Worker3 Review: Round 2 Worker1 Synthesis

Reviewer: Worker3(Codex)
Role: code review / bug detection / security checks
Reviewed: 2026-06-17
Input: javis/rsi/vibe-design/round2_worker1_synthesis.md
Reference: javis/rsi/vibe-design/round2_worker3_research.md

## Verdict

Reject Phase 1 as written. Worker1 improved over Round 1 by accepting evidence packets, security gates, and staged metadata, but the proposed execution still has unsafe architecture: global YAML as token SOT, a large global CLAUDE.md split, duplicated token values, weak schema semantics, Windows-incompatible lint scripts, and no compatibility contract for existing projects.

This should not be approved until the design contract is converted from a prose/YAML migration to a versioned, testable, reversible implementation plan.

## Blocking Findings

### Critical: Global YAML as SOT is the wrong abstraction

Worker1 explicitly chooses DESIGN.md YAML as the global token SOT (round2_worker1_synthesis.md:31, 40, 52, 351). This is a regression from the Round 2 research recommendation. YAML frontmatter is readable by agents, but it is not a reliable source of truth for schema validation, generated output, circular reference checks, or project-specific compatibility.

The proposal creates two sources of truth immediately: global YAML tokens and project JSON tokens (lines 31-58). It then says project DESIGN.md references inherited global tokens, while project design/tokens/base.tokens.json is also SOT. That creates ambiguity: if global background, project background, generated CSS, and component metadata disagree, the plan does not define precedence or conflict resolution.

Required fix: DESIGN.md must be policy only. If a global token source is needed, make it a separate versioned token file, e.g. ~/.claude/design/tokens/v1/base.tokens.json, and generate any readable DESIGN.md excerpt from it.

### Critical: Phase 1 can break every project using global CLAUDE.md

The plan proposes moving 922 lines out of ~/.claude/CLAUDE.md into ~/.claude/DESIGN.md (lines 83-119, 636-638, 681-687). This is a global file, not a cmux-win-local file. Any project, agent, script, or prompt profile that only loads CLAUDE.md will silently lose the design instructions unless it is updated to read DESIGN.md.

This is not a safe migration. There is no compatibility period, no loader check, no automated test proving agents read DESIGN.md, no backup/rollback procedure, and no inventory of consumers of ~/.claude/CLAUDE.md. The current plan replaces content with a pointer and assumes all agents obey it. That is not an engineering guarantee.

Required fix: keep CLAUDE.md design content in place during a transition window, add DESIGN.md as duplicate/generated companion first, add an explicit loader/agent check, then remove duplicated sections only after verifying each agent/runtime reads DESIGN.md.

### Critical: YAML schema is not a real schema

The proposed frontmatter has schemaVersion but no schema definition, type constraints, parser contract, or validation command (lines 130-246). Several fields are ambiguous or implementation-hostile:
- generatedAt is hard-coded in a hand-authored policy file, so it will become stale immediately.
- brand_mood values are subjective numbers with no unit or consuming code.
- typography mixes CSS strings, numeric values, ranges like 700-900, and prose-like values such as 14-16px.
- colors mix hex, rgba strings, arrays, nested maps, and duplicated RGB strings.
- performance limits use arbitrary counts without measurement method or enforcement target.

This is documentation, not a machine contract. Agents may parse it, but build tooling cannot safely validate or transform it.

Required fix: define JSON Schema or Zod schema first. Every token should have type, value, description, unit where needed, and optional deprecated/replacement metadata. Keep human mood guidance out of token objects.

### Critical: Token values are duplicated between YAML and Markdown

Worker1 says the Markdown body will contain the existing CLAUDE.md design sections and that token values are synchronized with YAML (lines 278-323). No synchronization mechanism is provided. Manual sync across a 1,000-line DESIGN.md is guaranteed drift.

Required fix: do not duplicate token values in prose. Generate token tables from canonical token files or keep prose examples intentionally non-authoritative.

## Token Naming Findings

### High: Token naming is internally inconsistent

The proposed naming mixes several incompatible vocabularies: colors.bg.*, colors.surface.*, colors.semantic.*, semantic_rgb, accent.blue_cyan, and CSS aliases like --surface-base / --interactive-primary (lines 149-178, 331-345). Some names describe UI role, some describe color hue, some describe status, and some describe implementation format.

Examples:
- colors.bg.primary maps to --surface-base, but bg and surface are different concepts.
- colors.semantic.info maps to --status-info, but then --accent maps to project-specific interactive primary.
- colors.semantic_rgb duplicates colors.semantic as strings rather than deriving RGB output.
- accent.blue_cyan is a color-family bucket, not a semantic usage token.
- text.emphasis/default/subtle is semantic, but bg.void/primary/raised is spatial/visual.

Required fix: define layers explicitly: primitive.palette.*, semantic.color.*, component.*, and output CSS names. Components must consume semantic/component tokens, not primitive hue buckets. RGB variants should be generated, not authored.

### High: Token units and value domains are unclear

Spacing uses numeric values without declaring px/rem output (lines 190-193). Radius uses numbers without units (lines 196-201). Breakpoints use numbers without px/rem semantics (lines 244-246). Typography uses mixed string ranges and CSS snippets (lines 180-189).

This prevents deterministic generation. A generator cannot know whether 10 means 10px, 10rem, or a scale index.

Required fix: every numeric token category must declare unit at the category level or per token. Textual ranges should become either concrete tokens or policy prose, not token values.

### High: Remote font CDN in global design policy is a security/performance footgun

The YAML includes pretendard_cdn pointing to jsDelivr (line 183). A global design system must not make remote runtime asset loading a default. For Electron apps and offline projects, this can break offline use, leak requests, add startup latency, and create supply-chain exposure.

Required fix: document font preference separately from runtime loading. Projects must opt in to hosted fonts, self-hosted fonts, or system fallback based on their security/performance profile.

## Migration Safety Findings

### Critical: Existing projects will break or silently diverge

The migration says new projects use only semantic CSS variables and existing projects add aliases project-by-project (lines 351-361). That is not safe. If global DESIGN.md changes immediately but old projects still use old variables, agents may start generating new semantic variables into old codebases without the alias layer present. The result is broken styling or mixed token systems.

The plan also says Phase M5 removes aliases eventually but gives no compatibility contract, no detection for projects still using old names, and no release window.

Required fix: global policy must say old names remain valid until a versioned deprecation date. Agent instructions must forbid emitting new semantic variables into a project unless that project declares tokenSchemaVersion support.

### High: CSS fallback chains mask migration bugs

The suggested fallback background: var(--surface-base, var(--bg-primary, #0c111b)) (lines 608-615) prevents obvious failures by hiding missing tokens behind hard-coded values. This is acceptable only as a temporary compatibility alias layer, not as normal component code. Otherwise missing tokens pass visual smoke tests and drift continues.

Required fix: put fallbacks in generated compatibility CSS, not in component code. Components should use one canonical variable. CI should fail on missing canonical tokens in migrated projects.

### High: No rollback or backup plan for global file edits

The plan asks to move a large global CLAUDE.md section (lines 681-687), but does not define a backup path, diff strategy, restore command, or validation command. Because this touches ~/.claude rather than just /c/dev/cmux-win, the blast radius is all sessions and projects.

Required fix: require timestamped backup, dry-run extraction, round-trip line-count verification, link-checking, and a rollback command before approval.

### Medium: Project identity is confused

The report alternates between global design system, cmux-win, and all projects. It uses ~/.claude paths for components (lines 119, 539-547) while also discussing project-level JSON tokens. This will make agents apply global glassmorphism/button/modal rules to projects that do not use React, do not have CSS variables, or have domain-specific design systems.

Required fix: separate global policy from project opt-in. Global components metadata should be templates, not active rules, unless a project declares compatibility.

## Component Metadata and Performance Findings

### High: Global component metadata can increase prompt cost and design drift

The plan creates five global meta.json files under ~/.claude/components (lines 119, 539-547), then later expands from 5 to 15 components (line 656). There is no loading policy, size budget, cache strategy, or on-demand retrieval protocol. If agents load all global metadata for every UI request, this increases context cost and may bias unrelated projects toward the global component model.

Required fix: metadata must be discoverable through a small index first. Load full component metadata only when the project has opted in and the component is relevant. Add metadata size limits and require examples to reference project-local components when available.

### High: Metadata is not tied to actual code APIs

The proposed meta.json list describes generic glass-card, button, input, modal, and toast components, but does not map them to real exported components, props, files, or styling APIs. In cmux-win, there is no central Button primitive or Storybook-style component package. The renderer has concrete components under src/renderer/components and many inline styles in App.tsx.

Metadata without code bindings makes agents hallucinate components that do not exist.

Required fix: metadata fields must include implementationPath, exportName, propsSchema or usageExamples, tokenDependencies, accessibilityStates, and testRefs. If a component does not exist, label it as a template, not an available primitive.

### Medium: Performance budgets are arbitrary and partly unenforceable

The global budget says max_backdrop_filter: 8 and max_css_variables: 80 (lines 238-240, 488-493). These numbers are not tied to viewport, DOM subtree, Electron renderer measurements, or xterm latency. max_css_variables: 80 is also likely too low once themes, semantic aliases, state tokens, and compatibility aliases are included.

Required fix: budgets should be measured per project and enforced by scripts. For cmux-win, track renderer startup, panel resize latency, xterm typing latency, CSS bytes, duplicate declarations, and long frames. Do not put arbitrary universal limits in global YAML as if they are validated facts.

### Medium: Always-on DESIGN.md may be too large

The proposed DESIGN.md is about 1,000 lines and includes full sections for colors, typography, icons, components, animation, accessibility, layout, data visualization, PWA, CSS injection, performance, security, and checklists (lines 83-323). Making this always-on context for agents may be more expensive than targeted retrieval and can increase contradictory instructions.

Required fix: split into a short DESIGN.md contract plus referenced detail files, or create an index that agents use to load relevant sections only.

## Code Quality of Proposed Lint Hook

### High: design-lint.sh is not Windows-safe and not repo-safe

The proposed hook is bash/grep based (lines 563-584). cmux-win is a Windows Electron project. The repo already uses npm scripts, ESLint, TypeScript, Vitest, and Playwright. A bash-only hook will fail or behave inconsistently in PowerShell/cmd contexts. It also scans only src/, while the proposal itself affects ~/.claude and project design files.

Required fix: implement lint as a Node/TypeScript script or ESLint custom rule so it works on Windows and CI.

### High: grep rules are brittle and will produce false positives/false negatives

The raw hex grep only catches six-digit hex and misses #fff, #ffffffff, rgb(), rgba(), hsl(), named colors, style object values, and CSS-in-JS template strings. It also allows // token: comments as bypasses without verifying the token. The inline style grep will flag many existing cmux-win patterns but only warns, so it cannot enforce migration.

Required fix: parse TSX/JSX/CSS with AST or PostCSS. Build an allowlist for generated files and existing debt. Fail only on new violations after baseline snapshot.

### Medium: Tailwind arbitrary checks do not apply cleanly

cmux-win does not currently use Tailwind. Checking bg-[#...] and w-[...] is not enough, and may distract from the real problem: hard-coded inline React style values and prototype CSS variables.

Required fix: target current architecture first: inline style object color/background/borderRadius/shadow values, CSS variable inventory, and resources/themes/themes.json mapping.

## Missing Edge Cases

- No tokenSchemaVersion handshake for projects. Agents need to know whether a project supports old names, new names, or both.
- No support matrix for non-web projects, Python scripts, PPT/sermon tools, Electron apps, static HTML prototypes, or SharePoint/Office outputs.
- No strategy for resources/themes/themes.json or xterm ANSI colors in cmux-win. Terminal themes are separate from marketing/UI tokens.
- No validation for rgba token accessibility. Contrast tools need resolved colors over concrete backgrounds.
- No policy for dark/light/high-contrast token inheritance. The plan adds high contrast CSS but not token-layer mode modeling.
- No generated-file boundary for global DESIGN.md or component metadata.
- No dependency review for axe-core, Style Dictionary, YAML parser, or future metadata tooling.
- No way to prevent agents from applying global glassmorphism rules to dense operational UIs where the repo design should stay utilitarian.
- No test that a project still builds after semantic variable emission.
- No visual regression baseline before global design changes.

## Approval Conditions

Do not approve Phase 1 until all of the following are true:

1. A compatibility plan proves existing projects keep receiving design instructions after the CLAUDE.md split.
2. DESIGN.md is policy-only, or canonical tokens are moved to a separate validated token file.
3. A schema validator exists before any schema is called production.
4. Token naming layers are defined: primitive, semantic, component, output aliases.
5. Migration includes project opt-in, tokenSchemaVersion, aliases, deprecation windows, and rollback.
6. Global component metadata is loaded on demand and maps to real implementation APIs or is explicitly marked template-only.
7. Linting is implemented in Node/TypeScript or ESLint, not bash grep.
8. cmux-win-specific performance budgets are measured on Electron workflows, not guessed globally.
9. A dry-run extraction and restore path exists for ~/.claude/CLAUDE.md.
10. Existing raw style debt is baselined so new lint gates do not block the repo immediately.

## Safer Replacement Plan

1. Create ~/.claude/DESIGN.md as an additive file first. Do not remove the CLAUDE.md design section yet.
2. Add a short CLAUDE.md pointer while keeping existing content for one transition period.
3. Add ~/.claude/design/tokens/v1/base.tokens.json if global tokens are needed. Use DESIGN.md to explain policy only.
4. Add a validator script and run it in dry-run mode.
5. Add project opt-in marker, for example DESIGN_COMPAT.md or design/config.json with tokenSchemaVersion.
6. For cmux-win, first inventory existing inline styles, design/prototype.html tokens, and resources/themes/themes.json.
7. Pilot one real component group only: PanelTab or CommandPaletteItem, because those exist in the repo.
8. Measure token/context size and renderer performance before expanding metadata.

## Final Assessment

1. Code quality of proposed DESIGN.md YAML schema: not acceptable as production schema. It is untyped documentation with mixed units, duplicated values, stale generatedAt, remote asset references, and no validator.
2. Token naming consistency: partially improved but still inconsistent across bg/surface/status/accent/semantic/RGB layers. RGB aliases should be generated; component-level tokens are missing.
3. Migration safety: unsafe. Existing projects can break or silently drift because global CLAUDE.md content is moved before consumer verification and semantic variables can be emitted into projects without aliases.
4. Component metadata performance: risky. Five global files may be acceptable only with on-demand loading and real API bindings; expansion to 15 without measurement is premature.

Worker3 recommendation: require a Round 3 revision before implementation. The next revision must be a concrete migration spec with validators, rollback, project opt-in, actual cmux-win inventory, and measured budgets. Be stricter: no approval for moving ~/.claude/CLAUDE.md content until the compatibility proof exists.
