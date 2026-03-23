export interface ShortcutDef {
  id: string;
  label: string;
  defaultKey: string;
  category: 'workspace' | 'panel' | 'surface' | 'view' | 'navigation';
}

// P2-BUG-9: Ctrl+T/W → Ctrl+Shift+T/W to avoid bash conflict
export const DEFAULT_SHORTCUTS: ShortcutDef[] = [
  // Workspace
  { id: 'newWorkspace', label: 'New Workspace', defaultKey: 'Ctrl+N', category: 'workspace' },
  {
    id: 'closeWorkspace',
    label: 'Close Workspace',
    defaultKey: 'Ctrl+Shift+W',
    category: 'workspace',
  },
  { id: 'nextWorkspace', label: 'Next Workspace', defaultKey: 'Ctrl+Tab', category: 'workspace' },
  {
    id: 'prevWorkspace',
    label: 'Prev Workspace',
    defaultKey: 'Ctrl+Shift+Tab',
    category: 'workspace',
  },
  {
    id: 'renameWorkspace',
    label: 'Rename Workspace',
    defaultKey: 'Ctrl+Shift+R',
    category: 'workspace',
  },

  // Panel
  { id: 'splitRight', label: 'Split Right', defaultKey: 'Ctrl+D', category: 'panel' },
  { id: 'splitDown', label: 'Split Down', defaultKey: 'Ctrl+Shift+D', category: 'panel' },
  { id: 'closePanel', label: 'Close Panel', defaultKey: 'Ctrl+Shift+X', category: 'panel' },
  { id: 'toggleZoom', label: 'Toggle Zoom', defaultKey: 'Ctrl+Shift+Enter', category: 'panel' },
  { id: 'focusLeft', label: 'Focus Left', defaultKey: 'Ctrl+Alt+Left', category: 'panel' },
  { id: 'focusRight', label: 'Focus Right', defaultKey: 'Ctrl+Alt+Right', category: 'panel' },
  { id: 'focusUp', label: 'Focus Up', defaultKey: 'Ctrl+Alt+Up', category: 'panel' },
  { id: 'focusDown', label: 'Focus Down', defaultKey: 'Ctrl+Alt+Down', category: 'panel' },

  // Surface
  { id: 'newSurface', label: 'New Tab', defaultKey: 'Ctrl+Shift+T', category: 'surface' },
  { id: 'closeSurface', label: 'Close Tab', defaultKey: 'Ctrl+Shift+Q', category: 'surface' },
  { id: 'nextSurface', label: 'Next Tab', defaultKey: 'Ctrl+Shift+]', category: 'surface' },
  { id: 'prevSurface', label: 'Prev Tab', defaultKey: 'Ctrl+Shift+[', category: 'surface' },

  // Navigation
  { id: 'find', label: 'Find', defaultKey: 'Ctrl+F', category: 'navigation' },

  // View
  { id: 'toggleSidebar', label: 'Toggle Sidebar', defaultKey: 'Ctrl+B', category: 'view' },
  { id: 'newWindow', label: 'New Window', defaultKey: 'Ctrl+Shift+N', category: 'view' },
  { id: 'closeWindow', label: 'Close Window', defaultKey: 'Ctrl+Alt+W', category: 'view' },
  { id: 'commandPalette', label: 'Command Palette', defaultKey: 'Ctrl+Shift+P', category: 'view' },
  { id: 'openSettings', label: 'Open Settings', defaultKey: 'Ctrl+,', category: 'view' },
];

export function parseKeyCombo(key: string): {
  ctrl: boolean;
  shift: boolean;
  alt: boolean;
  key: string;
} {
  const parts = key.split('+');
  return {
    ctrl: parts.includes('Ctrl'),
    shift: parts.includes('Shift'),
    alt: parts.includes('Alt'),
    key: parts[parts.length - 1],
  };
}

export function matchInput(
  input: { control: boolean; shift: boolean; alt: boolean; key: string },
  shortcuts: ShortcutDef[],
): string | null {
  for (const sc of shortcuts) {
    const combo = parseKeyCombo(sc.defaultKey);
    if (
      input.control === combo.ctrl &&
      input.shift === combo.shift &&
      input.alt === combo.alt &&
      input.key.toLowerCase() === combo.key.toLowerCase()
    ) {
      return sc.id;
    }
  }
  return null;
}
