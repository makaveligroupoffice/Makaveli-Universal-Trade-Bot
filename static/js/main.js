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
                document.getElementById('system-time').innerText = `LAST SYNC: ${new Date().toLocaleTimeString()}`;

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

setInterval(updateStats, 2000);
updateStats();
drawBot();
