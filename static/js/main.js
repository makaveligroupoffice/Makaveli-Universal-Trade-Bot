const canvas = document.getElementById('botCanvas');
const ctx = canvas.getContext('2d');
const chestMonitor = document.getElementById('chestMonitor');

let pnlValue = 0;
let botState = 'SCANNING';
let frame = 0;

function updateStats() {
    fetch('/api/stats')
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                pnlValue = data.daily_pnl;
                botState = data.operational_state;
                
                document.getElementById('dailyPnl').innerText = `$${pnlValue.toFixed(2)}`;
                document.getElementById('dailyPnl').className = pnlValue >= 0 ? 'text-xl font-bold text-green-400' : 'text-xl font-bold text-red-400';
                
                document.getElementById('botStatus').innerText = botState;
                document.getElementById('botStatus').className = botState === 'TRADING' ? 'text-xl font-bold text-yellow-400' : 'text-xl font-bold text-green-400';
                
                document.getElementById('accountEquity').innerText = `$${data.equity.toLocaleString()}`;
                document.getElementById('tradeCount').innerText = data.trades_today;
                if (data.sharpe_ratio) document.getElementById('sharpeRatio').innerText = data.sharpe_ratio.toFixed(2);
                if (data.profit_factor) document.getElementById('profitFactor').innerText = data.profit_factor.toFixed(2);
                document.getElementById('system-time').innerText = `LAST SYNC: ${new Date().toLocaleTimeString()}`;

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
    const token = prompt('Enter Authorization Token to confirm Kill Switch:');
    if (!token) return;
    
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
    const token = prompt('Enter Authorization Token:');
    if (!token) return;
    
    const log = document.getElementById('logFeed');
    log.innerHTML += `> AUTHORIZING BOT...<br>`;
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
    const token = prompt('Enter Current Authorization Token to authorize rotation:');
    if (!token) return;
    
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
    
    const token = prompt('Enter Authorization Token to authorize learning:');
    if (!token) return;

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
    const token = prompt('Enter Authorization Token to authorize reading session:');
    if (!token) return;

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

function investCrypto() {
    const token = prompt('Enter Authorization Token to authorize crypto investment:');
    if (!token) return;

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
    const token = prompt('Enter Authorization Token to check license:');
    if (!token) return;

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
