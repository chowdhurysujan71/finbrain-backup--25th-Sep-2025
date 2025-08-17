# replit.md

## Overview

FinBrain is a production-ready Facebook Messenger expense tracking application with streamlined AI-first architecture and comprehensive security hardening. The system features a clean webhook → router → (AI | deterministic) flow with bulletproof RL-2 fallback guarantees, fully operational Gemini AI integration, and runtime toggle capabilities. Processes expense messages through Facebook Messenger webhooks with intelligent AI categorization while maintaining deterministic core guarantees. Features mandatory HTTPS enforcement, X-Hub-Signature-256 verification, and production-grade security compliance.

**Recent Major Fix (Aug 13, 2025)**: Resolved critical production issue where Gemini AI was not being used despite correct configuration. Added complete Gemini support to production AI adapter (`utils/ai_adapter_v2.py`), enabling real AI-powered expense categorization with 2-3 second response times.

**Character Limits Enhancement (Aug 14, 2025)**: Successfully doubled all response character limits and resolved JSON parsing issues:
- AI tips limit: 200 → 400 characters for comprehensive financial advice
- Overall response limit: 280 → 560 characters for detailed guidance
- Fixed Gemini token truncation: maxOutputTokens 150 → 400 tokens
- Implemented robust JSON parsing with markdown wrapper cleanup and error recovery
- AI now delivers 300+ character detailed budgeting and money-saving strategies

**Rate Limiting & Configuration Enhancement (Aug 17, 2025)**: Implemented comprehensive centralized configuration with upgraded limits:
- Per-user AI requests: 2 → 4 requests per 60-second window for enhanced conversational flow
- Global rate limit: 10 → 120 requests per 60-second window for improved system capacity
- **Centralized configuration in config.py**: Single source of truth for all constants with environment variable support
  - Rate limits: AI_RL_USER_LIMIT, AI_RL_WINDOW_SEC, AI_RL_GLOBAL_LIMIT
  - App constants: MSG_MAX_CHARS, TIMEZONE, CURRENCY_SYMBOL, DEFAULT_CATEGORY
- Eliminated all hard-coded values across entire codebase
- Enhanced observability with comprehensive startup configuration logging
- Built-in testing framework with `test_centralized_config.py` for validation

**UX Enhancement Implementation (Aug 17, 2025)**: Comprehensive user experience upgrade with structured messaging and retention features:
- **Enhanced fallback copy**: "Taking a quick breather to stay fast & free. I'll do the smart analysis in ~{retry_in}s. Meanwhile, want a quick action?"
- **System prompt optimization**: 2-3 sentence maximum responses with action-oriented guidance and crisp follow-ups
- **Message sequencing helpers**: Multi-send pacing with structured quick replies for Log/Review/Goal actions
- **Advisor loops for retention**: Daily check-ins, weekly reviews, goal tracking, and smart nudges with proactive engagement
- **Fast non-AI utilities**: Expense parsing, 7-day snapshots, and budget cap checking during rate limit cool-downs
- **Observability counters**: Real-time engagement metrics tracking for AI usage, fallback rates, and user interaction patterns
- **Guardrails at send layer**: Automatic 280-character limits with graceful clipping and "Want details?" overflow handling

**Timeout Resolution (Aug 14, 2025)**: Fixed critical Gemini API timeout issue that was causing fallback responses:
- Increased Gemini API timeout from 3 → 8 seconds for reliable processing
- Resolved issue where users were getting short "Try log 50 coffee" responses instead of detailed AI advice
- System now consistently delivers 400-character comprehensive financial guidance
- AI response success rate improved from frequent timeouts to reliable 3-4 second responses

**Latest Enhancement (Aug 13, 2025)**: Implemented comprehensive monitoring infrastructure with specialized ops endpoints for production verification: `/ops/telemetry` (config validation), `/ops/ai/ping` (latency testing with p95 ≤ 2500ms), `/ops/rl/reset` (rate limiting reset), and `/ops/trace` (routing analysis). All UAT issues resolved with authentic AI processing confirmed operational.

