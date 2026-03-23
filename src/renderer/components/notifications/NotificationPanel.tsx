import React from 'react';
import { type FC } from 'react';

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  timestamp: number;
  read: boolean;
  type: 'info' | 'warning' | 'error' | 'agent';
}

interface NotificationPanelProps {
  notifications: NotificationItem[];
  visible: boolean;
  onClose: () => void;
  onMarkRead: (id: string) => void;
  onClearAll: () => void;
}

const NotificationPanel: FC<NotificationPanelProps> = ({
  notifications,
  visible,
  onClose,
  onMarkRead,
  onClearAll,
}) => {
  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        width: '320px',
        background: '#1e1e1e',
        borderLeft: '1px solid #3c3c3c',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 200,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid #3c3c3c',
        }}
      >
        <span style={{ color: '#ccc', fontWeight: 'bold', fontSize: '13px' }}>Notifications</span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={onClearAll} style={headerBtnStyle}>
            Clear All
          </button>
          <button onClick={onClose} style={headerBtnStyle}>
            &#x2715;
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {notifications.length === 0 ? (
          <div style={{ color: '#666', textAlign: 'center', padding: '32px 0', fontSize: '12px' }}>
            No notifications
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => onMarkRead(n.id)}
              style={{
                padding: '8px 12px',
                marginBottom: '4px',
                borderRadius: '4px',
                background: n.read ? 'transparent' : '#2a2d2e',
                cursor: 'pointer',
                borderLeft: `3px solid ${typeColor(n.type)}`,
              }}
            >
              <div
                style={{
                  color: '#ccc',
                  fontSize: '12px',
                  fontWeight: n.read ? 'normal' : 'bold',
                }}
              >
                {n.title}
              </div>
              <div style={{ color: '#888', fontSize: '11px', marginTop: '2px' }}>{n.body}</div>
              <div style={{ color: '#555', fontSize: '10px', marginTop: '4px' }}>
                {new Date(n.timestamp).toLocaleTimeString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

function typeColor(type: string): string {
  switch (type) {
    case 'error':
      return '#f44';
    case 'warning':
      return '#fa0';
    case 'agent':
      return '#4af';
    default:
      return '#4a4';
  }
}

const headerBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #555',
  color: '#888',
  padding: '2px 8px',
  borderRadius: '3px',
  cursor: 'pointer',
  fontSize: '11px',
};

export default NotificationPanel;
