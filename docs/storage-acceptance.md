# Storage Acceptance Testing (Supabase)

## Prerequisites

### Environment Setup
```bash
# Set required secrets in Replit
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_BUCKET=user-assets

# Optional: Enable delete endpoint
ASSETS_ALLOW_DELETE=true
```

### Supabase Bucket Configuration
1. Create bucket named `user-assets` in Supabase Storage
2. Set bucket to **private** (no public access)
3. Configure RLS policies for service role access

## Acceptance Test Steps

### Step 1: Test Environment Verification
```bash
# Verify server is running with assets routes
curl -s http://localhost:5000/health
# Expected: {"status":"ok"}

# Check server logs for assets registration
# Expected: "✓ Assets API routes registered"
```

### Step 2: Upload URL Generation
```bash
# Valid upload URL request
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -d '{"path":"testuser123/sample.jpg","content_type":"image/jpeg","size":1024}'

# Expected Response:
{
  "upload_url": "https://your-project.supabase.co/storage/v1/object/user-assets/testuser123/sample.jpg",
  "expires_in": 60,
  "path": "testuser123/sample.jpg",
  "headers": {
    "Authorization": "Bearer your-service-key",
    "Content-Type": "image/jpeg"
  }
}
```

### Step 3: Validation Testing
```bash
# Missing X-User-ID header (should return 401)
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -d '{"path":"testuser123/sample.jpg","content_type":"image/jpeg","size":1024}'

# Invalid path prefix (should return 403)
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -d '{"path":"wronguser/sample.jpg","content_type":"image/jpeg","size":1024}'

# Invalid content type (should return 400)
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -d '{"path":"testuser123/virus.exe","content_type":"application/x-executable","size":1024}'

# File too large (should return 400)
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -d '{"path":"testuser123/large.jpg","content_type":"image/jpeg","size":11000000}'
```

### Step 4: Actual File Upload
```bash
# Create test file
echo "Test file content for Supabase Storage" > test_upload.txt

# Get upload URL
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -d '{"path":"testuser123/test_upload.txt","content_type":"text/plain","size":36}')

# Extract upload URL and headers
UPLOAD_URL=$(echo $UPLOAD_RESPONSE | jq -r '.upload_url')
AUTH_HEADER=$(echo $UPLOAD_RESPONSE | jq -r '.headers.Authorization')

# Upload file to Supabase
curl -X POST "$UPLOAD_URL" \
  -H "Authorization: $AUTH_HEADER" \
  -H "Content-Type: text/plain" \
  -T test_upload.txt

# Expected: 200 OK response
```

### Step 5: Download URL Generation
```bash
# Get download URL for uploaded file
curl -X GET "http://localhost:5000/assets/download-url?path=testuser123/test_upload.txt" \
  -H "X-User-ID: testuser123"

# Expected Response:
{
  "download_url": "https://your-project.supabase.co/storage/v1/object/sign/user-assets/testuser123/test_upload.txt?token=...",
  "expires_in": 60
}
```

### Step 6: Actual File Download
```bash
# Get download URL
DOWNLOAD_RESPONSE=$(curl -s -X GET "http://localhost:5000/assets/download-url?path=testuser123/test_upload.txt" \
  -H "X-User-ID: testuser123")

# Extract download URL
DOWNLOAD_URL=$(echo $DOWNLOAD_RESPONSE | jq -r '.download_url')

# Download file from Supabase
curl -s "$DOWNLOAD_URL" -o downloaded_file.txt

# Verify content matches
diff test_upload.txt downloaded_file.txt
# Expected: No differences
```

### Step 7: Request Logging Verification
```bash
# Check server logs for structured JSON entries
# Expected log format for each request:
{
  "ts": 1757227445849,
  "level": "info", 
  "request_id": "uuid-string",
  "user_id": "testuser123",
  "path": "testuser123/test_upload.txt",
  "op": "upload_url",
  "status": 200,
  "latency_ms": 45.67
}
```

### Step 8: Security Verification
```bash
# Attempt direct access without signed URL (should fail)
curl -s "https://your-project.supabase.co/storage/v1/object/public/user-assets/testuser123/test_upload.txt"
# Expected: 403 Forbidden or 404 Not Found (bucket is private)

# Verify X-Request-ID propagation
curl -X POST http://localhost:5000/assets/upload-url \
  -H "Content-Type: application/json" \
  -H "X-User-ID: testuser123" \
  -H "X-Request-ID: test-correlation-123" \
  -d '{"path":"testuser123/test.jpg","content_type":"image/jpeg","size":1024}' \
  -i | grep "X-Request-ID: test-correlation-123"
```

### Step 9: Delete Endpoint (if enabled)
```bash
# Test delete endpoint when ASSETS_ALLOW_DELETE=true
curl -X DELETE "http://localhost:5000/assets/?path=testuser123/test_upload.txt" \
  -H "X-User-ID: testuser123"

# Expected Response:
{
  "success": true,
  "path": "testuser123/test_upload.txt"
}

# Verify file is deleted
curl -s -X GET "http://localhost:5000/assets/download-url?path=testuser123/test_upload.txt" \
  -H "X-User-ID: testuser123"
# Expected: 500 error when trying to generate URL for non-existent file
```

## Automated Test Suite
```bash
# Run comprehensive test suite
cd /home/runner/workspace
python -m pytest tests/test_assets_supabase.py -v

# Expected: All tests passing
# Tests cover: validation, mocking, edge cases, error handling
```

## Success Criteria

✅ **All manual curl tests pass**  
✅ **Automated test suite passes**  
✅ **File upload/download flow works end-to-end**  
✅ **Private bucket confirmed (no public access)**  
✅ **Request logging captures all required fields**  
✅ **Error responses don't leak stack traces**  
✅ **X-Request-ID correlation works**  
✅ **Content type and size validation enforced**  
✅ **Path prefix security enforced**

## Cleanup
```bash
# Remove test files
rm test_upload.txt downloaded_file.txt

# Optional: Clean up test files in Supabase Storage bucket
```