# replit.md

## Overview

FinBrain is a Facebook Messenger expense tracking application that processes expense messages through Facebook Messenger. The system uses AI-powered categorization to automatically classify expenses into 10 predefined categories, extracts amounts using regex patterns, and stores all data securely in a PostgreSQL database. Users can send expense messages in natural language, and the system responds with confirmation and monthly totals. The application includes a web dashboard for viewing expense statistics and automated reporting capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
- **Flask** serves as the core web framework with SQLAlchemy ORM for database operations
- **Fast webhook** at `/webhook/messenger` with signature verification, deduplication, and async processing (<300ms response)
- **Dashboard endpoint** at `/` provides a web interface for viewing expense statistics
- **Health check endpoint** for monitoring application status

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
- **No authentication middleware** - MVP uses PSID without login/session management
- **Environment variable** configuration for all sensitive credentials
- **Rate limiting** with daily and hourly message limits per user

### Message Processing Pipeline
- **Amount extraction** using regex patterns supporting multiple currencies
- **Smart categorization** into 10 categories (Food, Transport, Shopping, Groceries, Utilities, Entertainment, Health, Education, Personal Care, Misc) using keyword matching
- **Duplicate prevention** using unique message IDs
- **Real-time response** with expense confirmation and monthly totals

### Facebook Messenger Integration
- **Facebook Messenger Platform** via Graph API v17.0 with JSON message processing
- **Platform-specific handler** in facebook_handler.py utility module
- **Unified expense processing** for all messages

### Background Processing
- **APScheduler** for automated daily and weekly reports
- **Cron-based triggers** for scheduled report generation
- **Background task execution** without blocking main application

### Modular Architecture
- **Utils package** with specialized modules:
  - `expense.py`: Core parsing and processing logic
  - `categories.py`: Categorization system with keywords
  - `security.py`: Hashing and validation functions
  - `db.py`: Database operations and connection utilities
  - `rate_limiter.py`: Message rate limiting functionality
  - `facebook_handler.py`: Facebook Messenger messaging
  - `webhook_processor.py`: Fast webhook processing with signature verification and async handling
  - `report_generator.py`: Automated report creation
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
Core deployment secrets:
- `DATABASE_URL`: PostgreSQL connection string
- `FACEBOOK_PAGE_ACCESS_TOKEN`: Facebook Messenger API access
- `FACEBOOK_VERIFY_TOKEN`: Webhook verification token
- `ADMIN_USER`, `ADMIN_PASS`: Dashboard admin credentials
- `SENTRY_DSN`: Optional error monitoring

Application configuration:
- `SESSION_SECRET`: Flask session security
- `DAILY_MESSAGE_LIMIT`, `HOURLY_MESSAGE_LIMIT`: Rate limiting configuration