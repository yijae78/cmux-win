export type SearchEngine = 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage';

const SEARCH_URLS: Record<SearchEngine, string> = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  bing: 'https://www.bing.com/search?q=',
  kagi: 'https://kagi.com/search?q=',
  startpage: 'https://www.startpage.com/search?q=',
};

export function isUrl(input: string): boolean {
  if (/^https?:\/\//i.test(input)) return true;
  if (/^localhost(:\d+)?/i.test(input)) return true;
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(input)) return true;
  if (/^[a-z0-9]([a-z0-9-]*[a-z0-9])?\.[a-z]{2,}(\/|$)/i.test(input)) return true;
  return false;
}

export function inputToUrl(input: string, engine: SearchEngine = 'google'): string {
  const trimmed = input.trim();
  if (!trimmed) return 'about:blank';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (isUrl(trimmed)) {
    if (/^localhost/i.test(trimmed) || /^\d/.test(trimmed)) return `http://${trimmed}`;
    return `https://${trimmed}`;
  }
  return SEARCH_URLS[engine] + encodeURIComponent(trimmed);
}
