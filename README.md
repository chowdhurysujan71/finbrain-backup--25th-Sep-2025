# finbrain - Facebook Messenger Expense Tracker

A secure, AI-powered expense tracking application that processes expense messages through Facebook Messenger. Users can send expense messages in natural language, and the system automatically categorizes expenses, extracts amounts, and provides real-time confirmations with monthly totals.

## Features

- **Facebook Messenger Integration**: Process expense messages via Facebook Messenger using Graph API v17.0
- **AI-Powered Analysis**: Optional AI recommendation layer with fast models (GPT-4o-mini/Gemini-1.5-Flash)
- **Intelligent Categorization**: Automatically classify expenses into predefined categories
- **Cold-Start Mitigation**: Server pre-warming and health ping system for optimal performance
- **Secure Data Handling**: SHA-256 hashing for user identifiers, no raw personal data stored
- **Real-time Processing**: Sub-300ms webhook responses with background message processing
- **Web Dashboard**: Admin interface for monitoring expenses and user activity
- **Rate Limiting**: Daily and hourly message limits per user with 24-hour policy compliance
- **Comprehensive Logging**: Structured JSON logging for production observability

## Architecture

- **Backend**: Flask web application with SQLAlchemy ORM
- **Database**: PostgreSQL with connection pooling
- **Messaging**: Facebook Messenger Platform via webhook
- **Security**: PSID-based identity, SHA-256 user hashing
- **Background Tasks**: APScheduler for automated reporting

## Setup

1. Configure environment variables in `.env`:
   ```
   DATABASE_URL=postgresql://user:pass@localhost/finbrain
   FACEBOOK_PAGE_ACCESS_TOKEN=your_facebook_page_access_token
   FACEBOOK_VERIFY_TOKEN=your_verify_token
   SESSION_SECRET=your_session_secret
   DAILY_MESSAGE_LIMIT=50
   HOURLY_MESSAGE_LIMIT=10
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
   ```

## API Endpoints

- `GET /` - Admin dashboard for viewing expense statistics (HTTP Basic Auth required)
- `GET /health` - Enhanced health check with uptime, queue depth, and AI status
- `GET /ops` - Operations monitoring endpoint (HTTP Basic Auth required)
- `GET /psid/<hash>` - PSID explorer for user investigation (HTTP Basic Auth required)
- `GET|POST /webhook/messenger` - Facebook Messenger webhook with signature verification

## Documentation

### Facebook Messenger API References

- **[Send API Reference](https://developers.facebook.com/docs/messenger-platform/reference/send-api)** - Complete guide to sending messages via Messenger Platform
- **[24-Hour Policy Overview](https://developers.facebook.com/docs/messenger-platform/policy/policy-overview#messaging_type)** - Understanding messaging windows and compliance requirements
- **[m.me Links Guide](https://developers.facebook.com/docs/messenger-platform/discovery/m-me-links)** - Creating direct Messenger conversation links
- **[Account Linking](https://developers.facebook.com/docs/messenger-platform/identity/account-linking)** - Authentication flow for linking user accounts (future implementation)

### Additional Resources

- **[Webhook Setup](https://developers.facebook.com/docs/messenger-platform/getting-started/webhook-setup)** - Configuring webhooks for Messenger Platform
- **[Graph API v17.0](https://developers.facebook.com/docs/graph-api/overview)** - Core API documentation for Facebook integrations
- **[App Review Process](https://developers.facebook.com/docs/app-review)** - Requirements for production Messenger apps

## TODO

- **Future: Messenger Account Linking for dashboard access** - Add authentication flow to link Facebook Messenger accounts with dashboard access for personalized expense viewing.

## Project Structure

```
├── app.py                  # Main Flask application
├── main.py                 # WSGI entry point
├── models.py               # Database models
├── utils/                  # Utility modules
│   ├── expense.py         # Expense processing logic
│   ├── categories.py      # Categorization system
│   ├── security.py        # Security functions
│   ├── db.py              # Database operations
│   ├── rate_limiter.py    # Rate limiting
│   ├── facebook_handler.py # Facebook Messenger integration
│   ├── webhook_processor.py # Fast webhook processing
│   ├── background_processor.py # Background message processing
│   ├── ai_adapter.py      # Pluggable AI provider system
│   ├── cold_start_mitigation.py # Server warm-up system
│   ├── health_ping.py     # Health monitoring
│   ├── logger.py          # Structured logging
│   ├── policy_guard.py    # 24-hour messaging compliance
│   ├── mvp_router.py      # Regex-based intent routing
│   ├── report_generator.py # Automated reports
│   └── scheduler.py       # Background task scheduling
├── templates/             # HTML templates
└── static/               # Static assets
```