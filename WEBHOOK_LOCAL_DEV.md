# Local Development with Webhooks

This guide explains how to set up webhook listeners for external services in local development. This is needed whenever you're integrating with services that send HTTP callbacks (Slack, GitHub, email, etc.).

## The Problem

External services like Slack, GitHub, and webhook-based email providers need to send HTTP requests to your application. In local development:
- Your application runs on `http://localhost:5000`
- External services can't reach `localhost` from the internet
- You need a public URL that forwards to your local development server

## The Solution: ngrok

**ngrok** is a tunneling service that creates a public URL pointing to your local application.

```
Internet → https://abc123.ngrok.io → ngrok tunnel → http://localhost:5000 → Your App
```

## Installation

### macOS (with Homebrew)
```bash
brew install ngrok
```

### Linux
```bash
wget https://bin.equinox.io/c/4VmDzA7iaHg/ngrok-stable-linux-amd64.zip
unzip ngrok-stable-linux-amd64.zip
sudo mv ngrok /usr/local/bin
```

### Windows
Download from https://ngrok.com/download and add to PATH.

### Verify Installation
```bash
ngrok --version
```

## Setup

### 1. Create a Free ngrok Account

1. Sign up at https://ngrok.com/signup (free tier available)
2. Go to https://dashboard.ngrok.com/auth/your-authtoken
3. Copy your authtoken
4. Run:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
   ```

### 2. Identify Your Application Port

Check which port your FastAPI application uses:
- Default: `5000` (FastAPI dev mode)
- Alternative: `8000` (standard FastAPI)
- Check `Procfile` or `uvicorn` command in logs

### 3. Start the Tunnel

In a dedicated terminal, start ngrok pointing to your application port:

```bash
ngrok http 5000
```

You'll see output like:
```
Session Status                online
Account                       user@example.com
Version                       3.0.0
Region                        us-central (us)
Forwarding                    https://abc123def.ngrok.io -> http://localhost:5000
Forwarding                    http://abc123def.ngrok.io -> http://localhost:5000
Web Interface                 http://127.0.0.1:4040
```

**Your public URL is:** `https://abc123def.ngrok.io`

> 💡 **Keep this terminal open.** If you close it, the tunnel closes and the URL becomes invalid.

## Using Your Webhook URL

### Configure External Services

When setting up webhooks on external services, use:
- **Base URL:** `https://YOUR_NGROK_URL` (always use `https`)
- **Endpoint:** The full path on your application

Examples:
- Slack events: `https://abc123def.ngrok.io/channel-adapters/slack/events`
- GitHub webhooks: `https://abc123def.ngrok.io/channel-adapters/github/webhooks`
- Email webhooks: `https://abc123def.ngrok.io/channel-adapters/email/webhooks`

### Verify Your Application is Reachable

```bash
# Test the base URL
curl https://abc123def.ngrok.io/health

# Should return something like:
# {"status": "healthy", "version": "0.1.0"}
```

## Development Workflow

### Terminal Setup (3 terminals recommended)

**Terminal 1: ngrok tunnel**
```bash
ngrok http 5000
# Keep this open and visible
```

**Terminal 2: FastAPI dev server**
```bash
make dev
# or: uv run fastapi dev app/main.py
```

**Terminal 3: Logs & testing**
```bash
make dev-logs
# Use this to monitor what's happening
```

## Debugging Webhook Requests

### View ngrok Dashboard

ngrok provides a real-time dashboard showing all traffic:

```bash
# Open in your browser
open http://127.0.0.1:4040
```

This shows:
- All incoming requests to your tunnel
- Request headers, body, method
- Response status and body
- Useful for debugging webhook payloads

### Test Webhooks Manually

You can test your webhook endpoints without the external service:

```bash
# Simple GET request
curl https://abc123def.ngrok.io/health

# POST with JSON payload
curl -X POST https://abc123def.ngrok.io/channel-adapters/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test123"}'

# POST with custom headers
curl -X POST https://abc123def.ngrok.io/channel-adapters/slack/events \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: 1234567890" \
  -d '{"type":"event_callback","event":{"type":"message"}}'
```

