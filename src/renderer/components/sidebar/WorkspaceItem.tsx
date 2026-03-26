import React from 'react';
import { type FC, useState } from 'react';
import type {
  WorkspaceState,
  AgentSessionState,
  NotificationState,
  SurfaceState,
  PanelState,
} from '../../../shared/types';

/* ── Color constants ─────────────────────────────────────────────────── */
const ACCENT = '#0091FF';
const TEXT_PRIMARY = '#e0e0e0';
const TEXT_SECONDARY = '#888888';
const TEXT_MUTED = '#555555';
const STATUS_PILL_COLOR = '#7aa2f7';
const STATUS_PILL_BG = 'rgba(122, 162, 247, 0.1)';

/* ── Agent status config ─────────────────────────────────────────────── */
const STATUS_LABELS: Record<string, string> = {
  running: 'Running',
  idle: 'Idle',
  needs_input: 'Needs input',
};

const STATUS_ICONS: Record<string, string> = {
  running: '\u26A1',
  idle: '\u23F8',
  needs_input: '\uD83D\uDD14',
};

const STATUS_COLORS: Record<string, string> = {
  running: '#4C8DFF',
  idle: '#8E8E93',
  needs_input: '#FF9F0A',
};

/** Maximum number of status entry pills shown before collapsing. */
const MAX_VISIBLE_STATUS_ENTRIES = 3;

export interface WorkspaceItemProps {
  workspace: WorkspaceState;
  index: number;
  isActive: boolean;
  agents: AgentSessionState[];
  notifications: NotificationState[];
  surfaces?: SurfaceState[];
  panels?: PanelState[];
  onSelect: (workspaceId: string) => void;
  onClose: (workspaceId: string) => void;
  onRename: (workspaceId: string) => void;
}

