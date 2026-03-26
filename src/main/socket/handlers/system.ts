import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerSystemHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('system.ping', () => {
    return { pong: true, timestamp: Date.now() };
  });

  // L3: system.identify — extended with caller context
  router.register('system.identify', (params) => {
    const p = params as { surfaceId?: string } | undefined;
    const state = store.getState();

    const base = {
      name: 'cmux-win',
      version: '0.1.0',
      platform: 'win32',
    };

    if (p?.surfaceId) {
      const surface = state.surfaces.find((s) => s.id === p.surfaceId);
      const panel = surface ? state.panels.find((pp) => pp.id === surface.panelId) : null;
      const workspace = panel ? state.workspaces.find((w) => w.id === panel.workspaceId) : null;
      return {
        ...base,
        caller: {
          surfaceId: p.surfaceId,
          panelId: panel?.id,
          paneIndex: panel?.paneIndex,
          workspaceId: workspace?.id,
          workspaceName: workspace?.name,
        },
      };
    }

    return base;
  });

  // L3: system.tree — full topology snapshot
  router.register('system.tree', () => {
    const state = store.getState();
    return {
      workspaces: state.workspaces.map((ws) => ({
        id: ws.id,
        name: ws.name,
        panelLayout: ws.panelLayout,
        panels: state.panels
          .filter((p) => p.workspaceId === ws.id)
          .map((p) => ({
            id: p.id,
            paneIndex: p.paneIndex,
            panelType: p.panelType,
            surfaces: state.surfaces
              .filter((s) => s.panelId === p.id)
              .map((s) => ({
                id: s.id,
                surfaceType: s.surfaceType,
                title: s.title,
                terminal: s.terminal,
              })),
          })),
        agents: state.agents
          .filter((a) => a.workspaceId === ws.id)
          .map((a) => ({
            sessionId: a.sessionId,
            agentType: a.agentType,
            surfaceId: a.surfaceId,
            status: a.status,
            statusIcon: a.statusIcon,
          })),
      })),
      focus: state.focus,
    };
  });

  router.register('system.capabilities', () => {
    return {
      methods: router.getMethods(),
    };
  });
}
