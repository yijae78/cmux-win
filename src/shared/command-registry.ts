import type { ShortcutDef } from './shortcuts';

export interface Command {
  id: string;
  label: string;
  category: string;
  shortcut?: string;
}

export function buildCommandList(shortcuts: ShortcutDef[]): Command[] {
  return shortcuts.map((s) => ({
    id: s.id,
    label: s.label,
    category: s.category,
    shortcut: s.defaultKey,
  }));
}
