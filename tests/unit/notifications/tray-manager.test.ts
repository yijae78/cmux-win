import { describe, it, expect } from 'vitest';
import { computeUnreadCount, formatTrayTitle } from '../../../src/main/notifications/tray-manager';

describe('computeUnreadCount', () => {
  it('counts unread notifications', () => {
    expect(computeUnreadCount([{ isRead: false }, { isRead: true }, { isRead: false }])).toBe(2);
  });

  it('returns 0 when all read', () => {
    expect(computeUnreadCount([{ isRead: true }])).toBe(0);
  });

  it('returns 0 for empty array', () => {
    expect(computeUnreadCount([])).toBe(0);
  });
});

describe('formatTrayTitle', () => {
  it('shows count when > 0', () => {
    expect(formatTrayTitle(3)).toBe('(3) cmux-win');
  });

  it('returns app name when 0', () => {
    expect(formatTrayTitle(0)).toBe('cmux-win');
  });
});
