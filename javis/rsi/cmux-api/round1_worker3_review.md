# Worker3 Review: cmux-win API RSI Round 1

Reviewer: Worker3(Codex)
Scope: src/main/socket/handlers, src/shared/panel-layout-utils.ts, src/main/remote
Date: 2026-06-17
Constraint: 원본 소스 수정 없음. 보고서 파일만 생성.

## Executive Summary

cmux-win의 JSON-RPC 소켓 API는 마스터 Claude가 이미 쓰는 tmux shim 수준보다 훨씬 강한 오케스트레이션 기능을 갖고 있다. 특히 system.tree, system.capabilities, surface.health, agent.send_task, agent.rerun, agent.wait, agent.output, workflow.run, browser.* DOM 자동화, workspace.set_layout 조합은 마스터 Claude가 패널 상태를 추론하지 않고 구조화 데이터 기반으로 작업 지휘를 하게 만든다.

가장 큰 개선 포인트는 API 발견성과 안전한 고수준 orchestration wrapper다. 현재 기능은 충분히 많지만, CLI/tmux 사용 흐름에는 일부만 노출되어 있고, browser.eval 및 workspace.set_layout 같은 강력 기능은 검증/권한/스키마 가드가 더 필요하다.

## 1. Socket Handler API Inventory and Master Claude Opportunities

### system handlers

Files: src/main/socket/handlers/system.ts

Registered methods:
- system.ping
- system.identify
- system.tree
- system.capabilities

High-value underused capabilities:
- system.capabilities returns router.getMethods(). This is the API discovery endpoint Master Claude should call before deciding what tools are available.
- system.tree returns workspace -> panel -> surface -> agent topology plus focus. This is better than parsing tmux list/capture output because it includes panelLayout, panel IDs, surface IDs, agent status, and focus in one call.
- system.identify accepts surfaceId and returns caller context: surfaceId, panelId, paneIndex, workspaceId, workspaceName. Master Claude can use it to map a terminal to the app topology.

Recommended Master usage:
1. Call system.capabilities once at session start.
2. Call system.tree before spawning/splitting/closing panels.
3. Call system.identify with current surfaceId when a worker reports only its surface context.

### window handlers

Files: src/main/socket/handlers/window.ts

Registered methods:
- window.list
- window.current
- window.create
- window.move
- window.close

High-value underused capabilities:
- window.move can reposition the first BrowserWindow with x/y/width/height. This is useful for RSI dashboards, screen sharing, and arranging cmux on a known monitor.
- window.create and window.close exist at state level, but window.move operates on BrowserWindow.getAllWindows()[0], not a passed windowId.

Risk / limitation:
- window.move ignores windowId and always moves the first Electron window. This is surprising when multiple windows exist.
- window.create dispatches state but actual BrowserWindow creation depends on the surrounding main-process flow; Master should verify through window.list/current afterward.

### workspace handlers

Files: src/main/socket/handlers/workspace.ts

Registered methods:
- workspace.list
- workspace.current
- workspace.create
- workspace.select
- workspace.close
- workspace.set_layout
- workspace.rename

High-value underused capabilities:
- workspace.set_layout can replace the full PanelLayoutTree. Combined with collectLeafIds/rebuildEqualLayout semantics, Master Claude can impose deterministic layouts instead of repeatedly splitting manually.
- workspace.create accepts cwd. This can establish project-scoped workspaces for workers.
- workspace.rename gives Master a clean way to label RSI phases or task contexts.

Risk / limitation:
- workspace.set_layout accepts unknown panelLayout from params and relies on store/action validation path. It should expose a safer high-level equalize endpoint or validate against PanelLayoutTreeSchema explicitly at handler boundary.

### panel handlers

Files: src/main/socket/handlers/panel.ts

Registered methods:
- panel.list
- panel.focus
- panel.split
- panel.resize
- panel.zoom
- panel.close

High-value underused capabilities:
- panel.split accepts newPanelType terminal/browser/markdown plus url/filePath and returns paneIndex, panelId, surfaceId. This is much better than tmux split-window because the caller immediately receives the IDs needed for follow-up commands.
- panel.zoom can temporarily focus one worker/output panel.
- panel.resize can tune a specific split ratio directly.

Important behavior:
- panel.split now rebuilds the whole workspace layout as an equal balanced tree after adding the panel. This prevents nested split shrinkage.
- browser and markdown panels can be created through the same split API; Master Claude can open docs/dashboards/markdown reports inside cmux instead of only terminal panes.

