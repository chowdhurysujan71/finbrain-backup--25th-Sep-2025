# Data Integrity & Audit Trail Specification

**Generated:** 2025-09-08  
**Purpose:** Phase E audit system design for expense corrections and data integrity

## Core Requirements

### 1. Expense Correction System
- **"Edit Last Expense"** functionality for user corrections
- **No Duplicate Creation** - corrections update existing records
- **Complete Audit Trail** - all changes tracked with metadata
- **Idempotent Operations** - repeated edits with same data create no new audit entries

### 2. Audit Trail Schema

#### Primary Tables

**expenses** (existing)
```sql
id (Primary Key)
user_id_hash (Foreign Key to users)
amount (Decimal)
category (String)
description (String) 
created_at (DateTime)
updated_at (DateTime)
```

**expense_edits** (new audit table)
```sql
id (Primary Key) 
expense_id (Foreign Key to expenses.id)
editor_user_id (Foreign Key to users.user_id_hash)
edited_at (DateTime UTC)
old_amount (Decimal, nullable)
old_category (String, nullable) 
old_memo (Text, nullable)
new_amount (Decimal, nullable)
new_category (String, nullable)
new_memo (Text, nullable)
reason (Text, optional)
edit_type (ENUM: 'amount', 'category', 'description', 'full_edit')
checksum_before (String) -- Hash of record state before edit
checksum_after (String) -- Hash of record state after edit
```

#### Audit Metadata
```sql
audit_session_id (UUID) -- Groups related edits
client_info (JSON) -- Browser, IP (hashed), timestamp
confidence_score (Float) -- AI confidence when edit was made
source (ENUM: 'manual_form', 'nl_correction', 'bulk_import')
```

### 3. Idempotency Implementation

#### Duplicate Detection Logic
```python
def is_duplicate_edit(expense_id, new_data, time_window_minutes=5):
    """
    Check if this edit is a duplicate of recent edit attempt
    """
    recent_edit = get_last_edit(expense_id, within_minutes=time_window_minutes)
    
    if recent_edit and (
        recent_edit.new_amount == new_data.amount and
        recent_edit.new_category == new_data.category and  
        recent_edit.new_memo == new_data.description
    ):
        return True # Duplicate - skip audit entry
    return False
```

#### Edit Operation Flow
1. **Load Current State** - Get existing expense record
2. **Calculate Checksum** - Hash current state for integrity verification
3. **Duplicate Check** - Verify this isn't a duplicate edit attempt  
4. **Apply Changes** - Update expense record with new values
5. **Create Audit Entry** - Log the change with before/after state
6. **Verify Integrity** - Confirm checksum matches expectations

### 4. "Edit Last Expense" Feature

#### User Interface Flow
```
1. User clicks "Edit Last Expense" (appears after successful expense logging)
2. System shows pre-filled form with current expense details
3. User modifies amount/category/description  
4. System validates changes and shows confirmation
5. On confirm, system applies edit with audit trail
6. User sees updated expense in list with "Edited" indicator
```

#### Backend Implementation
```python
@app.route('/edit-last-expense', methods=['POST'])
def edit_last_expense():
    user_id = get_current_user_id()
    
    # Get user's most recent expense
    last_expense = get_user_last_expense(user_id)
    if not last_expense:
        return error("No recent expense found")
    
    # Extract new values from form
    new_amount = request.form.get('amount')
    new_category = request.form.get('category') 
    new_description = request.form.get('description')
    
    # Check for duplicates (idempotency)
    if is_duplicate_edit(last_expense.id, new_data):
        return success("No changes needed") # Don't create audit entry
        
    # Apply edit with audit trail
    result = apply_expense_edit(
        expense_id=last_expense.id,
        old_state=last_expense,
        new_values={'amount': new_amount, 'category': new_category, 'description': new_description},
        editor_user_id=user_id,
        reason=request.form.get('reason', 'User correction')
    )
    
    return success("Expense updated successfully")
```

### 5. Data Integrity Validation

#### Integrity Checks
1. **Checksum Verification** - Before/after state hashes must be consistent
2. **User Authorization** - Only expense owner can edit their expenses  
3. **Temporal Validation** - Edits must be within reasonable time window (24h default)
4. **Amount Validation** - New amounts must be positive, reasonable limits
5. **Category Validation** - New categories must be from allowed set

#### Automatic Rollback Triggers
- **Checksum Mismatch** - Indicates data corruption, auto-rollback
- **Constraint Violations** - Foreign key or data type errors
- **Concurrent Edit Detection** - Multiple users editing same record
- **Audit Chain Break** - Missing or corrupted audit entries

