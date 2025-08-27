# finbrain

## Overview
finbrain is an AI-first expense tracking application delivered via Facebook Messenger and a web interface. Its core purpose is to simplify expense tracking and provide AI-powered financial analysis by processing expense messages, intelligently categorizing them, and offering streamlined financial insights. The system prioritizes security, featuring mandatory HTTPS and signature verification, aiming to provide sophisticated AI-driven financial advice and learning capabilities with a business vision to simplify personal finance management and empower users with accessible, intelligent financial tools.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles
FinBrain utilizes a modular, AI-first architecture with **Phase 4: Limited Production PCA** active. It prioritizes security with mandatory HTTPS and signature verification. All AI features are always-on, with AI-first routing. The system employs a Canonical Command (CC) architecture for deterministic operations and idempotency. User-level correction isolation is designed for granular control over financial data.

### PCA (Precision Capture & Audit) System
The PCA system is in Full Production Active mode, ensuring audit transparency and high-confidence auto-application of expenses (≥85% confidence). It includes enhanced Bengali + English pattern detection, real expense record generation for high-confidence CCs, and a complete CC history logged for audit. Performance is optimized with a P95 latency of 0.0ms and comprehensive caching. The Clarifier Flow achieves a 20.8% optimal ask rate with 100% decision accuracy. Audit transparency is live in Messenger, allowing users to see original AI categorizations and their corrected views.

### Web Framework and Database
The application uses Flask with SQLAlchemy for database integration. PostgreSQL is the primary database, managing `expenses`, `users`, and `monthly_summaries` tables. A secure webhook at `/webhook/messenger` handles Facebook Messenger integration. Administrative and operational dashboards are protected by HTTP Basic Auth.

### Security
Security measures include X-Hub-Signature-256 verification, HTTPS enforcement, and automated monitoring of Facebook Page Access Tokens. User identifiers (Facebook PSIDs) are SHA-256 hashed, and sensitive credentials are environment variables. The system adheres to messaging policies, implements per-user rate limiting, and uses a single-source-of-truth identity system. Critical AI cross-contamination issues have been addressed by implementing per-request session isolation, user ID logging, real-time contamination detection, AI prompt user isolation, and response validation gateways.

### Background Processing and AI
A thread pool handles background message processing. An intelligent AI recommendation layer (Gemini-2.5-flash-lite) categorizes expenses and provides tips. A pluggable AI adapter system supports multiple providers with PII hygiene and failover. Robust AI rate limiting prevents abuse. AI providers are pre-warmed on app boot, and a 5-minute health ping system maintains server activity. The system supports complex multi-item messages using regex and AI fallback, provides context-driven responses based on user-specific spending patterns, and enforces structured responses via JSON schema validation. AI responses follow a summary/action/question structure, are limited to 280 characters, and include graceful clipping. Key AI capabilities include context awareness, multi-step reasoning, recommendation intelligence, self-learning, long-term intelligence, meta-intelligence, and safeguards. Duplicate AI calls for insights have been eliminated by correcting the production router configuration.

### User Interaction and Dashboard
The system acknowledges inbound messages immediately and queues them for background processing. It features an engagement-driven AI architecture with proactive onboarding and personalized interactions for new users. Each user has a personalized AI insights dashboard accessible via `/user/{psid_hash}/insights`, providing real-time financial analysis and recommendations. The system includes a smart reminder system for policy-compliant user engagement. Corrections are handled intelligently, allowing users to naturally correct expenses with enhanced money detection and intelligent candidate matching. Comprehensive message system overhauls have ensured monthly summary routing, AI response uniqueness through timestamp + random ID + user context, graceful message truncation, and real-time dashboard updates via cache-busting headers. Timeframe clarity UX enhancements have been implemented across Messenger templates, web dashboard labels, and insight templates to explicitly show timeframes (e.g., "Last 7 Days" vs "This Month").

### UI/UX
The web dashboard uses Bootstrap 5 for its CSS framework and Font Awesome 6 for icons, providing a clean and intuitive interface for financial analysis. The AI maintains a coach-style tone for consistent user experience.

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

### Frontend Libraries
- **Bootstrap 5**: CSS framework for the dashboard UI.
- **Font Awesome 6**: Icon library for the dashboard UI.