import { describe, it, expect } from 'vitest';
import {
  WindowStateSchema,
  WorkspaceStateSchema,
  PanelStateSchema,
  SurfaceStateSchema,
  SettingsStateSchema,
} from '../../../src/shared/schemas';

describe('Zod Schemas', () => {
  it('validates WindowState', () => {
    expect(
      WindowStateSchema.safeParse({
        id: 'win-1',
        workspaceIds: ['ws-1'],
        geometry: { x: 0, y: 0, width: 1200, height: 800 },
        isActive: true,
      }).success,
    ).toBe(true);
  });

  it('rejects WindowState without id', () => {
    expect(
      WindowStateSchema.safeParse({
        workspaceIds: [],
        geometry: { x: 0, y: 0, width: 100, height: 100 },
        isActive: false,
      }).success,
    ).toBe(false);
  });

  it('validates WorkspaceState', () => {
    expect(
      WorkspaceStateSchema.safeParse({
        id: 'ws-1',
        windowId: 'win-1',
        name: 'WS',
        panelLayout: { type: 'leaf' as const, panelId: 'p-1' },
        agentPids: {},
        statusEntries: [],
        unreadCount: 0,
        isPinned: false,
      }).success,
    ).toBe(true);
  });

  it('validates PanelState', () => {
    expect(
      PanelStateSchema.safeParse({
        id: 'p-1',
        workspaceId: 'ws-1',
        panelType: 'terminal',
        surfaceIds: ['s-1'],
        activeSurfaceId: 's-1',
        isZoomed: false,
      }).success,
    ).toBe(true);
  });

  it('rejects invalid panelType', () => {
    expect(
      PanelStateSchema.safeParse({
        id: 'p-1',
        workspaceId: 'ws-1',
        panelType: 'invalid',
        surfaceIds: [],
        activeSurfaceId: '',
        isZoomed: false,
      }).success,
    ).toBe(false);
  });

  it('validates SurfaceState with terminal', () => {
    expect(
      SurfaceStateSchema.safeParse({
        id: 's-1',
        panelId: 'p-1',
        surfaceType: 'terminal',
        title: 'PS',
        terminal: { pid: 1234, cwd: 'C:\\Users', shell: 'powershell' },
      }).success,
    ).toBe(true);
  });

  it('validates SettingsState', () => {
    expect(
      SettingsStateSchema.safeParse({
        appearance: { theme: 'system', language: 'system', iconMode: 'auto' },
        terminal: {
          defaultShell: 'powershell',
          fontSize: 14,
          fontFamily: 'Consolas',
          themeName: 'Dracula',
          cursorStyle: 'block',
        },
        browser: {
          searchEngine: 'google',
          searchSuggestions: true,
          httpAllowlist: [],
          externalUrlPatterns: [],
        },
        socket: { mode: 'automation', port: 19840 },
        agents: {
          claudeHooksEnabled: true,
          codexHooksEnabled: true,
          geminiHooksEnabled: true,
          orchestrationMode: 'auto',
        },
        telemetry: { enabled: true },
        updates: { autoCheck: true, channel: 'stable' },
        accessibility: { screenReaderMode: false, reducedMotion: false },
      }).success,
    ).toBe(true);
  });
});
