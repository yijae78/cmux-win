export interface FuzzyResult<T> {
  item: T;
  score: number;
}

export function fuzzySearch<T>(
  items: T[],
  query: string,
  getText: (item: T) => string,
): FuzzyResult<T>[] {
  if (!query) return items.map((item) => ({ item, score: 0 }));
  const lower = query.toLowerCase();
  return items
    .map((item) => ({ item, score: fuzzyScore(getText(item).toLowerCase(), lower) }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score);
}

function fuzzyScore(text: string, query: string): number {
  let score = 0;
  let qi = 0;
  let consecutive = 0;
  for (let ti = 0; ti < text.length && qi < query.length; ti++) {
    if (text[ti] === query[qi]) {
      score += 1 + consecutive;
      if (ti === qi) score += 2;
      consecutive++;
      qi++;
    } else {
      consecutive = 0;
    }
  }
  return qi === query.length ? score : 0;
}