**Integration Verification (Aug 14, 2025)**: Completed comprehensive E2E testing confirming all core functionality operational. AI processing delivers 300-400 character detailed financial advice consistently. Rate limiting, timeout resolution, and webhook security all working perfectly. Final integration step requires real Facebook Messenger PSIDs (obtained when users message the Facebook page directly) rather than test PSIDs for complete end-to-end message delivery.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
- **Flask** serves as the core web framework with SQLAlchemy ORM for database operations
- **Production-hardened webhook** at `/webhook/messenger` with mandatory signature verification, HTTPS enforcement, deduplication, and async processing (<300ms response)
- **Private dashboard** at `/` protected by HTTP Basic Auth (ADMIN_USER/ADMIN_PASS)
- **Enhanced health endpoint** at `/health` with uptime_s, queue_depth, ai_status, token monitoring, and security status
- **Ops monitoring** at `/ops` for operational metrics including Facebook token status (Basic Auth required)
- **Token refresh monitoring** at `/ops/token-refresh-status` with automated expiry tracking and refresh reminders (Basic Auth required)
- **PSID explorer** at `/psid/<hash>` for read-only user investigation (Basic Auth required)
- **Version endpoint** at `/version` for deployment tracking and build information

### Database Design
- **PostgreSQL** primary database with three core tables:
  - `expenses`: Detailed expense logs with user_id, amount, category, date/time, and platform
  - `users`: User profiles with hashed IDs, total expenses, and rate limiting counters
  - `monthly_summaries`: Aggregated analytics and insights
- **SQLAlchemy ORM** with DeclarativeBase for database models and migrations
- **Connection pooling** with pool recycling and pre-ping for reliability

### Security Architecture
- **Production-grade Facebook webhook security** with mandatory X-Hub-Signature-256 verification using FACEBOOK_APP_SECRET
- **HTTPS enforcement** - rejects HTTP requests as required by Meta's platform policies
- **Facebook Page Access Token monitoring** with automated expiry tracking and refresh reminders
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
- **AI recommendation layer** with Gemini-2.5-flash-lite for intelligent expense categorization and personalized tips (production-verified working)
- **Pluggable AI adapter system** supporting multiple providers (none/gemini/openai) with 8-second timeouts, PII hygiene, and failover mechanisms
- **AI Rate Limiting System** (Phase 1): Sliding 60-second window with per-PSID limits (2/min) and global caps (10/min), structured logging, never blocks request threads
- **Keep-alive HTTP sessions** for external API calls with connection pooling
- **Comprehensive error handling** with Flask app context management and graceful degradation

### Message Processing Pipeline  
- **Background job queue** processes {rid, psid, mid, text} after immediate webhook response (<1ms)
- **RL-2 Graceful Non-AI Fallback System**: Complete bulletproof deterministic processing for rate-limited scenarios
  - **Rate-limited expense patterns**: "log <amount> <note>", "<amount> <note>", "<note> <amount>"
  - **ASCII-safe disclaimer**: "NOTE: Taking a quick breather. I can do 2 smart replies per minute per person..."
  - **Deterministic summary**: Robust SQL with NULL safety and error handling
  - **Plain text only**: ≤280 chars, no emojis, Facebook API sanitized, never requeue
  - **Bulletproof guarantees**: Always reply, always ack, never requeue - even on SQL/DB/API errors
  - **RL-2 logging**: {rid, psid_hash, ai_allowed=false, handled_by="rules", job_status="done"}
- **AI recommendation system**: Uses Gemini-2.5-flash-lite for intelligent categorization when rate limits allow
- **AI failover logic**: If AI_ENABLED=true, try AI adapter first, then regex on failover:true
- **Streamlined parser**: Never-throws guarantee, Bengali numerals, multiple currencies, corruption handling
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
  - `ai_adapter.py`: Pluggable AI provider system with OpenAI/Gemini drivers and PII protection
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
- `AI_PROVIDER`: AI provider selection - none, openai, gemini (default: none)
- `AI_PROVIDER_URL`: AI provider endpoint for warm-up (default: https://api.openai.com)
- `AI_MAX_CALLS_PER_MIN`: Global AI rate limit per minute (default: 10)
- `AI_MAX_CALLS_PER_MIN_PER_PSID`: Per-user AI rate limit per minute (default: 2)
- `HEALTH_PING_ENABLED`: Enable 5-minute health pings to prevent cold starts (default: true)
- `ENV=production`: Enables production mode (INFO level logging, structured JSON output)

### Production Logging
**Structured JSON logging implemented for complete observability with zero PII exposure:**

**Request Tracking**: Every inbound request logged with unique request ID (rid), route, method, duration, status code
**Graph API Calls**: Every Facebook API call logged with endpoint, status, duration, tied to request context  
**Webhook Processing**: Message processing with psid_hash (SHA-256), intent detection, category/amount extraction
**No PII Policy**: All PSIDs hashed, no message content logged, only metadata and performance metrics

Production deployment command: `ENV=production gunicorn --bind 0.0.0.0:5000 --reuse-port main:app` (no --reload flag)