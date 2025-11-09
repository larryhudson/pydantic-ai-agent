# Local Development Setup for Slack Adapter

This guide walks you through setting up the Slack adapter for local development. For general webhook setup with ngrok, see [WEBHOOK_LOCAL_DEV.md](WEBHOOK_LOCAL_DEV.md).

## Prerequisites

- Python 3.12+ (for the main application)
- ngrok set up and running (see [WEBHOOK_LOCAL_DEV.md](WEBHOOK_LOCAL_DEV.md))
- A Slack workspace where you have permission to create apps
- PostgreSQL and Redis running locally (or via Docker)

## Step 1: Set Up Slack App

### Create a New Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. **App name:** `AI Agent Platform (Dev)` (or your preference)
4. **Workspace:** Select your workspace
5. Click "Create App"

### Get Bot Token & Signing Secret

1. In the left sidebar, click **Basic Information**
2. Under "App Credentials", find **Signing Secret** and copy it
3. Click **OAuth & Permissions** in the left sidebar
4. Under "OAuth Tokens for Your Workspace", find **Bot User OAuth Token** and copy it

### Configure Event Subscriptions

1. In the left sidebar, click **Event Subscriptions**
2. Toggle "Enable Events" to **On**
3. For "Request URL", use your ngrok tunnel URL (see below):
   ```
   https://YOUR_NGROK_URL/channel-adapters/slack/events
   ```
4. Subscribe to these bot events:
   - `app_mention`
   - `message.channels`
   - `message.groups`
   - `message.im`
5. Click "Save Changes"
6. Slack will verify the URL (your application must be running)

### Configure Interactivity & Shortcuts

1. In the left sidebar, click **Interactivity & Shortcuts**
2. Toggle "Interactivity" to **On**
3. For "Request URL", use:
   ```
   https://YOUR_NGROK_URL/channel-adapters/slack/interactions
   ```
4. Click "Save Changes"

## Step 2: Start ngrok Tunnel

Follow the instructions in [WEBHOOK_LOCAL_DEV.md](WEBHOOK_LOCAL_DEV.md) to start ngrok. Your tunnel URL will look like: `https://abc123def.ngrok.io`

Then go back to Slack app configuration and update:
- **Event Subscriptions Request URL:** `https://abc123def.ngrok.io/channel-adapters/slack/events`
- **Interactivity Request URL:** `https://abc123def.ngrok.io/channel-adapters/slack/interactions`

## Step 3: Configure Environment Variables

Create or update `.env` with:

```bash
# Slack Adapter Configuration
SLACK_BOT_TOKEN=xoxb-YOUR_BOT_TOKEN_HERE
SLACK_SIGNING_SECRET=YOUR_SIGNING_SECRET_HERE

# Database (assuming local PostgreSQL)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_platform

# Redis (assuming local)
REDIS_URL=redis://localhost:6379

# Optional: API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_MODEL=openai:gpt-4

# Debug mode (helpful for development)
DEBUG=true
DATABASE_ECHO=true
```

## Step 4: Start the Development Server

In a terminal:

```bash
make dev
```

Or manually:
```bash
uv run fastapi dev app/main.py
```

Check logs:
```bash
make dev-logs
```

You should see:
```
Starting AI Agent Platform
Database initialized
Slack adapter registered
Scheduler started
Server started at http://127.0.0.1:5000
```

## Step 5: Test the Integration

### Test 1: Health Check
```bash
curl https://abc123def.ngrok.io/health
```

Should return:
```json
{"status": "healthy", "version": "0.1.0"}
```

### Test 2: Mention the Bot in Slack

1. Go to your Slack workspace
2. In any channel, type `@AI Agent Platform (Dev) Hello!`
3. The bot should:
   - Receive the event via ngrok
   - Create a conversation
   - Process your message
   - Reply in the thread

### Test 3: Check Logs

```bash
make dev-logs
```

You should see logs from:
- Slack event verification
- Message parsing
- Agent execution
- Response sending

## Troubleshooting

### "Request URL failed verification" in Slack

