### Deployment & Syncing Guide (MacBook ↔ VPS)

This guide explains how to keep your MacBook development environment and your DigitalOcean VPS in sync while ensuring the bot can self-update.

#### 1. Repository Setup
The bot uses Git for syncing. Ensure your project is a Git repository:
```bash
git init
git add .
git commit -m "Initial commit"
```

#### 2. Remote Synchronization (GitHub/GitLab)
To sync between MacBook and VPS, use a private remote repository:
1. Create a **Private** repository on GitHub.
2. Add the remote on your MacBook:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```
3. On the VPS, clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
   ```

#### 3. Automatic Updates on VPS
The bot is configured to check for updates every hour.
- **How it works**: The bot runs `git pull --rebase` automatically.
- **Conflicts**: The bot will `stash` any local changes before pulling to prevent conflicts.
- **Restarting**: Since we are using **PM2** with `watch: true`, the bot will automatically restart as soon as `git pull` updates the source files.

#### 4. Workflow for Updates
1. **Develop on MacBook**: Make changes to `strategy.py`, `config.py`, etc.
2. **Test locally**: Run the bot on your MacBook to verify changes.
3. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Update strategy parameters"
   git push origin main
   ```
4. **VPS Sync**: Within an hour (or immediately if you restart the bot on VPS), the VPS instance will pull these changes and restart itself.

#### 5. Data Isolation
The following files are ignored by Git (`.gitignore`) and will **NOT** be synced:
- `.env` (Unique secrets per environment)
- `instance/users.db` (User database)
- `logs/` (All log files)
- `*.json` (State files)

This ensures that trading data on your VPS doesn't overwrite your MacBook data and vice versa.

#### 6. Production Server (Gunicorn & Nginx)
For stability and security, the Web HUD should be run using Gunicorn and Nginx:
1. **Gunicorn**: Manages multiple Python worker processes for the Flask app.
   - Configured in `com.tradebot.webhook.plist` to run with 4 workers.
2. **Nginx**: Acts as a reverse proxy, handling incoming traffic and forwarding it to Gunicorn.
   - Installed via Homebrew: `brew install nginx`
   - Configured in `/opt/homebrew/etc/nginx/servers/tradebot.conf`
   - Listens on port `8080` (proxying to `5001`).
   - Supports `X-Forwarded-For` for accurate IP whitelisting.

#### 7. Manual Update Trigger (VPS)
If you want to apply changes immediately on the VPS:
```bash
pm2 restart tradebot-runner
```
The bot checks for updates on every startup.
