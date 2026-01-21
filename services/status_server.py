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
    <meta http-equiv="refresh" content="30">
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
        </header>
        
        <div class="grid" id="dashboard">
            <p style="text-align: center; color: var(--text-secondary);">Loading...</p>
        </div>
        
        <footer>
            <div>Last updated: <span id="last-update">-</span></div>
            <div class="refresh-info">Auto-refresh every 30 seconds</div>
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

                    ${(insider.published_history && insider.published_history.length > 0) ? `
                        <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Recently Published Alerts (Last 20)
                        </h3>
                        <div style="overflow-x: auto; margin-bottom: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border-color); text-align: left;">
                                        <th style="padding: 8px; color: var(--text-secondary);">Time</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Scenario</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Market</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Outcome</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Volume</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Wallets</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${insider.published_history.map(p => `
                                    <tr style="border-bottom: 1px solid var(--bg-tertiary);">
                                        <td style="padding: 8px; color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.timestamp)/60)}m ago
                                        </td>
                                        <td style="padding: 8px;">
                                            <span class="status-badge status-online" style="font-size: 0.75rem;">${p.scenario}</span>
                                        </td>
                                        <td style="padding: 8px;">
                                            <a href="https://polymarket.com/event/${p.market_id}" target="_blank" style="color: var(--text-primary); text-decoration: none;">
                                                ${(p.market_title || p.market_id).substring(0, 40) + ((p.market_title || p.market_id).length > 40 ? '...' : '')}
                                            </a>
                                        </td>
                                        <td style="padding: 8px;">${p.outcome}</td>
                                        <td style="padding: 8px;">$${formatNumber(p.total_volume || 0)}</td>
                                        <td style="padding: 8px;">${p.participants_count || '-'}</td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : ''}

                    ${(insider.pending_patterns?.clusters && insider.pending_patterns.clusters.length > 0) ? `
                        <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Active CLUSTERS (${insider.pending_patterns.clusters.length})
                        </h3>
                        <div style="overflow-x: auto; margin-bottom: 20px;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border-color); text-align: left;">
                                        <th style="padding: 8px; color: var(--text-secondary);">Market</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Wallets</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Volume</th>
                                        <th style="padding: 8px; color: var(--text-secondary); width: 35%;">Buffer Participants</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${insider.pending_patterns.clusters.map(p => `
                                    <tr style="border-bottom: 1px solid var(--bg-tertiary);">
                                        <td style="padding: 8px;">${p.title.substring(0, 40) + (p.title.length > 40 ? '...' : '')}</td>
                                        <td style="padding: 8px;">
                                            <span style="color: ${p.wallets >= p.min_wallets ? 'var(--accent-green)' : 'var(--accent-yellow)'}">
                                                ${p.wallets} / ${p.min_wallets}
                                            </span>
                                        </td>
                                        <td style="padding: 8px;">
                                            <span style="color: ${p.volume >= p.min_total ? 'var(--accent-green)' : 'var(--text-primary)'}">
                                                $${formatNumber(p.volume)}
                                            </span>
                                        </td>
                                        <td style="padding: 8px; font-family: monospace; font-size: 0.8rem; color: var(--text-secondary);">
                                            ${(p.wallet_list || []).map(w => `<a href="https://polymarket.com/profile/${w}" target="_blank" style="color: #4facfe; text-decoration: none; border-bottom: 1px dotted #4facfe;">${w.substring(0,5)}..${w.substring(39)}</a>`).join(', ')}
                                        </td>
                                        <td style="padding: 8px; color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : ''}

                    ${(insider.pending_patterns?.accumulations && insider.pending_patterns.accumulations.length > 0) ? `
                        <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Active ACCUMULATIONS (${insider.pending_patterns.accumulations.length})
                        </h3>
                        <div style="overflow-x: auto; margin-bottom: 20px;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border-color); text-align: left;">
                                        <th style="padding: 8px; color: var(--text-secondary);">Market</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Days</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Volume</th>
                                        <th style="padding: 8px; color: var(--text-secondary); width: 35%;">Buffer Participants</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${insider.pending_patterns.accumulations.map(p => `
                                    <tr style="border-bottom: 1px solid var(--bg-tertiary);">
                                        <td style="padding: 8px;">${p.title.substring(0, 40) + (p.title.length > 40 ? '...' : '')}</td>
                                        <td style="padding: 8px;">
                                            <span style="color: ${p.days >= p.min_days ? 'var(--accent-green)' : 'var(--accent-yellow)'}">
                                                ${p.days} / ${p.min_days}
                                            </span>
                                        </td>
                                        <td style="padding: 8px;">
                                            $${formatNumber(p.volume)}
                                        </td>
                                        <td style="padding: 8px; font-family: monospace; font-size: 0.8rem; color: var(--text-secondary);">
                                            ${(p.wallet_list || []).map(w => `<a href="https://polymarket.com/profile/${w}" target="_blank" style="color: #4facfe; text-decoration: none; border-bottom: 1px dotted #4facfe;">${w.substring(0,5)}..${w.substring(39)}</a>`).join(', ')}
                                        </td>
                                        <td style="padding: 8px; color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : ''}

                    ${(insider.pending_patterns?.bursts && insider.pending_patterns.bursts.length > 0) ? `
                        <h3 style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 10px;">
                            Active BURSTS (${insider.pending_patterns.bursts.length})
                        </h3>
                        <div style="overflow-x: auto;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border-color); text-align: left;">
                                        <th style="padding: 8px; color: var(--text-secondary);">Market</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Wallets</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Volume</th>
                                        <th style="padding: 8px; color: var(--text-secondary); width: 35%;">Buffer Participants</th>
                                        <th style="padding: 8px; color: var(--text-secondary);">Last Activity</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${insider.pending_patterns.bursts.map(p => `
                                    <tr style="border-bottom: 1px solid var(--bg-tertiary);">
                                        <td style="padding: 8px;">${p.title.substring(0, 40) + (p.title.length > 40 ? '...' : '')}</td>
                                        <td style="padding: 8px;">
                                            <span style="color: ${p.wallets >= p.min_wallets ? 'var(--accent-green)' : 'var(--accent-yellow)'}">
                                                ${p.wallets} / ${p.min_wallets}
                                            </span>
                                        </td>
                                        <td style="padding: 8px;">
                                            <span style="color: ${p.volume >= p.min_total ? 'var(--accent-green)' : 'var(--text-primary)'}">
                                                $${formatNumber(p.volume)}
                                            </span>
                                        </td>
                                        <td style="padding: 8px; font-family: monospace; font-size: 0.8rem; color: var(--text-secondary);">
                                            ${(p.wallet_list || []).map(w => `<a href="https://polymarket.com/profile/${w}" target="_blank" style="color: #4facfe; text-decoration: none; border-bottom: 1px dotted #4facfe;">${w.substring(0,5)}..${w.substring(39)}</a>`).join(', ')}
                                        </td>
                                        <td style="padding: 8px; color: var(--text-secondary);">
                                            ${Math.floor((Date.now() / 1000 - p.last_ts)/60)}m ago
                                        </td>
                                    </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : ''}

                    ${(!insider.pending_patterns?.clusters?.length && !insider.pending_patterns?.accumulations?.length && !insider.pending_patterns?.bursts?.length) ? 
                      '<p style="text-align: center; color: var(--text-secondary); font-style: italic;">No emerging patterns detected currently.</p>' : ''}
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


@app.route('/')
def index():
    """Serve the dashboard HTML page."""
    return Response(HTML_TEMPLATE, mimetype='text/html')


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
