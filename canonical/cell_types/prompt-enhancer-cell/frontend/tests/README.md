# PromptEnhancerCell Tests

## Overview

This directory contains unit tests for the `PromptEnhancerCell` utility cell.

## Test Coverage

The test suite covers:

### Core Functionality
- ✅ Cell metadata (`describe()`)
- ✅ Input validation (`validate()`)
- ✅ Prompt enhancement execution (`execute()`)
- ✅ Error handling

### Enhancement Modes
- ✅ Concise mode
- ✅ Detailed mode
- ✅ Technical mode
- ✅ Creative mode

### Audience Targeting
- ✅ Developer framing
- ✅ User framing
- ✅ AI framing
- ✅ General framing

### Additional Features
- ✅ Context addition
- ✅ Prompt truncation (maxLength)
- ✅ Token estimation
- ✅ Lifecycle methods (setup/teardown)
- ✅ Health checks

## Running Tests

```bash
# From cockpit-vue directory
npm run test -- artifacts/canonical/cell_types/prompt-enhancer-cell/frontend/tests/PromptEnhancerCell.test.ts

# With coverage
npm run test:coverage -- artifacts/canonical/cell_types/prompt-enhancer-cell/frontend/tests/PromptEnhancerCell.test.ts
```

## Test Structure

```
PromptEnhancerCell.test.ts
├── describe()
│   └── should return correct metadata
├── validate()
│   ├── should pass validation for valid input
│   ├── should fail for missing/empty prompt
│   ├── should fail for invalid mode
│   ├── should fail for invalid audience
│   └── should fail for invalid maxLength
├── execute()
│   ├── Enhancement modes (concise/detailed/technical/creative)
│   ├── Audience framing (developer/user/ai/general)
│   ├── Context addition
│   ├── Prompt truncation
│   ├── Error handling
│   └── Execution metadata
├── setup() and teardown()
│   └── should execute without errors
└── health_check()
    └── should always return healthy

```

## Coverage Target

**Target**: 90%+ code coverage (RULESET.md Rule 3.1)

Current metrics measured include:
- Statement coverage
- Branch coverage
- Function coverage
- Line coverage

## Related Files

- [PromptEnhancerCell.ts](../PromptEnhancerCell.ts) - Implementation
- [README.md](../README.md) - Cell documentation
