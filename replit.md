# replit.md

## Overview

FinBrain is a Facebook Messenger expense tracking application that processes expense messages through Facebook Messenger. The system uses AI-powered categorization to automatically classify expenses into 10 predefined categories, extracts amounts using regex patterns, and stores all data securely in a PostgreSQL database. Users can send expense messages in natural language, and the system responds with confirmation and monthly totals. The application includes a web dashboard for viewing expense statistics and automated reporting capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
- **Flask** serves as the core web framework with SQLAlchemy ORM for database operations
- **Fast webhook** at `/webhook/messenger` with signature verification, deduplication, and async processing (<300ms response)
- **Private dashboard** at `/` protected by HTTP Basic Auth (ADMIN_USER/ADMIN_PASS)
- **Enhanced health endpoint** at `/health` with uptime_s, queue_depth, ai_status, and cold-start mitigation status
- **Ops monitoring** at `/ops` for operational metrics (Basic Auth required)
- **PSID explorer** at `/psid/<hash>` for read-only user investigation (Basic Auth required)

### Database Design
- **PostgreSQL** primary database with three core tables:
  - `expenses`: Detailed expense logs with user_id, amount, category, date/time, and platform
  - `users`: User profiles with hashed IDs, total expenses, and rate limiting counters
  - `monthly_summaries`: Aggregated analytics and insights
- **SQLAlchemy ORM** with DeclarativeBase for database models and migrations
- **Connection pooling** with pool recycling and pre-ping for reliability

### Security Architecture
- **SHA-256 hashing** for all user identifiers (Facebook PSIDs)
- **PSID-based identity** - uses Facebook Page-Scoped IDs as primary user identifier
- **No raw personal data** stored in database
- **HTTP Basic Auth** protects admin dashboard and ops endpoints (ADMIN_USER/ADMIN_PASS)
- **24-hour messaging policy** compliance with last_user_message_at tracking
- **Environment variable** configuration for all sensitive credentials
- **Rate limiting** with daily and hourly message limits per user

### Cold-Start Mitigation System
- **Pre-warm AI providers** on app boot with DNS resolution and status endpoint pings
- **Enhanced /health endpoint** includes uptime_s, queue_depth, ai_status for comprehensive monitoring
- **5-minute health ping system** keeps server warm to prevent cold starts (HEALTH_PING_ENABLED)
- **AI provider warm-up** via HEAD/GET requests to status URLs using shared sessions

### Background Processing System
- **Thread pool execution** with 3 worker threads for safe background message processing
- **5-second timeout protection** with automatic fallback replies ("Got it. Try 'summary' for a quick recap.")
- **AI adapter framework** with failover support (AI_ENABLED=false for MVP, falls back to regex routing)
- **Keep-alive HTTP sessions** for external API calls with connection pooling
- **Comprehensive error handling** with Flask app context management and graceful degradation

### Message Processing Pipeline  
- **Background job queue** processes {rid, psid, mid, text} after immediate webhook response (<1ms)
- **MVP Regex Router** with three intent patterns:
  - `^log (\d+) (.*)$`: Store expense with amount and note
  - `^summary$`: Generate 7-day category breakdown with actionable tip
  - Default: Show help with usage examples
- **AI failover logic**: If AI_ENABLED=true, try AI adapter first, then regex on failover:true
- **Simple categorization** into 5 categories (food, ride, bill, grocery, other) using keyword matching
- **Duplicate prevention** using unique message IDs
- **Response limits** ≤ 280 characters for all replies

### Facebook Messenger Integration
- **Facebook Messenger Platform** via Graph API v17.0 with JSON message processing
- **Platform-specific handler** in facebook_handler.py utility module
- **Unified expense processing** for all messages

### Background Processing
- **ThreadPoolExecutor** with 3 worker threads for safe message processing
- **Job queue system** with {rid, psid, mid, text} payload structure
- **5-second timeout cap** with fallback reply system for processing protection
- **AI adapter support** with failover to regex routing (AI_ENABLED environment flag)
- **APScheduler** for background task scheduling (reports disabled for MVP)
- **24-hour policy compliance** - no scheduled outbound messages
- **Flask app context** management for database operations in background threads

### Modular Architecture
- **Utils package** with specialized modules:
  - `expense.py`: Core parsing and processing logic
  - `categories.py`: Categorization system with keywords
  - `security.py`: Hashing and validation functions
  - `db.py`: Database operations and connection utilities
  - `rate_limiter.py`: Message rate limiting functionality
  - `facebook_handler.py`: Facebook Messenger messaging
  - `webhook_processor.py`: Fast webhook processing with signature verification and background job queuing
  - `background_processor.py`: Thread pool-based background execution with AI adapter and timeout protection
  - `cold_start_mitigation.py`: Pre-warm AI providers and DNS resolution to prevent cold starts
  - `health_ping.py`: 5-minute health ping system to keep server warm
  - `mvp_router.py`: Regex-based intent matching with lightweight job processing
  - `policy_guard.py`: 24-hour messaging window compliance
  - `report_generator.py`: Report creation (scheduled reports disabled for MVP)
  - `scheduler.py`: Background task scheduling

## External Dependencies

### Messaging Platform
- **Facebook Graph API v17.0**: Messenger platform integration, PSID handling

### Database
- **PostgreSQL**: Primary data storage with psycopg2-binary driver
- **SQLAlchemy**: ORM with connection pooling and migration support

### Task Scheduling
- **APScheduler**: Background task execution for automated reports

### Security & Validation
- **hashlib**: SHA-256 user identifier hashing
- **regex (re)**: Amount extraction and message parsing

### Web Framework
- **Flask**: Core web server with template rendering
- **Gunicorn**: WSGI server for production deployment
- **ProxyFix**: Reverse proxy header handling

### Frontend
- **Bootstrap 5**: Dark theme CSS framework
- **Font Awesome 6**: Icon library for dashboard UI

### Environment Configuration
**Strict boot validation enforced - application refuses to start if any required environment variable is missing.**

Required deployment secrets (no fallbacks):
- `DATABASE_URL`: PostgreSQL connection string
- `ADMIN_USER`, `ADMIN_PASS`: HTTP Basic Auth for dashboard and ops endpoints  
- `FACEBOOK_PAGE_ACCESS_TOKEN`: Facebook Messenger API access
- `FACEBOOK_VERIFY_TOKEN`: Webhook verification token

Optional configuration:
- `SENTRY_DSN`: Error monitoring (if used)
- `SESSION_SECRET`: Flask session security (auto-generated if not provided)
- `DAILY_MESSAGE_LIMIT`, `HOURLY_MESSAGE_LIMIT`: Rate limiting configuration (defaults applied)
- `AI_ENABLED`: Enable AI processing adapter (default: false, uses regex fallback)
- `AI_PROVIDER_URL`: AI provider endpoint for warm-up (default: https://api.openai.com)
- `HEALTH_PING_ENABLED`: Enable 5-minute health pings to prevent cold starts (default: true)
- `ENV=production`: Enables production mode (INFO level logging, structured JSON output)

### Production Logging
**Structured JSON logging implemented for complete observability with zero PII exposure:**

**Request Tracking**: Every inbound request logged with unique request ID (rid), route, method, duration, status code
**Graph API Calls**: Every Facebook API call logged with endpoint, status, duration, tied to request context  
**Webhook Processing**: Message processing with psid_hash (SHA-256), intent detection, category/amount extraction
**No PII Policy**: All PSIDs hashed, no message content logged, only metadata and performance metrics

Production deployment command: `ENV=production gunicorn --bind 0.0.0.0:5000 --reuse-port main:app` (no --reload flag)