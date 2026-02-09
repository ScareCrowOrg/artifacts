# SVG Generator Cell - Frontend Tests

## Overview

This directory contains comprehensive tests for the `SvgGeneratorCell` BaseCell implementation.

## Test Files

### `SvgGeneratorCell.test.ts`

Unit tests for the BaseCell implementation covering:

- **Execution Tests**: Valid inputs, LLM integration, fallback mechanisms
- **Validation Tests**: Input validation, error handling
- **Metadata Tests**: Cell description and capabilities
- **Health Check Tests**: Service availability monitoring
- **Integration Tests**: Complete workflows and edge cases

## Test Coverage

Target: **90%+ code coverage** (RULESET.md Rule 3.1)

### Coverage Areas:
- ✅ `execute()` method - All branches
- ✅ `validate()` method - All validation rules
- ✅ `describe()` method - Metadata completeness
- ✅ `health_check()` method - All service states
- ✅ Error handling and fallback mechanisms
- ✅ LLM service integration

## Running Tests

### Run all tests:
```bash
npm run test:unit
```

### Run svg-generator-cell tests only:
```bash
npm run test:unit -- svg-generator-cell
```

### Run with coverage:
```bash
npm run test:coverage
```

### Watch mode (development):
```bash
npm run test:watch
```

## Test Structure

Tests follow the **AAA pattern** (Arrange, Act, Assert):

```typescript
it('should successfully generate SVG from valid prompt', async () => {
  // Arrange
  const mockSvg = '<svg>...</svg>'
  vi.mocked(aiChatService.processMessage).mockResolvedValue({
    message: mockSvg
  } as any)
  
  // Act
  const result = await cell.execute({
    prompt: 'A blue circle'
  })
  
  // Assert
  expect(result.success).toBe(true)
  expect(result.output.svg).toBe(mockSvg)
})
```

## Mocking Strategy

### AI Chat Service (`aiChatService`)
- **Mock**: All LLM service calls
- **Reason**: Avoid external dependencies, ensure deterministic tests
- **Implementation**: Vitest `vi.mock()` with custom responses

### Test Scenarios:
1. **Success**: LLM returns valid SVG
2. **Code Blocks**: LLM wraps SVG in markdown code blocks
3. **Service Failure**: LLM service unavailable (use fallback)
4. **Invalid Response**: LLM returns non-SVG content (use fallback)
5. **No Models**: Service available but no models (degraded health)

## Key Test Insights

### Fallback Mechanism
The cell gracefully degrades when the LLM service is unavailable:
- Returns a minimal red circle SVG placeholder
- Marks output with `fallback: true`
- Still succeeds (not a failure) - user can retry

### Health Check States
- **Healthy**: LLM service available with models
- **Degraded**: Service available but limited (no models or errors)
- **Can Always Execute**: Even in degraded state, fallback ensures execution

### Validation Rules
- Prompt: Required, non-empty string, max 5000 chars
- Model: Optional string (default: 'mistral')
- Temperature: Optional number 0-1 (default: 0.7)
- MaxTokens: Optional number 100-10000 (default: 2000)

## Dependencies

### Test Framework
- **Vitest**: Test runner
- **@vue/test-utils**: Vue component testing utilities

### Mocked Services
- `@/services/aiChatService`: LLM interaction
- `@/types/BaseCell`: Type definitions

## Continuous Integration

Tests run automatically on:
- Pull Request creation
- Push to main branch
- Manual workflow dispatch

## Related Documentation

- [BaseCell Interface](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [Test Architecture](../../../docs/official/standards/ARQUITETURA_TESTES.md)
- [RULESET.md - Testing Rules](../../../docs/official/RULESET.md#3-testing-rules)

---

**Last Updated**: 2026-02-09  
**Test Coverage**: 90%+  
**Status**: ✅ All tests passing
