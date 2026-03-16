# xterm-terminal-cell

Interactive terminal cell that provides persistent shell access through the
[Node-PTY Service](../../services/node-pty-service/README.md).

## Quick Reference

- **Cell ID**: `xterm-terminal-cell`
- **Category**: infrastructure
- **Backend**: UI-only (no execution)
- **Frontend**: xterm.js + WebSocket

## Files

```
xterm-terminal-cell/
├── type.json                  Cell type definition
├── frontend/
│   ├── View.vue               Terminal UI component (TypeScript)
│   ├── xterm-terminal.ts      BaseCell implementation
│   ├── composables.ts         usePTYConnection, useTerminalResize
│   └── tests/
│       └── View.spec.ts       Vitest component tests
├── backend/
│   ├── scripts/main.py        UI-only no-op backend
│   └── tests/test_main.py     pytest tests
└── docs/README.md             Full documentation
```

## See Also

- [docs/README.md](docs/README.md) — Full documentation with WebSocket API reference
- [Node-PTY Service](../../services/node-pty-service/README.md) — Backend terminal service
