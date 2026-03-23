/**
 * JSON-RPC 2.0 protocol type definitions.
 *
 * Design spec §9.1 — shared protocol schemas used by both the socket
 * router (main process) and any external clients.
 */

import { z } from 'zod';

// ===== Request Schema =====

export const JsonRpcRequestSchema = z.object({
  jsonrpc: z.literal('2.0'),
  method: z.string(),
  params: z.unknown().optional(),
  id: z.union([z.string(), z.number(), z.null()]).optional(),
});

export type JsonRpcRequest = z.infer<typeof JsonRpcRequestSchema>;

// ===== Response Schema =====

export const JsonRpcResponseSchema = z.object({
  jsonrpc: z.literal('2.0'),
  id: z.union([z.string(), z.number(), z.null()]),
  result: z.unknown().optional(),
  error: z
    .object({
      code: z.number(),
      message: z.string(),
      data: z.unknown().optional(),
    })
    .optional(),
});

export type JsonRpcResponse = z.infer<typeof JsonRpcResponseSchema>;

// ===== Standard JSON-RPC Error Codes =====

export const JSON_RPC_ERRORS = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
} as const;

export type JsonRpcErrorCode = (typeof JSON_RPC_ERRORS)[keyof typeof JSON_RPC_ERRORS];
