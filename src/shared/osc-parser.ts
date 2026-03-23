export interface OscMetadata {
  gitBranch?: string;
  gitDirty?: boolean;
  cwd?: string;
}

/** Parse OSC 133 P data: "P;k=git_branch;v=main*" -> { gitBranch, gitDirty } */
export function parseOsc133P(data: string): OscMetadata {
  if (!data.startsWith('P;')) return {};
  const params: Record<string, string> = {};
  data
    .slice(2)
    .split(';')
    .forEach((kv) => {
      const eqIdx = kv.indexOf('=');
      if (eqIdx !== -1) {
        params[kv.slice(0, eqIdx)] = kv.slice(eqIdx + 1);
      }
    });
  const result: OscMetadata = {};
  if (params.k === 'git_branch' && params.v) {
    const dirty = params.v.endsWith('*');
    result.gitBranch = dirty ? params.v.slice(0, -1) : params.v;
    result.gitDirty = dirty;
  }
  return result;
}

/** Parse OSC 7 data: "file://localhost/c/Users/..." -> CWD path */
export function parseOsc7(data: string): string | null {
  try {
    const url = new URL(data);
    return decodeURIComponent(url.pathname);
  } catch {
    return null;
  }
}
