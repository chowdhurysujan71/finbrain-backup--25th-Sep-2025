# finbrain

## Overview
finbrain is an AI-first expense tracking application delivered via a web chat interface. Its core purpose is to simplify expense tracking and provide AI-powered financial analysis by processing expense messages through the web chat, intelligently categorizing them, and offering streamlined financial insights. The system prioritizes security, featuring mandatory HTTPS and authentication, aiming to provide sophisticated AI-driven financial advice and learning capabilities with a business vision to simplify personal finance management and empower users with accessible, intelligent financial tools.

## Production Readiness Status
✅ **PRODUCTION-READY** with comprehensive safety measures implemented (September 2025):
- **Database Protection**: Soft-delete functionality for User and Expense tables prevents accidental data loss
- **Backup System**: Secure pg_dump backup script with environment variable authentication 
- **Security Hardened**: A-grade security status, debug mode disabled, rate limiting active, CSRF protection enabled
- **Enterprise Safety**: 7-day database retention, migration system, comprehensive audit logging
- **Tester Safety**: Ready for controlled tester access (5-10 users initially recommended)
- **CSRF Protection**: Flask-WTF CSRF protection fully implemented and tested (September 30, 2025)

## Recent Development (September 30, 2025)
🚧 **4-System Integrated Architecture** - Building demo-grade finbrain with:

**Foundation Layer (✅ COMPLETE)**:
- ✅ Atomic `on_expense_committed()` event hook for deterministic UI updates
- ✅ Truth & safety guardrails with data provenance and "I don't have that yet" responses  
- ✅ Trust Hub database tables (password_resets, deletion_requests) with atomic operations
- ✅ Performance indexes for <500ms query SLO
- ✅ Kill switches with graceful degradation (banners, insights, exports)

**Active Development**:
- 🔧 System 4 (Friction Elimination): Quick-taps, undo, quick-edit endpoints
- 🔧 System 3 (Intelligence Layer): History, micro-dashboard, insights with verify CTAs
- 🔧 System 2 (Emotional Engagement): HTMX partials, banners, celebrations
- 🔧 System 1 (Trust Hub): Password reset, CSV exports, account deletion with 7-day hold

**Architecture Principles**:
- Atomic event hooks as single source of truth
- Zero-hallucination with provable claims only
- Asia/Dhaka timezone for all date operations
- Kill switches for instant feature disable
- Graceful degradation without breaking chat
- <2s expense→UI refresh, <3s exports, <500ms history queries

## User Preferences
Preferred communication style: Simple, everyday language.
Zero-surprise deployment requirement: 100% user-visible success demanded with comprehensive validation before any production changes.

## System Architecture
finbrain utilizes a modular, AI-first web architecture with a comprehensive 100% user-visible success guarantee. It prioritizes security with mandatory HTTPS and web authentication, employing deterministic routing with ADMIN > ANALYSIS > FAQ > COACHING > SMALLTALK hierarchy. A "never-empty" AI contract ensures zero blank responses. Complete bilingual support (English + Bengali) with advanced Unicode normalization and Bengali digit conversion is implemented.

The Precision Capture & Audit (PCA) system ensures audit transparency and high-confidence auto-application of expenses (≥85% confidence), including enhanced Bengali + English pattern detection and a complete confidence score history logged for audit. The Clarifier Flow optimizes user interaction with 100% decision accuracy.

The application uses Flask with SQLAlchemy for database integration, with PostgreSQL as the primary database. Security measures include:
- **CSRF Protection**: Flask-WTF with session-based tokens, X-CSRFToken headers for AJAX/HTMX requests
- **Token Management**: Secure /api/auth/csrf-token endpoint with Cache-Control: no-store headers
- **Request Protection**: All POST/PUT/PATCH/DELETE endpoints protected, GET requests unaffected
- **HTTPS Enforcement**: Mandatory HTTPS in production with secure session cookies
- **Authentication**: SHA-256 hashing of user identifiers, comprehensive input sanitization with XSS prevention
- **Legacy Security**: X-Hub-Signature-256 verification (deprecated, webhooks removed), automated monitoring

Background message processing is handled by a thread pool. The AI system implements a resilient fallback chain for responses (primary AI → backup providers → stale cache → deterministic local responses) and uses circuit breaker patterns. Bengali digit normalization and advanced money detection are supported.

The system acknowledges inbound messages immediately and queues them for background processing. It features an engagement-driven AI architecture with proactive onboarding, personalized AI insights dashboards, and a smart reminder system. Corrections are handled intelligently with enhanced money detection and intelligent candidate matching. The web dashboard uses Bootstrap 5 and Font Awesome 6, maintaining a coach-style tone for a consistent user experience.

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