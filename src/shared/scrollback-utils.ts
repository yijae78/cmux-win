export const MAX_SCROLLBACK_LINES = 10000;
export const MAX_SCROLLBACK_BYTES = 1_000_000; // 1MB

/**
 * 터미널 버퍼에서 스크롤백 텍스트를 추출한다.
 * xterm.js IBuffer 인터페이스를 받아 줄 단위로 텍스트를 추출.
 *
 * 실제 xterm.js 의존성 없이 테스트 가능하도록 최소 인터페이스 사용.
 */
export interface MinimalBuffer {
  length: number;
  getLine(index: number): { translateToString(trimRight?: boolean): string } | undefined;
}

export function extractScrollback(buffer: MinimalBuffer): string {
  const lines: string[] = [];
  const totalRows = buffer.length;
  const startRow = Math.max(0, totalRows - MAX_SCROLLBACK_LINES);

  for (let i = startRow; i < totalRows; i++) {
    const line = buffer.getLine(i);
    if (line) lines.push(line.translateToString(true));
  }

  let result = lines.join('\n');
  if (result.length > MAX_SCROLLBACK_BYTES) {
    result = result.slice(-MAX_SCROLLBACK_BYTES);
  }
  return result;
}

/**
 * 저장된 스크롤백 크기가 제한 이내인지 확인
 */
export function isScrollbackWithinLimits(scrollback: string): boolean {
  return scrollback.length <= MAX_SCROLLBACK_BYTES;
}
