import { describe, it, expect } from 'vitest';
import { ActionSchema } from '../../../src/shared/actions';

describe('Action Schema', () => {
  it('validates window.create', () => {
    expect(
      ActionSchema.safeParse({
        type: 'window.create',
        payload: { geometry: { x: 100, y: 100, width: 1200, height: 800 } },
      }).success,
    ).toBe(true);
  });

  it('validates window.close', () => {
    expect(
      ActionSchema.safeParse({
        type: 'window.close',
        payload: { windowId: 'win-1' },
      }).success,
    ).toBe(true);
  });

  it('validates workspace.create', () => {
    expect(
      ActionSchema.safeParse({
        type: 'workspace.create',
        payload: { windowId: 'win-1', name: 'Test' },
      }).success,
    ).toBe(true);
  });

  it('validates panel.split', () => {
    expect(
      ActionSchema.safeParse({
        type: 'panel.split',
        payload: { panelId: 'p-1', direction: 'horizontal', newPanelType: 'terminal' },
      }).success,
    ).toBe(true);
  });

  it('rejects unknown type', () => {
    expect(ActionSchema.safeParse({ type: 'unknown', payload: {} }).success).toBe(false);
  });

  it('rejects invalid direction', () => {
    expect(
      ActionSchema.safeParse({
        type: 'panel.split',
        payload: { panelId: 'p-1', direction: 'diagonal', newPanelType: 'terminal' },
      }).success,
    ).toBe(false);
  });

  it('validates agent.session_start', () => {
    expect(
      ActionSchema.safeParse({
        type: 'agent.session_start',
        payload: {
          sessionId: 's1',
          agentType: 'claude',
          workspaceId: 'ws-1',
          surfaceId: 'sf-1',
        },
      }).success,
    ).toBe(true);
  });

  it('validates notification.create', () => {
    expect(
      ActionSchema.safeParse({
        type: 'notification.create',
        payload: { title: 'Hello' },
      }).success,
    ).toBe(true);
  });
});
