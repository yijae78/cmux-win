import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { HistoryDb } from '../../../src/main/browser/history-db';

describe('HistoryDb', () => {
  let db: HistoryDb;

  beforeEach(() => {
    db = new HistoryDb(':memory:');
  });

  afterEach(() => {
    db.close();
  });

  it('add and query', () => {
    db.add('default', 'https://example.com', 'Example');
    const results = db.query('default', 'https://example');
    expect(results).toHaveLength(1);
    expect(results[0].url).toBe('https://example.com');
    expect(results[0].title).toBe('Example');
    expect(results[0].visits).toBe(1);
  });

  it('query filters by profileId', () => {
    db.add('profile-a', 'https://a.com', 'A');
    db.add('profile-b', 'https://b.com', 'B');
    expect(db.query('profile-a', 'https://')).toHaveLength(1);
    expect(db.query('profile-b', 'https://')).toHaveLength(1);
  });

  it('query filters by prefix', () => {
    db.add('default', 'https://example.com', 'Ex');
    db.add('default', 'https://other.com', 'Other');
    expect(db.query('default', 'https://example')).toHaveLength(1);
    expect(db.query('default', 'https://other')).toHaveLength(1);
    expect(db.query('default', 'https://')).toHaveLength(2);
  });

  it('query orders by visits DESC', () => {
    db.add('default', 'https://rare.com');
    db.add('default', 'https://popular.com');
    db.add('default', 'https://popular.com');
    db.add('default', 'https://popular.com');
    const results = db.query('default', 'https://');
    expect(results[0].url).toBe('https://popular.com');
    expect(results[0].visits).toBe(3);
  });

  it('clear removes all for profile', () => {
    db.add('profile-a', 'https://a.com');
    db.add('profile-b', 'https://b.com');
    db.clear('profile-a');
    expect(db.query('profile-a', '')).toHaveLength(0);
    expect(db.query('profile-b', '')).toHaveLength(1);
  });

  it('clear without profile removes everything', () => {
    db.add('profile-a', 'https://a.com');
    db.add('profile-b', 'https://b.com');
    db.clear();
    expect(db.query('profile-a', '')).toHaveLength(0);
    expect(db.query('profile-b', '')).toHaveLength(0);
  });
});
