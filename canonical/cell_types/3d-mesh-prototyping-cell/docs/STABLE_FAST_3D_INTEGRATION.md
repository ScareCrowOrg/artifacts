---
processed: true
processed_date: 2026-02-01
updated_docs:
  - docs/official/backend/ai-integration/stable-fast-3d-cloud-api.md
themes:
  - ai-integration
  - 3d-generation
  - setup-guide
  - api-documentation
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Stable Fast 3D API Integration Guide

## Overview

This document describes the integration of Stability AI's Stable Fast 3D API into the 3D Mesh Prototyping Cell. The implementation enables cloud-based 3D mesh generation from single images using the `cloud-api` generation mode.

## Features

- **Cloud-based 3D Generation**: Generate 3D meshes without local GPU requirements
- **Automatic Authentication**: Secure API key management via environment variables
- **Comprehensive Error Handling**: User-friendly error messages for common API issues
- **Configurable Parameters**: Control texture resolution and foreground ratio
- **Full Test Coverage**: 29 automated tests covering all scenarios

## Architecture

### Components

1. **Stable Fast 3D Client** (`stable_fast_3d_client.py`)
   - Handles API authentication and requests
   - Converts image formats (base64 data URLs to binary)
   - Parses API responses and extracts GLB data
   - Provides comprehensive error handling

2. **Main Integration** (`main.py`)
   - Routes cloud-api requests to the Stable Fast 3D client
   - Extracts and validates input data
   - Returns standardized responses

3. **Configuration** (`backend/app/config.py`, `.env.example`)
   - Centralizes API configuration
   - Provides sensible defaults
   - Supports environment variable overrides

## Configuration

### Required Setup

