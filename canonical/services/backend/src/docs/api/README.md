---
processed: true
processed_date: 2025-12-09
themes:
  - api
  - documentation
  - index
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend API Documentation

Documentation for the ScareVerse backend REST API, including endpoint specifications, integration tests, and contract testing.

## Index

### Core Documentation
- `MODELOS_IA_API.md` - AI Models API endpoints and usage
- `INTEGRATION_TEST_ARCHITECTURE.md` - Integration testing strategy and architecture
- `API_CONTRACT_TESTS_IMPLEMENTATION.md` - Contract testing with Pact implementation

## API Overview

The backend exposes RESTful endpoints for:
- **Artifacts**: Cells and books (notebooks) management
- **Authentication**: OAuth2 and password-based auth
- **AI Chat**: Message processing with multiple providers
- **File Operations**: File and directory management
- **AI Models**: Model configuration and management
- **Services**: External service integration
- **Sessions**: User session management
- **Sharing**: Ngrok-based file sharing

## Endpoint Categories

### Authentication (`/api/auth`)
- OAuth2 login flow
- Token refresh and validation
- Password authentication
- User session management

### Artifacts (`/api/celulas`, `/api/livros`)
- Create, read, update cells
- Execute cell code
- Book (notebook) management
- Cell-to-book associations

### Chat IA (`/api/chat`)
- Message processing
- Intention classification
- Multi-provider support (Ollama, Gemini)
- Conversation history

### File Operations (`/api/ScareFeraLab`, `/api/salvar`, `/api/listar_arquivos`)
- File tree navigation
- Save and load files
- Move files/directories
- Directory listing

### AI Models (`/api/modelos-ia`)
- CRUD operations for AI models
- Model configuration
- Provider selection
- See [MODELOS_IA_API.md](./MODELOS_IA_API.md) for details

### Services (`/api/services`)
- Service status checking
- External service management
- Health monitoring

### Sharing (`/api/share`)
- Create public share URLs
- Manage active shares
- File upload for sharing

## Testing

### Integration Tests
Complete integration test architecture documented in [INTEGRATION_TEST_ARCHITECTURE.md](./INTEGRATION_TEST_ARCHITECTURE.md).

Key points:
- Tests backend endpoints with mocked MongoDB
- Validates request/response contracts
- Ensures proper error handling
- Maintains fast execution (<3 minutes)

### Contract Tests
API contract testing using Pact framework documented in [API_CONTRACT_TESTS_IMPLEMENTATION.md](./API_CONTRACT_TESTS_IMPLEMENTATION.md).

Key points:
- Provider contract validation
- Consumer-driven contracts
- Backward compatibility checks
- Integration with CI/CD pipeline

### Running Tests

```bash
# Integration tests
pytest tests/integration/

# Contract tests (provider side)
pytest tests/contracts/provider/

# All API tests
pytest tests/ -k "integration or contract"
```

## API Standards

### Request/Response Format
- JSON content type
- RESTful conventions
- Proper HTTP status codes
- Consistent error responses

### Authentication
- Bearer token in Authorization header
- JWT-based authentication
- Token expiration handling
- Automatic refresh mechanisms

### Error Handling
- Structured error responses
- HTTP status code alignment
- Detailed error messages
- Validation error details

## Related Documentation

- [Backend App Code](../../app/) - API implementation
- [Authentication Documentation](../auth/) - Auth details
- [Chat IA Documentation](../chat-ia/) - AI chat integration
- [Test Architecture](../../../docs/ARQUITETURA_TESTES.md) - Overall testing strategy
- [Backend Main README](../../README.md) - Backend overview

## Notes

- All endpoint paths use English
- API contracts are language-agnostic
- Documentation may be bilingual
- Follow RESTful best practices
- Maintain backward compatibility
