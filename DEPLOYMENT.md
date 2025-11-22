# TrueNAS Scale Deployment Guide

Complete step-by-step guide for deploying the Torrent Agent bot on TrueNAS Scale using the App UI.

## Prerequisites

Before starting, ensure you have:
- ✅ TrueNAS Scale installed and running
- ✅ Apps enabled in TrueNAS Scale (Settings → Apps → Settings → Enable)
- ✅ Docker image built and pushed to a registry (Docker Hub, GitHub Container Registry, or local registry)
- ✅ All credentials ready:
  - Telegram bot token (from [@BotFather](https://t.me/botfather))
  - Rutracker username and password
  - qBittorrent URL, username, and password
  - Google Gemini API key (from [Google AI Studio](https://aistudio.google.com/apikey))

## Step 1: Build and Push Docker Image

### Option A: Build Locally and Push to Docker Hub

```bash
# Build the image
docker build -t your-username/torrent-agent:latest .

# Login to Docker Hub
docker login

# Push to Docker Hub
docker push your-username/torrent-agent:latest
```

### Option B: Build Locally and Push to GitHub Container Registry

```bash
# Build the image
docker build -t ghcr.io/your-username/torrent-agent:latest .

# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u your-username --password-stdin

# Push to GitHub Container Registry
docker push ghcr.io/your-username/torrent-agent:latest
```

### Option C: Use GitHub Actions (Recommended for Auto-Updates)

If you've set up GitHub Actions CI/CD, images are automatically built and pushed on each commit. Use:
```
ghcr.io/your-username/Torrent_agent:latest
```

## Step 2: Deploy via TrueNAS Scale App UI

### Detailed Step-by-Step Instructions

#### 1. Access TrueNAS Scale Apps Interface

1. Log into your TrueNAS Scale Web UI
2. Navigate to **Apps** in the left sidebar
3. Click **Available Applications** (or **Installed Applications** if you want to see existing apps)

#### 2. Launch Custom App

1. Click the **Settings** button (gear icon) in the top right
2. Ensure **Enable** is checked for Apps
3. Go back to **Available Applications**
4. Click the **Custom App** button (or click **Discover Apps** → **Custom App**)

#### 3. Configure Basic Settings

In the **Basic Configuration** section:

- **Application Name**: `torrent-bot`
- **Version**: `1.0.0` (or your version)
- **Release Name**: `torrent-bot` (or leave default)

#### 4. Configure Container Image

In the **Container Configuration** section:

- **Container Image**: Enter your image URL:
  - Docker Hub: `your-username/torrent-agent:latest`
  - GitHub Container Registry: `ghcr.io/your-username/torrent-agent:latest`
  - Or use a specific tag: `ghcr.io/your-username/torrent-agent:v1.0.0`

- **Image Pull Policy**: `Always` (recommended for latest updates) or `IfNotPresent`

#### 5. Configure Environment Variables

Click **Add Environment Variable** for each required variable:

**Required Variables:**

| Variable Name | Description | Example Value |
|--------------|-------------|---------------|
| `TG_BOT_TOKEN` | Telegram bot token from @BotFather | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `RUTRACKER_USERNAME` | Your rutracker.org username | `my_username` |
| `RUTRACKER_PASSWORD` | Your rutracker.org password | `my_password` |
| `QBITTORRENT_URL` | qBittorrent Web UI URL | `http://192.168.1.100:8080` |
| `QBITTORRENT_USERNAME` | qBittorrent Web UI username | `admin` |
| `QBITTORRENT_PASSWORD` | qBittorrent Web UI password | `my_password` |
| `GOOGLE_API_KEY` | Google Gemini API key | `AIzaSyD...` |

**Optional Variables:**

| Variable Name | Description | Example Value |
|--------------|-------------|---------------|
| `ALLOWED_CHAT_IDS` | Comma-separated list of allowed Telegram chat IDs (security) | `123456789,987654321` |

**Important Notes:**
- Do **NOT** add quotes around values (e.g., use `1234567890:ABC...` not `"1234567890:ABC..."`)
- For `QBITTORRENT_URL`:
  - If qBittorrent is on the same TrueNAS machine: use `http://localhost:8080` (with Host network) or `http://your-truenas-ip:8080` (with Bridge network)
  - If qBittorrent is on another machine: use `http://192.168.1.100:8080` (replace with actual IP)

#### 6. Configure Networking

In the **Networking** section:

**Option A: Host Network (Recommended if qBittorrent is on same machine)**
- **Network Mode**: Select `Host`
- **Advantages**: Direct access to localhost services, simpler configuration
- **qBittorrent URL**: Use `http://localhost:8080`

**Option B: Bridge Network (If qBittorrent is on different IP)**
- **Network Mode**: Select `Bridge` or `Default`
- **Port Mappings**: Not needed (bot doesn't expose ports)
- **qBittorrent URL**: Use `http://192.168.1.100:8080` (replace with actual IP)

#### 7. Configure Storage (Optional but Recommended)

To persist logs across container restarts:

1. Click **Add Volume** or **Add Storage**
2. Configure the volume:
   - **Volume Type**: `Host Path`
   - **Host Path**: `/mnt/pool/datasets/torrent-bot-logs` (create this directory first or use an existing dataset)
   - **Mount Path**: `/app/logs`
   - **Read Only**: `No` (unchecked)

**To create the directory:**
- In TrueNAS Scale, go to **Storage** → **Pools**
- Navigate to your pool and create a dataset (e.g., `torrent-bot-logs`)
- Or use SSH: `mkdir -p /mnt/pool/datasets/torrent-bot-logs`

#### 8. Configure Resources (Optional)

In the **Resources** section:

- **CPU Limits**: 
  - Request: `0.5` cores
  - Limit: `1` core
- **Memory Limits**:
  - Request: `512Mi`
  - Limit: `1Gi`

These are optional - the bot is lightweight and doesn't need many resources.

#### 9. Configure Advanced Settings (Optional)

- **Restart Policy**: `Always` (recommended)
- **Command**: Leave empty (uses Dockerfile CMD)
- **Args**: Leave empty
- **Working Directory**: Leave empty (uses Dockerfile WORKDIR)

#### 10. Deploy the Application

1. Review all settings
2. Click **Save** or **Deploy**
3. Wait for the container to start (status will change to "Running")

#### 11. Verify Deployment

1. **Check Container Status**:
   - In **Apps** → **Installed Applications**, find `torrent-bot`
   - Status should show "Running" (green)
   - If it shows "Stopped" or error, click on it to view logs

2. **View Logs**:
   - Click on `torrent-bot` app
   - Click **Logs** tab
   - Look for: `"Bot is running. Press Ctrl+C to stop."`
   - Look for: `"Configuration loaded successfully"`

3. **Test the Bot**:
   - Open Telegram and start a chat with your bot
   - Send `/start` command
   - You should receive a welcome message

4. **Test Search**:
   - Send a search query like: `"Find Matrix movie"`
   - Verify the bot responds with search results

## Step 3: Alternative Deployment Methods

### Via SSH (Docker Compose)

If you prefer using Docker Compose via SSH:

```bash
# SSH into TrueNAS Scale
ssh root@your-truenas-ip

# Clone repository (if not already cloned)
git clone https://github.com/your-username/Torrent_agent.git
cd Torrent_agent

# Create .env file
nano .env
# Paste all your environment variables (see README.md for format)

# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f torrent-bot
```

**Note**: This method uses Docker directly, bypassing TrueNAS Scale's App management. The App UI method is recommended for better integration with TrueNAS Scale.

## Troubleshooting

### Container Won't Start

**Symptoms**: App shows "Stopped" status or keeps restarting

**Solutions**:
1. **Check Logs**:
   - In TrueNAS Scale: Apps → torrent-bot → Click **Logs** tab
   - Look for error messages at the end of the log output

2. **Verify Environment Variables**:
   - Go to Apps → torrent-bot → **Edit**
   - Check that all required variables are present:
     - `TG_BOT_TOKEN` ✅
     - `RUTRACKER_USERNAME` ✅
     - `RUTRACKER_PASSWORD` ✅
     - `QBITTORRENT_URL` ✅
     - `QBITTORRENT_USERNAME` ✅
     - `QBITTORRENT_PASSWORD` ✅
     - `GOOGLE_API_KEY` ✅
   - Ensure no quotes around values
   - Check for typos (case-sensitive)

3. **Verify Container Image**:
   - Check the image URL is correct
   - Test pulling the image manually:
     ```bash
     docker pull your-username/torrent-agent:latest
     ```
   - Ensure image exists in the registry

4. **Check Network Mode**:
   - If using Host network and qBittorrent URL is `http://192.168.1.100:8080`, change to `http://localhost:8080`
   - If using Bridge network and qBittorrent URL is `http://localhost:8080`, change to `http://your-truenas-ip:8080`

### Bot Not Responding

**Symptoms**: Container is running but bot doesn't respond to Telegram messages

**Solutions**:
1. **Check Bot Logs**:
   - Apps → torrent-bot → **Logs**
   - Look for: `"Bot is running. Press Ctrl+C to stop."`
   - Look for errors about Telegram API

2. **Verify Telegram Bot Token**:
   - Check `TG_BOT_TOKEN` is correct (no quotes, no extra spaces)
   - Test token with curl:
     ```bash
     curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
     ```
   - Should return JSON with bot info

3. **Common Issues**:
   - Token has quotes: `"1234567890:ABC..."` ❌ → Remove quotes
   - Token has trailing space: `1234567890:ABC... ` ❌ → Remove space
   - Invalid token format: Should start with numbers and contain a colon

4. **Check Network Connectivity**:
   - Container needs internet access to reach Telegram API
   - Verify DNS resolution works in container

### qBittorrent Connection Fails

**Symptoms**: Bot starts but can't connect to qBittorrent

**Solutions**:
1. **Verify qBittorrent URL**:
   - **Host Network Mode**: Use `http://localhost:8080`
   - **Bridge Network Mode**: Use `http://your-truenas-ip:8080` or `http://qbittorrent-service-name:8080` (if qBittorrent is also a container)
   - Test URL in browser: Should show qBittorrent Web UI login page

2. **Check qBittorrent Settings**:
   - **Web UI Enabled**: qBittorrent → Settings → Web UI → Enable Web UI ✅
   - **API Enabled**: Should be enabled by default when Web UI is enabled ✅
   - **Port**: Usually `8080` (verify in qBittorrent settings)
   - **IP Binding**: Should be `0.0.0.0` (all interfaces) or specific IP

3. **Test Connectivity**:
   - **From TrueNAS Scale shell**:
     ```bash
     # Test if qBittorrent is accessible
     curl http://localhost:8080/api/v2/app/version
     ```
   - Should return qBittorrent version number

4. **Verify Credentials**:
   - Check `QBITTORRENT_USERNAME` and `QBITTORRENT_PASSWORD` are correct
   - Test login via browser to qBittorrent Web UI

5. **If qBittorrent is also a Container**:
   - Ensure both containers are on the same network
   - Use service name: `http://qbittorrent-service-name:8080`
   - Or use Host network mode for both containers

### Rutracker Login Fails

**Symptoms**: Bot can't log in to rutracker.org

**Solutions**:
1. **Verify Credentials**:
   - Check `RUTRACKER_USERNAME` and `RUTRACKER_PASSWORD` are correct
   - Test login manually in browser

2. **Check for CAPTCHA**:
   - If rutracker requires CAPTCHA, you may need to log in manually first
   - Clear cookies/session if needed

3. **Check Account Status**:
   - Ensure account is not banned or restricted
   - Verify account is active

### Gemini API Errors

**Symptoms**: Bot starts but search queries fail

**Solutions**:
1. **Verify API Key**:
   - Check `GOOGLE_API_KEY` is correct
   - Get new key from [Google AI Studio](https://aistudio.google.com/apikey)

2. **Check API Quota**:
   - Free tier has rate limits
   - Check quota usage in Google AI Studio

3. **Verify API is Enabled**:
   - Ensure Gemini API is enabled for your Google Cloud project

### Logs Location

- **Container Logs**: View in TrueNAS Scale Apps interface
  - Apps → torrent-bot → **Logs** tab
  - Shows real-time container logs

- **Persistent Logs** (if volume mounted):
  - Location: `/mnt/pool/datasets/torrent-bot-logs` (or your mount path)
  - Access via: TrueNAS Scale → Storage → Browse to the dataset
  - Or via SSH: `cat /mnt/pool/datasets/torrent-bot-logs/torrent_bot.log`

### Common TrueNAS Scale UI Issues

**Issue**: Can't find "Custom App" button
- **Solution**: Ensure Apps are enabled in Settings → Apps → Settings → Enable

**Issue**: Image pull fails
- **Solution**: 
  - Check image URL is correct
  - If using private registry, add registry credentials in Apps → Settings → Registries
  - For Docker Hub, ensure image is public or add Docker Hub credentials

**Issue**: Can't edit environment variables after deployment
- **Solution**: 
  - Apps → torrent-bot → **Edit** button
  - Navigate to **Environment Variables** section
  - Add/edit/remove variables
  - Click **Save** to apply changes

**Issue**: Container keeps restarting
- **Solution**: 
  - Check logs for crash errors
  - Verify all environment variables are set correctly
  - Check resource limits aren't too low

## Updating the Bot

### Method 1: Update via TrueNAS Scale UI (Recommended)

1. **Rebuild and Push Image**:
   - If using GitHub Actions: Just push to main branch, image auto-builds
   - If manual: Build and push new image:
     ```bash
     docker build -t your-image:latest .
     docker push your-image:latest
     ```

2. **Update in TrueNAS Scale**:
   - Go to **Apps** → **Installed Applications**
   - Find `torrent-bot`
   - Click **Edit** button
   - Change **Container Image** tag (if using version tags) or ensure **Image Pull Policy** is `Always`
   - Or click **Upgrade** button if available
   - Click **Save** to apply changes
   - Container will automatically restart with new image

### Method 2: Force Pull Latest Image

1. Go to **Apps** → **Installed Applications** → `torrent-bot`
2. Click **Edit**
3. Set **Image Pull Policy** to `Always`
4. Click **Save**
5. Click **Restart** on the app

### Method 3: Redeploy with New Image Tag

1. Build and push new image with version tag:
   ```bash
   docker build -t your-image:v1.1.0 .
   docker push your-image:v1.1.0
   ```

2. In TrueNAS Scale:
   - Apps → torrent-bot → **Edit**
   - Change **Container Image** to new tag: `your-image:v1.1.0`
   - Click **Save**

## Quick Reference

### Container Images

**Docker Hub**:
```
your-username/torrent-agent:latest
```

**GitHub Container Registry**:
```
ghcr.io/your-username/torrent-agent:latest
```

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `TG_BOT_TOKEN` | Telegram bot token from @BotFather |
| `RUTRACKER_USERNAME` | Rutracker.org username |
| `RUTRACKER_PASSWORD` | Rutracker.org password |
| `QBITTORRENT_URL` | qBittorrent Web UI URL (e.g., `http://192.168.1.100:8080`) |
| `QBITTORRENT_USERNAME` | qBittorrent Web UI username |
| `QBITTORRENT_PASSWORD` | qBittorrent Web UI password |
| `GOOGLE_API_KEY` | Google Gemini API key |

### Optional Environment Variables

| Variable | Description |
|----------|-------------|
| `ALLOWED_CHAT_IDS` | Comma-separated list of allowed Telegram chat IDs |

### Network Configuration

| Network Mode | qBittorrent URL | Use Case |
|--------------|-----------------|----------|
| `Host` | `http://localhost:8080` | qBittorrent on same TrueNAS machine |
| `Bridge` | `http://your-truenas-ip:8080` | qBittorrent accessible by IP |
| `Bridge` | `http://qbittorrent-service-name:8080` | qBittorrent is also a container on same network |

### Resource Recommendations

- **CPU**: 0.5-1 core
- **Memory**: 512MB-1GB
- **Storage**: Optional volume mount for logs persistence

### Important Notes

- ✅ Do **NOT** add quotes around environment variable values
- ✅ Use `Host` network mode if qBittorrent is on the same machine
- ✅ Mount a volume to `/app/logs` for log persistence
- ✅ Set `Image Pull Policy` to `Always` for automatic updates
- ✅ Use `Restart Policy` of `Always` for auto-restart on failure

