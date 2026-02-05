# 3D Mesh Prototyping Cell - Frontend Tests

This directory contains unit tests for the 3D Mesh Prototyping Cell frontend implementation.

## Test Files

### MeshPrototypingCell.test.ts
Comprehensive tests for the MeshPrototypingCell BaseCell v1.0 implementation.

**Coverage Areas**:
- ✅ Describe method returns correct metadata
- ✅ Validate method for local-gpu mode
- ✅ Validate method for cloud-api mode
- ✅ Validate method for manual-upload mode
- ✅ Execute method with local-gpu mode
- ✅ Execute method with cloud-api mode
- ✅ Execute method with manual-upload mode
- ✅ Health check with backend available
- ✅ Health check with backend unavailable
- ✅ Setup and teardown lifecycle methods
- ✅ Error handling for API failures

**Total Tests**: 15+

## Running Tests

### Run Tests
```bash
# From cockpit-vue directory
npm run test -- artifacts/canonical/cell_types/3d-mesh-prototyping-cell/frontend/tests/MeshPrototypingCell.test.ts
```

### Run with Coverage
```bash
npm run test:coverage -- artifacts/canonical/cell_types/3d-mesh-prototyping-cell/frontend/tests/
```

## Test Architecture

The MeshPrototypingCell frontend communicates with the backend via HTTP POST requests to execute 3D mesh generation with multiple generation modes.

**Mocked Services**:
- `apiService` - HTTP client for backend communication
- `endpoints` - Backend endpoint configuration
- `logger` - Logging utility

**Key Features**:
- Multiple generation modes (local-gpu, cloud-api, manual-upload)
- HTTP-based backend communication
- Comprehensive input validation
- Error handling and recovery

## References

- **Implementation**: `../MeshPrototypingCell.ts`
- **View Component**: `../View.vue`
- **BaseCell Interface**: `/cockpit-vue/src/types/BaseCell.ts`
- **Backend Implementation**: `../../backend/scripts/main.py`
