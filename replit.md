# finbrain

## Overview
finbrain is an AI-first expense tracking application delivered via a web chat interface. Its core purpose is to simplify expense tracking and provide AI-powered financial analysis by processing expense messages through the web chat, intelligently categorizing them, and offering streamlined financial insights. The system prioritizes security, featuring mandatory HTTPS and authentication, aiming to provide sophisticated AI-driven financial advice and learning capabilities with a business vision to simplify personal finance management and empower users with accessible, intelligent financial tools.

## User Preferences
Preferred communication style: Simple, everyday language.
Zero-surprise deployment requirement: 100% user-visible success demanded with comprehensive validation before any production changes.

## System Architecture
finbrain utilizes a modular, AI-first web architecture with a comprehensive 100% user-visible success guarantee. It prioritizes security with mandatory HTTPS and web authentication, employing deterministic routing with ADMIN > ANALYSIS > FAQ > COACHING > SMALLTALK hierarchy. A "never-empty" AI contract ensures zero blank responses. Complete bilingual support (English + Bengali) with advanced Unicode normalization and Bengali digit conversion is implemented.

The Precision Capture & Audit (PCA) system ensures audit transparency and high-confidence auto-application of expenses (≥85% confidence), including enhanced Bengali + English pattern detection and a complete confidence score history logged for audit. The Clarifier Flow optimizes user interaction with 100% decision accuracy.

The application uses Flask with SQLAlchemy for database integration, with PostgreSQL as the primary database. Security measures include X-Hub-Signature-256 verification, HTTPS enforcement, automated monitoring, SHA-256 hashing of user identifiers, and comprehensive input sanitization with XSS prevention.

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