Risk / limitation:
- panel.split casts direction string to horizontal/vertical. Invalid direction should be rejected explicitly before dispatch.
- Returned new panel is inferred from panels slice after panelsBefore; concurrent mutations could make this fragile if multi-client operations happen.

### surface handlers

Files: src/main/socket/handlers/surface.ts

Registered methods:
- surface.list
- surface.create
- surface.close
- surface.focus
- surface.send_text
- surface.rename
- surface.read
- surface.health

High-value underused capabilities:
- surface.health reports hasPty, bufferSize, terminal metadata, and attached agent. This is the safest preflight before sending text to a worker.
- surface.read reads real-time live PTY buffer first, falling back to scrollbackStore. It strips ANSI escapes and supports lines.
- surface.rename gives Master a durable label layer without depending on shell title output.
- surface.create can add a browser/markdown/terminal surface inside an existing panel.

Important behavior:
- surface.send_text refuses to report success if the surface has no active PTY. That prevents silent command loss.
- surface.read and agent.output overlap, but surface.read works for any surface with buffered terminal content.

Risk / limitation:
- hasPty is currently inferred from live buffer presence. A live PTY with empty/no-yet-written buffer can be misreported as absent depending on initialization behavior.
- surface.rename dispatch result is ignored; it should check result.ok like other handlers.

### agent handlers

Files: src/main/socket/handlers/agent.ts

Registered methods:
- agent.spawn
- agent.session_start
- agent.status_update
- agent.session_end
- agent.send_task
- agent.rerun
- agent.wait
- agent.output

High-value underused capabilities:
- agent.spawn returns paneIndex, panelId, surfaceId. Master Claude should use this instead of guessing the new pane after spawning Gemini/Codex.
- agent.send_task sends text and Enter as separate PTY chunks with a 500ms delay. This solves Ink TUI submit issues and is safer than direct surface.send_text for follow-up prompts.
- agent.rerun chooses interactive mode if the agent is alive, otherwise relaunches the CLI with proper flags. This is a high-value recovery primitive.
- agent.wait blocks until PTY exit or timeout. Useful for non-interactive jobs or health-gated workflows.
- agent.output returns last N clean lines from live buffer/scrollback. Useful for summarizing worker progress without full capture.

Important behavior:
- agent.send_task has a surfaceId send lock with 30s TTL to avoid interleaved prompt sends.
- agent.rerun relaunch mode builds shell command strings for gemini/codex/other agent types.

Risk / limitation:
- agent.rerun relaunch mode performs shell command string construction with quote escaping only for double quotes. This should be reviewed for shell injection and Windows shell metacharacters if exposed to untrusted task text.
- agent.wait only watches pty-exit/status. Interactive agents that become idle without exiting need workflow.run or future idle endpoint.
- agent.output duplicates ANSI stripping logic instead of reusing stripAnsiEscapes from shared/ansi-utils like surface.read does.

### browser handlers

Files: src/main/socket/handlers/browser.ts

Registered methods:
- browser.eval
- browser.snapshot
- browser.screenshot
- browser.click
- browser.type
- browser.fill
- browser.press
- browser.wait
- browser.navigate
- browser.url.get
- browser.title.get

High-value underused capabilities:
- browser.snapshot returns document.documentElement.outerHTML. Master Claude can inspect browser-panel DOM without OCR.
- browser.navigate/url.get/title.get provide a minimal browser automation loop.
- browser.click/fill/type/press/wait can operate on webviews that expose data-cmux-ref or selectors.
- browser.screenshot is currently a text/HTML snapshot wrapper, not real image capture.

Security concern:
- browser.eval executes arbitrary JS in renderer webview context. This is powerful and should remain restricted to automation/password/allow-all modes. It should not be available in cmux-only mode.
- browser.click/fill interpolate p.ref into a selector string without JSON.stringify. A malicious ref containing quotes/brackets can break the selector string or execute unintended JS. Use JSON.stringify selector construction or CSS.escape in the webview.

### workflow handlers

Files: src/main/socket/handlers/workflow.ts

Registered methods:
- workflow.run

High-value underused capabilities:
- workflow.run lets any planner provide a multi-step agent workflow. It spawns agents sequentially, waits for idle/crash/timeout, and returns per-step output.
- waitForIdle combines idle-pattern matching with output stabilization, plus pty-exit monitoring. This is stronger than raw sleep-based orchestration.

