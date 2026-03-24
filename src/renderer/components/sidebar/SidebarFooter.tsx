import React from 'react';
import { type FC, useState } from 'react';
import { useTranslation } from 'react-i18next';

/* -- Color constants ------------------------------------------------- */
const ACCENT = '#0091FF';
const TEXT_PRIMARY = '#e0e0e0';

export interface SidebarFooterProps {
  onNewWorkspace: () => void;
}

const SidebarFooter: FC<SidebarFooterProps> = ({ onNewWorkspace }) => {
  const { t } = useTranslation();
  const [wsHovered, setWsHovered] = useState(false);

  return (
    <div
      style={{
        padding: '4px 8px',
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
          padding: '5px 8px',
          background: wsHovered ? 'rgba(0, 145, 255, 0.1)' : 'transparent',
          border: 'none',
          borderRadius: '6px',
          color: wsHovered ? ACCENT : TEXT_PRIMARY,
          fontSize: '11px',
          fontWeight: 500,
          cursor: 'pointer',
          textAlign: 'center',
          transition: 'background-color 0.15s ease, color 0.15s ease',
          lineHeight: '18px',
        }}
      >
        + {t('sidebar.newWorkspace')}
      </button>
    </div>
  );
};

export default SidebarFooter;
