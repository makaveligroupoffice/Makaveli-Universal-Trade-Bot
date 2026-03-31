module.exports = {
  apps : [{
    name: 'tradebot-web',
    script: 'app.py',
    interpreter: 'python3',
    env: {
      NODE_ENV: 'development',
    },
    env_production: {
      NODE_ENV: 'production',
    },
    watch: true,
    ignore_watch: ["logs/*", "instance/*", ".git/*", "*.log", "*.json", "*.jsonl"],
    max_memory_restart: '1G',
  }, {
    name: 'tradebot-runner',
    script: 'bot_runner.py',
    interpreter: 'python3',
    args: '--all-users', // Hypothetical flag for future multi-user runner
    watch: true,
    ignore_watch: ["logs/*", "instance/*", ".git/*", "*.log", "*.json", "*.jsonl"],
    max_memory_restart: '1G',
    restart_delay: 5000,
  }]
};
