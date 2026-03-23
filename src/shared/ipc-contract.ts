/**
 * Zod-based bidirectional IPC contract.
 *
 * Design spec §7.3 — every IPC channel used between main ↔ renderer
 * is listed here with its input and output schemas so both sides can
 * validate payloads at runtime.
 */

import { z } from 'zod';
import { ActionSchema } from './actions';
import { IPC_CHANNELS } from './ipc-channels';

// ===== Reusable sub-schemas =====

const DispatchResultSchema = z.object({
  ok: z.boolean(),
  error: z.string().optional(),
});

const PtyWriteInputSchema = z.object({
  surfaceId: z.string(),
  data: z.string(),
});

const PtyMetadataSchema = z.object({
  surfaceId: z.string(),
  cwd: z.string().optional(),
  gitBranch: z.string().optional(),
  gitDirty: z.boolean().optional(),
  exitCode: z.number().optional(),
});

const PtySpawnInputSchema = z.object({
  surfaceId: z.string(),
  options: z
    .object({
      shell: z.string().optional(),
      cwd: z.string().optional(),
      cols: z.number().optional(),
      rows: z.number().optional(),
      workspaceId: z.string().optional(),
    })
    .optional(),
});

const PtySpawnOutputSchema = z.object({
  id: z.string(),
  pid: z.number(),
});

const PtyResizeInputSchema = z.object({
  surfaceId: z.string(),
  cols: z.number(),
  rows: z.number(),
});

const PtyKillInputSchema = z.object({
  surfaceId: z.string(),
});

const PtyHasInputSchema = z.object({
  surfaceId: z.string(),
});

const PtyDataSchema = z.object({
  surfaceId: z.string(),
  data: z.string(),
});

const PtyExitSchema = z.object({
  surfaceId: z.string(),
  exitCode: z.number(),
  signal: z.number().optional(),
});

const PtyGetShellsOutputSchema = z.array(z.string());

const ShortcutInputSchema = z.object({
  action: z.string(),
});

const ScrollbackSaveInputSchema = z.object({
  surfaceId: z.string(),
  data: z.string(),
});

const ScrollbackLoadInputSchema = z.object({
  surfaceId: z.string(),
});

const ScrollbackLoadOutputSchema = z.object({
  surfaceId: z.string(),
  data: z.string().nullable(),
});

const BrowserExecuteInputSchema = z.object({
  surfaceId: z.string(),
  code: z.string(),
});

const BrowserExecuteResultSchema = z.object({
  surfaceId: z.string(),
  result: z.unknown().optional(),
  error: z.string().optional(),
});

// ===== IPC Contract =====

export const IpcContract = {
  [IPC_CHANNELS.DISPATCH]: {
    input: ActionSchema,
    output: DispatchResultSchema,
  },
  [IPC_CHANNELS.QUERY_STATE]: {
    input: z.object({ path: z.string().optional() }),
    output: z.unknown(),
  },
  [IPC_CHANNELS.GET_INITIAL_STATE]: {
    input: z.void(),
    output: z.unknown(), // Full AppState
  },
  [IPC_CHANNELS.STATE_UPDATE]: {
    input: z.unknown(), // AppState slice pushed from main → renderer
    output: z.void(),
  },
  [IPC_CHANNELS.WINDOW_ID]: {
    input: z.void(),
    output: z.string(),
  },
  [IPC_CHANNELS.PTY_WRITE]: {
    input: PtyWriteInputSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_METADATA]: {
    input: PtyMetadataSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_SPAWN]: {
    input: PtySpawnInputSchema,
    output: PtySpawnOutputSchema,
  },
  [IPC_CHANNELS.PTY_RESIZE]: {
    input: PtyResizeInputSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_KILL]: {
    input: PtyKillInputSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_HAS]: {
    input: PtyHasInputSchema,
    output: z.boolean(),
  },
  [IPC_CHANNELS.PTY_DATA]: {
    input: PtyDataSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_EXIT]: {
    input: PtyExitSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.PTY_GET_SHELLS]: {
    input: z.void(),
    output: PtyGetShellsOutputSchema,
  },
  [IPC_CHANNELS.SHORTCUT]: {
    input: ShortcutInputSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.SCROLLBACK_SAVE]: {
    input: ScrollbackSaveInputSchema,
    output: DispatchResultSchema,
  },
  [IPC_CHANNELS.SCROLLBACK_LOAD]: {
    input: ScrollbackLoadInputSchema,
    output: ScrollbackLoadOutputSchema,
  },
  [IPC_CHANNELS.BROWSER_EXECUTE]: {
    input: BrowserExecuteInputSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.BROWSER_EXECUTE_RESULT]: {
    input: BrowserExecuteResultSchema,
    output: z.void(),
  },
  [IPC_CHANNELS.FILE_READ]: {
    input: z.object({ filePath: z.string() }),
    output: z.union([z.object({ content: z.string() }), z.object({ error: z.string() })]),
  },
} as const;

export type IpcContractType = typeof IpcContract;

// Type-level guard: ensure every channel has a contract entry.
// If a new channel is added to IPC_CHANNELS but not here, this
// line will produce a compile-time error.
export type AssertAllChannelsCovered = {
  [K in (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS]]: K extends keyof IpcContractType
    ? true
    : never;
};
