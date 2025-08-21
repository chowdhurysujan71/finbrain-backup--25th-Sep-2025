# ENVIRONMENT AND ENTRYPOINT SUMMARY

## Application Entrypoint
- **Command**: `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app`
- **Main Module**: `main:app` (imports from `app.py`)
- **Port**: 5000 (internal), 80 (external)
- **WSGI Server**: Gunicorn with reload enabled

## Required Environment Variables (Detected)
The following environment variables are required for the application to start:

### Core Facebook Integration
- `FACEBOOK_PAGE_ACCESS_TOKEN` - Facebook Messenger API access
- `FACEBOOK_VERIFY_TOKEN` - Webhook verification token
- `ADMIN_USER` - Admin interface username  
- `ADMIN_PASS` - Admin interface password

### Database
- `DATABASE_URL` - PostgreSQL connection string

### AI Integration
- `GEMINI_API_KEY` - Google Gemini AI API key
- `AI_ENABLED` - Toggle for AI processing (true/false)
- `AI_PROVIDER` - AI provider selection

### Security & Identity
- `ID_SALT` - Salt for user ID hashing
- `SESSION_SECRET` - Flask session secret key

### Optional Configuration
- `ENABLE_REPORTS` - Background reports toggle (default: false)
- `ENV` - Environment mode (production/development)

## Boot Validation
Application validates all required environment variables on startup and refuses to start if any are missing.