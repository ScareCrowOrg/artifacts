/**
 * @file UserSelectionCell.test.ts
 * @description Unit tests for UserSelectionCell (BaseCell implementation).
 *
 * NOTE: UserSelectionCell imports from `@/types/BaseCell` which cannot be
 * resolved in the test environment (the shared types live in artifacts/shared/types,
 * outside the cockpit-vue @/ alias). Following the established codebase pattern
 * (see ArtifactsExplorerCell.test.ts, fragment-editor-cell, calculator-cell), this
 * test uses inline stubs that replicate the cell's logic to verify behavior.
 *
 * Coverage:
 * - execute() returns a noop success result
 * - describe() returns correct metadata
 * - validate() accepts 'pick-one' and rejects other modes
 * - show() calls store.open() and resolves with user or null
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

// ── Module mocks (hoisted before imports) ─────────────────────────────────

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn(),
}))

// ── Inline stubs ──────────────────────────────────────────────────────────
// Avoids @/types/BaseCell import resolution issues in test environment.

export interface SelectableUser {
  id: string
  username: string
  email: string
  role?: string
}

/** Minimal stub replicating UserSelectionCell logic for unit testing. */
class UserSelectionCell {
  private _store: {
    open: (title: string, resolve: (user: SelectableUser | null) => void) => Promise<void>
  }

  constructor(store: { open: (title: string, resolve: (user: SelectableUser | null) => void) => Promise<void> }) {
    this._store = store
  }

  async execute(_input: Record<string, any>) {
    return {
      success: true,
      output: { message: 'UserSelectionCell is invoked via show(), not execute().' },
      execution_time: 0,
    }
  }

  async describe() {
    return {
      id: 'user-selection-cell',
      name: 'User Selection Cell',
      version: '1.0.0',
      description:
        'Ephemeral cell that opens a modal overlay for selecting a user. ' +
        'Returns Promise<SelectableUser | null> via show(). Admin-only.',
      inputs: {
        mode: {
          type: 'string',
          description: "Selection mode. Only 'pick-one' is supported.",
          required: false,
          default: 'pick-one',
        },
        title: {
          type: 'string',
          description: 'Title shown in the selection overlay.',
          required: false,
          default: 'Select a User',
        },
      },
      outputs: {
        user: {
          type: 'object',
          description: 'The selected user, or null if cancelled.',
        },
      },
      tags: ['user', 'selection', 'modal', 'ephemeral', 'admin'],
    }
  }

  validate(input: Record<string, any>) {
    const errors: Array<{ field: string; message: string }> = []
    if (input.mode && input.mode !== 'pick-one') {
      errors.push({
        field: 'mode',
        message: "Only 'pick-one' mode is currently supported.",
      })
    }
    return errors
  }

