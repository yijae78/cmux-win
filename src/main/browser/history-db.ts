import Database from 'better-sqlite3';

export class HistoryDb {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT,
        visit_time INTEGER NOT NULL,
        favicon_url TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
      CREATE INDEX IF NOT EXISTS idx_history_profile ON history(profile_id);
      CREATE INDEX IF NOT EXISTS idx_history_visit ON history(visit_time DESC);
    `);
  }

  add(profileId: string, url: string, title?: string, faviconUrl?: string): void {
    this.db
      .prepare(
        'INSERT INTO history (profile_id, url, title, visit_time, favicon_url) VALUES (?, ?, ?, ?, ?)',
      )
      .run(profileId, url, title ?? null, Date.now(), faviconUrl ?? null);
  }

  query(
    profileId: string,
    prefix: string,
    limit = 10,
  ): Array<{
    url: string;
    title: string | null;
    lastVisit: number;
    visits: number;
  }> {
    return this.db
      .prepare(
        `
      SELECT url, title, MAX(visit_time) as lastVisit, COUNT(*) as visits
      FROM history WHERE profile_id = ? AND url LIKE ? || '%'
      GROUP BY url ORDER BY visits DESC, lastVisit DESC LIMIT ?
    `,
      )
      .all(profileId, prefix, limit) as Array<{
      url: string;
      title: string | null;
      lastVisit: number;
      visits: number;
    }>;
  }

  clear(profileId?: string): void {
    if (profileId) {
      this.db.prepare('DELETE FROM history WHERE profile_id = ?').run(profileId);
    } else {
      this.db.exec('DELETE FROM history');
    }
  }

  close(): void {
    this.db.close();
  }
}
