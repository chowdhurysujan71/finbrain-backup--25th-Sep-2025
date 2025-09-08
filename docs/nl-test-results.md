# Natural Language Processing Test Results

**Generated:** 2025-09-08  
**Test Set:** /docs/nl-test-set.csv (110 test cases)  
**Target:** ≥90% PASS rate, <10% fallback rate

## Scoring Methodology

### Evaluation Matrix
For each test case, we evaluate:

| Field | Description | Scoring Criteria |
|-------|-------------|------------------|
| **Intent Recognition** | Did the parser identify this as an expense? | PASS: Correctly identified as expense<br>FAIL: Misclassified or rejected |
| **Amount Extraction** | Accuracy of monetary value parsing | PASS: Exact match or within ±5% for edge cases<br>FAIL: Wrong amount or no amount detected |
| **Category Classification** | Correct expense category assignment | PASS: Exact match or reasonable alternative<br>FAIL: Wrong category or no category |
| **Language Detection** | Correct language identification | PASS: Correctly identified as Bangla/English/Mixed<br>FAIL: Wrong language detection |
| **Confidence Score** | AI confidence level (0.0-1.0) | High: ≥0.8, Medium: 0.6-0.79, Low: <0.6 |
| **Action Taken** | System response to the input | Auto: Direct processing<br>Clarify: Requested clarification<br>Reject: Could not process |

### Overall Result Calculation
- **PASS**: All critical fields (Intent + Amount + Category) correct
- **PARTIAL**: Intent correct, but amount OR category needs clarification
- **FAIL**: Intent wrong or multiple critical errors

### Target Metrics
- **Accuracy Target**: ≥90% PASS + PARTIAL combined
- **Fallback Rate**: <10% requiring clarification
- **False Positive Rate**: <2% non-expenses processed as expenses

## Test Results Summary

*Results will be populated during testing phase*

| Category | Total Cases | PASS | PARTIAL | FAIL | PASS Rate |
|----------|-------------|------|---------|------|-----------|
| Bangla Only (1-40) | 40 | - | - | - | -% |
| English Only (41-80) | 40 | - | - | - | -% |
| Mixed Language (81-100) | 20 | - | - | - | -% |
| Low-Confidence (101-110) | 10 | - | - | - | -% |
| **Overall** | **110** | **-** | **-** | **-** | **-%** |

## Detailed Results

### Test Case Analysis Template
```
Case ID: [1-110]
Input: "[Original text]"
Expected: Amount=[amount], Category=[category], Confidence=[level]
Actual: Amount=[parsed], Category=[assigned], Confidence=[score]
Action: [auto/clarify/reject]
Result: [PASS/PARTIAL/FAIL]
Notes: [Any observations]
```

## Edge Case Performance

### Multiple Amounts (Cases 13, 31, 59, 96-100)
- **Challenge**: Parsing "coffee 120 + bus 40" style inputs
- **Expected Behavior**: Sum amounts, assign mixed/transport category
- **Results**: [To be filled during testing]

### Low-Confidence Cases (Cases 101-110)
- **Challenge**: Deliberately vague inputs like "spent some money"
- **Expected Behavior**: Trigger clarification flow
- **Results**: [To be filled during testing]

### Mixed Language (Cases 81-100)
- **Challenge**: Code-switching between Bangla and English
- **Expected Behavior**: Correct parsing regardless of language mix
- **Results**: [To be filled during testing]

### Bengali Numerals (Throughout Bangla cases)
- **Challenge**: Converting ৫০০, ১২০০ to 500, 1200
- **Expected Behavior**: Accurate numeral conversion
- **Results**: [To be filled during testing]

## Performance Benchmarks

### Latency Requirements
- **Target Response Time**: <500ms per parsing request
- **Batch Processing**: <50ms per item for 10+ items
- **Timeout Handling**: Graceful fallback after 2s

### Accuracy by Category
| Category | Target Accuracy |
|----------|-----------------|
| Food | ≥95% |
| Transport | ≥90% |
| Shopping | ≥85% |
| Bills | ≥95% |
| Health | ≥90% |
| Education | ≥85% |
| Entertainment | ≥80% |
| Other | ≥70% |

## Failure Analysis Framework

### Common Failure Patterns
1. **Amount Extraction Failures**
   - Bengali numeral conversion errors
   - Multiple amount summation issues
   - Currency symbol handling

2. **Category Classification Errors**
   - Ambiguous contexts (e.g., "phone" = bills vs shopping)
   - Cultural context misunderstanding
   - Mixed language category mapping

3. **Language Detection Issues**
   - Mixed language boundary detection
   - Script switching within single expense

### Error Recovery Strategies
- **Amount Errors**: Trigger clarification with detected amounts
- **Category Errors**: Show category selection chips
- **Language Errors**: Use context from user history

## Validation Criteria

**Test PASSES if:**
- Overall accuracy ≥90%
- Fallback rate <10%
- No critical security/data integrity issues
- All edge cases handle gracefully

**Test FAILS if:**
- Overall accuracy <85%
- Fallback rate >15%
- Data corruption or duplicate expense creation
- System crashes or timeouts on edge cases

---

**Next Steps After Testing:**
1. Run full test suite against NL parser
2. Analyze failure patterns
3. Implement clarification flows for common issues
4. Validate audit trail functionality
5. Performance optimization based on results