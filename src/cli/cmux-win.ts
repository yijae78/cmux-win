import fs from 'node:fs';
import crypto from 'node:crypto';
import { rpcCall } from './socket-client';

const HELP_TEXT = `cmux-win CLI - control cmux-win via socket API

Usage: cmux-win <command> [options]

Commands:
  ping                          Check if cmux-win is running
  version                       Show cmux-win version info
  list-workspaces               List all workspaces
  list-windows                  List all windows
  new-workspace                 Create a new workspace
    --window <id>               Window ID (required)
    --name <name>               Workspace name (optional)
  select-workspace <id>         Select a workspace by ID
  send                          Send text to a terminal surface
    --surface <id>              Surface ID (required)
    <text>                      Text to send (remaining args)
  notify                        Create a notification
    --title <title>             Notification title (required)
    --body <body>               Notification body (optional)
    --subtitle <subtitle>       Notification subtitle (optional)
  list-notifications            List all notifications
  ssh <user@host[:port]>        Create workspace and connect via SSH
  claude-hook <subcommand>      Agent hook commands
    session-start                 Register a new agent session
    prompt-submit                 Clear notifications, set running status
    pre-tool-use                  Track tool usage (captures AskUserQuestion)
    notification | notify         Send notification for agent input needed
    stop | idle                   Mark agent as idle, send completion notification
    session-end                   Remove session and clear notifications

Options:
  --addr <address>              Socket address (default: tcp://127.0.0.1:19840)
  --help                        Show this help message
`;

interface ParsedArgs {
  command: string;
  positional: string[];
  flags: Map<string, string>;
}

function parseArgs(argv: string[]): ParsedArgs {
  // Skip node and script path
  const args = argv.slice(2);
  const command = args[0] || '';
  const positional: string[] = [];
  const flags = new Map<string, string>();

  let i = 1;
  while (i < args.length) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const key = arg;
      const nextVal = args[i + 1];
      if (nextVal !== undefined && !nextVal.startsWith('--')) {
        flags.set(key, nextVal);
        i += 2;
      } else {
        flags.set(key, '');
        i += 1;
      }
    } else {
      positional.push(arg);
      i += 1;
    }
  }

  return { command, positional, flags };
}

function readStdinJson(): Record<string, unknown> | null {
  try {
    if (process.stdin.isTTY) return null;
    const input = fs.readFileSync(0, 'utf8');
    return input.trim() ? JSON.parse(input) : null;
  } catch {
    return null;
  }
}