### 6. Correction UI Integration

#### Form Enhancement for NL Corrections
```html
<!-- Enhanced expense form with correction capability -->
<form id="expense-form" hx-post="/expense">
    <!-- Standard fields: amount, category, description -->
    
    <!-- Correction context (hidden unless correcting) -->
    <input type="hidden" id="correction-mode" name="correction_mode" value="false">
    <input type="hidden" id="original-expense-id" name="original_expense_id">
    
    <!-- AI confidence display (for NL entries) -->
    <div id="confidence-indicator" style="display: none;">
        <span class="confidence-score">AI Confidence: <strong id="confidence-value">--</strong></span>
        <button type="button" id="manual-verify-btn">Verify Details</button>
    </div>
    
    <!-- Correction reason (for audit trail) -->
    <div id="correction-reason" style="display: none;">
        <label for="edit-reason">Reason for correction (optional):</label>
        <input type="text" id="edit-reason" name="reason" placeholder="e.g., Wrong amount, Different category">
    </div>
</form>
```

#### Category Clarification Chips
```html
<!-- Triggered when AI confidence <0.6 for category -->
<div id="category-clarification" class="clarification-section" style="display: none;">
    <h4>Help us categorize this expense:</h4>
    <p class="detected-amount">Amount: <strong id="detected-amount">৳--</strong></p>
    <p class="detected-text">For: "<span id="detected-description">--</span>"</p>
    
    <div class="category-chips">
        <button type="button" class="category-chip" data-category="food">🍽️ Food</button>
        <button type="button" class="category-chip" data-category="transport">🚗 Transport</button>
        <button type="button" class="category-chip" data-category="shopping">🛍️ Shopping</button>
        <button type="button" class="category-chip" data-category="bills">💡 Bills</button>
        <button type="button" class="category-chip" data-category="other">📝 Other</button>
    </div>
    
    <button type="button" id="confirm-clarification" class="btn btn-primary">Confirm & Save</button>
</div>
```

### 7. Performance Considerations

#### Database Indexing
```sql
-- Optimize audit trail queries
CREATE INDEX idx_expense_edits_expense_id ON expense_edits(expense_id);
CREATE INDEX idx_expense_edits_editor_user ON expense_edits(editor_user_id);
CREATE INDEX idx_expense_edits_edited_at ON expense_edits(edited_at);

-- Optimize "last expense" queries  
CREATE INDEX idx_expenses_user_created ON expenses(user_id_hash, created_at DESC);
```

#### Audit Retention Policy
- **Active Audits**: Keep all edits for current month
- **Historical Audits**: Compress edits older than 6 months
- **Critical Audits**: Permanent retention for significant changes (>1000 taka)
- **Cleanup Schedule**: Monthly automated cleanup of expired audit data

### 8. Testing & Validation

#### Test Scenarios
1. **Basic Edit**: Simple amount/category change on recent expense
2. **Idempotency**: Repeated identical edits should not create duplicate audit entries  
3. **Concurrent Edits**: Multiple edit attempts on same expense
4. **Edge Cases**: Edit expense created via NL parsing vs manual form
5. **Audit Chain**: Verify complete audit trail for multiple edits on same expense
6. **Data Recovery**: Restore expense to previous state using audit trail

#### Acceptance Criteria
- ✅ **No Duplicate Expenses**: Corrections update existing records, never create new ones
- ✅ **Complete Audit Trail**: Every change tracked with full before/after state
- ✅ **Idempotent Operations**: Repeated identical edits don't generate multiple audit entries
- ✅ **Performance**: Edit operations complete in <200ms
- ✅ **Data Integrity**: All audit checksums validate correctly
- ✅ **User Experience**: Clear feedback on edit success/failure

### 9. Security Considerations

#### Access Control
- **User Isolation**: Users can only edit their own expenses
- **Admin Oversight**: Admins can view audit trails but not modify them
- **API Security**: Edit endpoints require authentication + CSRF protection
- **Audit Immutability**: Audit records cannot be deleted or modified once created

#### Privacy Protection  
- **IP Address Hashing**: Store hashed IP addresses in audit metadata
- **Sensitive Data**: Never log sensitive personal information in audit reasons
- **Data Minimization**: Only store necessary fields for audit purposes
- **Retention Limits**: Automatic cleanup of old audit data per retention policy

---

**Implementation Priority:**
1. Core audit table schema and basic edit functionality
2. Idempotency logic and duplicate detection
3. "Edit Last Expense" UI integration
4. Category clarification flow for low-confidence NL parsing
5. Performance optimization and comprehensive testing