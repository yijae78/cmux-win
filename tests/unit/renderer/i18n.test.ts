import { describe, it, expect } from 'vitest';

// 직접 JSON을 import하여 구조 검증
import en from '../../../resources/locales/en.json';
import ko from '../../../resources/locales/ko.json';
import ja from '../../../resources/locales/ja.json';

function getAllKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null) {
      keys.push(...getAllKeys(v as Record<string, unknown>, path));
    } else {
      keys.push(path);
    }
  }
  return keys;
}

describe('i18n locale files', () => {
  const enKeys = getAllKeys(en);
  const koKeys = getAllKeys(ko);
  const jaKeys = getAllKeys(ja);

  it('en has at least 40 keys', () => {
    expect(enKeys.length).toBeGreaterThanOrEqual(40);
  });

  it('ko has same keys as en', () => {
    expect(koKeys.sort()).toEqual(enKeys.sort());
  });

  it('ja has same keys as en', () => {
    expect(jaKeys.sort()).toEqual(enKeys.sort());
  });
});
