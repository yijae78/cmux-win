import { createContext, useContext } from 'react';
import type { SurfaceState, SettingsState } from '../../../shared/types';
import type { Action } from '../../../shared/actions';

/**
 * L1: PanelContext — reduces prop drilling for shared panel data.
 * Provides surfaces, settings, dispatch, workspaceId, and common callbacks
 * so PanelContainer/PanelLayout don't need 14+ individual props.
 */
export interface PanelContextValue {
  surfaces: SurfaceState[];
  settings: SettingsState;
  workspaceId: string;
  dispatch: (action: Action) => Promise<{ ok: boolean }>;
  onPanelFocus: (panelId: string) => void;
  onSurfaceFocus: (surfaceId: string) => void;
  onSurfaceClose: (surfaceId: string) => void;
  onNewSurface: (panelId: string) => void;
  onOpenFolder?: (surfaceId: string) => void;
  onEqualizeH?: () => void;
  onEqualizeV?: () => void;
  onBrowserUrlChange?: (surfaceId: string, url: string) => void;
  onBrowserTitleChange?: (surfaceId: string, title: string) => void;
}

export const PanelContext = createContext<PanelContextValue | null>(null);

export function usePanelContext(): PanelContextValue {
  const ctx = useContext(PanelContext);
  if (!ctx) throw new Error('usePanelContext must be used within PanelContext.Provider');
  return ctx;
}
