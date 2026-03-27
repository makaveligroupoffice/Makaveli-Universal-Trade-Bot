function withdrawProfitsToBank() {
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to confirm profit withdrawal:');
    if (!isSharingAuthorized && !token) return;
    
    if (!confirm('This will send all profits above your capital reserve to your linked bank account. CONTINUE?')) return;
    
    const log = document.getElementById('logFeed');
    log.innerHTML += `> INITIATING PROFIT WITHDRAWAL...<br>`;
    
    fetch('/api/bot/withdraw-profits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `<span class="text-green-400 font-bold">> SUCCESS: ${data.message}</span><br>`;
            updateStats();
        } else {
            log.innerHTML += `<span class="text-red-400 font-bold">> ERROR: ${data.error}</span><br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

const canvas = document.getElementById('botCanvas');
const ctx = canvas.getContext('2d');
const chestMonitor = document.getElementById('chestMonitor');

let pnlValue = 0;
let botState = 'SCANNING';
let frame = 0;
let isSharingAuthorized = false;

function updateStats() {
    fetch('/api/stats')
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                pnlValue = data.daily_pnl;
                botState = data.operational_state;
                isSharingAuthorized = data.sharing_authorized;
                
                document.getElementById('dailyPnl').innerText = `$${pnlValue.toFixed(2)}`;
                document.getElementById('dailyPnl').className = pnlValue >= 0 ? 'text-xl font-bold text-green-400' : 'text-xl font-bold text-red-400';
                
                document.getElementById('botStatus').innerText = botState;
                document.getElementById('botStatus').className = botState === 'TRADING' ? 'text-xl font-bold text-yellow-400' : 'text-xl font-bold text-green-400';
                
                document.getElementById('accountEquity').innerText = `$${data.equity.toLocaleString()}`;
                document.getElementById('tradeCount').innerText = data.trades_today;
                if (data.sharpe_ratio) document.getElementById('sharpeRatio').innerText = data.sharpe_ratio.toFixed(2);
                if (data.profit_factor) document.getElementById('profitFactor').innerText = data.profit_factor.toFixed(2);
                document.getElementById('system-time').innerText = `LAST SYNC: ${new Date().toLocaleTimeString()}`;

                // Update Master Notifications (Master Account only)
                const masterNotify = document.getElementById('masterNotifications');
                if (masterNotify) {
                    if (data.unauthorized_users && data.unauthorized_users.length > 0) {
                        masterNotify.classList.remove('hidden');
                        masterNotify.innerHTML = data.unauthorized_users.map(u => `
                            <div class="cyber-panel p-3 rounded bg-yellow-900 bg-opacity-20 border-yellow-500 animate-pulse">
                                <h2 class="text-[10px] font-bold text-yellow-500 uppercase tracking-widest">Master Notification: New User Pending</h2>
                                <p class="text-[12px] text-white">ID: ${u.id} | USER: ${u.username}</p>
                                <p class="text-[10px] text-gray-400 mt-1 uppercase">SHARING TOKEN: <span class="text-yellow-400 font-mono select-all font-bold">${u.token}</span></p>
                                <p class="text-[8px] text-gray-600 mt-1">GIVE THIS TOKEN TO THE USER TO AUTHORIZE THEIR BOT.</p>
                            </div>
                        `).join('');
                    } else {
                        masterNotify.classList.add('hidden');
                    }
                }

                // Update Withdrawal Panel
                const withdrawalPanel = document.getElementById('withdrawalPanel');
                if (data.bank_withdrawal_enabled) {
                    withdrawalPanel.classList.remove('hidden');
                    document.getElementById('withdrawableProfit').innerText = `$${data.withdrawable_profit.toFixed(2)}`;
                    document.getElementById('minReserve').innerText = `$${data.min_capital_reserve.toLocaleString()}`;
                    
                    if (data.withdrawable_profit <= 0) {
                        withdrawalPanel.classList.add('opacity-40');
                    } else {
                        withdrawalPanel.classList.remove('opacity-40');
                    }
                } else {
                    withdrawalPanel.classList.add('hidden');
                }

                // Update Mode Badges
                const modeBadge = document.getElementById('modeBadge');
                const liveSafetyBadge = document.getElementById('liveSafetyBadge');
                
                if (data.alpaca_paper) {
                    modeBadge.innerText = 'PAPER MODE';
                    modeBadge.className = 'flex-1 cyber-panel p-2 rounded text-center text-[10px] font-bold uppercase tracking-widest bg-blue-900 bg-opacity-20 border-blue-500 text-blue-400';
                } else {
                    modeBadge.innerText = 'LIVE MODE';
                    modeBadge.className = 'flex-1 cyber-panel p-2 rounded text-center text-[10px] font-bold uppercase tracking-widest bg-red-900 bg-opacity-40 border-red-500 text-red-500 glitch-text';
                }

                if (data.live_mode_enabled) {
                    liveSafetyBadge.innerText = 'LIVE ARMED';
                    liveSafetyBadge.className = 'flex-1 cyber-panel p-2 rounded text-center text-[10px] font-bold uppercase tracking-widest bg-orange-900 bg-opacity-20 border-orange-500 text-orange-500';
                } else {
                    liveSafetyBadge.innerText = 'LIVE LOCKED';
                    liveSafetyBadge.className = 'flex-1 cyber-panel p-2 rounded text-center text-[10px] font-bold uppercase tracking-widest bg-gray-900 bg-opacity-40 border-gray-700 text-gray-500';
                }

                // Update Elite Status
                const whaleValue = document.getElementById('whaleValue');
                const whaleVal = data.whale_sentiment || 0;
                if (whaleVal > 1000) {
                    whaleValue.innerText = `BULLISH (${whaleVal.toFixed(0)})`;
                    whaleValue.className = 'text-green-400 font-bold';
                } else if (whaleVal < -1000) {
                    whaleValue.innerText = `BEARISH (${whaleVal.toFixed(0)})`;
                    whaleValue.className = 'text-red-400 font-bold';
                } else {
                    whaleValue.innerText = `NEUTRAL (${whaleVal.toFixed(0)})`;
                    whaleValue.className = 'text-white';
                }

                const hedgeStatus = document.getElementById('hedgeStatus');
                if (data.hedge_active) {
                    hedgeStatus.innerText = 'ARMED (SHIELD UP)';
                    hedgeStatus.className = 'text-orange-500 font-bold glitch-text';
                } else {
                    hedgeStatus.innerText = 'INACTIVE';
                    hedgeStatus.className = 'text-green-400';
                }

                // Update Market Sentiment
                const marketSent = document.getElementById('marketSentiment');
                if (marketSent) {
                    fetch('/api/bot/sentiment?symbol=SPY')
                        .then(res => res.json())
                        .then(sdata => {
                            if (sdata.status === 'success') {
                                const s = sdata.sentiment;
                                let label = 'NEUTRAL';
                                let color = 'text-blue-400';
                                if (s > 0.6) { label = 'GREED'; color = 'text-green-400'; }
                                else if (s > 0.2) { label = 'OPTIMISTIC'; color = 'text-green-200'; }
                                else if (s < -0.6) { label = 'EXTREME FEAR'; color = 'text-red-500 glitch-text'; }
                                else if (s < -0.2) { label = 'FEAR'; color = 'text-red-400'; }
                                marketSent.innerText = `${label} (${s.toFixed(2)})`;
                                marketSent.className = `font-bold ${color}`;
                            }
                        });
                }

                // Update License Alert
                const licenseAlert = document.getElementById('licenseAlert');
                if (data.license_revoked) {
                    licenseAlert.classList.remove('hidden');
                    document.getElementById('licenseIdDisplay').innerText = `ID: ${data.license_id}`;
                    botStatus.innerText = 'REVOKED';
                    botStatus.className = 'text-xl font-bold text-red-500 glitch-text';
                    document.getElementById('botToggleButton').classList.add('opacity-50', 'pointer-events-none');
                    botState = 'REVOKED';
                } else {
                    licenseAlert.classList.add('hidden');
                    document.getElementById('botToggleButton').classList.remove('opacity-50', 'pointer-events-none');
                }

                // Update Bot Engine Toggle UI
                const isEnabled = data.bot_enabled;
                const toggleLabel = document.getElementById('botToggleLabel');
                const toggleBtn = document.getElementById('botToggleButton');
                const toggleKnob = document.getElementById('botToggleKnob');
                
                if (isEnabled) {
                    toggleLabel.innerText = 'BOT ACTIVE';
                    toggleLabel.className = 'text-xs font-bold text-green-400 uppercase';
                    toggleBtn.className = 'p-2 w-16 h-8 rounded-full border border-green-400 bg-green-900 bg-opacity-20 flex items-center justify-start transition-all duration-300 overflow-hidden';
                    toggleKnob.className = 'w-6 h-6 rounded-full bg-green-400 shadow-[0_0_5px_#0f0] transform translate-x-0 transition-transform duration-300';
                } else {
                    toggleLabel.innerText = 'BOT STOPPED';
                    toggleLabel.className = 'text-xs font-bold text-red-500 uppercase';
                    toggleBtn.className = 'p-2 w-16 h-8 rounded-full border border-red-500 bg-red-900 bg-opacity-20 flex items-center justify-end transition-all duration-300 overflow-hidden';
                    toggleKnob.className = 'w-6 h-6 rounded-full bg-red-500 shadow-[0_0_5px_#f00] transform translate-x-0 transition-transform duration-300';
                }

                // Update Positions
                const posContainer = document.getElementById('positionList');
                if (data.positions.length > 0) {
                    posContainer.innerHTML = data.positions.map(p => `
                        <div class="flex justify-between border-b border-gray-900 pb-1">
                            <span class="font-bold">${p.symbol}</span>
                            <span>${p.qty} @ $${p.entry.toFixed(2)}</span>
                            <span class="${p.pnl >= 0 ? 'text-green-400' : 'text-red-400'}">$${p.pnl.toFixed(2)}</span>
                        </div>
                    `).join('');
                } else {
                    posContainer.innerHTML = '<p class="italic text-gray-600">No active positions.</p>';
                }
            }
        });
}

function triggerAction(action) {
    const log = document.getElementById('logFeed');
    log.innerHTML += `> REQUESTING ${action.toUpperCase()}...<br>`;
    fetch('/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json()).then(data => {
        log.innerHTML += `> SERVER: ${data.message || data.error}<br>`;
        log.scrollTop = log.scrollHeight;
    });
}

function toggleBot() {
    const log = document.getElementById('logFeed');
    log.innerHTML += `> TOGGLING BOT ENGINE...<br>`;
    fetch('/api/bot/toggle', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                log.innerHTML += `> SERVER: BOT IS NOW ${data.enabled ? 'ACTIVE' : 'STOPPED'}<br>`;
                updateStats(); // Refresh UI immediately
            } else {
                log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
            }
            log.scrollTop = log.scrollHeight;
        });
}

function triggerKillSwitch() {
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to confirm Kill Switch:');
    if (!isSharingAuthorized && !token) return;
    
    if (!confirm('CRITICAL: This will stop the bot, cancel all orders, and close all positions. ARE YOU SURE?')) return;
    
    const log = document.getElementById('logFeed');
    log.innerHTML += `> TRIGGERING KILL SWITCH...<br>`;
    fetch('/api/bot/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                log.innerHTML += `> SERVER: ${data.message}<br>`;
                updateStats();
            } else {
                log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
            }
            log.scrollTop = log.scrollHeight;
        });
}

function promptAuthorization() {
    const token = prompt('Enter SHARING ACTIVATION KEY:');
    if (!token) return;
    
    const log = document.getElementById('logFeed');
    log.innerHTML += `> AUTHORIZING BOT SHARING...<br>`;
    fetch('/api/bot/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message}<br>`;
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function rotateToken() {
    let token = isSharingAuthorized ? null : prompt('Enter Current Authorization Token to authorize rotation:');
    if (!isSharingAuthorized && !token) return;
    
    if (!confirm('This will generate a new random token and update the auth file. You will need to use the NEW token next time. CONTINUE?')) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> REQUESTING TOKEN ROTATION...<br>`;
    
    fetch('/api/bot/rotate-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message}<br>`;
            alert('Token rotated successfully. Please restart the bot and check logs/auth.env for the new token.');
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function learnFromYoutube() {
    const url = prompt('Enter YouTube Video URL:');
    if (!url) return;
    
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to authorize learning:');
    if (!isSharingAuthorized && !token) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> REQUESTING YOUTUBE ANALYSIS...<br>`;
    
    fetch('/api/bot/learn-youtube', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url, token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message}<br>`;
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function deepReadingSession() {
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to authorize reading session:');
    if (!isSharingAuthorized && !token) return;

    if (!confirm('The bot will analyze 25+ classic trading books and rewrite its core strategy. This takes time. CONTINUE?')) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> STARTING DEEP READING SESSION...<br>`;
    
    fetch('/api/bot/reading-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message}<br>`;
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function setupGridTrader() {
    const symbol = prompt('Enter symbol for Grid Trading (e.g. BTC/USD, SPY):');
    if (!symbol) return;
    const price = prompt('Enter base price for Grid levels:');
    if (!price) return;
    
    let token = isSharingAuthorized ? null : prompt('Enter Master Token to authorize Grid Setup:');
    if (!isSharingAuthorized && !token) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> SETTING UP GRID FOR ${symbol} @ ${price}...<br>`;

    fetch('/api/bot/setup-grid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: symbol, price: price, token: token })
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') {
            log.innerHTML += `<span class="text-green-400 font-bold">> SUCCESS: ${data.message}</span><br>`;
        } else {
            log.innerHTML += `<span class="text-red-400 font-bold">> ERROR: ${data.message}</span><br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function investCrypto() {
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to authorize crypto investment:');
    if (!isSharingAuthorized && !token) return;

    if (!confirm('The bot will scan for long-term crypto investments and buy them based on AI analysis. CONTINUE?')) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> STARTING CRYPTO INVESTMENT SCAN...<br>`;
    
    fetch('/api/bot/invest-crypto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message}<br>`;
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

function checkLicense() {
    let token = isSharingAuthorized ? null : prompt('Enter Authorization Token to check license:');
    if (!isSharingAuthorized && !token) return;

    const log = document.getElementById('logFeed');
    log.innerHTML += `> REQUESTING REMOTE LICENSE VERIFICATION...<br>`;
    
    fetch('/api/license/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
    }).then(res => res.json()).then(data => {
        if (data.ok) {
            log.innerHTML += `> SERVER: ${data.message} (VALID: ${data.is_valid})<br>`;
            if (!data.is_valid) {
                alert("CRITICAL: LICENSE REVOKED BY SERVER!");
                location.reload();
            } else {
                alert("License is valid and active.");
            }
        } else {
            log.innerHTML += `> SERVER ERROR: ${data.error}<br>`;
        }
        log.scrollTop = log.scrollHeight;
    });
}

// BOT ANIMATION (Ported from Tkinter to Web Canvas)
function drawBot() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    frame++;

    const color = pnlValue >= 0 ? '#00ff00' : '#ff0000';
    const auraColor = pnlValue >= 0 ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 0, 0, 0.1)';
    const speed = botState === 'TRADING' ? 0.15 : 0.05;
    const breathe = Math.sin(frame * speed) * 5;

    // Aura
    for(let i=1; i<=3; i++) {
        ctx.beginPath();
        ctx.arc(200, 200, 80 + i*20 + Math.sin(frame*0.02)*10, 0, Math.PI*2);
        ctx.strokeStyle = auraColor;
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    // Head
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(170, 100 + breathe, 60, 50);

    // Eyes
    if (Math.sin(frame * 0.05) > -0.9) { // Periodic blinking
        ctx.fillStyle = color;
        ctx.fillRect(180, 115 + breathe, 10, 5);
        ctx.fillRect(210, 115 + breathe, 10, 5);
    }

    // Scan line
    const scanY = 100 + breathe + (Math.sin(frame * 0.1) * 20 + 25);
    ctx.beginPath();
    ctx.moveTo(170, scanY);
    ctx.lineTo(230, scanY);
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.5;
    ctx.stroke();
    ctx.globalAlpha = 1.0;

    // Torso
    ctx.strokeRect(160, 160 + breathe, 80, 100);
    
    // Chest Monitor Glitch Text
    if (frame % 30 < 25) {
        chestMonitor.style.color = color;
        const statuses = botState === 'TRADING' ? ['TRADE', 'EXEC', 'LIVE'] : ['SYNC', 'SCAN', 'OK'];
        chestMonitor.innerText = statuses[Math.floor(frame/20) % statuses.length];
    } else {
        chestMonitor.innerText = '----';
    }

    // Arms
    ctx.strokeRect(130, 160 + breathe, 20, 70);
    ctx.strokeRect(250, 160 + breathe, 20, 70);

    // Legs
    ctx.strokeRect(170, 260, 20, 80);
    ctx.strokeRect(210, 260, 20, 80);

    requestAnimationFrame(drawBot);
}

function updateAuditTrail() {
    fetch('/api/bot/audit-trail')
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                const trailContainer = document.getElementById('auditTrail');
                if (data.audit_trail && data.audit_trail.length > 0) {
                    const trail = [...data.audit_trail].reverse();
                    trailContainer.innerHTML = trail.map(item => {
                        const timeStr = item.timestamp ? item.timestamp.split('T')[1].split('.')[0] : '---';
                        return `<div class="border-l border-green-900 pl-1 mb-1">
                                    <span class="text-blue-500">[${timeStr}]</span> 
                                    <span class="text-white uppercase">${item.action}</span> 
                                    <span class="text-gray-500 italic">${item.reason || ''}</span>
                                </div>`;
                    }).join('');
                }
            }
        });
}

setInterval(updateStats, 2000);
setInterval(updateAuditTrail, 10000);
updateStats();
updateAuditTrail();
drawBot();
