# User Acceptance Tests for KC
*Testing core FinBrain functionality with fresh user account*

## UAT-1: Basic Expense Logging
**Objective**: Verify expense logging works for new user

**Test Steps**:
1. Send message: `spent 50 on lunch`
2. Verify response confirms expense logged
3. Check expense appears with food category
4. Send message: `summary`
5. Verify summary shows the ৳50 lunch expense

**Expected Results**:
- Expense logged successfully with amount, category, timestamp
- Summary displays total spent and categorization
- No errors or system failures

---

## UAT-2: AI Coaching Flow
**Objective**: Test coaching system with explicit opt-in

**Test Steps**:
1. Log a few expenses: `spent 30 on coffee`, `spent 200 on groceries`, `spent 15 on transport`
2. Send message: `summary` 
3. Verify normal summary response (no coaching)
4. Send message: `insight`
5. Verify coaching starts with topic suggestions
6. Respond with one of the suggested topics (e.g., `transport`)
7. Follow coaching conversation to completion

**Expected Results**:
- Summary works normally without coaching interference
- Coaching only starts with explicit "insight" keyword
- Coaching provides relevant financial advice
- Session flows naturally and ends appropriately

---

## UAT-3: Correction Functionality
**Objective**: Test smart corrections system

**Test Steps**:
1. Send message: `spent 100 on dinner`
2. Verify expense logged correctly
3. Send correction: `sorry I meant 150`
4. Verify original expense marked as corrected
5. Check new expense created with ৳150
6. Send message: `summary`
7. Verify summary shows corrected amount, not original

**Expected Results**:
- Original expense superseded (not deleted)
- New expense created with correct amount
- Summary reflects corrected data
- Clear confirmation of correction applied

---

## UAT-4: Multi-Currency & Categories
**Objective**: Test currency detection and category inference

**Test Steps**:
1. Send message: `spent $25 on books`
2. Verify currency conversion or handling
3. Send message: `spent 300 taka on medicine`
4. Check medical/health category assignment
5. Send message: `spent 500 on uber`
6. Verify transport category
7. Request summary to see all categories

**Expected Results**:
- Proper currency handling and display
- Accurate category inference
- Clean summary with category breakdown

---

## UAT-5: Edge Cases & Error Handling
**Objective**: Test system resilience with unusual inputs

**Test Steps**:
1. Send unclear message: `money stuff happened`
2. Verify helpful response, no errors
3. Send partial info: `spent money`
4. Check system asks for clarification or provides guidance
5. Send very long message with expense info embedded
6. Verify expense extracted correctly
7. Send message: `undo` or similar
8. Check undo functionality works

**Expected Results**:
- Graceful handling of unclear inputs
- Helpful guidance for incomplete information
- Robust parsing of complex messages
- Proper undo/correction mechanisms

---

## UAT-6: Session Continuity
**Objective**: Test system memory and session handling

**Test Steps**:
1. Log expense: `spent 75 on gas`
2. Wait 2-3 minutes
3. Send follow-up: `actually it was premium gas`
4. Check if context maintained
5. Send message: `summary`
6. Verify all expenses tracked correctly across time
7. Test coaching session: say `insight` and then stop responding
8. Later, try `insight` again to verify clean state

**Expected Results**:
- Context preserved appropriately
- Session timeouts handled gracefully
- No memory leaks or stuck states
- Fresh coaching sessions start cleanly

---

## Acceptance Criteria

### ✅ Core Functionality
- [ ] Expense logging works reliably
- [ ] Category inference is accurate
- [ ] Summary generation is correct
- [ ] Currency handling is proper

### ✅ AI Features
- [ ] Coaching only starts with "insight" keyword
- [ ] Protected intents (summary/log) never trigger coaching
- [ ] Coaching provides relevant advice
- [ ] Error handling preserves normal functionality

### ✅ Safety & Reliability
- [ ] No system crashes or errors
- [ ] Graceful handling of edge cases
- [ ] Data integrity maintained
- [ ] User experience is smooth and intuitive

### ✅ Performance
- [ ] Responses arrive within 2-3 seconds
- [ ] No noticeable delays or timeouts
- [ ] System handles rapid message sequences

---

## Notes for KC
- Test each scenario in order for best results
- Feel free to use realistic amounts and merchants
- Report any unexpected behavior or confusing responses
- The system should feel natural and helpful throughout
- If anything breaks, normal expense logging should still work