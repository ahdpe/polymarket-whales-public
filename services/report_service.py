import os
import sqlite3
import json
import logging
import psutil
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_report(poly_service=None):
    """Generate daily status report with memory, users, and database stats."""
    try:
        # Memory info
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_percent = process.memory_percent()
        system_mem = psutil.virtual_memory()
        
        # Database stats
        saved_count = 0
        keys_count = 0
        trades_count = 0
        
        try:
            conn = sqlite3.connect('data/saved_whales.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM saved_whales")
            saved_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM whale_keys")
            keys_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.error(f"Error reading saved_whales.db: {e}")
        
        try:
            conn = sqlite3.connect('data/trades.db')
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_trades")
            trades_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.error(f"Error reading trades.db: {e}")
        
        # User count
        users_count = 0
        try:
            with open('user_settings.json', 'r') as f:
                data = json.load(f)
                users_count = len(data.get('filters', {}))
        except Exception as e:
            logger.error(f"Error reading user_settings.json: {e}")
        
        # File sizes
        files_info = []
        total_size = 0
        for name, path in [
            ('user_settings.json', 'user_settings.json'),
            ('saved_whales.db', 'data/saved_whales.db'),
            ('trades.db', 'data/trades.db'),
            ('bot_output.log', 'bot_output.log')
        ]:
            if os.path.exists(path):
                size = os.path.getsize(path)
                size_mb = size / 1024 / 1024
                total_size += size
                files_info.append(f"   {name}: {size_mb:.2f} MB")
        
        # Polymarket service stats
        poly_stats = {}
        if poly_service:
            poly_stats = poly_service.get_stats()
        
        # Format numbers
        rss_mb = f"{mem_info.rss / 1024 / 1024:.2f}"
        mem_pct = f"{mem_percent:.2f}"
        sys_used_gb = f"{system_mem.used / 1024 / 1024 / 1024:.2f}"
        sys_total_gb = f"{system_mem.total / 1024 / 1024 / 1024:.2f}"
        sys_pct = f"{system_mem.percent:.1f}"
        sys_available_gb = f"{system_mem.available / 1024 / 1024 / 1024:.2f}"
        total_mb = f"{total_size / 1024 / 1024:.2f}"
        
        report = f"""📊 <b>Отчет бота (запрос)</b>

🤖 <b>Процесс:</b>
   RSS: {rss_mb} MB
   Процент памяти: {mem_pct}%
   Системная память: {sys_used_gb} GB / {sys_total_gb} GB ({sys_pct}%)
   Доступно: {sys_available_gb} GB

👥 <b>Пользователи:</b> {users_count}

💾 <b>База данных:</b>
   Сохраненных трейдеров: {saved_count}
   Ключей трейдеров: {keys_count}
   Обработанных сделок: {trades_count:,}

📁 <b>Файлы данных:</b>
{chr(10).join(files_info)}
   Итого: {total_mb} MB"""

        if poly_stats:
            report += f"""

📈 <b>Статистика обработки:</b>
   Обработано сделок: {poly_stats.get('total_processed', 0):,}
   LRU кэш: {poly_stats.get('lru_size', 0):,}
   Активных серий: {poly_stats.get('active_series', 0)}"""
        
        report += f"\n\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return report
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return f"❌ Ошибка генерации отчета: {e}"