async function main(): Promise<void> {
  const { command, positional, flags } = parseArgs(process.argv);
  const addr = flags.get('--addr');

  if (!command || command === '--help' || flags.has('--help')) {
    console.log(HELP_TEXT);
    return;
  }

  try {
    let result: unknown;

    switch (command) {
      case 'ping':
        result = await rpcCall('system.ping', undefined, addr);
        break;

      case 'version':
        result = await rpcCall('system.identify', undefined, addr);
        break;

      case 'list-workspaces':
        result = await rpcCall('workspace.list', undefined, addr);
        break;

      case 'list-windows':
        result = await rpcCall('window.list', undefined, addr);
        break;

      case 'new-workspace': {
        const windowId = flags.get('--window');
        if (!windowId) {
          console.error('Error: --window <id> is required');
          process.exit(1);
        }
        const params: Record<string, string> = { windowId };
        const name = flags.get('--name');
        if (name) params.name = name;
        result = await rpcCall('workspace.create', params, addr);
        break;
      }

      case 'select-workspace': {
        const workspaceId = positional[0];
        if (!workspaceId) {
          console.error('Error: workspace ID is required');
          process.exit(1);
        }
        result = await rpcCall('workspace.select', { workspaceId }, addr);
        break;
      }

      case 'send': {
        const surfaceId = flags.get('--surface');
        if (!surfaceId) {
          console.error('Error: --surface <id> is required');
          process.exit(1);
        }
        const text = positional.join(' ');
        if (!text) {
          console.error('Error: text to send is required');
          process.exit(1);
        }
        result = await rpcCall('surface.send_text', { surfaceId, text }, addr);
        break;
      }

      case 'notify': {
        const title = flags.get('--title');
        if (!title) {
          console.error('Error: --title is required');
          process.exit(1);
        }
        const notifyParams: Record<string, string> = { title };
        const body = flags.get('--body');
        if (body) notifyParams.body = body;
        const subtitle = flags.get('--subtitle');
        if (subtitle) notifyParams.subtitle = subtitle;
        result = await rpcCall('notification.create', notifyParams, addr);
        break;
      }

      case 'list-notifications':
        result = await rpcCall('notification.list', undefined, addr);
        break;

      case 'claude-hook': {
        const { ClaudeHookSessionStore } = await import('./claude-hook-session-store');
        const subCmd = positional[0];
        const sessionStore = new ClaudeHookSessionStore();
        const hookAddr = flags.get('--addr') || addr;

        // session_id is read from stdin JSON
        const input = readStdinJson();
        const sessionId = input?.session_id as string | undefined;
        const surfaceId = process.env.CMUX_SURFACE_ID || '';
        const workspaceId = process.env.CMUX_WORKSPACE_ID || '';
        const claudePid = process.env.CMUX_CLAUDE_PID;

        const resolveSession = () => {
          if (sessionId) return sessionStore.lookup(sessionId);
          return sessionStore.findByContext(surfaceId, workspaceId);
        };
        const consumeSession = () => {
          if (sessionId) return sessionStore.consume(sessionId);
          const found = sessionStore.findByContext(surfaceId, workspaceId);
          if (found) return sessionStore.consume(found.sessionId);
          return null;
        };

        try {
          switch (subCmd) {
            case 'session-start':
            case 'active': {
              const sid = sessionId || crypto.randomUUID();
              sessionStore.upsert({
                sessionId: sid,
                workspaceId,
                surfaceId,
                cwd: (input?.cwd as string) || process.cwd(),
                pid: claudePid ? parseInt(claudePid) : undefined,
                startedAt: Date.now(),
                updatedAt: Date.now(),
              });
              await rpcCall(
                'agent.session_start',
                {
                  sessionId: sid,
                  agentType: 'claude',
                  workspaceId,
                  surfaceId,
                  pid: claudePid ? parseInt(claudePid) : undefined,
                },
                hookAddr,
              );
              break;
            }

            case 'prompt-submit': {
              const record = resolveSession();
              if (!record) break;
              await rpcCall('notification.clear', { workspaceId: record.workspaceId }, hookAddr);
              await rpcCall(
                'agent.status_update',
                {
                  sessionId: record.sessionId,
                  status: 'running',
                  icon: '\u26A1',
                  color: '#4C8DFF',
                },
                hookAddr,
              );
              break;
            }

            case 'pre-tool-use': {
              const record = resolveSession();
              if (!record) break;
              if (
                input?.tool_name === 'AskUserQuestion' &&
                (input?.tool_input as Record<string, unknown>)?.question
              ) {
                record.lastBody = (input.tool_input as Record<string, unknown>).question as string;
                record.updatedAt = Date.now();
                sessionStore.upsert(record);
              }
              await rpcCall(
                'agent.status_update',
                {
                  sessionId: record.sessionId,
                  status: 'running',
                },
                hookAddr,
              );
              break;
            }

            case 'notification':
            case 'notify': {
              const record = resolveSession();
              if (!record) break;
              const body = record.lastBody || (input?.body as string) || '';
              if (record.lastBody) {
                record.lastBody = undefined;
                record.updatedAt = Date.now();
                sessionStore.upsert(record);
              }
              await rpcCall(
                'agent.status_update',
                {
                  sessionId: record.sessionId,
                  status: 'needs_input',
                  icon: '\uD83D\uDD14',
                  color: '#4C8DFF',
                },
                hookAddr,
              );
              await rpcCall(
                'notification.create',
                {
                  title: (input?.title as string) || 'Claude needs input',
                  subtitle: input?.subtitle as string,
                  body,
                  workspaceId: record.workspaceId,
                  surfaceId: record.surfaceId,
                },
                hookAddr,
              );
              break;
            }

            case 'stop':
            case 'idle': {
              const record = consumeSession();
              if (!record) break;
              await rpcCall(
                'agent.status_update',
                {
                  sessionId: record.sessionId,
                  status: 'idle',
                  icon: '\u23F8',
                  color: '#8E8E93',
                },
                hookAddr,
              );
              await rpcCall(
                'notification.create',
                {
                  title: 'Claude finished',
                  body:
                    (input?.transcript_summary as string) ||
                    `Completed in ${record.cwd || 'unknown'}`,
                  workspaceId: record.workspaceId,
                  surfaceId: record.surfaceId,
                },
                hookAddr,
              );
              break;
            }

            case 'session-end': {
              const record = consumeSession();
              if (!record) break;
              await rpcCall('agent.session_end', { sessionId: record.sessionId }, hookAddr);
              await rpcCall('notification.clear', { workspaceId: record.workspaceId }, hookAddr);
              break;
            }

            default:
              console.error(`Unknown claude-hook subcommand: ${subCmd}`);
              process.exit(1);
          }
        } catch (err) {
          // RPC failure: warn only, exit normally
          console.error(`[claude-hook] Warning: ${err instanceof Error ? err.message : err}`);
        }
        return;
      }

      case 'ssh': {
        const target = positional[0];
        if (!target) {
          console.error('Usage: cmux-win ssh user@host[:port]');
          process.exit(1);
        }

        const { parseSshTarget, buildSshCommand } = await import('../main/remote/ssh-session');
        const parsed = parseSshTarget(target);
        const sshCmd = buildSshCommand(parsed);

        // Get first available window
        const windows = (await rpcCall('window.list', undefined, addr)) as { id: string }[] | null;
        const windowId = windows?.[0]?.id;
        if (!windowId) {
          console.error('Error: no window available');
          process.exit(1);
        }

        // Create workspace named after the SSH target
        await rpcCall(
          'workspace.create',
          {
            windowId,
            name: `SSH: ${parsed.host}`,
          },
          addr,
        );

        console.log(
          JSON.stringify({
            status: 'ok',
            message: `Created workspace "SSH: ${parsed.host}". Run: ${sshCmd.shell} ${sshCmd.args.join(' ')}`,
            host: parsed.host,
            user: parsed.user,
            port: parsed.port,
          }),
        );
        return;
      }

      default:
        console.error(`Unknown command: ${command}`);
        console.log(HELP_TEXT);
        process.exit(1);
    }

    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`Error: ${message}`);
    process.exit(1);
  }
}

main();
