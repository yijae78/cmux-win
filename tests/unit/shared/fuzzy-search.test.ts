import { describe, it, expect } from 'vitest';
import { fuzzySearch } from '../../../src/shared/fuzzy-search';

describe('fuzzySearch', () => {
  const items = [
    { name: 'Split Right' },
    { name: 'Split Down' },
    { name: 'New Workspace' },
    { name: 'Close Panel' },
  ];
  const search = (q: string) => fuzzySearch(items, q, (i) => i.name);

  it('matches substring', () => {
    const r = search('split');
    expect(r.length).toBe(2);
    expect(r[0].item.name).toContain('Split');
  });

  it('scores consecutive matches higher', () => {
    const r = fuzzySearch([{ n: 'abc' }, { n: 'axbxc' }], 'abc', (i) => i.n);
    expect(r[0].item.n).toBe('abc');
  });

  it('returns all for empty query', () => {
    expect(search('').length).toBe(4);
  });

  it('returns empty for no match', () => {
    expect(search('xyz').length).toBe(0);
  });

  it('case insensitive', () => {
    expect(search('SPLIT').length).toBe(2);
  });
});
