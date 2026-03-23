import { useCallback, useRef, useEffect } from 'react';

// ── Public types ──────────────────────────────────────────────────

export type FocusDirection = 'left' | 'right' | 'up' | 'down';

export interface PanelFocusState {
  focusedPanelId: string | null;
  setFocusedPanel: (panelId: string) => void;
  moveFocus: (direction: FocusDirection) => void;
}

// ── Pure helpers (exported for testing) ───────────────────────────

/**
 * Clamp `index` to [0, length-1].  Returns 0 when length is 0.
 */
export function clampIndex(index: number, length: number): number {
  if (length <= 0) return 0;
  if (index < 0) return 0;
  if (index >= length) return length - 1;
  return index;
}

/**
 * Given an ordered list of panel IDs, the currently focused panel,
 * and a direction, return the next panel ID to focus.
 *
 * Navigation model (flat list):
 *   left / up   → previous index (wraps to end)
 *   right / down → next index    (wraps to start)
 *
 * Edge cases:
 *   - empty list        → null
 *   - unknown currentId → first panel
 *   - single panel      → same panel
 */
export function resolveNextPanel(
  panelIds: readonly string[],
  currentId: string | null,
  direction: FocusDirection,
): string | null {
  if (panelIds.length === 0) return null;

  const idx = currentId !== null ? panelIds.indexOf(currentId) : -1;

  // If the current panel is not found, fall back to the first panel.
  if (idx === -1) return panelIds[0];

  const delta = direction === 'left' || direction === 'up' ? -1 : 1;
  const next = (idx + delta + panelIds.length) % panelIds.length;
  return panelIds[next];
}

// ── React hook ────────────────────────────────────────────────────

/**
 * Manages panel focus state and keyboard navigation.
 * Used with Ctrl+Alt+Arrow shortcuts for panel switching.
 *
 * @param panelIds      Ordered list of panel IDs in the current workspace.
 * @param onFocusChange Optional callback fired when the focused panel changes.
 */
export function usePanelFocus(
  panelIds: string[],
  onFocusChange?: (panelId: string) => void,
): PanelFocusState {
  const focusedRef = useRef<string | null>(panelIds[0] ?? null);

  // Keep focusedRef in sync when the panel list changes
  // (e.g. a panel is closed and the focused one disappears).
  useEffect(() => {
    if (focusedRef.current !== null && panelIds.includes(focusedRef.current)) {
      return; // still valid
    }
    focusedRef.current = panelIds[0] ?? null;
  }, [panelIds]);

  const setFocusedPanel = useCallback(
    (panelId: string) => {
      if (focusedRef.current === panelId) return;
      focusedRef.current = panelId;
      onFocusChange?.(panelId);
    },
    [onFocusChange],
  );

  const moveFocus = useCallback(
    (direction: FocusDirection) => {
      const next = resolveNextPanel(panelIds, focusedRef.current, direction);
      if (next !== null && next !== focusedRef.current) {
        focusedRef.current = next;
        onFocusChange?.(next);
      }
    },
    [panelIds, onFocusChange],
  );

  return {
    focusedPanelId: focusedRef.current,
    setFocusedPanel,
    moveFocus,
  };
}
