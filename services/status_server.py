"""
Flask-based Status Dashboard Server for PolymarketWhales Bot.
Provides a web interface to monitor bot status and statistics.
"""
import os
import hmac
import json
import logging
import threading
from flask import Flask, jsonify, Response, request

from services.status_service import get_full_status, get_whale_trades

logger = logging.getLogger(__name__)


def _insider_scenario_check_interval_sec() -> int:
    """Must match main.py check_insider_scenarios_periodically() default."""
    return max(60, int(os.getenv("INSIDER_SCENARIO_CHECK_INTERVAL_SEC", "900")))


def _insider_refresh_interval_human() -> str:
    sec = _insider_scenario_check_interval_sec()
    if sec % 3600 == 0:
        h = sec // 3600
        return f"{h} hour{'s' if h != 1 else ''}"
    if sec % 60 == 0:
        m = sec // 60
        return f"{m} minute{'s' if m != 1 else ''}"
    return f"{sec} seconds"


def _apply_insider_refresh_to_html(html: str) -> str:
    """Substitute meta refresh, footer text, and JS poll interval from env."""
    sec = _insider_scenario_check_interval_sec()
    ms = sec * 1000
    human = _insider_refresh_interval_human()
    return (
        html.replace("__INSIDER_REFRESH_META_SEC__", str(sec))
        .replace("__INSIDER_JS_REFRESH_MS__", str(ms))
        .replace("__INSIDER_REFRESH_HUMAN__", human)
    )


