# FinBrain - Facebook Messenger Expense Tracker

A secure, AI-powered expense tracking application that processes expense messages through Facebook Messenger. Users can send expense messages in natural language, and the system automatically categorizes expenses, extracts amounts, and provides real-time confirmations with monthly totals.

## Features

- **Facebook Messenger Integration**: Process expense messages via Facebook Messenger using Graph API v17.0
- **AI-Powered Categorization**: Automatically classify expenses into 10 predefined categories
- **Secure Data Handling**: SHA-256 hashing for user identifiers, no raw personal data stored
- **Real-time Processing**: Instant expense confirmation and monthly summaries
- **Web Dashboard**: View expense statistics and analytics
- **Rate Limiting**: Daily and hourly message limits per user
- **Automated Reports**: Background task scheduling for daily and weekly reports

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

- `GET /` - Web dashboard for viewing expense statistics
- `GET /health` - Health check endpoint
- `GET|POST /webhook/messenger` - Facebook Messenger webhook

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
│   ├── report_generator.py # Automated reports
│   └── scheduler.py       # Background tasks
├── templates/             # HTML templates
└── static/               # Static assets
```