1. Verify your ngrok tunnel is active (check Terminal 1)
2. Verify FastAPI is running: `make dev-logs`
3. Verify the URL in Slack matches your ngrok URL exactly
4. Check application logs for signature verification errors:
   ```bash
   make dev-logs 2>&1 | tail -50
   ```

### "Invalid Slack signature" Error

This means request signature verification is failing:
- Verify `SLACK_SIGNING_SECRET` is exactly correct (copy from Slack app Basic Information)
- Make sure there are no extra spaces or newlines
- Signing secret is **different** from bot token

### Bot Doesn't Respond to Messages

1. Verify credentials in `.env`:
   - `SLACK_BOT_TOKEN` starts with `xoxb-`
   - `SLACK_SIGNING_SECRET` is present
2. Check that bot is installed to your workspace (OAuth & Permissions page)
3. Check that app has required permissions (Event Subscriptions configured)
4. Check application logs: `make dev-logs`

### Event Subscriptions Verification Keeps Failing

See [WEBHOOK_LOCAL_DEV.md - Troubleshooting](WEBHOOK_LOCAL_DEV.md#troubleshooting) for general webhook issues.

## Tips for Development

### Testing Slack Webhooks Directly

You can test your Slack webhook endpoints without the Slack app:

```bash
# Test Slack event verification challenge
curl -X POST http://localhost:5000/channel-adapters/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type": "url_verification", "challenge": "test123"}'

# Should return: {"challenge": "test123"}

# Test with actual Slack event payload (minimal)
curl -X POST http://localhost:5000/channel-adapters/slack/events \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: $(date +%s)" \
  -H "X-Slack-Request-Signature: v0=fake_signature" \
  -d '{
    "type": "event_callback",
    "event": {
      "type": "app_mention",
      "user": "U123456",
      "text": "Hello <@BOT_ID>",
      "channel": "C123456",
      "ts": "1234567890.000000"
    }
  }'
```

### Debugging with ngrok Dashboard

For general ngrok debugging, see [WEBHOOK_LOCAL_DEV.md - Debugging Webhook Requests](WEBHOOK_LOCAL_DEV.md#debugging-webhook-requests).

### Slack-Specific Debugging

Enable debug logging to see Slack request details:

```bash
# In .env
DEBUG=true
DATABASE_ECHO=true
```

Then check logs:
```bash
make dev-logs 2>&1 | grep -i slack
```

## Environment Variables Reference

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes | `xoxb-...` | Bot token from OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | Yes | `abc123...` | Signing secret from Basic Information |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_platform` | PostgreSQL connection |
| `REDIS_URL` | Yes | `redis://localhost:6379` | Redis connection |
| `DEBUG` | No | `true` | Enable debug logging |
| `DATABASE_ECHO` | No | `true` | Log all SQL queries |

## Testing Checklist

Before testing, verify:

- [ ] PostgreSQL is running
- [ ] Redis is running
- [ ] ngrok tunnel is active and shows "Status: online"
- [ ] FastAPI is running (`make dev`)
- [ ] `SLACK_BOT_TOKEN` is set and starts with `xoxb-`
- [ ] `SLACK_SIGNING_SECRET` is set correctly
- [ ] Slack app Request URLs are updated with your current ngrok URL
- [ ] URLs are verified in Slack app (Event Subscriptions & Interactivity)
- [ ] Bot is installed to your workspace (OAuth & Permissions page)

## Testing Scenarios

Once basic setup works, test these scenarios:

1. **Simple message** - Mention the bot in any channel
2. **Thread reply** - Reply to a bot message in a thread
3. **Streaming response** - Ask the bot a multi-step question
4. **Error handling** - Test with invalid inputs
5. **Conversation history** - Verify messages are stored and retrieved

## Useful Links

- Slack API Docs: https://api.slack.com/docs
- Slack App Configuration: https://api.slack.com/apps
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Project Architecture: See [ADAPTER_PATTERN.md](ADAPTER_PATTERN.md)
- Webhook Debugging: See [WEBHOOK_LOCAL_DEV.md](WEBHOOK_LOCAL_DEV.md)