def _safe_inline_json(payload: dict | None) -> str:
    """Serialize JSON safely for inline <script> embedding."""
    if payload is None:
        return "null"
    # Prevent accidental script tag termination in HTML parser.
    return (
        json.dumps(payload, ensure_ascii=True)
        .replace("</", "<\\/")
        # Avoid breaking inline script parsing on JS line-separator chars.
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


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
    <meta name="robots" content="noindex, nofollow">
    <meta http-equiv="refresh" content="__INSIDER_REFRESH_META_SEC__">
    <title>🐋 PolymarketWhales Status</title>
    <link rel="icon" type="image/png" href="/favicon.png?v=4">
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
            <div style="display: none;">Last updated: <span id="last-update">-</span></div>
            <div class="refresh-info">Auto-refresh every __INSIDER_REFRESH_HUMAN__</div>
        </footer>
    </div>
    
    <script>
        window.__EMBEDDED_PATTERNS__ = __EMBEDDED_PATTERNS_JSON__;
    </script>
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
            
            const memPercent = (sys.system_memory ? sys.system_memory.percent : 0) || 0;
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
                        <span class="stat-label">⏸️ Paused</span>
                        <span class="stat-value" style="color: var(--text-secondary)">${users.paused || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">🛑 Blocked</span>
                        <span class="stat-value" style="color: #ff6b6b">${users.blocked || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Languages</span>
                        <span class="stat-value">EN: ${(users.languages ? users.languages.en : 0) || 0} | RU: ${(users.languages ? users.languages.ru : 0) || 0}</span>
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
                        <span class="stat-value">${(sys.memory ? sys.memory.rss_formatted : 'N/A') || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Process %</span>
                        <span class="stat-value">${(sys.memory ? sys.memory.percent : 0) || 0}%</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">System</span>
                        <span class="stat-value">${(sys.system_memory ? sys.system_memory.used_formatted : 'N/A') || 'N/A'} / ${(sys.system_memory ? sys.system_memory.total_formatted : 'N/A') || 'N/A'}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Available</span>
                        <span class="stat-value">${(sys.system_memory ? sys.system_memory.available_formatted : 'N/A') || 'N/A'}</span>
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
                        <span class="stat-value">${(db.saved_whales ? db.saved_whales.saved_count : 0) || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Trader Keys</span>
                        <span class="stat-value">${(db.saved_whales ? db.saved_whales.keys_count : 0) || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Users w/ Favorites</span>
                        <span class="stat-value">${(db.saved_whales ? db.saved_whales.users_with_favorites : 0) || 0}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Seen Trades</span>
                        <span class="stat-value">${formatNumber((db.trades ? db.trades.count : 0) || 0)}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Trades DB Size</span>
                        <span class="stat-value">${(db.trades ? db.trades.size_formatted : 'N/A') || 'N/A'}</span>
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
                        <span class="stat-value"><strong>${(files._total ? files._total.size_formatted : 'N/A') || 'N/A'}</strong></span>
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
                            <div class="dist-value">${(users.categories ? users.categories.crypto : 0) || 0}</div>
                            <div class="dist-label">💰 Crypto</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.categories ? users.categories.sports : 0) || 0}</div>
                            <div class="dist-label">⚽ Sports</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.categories ? users.categories.other : 0) || 0}</div>
                            <div class="dist-label">📌 Other</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.categories ? users.categories.all : 0) || 0}</div>
                            <div class="dist-label">🌐 All</div>
                        </div>
                    </div>
                    <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin: 20px 0 15px;">Side Types Enabled</h3>
                    <div class="distribution-grid">
                        <div class="dist-item">
                            <div class="dist-value">${(users.side_types ? users.side_types.BUY : 0) || 0}</div>
                            <div class="dist-label">🟢 BUY</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.side_types ? users.side_types.SELL : 0) || 0}</div>
                            <div class="dist-label">🔵 SELL</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.side_types ? users.side_types.SPLIT : 0) || 0}</div>
                            <div class="dist-label">⚪ SPLIT</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.side_types ? users.side_types.MERGE : 0) || 0}</div>
                            <div class="dist-label">↔️ MERGE</div>
                        </div>
                        <div class="dist-item">
                            <div class="dist-value">${(users.side_types ? users.side_types.REDEEM : 0) || 0}</div>
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
                            <div class="dist-label">${((insider.scenarios && insider.scenarios.CLUSTER) ? insider.scenarios.CLUSTER.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
                        </div>
                        <div class="dist-item">
                             <div class="dist-value" style="font-size: 1.1rem;">ACCUMULATION</div>
                            <div class="dist-label">${((insider.scenarios && insider.scenarios.ACCUMULATION) ? insider.scenarios.ACCUMULATION.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
                        </div>
                        <div class="dist-item">
                             <div class="dist-value" style="font-size: 1.1rem;">BURST</div>
                            <div class="dist-label">${((insider.scenarios && insider.scenarios.BURST) ? insider.scenarios.BURST.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
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
                            CLUSTERS: ${((insider.pending_patterns && insider.pending_patterns.clusters) ? insider.pending_patterns.clusters.length : 0) || 0} | 
                            ACCUMULATIONS: ${((insider.pending_patterns && insider.pending_patterns.accumulations) ? insider.pending_patterns.accumulations.length : 0) || 0} | 
                            BURSTS: ${((insider.pending_patterns && insider.pending_patterns.bursts) ? insider.pending_patterns.bursts.length : 0) || 0}
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('dashboard').innerHTML = html;
            document.getElementById('last-update').textContent = data.timestamp;
        }
        
        async function loadData() {
            try {
                // Try using pre-embedded data first
                if (window.__EMBEDDED_STATUS__) {
                    renderDashboard(window.__EMBEDDED_STATUS__);
                    window.__EMBEDDED_STATUS__ = null;
                    return;
                }
                const token = new URLSearchParams(window.location.search).get('token');
                const apiUrl = token ? `/api/status?token=${encodeURIComponent(token)}` : '/api/status';
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000);
                const response = await fetch(apiUrl, { signal: controller.signal });
                clearTimeout(timeoutId);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
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
    <meta name="robots" content="noindex, nofollow">
    <meta http-equiv="refresh" content="__INSIDER_REFRESH_META_SEC__">
    <title>🕵️ Active Patterns - PolymarketWhales</title>
    <link rel="icon" type="image/png" href="/favicon.png?v=4">
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
            <div style="display: none;">Last updated: <span id="last-update">-</span></div>
            <div style="margin-top: 5px;">Auto-refresh every __INSIDER_REFRESH_HUMAN__</div>
        </footer>
    </div>
    
    <script>
        window.__EMBEDDED_PATTERNS__ = __EMBEDDED_PATTERNS_JSON__;
    </script>
    <script>
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        }
        
        function formatSettings(scenario, type) {
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
            
            // Interval (for CLUSTER, BURST, and ACCUMULATION)
            if (scenario.interval) {
                // For ACCUMULATION, interval is in days; for others, in hours
                const isAccumulation = type === 'ACCUMULATION';
                const unit = isAccumulation ? 'd' : 'h';
                parts.push(`<span class="settings-group">⏱️ <strong>Interval:</strong> ${scenario.interval}${unit}</span>`);
            }
            
            return parts.length > 0 ? `<div class="section-settings">${parts.join(' | ')}</div>` : '';
        }

        function toMinutesAgo(ts) {
            if (!ts) return 'N/A';
            const now = Date.now() / 1000;
            const diffSec = Math.max(0, Math.floor(now - ts));
            const min = 60;
            const hour = 3600;
            const day = 86400;
            const week = 7 * day;
            const month = 30 * day;

            if (diffSec < hour) return Math.floor(diffSec / min) + 'm ago';
            if (diffSec < day) return Math.floor(diffSec / hour) + 'h ago';
            if (diffSec < week) return Math.floor(diffSec / day) + 'd ago';
            if (diffSec < month) return Math.floor(diffSec / week) + 'w ago';

            const d = new Date(ts * 1000);
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
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
                                <div class="scenario-status">${((scenarios.CLUSTER) ? scenarios.CLUSTER.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                            <div class="scenario-item">
                                <div class="scenario-name">ACCUMULATION</div>
                                <div class="scenario-status">${((scenarios.ACCUMULATION) ? scenarios.ACCUMULATION.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                            <div class="scenario-item">
                                <div class="scenario-name">BURST</div>
                                <div class="scenario-status">${((scenarios.BURST) ? scenarios.BURST.enabled : false) == 'true' ? '✅ On' : '❌ Off'}</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // CLUSTERS
            if (patterns.clusters && patterns.clusters.length > 0) {
                const clusterSettings = formatSettings(scenarios.CLUSTER, 'CLUSTER');
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
                                        <th>Why not published</th>
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
                                            ${toMinutesAgo(p.last_ts)}
                                        </td>
                                        <td style="color: var(--text-secondary); font-size: 0.9rem;">
                                            ${p.blocked_reason || '—'}
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
                const accumulationSettings = formatSettings(scenarios.ACCUMULATION, 'ACCUMULATION');
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
                                        <th>Wallets</th>
                                        <th>Volume</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                        <th>Last Activity</th>
                                        <th>Why not published</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${patterns.accumulations.map(p => `
                                    <tr>
                                        <td>${p.title.substring(0, 50) + (p.title.length > 50 ? '...' : '')}</td>
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
                                            ${toMinutesAgo(p.last_ts)}
                                        </td>
                                        <td style="color: var(--text-secondary); font-size: 0.9rem;">
                                            ${p.blocked_reason || '—'}
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
                                        <th>Why not published</th>
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
                                            ${toMinutesAgo(p.last_ts)}
                                        </td>
                                        <td style="color: var(--text-secondary); font-size: 0.9rem;">
                                            ${p.blocked_reason || '—'}
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
                // Pagination state for admin page
                window.currentPagePublishedAdmin = window.currentPagePublishedAdmin || 1;
                const itemsPerPage = 20;
                const items = insider.published_history;
                
                const totalPages = Math.ceil(items.length / itemsPerPage);
                if (window.currentPagePublishedAdmin > totalPages) window.currentPagePublishedAdmin = Math.max(1, totalPages);
                
                const startIdx = (window.currentPagePublishedAdmin - 1) * itemsPerPage;
                const currentItems = items.slice(startIdx, startIdx + itemsPerPage);

                html += `
                    <div class="section">
                        <div class="section-header">
                            <h2>Recently Published Alerts (${items.length} total)</h2>
                        </div>
                        <div style="overflow-x: auto;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Scenario</th>
                                        <th>Market</th>
                                        <th>Outcome</th>
                                        <th>Result</th>
                                        <th>Volume</th>
                                        <th>Wallets</th>
                                        <th style="width: 35%;">Buffer Participants</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${currentItems.map(p => `
                                    <tr>
                                        <td style="color: var(--text-secondary);">
                                            ${toMinutesAgo(p.timestamp)}
                                        </td>
                                        <td>
                                            <span class="status-badge status-online" style="font-size: 0.75rem;">${p.scenario}</span>
                                        </td>
                                        <td>
                                            <a href="https://polymarket.com/event/${p.event_slug || p.market_id}" target="_blank" style="color: var(--text-primary); text-decoration: none;">
                                                ${(p.market_title || p.market_id).substring(0, 50) + ((p.market_title || p.market_id).length > 50 ? '...' : '')}
                                            </a>
                                        </td>
                                        <td>${p.outcome || '-'}</td>
                                        <td>
                                            ${p.result_status === 'win' ? '<span title="In Profit / Won">✅</span>' : 
                                              p.result_status === 'loss' ? '<span title="In Loss / Lost">❌</span>' : 
                                              '<span title="Pending">⏳</span>'}
                                        </td>
                                        <td>$${formatNumber(p.total_volume || 0)}</td>
                                        <td>${p.participants_count || '-'}</td>
                                        <td>
                                            ${renderWalletsWithAppendedAdmin(p)}
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                `;
                
                if (totalPages > 1) {
                    html += `
                        <div class="pagination" style="margin-top: 15px; display: flex; justify-content: center; align-items: center; gap: 10px;">
                            <button onclick="window.changePubPageAdmin(-1)" ${window.currentPagePublishedAdmin === 1 ? 'disabled' : ''} style="padding: 6px 12px; font-size: 13px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 4px; cursor: ${window.currentPagePublishedAdmin === 1 ? 'not-allowed' : 'pointer'}; opacity: ${window.currentPagePublishedAdmin === 1 ? '0.5' : '1'};">Previous</button>
                            <span style="font-size: 13px; color: var(--text-secondary);">Page ${window.currentPagePublishedAdmin} of ${totalPages}</span>
                            <button onclick="window.changePubPageAdmin(1)" ${window.currentPagePublishedAdmin >= totalPages ? 'disabled' : ''} style="padding: 6px 12px; font-size: 13px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 4px; cursor: ${window.currentPagePublishedAdmin >= totalPages ? 'not-allowed' : 'pointer'}; opacity: ${window.currentPagePublishedAdmin >= totalPages ? '0.5' : '1'};">Next</button>
                        </div>
                    `;
                }
                
                html += `</div>`;
            }
            
            if (!html || (html.includes('status-section') && !(patterns.clusters && patterns.clusters.length) && !(patterns.accumulations && patterns.accumulations.length) && !(patterns.bursts && patterns.bursts.length) && !(insider && insider.published_history && insider.published_history.length))) {
                if (!html || !html.includes('status-section')) {
                    html = '<div class="empty-state">No emerging patterns detected currently.</div>';
                } else if (!(insider && insider.published_history && insider.published_history.length)) {
                    html += '<div class="empty-state">No alerts published yet.</div>';
                }
            }
            
            document.getElementById('patterns-content').innerHTML = html;
            document.getElementById('last-update').textContent = data.timestamp;
        }

        function renderWalletsWithAppendedAdmin(p) {
            const original = p.original_wallet_list || [];
            const appendedInfo = p.appended_wallets_info || {};
            const allWallets = p.wallet_list || [];
            
            if (allWallets.length === 0) return '-';

            const originalSet = new Set(original);
            const appendedWallets = allWallets.filter(w => !originalSet.has(w));
            
            let html = '';
            
            if (appendedWallets.length > 0) {
                let yesCount = 0;
                let noCount = 0;
                appendedWallets.forEach(w => {
                    if (appendedInfo[w] === 'YES') yesCount++;
                    else if (appendedInfo[w] === 'NO') noCount++;
                });
                
                const stats = [];
                if (yesCount > 0) stats.push(`<span style="color: #34d399">${yesCount} YES</span>`);
                if (noCount > 0) stats.push(`<span style="color: #fb7185">${noCount} NO</span>`);
                
                html += `<div style="font-size: 0.75rem; margin-bottom: 4px; color: #888;">+${appendedWallets.length} since signal (${stats.join(' / ')})</div>`;
            }

            const originalWallets = allWallets.filter(w => originalSet.has(w));
            const appendedWalletsReversed = [...appendedWallets].reverse();
            
            const originalHtml = originalWallets.map(w => {
                return `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${w.substring(0,5)}..${w.substring(39)}</a>`;
            }).join(', ');
            
            const appendedHtml = appendedWalletsReversed.map(w => {
                const outcome = appendedInfo[w];
                let prefix = '';
                if (outcome === 'YES') prefix = '🟢 ';
                else if (outcome === 'NO') prefix = '🔴 ';
                return `<a href="https://polymarket.com/profile/${w}" target="_blank" class="wallet-link">${prefix}${w.substring(0,5)}..${w.substring(39)}</a>`;
            }).join(', ');
            
            html += originalHtml;
            if (appendedHtml) {
                html += (originalHtml ? `<div style="margin-top: 4px;">` : `<div>`) + appendedHtml + `</div>`;
            }
            
            return html;
        }

        function normalizePatternsPayload(data) {
            if (data && data.insider) {
                return data;
            }
            return {
                timestamp: data && data.timestamp ? data.timestamp : null,
                insider: {
                    enabled: data && data.enabled !== undefined ? data.enabled : true,
                    pending_patterns: (data && data.patterns) || {},
                    scenarios: (data && data.scenarios) || {},
                    published_history: (data && data.recent_published) || []
                }
            };
        }

        function safeRenderPatterns(data) {
            try {
                renderPatterns(data);
                return true;
            } catch (err) {
                console.error('renderPatterns failed:', err);
                const insider = (data && data.insider) || {};
                const pending = insider.pending_patterns || {};
                const clusters = (pending.clusters || []).length;
                const accumulations = (pending.accumulations || []).length;
                const bursts = (pending.bursts || []).length;
                document.getElementById('patterns-content').innerHTML =
                    `<div class="empty-state" style="color: var(--accent-red);">
                        Failed to render patterns (${(err && err.message) ? err.message : 'unknown error'}).
                        <div style="margin-top:8px;color:var(--text-secondary);font-size:0.9rem;">
                            Data snapshot: CLUSTERS ${clusters}, ACCUMULATIONS ${accumulations}, BURSTS ${bursts}
                        </div>
                    </div>`;
                return false;
            }
        }

        async function loadData() {
            try {
                if (window.__EMBEDDED_PATTERNS__) {
                    const normalizedEmbedded = normalizePatternsPayload(window.__EMBEDDED_PATTERNS__);
                    window.__EMBEDDED_PATTERNS__ = null;
                    window.lastRenderDataAdmin = normalizedEmbedded;
                    safeRenderPatterns(normalizedEmbedded);
                    return;
                }
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000);
                const response = await fetch('/api/public_patterns', { signal: controller.signal });
                clearTimeout(timeoutId);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                const normalized = normalizePatternsPayload(data);
                window.lastRenderDataAdmin = normalized;
                safeRenderPatterns(normalized);
            } catch (error) {
                console.error('Failed to load data:', error);
                document.getElementById('patterns-content').innerHTML = 
                    '<div class="empty-state" style="color: var(--accent-red);">Failed to load data. Retrying...</div>';
            }
        }
        
        window.lastRenderDataAdmin = null;
        window.changePubPageAdmin = function(delta) {
            window.currentPagePublishedAdmin += delta;
            if (window.lastRenderDataAdmin) {
                safeRenderPatterns(window.lastRenderDataAdmin);
            }
        };

        // Initial load
        loadData();
        
        // Auto-refresh
        setInterval(loadData, __INSIDER_JS_REFRESH_MS__);
    </script>
</body>
</html>
"""


PUBLIC_PATTERNS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow">
    <title>PolymarketWhales – Live Whale Signals &amp; Smart Money Alerts on Polymarket</title>
    <link rel="icon" type="image/png" href="/favicon.png?v=4">
    <meta name="description" content="PolymarketWhales — real-time intelligence feed tracking unusual positioning, accumulation patterns, and volume bursts on Polymarket. Free behavioral analytics for prediction market traders.">
    <link rel="canonical" href="https://polymarketwhales.online/public">
    <meta property="og:type" content="website">
    <meta property="og:title" content="PolymarketWhales – Live Whale Signals & Smart Money Alerts">
    <meta property="og:description" content="PolymarketWhales — real-time intelligence feed tracking unusual positioning, accumulation patterns, and volume bursts on Polymarket.">
    <meta property="og:url" content="https://polymarketwhales.online/public">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="PolymarketWhales – Live Whale Signals & Smart Money Alerts">
    <meta name="twitter:description" content="PolymarketWhales — real-time intelligence feed tracking unusual positioning, accumulation patterns, and volume bursts on Polymarket.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #090d19;
            --bg-card: #101a2d;
            --bg-soft: #16233d;
            --line: #263b61;
            --text-main: #ecf3ff;
            --text-soft: #a9bddf;
            --c-cluster: #60a5fa;
            --c-acc: #2dd4bf;
            --c-burst: #fb7185;
            --c-good: #34d399;
            --c-warn: #f59e0b;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Space Grotesk', sans-serif;
            background:
                radial-gradient(1200px 500px at 5% -10%, rgba(96, 165, 250, 0.25), transparent 60%),
                radial-gradient(900px 450px at 95% 0%, rgba(45, 212, 191, 0.2), transparent 60%),
                var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px 18px 30px;
        }
        .container {
            max-width: 1320px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 16px;
            margin-bottom: 14px;
        }
        .brand h1 {
            font-size: 2rem;
            line-height: 1;
            letter-spacing: 0.2px;
        }
        .brand p {
            margin-top: 8px;
            color: var(--text-soft);
            font-size: 0.95rem;
        }
        .top-actions {
            display: flex;
            flex-direction: column;
            align-items: end;
            gap: 8px;
        }
        .tag {
            border: 1px solid var(--line);
            background: rgba(22, 35, 61, 0.65);
            color: var(--text-soft);
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 0.78rem;
            letter-spacing: 0.2px;
        }
        .hero {
            background: linear-gradient(145deg, rgba(16, 26, 45, 0.95), rgba(10, 15, 29, 0.95));
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 14px;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
        }
        .hero h2 {
            font-size: 1.1rem;
            margin-bottom: 10px;
            color: var(--c-cluster);
        }
        .hero p {
            color: var(--text-main);
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 7px;
        }
        .hero ul {
            margin: 8px 0 8px 20px;
            color: var(--text-main);
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .hero .note {
            color: var(--text-soft);
            font-size: 0.9rem;
        }
        .signal-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }
        .signal-card {
            background: var(--bg-card);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 14px;
            min-height: 108px;
            animation: reveal 0.45s ease both;
        }
        @keyframes reveal {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .signal-card h3 {
            font-size: 0.78rem;
            color: var(--text-soft);
            letter-spacing: 0.4px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .signal-value {
            font-size: 1.7rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 8px;
        }
        .signal-sub {
            color: var(--text-soft);
            font-size: 0.86rem;
        }
        .v-cluster { color: var(--c-cluster); }
        .v-acc { color: var(--c-acc); }
        .v-burst { color: var(--c-burst); }
        .v-total { color: var(--text-main); }

        .section {
            background: var(--bg-card);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 14px 14px 12px;
            margin-bottom: 16px;
        }
        .section-head {
            display: flex;
            justify-content: space-between;
            align-items: start;
            gap: 12px;
            margin-bottom: 10px;
        }
        .section-head h2 {
            font-size: 1.02rem;
            letter-spacing: 0.2px;
        }
        .section-count {
            color: var(--text-soft);
            font-size: 0.86rem;
            margin-top: 5px;
        }
        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            margin-top: 6px;
        }
        .chip {
            padding: 5px 9px;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: rgba(22, 35, 61, 0.8);
            color: var(--text-soft);
            font-size: 0.75rem;
            white-space: nowrap;
        }
        .chip b {
            color: var(--text-main);
            font-weight: 500;
        }
        .cluster-accent { color: var(--c-cluster); }
        .acc-accent { color: var(--c-acc); }
        .burst-accent { color: var(--c-burst); }

        .scroll-wrap {
            overflow-x: auto;
            border: 1px solid rgba(38, 59, 97, 0.5);
            border-radius: 12px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.86rem;
        }
        th, td {
            text-align: left;
            padding: 10px 9px;
            border-bottom: 1px solid rgba(38, 59, 97, 0.5);
            vertical-align: top;
        }
        th {
            color: var(--text-soft);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: rgba(22, 35, 61, 0.5);
            white-space: nowrap;
        }
        tr:last-child td { border-bottom: none; }
        .market-link {
            color: var(--text-main);
            text-decoration: none;
            border-bottom: 1px dotted rgba(236, 243, 255, 0.45);
        }
        .market-link:hover {
            color: var(--c-cluster);
            border-bottom-color: var(--c-cluster);
        }
        .wallet-link {
            color: var(--c-cluster);
            text-decoration: none;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            border-bottom: 1px dotted rgba(96, 165, 250, 0.45);
        }
        .wallet-link:hover {
            border-bottom-color: var(--c-cluster);
        }
        .mono {
            font-family: 'IBM Plex Mono', monospace;
        }
        .dim { color: var(--text-soft); }
        .state-ready { color: var(--c-good); }
        .state-buffer { color: var(--c-warn); }
        .progress {
            margin-top: 6px;
            width: 100%;
            height: 6px;
            border-radius: 999px;
            background: rgba(22, 35, 61, 0.9);
            overflow: hidden;
        }
        .bar {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #60a5fa, #2dd4bf);
        }
        .empty {
            color: var(--text-soft);
            text-align: center;
            padding: 18px 0;
        }
        footer {
            margin-top: 20px;
            text-align: center;
            color: var(--text-soft);
            font-size: 0.85rem;
        }
        .whale-nav-btn {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 3px;
            padding: 10px 20px;
            background: linear-gradient(135deg, rgba(0,212,170,0.12), rgba(96,165,250,0.10));
            border: 1px solid rgba(0,212,170,0.45);
            border-radius: 12px;
            color: var(--text-main);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            transition: all 0.25s ease;
            white-space: nowrap;
            position: relative;
            animation: whalePulse 3s ease-in-out infinite;
        }
        @keyframes whalePulse {
            0%, 100% { box-shadow: 0 0 6px rgba(0,212,170,0.15); }
            50% { box-shadow: 0 0 18px rgba(0,212,170,0.35), 0 0 40px rgba(0,212,170,0.10); }
        }
        .whale-nav-btn:hover {
            background: linear-gradient(135deg, rgba(0,212,170,0.22), rgba(96,165,250,0.18));
            border-color: rgba(0,212,170,0.7);
            transform: translateY(-1px);
            box-shadow: 0 4px 24px rgba(0,212,170,0.25);
            animation: none;
        }
        .whale-nav-sub {
            font-size: 0.72rem;
            font-weight: 400;
            color: var(--text-soft);
        }
        .whale-live-badge {
            position: absolute;
            top: -7px;
            right: -7px;
            background: rgba(0,212,170,0.18);
            border: 1px solid rgba(0,212,170,0.5);
            color: #00d4aa;
            font-size: 0.58rem;
            font-weight: 700;
            letter-spacing: 0.8px;
            padding: 2px 7px 2px 5px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 4px;
            text-transform: uppercase;
        }
        .whale-live-dot {
            width: 5px;
            height: 5px;
            border-radius: 50%;
            background: #00d4aa;
            animation: liveDot 1.5s ease-in-out infinite;
        }
        @keyframes liveDot {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        @media (max-width: 860px) {
            header {
                flex-direction: column;
                align-items: start;
            }
            .top-actions {
                align-items: start;
            }
            body {
                padding: 16px 12px 24px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>PolymarketWhales Signals</h1>
                <p>Behavioral intelligence feed for unusual market positioning</p>
            </div>
            <div class="top-actions">
                <a href="/whale-trades" class="whale-nav-btn"><span class="whale-live-badge"><span class="whale-live-dot"></span>LIVE</span>🐋 Whale Trades<span class="whale-nav-sub">Live feed of whale buys over $10K</span></a>
            </div>
        </header>

        <div style="font-size: 0.85rem; color: var(--text-soft); padding: 0 10px 15px; line-height: 1.4;">
            <p style="margin: 0 0 5px 0;">Real-time intelligence feed tracking atypical behavior and fresh wallets on Polymarket. <em>Not financial advice.</em></p>
            <p style="margin: 0;">Signal types: <strong>CLUSTER</strong> (coordinated activity), <strong>ACCUMULATION</strong> (steady buildup), <strong>BURST</strong> (sudden volume spikes).</p>
        </div>

        <div id="content">
            <p class="empty">Loading...</p>
        </div>
        <footer>
            <span id="last-update" style="display: none;">-</span>Updated every __INSIDER_REFRESH_HUMAN__
        </footer>
    </div>
    <script>
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        }

        function asNumber(value) {
            if (value === null || value === undefined || value === '') return null;
            const n = Number(value);
            return Number.isFinite(n) ? n : null;
        }

        function shortWallet(wallet) {
            if (!wallet || wallet.length < 10) return wallet || '';
            return wallet.substring(0, 6) + '..' + wallet.substring(wallet.length - 4);
        }

        function withRef(url) {
            if (!url) return '';
            const sep = url.includes('?') ? '&' : '?';
            return `${url}${sep}r=PolymarketWhaleAlrts`;
        }

        function toMinutesAgo(ts) {
            if (!ts) return 'N/A';
            const now = Date.now() / 1000;
            const diffSec = Math.max(0, Math.floor(now - ts));
            const min = 60;
            const hour = 3600;
            const day = 86400;
            const week = 7 * day;
            const month = 30 * day;

            if (diffSec < hour) return Math.floor(diffSec / min) + 'm ago';
            if (diffSec < day) return Math.floor(diffSec / hour) + 'h ago';
            if (diffSec < week) return Math.floor(diffSec / day) + 'd ago';
            if (diffSec < month) return Math.floor(diffSec / week) + 'w ago';

            const d = new Date(ts * 1000);
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
        }

        function renderWalletsWithAppended(p) {
            const original = p.original_wallet_list || [];
            const appendedInfo = p.appended_wallets_info || {};
            const allWallets = p.wallet_list || [];
            
            if (allWallets.length === 0) return '<span class="dim">-</span>';

            const originalSet = new Set(original);
            const appendedWallets = allWallets.filter(w => !originalSet.has(w));
            
            let html = '';
            
            // Show summary if there are appended wallets
            if (appendedWallets.length > 0) {
                let yesCount = 0;
                let noCount = 0;
                appendedWallets.forEach(w => {
                    if (appendedInfo[w] === 'YES') yesCount++;
                    else if (appendedInfo[w] === 'NO') noCount++;
                });
                
                const stats = [];
                if (yesCount > 0) stats.push(`<span style="color: var(--c-good)">${yesCount} YES</span>`);
                if (noCount > 0) stats.push(`<span style="color: var(--c-burst)">${noCount} NO</span>`);
                
                html += `<div style="font-size: 0.72rem; margin-bottom: 4px; color: var(--text-soft);">+${appendedWallets.length} since signal (${stats.join(' / ')})</div>`;
            }

            const originalWallets = allWallets.filter(w => originalSet.has(w));
            const appendedWalletsReversed = [...appendedWallets].reverse();
            
            const originalHtml = originalWallets.map(w => {
                return `<a class="wallet-link" target="_blank" href="${withRef(`https://polymarket.com/profile/${w}`)}">${shortWallet(w)}</a>`;
            }).join(', ');
            
            const appendedHtml = appendedWalletsReversed.map(w => {
                const outcome = appendedInfo[w];
                let prefix = '';
                if (outcome === 'YES') prefix = '🟢 ';
                else if (outcome === 'NO') prefix = '🔴 ';
                return `<a class="wallet-link" target="_blank" href="${withRef(`https://polymarket.com/profile/${w}`)}">${prefix}${shortWallet(w)}</a>`;
            }).join(', ');
            
            html += originalHtml;
            if (appendedHtml) {
                html += (originalHtml ? `<div style="margin-top: 4px;">` : `<div>`) + appendedHtml + `</div>`;
            }
            
            return html;
        }

        function hoursToReadable(hoursRaw) {
            const hours = asNumber(hoursRaw);
            if (!hours || hours <= 0) return null;
            const days = Math.floor(hours / 24);
            const remainHours = hours % 24;
            if (days > 0 && remainHours > 0) return `${days}d ${remainHours}h`;
            if (days > 0) return `${days}d`;
            return `${hours}h`;
        }

        function pct(current, target) {
            const c = asNumber(current);
            const t = asNumber(target);
            if (!c || !t || t <= 0) return 0;
            return Math.max(0, Math.min(100, Math.round((c / t) * 100)));
        }

        function renderProgress(current, target) {
            const p = pct(current, target);
            return `<div class="progress"><div class="bar" style="width: ${p}%;"></div></div>`;
        }

        function textOrDash(value) {
            return value === null || value === undefined || value === '' ? '<span class="dim">-</span>' : value;
        }

        function renderScenarioChips(scenario, type) {
            if (!scenario || Object.keys(scenario).length === 0) return '';
            const chips = [];
            if (scenario.min_usd || scenario.min_total) {
                const minTrade = scenario.min_usd ? `$${formatNumber(Number(scenario.min_usd))}` : 'n/a';
                const minTotal = scenario.min_total ? `$${formatNumber(Number(scenario.min_total))}` : 'n/a';
                chips.push(`<span class="chip">Volume: <b>${minTrade} min, ${minTotal} total</b></span>`);
            }
            if (scenario.min_wallets) chips.push(`<span class="chip">Wallets: <b>${scenario.min_wallets}+</b></span>`);
            if (scenario.min_dir) chips.push(`<span class="chip">Direction: <b>${scenario.min_dir}%+</b></span>`);
            if (scenario.interval) {
                const intervalLabel = type === 'ACCUMULATION' ? `${scenario.interval}d` : `${scenario.interval}h`;
                chips.push(`<span class="chip">Interval: <b>${intervalLabel}</b></span>`);
            }
            const ageText = hoursToReadable(scenario.max_age);
            if (ageText) chips.push(`<span class="chip">Wallet age: <b>&le; ${ageText}</b></span>`);
            if (scenario.max_pos) chips.push(`<span class="chip">Open positions: <b>&le; ${scenario.max_pos}</b></span>`);
            if (!chips.length) return '';
            return `<div class="chips">${chips.join('')}</div>`;
        }

        function marketTitleCell(pattern) {
            const title = (pattern.title || '').trim();
            const shortTitle = title.length > 72 ? `${title.substring(0, 72)}...` : title;
            const makeSlug = (value) => (value || '')
                .toLowerCase()
                .normalize('NFKD')
                .replace(/['".,!?()[\]{}:;\\/|+*&^%$#@`~]/g, '')
                .replace(/\s+/g, '-')
                .replace(/-+/g, '-')
                .replace(/^-|-$/g, '');

            const titleSlug = makeSlug(title);
            let url = '';
            if (pattern.event_slug) {
                url = withRef(`https://polymarket.com/event/${pattern.event_slug}`);
            } else if (pattern.market_id) {
                url = withRef(`https://polymarket.com/event/${pattern.market_id}`);
            }

            if (url) {
                return `<a class="market-link" href="${url}" target="_blank">${shortTitle || pattern.market_id}</a>`;
            }
            return shortTitle || '<span class="dim">Unknown market</span>';
        }

        function directionCell(pattern) {
            const directionality = asNumber(pattern.directionality);
            const rawOutcome = String(pattern.outcome || '').trim();
            if (!rawOutcome) {
                return '<span class="dim">-</span>';
            }
            const outcomeUpper = rawOutcome.toUpperCase();
            const outcomeLabel = outcomeUpper === 'YES'
                ? 'Yes'
                : outcomeUpper === 'NO'
                    ? 'No'
                    : rawOutcome;
            
            if (directionality === null) {
                return outcomeLabel;
            }
            return `${outcomeLabel} ${Math.round(directionality)}%`;
        }

        function renderRows(items, scenario) {
            if (!items || items.length === 0) {
                return '<div class="empty">No active patterns right now.</div>';
            }

            return `
                <div class="scroll-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Market</th>
                                <th>Wallets</th>
                                <th>Volume</th>
                                <th>Direction</th>
                                <th>Participants</th>
                                <th>Buffer State</th>
                                <th>Last activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${items.map(p => `
                                <tr>
                                    <td>${marketTitleCell(p)}</td>
                                    <td class="mono">
                                        ${p.wallets || 0} / ${p.min_wallets || scenario.min_wallets || '-'}
                                        ${renderProgress(p.wallets || 0, p.min_wallets || scenario.min_wallets || 0)}
                                    </td>
                                    <td class="mono">
                                        $${formatNumber(p.volume || 0)} / $${formatNumber(asNumber(p.min_total || scenario.min_total) || 0)}
                                        ${renderProgress(p.volume || 0, p.min_total || scenario.min_total || 0)}
                                    </td>
                                    <td class="mono">${directionCell(p)}</td>
                                    <td>${(p.wallet_list || []).map(w => `<a class="wallet-link" target="_blank" href="${withRef(`https://polymarket.com/profile/${w}`)}">${shortWallet(w)}</a>`).join(', ') || '<span class="dim">-</span>'}</td>
                                    <td>${p.blocked_reason ? `<span class="state-buffer">${p.blocked_reason}</span>` : '<span class="state-ready">Ready</span>'}</td>
                                    <td class="dim">${toMinutesAgo(p.last_ts)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        // Pagination state for public page
        let currentPublishedPagePublic = 1;
        const itemsPerPagePublic = 20;

        function renderPublishedTable(items) {
            if (!items || items.length === 0) {
                return '<div class="empty">No published alerts yet.</div>';
            }
            
            const totalPages = Math.ceil(items.length / itemsPerPagePublic);
            if (currentPublishedPagePublic > totalPages) currentPublishedPagePublic = Math.max(1, totalPages);
            if (currentPublishedPagePublic < 1) currentPublishedPagePublic = 1;
            
            const startIdx = (currentPublishedPagePublic - 1) * itemsPerPagePublic;
            const currentItems = items.slice(startIdx, startIdx + itemsPerPagePublic);
            
            let html = `
                <div class="scroll-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Scenario</th>
                                <th>Market</th>
                                <th>Outcome</th>
                                <th>Result</th>
                                <th>Volume</th>
                                <th>Wallets</th>
                                <th>Participants</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${currentItems.map(p => `
                                <tr>
                                    <td class="dim">${toMinutesAgo(p.timestamp)}</td>
                                    <td><span class="mono">${textOrDash(p.scenario)}</span></td>
                                    <td>${marketTitleCell(p)}</td>
                                    <td class="mono">${directionCell(p)}</td>
                                    <td style="text-align: center;">
                                        ${p.result_status === 'win' ? '<span title="In Profit / Won">✅</span>' : 
                                          p.result_status === 'loss' ? '<span title="In Loss / Lost">❌</span>' : 
                                          '<span title="Pending">⏳</span>'}
                                    </td>
                                    <td class="mono">$${formatNumber(p.total_volume || 0)}</td>
                                    <td class="mono">${textOrDash(p.participants_count)}</td>
                                    <td>${renderWalletsWithAppended(p)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            
            if (totalPages > 1) {
                html += `
                    <div class="pagination" style="margin-top: 15px; display: flex; justify-content: center; align-items: center; gap: 10px;">
                        <button onclick="changePubPagePublic(-1)" ${currentPublishedPagePublic === 1 ? 'disabled' : ''} style="padding: 6px 12px; font-size: 13px; background: var(--bg-card); color: var(--text-main); border: 1px solid var(--line); border-radius: 4px; cursor: ${currentPublishedPagePublic === 1 ? 'not-allowed' : 'pointer'}; opacity: ${currentPublishedPagePublic === 1 ? '0.5' : '1'};">Previous</button>
                        <span style="font-size: 13px; color: var(--text-soft);">Page ${currentPublishedPagePublic} of ${totalPages}</span>
                        <button onclick="changePubPagePublic(1)" ${currentPublishedPagePublic >= totalPages ? 'disabled' : ''} style="padding: 6px 12px; font-size: 13px; background: var(--bg-card); color: var(--text-main); border: 1px solid var(--line); border-radius: 4px; cursor: ${currentPublishedPagePublic >= totalPages ? 'not-allowed' : 'pointer'}; opacity: ${currentPublishedPagePublic >= totalPages ? '0.5' : '1'};">Next</button>
                    </div>
                `;
            }
            
            return html;
        }

        function sumVolume(items) {
            return (items || []).reduce((acc, p) => acc + (Number(p.volume) || 0), 0);
        }

        let lastFetchedData = {};

        function renderPage(data) {
            lastFetchedData = data;
            const patterns = data.patterns || {};
            const scenarios = data.scenarios || {};
            const clusters = patterns.clusters || [];
            const accumulations = patterns.accumulations || [];
            const bursts = patterns.bursts || [];
            const published = data.recent_published || [];

            const totalSignals = clusters.length + accumulations.length + bursts.length;
            const trackedVolume = sumVolume(clusters) + sumVolume(accumulations) + sumVolume(bursts);

            const html = `
                <div class="hero">
                    <h2>About These Signals</h2>
                    <p>This page publishes signals of unusual trading behavior on Polymarket.</p>
                    <p>The focus is not on predictions, but on participant behavior patterns that may indicate early information or high conviction positioning.</p>
                    <p>This is not financial advice. These are behavioral signals.</p>
                    <p class="note"><strong>Distribution:</strong> confirmed signals are published in Telegram: <a class="market-link" href="https://t.me/PMInsiderSignals" target="_blank" rel="noopener noreferrer">@PMInsiderSignals</a>.</p>
                    <p class="note"><strong>Platform:</strong> data is sourced from <a class="market-link" href="https://polymarket.com/?r=PolymarketWhaleAlrts" target="_blank" rel="noopener noreferrer">Polymarket</a>.</p>
                    <p class="note"><strong>Signal engine:</strong> signals are formed by <a class="market-link" href="https://t.me/PolymarketWhales_bot" target="_blank" rel="noopener noreferrer">@PolymarketWhales_bot</a>.</p>

                    <p><strong>Signal Types</strong></p>
                    <ul>
                        <li><strong>CLUSTER:</strong> Several new wallets enter the same market, same direction, almost at the same time, with meaningful size.</li>
                        <li><strong>ACCUMULATION:</strong> Several new wallets steadily and significantly build a position in one market over multiple days.</li>
                        <li><strong>BURST:</strong> Sharp spike of activity from multiple young wallets in a short time window.</li>
                    </ul>
                    <p class="note">Why this can be useful: signals can appear before news and public consensus, and strict time/size/direction filters are applied.</p>
                    <p class="note">Sports and crypto-related events are intentionally excluded due to high noise, emotion, arbitrage, and automated strategies that can hide real behavioral patterns.</p>
                </div>

                <div class="signal-grid">
                    <div class="signal-card">
                        <h3>Total Active Signals</h3>
                        <div class="signal-value v-total">${totalSignals}</div>
                        <div class="signal-sub">across all pattern types</div>
                    </div>
                    <div class="signal-card">
                        <h3>Clusters</h3>
                        <div class="signal-value v-cluster">${clusters.length}</div>
                        <div class="signal-sub">$${formatNumber(sumVolume(clusters))} tracked volume</div>
                    </div>
                    <div class="signal-card">
                        <h3>Accumulations</h3>
                        <div class="signal-value v-acc">${accumulations.length}</div>
                        <div class="signal-sub">$${formatNumber(sumVolume(accumulations))} tracked volume</div>
                    </div>
                    <div class="signal-card">
                        <h3>Bursts</h3>
                        <div class="signal-value v-burst">${bursts.length}</div>
                        <div class="signal-sub">$${formatNumber(sumVolume(bursts))} tracked volume</div>
                    </div>
                    <div class="signal-card">
                        <h3>Recent Alerts</h3>
                        <div class="signal-value v-total">${published.length}</div>
                        <div class="signal-sub">last published pattern alerts</div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-head">
                        <div>
                            <h2 class="cluster-accent">Active CLUSTERS</h2>
                            <div class="section-count">${clusters.length} active</div>
                        </div>
                    </div>
                    ${renderScenarioChips(scenarios.CLUSTER || {}, 'CLUSTER')}
                    ${renderRows(clusters, scenarios.CLUSTER || {})}
                </div>

                <div class="section">
                    <div class="section-head">
                        <div>
                            <h2 class="acc-accent">Active ACCUMULATIONS</h2>
                            <div class="section-count">${accumulations.length} active</div>
                        </div>
                    </div>
                    ${renderScenarioChips(scenarios.ACCUMULATION || {}, 'ACCUMULATION')}
                    ${renderRows(accumulations, scenarios.ACCUMULATION || {})}
                </div>

                <div class="section">
                    <div class="section-head">
                        <div>
                            <h2 class="burst-accent">Active BURSTS</h2>
                            <div class="section-count">${bursts.length} active</div>
                        </div>
                    </div>
                    ${renderScenarioChips(scenarios.BURST || {}, 'BURST')}
                    ${renderRows(bursts, scenarios.BURST || {})}
                </div>

                <div class="section">
                    <div class="section-head">
                        <div>
                            <h2>Recently Published Alerts</h2>
                            <div class="section-count">last ${published.length} alerts</div>
                        </div>
                    </div>
                    ${renderPublishedTable(published)}
                </div>
            `;

            document.getElementById('content').innerHTML = html;
            document.getElementById('last-update').textContent = data.timestamp || '-';
        }

        async function loadData() {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000);
                const response = await fetch('/api/public_patterns', { signal: controller.signal });
                clearTimeout(timeoutId);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const data = await response.json();
                renderPage(data);
            } catch (err) {
                console.error('Failed to load data:', err);
                document.getElementById('content').innerHTML = '<div class="empty" style="color:#ef4444">Failed to load data. Retrying...</div>';
            }
        }
        
        window.changePubPagePublic = function(delta) {
            currentPublishedPagePublic += delta;
            if (lastFetchedData) {
                renderPage(lastFetchedData);
            }
        };

        loadData();
        setInterval(loadData, __INSIDER_JS_REFRESH_MS__);
    </script>
</body>
</html>
"""


WHALE_TRADES_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow">
    <title>PolymarketWhales – Live Whale Trades on Polymarket | Real-Time $10K+ BUY Orders</title>
    <link rel="icon" type="image/png" href="/favicon.png?v=4">
    <meta name="description" content="PolymarketWhales — track large whale BUY orders over $10,000 on Polymarket in real-time. See trader PnL, open positions, wallet age, and entry prices as they happen.">
    <link rel="canonical" href="https://polymarketwhales.online/whale-trades">
    <meta property="og:type" content="website">
    <meta property="og:title" content="PolymarketWhales – Live Whale Trades | Real-Time $10K+ Orders">
    <meta property="og:description" content="PolymarketWhales — track large whale BUY orders over $10,000 on Polymarket in real-time. Trader PnL, positions, wallet age, and entry prices.">
    <meta property="og:url" content="https://polymarketwhales.online/whale-trades">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="PolymarketWhales – Live Whale Trades | Real-Time $10K+ Orders">
    <meta name="twitter:description" content="PolymarketWhales — track large whale BUY orders over $10,000 on Polymarket in real-time. Trader PnL, positions, wallet age, and entry prices.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #090d19;
            --bg-card: #101a2d;
            --bg-soft: #16233d;
            --line: #263b61;
            --text-main: #ecf3ff;
            --text-soft: #a9bddf;
            --c-good: #34d399;
            --c-burst: #fb7185;
            --c-cluster: #60a5fa;
            --c-acc: #2dd4bf;
            --c-warn: #f59e0b;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Space Grotesk', sans-serif;
            background:
                radial-gradient(1200px 500px at 5% -10%, rgba(96,165,250,0.20), transparent 60%),
                radial-gradient(900px 450px at 95% 0%, rgba(52,211,153,0.15), transparent 60%),
                var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px 18px 30px;
        }
        .container {
            max-width: 1420px;
            margin: 0 auto;
        }
        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 16px;
            margin-bottom: 18px;
        }
        .brand h1 {
            font-size: 2rem;
            line-height: 1;
            letter-spacing: 0.2px;
        }
        .brand p {
            margin-top: 8px;
            color: var(--text-soft);
            font-size: 0.95rem;
        }
        .top-actions {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 9px 16px;
            background: linear-gradient(135deg, rgba(45,212,191,0.08), rgba(96,165,250,0.08));
            border: 1px solid rgba(45,212,191,0.3);
            border-radius: 10px;
            color: var(--text-main);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: 0 0 10px rgba(45,212,191,0.05);
        }
        .back-btn:hover {
            background: linear-gradient(135deg, rgba(45,212,191,0.15), rgba(96,165,250,0.12));
            border-color: rgba(45,212,191,0.6);
            color: var(--text-main);
            box-shadow: 0 4px 15px rgba(45,212,191,0.15);
        }
        .tag {
            border: 1px solid var(--line);
            background: rgba(22,35,61,0.65);
            color: var(--text-soft);
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 0.78rem;
            letter-spacing: 0.2px;
        }
        .live-dot {
            display: inline-block;
            width: 7px; height: 7px;
            background: var(--c-good);
            border-radius: 50%;
            margin-right: 5px;
            animation: pulse-dot 2s infinite;
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(52,211,153,0.5); }
            50% { opacity: 0.7; box-shadow: 0 0 0 5px rgba(52,211,153,0); }
        }

        /* Filters */
        .filters-bar {
            display: flex;
            align-items: center;
            gap: 18px;
            flex-wrap: wrap;
            margin-bottom: 16px;
            padding: 14px 16px;
            background: var(--bg-card);
            border: 1px solid var(--line);
            border-radius: 14px;
        }
        .filter-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .filter-label {
            color: var(--text-soft);
            font-size: 0.8rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        .seg-group {
            display: flex;
            background: var(--bg-soft);
            border-radius: 8px;
            border: 1px solid var(--line);
            overflow: hidden;
        }
        .seg-btn {
            padding: 7px 14px;
            background: transparent;
            border: none;
            color: var(--text-soft);
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.82rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .seg-btn.active {
            background: linear-gradient(135deg, rgba(96,165,250,0.25), rgba(45,212,191,0.15));
            color: var(--text-main);
            font-weight: 600;
        }
        .seg-btn:hover:not(.active) {
            background: rgba(96,165,250,0.08);
            color: var(--text-main);
        }
        .chk-label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            font-size: 0.84rem;
            color: var(--text-soft);
            user-select: none;
            transition: color 0.2s ease;
        }
        .chk-label:hover {
            color: var(--text-main);
        }
        .chk-label input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            width: 16px; height: 16px;
            border: 1.5px solid var(--line);
            border-radius: 4px;
            background: var(--bg-soft);
            cursor: pointer;
            position: relative;
            transition: all 0.2s ease;
        }
        .chk-label input[type="checkbox"]:checked {
            background: var(--c-cluster);
            border-color: var(--c-cluster);
        }
        .chk-label input[type="checkbox"]:checked::after {
            content: '✓';
            position: absolute;
            top: -1px; left: 2px;
            font-size: 11px;
            color: #fff;
            font-weight: 700;
        }
        .filter-sep {
            width: 1px;
            height: 24px;
            background: var(--line);
        }

        /* Table */
        .scroll-wrap {
            overflow-x: auto;
            border: 1px solid rgba(38,59,97,0.5);
            border-radius: 14px;
            background: var(--bg-card);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.86rem;
        }
        th, td {
            text-align: left;
            padding: 12px 10px;
            border-bottom: 1px solid rgba(38,59,97,0.4);
            vertical-align: middle;
        }
        th {
            color: var(--text-soft);
            font-weight: 600;
            font-size: 0.73rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: rgba(22,35,61,0.6);
            white-space: nowrap;
            position: sticky;
            top: 0;
        }
        tr:last-child td { border-bottom: none; }
        tr {
            animation: reveal 0.4s ease both;
        }
        @keyframes reveal {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        tr:hover td {
            background: rgba(96,165,250,0.04);
        }
        .market-link {
            color: var(--text-main);
            text-decoration: none;
            border-bottom: 1px dotted rgba(236,243,255,0.35);
            font-weight: 500;
        }
        .market-link:hover {
            color: var(--c-cluster);
            border-bottom-color: var(--c-cluster);
        }
        .trader-link {
            color: var(--c-cluster);
            text-decoration: none;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            border-bottom: 1px dotted rgba(96,165,250,0.35);
        }
        .trader-link:hover {
            border-bottom-color: var(--c-cluster);
        }
        .amount-cell {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--c-good);
            white-space: nowrap;
        }
        .outcome-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            font-family: 'IBM Plex Mono', monospace;
        }
        .outcome-yes {
            background: rgba(52,211,153,0.12);
            color: var(--c-good);
        }
        .outcome-no {
            background: rgba(251,113,133,0.12);
            color: var(--c-burst);
        }
        .price-tag {
            font-family: 'IBM Plex Mono', monospace;
            color: var(--text-soft);
            font-size: 0.82rem;
            margin-left: 5px;
        }
        .pnl-positive {
            color: var(--c-good);
            font-family: 'IBM Plex Mono', monospace;
            font-weight: 500;
        }
        .pnl-negative {
            color: var(--c-burst);
            font-family: 'IBM Plex Mono', monospace;
            font-weight: 500;
        }
        .mono {
            font-family: 'IBM Plex Mono', monospace;
        }
        .dim {
            color: var(--text-soft);
        }
        .small-dim {
            color: var(--text-soft);
            font-size: 0.78rem;
        }
        .empty {
            color: var(--text-soft);
            text-align: center;
            padding: 40px 0;
            font-size: 0.95rem;
        }
        footer {
            margin-top: 24px;
            text-align: center;
            color: var(--text-soft);
            font-size: 0.85rem;
        }
        .count-badge {
            display: inline-block;
            padding: 3px 10px;
            background: var(--bg-soft);
            border: 1px solid var(--line);
            border-radius: 999px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: var(--text-soft);
            margin-left: 10px;
        }

        /* Mobile cards */
        .mobile-cards, .whale-cards {
            display: none;
        }
        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: start;
            }
            .top-actions {
                width: 100%;
                justify-content: space-between;
            }
            body {
                padding: 16px 10px 24px;
            }
            .scroll-wrap, .whale-table {
                display: none;
            }
            .mobile-cards, .whale-cards {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .whale-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 14px;
                animation: reveal 0.4s ease both;
            }
            .card-market { font-weight: 500; font-size: 0.92rem; line-height: 1.3; margin-bottom: 6px; }
            .card-market a { color: var(--text-primary); text-decoration: none; }
            .card-amount { font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; font-weight: 700; color: var(--c-good); margin-bottom: 8px; }
            .card-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-top: 1px solid rgba(38,59,97,0.3); }
            .card-label { color: var(--text-soft); font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.3px; }
            .m-card {
                background: var(--bg-card);
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 14px;
                animation: reveal 0.4s ease both;
            }
            .m-card-head {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 10px;
                margin-bottom: 10px;
            }
            .m-card-market {
                font-weight: 500;
                font-size: 0.92rem;
                line-height: 1.3;
                flex: 1;
            }
            .m-card-amount {
                font-family: 'IBM Plex Mono', monospace;
                font-size: 1.3rem;
                font-weight: 700;
                color: var(--c-good);
                white-space: nowrap;
            }
            .m-card-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 5px 0;
                border-top: 1px solid rgba(38,59,97,0.3);
            }
            .m-card-label {
                color: var(--text-soft);
                font-size: 0.76rem;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            .m-card-value {
                font-size: 0.86rem;
                text-align: right;
            }
            .filters-bar {
                gap: 10px;
                padding: 12px;
            }
            .filter-sep {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>🐋 Whale Trades</h1>
                <p>Live feed of large BUY trades over $10,000 on Polymarket</p>
            </div>
            <div class="top-actions">
                <a href="/public" class="back-btn">← Signals & Patterns</a>
                <span class="tag"><span class="live-dot"></span>Live · 60s refresh</span>
            </div>
        </header>

        <div class="filters-bar" id="filters-bar">
            <div class="filter-group">
                <span class="filter-label">Show</span>
                <div class="seg-group" id="seg-limit">
                    <button class="seg-btn active" data-val="25">25</button>
                    <button class="seg-btn" data-val="50">50</button>
                    <button class="seg-btn" data-val="100">100</button>
                </div>
            </div>
            <div class="filter-sep"></div>
            <div class="filter-group">
                <span class="filter-label">Include</span>
                <label class="chk-label"><input type="checkbox" id="chk-crypto" checked> Crypto</label>
                <label class="chk-label"><input type="checkbox" id="chk-sport" checked> Sport</label>
            </div>
        </div>

        <div style="font-size: 0.85rem; color: var(--text-soft); padding: 0 10px 15px; line-height: 1.4;">
            <p style="margin: 0;">Live whale trades feed monitoring large Polymarket positions. Minimum trade threshold is $10,000 USD. Data updates automatically in real-time.</p>
        </div>

        <div id="content">
            <p class="empty">Loading whale trades…</p>
        </div>
        <footer>
            <span id="last-update" style="display: none;">-</span>
        </footer>
    </div>

    <script>
        // ========== LIVE DATA ==========
        let allTrades = [];

        // ========== STATE ==========
        let currentLimit = 25;
        let includeCrypto = true;
        let includeSport = true;

        // ========== HELPERS ==========
        function formatUSD(num) {
            if (num >= 1000000) return '$' + (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return '$' + (num / 1000).toFixed(1) + 'K';
            return '$' + num;
        }

        function shortAddr(addr) {
            if (!addr || addr.length < 10) return addr || '-';
            return addr.substring(0, 6) + '…' + addr.substring(addr.length - 4);
        }

        function timeAgo(ts) {
            const now = Date.now() / 1000;
            const diff = Math.max(0, now - ts);
            if (diff < 60) return Math.floor(diff) + 's ago';
            if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
            if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
            return Math.floor(diff / 86400) + 'd ago';
        }

        function walletAge(hours) {
            if (hours == null) return '-';
            if (hours < 1) return '<1h';
            if (hours < 24) return Math.floor(hours) + 'h';
            if (hours < 720) return Math.floor(hours / 24) + 'd';
            if (hours < 8760) return (hours / 720).toFixed(1) + 'mo';
            return (hours / 8760).toFixed(1) + 'y';
        }

        function pnlClass(val) {
            return val >= 0 ? 'pnl-positive' : 'pnl-negative';
        }

        function pnlSign(val) {
            return val >= 0 ? '+' : '';
        }

        function withRef(url) {
            if (!url) return '';
            const sep = url.includes('?') ? '&' : '?';
            return url + sep + 'r=PolymarketWhaleAlrts';
        }

        // ========== FILTER & RENDER ==========
        function filterTrades(trades) {
            let filtered = trades.filter(t => {
                const cat = (t.category || '').toLowerCase();
                if (cat === 'crypto' && !includeCrypto) return false;
                if ((cat === 'sport' || cat === 'sports') && !includeSport) return false;
                return true;
            });
            filtered.sort((a, b) => b.timestamp - a.timestamp);
            return filtered.slice(0, currentLimit);
        }

        function renderTable(trades) {
            if (!trades.length) {
                return '<div class="empty">No whale trades yet. Trades will appear as they happen in real-time.</div>';
            }

            const traderDisplay = (t) => {
                const name = t.trader_name || shortAddr(t.trader_address);
                const url = withRef('https://polymarket.com/profile/' + t.trader_address);
                return `<a class="trader-link" href="${url}" target="_blank">${name}</a>`;
            };

            const marketLink = (t) => {
                const title = (t.market_title || '').length > 65 ? t.market_title.substring(0, 65) + '…' : t.market_title;
                const url = withRef('https://polymarket.com/event/' + (t.event_slug || ''));
                return `<a class="market-link" href="${url}" target="_blank">${title}</a>`;
            };

            const outcomeHtml = (t) => {
                const cls = t.outcome && t.outcome.toUpperCase() === 'YES' ? 'outcome-yes' : 'outcome-no';
                return `<span class="${cls}">${t.outcome || '-'}</span> <span class="dim">@ ${t.price != null ? t.price + '%' : '-'}</span>`;
            };

            const pnlHtml = (t) => {
                if (t.open_pnl == null) return '<span class="dim">n/a</span>';
                const cls = pnlClass(t.open_pnl);
                return `<span class="${cls}">${pnlSign(t.open_pnl)}${formatUSD(Math.abs(t.open_pnl))}</span> <span class="dim">(${pnlSign(t.open_pnl_pct || 0)}${(t.open_pnl_pct || 0).toFixed(1)}%)</span>`;
            };

            const posHtml = (t) => {
                if (t.open_positions == null) return '<span class="dim">n/a</span>';
                return `${t.open_positions} <span class="dim">| ${formatUSD(t.positions_value || 0)}</span>`;
            };

            // Desktop table
            let html = `<table class="whale-table">
                <thead><tr>
                    <th>Market</th><th>Trader</th><th>Amount</th><th>Outcome & Price</th>
                    <th>Open PnL</th><th>Positions</th><th>Wallet Age</th><th>Time</th>
                </tr></thead><tbody>`;
            trades.forEach((t, i) => {
                html += `<tr style="animation-delay:${i*0.04}s">
                    <td>${marketLink(t)}</td>
                    <td>${traderDisplay(t)}</td>
                    <td class="amount-cell">${formatUSD(t.amount)}</td>
                    <td>${outcomeHtml(t)}</td>
                    <td>${pnlHtml(t)}</td>
                    <td>${posHtml(t)}</td>
                    <td>${walletAge(t.wallet_age_hours)}</td>
                    <td>${timeAgo(t.timestamp)}</td>
                </tr>`;
            });
            html += '</tbody></table>';

            // Mobile cards
            html += '<div class="whale-cards">';
            trades.forEach((t, i) => {
                html += `<div class="whale-card" style="animation-delay:${i*0.04}s">
                    <div class="card-market">${marketLink(t)}</div>
                    <div class="card-amount">${formatUSD(t.amount)}</div>
                    <div class="card-row">
                        <span class="card-label">Trader</span>
                        <span>${traderDisplay(t)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Outcome</span>
                        <span>${outcomeHtml(t)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Open PnL</span>
                        <span>${pnlHtml(t)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Positions</span>
                        <span>${posHtml(t)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Wallet Age</span>
                        <span>${walletAge(t.wallet_age_hours)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Time</span>
                        <span>${timeAgo(t.timestamp)}</span>
                    </div>
                </div>`;
            });
            html += '</div>';

            return html;
        }

        function render() {
            const filtered = filterTrades(allTrades);
            document.getElementById('content').innerHTML = renderTable(filtered);
            document.getElementById('trade-count').textContent = filtered.length;
        }

        function fetchTrades() {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);
            fetch('/api/whale_trades?limit=200', { signal: controller.signal })
                .then(r => {
                    clearTimeout(timeoutId);
                    if (!r.ok) {
                        throw new Error(`HTTP ${r.status}`);
                    }
                    return r.json();
                })
                .then(data => {
                    allTrades = data.trades || [];
                    render();
                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                })
                .catch(err => console.error('Failed to fetch whale trades:', err));
        }

        // ========== LIMIT BUTTONS ==========
        document.querySelectorAll('.seg-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentLimit = parseInt(btn.dataset.val);
                render();
            });
        });

        document.getElementById('chk-crypto').addEventListener('change', (e) => {
            includeCrypto = e.target.checked;
            render();
        });

        document.getElementById('chk-sport').addEventListener('change', (e) => {
            includeSport = e.target.checked;
            render();
        });

        // ========== INIT ==========
        fetchTrades();

        // Auto-refresh every 60 seconds
        setInterval(fetchTrades, 60000);
    </script>
</body>
</html>
"""


def _is_admin_authorized() -> bool:
    """Check optional token auth for sensitive admin endpoints."""
    configured_token = os.getenv("STATUS_ADMIN_TOKEN", "").strip()
    if not configured_token:
        return True

    provided_token = request.args.get("token", "") or request.headers.get("X-Status-Token", "")
    return hmac.compare_digest(provided_token, configured_token)


def _public_patterns_payload() -> dict:
    """Return sanitized payload for public patterns page."""
    status = get_full_status()
    insider = status.get("insider") or {}
    pending = insider.get("pending_patterns") or {}
    scenarios = insider.get("scenarios") or {}
    
    def sanitize_pattern(pattern: dict) -> dict:
        return {
            "title": pattern.get("title", ""),
            "market_id": pattern.get("market_id"),
            "event_slug": pattern.get("event_slug"),
            "wallets": pattern.get("wallets", 0),
            "volume": pattern.get("volume", 0),
            "min_wallets": pattern.get("min_wallets"),
            "min_total": pattern.get("min_total"),
            "side": pattern.get("side"),
            "min_dir": pattern.get("min_dir"),
            "interval": pattern.get("interval"),
            "blocked_reason": pattern.get("blocked_reason"),
            "wallet_list": pattern.get("wallet_list", []),
            "last_ts": pattern.get("last_ts"),
            "outcome": pattern.get("outcome"),
            "directionality": pattern.get("directionality"),
        }
    
    def sanitize_published(item: dict) -> dict:
        return {
            "timestamp": item.get("timestamp"),
            "scenario": item.get("scenario"),
            "market_id": item.get("market_id"),
            "market_title": item.get("market_title"),
            # marketTitleCell() in JS reads 'title' and 'event_slug'
            "title": item.get("market_title", ""),
            "event_slug": item.get("event_slug"),
            "outcome": item.get("outcome"),
            "directionality": item.get("directionality"),
            "total_volume": item.get("total_volume", 0),
            "participants_count": item.get("participants_count", 0),
            "wallet_list": item.get("wallet_list", []),
            "original_wallet_list": item.get("original_wallet_list", []),
            "appended_wallets_info": item.get("appended_wallets_info", {}),
            "result_status": item.get("result_status", "pending"),
            "entry_price": item.get("entry_price"),
        }

    def sanitize_scenario(cfg: dict) -> dict:
        if not isinstance(cfg, dict):
            return {}
        return {
            "enabled": cfg.get("enabled"),
            "min_usd": cfg.get("min_usd"),
            "min_total": cfg.get("min_total"),
            "min_wallets": cfg.get("min_wallets"),
            "max_age": cfg.get("max_age"),
            "min_dir": cfg.get("min_dir"),
            "side": cfg.get("side"),
            "max_pos": cfg.get("max_pos"),
            "interval": cfg.get("interval"),
        }

    from storage.alerts_storage import get_recent_published
    recent_published = get_recent_published(200)

    return {
        "timestamp": status.get("timestamp"),
        "enabled": insider.get("enabled"),
        "patterns": {
            "clusters": [sanitize_pattern(p) for p in pending.get("clusters", [])],
            "accumulations": [sanitize_pattern(p) for p in pending.get("accumulations", [])],
            "bursts": [sanitize_pattern(p) for p in pending.get("bursts", [])],
        },
        "scenarios": {
            "CLUSTER": sanitize_scenario(scenarios.get("CLUSTER")),
            "ACCUMULATION": sanitize_scenario(scenarios.get("ACCUMULATION")),
            "BURST": sanitize_scenario(scenarios.get("BURST")),
        },
        "recent_published": [sanitize_published(p) for p in recent_published],
    }


@app.route('/')
def index():
    """Serve the dashboard HTML page."""
    if not _is_admin_authorized():
        return jsonify({"error": "Forbidden"}), 403
    status_payload = get_full_status()
    html = _apply_insider_refresh_to_html(HTML_TEMPLATE).replace(
        "__EMBEDDED_STATUS_JSON__", _safe_inline_json(status_payload)
    )
    return Response(html, mimetype='text/html')


@app.route('/patterns')
def patterns():
    """Serve the active patterns page."""
    if not _is_admin_authorized():
        return jsonify({"error": "Forbidden"}), 403
    status_payload = _public_patterns_payload()
    html = _apply_insider_refresh_to_html(PATTERNS_TEMPLATE).replace(
        "__EMBEDDED_PATTERNS_JSON__", _safe_inline_json(status_payload)
    )
    return Response(html, mimetype='text/html')


@app.route('/api/status')
def api_status():
    """Return full status as JSON."""
    if not _is_admin_authorized():
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(get_full_status())


@app.route('/public')
def public_patterns():
    """Serve public patterns page."""
    return Response(_apply_insider_refresh_to_html(PUBLIC_PATTERNS_TEMPLATE), mimetype='text/html')


@app.route('/whale-trades')
def whale_trades_page():
    """Serve whale trades live feed page."""
    return Response(WHALE_TRADES_TEMPLATE, mimetype='text/html')


@app.route('/api/whale_trades')
def api_whale_trades():
    """Return whale trades from the in-memory ring buffer."""
    limit = request.args.get('limit', 100, type=int)
    limit = min(limit, 200)  # Cap at 200
    trades = get_whale_trades(limit=limit)
    return jsonify({'trades': trades, 'count': len(trades)})


@app.route('/api/public_patterns')
def api_public_patterns():
    """Return public safe patterns payload."""
    return jsonify(_public_patterns_payload())


@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    content = (
        "User-agent: *\n"
        "Allow: /public\n"
        "Allow: /whale-trades\n"
        "Disallow: /api/status\n"
        "Disallow: /patterns\n"
        "Allow: /api/public_patterns\n"
        "Allow: /api/whale_trades\n"
        "\n"
        "Sitemap: https://polymarketwhales.online/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    """Serve sitemap.xml for search engine indexing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        '    <loc>https://polymarketwhales.online/public</loc>\n'
        f'    <lastmod>{now}</lastmod>\n'
        '    <changefreq>hourly</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
        '  <url>\n'
        '    <loc>https://polymarketwhales.online/whale-trades</loc>\n'
        f'    <lastmod>{now}</lastmod>\n'
        '    <changefreq>hourly</changefreq>\n'
        '    <priority>0.9</priority>\n'
        '  </url>\n'
        '</urlset>\n'
    )
    return Response(xml, mimetype='application/xml')


def run_server(port=5000, host='0.0.0.0'):
    """Run Flask server in a separate thread."""
    def run():
        try:
            from waitress import serve
            serve(app, host=host, port=port, _quiet=True, threads=8, channel_timeout=30, recv_bytes=65536, send_bytes=65536)
        except ImportError:
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info(f"Status dashboard started on http://{host}:{port}")
    return thread


def start_status_server(port=5000):
    """Start the status dashboard server."""
    return run_server(port=port)
