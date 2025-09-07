# Supabase Smoke Test Endpoint

## Overview
The `/supabase-smoke` endpoint provides a comprehensive connectivity test for Supabase Storage API integration. It validates that the application can successfully authenticate and communicate with Supabase Storage.

## What It Does
This endpoint:
- Validates presence of required environment variables
- Makes an authenticated POST request to Supabase Storage list API
- Tests the specific API call format used by the application
- Returns structured response indicating connection status
- Handles all error scenarios gracefully with 3-second timeout

## API Details

**URL**: `GET /supabase-smoke`  
**Authentication**: None required (uses service key internally)  
**Timeout**: 3 seconds  
**Method**: Makes POST request to Supabase internally

## Expected Outputs

### Success Response (200)
```json
{
  "connected": true,
  "objects": [
    {
      "name": "testuser/hello.txt",
      "id": "uuid-here",
      "updated_at": "2025-09-07T10:00:00.000Z",
      "created_at": "2025-09-07T09:00:00.000Z",
      "last_accessed_at": "2025-09-07T10:30:00.000Z",
      "metadata": {
        "eTag": "\"abc123\"",
        "size": 12,
        "mimetype": "text/plain"
      }
    }
  ]
}
```

**Note**: The `objects` array may be empty `[]` if no files exist in the bucket.

### Failure Response (503)
```json
{
  "connected": false,
  "error": "Supabase connection failed: 401 Unauthorized"
}
```

## Usage Examples

### Basic Test
```bash
curl https://your-replit-app.replit.app/supabase-smoke
```

### Local Development
```bash
curl http://localhost:5000/supabase-smoke
```

### Check Response Status
```bash
curl -i https://your-replit-app.replit.app/supabase-smoke
```

## Supabase API Call Details

The endpoint makes this exact API call to Supabase:

**Request**:
```http
POST {SUPABASE_URL}/storage/v1/object/list/{SUPABASE_BUCKET}
Authorization: Bearer {SUPABASE_SERVICE_KEY}
apikey: {SUPABASE_SERVICE_KEY}  
Content-Type: application/json

{
  "prefix": "",
  "limit": 1,
  "offset": 0
}
```

This validates the exact authentication and request format used by the application's storage functionality.

## Common Error Scenarios

### Missing Environment Variables
```json
{
  "connected": false,
  "error": "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required"
}
```

### Connection Timeout
```json
{
  "connected": false,
  "error": "Supabase request timeout (3s exceeded)"
}
```

### Authentication Failed
```json
{
  "connected": false,
  "error": "Supabase connection failed: 401 Unauthorized"
}
```

### Bucket Not Found
```json
{
  "connected": false,
  "error": "Supabase connection failed: 404 Not Found"
}
```

## Troubleshooting

1. **503 with missing variables**: Configure `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` in Replit Secrets
2. **503 with 401 error**: Verify service key has storage permissions in Supabase dashboard
3. **503 with 404 error**: Create the specified bucket in Supabase Storage
4. **503 with timeout**: Check network connectivity and Supabase service status

## Success Criteria

✅ **Connected**: Returns `{"connected": true}` with HTTP 200  
✅ **Performance**: Response within 3 seconds  
✅ **Error Handling**: Never crashes app, always returns JSON  
✅ **Real API Test**: Uses actual Supabase Storage list endpoint