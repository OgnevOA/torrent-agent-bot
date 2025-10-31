# Torrent Agent - Telegram Bot

An AI-powered Telegram bot that searches for torrents on rutracker.org using natural language queries and sends selected torrents to qBittorrent on your TrueNAS Scale server.

## Features

- Natural language search queries using Google Gemini 2.5 Flash
- Automatic torrent search on rutracker.org
- Interactive torrent selection via Telegram inline keyboards
- Direct integration with qBittorrent API
- Secure credential management

## Setup

### Prerequisites

- Python 3.9 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Rutracker.org account credentials
- qBittorrent API access (enabled on your TrueNAS Scale server)
- Google AI API key (for Gemini 2.5 Flash)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Torrent_agent
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

**Note:** The bot uses a custom scraper implementation for rutracker.org that handles authentication and search directly.

4. Configure environment variables:
```bash
# Create .env file in the root directory
# Copy the template below and fill in your values
```

Create a `.env` file in the root directory with the following content:

```env
# Telegram Bot Configuration
# Get your bot token from @BotFather on Telegram
# No quotes needed unless value contains spaces
TG_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Security: Allowed Chat IDs (optional but recommended)
# Get your chat ID by messaging @userinfobot on Telegram
# Comma-separated list, e.g., "123456789,987654321"
# Leave empty to allow all users (NOT RECOMMENDED for production)
ALLOWED_CHAT_IDS=123456789

# Rutracker Credentials
RUTRACKER_USERNAME=your_username
RUTRACKER_PASSWORD=your_password

# qBittorrent API Configuration
# For TrueNAS Scale, use the IP or hostname of your server
# No quotes needed for URLs
QBITTORRENT_URL=http://192.168.1.100:8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=your_qbittorrent_password

# Google Gemini API
# Get your API key from https://aistudio.google.com/apikey
GOOGLE_API_KEY=your_google_api_key_here
```

**Note:** Quotes are NOT required for these values. Only use quotes if your value contains spaces or special characters that need escaping. For example:
- `TG_BOT_TOKEN=1234567890:ABCdef` ✅ (no quotes needed)
- `RUTRACKER_PASSWORD="my password"` ✅ (quotes needed due to space)

### Configuration

Edit the `.env` file with your credentials:

- `TG_BOT_TOKEN`: Get from [@BotFather](https://t.me/botfather)
- `ALLOWED_CHAT_IDS`: (Optional but recommended) Comma-separated list of authorized Telegram chat IDs. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot). Leave empty to allow all users (not recommended for production)
- `RUTRACKER_USERNAME`: Your rutracker.org username
- `RUTRACKER_PASSWORD`: Your rutracker.org password
- `QBITTORRENT_URL`: Full URL to qBittorrent Web UI (e.g., `http://192.168.1.100:8080`)
- `QBITTORRENT_USERNAME`: qBittorrent Web UI username
- `QBITTORRENT_PASSWORD`: qBittorrent Web UI password
- `GOOGLE_API_KEY`: Get from [Google AI Studio](https://aistudio.google.com/apikey) (free tier available)

### Running

```bash
python src/main.py
```

## Usage

1. Start a conversation with your bot on Telegram
2. Send `/start` to see the welcome message
3. Send a natural language query like:
   - "Find Matrix movie torrent with good seeders"
   - "Find X, with russian dub, Fox Crime preferred"
   - "Search for latest Linux distribution ISO"
4. The bot will show you numbered results from rutracker.org
5. Reply with the number to download:
   - "3" or "Download the third one" or "Download number 3"
6. The bot will automatically add it to your qBittorrent

## Project Structure

```
Torrent_agent/
├── src/
│   ├── bot/           # Telegram bot handlers
│   ├── agent/         # LangChain agent
│   ├── scrapers/      # Rutracker scraper
│   ├── qbittorrent/   # qBittorrent client
│   ├── config/        # Configuration
│   └── main.py        # Entry point
├── requirements.txt
├── .env              # Your credentials (not in git)
└── README.md
```

## Troubleshooting

### Bot not responding to commands
1. **Check if bot is running**: Look at the console/logs for "Bot is running" message
2. **Verify bot token**: 
   - Check that `TG_BOT_TOKEN` in `.env` is correct
   - Get token from [@BotFather](https://t.me/botfather) if needed
   - Make sure token doesn't have quotes or extra spaces
3. **Check logs**: Look at `torrent_bot.log` or console output for errors
4. **Verify bot is started**: In [@BotFather](https://t.me/botfather), make sure your bot is not stopped
5. **Test bot token**: Try to get bot info using Telegram API or test with curl:
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
   ```
6. **Common issues**:
   - `.env` file not in root directory
   - Missing or incorrect environment variables
   - Bot token has placeholder value still
   - Old `TELEGRAM_BOT_TOKEN` in Windows env (should use `TG_BOT_TOKEN` instead)
   - Network/firewall blocking Telegram API

### qBittorrent API not working
- Make sure qBittorrent Web UI is enabled in Settings → Web UI
- Check that the API is enabled (default port is 8080)
- Verify the URL, username, and password in `.env`
- Ensure qBittorrent is accessible from the machine running the bot

### Rutracker login fails
- Verify your username and password are correct
- Check if rutracker.org requires CAPTCHA (may need manual login first)
- Ensure your account is not banned or restricted

### Telegram bot not responding
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Make sure the bot is started (not stopped) in [@BotFather](https://t.me/botfather)
- Check logs in `torrent_bot.log` for errors

### Gemini API errors
- Verify `GOOGLE_API_KEY` is correct
- Check your Google AI Studio quota (free tier has limits)
- Ensure the API is enabled for Gemini models

### No search results found
- Try different search terms
- Check if rutracker.org is accessible
- Verify the scraper is parsing HTML correctly (may need updates if site changes)

## Notes

- The bot uses experimental `gemini-2.0-flash-exp` model by default. To use a different model, edit `src/agent/langchain_agent.py`
- Rate limiting: The scraper includes basic rate limiting, but be respectful of rutracker.org's servers
- Session management: Rutracker sessions are maintained during bot operation

## License

MIT

