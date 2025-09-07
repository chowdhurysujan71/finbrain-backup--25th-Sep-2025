# Storage Spec (Supabase, Signed URLs)

Provider: Supabase Storage (bucket: $SUPABASE_BUCKET, private)

## Endpoints

### POST /assets/upload-url
**Purpose**: Generate signed URL for file upload  
**Input**: `{"path","content_type","size"}` with path prefix `"{user_id}/"`  
**Output**: `{"upload_url","expires_in": 60, "path"}`  
**Authentication**: X-User-ID header required

### GET /assets/download-url?path=...
**Purpose**: Generate signed URL for file download  
**Output**: `{"download_url","expires_in": 60}`  
**Authentication**: X-User-ID header required

### DELETE /assets?path=...
**Purpose**: Delete asset (optional)  
**Requirement**: `ASSETS_ALLOW_DELETE=true`  
**Authentication**: X-User-ID header required

## Security

### Authentication
- Require X-User-ID header
- Path must start with `"{user_id}/"`

### Content Type Allowlist
- `image/png`
- `image/jpeg`
- `application/pdf`
- `text/plain`
- `application/json`

### File Size Limits
- Maximum: 10 MB (10,485,760 bytes)

### URL Expiration
- Signed URLs expire in 60 seconds
- Private bucket (no public ACLs)

## Client Flow

1. **Upload Process**:
   ```bash
   # 1. Get upload URL
   POST /assets/upload-url
   Headers: X-User-ID: user123
   Body: {"path":"user123/document.pdf","content_type":"application/pdf","size":1024}
   
   # 2. Upload file bytes directly to Supabase
   PUT {upload_url}
   Headers: {headers from step 1}
   Body: {file bytes}
   
   # 3. Store canonical path in database
   ```

2. **Download Process**:
   ```bash
   # 1. Get download URL
   GET /assets/download-url?path=user123/document.pdf
   Headers: X-User-ID: user123
   
   # 2. Download file bytes directly from Supabase
   GET {download_url}
   ```

## Environment Variables

- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Service role key with storage permissions
- `SUPABASE_BUCKET`: Storage bucket name (default: "user-assets")
- `ASSETS_ALLOW_DELETE`: Enable delete endpoint (default: false)

## Error Responses

### 400 Bad Request
- Missing required fields in request body
- Invalid content type (not in allowlist)
- File size exceeds 10 MB limit
- Missing path query parameter

### 401 Unauthorized
- Missing X-User-ID header

### 403 Forbidden
- Path doesn't start with user ID prefix
- Asset deletion not enabled (for DELETE endpoint)

### 500 Internal Server Error
- Supabase API communication failure
- Invalid environment configuration

## Runbook

### Common Issues

#### 4xx Errors
- **Validation failures**: Check request format, headers, path prefix
- **Content type rejection**: Verify file type is in allowlist
- **Size limit**: Ensure file is under 10 MB

#### 5xx Errors from Provider
- **Temporary failures**: Retry with exponential backoff
- **Sustained failures**: Open incident, check Supabase status
- **Configuration issues**: Verify environment variables

### Monitoring
- All requests logged with user_id, request_id, path, operation, status, latency
- Structured JSON logging for observability
- X-Request-ID header propagation for correlation

## Acceptance Criteria

- [ ] All tests pass (validation, mocking, edge cases)
- [ ] Direct upload succeeds with curl using signed URLs
- [ ] Private bucket verified (no public access without signed URL)
- [ ] Request logging includes all required fields
- [ ] Error handling prevents stack trace leakage
- [ ] Feature flag controls delete endpoint availability