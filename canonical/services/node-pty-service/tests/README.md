# Node-PTY Service Tests

Unit tests for the Node-PTY Service, covering PTY session management and Git helper operations.

## Purpose

This directory contains the test suite for the Node-PTY Service source modules:
- **PTY Manager tests**: Validates session creation, input handling, resize, and cleanup
- **Git Helper tests**: Validates Git status, log, and clone operation implementations

## Directory Structure

```
tests/
├── ptyManager.test.js   - Unit tests for PTY session lifecycle management
└── gitHelper.test.js    - Unit tests for Git operation helpers
```

## How to Use

```bash
# Run from the node-pty-service root
cd artifacts/canonical/services/node-pty-service
npm test

# Run specific test file
npx jest tests/ptyManager.test.js
```

## Content Index

| File | Description |
|---|---|
| `ptyManager.test.js` | Tests for PTY session creation, I/O, resize, and close |
| `gitHelper.test.js` | Tests for Git status, log, and clone helper functions |
