# Paste-Ready Replit AI Auto-Verification Prompt

Copy the text below and paste directly into Replit AI:

---

**Act as a test engineer performing black-box verification of the FinBrain `/ai-chat` endpoint.**

Run the following automated verification checks against the running application and provide a detailed test report.

## Test Objectives

1. **Authentication Gate**: Verify `/ai-chat` returns 401/403 without cookies
2. **Authenticated Flow**: Verify `/ai-chat` returns 200 with valid session cookie  
3. **Data Persistence**: Confirm expense appears in Report view after chat creation
4. **Server Logging**: Detect consistent user_id across request lifecycle
5. **Log Pattern Analysis**: Grep server logs for critical patterns

## Test Execution Steps

### Step 1: Anonymous Access Test
```bash
curl -i -X POST "https://$(echo $REPL_SLUG.$(echo $REPL_OWNER).repl.co)/ai-chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"log 50 taxi unauthorized test"}'
```
**Expected**: HTTP 401 or 403 status code, no expense created

### Step 2: Authenticated Access Test
**[PROMPT USER]** Please paste your browser Cookie header from DevTools:
1. Open DevTools → Network tab
2. Make any request to the app while logged in
3. Find the request → Headers → Copy the full `Cookie:` header value
4. Paste it here

Once provided, I'll run:
```bash
curl -i -X POST "https://$(echo $REPL_SLUG.$(echo $REPL_OWNER).repl.co)/ai-chat" \
  -H "Content-Type: application/json" \
  -H "Cookie: [PASTED_COOKIE_HEADER]" \
  -d '{"message":"log 77 groceries auth test"}'
```
**Expected**: HTTP 200 status, JSON response containing success confirmation

### Step 3: Data Persistence Verification
Test that the expense appears in the Report view:
```bash
curl -s -H "Cookie: [SAME_COOKIE]" "https://$(echo $REPL_SLUG.$(echo $REPL_OWNER).repl.co)/report" | grep -i "groceries\|77"
```
**Expected**: HTML containing the new expense entry

### Step 4: Server Log Analysis
Grep application logs for critical patterns:

```bash
# Check for route access logging
grep "route=/ai-chat" /tmp/logs/*.log | tail -20

# Check for authentication failures  
grep -i "auth_failed\|unauthorized_access" /tmp/logs/*.log | tail -20

# Check for successful expense saves
grep -i "expense_saved\|expense_logged" /tmp/logs/*.log | tail -20

# Check for request correlation IDs
grep -E "request_id|rid.*ai-chat" /tmp/logs/*.log | tail -20
```

### Step 5: User ID Consistency Check
Verify the same user_id flows through the entire request:
```bash
# Extract request_id from the successful auth test response headers or logs
LAST_REQUEST_ID="[EXTRACT_FROM_LOGS]"

# Find all log entries for that request_id
grep "$LAST_REQUEST_ID" /tmp/logs/*.log | grep -E "user_id|session_user_id|resolved_user_id|db_user_id"
```

## Test Report Format

Provide your findings in this exact format:

```
## AUTO-VERIFICATION TEST REPORT

### Test Results Summary
- [ ] Anonymous Access: PASS/FAIL - Status: [HTTP_CODE]
- [ ] Authenticated Access: PASS/FAIL - Status: [HTTP_CODE] 
- [ ] Data Persistence: PASS/FAIL - Found in Report: YES/NO
- [ ] Server Logging: PASS/FAIL - Patterns Found: [COUNT]
- [ ] User ID Consistency: PASS/FAIL - Same ID: YES/NO

### Detailed Findings

**Authentication Gate Test:**
Request: [CURL_COMMAND]
Response Status: [HTTP_CODE]
Response Headers: [KEY_HEADERS]
Response Body: [TRUNCATED_BODY]

**Authenticated Flow Test:**
Request: [CURL_COMMAND]
Response Status: [HTTP_CODE] 
Response Body: [TRUNCATED_BODY]
Detected User ID: [USER_ID_PREFIX]

**Data Persistence Check:**
Report URL: [URL]
Expense Found: YES/NO
Excerpt: [RELEVANT_HTML_SNIPPET]

**Log Pattern Analysis:**
route=/ai-chat matches: [COUNT] 
auth_failed matches: [COUNT]
expense_saved matches: [COUNT]

Last 5 relevant log entries:
[LOG_ENTRIES]

**User ID Flow Tracking:**
Request ID: [REQUEST_ID]
Session User ID: [ID_FROM_SESSION]
Resolved User ID: [ID_FROM_MIDDLEWARE] 
DB User ID: [ID_FROM_INSERT]
Consistency: PASS/FAIL

### Security Assessment
- Authentication properly enforced: YES/NO
- User isolation maintained: YES/NO  
- Sensitive data logged: YES/NO (flag if found)

### Overall Result: PASS/FAIL

**Critical Issues (if any):**
- [List any security or functional issues]

**Recommendations:**
- [List any improvements needed]
```

## Failure Criteria

Mark the test as **FAIL** if any of these occur:
- Anonymous access returns 200 (authentication bypass)
- Authenticated access returns 401/403 (auth system broken)
- Expense doesn't appear in Report view (persistence failure)
- User ID inconsistencies in logs (identity confusion)
- No structured logging for security events (monitoring gap)

## Success Criteria

Mark the test as **PASS** only if:
✅ Anonymous calls blocked with 401/403
✅ Authenticated calls succeed with 200
✅ New expenses visible in Report immediately
✅ Consistent user_id throughout request lifecycle  
✅ Proper structured logging for audit trail

Start the verification process now. Ask for the Cookie header when needed.