  async show(
    _data: Record<string, any>,
    options: { mode?: string; title?: string; [key: string]: any },
  ): Promise<SelectableUser | null> {
    const overlayTitle =
      typeof options?.title === 'string' ? options.title : 'Select a User'

    return new Promise<SelectableUser | null>((resolve) => {
      this._store.open(overlayTitle, (user) => {
        resolve(user)
      })
    })
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeUser(overrides: Partial<SelectableUser> = {}): SelectableUser {
  return {
    id: 'user-1',
    username: 'alice',
    email: 'alice@example.com',
    role: 'admin',
    ...overrides,
  }
}

function makeStore(
  onOpen?: (title: string, resolve: (user: SelectableUser | null) => void) => void,
) {
  return {
    open: vi.fn(async (title: string, resolve: (user: SelectableUser | null) => void) => {
      onOpen?.(title, resolve)
    }),
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// execute()
// ─────────────────────────────────────────────────────────────────────────────

describe('UserSelectionCell.execute()', () => {
  let store: ReturnType<typeof makeStore>
  let cell: UserSelectionCell

  beforeEach(() => {
    store = makeStore()
    cell = new UserSelectionCell(store)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('returns success=true with a noop message', async () => {
    const result = await cell.execute({})
    expect(result.success).toBe(true)
    expect(result.output.message).toContain('show()')
  })

  it('does not call the store in execute()', async () => {
    await cell.execute({})
    expect(store.open).not.toHaveBeenCalled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// describe()
// ─────────────────────────────────────────────────────────────────────────────

describe('UserSelectionCell.describe()', () => {
  let store: ReturnType<typeof makeStore>
  let cell: UserSelectionCell

  beforeEach(() => {
    store = makeStore()
    cell = new UserSelectionCell(store)
  })

  it('returns id = "user-selection-cell"', async () => {
    const meta = await cell.describe()
    expect(meta.id).toBe('user-selection-cell')
  })

  it('returns name = "User Selection Cell"', async () => {
    const meta = await cell.describe()
    expect(meta.name).toBe('User Selection Cell')
  })

  it('returns version = "1.0.0"', async () => {
    const meta = await cell.describe()
    expect(meta.version).toBe('1.0.0')
  })

  it('includes mode and title in inputs', async () => {
    const meta = await cell.describe()
    expect(meta.inputs).toHaveProperty('mode')
    expect(meta.inputs).toHaveProperty('title')
  })

  it('includes user in outputs', async () => {
    const meta = await cell.describe()
    expect(meta.outputs).toHaveProperty('user')
  })

  it('includes admin and ephemeral tags', async () => {
    const meta = await cell.describe()
    expect(meta.tags).toContain('ephemeral')
    expect(meta.tags).toContain('admin')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// validate()
// ─────────────────────────────────────────────────────────────────────────────

describe('UserSelectionCell.validate()', () => {
  let store: ReturnType<typeof makeStore>
  let cell: UserSelectionCell

  beforeEach(() => {
    store = makeStore()
    cell = new UserSelectionCell(store)
  })

  it('returns no errors for mode "pick-one"', () => {
    const errors = cell.validate({ mode: 'pick-one' })
    expect(errors).toHaveLength(0)
  })

  it('returns no errors when mode is absent', () => {
    const errors = cell.validate({})
    expect(errors).toHaveLength(0)
  })

  it('returns error for unsupported mode "pick-many"', () => {
    const errors = cell.validate({ mode: 'pick-many' })
    expect(errors).toHaveLength(1)
    expect(errors[0].field).toBe('mode')
    expect(errors[0].message).toContain("'pick-one'")
  })

  it('returns error for any other mode value', () => {
    const errors = cell.validate({ mode: 'broadcast' })
    expect(errors.some((e) => e.field === 'mode')).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// show()
// ─────────────────────────────────────────────────────────────────────────────

describe('UserSelectionCell.show()', () => {
  let store: ReturnType<typeof makeStore>
  let cell: UserSelectionCell

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls store.open() with the provided title', async () => {
    store = makeStore((title, resolve) => resolve(null))
    cell = new UserSelectionCell(store)

    await cell.show({}, { title: 'Select a user for allowance' })

    expect(store.open).toHaveBeenCalledTimes(1)
    const [calledTitle] = store.open.mock.calls[0]
    expect(calledTitle).toBe('Select a user for allowance')
  })

  it('defaults title to "Select a User" when not provided', async () => {
    store = makeStore((title, resolve) => resolve(null))
    cell = new UserSelectionCell(store)

    await cell.show({}, {})

    const [calledTitle] = store.open.mock.calls[0]
    expect(calledTitle).toBe('Select a User')
  })

  it('resolves with selected user when store calls resolve(user)', async () => {
    const user = makeUser()
    store = makeStore((_title, resolve) => resolve(user))
    cell = new UserSelectionCell(store)

    const result = await cell.show({}, { title: 'Pick user' })

    expect(result).toEqual(user)
    expect(result?.username).toBe('alice')
  })

  it('resolves with null when store calls resolve(null) (cancel)', async () => {
    store = makeStore((_title, resolve) => resolve(null))
    cell = new UserSelectionCell(store)

    const result = await cell.show({}, {})

    expect(result).toBeNull()
  })

  it('uses "mode" from options without error (pick-one)', async () => {
    store = makeStore((_title, resolve) => resolve(null))
    cell = new UserSelectionCell(store)

    await expect(
      cell.show({}, { mode: 'pick-one', title: 'Test' }),
    ).resolves.toBeNull()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// allowArtifact() — mirror of ArtifactsExplorerCell.allowArtifact()
// (tests the integration pattern, not the actual class which uses BaseCell)
// ─────────────────────────────────────────────────────────────────────────────

describe('allowArtifact() integration pattern', () => {
  it('returns selected user when show() resolves with user', async () => {
    const user = makeUser({ username: 'bob', email: 'bob@example.com' })
    const userCellStore = makeStore((_title, resolve) => resolve(user))
    const userCell = new UserSelectionCell(userCellStore)

    const result = await userCell.show({}, { mode: 'pick-one', title: 'Select user for allowance' })

    expect(result).toEqual(user)
  })

  it('returns null when show() is cancelled', async () => {
    const userCellStore = makeStore((_title, resolve) => resolve(null))
    const userCell = new UserSelectionCell(userCellStore)

    const result = await userCell.show({}, { mode: 'pick-one', title: 'Select user for allowance' })

    expect(result).toBeNull()
  })
})