1. **Get API Key**
   - Sign up at [Stability AI Platform](https://platform.stability.ai/)
   - Navigate to API Keys section
   - Generate a new API key

2. **Configure Environment**
   
   Add to your `.env` file:
   ```bash
   # Stable Fast 3D API Configuration
   STABLE_FAST_3D_API_KEY=sk-your-api-key-here
   STABLE_FAST_3D_URL=https://api.stability.ai/v2beta/3d/stable-fast-3d
   STABLE_FAST_3D_TIMEOUT=60
   ```

3. **Verify Configuration**
   
   The client will automatically load configuration from environment variables. If the API key is not configured, cloud-api mode will gracefully fail with an informative error message.

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `STABLE_FAST_3D_API_KEY` | Your Stability AI API key | None | Yes |
| `STABLE_FAST_3D_URL` | API endpoint URL | `https://api.stability.ai/v2beta/3d/stable-fast-3d` | No |
| `STABLE_FAST_3D_TIMEOUT` | Request timeout in seconds | 60 | No |

## Usage

### From Frontend

The frontend can trigger cloud-api generation by setting the generation mode:

```javascript
const response = await apiFetch('/api/cells/execute-ephemeral', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    cell_type: '3d-mesh-prototyping-cell',
    input_data: {
      generationMode: 'cloud-api',  // Use cloud API
      inputImage: 'data:image/png;base64,iVBORw0KGgo...',
      reconstructionParams: {
        textureResolution: 1024,  // Optional: 1024, 2048, etc.
        foregroundRatio: 0.85     // Optional: 0.0 to 1.0
      }
    }
  })
})
```

### Direct API Usage

You can also use the Stable Fast 3D client directly:

```python
from stable_fast_3d_client import create_client

# Create client (loads config from environment)
client = create_client()

if client:
    # Generate mesh
    result = client.generate_mesh(
        image_data="data:image/png;base64,iVBORw0KGgo...",
        texture_resolution=1024,
        foreground_ratio=0.85
    )
    
    if result["success"]:
        glb_data = result["mesh_data"]  # Base64-encoded GLB
        metadata = result["metadata"]
    else:
        print(f"Error: {result['error']}")
else:
    print("API key not configured")
```

## API Parameters

### Input Parameters

- **image_data** (required): Base64-encoded image data URL
  - Format: `data:image/png;base64,<base64_data>`
  - Supported formats: PNG, JPG, JPEG
  - Recommended: High-quality images with clear subject

- **texture_resolution** (optional, default: 1024)
  - Controls the resolution of generated textures
  - Options: 512, 1024, 2048
  - Higher values = better quality but slower generation

- **foreground_ratio** (optional, default: 0.85)
  - Ratio of foreground subject to background
  - Range: 0.0 to 1.0
  - 0.85 works well for most images

### Response Format

Success response:
```python
{
    "success": True,
    "mode": "cloud-api",
    "message": "3D mesh generated successfully via Stable Fast 3D API",
    "mesh_data": "data:model/gltf-binary;base64,<glb_data>",
    "metadata": {
        "fileSizeBytes": 12345,
        "modelType": "stable_fast_3d",
        "generationSource": "stability_ai_api"
    }
}
```

Error response:
```python
{
    "success": False,
    "error": "Authentication failed. Please check your API key.",
    "mesh_data": None,
    "metadata": {
        "error_code": 401,
        "error_detail": "Invalid API key"
    }
}
```

## Error Handling

The client provides user-friendly error messages for common scenarios:

| HTTP Status | User Message |
|-------------|--------------|
| 401 | Authentication failed. Please check your API key. |
| 403 | Access forbidden. Your API key may not have permission for this service. |
| 429 | Rate limit exceeded. Please try again later. |
| 400 | Bad request: [specific error from API] |
| 500+ | Stability AI service error. Please try again later. |
| Timeout | API request timeout after N seconds. The service may be overloaded. |
| Network | Network error: [specific error] |

## Troubleshooting

### "API key not configured"

**Cause**: `STABLE_FAST_3D_API_KEY` environment variable is not set.

**Solution**:
1. Add API key to `.env` file
2. Restart backend service
3. Verify configuration with: `echo $STABLE_FAST_3D_API_KEY`

### "Authentication failed"

**Cause**: Invalid or expired API key.

**Solution**:
1. Verify API key is correct (check for extra spaces)
2. Generate new API key at [Stability AI Platform](https://platform.stability.ai/)
3. Update `.env` file with new key
4. Restart backend service

### "Rate limit exceeded"

**Cause**: Too many requests in short time period.

**Solution**:
1. Wait before retrying (typically 1 minute)
2. Consider upgrading API plan for higher limits
3. Implement request queuing in your application

### "Request timeout"

**Cause**: API taking too long to respond (> 60 seconds default).

**Solution**:
1. Check internet connection
2. Try again (may be temporary service load)
3. Increase timeout: `STABLE_FAST_3D_TIMEOUT=120`

### Invalid image format errors

**Cause**: Image data is not properly formatted or corrupted.

**Solution**:
1. Ensure image is base64-encoded data URL
2. Verify image is valid PNG/JPG
3. Check image size (recommended < 5MB)
4. Test with known-good image first

## Testing

### Running Tests

```bash
# Run all Stable Fast 3D tests
cd backend
poetry run pytest ../artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/test_stable_fast_3d_client.py -v

# Run integration tests
poetry run pytest ../artifacts/canonical/cell_types/3d-mesh-prototyping-cell/backend/tests/test_main.py::TestCloudAPIGeneration -v
```

### Test Coverage

- **Client Tests**: 24 tests covering initialization, image decoding, API requests, response handling
- **Integration Tests**: 5 tests covering main.py integration
- **Total**: 29 tests with 100% pass rate

### Testing Without API Key

All tests use mocks and do not require a real API key. They verify:
- Correct request formatting
- Proper authentication headers
- Response parsing logic
- Error handling for all scenarios

## Performance Considerations

- **Generation Time**: Typically 1-5 seconds on Stability AI servers
- **Network Latency**: Add 100-500ms for API round-trip
- **Recommended Timeout**: 60 seconds (default)
- **Rate Limits**: Check your API plan limits
- **Cost**: API calls are metered - see [Stability AI Pricing](https://platform.stability.ai/pricing)

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for all secrets
3. **Rotate API keys** regularly (every 90 days)
4. **Monitor API usage** to detect unauthorized access
5. **Use HTTPS** for all API communications (enforced by client)
6. **Validate input** before sending to API (prevents unnecessary costs)

## API Documentation

For more details on the Stable Fast 3D API:
- [Official API Documentation](https://platform.stability.ai/docs/api-reference)
- [Stable Fast 3D Product Page](https://www.stablefast3d.com/)
- [API Status Page](https://status.stability.ai/)

## Support

For issues related to:
- **This integration**: Open issue in ScareVerse repository
- **Stability AI API**: Contact [Stability AI Support](https://platform.stability.ai/support)
- **API key or billing**: [Stability AI Account](https://platform.stability.ai/account)
