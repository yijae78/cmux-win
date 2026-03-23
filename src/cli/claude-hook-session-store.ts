import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

export interface SessionRecord {
  sessionId: string;
  workspaceId: string;
  surfaceId: string;
  cwd?: string;
  pid?: number;
  lastSubtitle?: string;
  lastBody?: string;
  startedAt: number;
  updatedAt: number;
}

export interface SessionStoreData {
  sessions: Record<string, SessionRecord>;
}

const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export class ClaudeHookSessionStore {
  private filePath: string;

  constructor(filePath?: string) {
    this.filePath =
      filePath ??
      path.join(
        process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
        'cmux-win',
        'claude-hook-sessions.json',
      );
  }

  load(): SessionStoreData {
    try {
      const raw = fs.readFileSync(this.filePath, 'utf8');
      const data: SessionStoreData = JSON.parse(raw);
      const now = Date.now();
      for (const [key, record] of Object.entries(data.sessions)) {
        if (now - record.updatedAt > SESSION_TTL_MS) {
          delete data.sessions[key];
        }
      }
      return data;
    } catch {
      return { sessions: {} };
    }
  }

  save(data: SessionStoreData): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const tmp = this.filePath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
    fs.renameSync(tmp, this.filePath);
  }

  upsert(record: SessionRecord): void {
    const data = this.load();
    data.sessions[record.sessionId] = record;
    this.save(data);
  }

  lookup(sessionId: string): SessionRecord | null {
    if (!sessionId) return null;
    const data = this.load();
    return data.sessions[sessionId] ?? null;
  }

  consume(sessionId: string): SessionRecord | null {
    if (!sessionId) return null;
    const data = this.load();
    const record = data.sessions[sessionId];
    if (!record) return null;
    delete data.sessions[sessionId];
    this.save(data);
    return record;
  }

  findByContext(surfaceId: string, workspaceId: string): SessionRecord | null {
    const data = this.load();
    return (
      Object.values(data.sessions).find(
        (r) => r.surfaceId === surfaceId && r.workspaceId === workspaceId,
      ) ?? null
    );
  }
}
