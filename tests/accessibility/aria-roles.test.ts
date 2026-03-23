import { describe, it, expect } from 'vitest';

/**
 * Accessibility validation tests.
 * These verify that components declare proper ARIA roles.
 * Full axe-core integration requires a browser environment (E2E).
 */

describe('Accessibility requirements', () => {
  it('defines required ARIA roles for sidebar', async () => {
    // Verify Sidebar component exports with role="navigation"
    const sidebarSource = await import('fs').then((fs) =>
      fs.readFileSync('src/renderer/components/sidebar/Sidebar.tsx', 'utf8'),
    );
    expect(sidebarSource).toContain('role="navigation"');
    expect(sidebarSource).toContain('aria-label');
  });

  it('defines required ARIA roles for workspace items', async () => {
    const source = await import('fs').then((fs) =>
      fs.readFileSync('src/renderer/components/sidebar/WorkspaceItem.tsx', 'utf8'),
    );
    expect(source).toContain('role=');
    expect(source).toContain('aria-');
  });

  it('defines required ARIA roles for panel container', async () => {
    const source = await import('fs').then((fs) =>
      fs.readFileSync('src/renderer/components/panels/PanelContainer.tsx', 'utf8'),
    );
    expect(source).toContain('role=');
    expect(source).toContain('aria-label');
  });

  it('defines required ARIA roles for panel layout', async () => {
    const source = await import('fs').then((fs) =>
      fs.readFileSync('src/renderer/components/panels/PanelLayout.tsx', 'utf8'),
    );
    expect(source).toContain('role=');
    expect(source).toContain('aria-label');
  });

  it('XTermWrapper supports screenReaderMode option', async () => {
    const source = await import('fs').then((fs) =>
      fs.readFileSync('src/renderer/components/terminal/XTermWrapper.tsx', 'utf8'),
    );
    expect(source).toContain('screenReaderMode');
  });
});
