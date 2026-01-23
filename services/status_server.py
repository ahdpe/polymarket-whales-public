"""
Flask-based Status Dashboard Server for PolymarketWhales Bot.
Provides a web interface to monitor bot status and statistics.
"""
import os
import logging
import threading
from flask import Flask, jsonify, Response

from services.status_service import get_full_status

logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Disable Flask's default logging to reduce noise
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>🐋 PolymarketWhales Status</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-yellow: #d29922;
            --accent-blue: #58a6ff;
            --accent-purple: #a371f7;
            --border-color: #30363d;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        header h1 {
            font-size: 2rem;
            margin-bottom: 5px;
        }
        
        header .subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
        }
        
        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .card-header h2 {
            font-size: 1rem;
            font-weight: 600;
        }
        
        .card-header .icon {
            margin-right: 10px;
            font-size: 1.2rem;
        }
        
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--bg-tertiary);
        }
        
        .stat-row:last-child {
            border-bottom: none;
        }
        
        .stat-label {
            color: var(--text-secondary);
        }
        
        .stat-value {
            font-weight: 500;
            font-family: 'SF Mono', Consolas, monospace;
        }
        
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .status-online {
            background: rgba(63, 185, 80, 0.2);
            color: var(--accent-green);
        }
        
        .status-offline {
            background: rgba(248, 81, 73, 0.2);
            color: var(--accent-red);
        }
        
        .status-warning {
            background: rgba(210, 153, 34, 0.2);
            color: var(--accent-yellow);
        }
        
        .progress-bar {
            background: var(--bg-tertiary);
            border-radius: 4px;
            height: 8px;
            margin-top: 5px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }
        
        .progress-green { background: var(--accent-green); }
        .progress-yellow { background: var(--accent-yellow); }
        .progress-red { background: var(--accent-red); }
        
        .wide-card {
            grid-column: 1 / -1;
        }
        
        .distribution-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }
        
        .dist-item {
            background: var(--bg-tertiary);
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }
        
        .dist-value {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--accent-blue);
        }
        
        .dist-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 5px;
        }
        
        footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 0.85rem;
        }
        
        .refresh-info {
            margin-top: 10px;
        }
        
        @media (max-width: 600px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐋 PolymarketWhales Status Dashboard</h1>
            <p class="subtitle">Real-time bot monitoring</p>
            <div style="margin-top: 15px;">
                <a href="/patterns" style="display: inline-block; padding: 8px 16px; background: var(--bg-secondary); color: var(--accent-blue); text-decoration: none; border-radius: 6px; border: 1px solid var(--border-color); font-size: 0.9rem;">
                    🕵️ View Active Patterns
                </a>
            </div>
        </header>
        
        <div class="grid" id="dashboard">
            <p style="text-align: center; color: var(--text-secondary);">Loading...</p>
        </div>
        
        <footer>
            <div>Last updated: <span id="last-update">-</span></div>
            <div class="refresh-info">Auto-refresh every 5 minutes</div>
        </footer>
    </div>
    
    <script>
        function getProgressClass(percent) {
            if (percent < 60) return 'progress-green';
            if (percent < 85) return 'progress-yellow';
            return 'progress-red';
        }
        
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        }
        
        function renderDashboard(data) {
            const sys = data.system;
            const users = data.users;
            const twitter = data.twitter;
            const db = data.databases;
            const poly = data.polymarket;
            const insider = data.insider;
            const files = data.files;
            
            const memPercent = sys.system_memory?.percent || 0;
            const memClass = getProgressClass(memPercent);
            
            let html = `
                <!-- Bot Status Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">🤖</span>
                        <h2>Bot Status</h2>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Status</span>
                        <span class="status-badge ${users.bot_enabled ? 'status-online' : 'status-offline'}">
                            ${users.bot_enabled ? '✅ Running' : '⏸️ Stopped'}
                        </span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Uptime</span>
                        <span class="stat-value">${sys.uptime_formatted || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Started</span>
                        <span class="stat-value">${sys.start_time || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">PID</span>
                        <span class="stat-value">${sys.pid || 'N/A'}</span>
                    </div>
                </div>
                
                <!-- Users Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">👥</span>
                        <h2>Users</h2>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Total</span>
                        <span class="stat-value">${users.total || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Active</span>
                        <span class="stat-value" style="color: var(--accent-green)">${users.active || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Inactive</span>
                        <span class="stat-value" style="color: var(--text-secondary)">${users.inactive || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Languages</span>
                        <span class="stat-value">EN: ${users.languages?.en || 0} | RU: ${users.languages?.ru || 0}</span>
                    </div>
                </div>
                
                <!-- Memory Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">💾</span>
                        <h2>Memory</h2>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Process RSS</span>
                        <span class="stat-value">${sys.memory?.rss_formatted || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Process %</span>
                        <span class="stat-value">${sys.memory?.percent || 0}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">System</span>
                        <span class="stat-value">${sys.system_memory?.used_formatted || 'N/A'} / ${sys.system_memory?.total_formatted || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Available</span>
                        <span class="stat-value">${sys.system_memory?.available_formatted || 'N/A'}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${memClass}" style="width: ${memPercent}%"></div>
                    </div>
                </div>
                
                <!-- Polymarket Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">📊</span>
                        <h2>Polymarket</h2>
                    </div>
                    ${poly.available ? `
                    <div class="stat-row">
                        <span class="stat-label">Trades Processed</span>
                        <span class="stat-value">${formatNumber(poly.total_processed || 0)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">LRU Cache</span>
                        <span class="stat-value">${formatNumber(poly.lru_size || 0)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Active Series</span>
                        <span class="stat-value">${poly.active_series || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Consecutive Errors</span>
                        <span class="stat-value" style="color: ${poly.consecutive_errors > 0 ? 'var(--accent-red)' : 'var(--accent-green)'}">
                            ${poly.consecutive_errors || 0}
                        </span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Last Update</span>
                        <span class="stat-value">${poly.last_update_seconds_ago !== null ? poly.last_update_seconds_ago + 's ago' : 'N/A'}</span>
                    </div>
                    ` : '<p style="color: var(--text-secondary)">Service not available</p>'}
                </div>
                
                <!-- Twitter Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">🐦</span>
                        <h2>Twitter</h2>
                    </div>
                    ${twitter.configured ? `
                    <div class="stat-row">
                        <span class="stat-label">Status</span>
                        <span class="status-badge ${twitter.enabled ? (twitter.is_paused ? 'status-warning' : 'status-online') : 'status-offline'}">
                            ${twitter.enabled ? (twitter.is_paused ? '⏸️ Paused' : '✅ Enabled') : '❌ Disabled'}
                        </span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Tweets (24h)</span>
                        <span class="stat-value">${twitter.tweets_24h || 0} / ${twitter.max_tweets_24h}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Queue</span>
                        <span class="stat-value">${twitter.queue_size || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Min Alert</span>
                        <span class="stat-value">$${formatNumber(twitter.min_alert_usd)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Insider Min</span>
                        <span class="stat-value">$${formatNumber(twitter.min_insider_usd)}</span>
                    </div>
                    ` : '<p style="color: var(--text-secondary)">Not configured</p>'}
                </div>
                
                <!-- Databases Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">🗄️</span>
                        <h2>Databases</h2>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Saved Traders</span>
                        <span class="stat-value">${db.saved_whales?.saved_count || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Trader Keys</span>
                        <span class="stat-value">${db.saved_whales?.keys_count || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Users w/ Favorites</span>
                        <span class="stat-value">${db.saved_whales?.users_with_favorites || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Seen Trades</span>
                        <span class="stat-value">${formatNumber(db.trades?.count || 0)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Trades DB Size</span>
                        <span class="stat-value">${db.trades?.size_formatted || 'N/A'}</span>
                    </div>
                </div>
                
                <!-- Twitter Filters Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">⚙️</span>
                        <h2>Twitter Filters</h2>
                    </div>
                    ${twitter.configured ? `
                    <div class="stat-row">
                        <span class="stat-label">Probability</span>
                        <span class="stat-value">${twitter.probability_filter || 'any'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Insider Age</span>
                        <span class="stat-value">≤ ${twitter.max_insider_age_days || 7} days</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Insider Positions</span>
                        <span class="stat-value">≤ ${twitter.max_insider_positions || 5}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Interval</span>
                        <span class="stat-value">${twitter.interval_minutes || 25} min</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Categories</span>
                        <span class="stat-value">
                            ${Object.entries(twitter.categories || {}).filter(([k, v]) => v).map(([k]) => k).join(', ') || 'none'}
                        </span>
                    </div>
                    ` : '<p style="color: var(--text-secondary)">Not configured</p>'}
                </div>
                
                <!-- Files Card -->
                <div class="card">
                    <div class="card-header">
                        <span class="icon">📁</span>
                        <h2>Data Files</h2>
                    </div>
                    ${Object.entries(files).filter(([k]) => k !== '_total').map(([name, info]) => `
                    <div class="stat-row">
                        <span class="stat-label">${name}</span>
                        <span class="stat-value">${info.size_formatted}</span>
                    </div>
                    `).join('')}
                    <div class="stat-row" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color);">
                        <span class="stat-label"><strong>Total</strong></span>
                        <span class="stat-value"><strong>${files._total?.size_formatted || 'N/A'}</strong></span>
                    </div>
                </div>
                
                <!-- User Settings Distribution Card -->
                <div class="card wide-card">
                    <div class="card-header">
                        <span class="icon">📈</span>
                        <h2>User Settings Distribution</h2>
                    </div>
                    <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 15px;">Threshold Distribution</h3>
                    <div class="distribution-grid">
                        ${Object.entries(users.thresholds || {}).slice(0, 8).map(([threshold, count]) => `
                        <div class="dist-item">
                            <div class="dist-value">${count}</div>
                            <div class="dist-label">$${formatNumber(parseInt(threshold))}</div>
                        </div>
                        `).join('')}
                    </div>
                    <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin: 20px 0 15px;">Categories Enabled</h3>
                    <div class="distribution-grid">
                        <div class="dist-item">
                            <div class="dist-value">${users.categories?.crypto || 0}</div>
                            <div class="dist-label">💰 Crypto</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.categories?.sports || 0}</div>
                            <div class="dist-label">⚽ Sports</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.categories?.other || 0}</div>
                            <div class="dist-label">📌 Other</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.categories?.all || 0}</div>
                            <div class="dist-label">🌐 All</div>
                        </div>
                    </div>
                    <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin: 20px 0 15px;">Side Types Enabled</h3>
                    <div class="distribution-grid">
                        <div class="dist-item">
                            <div class="dist-value">${users.side_types?.BUY || 0}</div>
                            <div class="dist-label">🟢 BUY</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.side_types?.SELL || 0}</div>
                            <div class="dist-label">🔵 SELL</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.side_types?.SPLIT || 0}</div>
                            <div class="dist-label">⚪ SPLIT</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.side_types?.MERGE || 0}</div>
                            <div class="dist-label">↔️ MERGE</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${users.side_types?.REDEEM || 0}</div>
                            <div class="dist-label">🟣 REDEEM</div>
                        </div>
                    </div>
                    <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin: 20px 0 15px;">Probability Filters</h3>
                    <div class="distribution-grid">
                        ${Object.entries(users.probabilities || {}).map(([filter, count]) => `
                        <div class="dist-item">
                            <div class="dist-value">${count}</div>
                            <div class="dist-label">${filter === 'any' ? 'Any' : filter.replace('_', '-') + '%'}</div>
                        </div>
                        `).join('')}
                    </div>
                    <div style="margin-top: 20px; display: flex; gap: 20px;">
                        <div class="stat-row" style="flex: 1;">
                            <span class="stat-label">Users with Age Filter</span>
                            <span class="stat-value">${users.age_filter_users || 0}</span>
                        </div>
                        <div class="stat-row" style="flex: 1;">
                            <span class="stat-label">Users with Positions Filter</span>
                            <span class="stat-value">${users.positions_filter_users || 0}</span>
                        </div>
                    </div>
                </div>

                <!-- Insider Intelligence Card -->
                <div class="card wide-card">
                    <div class="card-header">
                        <span class="icon">🕵️</span>
                        <h2>Insider Intelligence</h2>
                        <span class="status-badge ${(String(insider.enabled) == 'true') ? 'status-online' : 'status-offline'}" style="margin-left: auto;">
                             ${(String(insider.enabled) == 'true') ? 'Active' : 'Disabled'}
                        </span>
                    </div>
                    
                    <div class="distribution-grid" style="margin-bottom: 20px; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));">
                        <div class="dist-item">
                            <div class="dist-value" style="font-size: 1.1rem;">CLUSTER</div>
                            <div class="dist-label">${insider.scenarios?.CLUSTER?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                        </div>
                        <div class="dist-item">
                             <div class="dist-value" style="font-size: 1.1rem;">ACCUMULATION</div>
                            <div class="dist-label">${insider.scenarios?.ACCUMULATION?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                        </div>
                        <div class="dist-item">
                             <div class="dist-value" style="font-size: 1.1rem;">BURST</div>
                            <div class="dist-label">${insider.scenarios?.BURST?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                        </div>
                    </div>


                    <div style="text-align: center; padding: 20px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-tertiary);">
                        <p style="margin-bottom: 15px; color: var(--text-secondary);">
                            Active patterns tables moved to separate page
                        </p>
                        <a href="/patterns" style="display: inline-block; padding: 10px 20px; background: var(--accent-blue); color: white; text-decoration: none; border-radius: 6px; font-weight: 500;">
                            View Active Patterns →
                        </a>
                        <div style="margin-top: 15px; font-size: 0.85rem; color: var(--text-secondary);">
                            CLUSTERS: ${insider.pending_patterns?.clusters?.length || 0} | 
                            ACCUMULATIONS: ${insider.pending_patterns?.accumulations?.length || 0} | 
                            BURSTS: ${insider.pending_patterns?.bursts?.length || 0}
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('dashboard').innerHTML = html;
            document.getElementById('last-update').textContent = data.timestamp;
        }
        
        async function loadData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                renderDashboard(data);
            } catch (error) {
                console.error('Failed to load data:', error);
                document.getElementById('dashboard').innerHTML = 
                    '<p style="text-align: center; color: var(--accent-red);">Failed to load data. Retrying...</p>';
            }
        }
        
        // Initial load
        loadData();
    </script>
</body>
</html>
"""


PATTERNS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>🕵️ Active Patterns - PolymarketWhales</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-green: #3fb950;
            --accent-red: #f85149;
            --accent-yellow: #d29922;
            --accent-blue: #58a6ff;
            --accent-purple: #a371f7;
            --border-color: #30363d;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        header h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }
        
        .nav-link {
            display: inline-block;
            margin-top: 10px;
            padding: 8px 16px;
            background: var(--bg-secondary);
            color: var(--accent-blue);
            text-decoration: none;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }
        
        .nav-link:hover {
            background: var(--bg-tertiary);
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section-header {
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .section-header h2 {
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .section-settings {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.6;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .settings-group {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        
        .settings-group strong {
            color: var(--text-primary);
            font-weight: 500;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }
        
        thead {
            background: var(--bg-tertiary);
        }
        
        th {
            padding: 12px;
            text-align: left;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 2px solid var(--border-color);
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid var(--bg-tertiary);
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        tr:hover {
            background: var(--bg-tertiary);
        }
        
        .wallet-link {
            color: #4facfe;
            text-decoration: none;
            border-bottom: 1px dotted #4facfe;
            font-family: monospace;
            font-size: 0.85rem;
        }
        
        .wallet-link:hover {
            color: #6bc5ff;
        }
        
        .status-good {
            color: var(--accent-green);
        }
        
        .status-warning {
            color: var(--accent-yellow);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
            font-style: italic;
        }
        
        .status-section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        .status-section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .status-section-header h2 {
            font-size: 1.3rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .scenarios-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .scenario-item {
            background: var(--bg-tertiary);
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }
        
        .scenario-name {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 5px;
        }
        
        .scenario-status {
            font-size: 0.9rem;
        }
        
        footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🕵️ Active Insider Patterns</h1>
            <p style="color: var(--text-secondary); margin-top: 5px;">Real-time monitoring of emerging trading patterns</p>
            <a href="/" class="nav-link">← Back to Dashboard</a>
        </header>
        
        <div id="patterns-content">
            <p style="text-align: center; color: var(--text-secondary);">Loading...</p>
        </div>
        
        <footer>
            <div>Last updated: <span id="last-update">-</span></div>
            <div style="margin-top: 5px;">Auto-refresh every 5 minutes</div>
        </footer>
    </div>
    
    <script>
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        }
        
        function formatSettings(scenario) {
            if (!scenario) return '';
            
            const parts = [];
            
            // Volume group
            if (scenario.min_usd && scenario.min_total) {
                parts.push(`<span class="settings-group">💰 <strong>Volume:</strong> $${formatNumber(parseInt(scenario.min_usd))} min, $${formatNumber(parseInt(scenario.min_total))} total</span>`);
            }
            
            // Wallets group
            const walletParts = [];
            if (scenario.min_wallets) {
                walletParts.push(`${scenario.min_wallets} min`);
            }
            if (scenario.max_age) {
                const hours = parseInt(scenario.max_age);
                const days = Math.floor(hours / 24);
                const remainingHours = hours % 24;
                let ageStr = '';
                if (days > 0) {
                    ageStr = days + 'd';
                    if (remainingHours > 0) ageStr += ' ' + remainingHours + 'h';
                } else {
                    ageStr = hours + 'h';
                }
                walletParts.push(`≤${ageStr} age`);
            }
            if (walletParts.length > 0) {
                parts.push(`<span class="settings-group">👥 <strong>Wallets:</strong> ${walletParts.join(', ')}</span>`);
            }
            
            // Direction group
            const dirParts = [];
            if (scenario.min_dir) {
                dirParts.push(`${scenario.min_dir}%`);
            }
            if (scenario.side && scenario.side !== 'both') {
                dirParts.push(scenario.side.toLowerCase());
            }
            if (dirParts.length > 0) {
                parts.push(`<span class="settings-group">🎯 <strong>Direction:</strong> ${dirParts.join(', ')}</span>`);
            }
            
            // Positions group
            if (scenario.max_pos) {
                parts.push(`<span class="settings-group">📍 <strong>Positions:</strong> ≤${scenario.max_pos}</span>`);
            }
            
            // Interval (for CLUSTER and BURST)
            if (scenario.interval) {
                parts.push(`<span class="settings-group">⏱️ <strong>Interval:</strong> ${scenario.interval}h</span>`);
            }
            
            // Min days (for ACCUMULATION)
            if (scenario.min_days) {
                parts.push(`<span class="settings-group">📅 <strong>Min days:</strong> ${scenario.min_days}</span>`);
            }
            
            return parts.length > 0 ? `<div class="section-settings">${parts.join(' | ')}</div>` : '';
        }
        
        function renderPatterns(data) {
            const insider = data.insider;
            const patterns = insider.pending_patterns || {};
            const scenarios = insider.scenarios || {};
            
            let html = '';
            
            // Insider Intelligence Status Section
            if (insider && insider.scenarios) {
                const isEnabled = String(insider.enabled) === 'true';
                html += `
                    <div class="status-section">
                        <div class="status-section-header">
                            <h2>
                                <span>🕵️</span>
                                <span>Insider Intelligence</span>
                            </h2>
                            <span class="status-badge ${isEnabled ? 'status-online' : 'status-offline'}">
                                ${isEnabled ? 'Active' : 'Disabled'}
                            </span>
                        </div>
                        <div class="scenarios-grid">
                            <div class="scenario-item">
                                <div class="scenario-name">CLUSTER</div>
                                <div class="scenario-status">${scenarios.CLUSTER?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                            <div class="scenario-item">
                                <div class="scenario-name">ACCUMULATION</div>
                                <div class="scenario-status">${scenarios.ACCUMULATION?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                            <div class="scenario-item">
                                <div class="scenario-name">BURST</div>
                                <div class="scenario-status">${scenarios.BURST?.enabled == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // CLUSTERS
            if (patterns.clusters && patterns.clusters.length > 0) {
                const clusterSettings = formatSettings(scenarios.CLUSTER);
                html += `
                    <div class="section">
                        <div class="section-header">
                            <h2>Active CLUSTERS (${patterns.clusters.length})</h2>
                            ${clusterSettings}
                        </div>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Market</th>
                                        <th>Wallets</th>
                                        <th>Volume</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                        <th>Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${patterns.clusters.map(p => `
                                    <tr>
                                        <td>${p.title.substring(0, 50) + (p.title.length > 50 ? '...' : '')}</td>
                                        <td>
                                            <span class="${p.wallets >= p.min_wallets ? 'status-good' : 'status-warning'}">
                                                ${p.wallets} / ${p.min_wallets}
                                            </span>
                                        </td>
                                        <td>
                                            <span class="${p.volume >= p.min_total ? 'status-good' : ''}">
                                                $${formatNumber(p.volume)}
                                            </span>
                                        </td>
                                        <td>
                                            ${(p.wallet_list || []).map(w => 
                                                `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${w.substring(0,5)}..${w.substring(39)}</a>`
                                            ).join(', ')}
                                        </td>
                                        <td style="color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            // ACCUMULATIONS
            if (patterns.accumulations && patterns.accumulations.length > 0) {
                const accumulationSettings = formatSettings(scenarios.ACCUMULATION);
                html += `
                    <div class="section">
                        <div class="section-header">
                            <h2>Active ACCUMULATIONS (${patterns.accumulations.length})</h2>
                            ${accumulationSettings}
                        </div>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Market</th>
                                        <th>Days</th>
                                        <th>Wallets</th>
                                        <th>Volume</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                        <th>Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${patterns.accumulations.map(p => `
                                    <tr>
                                        <td>${p.title.substring(0, 50) + (p.title.length > 50 ? '...' : '')}</td>
                                        <td>
                                            <span class="${p.days >= p.min_days ? 'status-good' : 'status-warning'}">
                                                ${p.days} / ${p.min_days}
                                            </span>
                                        </td>
                                        <td>
                                            <span class="${p.wallets >= p.min_wallets ? 'status-good' : 'status-warning'}">
                                                ${p.wallets} / ${p.min_wallets}
                                            </span>
                                        </td>
                                        <td>$${formatNumber(p.volume)}</td>
                                        <td>
                                            ${(p.wallet_list || []).map(w => 
                                                `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${w.substring(0,5)}..${w.substring(39)}</a>`
                                            ).join(', ')}
                                        </td>
                                        <td style="color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            // BURSTS
            if (patterns.bursts && patterns.bursts.length > 0) {
                const burstSettings = formatSettings(scenarios.BURST);
                html += `
                    <div class="section">
                        <div class="section-header">
                            <h2>Active BURSTS (${patterns.bursts.length})</h2>
                            ${burstSettings}
                        </div>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Market</th>
                                        <th>Wallets</th>
                                        <th>Volume</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                        <th>Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${patterns.bursts.map(p => `
                                    <tr>
                                        <td>${p.title.substring(0, 50) + (p.title.length > 50 ? '...' : '')}</td>
                                        <td>
                                            <span class="${p.wallets >= p.min_wallets ? 'status-good' : 'status-warning'}">
                                                ${p.wallets} / ${p.min_wallets}
                                            </span>
                                        </td>
                                        <td>
                                            <span class="${p.volume >= p.min_total ? 'status-good' : ''}">
                                                $${formatNumber(p.volume)}
                                            </span>
                                        </td>
                                        <td>
                                            ${(p.wallet_list || []).map(w => 
                                                `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${w.substring(0,5)}..${w.substring(39)}</a>`
                                            ).join(', ')}
                                        </td>
                                        <td style="color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            // Recently Published Alerts Table
            if (insider && insider.published_history && insider.published_history.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-header">
                            <h2>Recently Published Alerts (Last 20)</h2>
                        </div>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Scenario</th>
                                        <th>Market</th>
                                        <th>Outcome</th>
                                        <th>Volume</th>
                                        <th>Wallets</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${insider.published_history.map(p => `
                                    <tr>
                                        <td style="color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.timestamp)/60)}m ago
                                        </td>
                                        <td>
                                            <span class="status-badge status-online" style="font-size: 0.75rem;">${p.scenario}</span>
                                        </td>
                                        <td>
                                            <a href="https://polymarket.com/event/${p.market_id}" target="_blank" style="color: var(--text-primary); text-decoration: none;">
                                                ${(p.market_title || p.market_id).substring(0, 50) + ((p.market_title || p.market_id).length > 50 ? '...' : '')}
                                            </a>
                                        </td>
                                        <td>${p.outcome || '-'}</td>
                                        <td>$${formatNumber(p.total_volume || 0)}</td>
                                        <td>${p.participants_count || '-'}</td>
                                        <td>
                                            ${(p.wallet_list && p.wallet_list.length > 0) ? p.wallet_list.map(w => 
                                                `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${w.substring(0,5)}..${w.substring(39)}</a>`
                                            ).join(', ') : '-'}
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            }
            
            if (!html || (html.includes('status-section') && !patterns.clusters?.length && !patterns.accumulations?.length && !patterns.bursts?.length && !insider?.published_history?.length)) {
                if (!html || !html.includes('status-section')) {
                    html = '<div class="empty-state">No emerging patterns detected currently.</div>';
                } else if (!insider?.published_history?.length) {
                    html += '<div class="empty-state">No alerts published yet.</div>';
                }
            }
            
            document.getElementById('patterns-content').innerHTML = html;
            document.getElementById('last-update').textContent = data.timestamp;
        }
        
        async function loadData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                renderPatterns(data);
            } catch (error) {
                console.error('Failed to load data:', error);
                document.getElementById('patterns-content').innerHTML = 
                    '<div class="empty-state" style="color: var(--accent-red);">Failed to load data. Retrying...</div>';
            }
        }
        
        // Initial load
        loadData();
        
        // Auto-refresh
        setInterval(loadData, 300000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve the dashboard HTML page."""
    return Response(HTML_TEMPLATE, mimetype='text/html')


@app.route('/patterns')
def patterns():
    """Serve the active patterns page."""
    return Response(PATTERNS_TEMPLATE, mimetype='text/html')


@app.route('/api/status')
def api_status():
    """Return full status as JSON."""
    return jsonify(get_full_status())


def run_server(port=5000, host='0.0.0.0'):
    """Run Flask server in a separate thread."""
    def run():
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"Status dashboard started on http://{host}:{port}")
    return thread


def start_status_server(port=5000):
    """Start the status dashboard server."""
    return run_server(port=port)