Limitations:
- Idle patterns are defined only for gemini and codex. Claude/opencode get empty pattern list and rely on stabilization only.
- workflow.run always spawns new panels. It does not reuse existing agent surfaces or close panels after completion.
- cwd is accepted per step and passed to agent.spawn, useful for project-specific worker runs.

### notification and telegram handlers

Files: src/main/socket/handlers/notification.ts; src/main/notifications/telegram-bot.ts

Registered methods:
- telegram.set_token
- telegram.get_token_status
- telegram.delete_token
- telegram.test
- notification.create
- notification.list
- notification.clear

High-value underused capabilities:
- notification.create can attach workspaceId and surfaceId. Master Claude can send structured handoff or alert messages linked to a worker.
- notification.clear can clear all or workspace-scoped notifications.
- Telegram remote control supports /status, /agents, /approve, /reject, /send, /task, and inline confirmation callbacks. This gives mobile remote control of agents.

Security posture:
- Telegram token is stored through safeStorage-backed token store, not app state. Good.
- Telegram inbound commands are guarded by chatId and ignore unauthorized chats. Good.
- Plain text messages are blocked; explicit commands only. Good.

### settings handlers

Files: src/main/socket/handlers/settings.ts

Registered methods:
- settings.get
- settings.update

High-value underused capabilities:
- settings.get can let Master inspect socket mode, Telegram, bridge, agent orchestration, accessibility, and browser settings.
- settings.update allows partial settings changes through store validation. Could be used to toggle bridge/telegram/socket/agent settings from automation.

Risk / limitation:
- settings.update accepts arbitrary object at handler boundary and depends on store/action schema. For remote automation, add documented partial schema examples and sensitive-setting audit logs.

## 2. panel-layout-utils.ts: Equal Split Implementation

File: src/shared/panel-layout-utils.ts

### Data model

PanelLayoutTree is a binary tree:
- leaf: { type: leaf, panelId }
- split: { type: split, direction, ratio, children: [left, right] }

ratio is the fraction assigned to the left/top child depending on direction. Children recursively divide their assigned region.

### Utility functions

- findLeaf(tree, panelId): DFS search for a leaf by panelId.
- replaceLeaf(tree, panelId, replacement): immutable replacement of a matching leaf.
- findParentSplit(tree, panelId): finds the split node that directly contains the target leaf and returns its direction/ratio.
- updateRatioForPanel(tree, panelId, newRatio): clamps ratio to [0.1, 0.9] and updates the direct parent split containing the target leaf.
- equalizeLayout(tree): recursively sets every existing split ratio to 0.5 without changing tree shape.
- collectLeafIds(tree): left-to-right DFS list of leaf panel IDs.
- rebuildEqualLayout(panelIds, direction): rebuilds a new balanced binary split tree in one direction.
- removeLeaf(tree, panelId): removes a panel leaf and promotes its sibling.

### Exact equal-split behavior

There are two distinct equalization modes:

1. equalizeLayout(existingTree)
- Preserves the current nested shape.
- Sets every split ratio to 0.5.
- This does not guarantee all leaves get equal area if the tree is unbalanced. Example: a chain of three leaves can still produce 50%, 25%, 25%.

2. rebuildEqualLayout(panelIds, direction)
- Rebuilds the whole tree from the panel ID list.
- For 0 panels, returns leaf with empty panelId. This is a questionable fallback and should not be used as a real layout.
- For 1 panel, returns one leaf.
- For 2 panels, returns one split ratio 0.5.
- For N > 2, splits panelIds at mid = ceil(N/2), sets root ratio = left.length / N, and recursively rebuilds both sides.

This does produce equal leaf sizes for any N under the same direction because each subtree receives a proportional region matching its leaf count. Example N=3: root ratio 2/3, left subtree has two leaves split 0.5 each, so leaves are 1/3, 1/3, 1/3. Example N=5: root ratio 3/5, left subtree distributes 3 leaves equally, right subtree distributes 2 leaves equally, so all leaves are 1/5.

### Where rebuildEqualLayout is used

- App.tsx equalizeHorizontal/equalizeVertical collects active workspace leaf IDs and dispatches workspace.set_layout with rebuildEqualLayout(panelIds, direction).
- store.ts panel.split adds the new panel ID and rebuilds the entire workspace layout with the requested direction. This prevents exponential shrinkage from nested split chains.
- store.ts agent.spawn always rebuilds the workspace layout horizontally after adding the agent panel.

### Correctness assessment

