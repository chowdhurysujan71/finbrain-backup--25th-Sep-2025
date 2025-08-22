# FinBrain

## Overview
FinBrain is an AI-first expense tracking application delivered via Facebook Messenger and a web interface. Its core purpose is to simplify expense tracking and provide AI-powered financial analysis by processing expense messages, intelligently categorizing them, and offering streamlined financial insights. The system prioritizes security, featuring mandatory HTTPS and signature verification, aiming to provide sophisticated AI-driven financial advice and learning capabilities.

## User Preferences
Preferred communication style: Simple, everyday language.

## Recent Changes (August 2025)
- **SMART_CORRECTIONS System Completed (Aug 22):** Comprehensive expense correction flow with supersede logic
  - Feature: Natural language correction detection ("sorry, I meant 500", "actually 300 for coffee")
  - Feature: Intelligent candidate matching based on category and merchant similarity within 10-minute window
  - Feature: Supersede logic - original expenses marked as superseded instead of deleted for data integrity
  - Feature: Coach-style confirmations and error handling for all correction scenarios
  - Feature: Feature flag (SMART_CORRECTIONS) defaulting to OFF for zero-downgrade safety deployment
  - Feature: Allowlist-based canary rollout system enabling specific users before global rollout
  - Feature: Comprehensive telemetry and structured logging for correction events
  - Feature: Duplicate correction protection via message ID uniqueness constraints
  - Feature: Backwards-compatible database schema with nullable correction tracking columns
  - Implementation: handlers/expense.py, parsers/expense.py, utils/feature_flags.py, templates/replies.py
  - Integration: Production router detects corrections before regular expense parsing
  - Safety: Idempotent operations, graceful fallbacks, comprehensive test coverage
  - Result: Users can now correct mistakes naturally: "coffee 50" → "sorry, I meant 500"
  - Status: Production ready with comprehensive testing completed, awaiting canary rollout

- **SMART_NLP_ROUTING System Completed (Aug 22):** Comprehensive natural language expense logging system
  - Feature: Enhanced money detection with multi-currency support (৳$£€₹)
  - Feature: Sophisticated parsing with merchant extraction and category inference
  - Feature: Coach-tone replies for consistent UX across STD and AI modes
  - Feature: Feature flags (SMART_NLP_ROUTING) defaulting to OFF for zero-downgrade safety
  - Feature: Allowlist-based canary rollout system for gradual deployment
  - Feature: Comprehensive test suite and dev simulation tools
  - Implementation: finbrain/router.py, parsers/expense.py, utils/feature_flags.py, templates/replies.py
  - Integration: Production router checks feature flags and routes enhanced parsing when enabled
  - Safety: Idempotency protection via (psid_hash, mid) unique constraint
  - Result: System handles natural language like "I spent 300 on lunch in The Wind Lounge today"
  - Status: Production ready - comprehensive testing completed, awaiting canary rollout

- **Previous Critical Fix (Aug 21):** Resolved database constraint violation preventing expense logging
  - Issue: Missing unique_id field causing "Unable to log expense" errors
  - Solution: Added idempotent unique_id generation using Facebook message ID + UUID fallback
  - Result: System now stable and functioning as expected

## System Architecture

### Web Framework and Database
FinBrain utilizes Flask with SQLAlchemy for database integration. The primary database is PostgreSQL, with tables for `expenses`, `users`, and `monthly_summaries`. SQLAlchemy ORM manages models with connection pooling. A secure webhook at `/webhook/messenger` requires signature verification and HTTPS. Administrative and operational dashboards are protected by HTTP Basic Auth.

### Security
Security measures include X-Hub-Signature-256 verification for Facebook webhooks, HTTPS enforcement, and automated monitoring of Facebook Page Access Tokens. User identifiers (Facebook PSIDs) are SHA-256 hashed, and all sensitive credentials are environment variables. The system adheres to messaging policies and implements per-user rate limiting. A single-source-of-truth identity system is implemented to prevent fragmentation.

### Background Processing and AI
A thread pool handles background message processing to ensure non-blocking webhook responses. An intelligent AI recommendation layer (Gemini-2.5-flash-lite) categorizes expenses and provides tips. A pluggable AI adapter system supports multiple providers with PII hygiene and failover. A robust AI rate limiting system prevents abuse. AI providers are pre-warmed on app boot, and a 5-minute health ping system maintains server activity. The system supports complex multi-item messages using regex and AI fallback to extract multiple expenses. The AI provides context-driven responses based on user-specific spending patterns, enforcing structured responses via JSON schema validation. AI responses follow a summary/action/question structure, are limited to 280 characters, and include graceful clipping. Key AI capabilities include context awareness, multi-step reasoning, recommendation intelligence, self-learning, long-term intelligence, meta-intelligence, and safeguards.

### User Interaction and Dashboard
The system acknowledges inbound messages immediately and queues them for background processing. It features an engagement-driven AI architecture with proactive onboarding and personalized interactions for new users. Each user has a personalized AI insights dashboard accessible via `/user/{psid_hash}/insights`, providing real-time financial analysis, recommendations, and spending pattern insights generated by Gemini AI.

### Modular Design
The codebase is modular, organized into a `utils` package containing modules for expense parsing, categorization, security, database operations, rate limiting, Facebook messaging, webhook processing, background execution, AI adaptation, cold-start mitigation, health pings, routing, policy guarding, report generation, and scheduling.

## External Dependencies

### Messaging Platform
- **Facebook Graph API v17.0**: For Messenger platform integration and PSID handling.

### Database
- **PostgreSQL**: Primary data storage.
- **SQLAlchemy**: ORM for database interactions.

### Web Framework
- **Flask**: Core web server.
- **Gunicorn**: WSGI server for production.
- **ProxyFix**: For handling reverse proxy headers.

### Frontend
- **Bootstrap 5**: CSS framework for the dashboard UI.
- **Font Awesome 6**: Icon library for the dashboard UI.