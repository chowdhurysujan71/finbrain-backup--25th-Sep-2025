# finbrain

## Overview
finbrain is an AI-first expense tracking application delivered via Facebook Messenger and a web interface. Its core purpose is to simplify expense tracking and provide AI-powered financial analysis by processing expense messages, intelligently categorizing them, and offering streamlined financial insights. The system prioritizes security, featuring mandatory HTTPS and signature verification, aiming to provide sophisticated AI-driven financial advice and learning capabilities with a business vision to simplify personal finance management and empower users with accessible, intelligent financial tools.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles
FinBrain utilizes a modular, AI-first architecture with **Phase 4: Limited Production PCA** active (`PCA_MODE=ON`). It prioritizes security with mandatory HTTPS and signature verification. All AI features are always-on, with AI-first routing. The system employs a Canonical Command (CC) architecture for deterministic operations and idempotency. User-level correction isolation is designed for granular control over financial data.

### PCA (Precision Capture & Audit) System - Phase 4 Active
- **Current Phase**: Limited Production (PCA_MODE=ON)
- **High-Confidence Auto-Apply**: Expenses with ≥85% confidence automatically create transactions
- **Enhanced Detection**: Bengali + English patterns with confidence scoring
- **Transaction Creation**: Real expense records generated for high-confidence CCs
- **Audit Trail**: Complete CC history logged to inference_snapshots table
- **Performance**: <100ms processing overhead maintained

### Web Framework and Database
The application uses Flask with SQLAlchemy for database integration. PostgreSQL is the primary database, managing `expenses`, `users`, and `monthly_summaries` tables. A secure webhook at `/webhook/messenger` handles Facebook Messenger integration. Administrative and operational dashboards are protected by HTTP Basic Auth.

### Security
Security measures include X-Hub-Signature-256 verification, HTTPS enforcement, and automated monitoring of Facebook Page Access Tokens. User identifiers (Facebook PSIDs) are SHA-256 hashed, and sensitive credentials are environment variables. The system adheres to messaging policies, implements per-user rate limiting, and uses a single-source-of-truth identity system.

### Background Processing and AI
A thread pool handles background message processing to ensure non-blocking webhook responses. An intelligent AI recommendation layer (Gemini-2.5-flash-lite) categorizes expenses and provides tips. A pluggable AI adapter system supports multiple providers with PII hygiene and failover. Robust AI rate limiting prevents abuse. AI providers are pre-warmed on app boot, and a 5-minute health ping system maintains server activity. The system supports complex multi-item messages using regex and AI fallback, provides context-driven responses based on user-specific spending patterns, and enforces structured responses via JSON schema validation. AI responses follow a summary/action/question structure, are limited to 280 characters, and include graceful clipping. Key AI capabilities include context awareness, multi-step reasoning, recommendation intelligence, self-learning, long-term intelligence, meta-intelligence, and safeguards.

### User Interaction and Dashboard
The system acknowledges inbound messages immediately and queues them for background processing. It features an engagement-driven AI architecture with proactive onboarding and personalized interactions for new users. Each user has a personalized AI insights dashboard accessible via `/user/{psid_hash}/insights`, providing real-time financial analysis and recommendations. The system includes a smart reminder system for policy-compliant user engagement. Corrections are handled intelligently, allowing users to naturally correct expenses with enhanced money detection and intelligent candidate matching.

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