const WorkspaceItem: FC<WorkspaceItemProps> = ({
  workspace,
  index,
  isActive,
  agents,
  notifications,
  surfaces,
  panels,
  onSelect,
  onClose,
  onRename,
}) => {
  const [hovered, setHovered] = useState(false);

  const wsAgents = agents.filter((a) => a.workspaceId === workspace.id);
  const wsNotifications = notifications.filter((n) => n.workspaceId === workspace.id && !n.isRead);

  // Find terminal surfaces belonging to this workspace's panels
  const wsPanelIds = new Set(
    (panels || []).filter((p) => p.workspaceId === workspace.id).map((p) => p.id),
  );
  const wsSurface = surfaces?.find(
    (s) =>
      s.surfaceType === 'terminal' &&
      s.terminal?.cwd &&
      (wsPanelIds.size === 0 || wsPanelIds.has(s.panelId)),
  );
  const cwd = wsSurface?.terminal?.cwd;
  const shortCwd = cwd ? cwd.split(/[/\\]/).filter(Boolean).pop() || cwd : null;
  const gitBranch = wsSurface?.terminal?.gitBranch;
  const gitDirty = wsSurface?.terminal?.gitDirty;

  // Status entries (ports, custom metadata)
  const statusEntries = workspace.statusEntries;
  const visibleEntries = statusEntries.slice(0, MAX_VISIBLE_STATUS_ENTRIES);
  const overflowCount = statusEntries.length - MAX_VISIBLE_STATUS_ENTRIES;

  // Latest unread notification body
  const latestUnreadBody =
    wsNotifications.length > 0
      ? (wsNotifications.reduce((latest, n) => (n.createdAt > latest.createdAt ? n : latest))
          .body ??
        wsNotifications.reduce((latest, n) => (n.createdAt > latest.createdAt ? n : latest))
          .subtitle)
      : null;

  // Keyboard shortcut hint (Ctrl+1 through Ctrl+9)
  const shortcutHint = index < 9 ? `Ctrl+${index + 1}` : null;

  /* ── Computed styles ───────────────────────────────────────────────── */
  const bgColor = isActive ? ACCENT : hovered ? 'rgba(0, 145, 255, 0.1)' : 'transparent';

  return (
    <div
      role="option"
      aria-selected={isActive}
      aria-label={workspace.name}
      onClick={() => onSelect(workspace.id)}
      onContextMenu={(e) => {
        e.preventDefault();
        const action = window.confirm(`Rename "${workspace.name}"? (Cancel to close)`)
          ? 'rename'
          : 'close';
        if (action === 'rename') onRename(workspace.id);
        else onClose(workspace.id);
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        padding: '8px 12px',
        cursor: 'pointer',
        gap: '8px',
        borderRadius: '6px',
        marginLeft: '4px',
        marginRight: '4px',
        background: bgColor,
        transition: 'background-color 0.15s ease',
        position: 'relative',
      }}
    >
      {/* Drag handle (subtle grip dots) */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '2px',
          flexShrink: 0,
          opacity: hovered || isActive ? 0.5 : 0.2,
          transition: 'opacity 0.15s ease',
          cursor: 'grab',
          marginTop: '2px',
        }}
        title="Drag to reorder"
      >
        <div style={{ display: 'flex', gap: '2px' }}>
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
        </div>
        <div style={{ display: 'flex', gap: '2px' }}>
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
        </div>
        <div style={{ display: 'flex', gap: '2px' }}>
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
          <span
            style={{
              width: '3px',
              height: '3px',
              borderRadius: '50%',
              background: isActive ? '#fff' : TEXT_MUTED,
            }}
          />
        </div>
      </div>

      {/* Workspace name + meta info */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {/* ── Row 1: Title row with name ─────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span
            style={{
              fontSize: '13px',
              fontWeight: 700,
              color: isActive ? '#ffffff' : TEXT_PRIMARY,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: '16px',
              flex: 1,
              minWidth: 0,
            }}
          >
            {workspace.name}
          </span>

          {/* Keyboard shortcut hint (visible on hover) */}
          {shortcutHint && (
            <span
              style={{
                fontSize: '9px',
                color: isActive ? 'rgba(255,255,255,0.85)' : '#888',
                border: isActive ? '0.8px solid rgba(255,255,255,0.4)' : '0.8px solid rgba(255,255,255,0.2)',
                background: isActive ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)',
                borderRadius: '999px',
                padding: '1px 5px',
                whiteSpace: 'nowrap',
                flexShrink: 0,
                lineHeight: '13px',
                opacity: hovered ? 1 : 0,
                transition: 'opacity 0.15s ease',
                pointerEvents: 'none',
              }}
            >
              {shortcutHint}
            </span>
          )}

          {/* Close button (visible on hover) */}
          <button
            aria-label={`Close workspace ${workspace.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onClose(workspace.id);
            }}
            style={{
              width: '16px',
              height: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: 'none',
              background: 'transparent',
              color: isActive ? 'rgba(255,255,255,0.85)' : '#888',
              fontSize: '12px',
              lineHeight: '16px',
              cursor: 'pointer',
              padding: 0,
              flexShrink: 0,
              borderRadius: '3px',
              opacity: hovered ? 1 : 0,
              transition: 'opacity 0.15s ease, color 0.15s ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = '#fff';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = isActive ? 'rgba(255,255,255,0.85)' : '#888';
            }}
          >
            {'\u2715'}
          </button>
        </div>

        {/* ── Row 2: Git branch + CWD ────────────────────────────────── */}
        {gitBranch && (
          <span
            style={{
              fontSize: '11px',
              color: isActive ? 'rgba(255,255,255,0.7)' : TEXT_SECONDARY,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: '14px',
            }}
          >
            {'\u2387'} {gitBranch}
            {gitDirty ? ' \u25CF' : ''}
          </span>
        )}

        {shortCwd && (
          <span
            style={{
              fontSize: '10px',
              color: isActive ? 'rgba(255,255,255,0.5)' : TEXT_MUTED,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: '13px',
            }}
          >
            {shortCwd}
          </span>
        )}

        {/* ── Row 3: Status entries (pills) ──────────────────────────── */}
        {statusEntries.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '3px',
              marginTop: '1px',
            }}
          >
            {visibleEntries.map((entry) => (
              <span
                key={entry.key}
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  color: isActive ? 'rgba(255,255,255,0.85)' : entry.color || STATUS_PILL_COLOR,
                  background: isActive ? 'rgba(255,255,255,0.15)' : STATUS_PILL_BG,
                  borderRadius: '3px',
                  padding: '1px 6px',
                  lineHeight: '14px',
                  whiteSpace: 'nowrap',
                }}
                title={`${entry.key}: ${entry.label}`}
              >
                {entry.icon ? `${entry.icon} ` : ''}
                {entry.label}
              </span>
            ))}
            {overflowCount > 0 && (
              <span
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  color: isActive ? 'rgba(255,255,255,0.6)' : TEXT_MUTED,
                  lineHeight: '14px',
                  whiteSpace: 'nowrap',
                }}
              >
                +{overflowCount} more
              </span>
            )}
          </div>
        )}

        {/* ── Row 4: Notification preview ────────────────────────────── */}
        {latestUnreadBody && (
          <span
            style={{
              fontSize: '10px',
              color: isActive ? 'rgba(255,255,255,0.5)' : '#666',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              lineHeight: '13px',
            }}
          >
            {latestUnreadBody}
          </span>
        )}

        {/* ── Row 5: Agent status icons ──────────────────────────────── */}
        {wsAgents.length > 0 && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '1px' }}>
            {wsAgents.map((agent) => {
              const color = isActive
                ? '#ffffff'
                : STATUS_COLORS[agent.status] || agent.statusColor || '#8E8E93';
              return (
                <span
                  key={agent.sessionId}
                  style={{
                    fontSize: '10px',
                    color,
                    lineHeight: '13px',
                    whiteSpace: 'nowrap',
                  }}
                  title={`${agent.agentType}: ${agent.status}`}
                >
                  {STATUS_ICONS[agent.status] || agent.statusIcon}{' '}
                  {STATUS_LABELS[agent.status] || agent.status}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Unread notification badge (blue dot) */}
      {wsNotifications.length > 0 && (
        <div
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: isActive ? 'rgba(255,255,255,0.8)' : ACCENT,
            flexShrink: 0,
            marginTop: '5px',
          }}
          title={`${wsNotifications.length} unread`}
        />
      )}
    </div>
  );
};

export default WorkspaceItem;
