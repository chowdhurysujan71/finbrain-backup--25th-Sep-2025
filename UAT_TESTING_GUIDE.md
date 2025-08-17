# FinBrain UAT Testing Guide

## Overview
FinBrain includes a built-in User Acceptance Testing (UAT) system that runs live tests through actual Messenger interactions. This allows you to systematically verify all features work correctly in the production environment.

## How to Start UAT Testing

### Method 1: Messenger Command
1. Open your Facebook Messenger bot
2. Send the message: **`start uat`**
3. Follow the guided 8-step testing sequence

### Method 2: Alternative Commands
- `begin uat`
- `uat start` 
- `test bot`

## UAT Testing Sequence

The UAT system will guide you through these steps:

### Step 1: Welcome Response
- **Prompt**: "Welcome! Let's run a live test of your Financial Advisor bot. Reply with anything to continue."
- **Test**: Basic bot responsiveness

### Step 2: Expense Logging
- **Prompt**: "Please type an expense, e.g. 'I spent 500 BDT on groceries yesterday.'"
- **Test**: Amount extraction and expense recording

### Step 3: Categorization
- **Prompt**: "Now add a different type of spend, e.g. '2000 BDT for rent.'"
- **Test**: AI categorization accuracy

### Step 4: Multi-Entry
- **Prompt**: "Add one more, e.g. '150 BDT for transport.'"
- **Test**: Multiple expense handling

### Step 5: Summary Generation
- **Prompt**: "Type 'summary' to ask the bot for an overview of your spends."
- **Test**: Data aggregation and summary generation

### Step 6: Rate Limiting Test
- **Prompt**: "Send 5 messages quickly, e.g. 'test1', 'test2'… until you hit the 4-per-minute AI cap."
- **Test**: Rate limiter functionality (4 AI requests per 60 seconds)

### Step 7: Fallback Verification
- **Prompt**: "After hitting the cap, verify the bot shows the disclaimer + template reply."
- **Test**: Graceful degradation when rate limited

### Step 8: Context Recall
- **Prompt**: "Ask 'What did I spend most on?' to see if AI recalls your data."
- **Test**: Context-driven AI responses

## Expected Results

### ✅ Successful UAT Completion
After all 8 steps, you should see:
```
🎉 UAT COMPLETED!

Tester: Live Tester
Duration: 45.2 seconds
Steps completed: 8/8

✅ Test Results Summary:
- Data logging: ✓
- Categorization: ✓
- Multi-entry: ✓
- Summary/advice: ✓
- Rate limiting: ✓
- Fallback system: ✓
- Context recall: ✓

Your FinBrain system is ready for production!
```

### ⚠️ Potential Issues
- **Database errors**: Check PostgreSQL connection
- **AI failures**: Verify Gemini API key is configured
- **Rate limiting not working**: Check limiter configuration
- **Missing context**: Verify expense logging is working

## UAT Management Commands

### Check UAT Status
Send: `uat stats` or `uat status`
Response: Shows number of active UAT sessions

### UAT Logs
Check Replit console for detailed logs:
- `UAT step X completed for [user_hash]...`
- Routing decisions and processing details
- Error messages if issues occur

## Manual Testing Checklist

If you prefer manual testing, verify these features:

- [ ] Bot responds to expense messages
- [ ] Amounts are extracted correctly (500 BDT, $25, etc.)
- [ ] Categories are assigned (food, rent, transport, etc.)
- [ ] Rate limiting kicks in after 4 AI requests/minute
- [ ] Fallback messages appear when rate limited
- [ ] Summary command works
- [ ] Context-driven advice is relevant
- [ ] 280-character limit is enforced

## Production Deployment

Once UAT passes all tests:

1. **Re-enable security features**:
   - HTTPS enforcement in `app.py`
   - Signature verification in `webhook_processor.py`

2. **Deploy to Replit**:
   - Click the Deploy button
   - Update Facebook webhook URL to production domain

3. **Final verification**:
   - Run UAT one more time on production URL
   - Verify all security features work

## Troubleshooting

### Common Issues

**Database Schema Errors**:
```bash
# Run this to update schema
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

**Rate Limiting Not Working**:
- Check `utils/engagement.py` configuration
- Verify AI_LIMIT = 4 and WINDOW_SECONDS = 60

**AI Not Responding**:
- Verify GEMINI_API_KEY is set
- Check `ai_adapter_gemini.py` logs

**Webhook Not Receiving Messages**:
- Verify HTTPS is enabled for production
- Check Facebook webhook configuration
- Confirm signature verification is working

This UAT system ensures your FinBrain deployment is fully functional before going live with real users.