## Troubleshooting

### Connection Refused
- Verify your application is running: `make dev`
- Check the port matches (e.g., 5000 vs 8000): `netstat -tuln | grep LISTEN`
- Verify ngrok tunnel is active and shows "Status: online"

### "Invalid Request URL" or Webhook Verification Failed
- Make sure your application is running (`make dev`)
- Check logs: `make dev-logs`
- Verify the ngrok URL is correct (check Terminal 1)
- Ensure you're using `https://` not `http://`

### Webhook Endpoint Returns 404
- Verify the full path is correct
- Check application logs for routing errors
- Test with curl first: `curl https://abc123def.ngrok.io/channel-adapters/slack/events`

### Requests Time Out
- ngrok tunnel might have closed (check Terminal 1)
- Application might have crashed (check Terminal 2)
- Firewall might be blocking the port

### Ngrok Dashboard Shows 401/403 Errors
- Usually a signature verification issue (Slack signing secret incorrect)
- Check application logs for specific error messages
- Verify credentials in `.env` file

## Advanced Topics

### Using a Static Domain (Paid Plan)

On ngrok paid plans, you can reserve a static domain to avoid URL changes:

```bash
# With a reserved domain
ngrok http 5000 --domain=my-reserved-domain.ngrok.io
```

This is convenient because:
- URL doesn't change when you restart ngrok
- No need to update webhook URLs in external services frequently

### Running Multiple Tunnels

If you need to test multiple ports (e.g., FastAPI on 5000, admin dashboard on 8001):

```bash
# Terminal 1
ngrok http 5000 --subdomain=api

# Terminal 2 (separate ngrok session)
ngrok http 8001 --subdomain=admin
```

Results in:
- `https://api.ngrok.io` → `http://localhost:5000`
- `https://admin.ngrok.io` → `http://localhost:8001`

### Inspecting Requests Programmatically

Use ngrok's inspection API:

```bash
# Get details of recent requests
curl http://127.0.0.1:4040/api/requests/http

# Get specific request details
curl http://127.0.0.1:4040/api/requests/http/req_YOUR_REQUEST_ID
```

## Tips

### 1. Keep ngrok URL in `.env`
Some applications need to know their public URL:
```bash
PUBLIC_URL=https://abc123def.ngrok.io
```

### 2. Log All Webhook Traffic
Add logging to your webhook endpoints to debug issues:
```python
import logging
logger = logging.getLogger(__name__)

@router.post("/webhooks/slack")
async def slack_webhook(request: Request):
    logger.info(f"Received Slack webhook: {request.headers}")
    ...
```

### 3. Test with Real Data
Use ngrok dashboard to capture real webhook payloads, then replay them for testing.

### 4. Document Your Tunnel
Add a comment in your code:
```python
# Note: When testing locally, use ngrok tunnel URL
# Example: https://abc123def.ngrok.io/channel-adapters/slack/events
```

## Common Adapter Webhook URLs

| Adapter | Endpoint | Example URL |
|---------|----------|-------------|
| Slack Events | `/channel-adapters/slack/events` | `https://abc123.ngrok.io/channel-adapters/slack/events` |
| Slack Interactions | `/channel-adapters/slack/interactions` | `https://abc123.ngrok.io/channel-adapters/slack/interactions` |
| GitHub | `/channel-adapters/github/webhooks` | `https://abc123.ngrok.io/channel-adapters/github/webhooks` |
| Email | `/channel-adapters/email/webhooks` | `https://abc123.ngrok.io/channel-adapters/email/webhooks` |
| Tasks | `/tasks/webhooks/{id}` | `https://abc123.ngrok.io/tasks/webhooks/abc123` |

## Useful Links

- ngrok Documentation: https://ngrok.com/docs
- ngrok Dashboard: https://dashboard.ngrok.com
- HTTP Status Codes: https://httpwg.org/specs/rfc7231.html#status.codes
- curl Documentation: https://curl.se/docs/manual.html
