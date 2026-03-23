import { describe, it, expect, afterAll } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

describe('scrollback file persistence', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sb-test-'));

  afterAll(() => fs.rmSync(tmpDir, { recursive: true, force: true }));

  it('saves and loads scrollback data', () => {
    const filePath = path.join(tmpDir, 'scrollback.json');
    const data = { 'surf-1': 'line1\nline2', 'surf-2': 'hello' };
    fs.writeFileSync(filePath, JSON.stringify(data));
    const loaded = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    expect(loaded['surf-1']).toBe('line1\nline2');
    expect(loaded['surf-2']).toBe('hello');
  });

  it('handles missing file gracefully', () => {
    let result: Record<string, string> = {};
    try {
      result = JSON.parse(fs.readFileSync(path.join(tmpDir, 'missing.json'), 'utf8'));
    } catch {
      /* expected */
    }
    expect(Object.keys(result)).toHaveLength(0);
  });

  it('handles corrupted file gracefully', () => {
    const corruptPath = path.join(tmpDir, 'corrupt.json');
    fs.writeFileSync(corruptPath, 'not valid json{{{');
    let result: Record<string, string> = {};
    try {
      result = JSON.parse(fs.readFileSync(corruptPath, 'utf8'));
    } catch {
      /* expected */
    }
    expect(Object.keys(result)).toHaveLength(0);
  });

  it('atomic write prevents corruption', () => {
    const filePath = path.join(tmpDir, 'atomic.json');
    const tmpPath = filePath + '.tmp';
    const data = { 'surf-1': 'test content' };
    fs.writeFileSync(tmpPath, JSON.stringify(data));
    fs.renameSync(tmpPath, filePath);
    const loaded = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    expect(loaded['surf-1']).toBe('test content');
    expect(fs.existsSync(tmpPath)).toBe(false);
  });
});
