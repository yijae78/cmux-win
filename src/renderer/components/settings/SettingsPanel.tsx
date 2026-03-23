import React from 'react';
import { useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import type { SettingsState } from '../../../shared/types';
import { DEFAULT_SHORTCUTS } from '../../../shared/shortcuts';

export interface SettingsPanelProps {
  settings: SettingsState;
  onUpdate: (partial: Record<string, unknown>) => void;
  onClose: () => void;
}

const SECTION_KEYS = [
  'appearance',
  'terminal',
  'browser',
  'agents',
  'shortcuts',
  'updates',
  'accessibility',
] as const;

const BUNDLED_THEMES = [
  'Dracula',
  'Monokai',
  'One Dark',
  'Solarized Dark',
  'Solarized Light',
  'Nord',
  'Gruvbox Dark',
  'Tokyo Night',
];

const SettingsPanel: FC<SettingsPanelProps> = ({ settings, onUpdate, onClose }) => {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState<string>('appearance');

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('settings.title', 'Settings')}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '700px',
          height: '500px',
          background: '#272822',
          border: '1px solid #3c3c3c',
          borderRadius: '8px',
          display: 'flex',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
        }}
      >
        {/* Sidebar */}
        <nav
          aria-label="Settings sections"
          style={{
            width: '180px',
            borderRight: '1px solid #3c3c3c',
            padding: '12px 0',
            flexShrink: 0,
          }}
        >
          {SECTION_KEYS.map((s) => (
            <div
              key={s}
              role="button"
              tabIndex={0}
              aria-current={s === activeSection ? 'true' : undefined}
              onClick={() => setActiveSection(s)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setActiveSection(s);
              }}
              style={{
                padding: '6px 16px',
                cursor: 'pointer',
                fontSize: '13px',
                background: s === activeSection ? '#37373d' : 'transparent',
                color: s === activeSection ? '#fff' : '#e0e0e0',
              }}
            >
              {t(`settings.${s}`)}
            </div>
          ))}
        </nav>
        {/* Content */}
        <div style={{ flex: 1, padding: '16px', overflowY: 'auto', color: '#e0e0e0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h2 style={{ margin: 0, fontSize: '18px', color: '#fff' }}>
              {t(`settings.${activeSection}`)}
            </h2>
            <button
              onClick={onClose}
              aria-label="Close settings"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#888',
                cursor: 'pointer',
                fontSize: '18px',
              }}
            >
              &#x2715;
            </button>
          </div>

          {/* ── 1. Appearance ──────────────────────────────────────────── */}
          {activeSection === 'appearance' && (
            <div>
              <SettingRow label={t('settings.theme')}>
                <select
                  value={settings.appearance.theme}
                  onChange={(e) =>
                    onUpdate({ appearance: { ...settings.appearance, theme: e.target.value } })
                  }
                  style={selectStyle}
                >
                  <option value="system">System</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.terminalTheme', 'Terminal Theme')}>
                <select
                  value={settings.terminal.themeName}
                  onChange={(e) =>
                    onUpdate({ terminal: { ...settings.terminal, themeName: e.target.value } })
                  }
                  style={selectStyle}
                >
                  {BUNDLED_THEMES.map((th) => (
                    <option key={th} value={th}>
                      {th}
                    </option>
                  ))}
                </select>
              </SettingRow>
              <SettingRow label={t('settings.fontSize')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="range"
                    min={8}
                    max={32}
                    value={settings.terminal.fontSize}
                    onChange={(e) =>
                      onUpdate({
                        terminal: { ...settings.terminal, fontSize: parseInt(e.target.value) || 14 },
                      })
                    }
                    style={{ width: '100px', accentColor: '#569cd6' }}
                  />
                  <span style={{ fontSize: '12px', color: '#888', minWidth: '28px' }}>
                    {settings.terminal.fontSize}px
                  </span>
                </div>
              </SettingRow>
              <SettingRow label={t('settings.language')}>
                <select
                  value={settings.appearance.language}
                  onChange={(e) =>
                    onUpdate({ appearance: { ...settings.appearance, language: e.target.value } })
                  }
                  style={selectStyle}
                >
                  <option value="system">System</option>
                  <option value="en">English</option>
                  <option value="ko">{'\uD55C\uAD6D\uC5B4'}</option>
                  <option value="ja">{'\u65E5\u672C\u8A9E'}</option>
                </select>
              </SettingRow>
            </div>
          )}

          {/* ── 2. Terminal ────────────────────────────────────────────── */}
          {activeSection === 'terminal' && (
            <div>
              <SettingRow label={t('settings.defaultShell')}>
                <select
                  value={settings.terminal.defaultShell}
                  onChange={(e) =>
                    onUpdate({ terminal: { ...settings.terminal, defaultShell: e.target.value } })
                  }
                  style={selectStyle}
                >
                  <option value="powershell">PowerShell</option>
                  <option value="cmd">CMD</option>
                  <option value="wsl">WSL</option>
                  <option value="git-bash">Git Bash</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.cursorStyle', 'Cursor Style')}>
                <select
                  value={settings.terminal.cursorStyle}
                  onChange={(e) =>
                    onUpdate({
                      terminal: {
                        ...settings.terminal,
                        cursorStyle: e.target.value as 'block' | 'underline' | 'bar',
                      },
                    })
                  }
                  style={selectStyle}
                >
                  <option value="block">Block</option>
                  <option value="underline">Underline</option>
                  <option value="bar">Bar</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.fontSize')}>
                <input
                  type="number"
                  value={settings.terminal.fontSize}
                  min={8}
                  max={32}
                  onChange={(e) =>
                    onUpdate({
                      terminal: { ...settings.terminal, fontSize: parseInt(e.target.value) || 14 },
                    })
                  }
                  style={inputStyle}
                />
              </SettingRow>
              <SettingRow label={t('settings.fontFamily')}>
                <input
                  type="text"
                  value={settings.terminal.fontFamily}
                  onChange={(e) =>
                    onUpdate({ terminal: { ...settings.terminal, fontFamily: e.target.value } })
                  }
                  style={inputStyle}
                />
              </SettingRow>
            </div>
          )}

          {/* ── 3. Browser ─────────────────────────────────────────────── */}
          {activeSection === 'browser' && (
            <div>
              <SettingRow label={t('settings.searchEngine')}>
                <select
                  value={settings.browser.searchEngine}
                  onChange={(e) =>
                    onUpdate({ browser: { ...settings.browser, searchEngine: e.target.value } })
                  }
                  style={selectStyle}
                >
                  <option value="google">Google</option>
                  <option value="duckduckgo">DuckDuckGo</option>
                  <option value="bing">Bing</option>
                  <option value="kagi">Kagi</option>
                  <option value="startpage">Startpage</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.homepage', 'Homepage URL')}>
                <input
                  type="text"
                  value={
                    (settings.browser as Record<string, unknown>).homepage as string ??
                    'about:blank'
                  }
                  onChange={(e) =>
                    onUpdate({ browser: { ...settings.browser, homepage: e.target.value } })
                  }
                  placeholder="https://..."
                  style={{ ...inputStyle, width: '200px' }}
                />
              </SettingRow>
              <SettingRow label={t('settings.searchSuggestions', 'Search Suggestions')}>
                <ToggleSwitch
                  checked={settings.browser.searchSuggestions}
                  onChange={(v) =>
                    onUpdate({ browser: { ...settings.browser, searchSuggestions: v } })
                  }
                />
              </SettingRow>
            </div>
          )}

          {/* ── 4. Agents ──────────────────────────────────────────────── */}
          {activeSection === 'agents' && (
            <div>
              <SettingRow label={t('settings.orchestrationMode', 'Orchestration Mode')}>
                <select
                  value={settings.agents.orchestrationMode}
                  onChange={(e) =>
                    onUpdate({
                      agents: {
                        ...settings.agents,
                        orchestrationMode: e.target.value as
                          | 'auto'
                          | 'claude-teams'
                          | 'self-managed',
                      },
                    })
                  }
                  style={selectStyle}
                >
                  <option value="auto">Auto</option>
                  <option value="claude-teams">Claude Teams</option>
                  <option value="self-managed">Self-Managed</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.claudeHooks')}>
                <ToggleSwitch
                  checked={settings.agents.claudeHooksEnabled}
                  onChange={(v) =>
                    onUpdate({ agents: { ...settings.agents, claudeHooksEnabled: v } })
                  }
                />
              </SettingRow>
              <SettingRow label={t('settings.codexHooks', 'Codex Hooks')}>
                <ToggleSwitch
                  checked={settings.agents.codexHooksEnabled}
                  onChange={(v) =>
                    onUpdate({ agents: { ...settings.agents, codexHooksEnabled: v } })
                  }
                />
              </SettingRow>
              <SettingRow label={t('settings.geminiHooks', 'Gemini Hooks')}>
                <ToggleSwitch
                  checked={settings.agents.geminiHooksEnabled}
                  onChange={(v) =>
                    onUpdate({ agents: { ...settings.agents, geminiHooksEnabled: v } })
                  }
                />
              </SettingRow>
            </div>
          )}

          {/* ── 5. Shortcuts (read-only) ───────────────────────────────── */}
          {activeSection === 'shortcuts' && (
            <div>
              {(['workspace', 'panel', 'surface', 'navigation', 'view'] as const).map(
                (category) => {
                  const items = DEFAULT_SHORTCUTS.filter((s) => s.category === category);
                  if (items.length === 0) return null;
                  return (
                    <div key={category} style={{ marginBottom: '12px' }}>
                      <div
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          color: '#888',
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          marginBottom: '4px',
                          paddingBottom: '4px',
                          borderBottom: '1px solid #3c3c3c',
                        }}
                      >
                        {category}
                      </div>
                      {items.map((sc) => (
                        <div
                          key={sc.id}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '4px 0',
                            fontSize: '13px',
                          }}
                        >
                          <span style={{ color: '#e0e0e0' }}>{sc.label}</span>
                          <kbd
                            style={{
                              background: '#3c3c3c',
                              border: '1px solid #555',
                              borderRadius: '3px',
                              padding: '2px 6px',
                              fontSize: '11px',
                              color: '#ccc',
                              fontFamily: 'monospace',
                            }}
                          >
                            {sc.defaultKey}
                          </kbd>
                        </div>
                      ))}
                    </div>
                  );
                },
              )}
            </div>
          )}

          {/* ── 6. Updates ─────────────────────────────────────────────── */}
          {activeSection === 'updates' && (
            <div>
              <SettingRow label={t('settings.autoCheck', 'Auto-Update')}>
                <ToggleSwitch
                  checked={settings.updates.autoCheck}
                  onChange={(v) =>
                    onUpdate({ updates: { ...settings.updates, autoCheck: v } })
                  }
                />
              </SettingRow>
              <SettingRow label={t('settings.channel')}>
                <select
                  value={settings.updates.channel}
                  onChange={(e) =>
                    onUpdate({ updates: { ...settings.updates, channel: e.target.value } })
                  }
                  style={selectStyle}
                >
                  <option value="stable">Stable</option>
                  <option value="nightly">Nightly</option>
                </select>
              </SettingRow>
              <SettingRow label={t('settings.currentVersion', 'Current Version')}>
                <span style={{ fontSize: '12px', color: '#888' }}>v0.1.0</span>
              </SettingRow>
            </div>
          )}

          {/* ── 7. Accessibility ───────────────────────────────────────── */}
          {activeSection === 'accessibility' && (
            <div>
              <SettingRow label={t('settings.screenReader')}>
                <ToggleSwitch
                  checked={settings.accessibility.screenReaderMode}
                  onChange={(v) =>
                    onUpdate({
                      accessibility: {
                        ...settings.accessibility,
                        screenReaderMode: v,
                      },
                    })
                  }
                />
              </SettingRow>
              <SettingRow label={t('settings.reducedMotion')}>
                <ToggleSwitch
                  checked={settings.accessibility.reducedMotion}
                  onChange={(v) =>
                    onUpdate({
                      accessibility: { ...settings.accessibility, reducedMotion: v },
                    })
                  }
                />
              </SettingRow>
              <SettingRow label={t('settings.highContrast', 'High Contrast')}>
                <ToggleSwitch
                  checked={
                    (settings.accessibility as Record<string, unknown>).highContrast as boolean ??
                    false
                  }
                  onChange={(v) =>
                    onUpdate({
                      accessibility: { ...settings.accessibility, highContrast: v },
                    })
                  }
                />
              </SettingRow>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ── ToggleSwitch component ───────────────────────────────────────────── */
const ToggleSwitch: FC<{ checked: boolean; onChange: (v: boolean) => void }> = ({
  checked,
  onChange,
}) => (
  <button
    role="switch"
    aria-checked={checked}
    onClick={() => onChange(!checked)}
    style={{
      width: '36px',
      height: '20px',
      borderRadius: '10px',
      border: '1px solid #555',
      background: checked ? '#569cd6' : '#3c3c3c',
      cursor: 'pointer',
      position: 'relative',
      padding: 0,
      transition: 'background 0.15s',
    }}
  >
    <span
      style={{
        position: 'absolute',
        top: '2px',
        left: checked ? '17px' : '2px',
        width: '14px',
        height: '14px',
        borderRadius: '50%',
        background: '#fff',
        transition: 'left 0.15s',
      }}
    />
  </button>
);

/* ── SettingRow helper ────────────────────────────────────────────────── */
const SettingRow: FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 0',
      borderBottom: '1px solid #3c3c3c',
    }}
  >
    <span style={{ fontSize: '13px', color: '#e0e0e0' }}>{label}</span>
    {children}
  </div>
);

/* ── Shared styles ────────────────────────────────────────────────────── */
const selectStyle: React.CSSProperties = {
  background: '#3c3c3c',
  color: '#e0e0e0',
  border: '1px solid #555',
  borderRadius: '3px',
  padding: '4px 8px',
  fontSize: '12px',
};

const inputStyle: React.CSSProperties = {
  ...selectStyle,
  width: '120px',
};

export default SettingsPanel;
