import sqlite3
from datetime import datetime, timedelta  
import pytz
from config import TIMEZONE, FREE_PRICE, PAID_PRICE

class Database:
    def __init__(self, db_path='karaoke.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.init_songs()
    
    def get_current_time(self):
        """Текущее время в Екатеринбурге"""
        return datetime.now(TIMEZONE)
    
    def create_tables(self):
        """Создание всех таблиц"""
        # Таблица пользователей (сессий)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,  -- для веб-сессий
                table_number INTEGER,
                user_name TEXT,
                created_at TIMESTAMP
            )
        ''')
        
        # Таблица столов (активные столы)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tables (
                table_number INTEGER PRIMARY KEY,
                is_active BOOLEAN DEFAULT 1,
                current_session_id TEXT,
                current_user_name TEXT,
                locked_until TIMESTAMP,  -- время разблокировки
                total_debt INTEGER DEFAULT 0,
                updated_at TIMESTAMP
            )
        ''')
        
        # Таблица песен
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                song_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                artist TEXT
            )
        ''')
        
        # Таблица заказов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number INTEGER,
                session_id TEXT,
                user_name TEXT,
                song_id INTEGER,
                order_type TEXT,  -- 'free' или 'paid'
                price INTEGER,
                status TEXT DEFAULT 'pending',  -- 'pending', 'completed', 'cancelled'
                created_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (song_id) REFERENCES songs (song_id)
            )
        ''')
        
        # Таблица блокировок песен (кто спел первым)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS song_locks (
                song_id INTEGER PRIMARY KEY,
                first_table INTEGER,
                first_user_name TEXT,
                locked_at TIMESTAMP,
                FOREIGN KEY (song_id) REFERENCES songs (song_id)
            )
        ''')
        
        self.conn.commit()
    
def init_songs(self):
    """Инициализация тестовых песен (если таблица пуста)"""
    self.cursor.execute("SELECT COUNT(*) FROM songs")
    if self.cursor.fetchone()[0] == 0:
        all_songs = [
            ("Айдахар", "Ирина Кайратовна"),
            ("Банк", "Zivert"),
            ("Дожди-пистолеты", "Звери"),
            ("Знаешь ли ты", "Максим"),
            ("Паруса", "Zivert"),
            ("Плачу на техно", "Cream Soda"),
            ("Прощание", "Три дня дождя"),
            ("Ресницы", "Братья Гримм"),
            ("Седая ночь", "Юрий Шатунов"),
            ("Я твой номер один", "Дима Билан"),
            ("Alors on Danse", "Stromae"),
            ("Begin", "Maneskin"),
            ("Personal Jesus", "Depeche Mode"),
            ("What Is Love / You my heart, you my soul", "Haddaway"),
            ("Как на войне", "Агата Кристи"),
            ("Лететь", "Амега"),
            ("Сансара", "Баста"),
            ("Текила любовь", "Валерий Меладзе"),
            ("Шелк", "Ваня Дмитриенко"),
            ("Держи", "Дима Билан"),
            ("Молния", "Дима Билан"),
            ("Самолеты", "Женя Трофимов, Комната культуры"),
            ("Все, что касается", "Звери"),
            ("Танцуй", "Звери"),
            ("Кукла колдуна", "Король и Шут"),
            ("Лесник", "Король и Шут"),
            ("Мамба", "Ленинград"),
            ("WWW", "Ленинград"),
            ("Остров", "Леонид Агутин"),
            ("Ничего не говори", "Рок острова"),
            ("Он тебя целует", "Руки Вверх!"),
            ("18 мне уже", "Руки Вверх!"),
            ("Понарошку", "Тима Акимов"),
            ("Отшумели летние дожди", "Шура"),
            ("Ты не верь слезам", "Шура"),
            ("Комета", "JONY"),
            ("Проститься", "Uma2rman"),
            ("Пожары", "XOLIDAYBOY"),
        ]
        
        self.cursor.executemany(
            "INSERT INTO songs (title, artist) VALUES (?, ?)", 
            all_songs
        )
        self.conn.commit()
    
    # ===== Методы для гостей =====
    
    def register_session(self, session_id, table_number, user_name):
        """Регистрация новой сессии гостя"""
        now = self.get_current_time()
        
        # Проверяем, активен ли стол
        self.cursor.execute(
            "SELECT * FROM tables WHERE table_number = ?",
            (table_number,)
        )
        table = self.cursor.fetchone()
        
        if not table:
            # Новый стол
            self.cursor.execute('''
                INSERT INTO tables (table_number, current_session_id, current_user_name, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (table_number, session_id, user_name, now))
        else:
            # Обновляем существующий стол
            self.cursor.execute('''
                UPDATE tables 
                SET current_session_id = ?, current_user_name = ?, is_active = 1, updated_at = ?
                WHERE table_number = ?
            ''', (session_id, user_name, now, table_number))
        
        # Сохраняем сессию
        self.cursor.execute('''
            INSERT INTO users (session_id, table_number, user_name, created_at)
            VALUES (?, ?, ?, ?)
        ''', (session_id, table_number, user_name, now))
        
        self.conn.commit()
        return True
    
    def get_session(self, session_id):
        """Получить информацию о сессии"""
        self.cursor.execute(
            "SELECT * FROM users WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        )
        return self.cursor.fetchone()
    
    def get_table_info(self, table_number):
        """Получить информацию о столе"""
        self.cursor.execute(
            "SELECT * FROM tables WHERE table_number = ?",
            (table_number,)
        )
        return self.cursor.fetchone()
    
    def is_table_locked(self, table_number):
        """Проверить, заблокирован ли стол"""
        self.cursor.execute(
            "SELECT locked_until FROM tables WHERE table_number = ?",
            (table_number,)
        )
        result = self.cursor.fetchone()
        if result and result['locked_until']:
            locked_until = datetime.fromisoformat(result['locked_until'])
            return locked_until > self.get_current_time(), locked_until
        return False, None
    
    def lock_table(self, table_number, duration_seconds=60):
        """Заблокировать стол на duration_seconds секунд"""
        now = self.get_current_time()
        locked_until = now + timedelta(seconds=duration_seconds)
        
        self.cursor.execute('''
            UPDATE tables 
            SET locked_until = ?, updated_at = ?
            WHERE table_number = ?
        ''', (locked_until.isoformat(), now, table_number))
        
        self.conn.commit()
        return locked_until
    
    # ===== Методы для песен =====
    
    def get_available_songs(self):
        """Получить новые песни (которые ещё не пели)"""
        self.cursor.execute('''
            SELECT s.song_id, s.title, s.artist 
            FROM songs s
            LEFT JOIN song_locks l ON s.song_id = l.song_id
            WHERE l.song_id IS NULL
            ORDER BY s.title
        ''')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_paid_songs(self):
        """Получить повторы (песни, которые уже пели)"""
        self.cursor.execute('''
            SELECT s.song_id, s.title, s.artist,
                   l.first_table, l.first_user_name
            FROM song_locks l
            JOIN songs s ON l.song_id = s.song_id
            ORDER BY l.locked_at DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def is_song_sung(self, song_id):
        """Проверить, пелась ли песня"""
        self.cursor.execute(
            "SELECT * FROM song_locks WHERE song_id = ?",
            (song_id,)
        )
        return self.cursor.fetchone() is not None
    
    def get_song_info(self, song_id):
        """Получить информацию о песне"""
        self.cursor.execute(
            "SELECT * FROM songs WHERE song_id = ?",
            (song_id,)
        )
        return self.cursor.fetchone()
    
    # ===== Методы для заказов =====
    
    def create_order(self, table_number, session_id, user_name, song_id, order_type):
        """Создать заказ"""
        now = self.get_current_time()
        price = FREE_PRICE if order_type == 'free' else PAID_PRICE
        
        # Проверяем возможность заказа
        if order_type == 'free' and self.is_song_sung(song_id):
            return False, "Эту песню уже кто-то спел"
        
        if order_type == 'paid' and not self.is_song_sung(song_id):
            return False, "Эту песню ещё никто не пел"
        
        # Создаем заказ
        self.cursor.execute('''
            INSERT INTO orders 
            (table_number, session_id, user_name, song_id, order_type, price, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (table_number, session_id, user_name, song_id, order_type, price, now))
        
        # Если это первый заказ песни (free) - блокируем её
        if order_type == 'free' and not self.is_song_sung(song_id):
            self.cursor.execute('''
                INSERT INTO song_locks (song_id, first_table, first_user_name, locked_at)
                VALUES (?, ?, ?, ?)
            ''', (song_id, table_number, user_name, now))
        
        # Обновляем долг стола
        self.cursor.execute('''
            UPDATE tables 
            SET total_debt = total_debt + ?, updated_at = ?
            WHERE table_number = ?
        ''', (price, now, table_number))
        
        self.conn.commit()
        return True, "Заказ создан"
    
    def get_table_debt(self, table_number):
        """Получить текущий долг стола"""
        self.cursor.execute(
            "SELECT total_debt FROM tables WHERE table_number = ?",
            (table_number,)
        )
        result = self.cursor.fetchone()
        return result['total_debt'] if result else 0
    
    # ===== Методы для админа =====
    
    def get_all_tables(self):
        """Получить информацию по всем активным столам"""
        self.cursor.execute('''
            SELECT * FROM tables 
            WHERE is_active = 1 
            ORDER BY table_number
        ''')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_pending_orders(self):
        """Получить все неоплаченные заказы"""
        self.cursor.execute('''
            SELECT o.*, s.title, s.artist 
            FROM orders o
            JOIN songs s ON o.song_id = s.song_id
            WHERE o.status = 'pending'
            ORDER BY o.created_at DESC
        ''')
        return [dict(row) for row in self.cursor.fetchall()]
    
    def mark_table_as_paid(self, table_number):
        """Отметить стол как оплаченный"""
        now = self.get_current_time()
        
        # Обновляем статус заказов
        self.cursor.execute('''
            UPDATE orders 
            SET status = 'completed', completed_at = ?
            WHERE table_number = ? AND status = 'pending'
        ''', (now, table_number))
        
        # Обнуляем долг стола
        self.cursor.execute('''
            UPDATE tables 
            SET total_debt = 0, updated_at = ?
            WHERE table_number = ?
        ''', (now, table_number))
        
        self.conn.commit()
        return True
    
    def close_table(self, table_number):
        """Закрыть столик (гости ушли)"""
        now = self.get_current_time()
        
        # Помечаем стол как неактивный
        self.cursor.execute('''
            UPDATE tables 
            SET is_active = 0, 
                current_session_id = NULL, 
                current_user_name = NULL,
                total_debt = 0,
                updated_at = ?
            WHERE table_number = ?
        ''', (now, table_number))
        
        # Все неоплаченные заказы помечаем как завершённые (админ закроет отдельно)
        self.cursor.execute('''
            UPDATE orders 
            SET status = 'cancelled', completed_at = ?
            WHERE table_number = ? AND status = 'pending'
        ''', (now, table_number))
        
        self.conn.commit()
        return True
    
    def reset_all_data(self):
        """Сбросить все данные (новый день)"""
        now = self.get_current_time()
        
        # Очищаем все заказы
        self.cursor.execute("DELETE FROM orders")
        
        # Очищаем блокировки песен
        self.cursor.execute("DELETE FROM song_locks")
        
        # Очищаем столы
        self.cursor.execute("DELETE FROM tables")
        
        # Очищаем сессии пользователей (можно оставить для истории)
        self.cursor.execute("DELETE FROM users")
        
        self.conn.commit()
        return True
    
    def close(self):
        self.conn.close()