The core equal-size math is correct for a single-axis balanced tree. It is intentionally destructive to mixed-direction layout structure: when called, all existing split directions are replaced with the chosen direction. That is good for equalize horizontal/vertical commands, but it means split operations erase prior mixed layouts.

Technical risks:
- rebuildEqualLayout([]) returns a leaf with empty panelId; this can create invalid topology if ever used outside guarded paths.
- workspace.set_layout accepts externally supplied layout; invalid trees could bypass collect/rebuild safety unless action validation catches them.
- updateRatioForPanel updates the first split where the target is a direct child. For nested layout, resizing a subtree leaf changes only its immediate parent, which is expected but should be documented for UI resize semantics.

## 3. src/main/remote: Remote Control Functionality

File: src/main/remote/ssh-session.ts

### SSH target parsing

parseSshTarget(target) supports:
- host
- user@host
- host:port
- user@host:port

It uses regex ^(?:([^@]+)@)?([^:]+)(?::(\\d+))?$ and returns { user?, host, port? }.

### SSH command construction

buildSshCommand(target) returns spawn args suitable for node-pty:
- shell: ssh
- args: [ -p port, -l user, host ] as applicable

This avoids string shell concatenation and is safer than building one command string.

### Session creation

createSshSession(target) checks ssh availability with where ssh, parses target if needed, and returns { ok: true, spawn } or { ok: false, error }.

### Actual integration status

src/main/remote currently only builds SSH spawn arguments; it does not create a workspace, panel, PTY, or reconnect loop by itself. The CLI command cmux-win ssh imports parseSshTarget/buildSshCommand, creates a workspace named SSH: host, and prints the ssh command to run. It does not automatically start the SSH PTY in that workspace.

Remote control is broader than src/main/remote:
- TelegramBotService provides mobile command control via /status, /agents, /approve, /reject, /send, /task.
- Socket API provides local JSON-RPC remote control over TCP localhost:19840 with auth modes.
- Cowork Bridge and CLI paths appear elsewhere and can drive surfaces through socket methods.

### Reconnection state

nextReconnectState and initialReconnectState define exponential backoff: 1s, 2s, 4s, 8s, 16s, max 5 retries, but no caller currently wires this into live SSH reconnection in src/main/remote.

### Remote feature gaps

- No socket handler for remote.ssh.connect.
- No automatic PTY launch for SSH from CLI beyond printing command.
- remoteSession exists in WorkspaceState/schema, but the analyzed SSH module does not persist session state into workspace.
- Reconnect state is implemented as pure functions but not integrated into PTY lifecycle.

## 4. Master Claude: Best Unused / Underused API Playbook

Recommended high-leverage sequence:

1. Discover
- system.capabilities
- system.tree
- settings.get

2. Preflight before sending to any worker
- surface.health(surfaceId)
- surface.read(surfaceId, lines)
- agent.output(surfaceId, lines) when the surface is an agent

3. Spawn and track workers
- agent.spawn(agentType, workspaceId, task) and store returned panelId/surfaceId/paneIndex
- surface.rename(surfaceId, label) to label worker purpose
- agent.send_task(surfaceId, task) for follow-up instructions

4. Recover stuck workers
- surface.health to verify PTY
- agent.output to inspect tail
- agent.rerun to send interactively or relaunch
- agent.wait only when expecting PTY exit

5. Manage layout deterministically
- system.tree to get current workspace/panels
- workspace.set_layout with a generated PanelLayoutTree for deliberate layout
- panel.zoom for focused review
- panel.split with newPanelType browser/markdown for dashboards/reports

6. Browser panel automation
- panel.split(newPanelType=browser, url)
- browser.wait(selector)
- browser.snapshot
- browser.fill/click/press
- browser.url.get/title.get

7. Full workflow delegation
- workflow.run for sequential multi-agent plans where new panels per step are acceptable.

## 5. Technical Improvement Proposals

### P0: Document and expose Master orchestration API

Problem: system.capabilities exposes method names, but there is no higher-level contract document that tells Master Claude the intended orchestration sequence.

Proposal: add generated API docs or a master_api.md that groups methods by workflow: discover, spawn, send, read, wait, recover, layout, browser, notification, remote. This report can be the seed.

### P0: Add a high-level agent orchestration endpoint

Current Master must manually combine agent.spawn, surface.health, agent.send_task, agent.output, agent.rerun, and agent.wait.

Proposal: add methods such as:
- agent.ensure { agentType, workspaceId, task?, label? }
- agent.send_and_wait { surfaceId, task, idleTimeout }
- agent.tail { surfaceId, lines, stripAnsi }
- agent.recover { surfaceId, task, strategy }

