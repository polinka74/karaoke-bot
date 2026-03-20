import pytz

# Настройки приложения
APP_NAME = "Караоке-бар"
APP_VERSION = "1.0.0"

# Цены
FREE_PRICE = 300      # новая песня
PAID_PRICE = 1000     # повтор

# Время блокировки стола после заказа (в секундах)
LOCK_DURATION = 60  # 10 минут

# Часовой пояс Екатеринбург
TIMEZONE = pytz.timezone('Asia/Yekaterinburg')

# Админский пароль (один на всех)
ADMIN_PASSWORD = "karaoke26"

# Настройки пагинации
ITEMS_PER_PAGE = 5

# Диапазон столов для QR-кодов
MIN_TABLE = 1
MAX_TABLE = 30

# Домен для QR-кодов (замените на свой после деплоя)
SITE_DOMAIN = "http://localhost:8000"  # Потом замените на реальный домен

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
