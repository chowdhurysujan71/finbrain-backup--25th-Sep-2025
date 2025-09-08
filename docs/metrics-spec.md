# Phase F - Growth Telemetry Specification

## Overview
FinBrain growth telemetry system tracks user engagement and retention metrics to understand product adoption and user behavior patterns.

## Core Metrics Definitions

### Daily Active Users (DAU)
**Definition:** Users with ≥1 successful `expense_logged` event on a given day (UTC timezone)

**Calculation:**
- Count unique `user_id` values from `expense_logged` events in the current UTC day
- Only successful expense logging events count toward DAU
- Time range: 00:00:00 UTC to 23:59:59 UTC

### 7-Day Active Users  
**Definition:** Users with ≥1 successful `expense_logged` event in the last 7 days (UTC timezone)

**Calculation:**
- Count unique `user_id` values from `expense_logged` events in the last 7 complete UTC days
- Rolling 7-day window updated daily

### User Retention (D1/D3)
**Definition:** Percentage of new users returning to log expenses on Day 1 and Day 3 after signup

**Calculation Logic:**
- **Signup Day (D0):** First recorded `expense_logged` event for a user
- **D1 Retention:** % of D0 users who have ≥1 `expense_logged` event exactly 1 day after D0
- **D3 Retention:** % of D0 users who have ≥1 `expense_logged` event exactly 3 days after D0
- **Cohort Tracking:** Calculate for the last 7 cohorts (users who signed up in the last 7 days)

## Running Totals (Counters)

### total_expenses
**Definition:** Total count of all successfully logged expenses across all users and time

**Increment Trigger:** Each successful `expense_logged` event

### total_reports  
**Definition:** Total count of all financial reports generated across all users and time

**Increment Trigger:** Each `report_requested` event

### challenges_started
**Definition:** Total count of financial challenges or goals initiated by users

**Increment Trigger:** Each challenge creation event (future feature)

## Event Mapping

### expense_logged
**Description:** User successfully logs an expense entry

**Schema:**
```json
{
  "event": "expense_logged",
  "user_id": "string (user identifier hash)",
  "amount": "float (expense amount)",
  "category": "string (expense category)",
  "timestamp": "ISO 8601 UTC timestamp", 
  "source": "string (form|messenger|api)"
}
```

**Trigger Conditions:**
- Expense successfully saved to database
- Amount > 0
- Valid category assigned
- User authenticated/identified

### expense_edited
**Description:** User modifies an existing expense entry

**Schema:**
```json
{
  "event": "expense_edited",
  "user_id": "string (user identifier hash)",
  "expense_id": "integer (expense database ID)",
  "timestamp": "ISO 8601 UTC timestamp"
}
```

**Trigger Conditions:**
- Expense edit successfully saved
- Audit trail record created
- User owns the expense being edited

### report_requested  
**Description:** User generates or views a financial report

**Schema:**
```json
{
  "event": "report_requested", 
  "user_id": "string (user identifier hash)",
  "report_type": "string (monthly|weekly|category|insights)",
  "timestamp": "ISO 8601 UTC timestamp"
}
```

**Trigger Conditions:**
- Report successfully generated
- User has access to the report
- Report contains valid data

### install_pwa
**Description:** User installs the Progressive Web App

**Schema:** 
```json
{
  "event": "install_pwa",
  "user_id": "string (user identifier hash or anonymous ID)", 
  "timestamp": "ISO 8601 UTC timestamp"
}
```

**Trigger Conditions:**
- PWA installation event detected
- Browser supports PWA installation
- User completes installation process

## Data Storage

### Telemetry Events Table
```sql
CREATE TABLE telemetry_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id_hash VARCHAR(64),
    event_data JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_telemetry_events_type_time ON telemetry_events(event_type, timestamp);
CREATE INDEX idx_telemetry_events_user_time ON telemetry_events(user_id_hash, timestamp);
```

### Running Counters Table
```sql  
CREATE TABLE growth_counters (
    id SERIAL PRIMARY KEY,
    counter_name VARCHAR(50) UNIQUE NOT NULL,
    counter_value BIGINT DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO growth_counters (counter_name, counter_value) VALUES 
    ('total_expenses', 0),
    ('total_reports', 0), 
    ('challenges_started', 0);
```

## API Endpoints

### GET /metrics
**Description:** Human-readable metrics endpoint for monitoring

**Response Format:**
```
FinBrain Growth Metrics
======================
Generated: 2025-09-08 08:10:00 UTC

Daily Active Users (DAU)
- Today: 142 users
- 7-day: 1,247 users

User Retention (Last 7 Cohorts)
Cohort    | D0 Users | D1 Retention | D3 Retention
2025-09-07|    18    |    61.1%     |    33.3%
2025-09-06|    23    |    56.5%     |    39.1%
2025-09-05|    15    |    66.7%     |    46.7%
2025-09-04|    31    |    48.4%     |    32.3%
2025-09-03|    27    |    59.3%     |    37.0%
2025-09-02|    19    |    63.2%     |    42.1%
2025-09-01|    22    |    54.5%     |    36.4%

Running Totals
- Total Expenses: 15,847
- Total Reports: 2,156  
- Challenges Started: 456
```

### GET /admin/metrics
**Description:** Admin dashboard with same metrics in web interface

**Features:**
- Same numerical data as /metrics endpoint
- Bootstrap-styled tables and cards
- Auto-refresh every 5 minutes
- Export functionality for data analysis

## Implementation Notes

### Timezone Handling
- All timestamps stored in UTC
- DAU calculations use UTC day boundaries
- Retention calculations account for UTC date changes

### Performance Considerations  
- Telemetry events table will grow large - implement partitioning by month
- Running counters updated via database triggers for performance
- Cache expensive retention calculations for 1 hour

### Privacy & Security
- User IDs are hashed before storage in telemetry
- No personally identifiable information in event data
- Aggregate metrics only, no individual user tracking exposed

### Data Retention
- Keep telemetry events for 13 months (rolling window)
- Archive older data for compliance
- Running counters maintained indefinitely

## Success Criteria

1. ✅ **Accurate DAU Tracking:** Real-time DAU count updates within 1 minute of expense logging
2. ✅ **Retention Calculation:** D1/D3 retention percentages calculated correctly for cohorts
3. ✅ **Performance:** /metrics endpoint responds within 500ms
4. ✅ **Data Integrity:** Running counters match actual event counts
5. ✅ **Monitoring Ready:** Human-readable format suitable for dashboards and alerts