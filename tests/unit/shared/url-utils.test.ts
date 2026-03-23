import { describe, it, expect } from 'vitest';
import { isUrl, inputToUrl } from '../../../src/shared/url-utils';

describe('isUrl', () => {
  it('detects http://', () => expect(isUrl('http://x.com')).toBe(true));
  it('detects https://', () => expect(isUrl('https://x.com')).toBe(true));
  it('detects localhost', () => expect(isUrl('localhost:3000')).toBe(true));
  it('detects IP', () => expect(isUrl('192.168.1.1')).toBe(true));
  it('detects domain.tld', () => expect(isUrl('example.com')).toBe(true));
  it('rejects plain text', () => expect(isUrl('hello world')).toBe(false));
  it('rejects no-tld', () => expect(isUrl('notadomain')).toBe(false));
});

describe('inputToUrl', () => {
  it('passes http through', () => expect(inputToUrl('http://x.com')).toBe('http://x.com'));
  it('passes https through', () => expect(inputToUrl('https://x.com')).toBe('https://x.com'));
  it('adds http to localhost', () =>
    expect(inputToUrl('localhost:3000')).toBe('http://localhost:3000'));
  it('adds http to IP', () => expect(inputToUrl('192.168.1.1')).toBe('http://192.168.1.1'));
  it('adds https to domain', () => expect(inputToUrl('example.com')).toBe('https://example.com'));
  it('converts text to search', () =>
    expect(inputToUrl('hello')).toContain('google.com/search?q=hello'));
  it('uses specified engine', () =>
    expect(inputToUrl('test', 'duckduckgo')).toContain('duckduckgo.com'));
  it('returns about:blank for empty', () => expect(inputToUrl('')).toBe('about:blank'));
});