This would reduce fragile orchestration logic in external leaders.

### P0: Harden browser automation string construction

browser.click and browser.fill interpolate ref into JavaScript selector strings. Use JSON.stringify for the full selector or CSS.escape inside executed code. Keep browser.eval restricted by auth mode and consider audit logging for eval calls.

### P1: Add layout-safe APIs

workspace.set_layout is powerful but low-level. Add safe wrappers:
- workspace.equalize { workspaceId, direction }
- workspace.layout_preview { workspaceId, direction }
- workspace.layout_validate { panelLayout }

Also reject rebuildEqualLayout([]) at call sites or replace empty leaf fallback with an explicit error in wrappers.

### P1: Implement remote.ssh.connect end-to-end

The remote SSH module has parser/build/reconnect primitives but no socket handler that launches SSH. Add:
- remote.ssh.parse { target }
- remote.ssh.connect { target, windowId?, workspaceId?, name? }
- remote.ssh.status { workspaceId }
- remote.ssh.reconnect { workspaceId }

Implementation should create/select workspace, create terminal surface, send or spawn ssh command through node-pty, and persist WorkspaceState.remoteSession.

### P1: Align SSH CLI with actual remote session behavior

Current cmux-win ssh creates a workspace and prints Run: ssh ... rather than launching SSH. Either rename it to ssh-plan or complete it so it actually opens a terminal and starts SSH.

### P1: Add structured validation at handler boundary

Several handlers cast params directly. Add zod schemas per socket method or reuse shared action schemas for params. Priority targets:
- workspace.set_layout
- panel.split direction/newPanelType
- settings.update
- browser.* params
- agent.rerun task/agentType

### P1: Make surface PTY health explicit

surface.send_text and surface.health infer PTY status from __cmuxLiveBuffers. Introduce a dedicated global/live PTY registry API from pty-manager, e.g. hasPty(surfaceId), getPtyStatus(surfaceId), getBuffer(surfaceId). This avoids false negatives when a PTY exists but buffer state is empty or not initialized.

### P2: Reduce duplicated ANSI stripping logic

surface.read uses stripAnsiEscapes, while workflow.ts and agent.output duplicate regexes. Consolidate all clean-output reads through a shared helper to avoid inconsistent escape handling.

### P2: Extend workflow.run reuse and cleanup modes

Add workflow.run options:
- reuseAgent: true/false
- closePanelsOnComplete: true/false
- parallel groups
- idlePatternOverride
- outputLines

This would make it more useful for RSI worker fleets without leaving many panels open.

### P2: Improve window.move semantics

window.move should accept windowId and move the matching BrowserWindow instead of BrowserWindow.getAllWindows()[0]. If state window IDs are not currently mapped to BrowserWindow IDs here, expose a window-manager method.

### P2: Promote API usage to CLI/cmux MCP

The CLI and cmux MCP should expose high-value APIs directly:
- capabilities
- tree
- health
- tail/output
- send-task
- rerun
- workflow-run
- browser snapshot/navigate
- equalize layout

This makes the hidden API usable without custom JSON-RPC calls.

## 6. Risk Notes

- browser.eval is intentionally powerful. Keep it out of cmux-only mode and consider per-call logs.
- agent.rerun relaunch command construction should be treated as shell-sensitive. Prefer argument-array spawn paths where possible.
- workspace.set_layout can corrupt UI topology if invalid trees pass in. Validate before mutation.
- Telegram /send has confirmation callback, which is good. Direct /task sends to Claude without confirmation; acceptable for owner chat but worth documenting.
- remoteSession state is defined but not yet fully realized by SSH workflow. Avoid presenting SSH reconnect as implemented until wired.

## 7. Bottom Line

cmux-win already contains a strong control plane, but Master Claude is likely underusing it. The highest-value immediate change is not new low-level capability; it is a documented and safer orchestration layer over the APIs already present.

Most useful hidden APIs for Master Claude:
- system.tree
- system.capabilities
- surface.health
- surface.read
- agent.spawn return IDs
- agent.send_task
- agent.rerun
- agent.wait
- agent.output
- workflow.run
- browser.snapshot / browser.wait / browser.navigate
- workspace.set_layout
- panel.split browser/markdown modes

Recommended next engineering step: build a master-control helper around these methods, then harden browser/ref string handling and add remote.ssh.connect as the first missing end-to-end remote feature.
