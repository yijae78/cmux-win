import React from 'react';
import { type FC, useState } from 'react';
import { useTranslation } from 'react-i18next';

/* -- Color constants ------------------------------------------------- */
const ACCENT = '#0091FF';
const DIVIDER = '#3c3c3c';
const TEXT_PRIMARY = '#e0e0e0';
const TEXT_SECONDARY = '#888888';

export interface SidebarFooterProps {
  onNewWorkspace: () => void;
  onNewAgent: (agentType: string) => void;
  hasActiveWorkspace: boolean;
}

const SidebarFooter: FC<SidebarFooterProps> = ({
  onNewWorkspace,
  onNewAgent,
  hasActiveWorkspace,
}) => {
  const { t } = useTranslation();
  const [wsHovered, setWsHovered] = useState(false);

  return (
    <div
      style={{
        borderTop: `1px solid ${DIVIDER}`,
        padding: '8px',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        flexShrink: 0,
      }}
    >
      {/* + Workspace button */}
      <button
        onClick={onNewWorkspace}
        onMouseEnter={() => setWsHovered(true)}
        onMouseLeave={() => setWsHovered(false)}
        style={{
          width: '100%',
          padding: '6px 8px',
          background: wsHovered ? 'rgba(0, 145, 255, 0.1)' : 'transparent',
          border: 'none',
          borderRadius: '6px',
          color: wsHovered ? ACCENT : TEXT_PRIMARY,
          fontSize: '12px',
          fontWeight: 500,
          cursor: 'pointer',
          textAlign: 'center',
          transition: 'background-color 0.15s ease, color 0.15s ease',
          lineHeight: '18px',
        }}
      >
        + {t('sidebar.newWorkspace')}
      </button>

      {/* Agent type selector dropdown */}
      <select
        onChange={(e) => {
          if (e.target.value && onNewAgent) {
            onNewAgent(e.target.value);
          }
          e.target.selectedIndex = 0; // reset to placeholder
        }}
        disabled={!hasActiveWorkspace}
        style={{
          width: '100%',
          padding: '6px 8px',
          background: 'transparent',
          border: 'none',
          borderRadius: '6px',
          color: hasActiveWorkspace ? TEXT_SECONDARY : TEXT_SECONDARY,
          fontSize: '11px',
          fontWeight: 400,
          cursor: hasActiveWorkspace ? 'pointer' : 'default',
          textAlign: 'center',
          lineHeight: '16px',
          opacity: hasActiveWorkspace ? 1 : 0.5,
          appearance: 'none',
          WebkitAppearance: 'none',
          MozAppearance: 'none' as never,
          backgroundImage: hasActiveWorkspace
            ? `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5' viewBox='0 0 8 5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23888888'/%3E%3C/svg%3E")`
            : 'none',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 8px center',
          paddingRight: '20px',
        }}
      >
        <option value="">+ {t('sidebar.addAgent')}</option>
        <option value="claude">Claude</option>
        <option value="codex">Codex</option>
        <option value="gemini">Gemini</option>
        <option value="opencode">OpenCode</option>
      </select>
    </div>
  );
};

export default SidebarFooter;
