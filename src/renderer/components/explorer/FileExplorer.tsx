import { FC, useState, useEffect, useRef, useCallback } from 'react';

interface DirEntry {
  name: string;
  isDirectory: boolean;
  path: string;
}

declare global {
  interface Window {
    cmuxFile?: {
      readFile(filePath: string): Promise<{ content: string } | { error: string }>;
      listDirectory(
        dirPath: string,
      ): Promise<{ entries: DirEntry[] } | { error: string }>;
      openFolderDialog(): Promise<{ path: string } | { cancelled: true }>;
    };
  }
}

interface FileExplorerProps {
  rootPath: string | undefined;
  openedProjects?: string[];
  onProjectSelect?: (path: string) => void;
  onNavigate: (dirPath: string) => void;
  onOpenFolder?: () => void;
}

const HIDDEN_NAMES = new Set(['.git', 'node_modules', '.next', '__pycache__', '.venv', '.DS_Store', 'Thumbs.db']);
const DEBOUNCE_MS = 300;

const FileExplorer: FC<FileExplorerProps> = ({ rootPath, openedProjects, onProjectSelect, onNavigate, onOpenFolder }) => {
  const [entries, setEntries] = useState<Map<string, DirEntry[]>>(new Map());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<Set<string>>(new Set());
  const [showHidden, setShowHidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevRootRef = useRef<string | undefined>(undefined);

  // Load a directory's entries
  const loadDir = useCallback(async (dirPath: string) => {
    if (!window.cmuxFile?.listDirectory) return;
    setLoading((prev) => new Set(prev).add(dirPath));
    const result = await window.cmuxFile.listDirectory(dirPath);
    setLoading((prev) => {
      const next = new Set(prev);
      next.delete(dirPath);
      return next;
    });
    if ('error' in result) {
      setError(result.error);
      return;
    }
    setEntries((prev) => {
      const next = new Map(prev);
      next.set(dirPath, result.entries);
      return next;
    });
    setError(null);
  }, []);

  // Debounced root path change
  useEffect(() => {
    if (!rootPath || rootPath === prevRootRef.current) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      prevRootRef.current = rootPath;
      setEntries(new Map());
      setExpanded(new Set());
      void loadDir(rootPath);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [rootPath, loadDir]);

  const toggleExpand = useCallback(
    (dirPath: string) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(dirPath)) {
          next.delete(dirPath);
        } else {
          next.add(dirPath);
          // Lazy load: only load when first expanding
          if (!entries.has(dirPath)) {
            void loadDir(dirPath);
          }
        }
        return next;
      });
    },
    [entries, loadDir],
  );

  const handleDoubleClick = useCallback(
    (dirPath: string) => {
      onNavigate(dirPath);
    },
    [onNavigate],
  );

  // Shorten path for display
  const displayRoot = rootPath
    ? rootPath.replace(/\\/g, '/').split('/').filter(Boolean).slice(-2).join('/')
    : 'No folder';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: '#1e1e1e',
        color: '#ccc',
        display: 'flex',
        flexDirection: 'column',
        fontSize: '13px',
        userSelect: 'none',
      }}
    >
      {/* Header with title + actions */}
      <div
        style={{
          padding: '4px 8px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: '10px', color: '#888', textTransform: 'uppercase', fontWeight: 600 }}>
          Explorer
        </span>
        <span style={{ flex: 1 }} />
        <button
          onClick={() => setShowHidden((v) => !v)}
          title={showHidden ? 'Hide hidden files' : 'Show hidden files'}
          style={{ background: 'none', border: 'none', color: showHidden ? '#0091FF' : '#555', cursor: 'pointer', fontSize: '11px', padding: '1px 3px' }}
        >
          .*
        </button>
        {onOpenFolder && (
          <button
            onClick={onOpenFolder}
            title="Open folder"
            style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '13px', padding: '0 2px' }}
          >
            +
          </button>
        )}
      </div>

      {/* Project tabs — show opened projects, click to switch */}
      {openedProjects && openedProjects.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '2px',
            padding: '4px 6px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            flexShrink: 0,
          }}
        >
          {openedProjects.map((proj) => {
            const isActive = proj === rootPath;
            const label = proj.replace(/\\/g, '/').split('/').filter(Boolean).pop() || proj;
            return (
              <button
                key={proj}
                onClick={() => onProjectSelect?.(proj)}
                title={proj}
                style={{
                  background: isActive ? 'rgba(0,145,255,0.15)' : 'rgba(255,255,255,0.04)',
                  border: isActive ? '1px solid rgba(0,145,255,0.4)' : '1px solid transparent',
                  borderRadius: '3px',
                  color: isActive ? '#0091FF' : '#999',
                  cursor: 'pointer',
                  fontSize: '10px',
                  padding: '2px 6px',
                  maxWidth: '100%',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Tree view */}
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {!rootPath ? (
          <div style={{ color: '#666', padding: '16px', textAlign: 'center' }}>
            {onOpenFolder ? (
              <button
                onClick={onOpenFolder}
                style={{
                  background: '#0091FF',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '6px 16px',
                  cursor: 'pointer',
                  fontSize: '12px',
                }}
              >
                Open Folder
              </button>
            ) : (
              'No folder open'
            )}
          </div>
        ) : error ? (
          <div style={{ color: '#f44', padding: '8px 10px', fontSize: '12px' }}>{error}</div>
        ) : (
          <TreeNode
            dirPath={rootPath}
            depth={0}
            entries={entries}
            expanded={expanded}
            loading={loading}
            showHidden={showHidden}
            onToggle={toggleExpand}
            onDoubleClick={handleDoubleClick}
          />
        )}
      </div>
    </div>
  );
};

// --- TreeNode recursive component ---

interface TreeNodeProps {
  dirPath: string;
  depth: number;
  entries: Map<string, DirEntry[]>;
  expanded: Set<string>;
  loading: Set<string>;
  showHidden: boolean;
  onToggle: (dirPath: string) => void;
  onDoubleClick: (dirPath: string) => void;
}

const TreeNode: FC<TreeNodeProps> = ({
  dirPath,
  depth,
  entries,
  expanded,
  loading,
  showHidden,
  onToggle,
  onDoubleClick,
}) => {
  const items = entries.get(dirPath);
  if (!items && loading.has(dirPath)) {
    return (
      <div style={{ paddingLeft: `${(depth + 1) * 16}px`, color: '#666', fontSize: '12px' }}>
        Loading...
      </div>
    );
  }
  if (!items) return null;

  const filtered = showHidden ? items : items.filter((e) => !HIDDEN_NAMES.has(e.name) && !e.name.startsWith('.'));

  return (
    <>
      {filtered.map((entry) => (
        <FileRow
          key={entry.path}
          entry={entry}
          depth={depth}
          isExpanded={expanded.has(entry.path)}
          isLoading={loading.has(entry.path)}
          onToggle={onToggle}
          onDoubleClick={onDoubleClick}
          entries={entries}
          expanded={expanded}
          loading={loading}
          showHidden={showHidden}
        />
      ))}
    </>
  );
};

// --- FileRow individual item ---

interface FileRowProps {
  entry: DirEntry;
  depth: number;
  isExpanded: boolean;
  isLoading: boolean;
  onToggle: (dirPath: string) => void;
  onDoubleClick: (dirPath: string) => void;
  entries: Map<string, DirEntry[]>;
  expanded: Set<string>;
  loading: Set<string>;
  showHidden: boolean;
}

const FileRow: FC<FileRowProps> = ({
  entry,
  depth,
  isExpanded,
  isLoading,
  onToggle,
  onDoubleClick,
  entries,
  expanded,
  loading,
  showHidden,
}) => {
  const [hovered, setHovered] = useState(false);

  return (
    <>
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => {
          if (entry.isDirectory) onToggle(entry.path);
        }}
        onDoubleClick={() => {
          if (entry.isDirectory) onDoubleClick(entry.path);
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          height: '22px',
          paddingLeft: `${depth * 16 + 8}px`,
          paddingRight: '8px',
          cursor: entry.isDirectory ? 'pointer' : 'default',
          background: hovered ? 'rgba(255,255,255,0.06)' : 'transparent',
          transition: 'background 0.1s',
        }}
      >
        {/* Chevron / indent */}
        <span
          style={{
            width: '16px',
            textAlign: 'center',
            fontSize: '10px',
            color: '#888',
            flexShrink: 0,
          }}
        >
          {entry.isDirectory ? (isLoading ? '\u23F3' : isExpanded ? '\u25BC' : '\u25B6') : ''}
        </span>
        {/* Icon */}
        <span style={{ width: '16px', textAlign: 'center', fontSize: '12px', flexShrink: 0 }}>
          {entry.isDirectory ? '\uD83D\uDCC1' : '\uD83D\uDCC4'}
        </span>
        {/* Name */}
        <span
          style={{
            marginLeft: '4px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: entry.isDirectory ? '#e0e0e0' : '#bbb',
            fontSize: '12px',
          }}
        >
          {entry.name}
        </span>
      </div>
      {/* Recursive children */}
      {entry.isDirectory && isExpanded && (
        <TreeNode
          dirPath={entry.path}
          depth={depth + 1}
          entries={entries}
          expanded={expanded}
          loading={loading}
          showHidden={showHidden}
          onToggle={onToggle}
          onDoubleClick={onDoubleClick}
        />
      )}
    </>
  );
};

export default FileExplorer;
