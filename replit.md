# FinBrain replit.md

## Overview
FinBrain is a production-ready Facebook Messenger expense tracking application with an AI-first architecture. It processes expense messages via webhooks, providing intelligent AI categorization while ensuring deterministic core functionality. The system emphasizes robust security, including mandatory HTTPS and signature verification. Its primary purpose is to offer streamlined expense tracking and financial insights directly through Messenger.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
FinBrain uses Flask as its core web framework, integrating with SQLAlchemy for database operations. It features a production-hardened webhook at `/webhook/messenger` with mandatory signature verification and HTTPS enforcement for secure and asynchronous processing. Administrative and operational dashboards are protected by HTTP Basic Auth, including endpoints for health checks, token monitoring, PSID exploration, and version tracking.

### Database Design
The primary database is PostgreSQL, structured with `expenses` for detailed logs, `users` for profiles and rate limiting, and `monthly_summaries` for aggregated analytics. SQLAlchemy ORM manages database models, incorporating connection pooling for reliability.

### Security Architecture
Security is paramount, with mandatory X-Hub-Signature-256 verification for Facebook webhooks, HTTPS enforcement, and automated monitoring of Facebook Page Access Tokens. User identifiers (Facebook PSIDs) are SHA-256 hashed, and no raw personal data is stored. All sensitive credentials are configured via environment variables, and the system adheres to the 24-hour messaging policy and implements rate limiting per user.

### Cold-Start Mitigation System
To ensure responsiveness, AI providers are pre-warmed on app boot. A 5-minute health ping system keeps the server active, and the `/health` endpoint offers comprehensive monitoring of uptime, queue depth, and AI status.

### Background Processing System
A thread pool with three worker threads handles background message processing, ensuring non-blocking webhook responses. It includes a 5-second timeout with automatic fallback replies. An intelligent AI recommendation layer, utilizing Gemini-2.5-flash-lite, categorizes expenses and offers personalized tips. A pluggable AI adapter system supports multiple providers with PII hygiene and failover mechanisms. A robust AI rate limiting system prevents abuse without blocking request threads.

### Message Processing Pipeline
Inbound messages are immediately acknowledged by the webhook and then queued for background processing. An RL-2 Graceful Non-AI Fallback System ensures deterministic processing for rate-limited scenarios, providing ASCII-safe, concise replies. When AI is available, it categorizes expenses into categories like food, ride, bill, grocery, and other. The system includes logic for AI failover to regex-based routing and duplicate prevention. All responses are limited to 280 characters.

### Facebook Messenger Integration
The system integrates with the Facebook Messenger Platform via Graph API v17.0, using `facebook_handler.py` for platform-specific interactions and unified expense processing.

### Modular Architecture
The codebase is highly modular, organized into a `utils` package containing specialized modules for expense parsing, categorization, security, database operations, rate limiting, Facebook messaging, webhook processing, background execution, AI adaptation, cold-start mitigation, health pings, routing, policy guarding, report generation, and scheduling.

## External Dependencies

### Messaging Platform
- **Facebook Graph API v17.0**: For Messenger platform integration and PSID handling.

### Database
- **PostgreSQL**: Primary data storage.
- **SQLAlchemy**: ORM for database interactions.

### Task Scheduling
- **APScheduler**: For background task execution (reports disabled for MVP).

### Security & Validation
- **hashlib**: For SHA-256 hashing of user identifiers.
- **regex (re)**: For amount extraction and message parsing.

### Web Framework
- **Flask**: Core web server.
- **Gunicorn**: WSGI server for production.
- **ProxyFix**: For handling reverse proxy headers.

### Frontend
- **Bootstrap 5**: CSS framework for the dashboard UI.
- **Font Awesome 6**: Icon library for the dashboard UI.

### Environment Configuration
The application enforces strict boot validation, requiring specific environment variables for operation, including `DATABASE_URL`, `ADMIN_USER`, `ADMIN_PASS`, `FACEBOOK_PAGE_ACCESS_TOKEN`, and `FACEBOOK_VERIFY_TOKEN`. Optional configurations include `SENTRY_DSN`, `SESSION_SECRET`, rate limiting parameters, AI enablement, AI provider selection, and production mode settings.