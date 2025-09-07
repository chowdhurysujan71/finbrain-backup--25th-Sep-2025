# Supabase Test Endpoint

## Overview
The `/supabase-test` endpoint provides a minimal smoke test to verify Supabase Storage connectivity from the FinBrain application.

## Expected Secrets
This endpoint requires the following environment variables to be configured in Replit Secrets:

- `SUPABASE_URL`: Your Supabase project URL (e.g., `https://your-project.supabase.co`)
- `SUPABASE_SERVICE_KEY`: Service role key with storage permissions
- `SUPABASE_BUCKET`: Storage bucket name (defaults to "user-assets" if not specified)

## Endpoint Details

**URL**: `GET /supabase-test`  
**Authentication**: None required (uses service key internally)  
**Timeout**: 3 seconds

## API Behavior

### Success Response (200)
Returns a JSON array listing objects in the configured bucket:
```json
[
  {
    "name": "user123/document.pdf",
    "id": "uuid-here",
    "updated_at": "2025-09-07T10:00:00.000Z",
    "created_at": "2025-09-07T09:00:00.000Z",
    "last_accessed_at": "2025-09-07T10:30:00.000Z",
    "metadata": {
      "eTag": "\"abc123\"",
      "size": 1024,
      "mimetype": "application/pdf"
    }
  }
]
```

**Note**: The array may be empty `[]` if no objects exist in the bucket.

### Error Response (503)
Returns error details when connection fails:
```json
{
  "error": "Supabase connection failed: HTTPSConnectionPool..."
}
```

Common error scenarios:
- Missing environment variables
- Network connectivity issues  
- Invalid credentials
- Request timeout (>3s)
- Bucket access denied

## Usage Example

```bash
curl https://<your-replit-app>.replit.app/supabase-test
```

Example with local development:
```bash
curl http://localhost:5000/supabase-test
```

## Acceptance Criteria

✅ **Success**: Returns HTTP 200 with JSON array (empty or populated)  
✅ **Environment**: All required secrets configured in Replit  
✅ **Performance**: Response within 3 seconds  
✅ **Error Handling**: Returns 503 with descriptive error message on failure  

## Troubleshooting

### Common Issues

**503 - Missing Environment Variables**
```json
{"error": "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required"}
```
**Solution**: Configure the required secrets in Replit

**503 - Connection Timeout**
```json
{"error": "Supabase request timeout (3s exceeded)"}
```
**Solution**: Check network connectivity and Supabase service status

**503 - Authentication Failed**
```json
{"error": "Supabase connection failed: 401 Unauthorized"}
```
**Solution**: Verify SUPABASE_SERVICE_KEY has storage permissions

**503 - Bucket Not Found**
```json
{"error": "Supabase connection failed: 404 Not Found"}
```
**Solution**: Create the specified bucket in Supabase Storage or update SUPABASE_BUCKET variable