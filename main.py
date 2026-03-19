from fastapi import FastAPI, Request, HTTPException, Depends, Cookie, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uuid
import json
import asyncio
import logging  # Добавлено для логирования
import traceback  # Добавлено для детального вывода ошибок
from typing import Optional
# import qrcode
# from io import BytesIO
# import base64
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
import os

from database import Database
from config import *

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
# Создаем папку для логов, если её нет
os.makedirs("logs", exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log", encoding='utf-8'),  # Все логи
        logging.FileHandler("logs/errors.log", encoding='utf-8'),  # Только ошибки
        logging.StreamHandler()  # Вывод в консоль
    ]
)

# Создаем логгеры для разных целей
app_logger = logging.getLogger("app")
error_logger = logging.getLogger("errors")
access_logger = logging.getLogger("access")

# Устанавливаем уровни
error_logger.setLevel(logging.ERROR)
app_logger.setLevel(logging.INFO)
access_logger.setLevel(logging.INFO)

# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========
app = FastAPI(title=APP_NAME, version=APP_VERSION)

# ========== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ==========
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик всех исключений"""
    error_id = str(uuid.uuid4())[:8]  # Уникальный ID ошибки для отслеживания
    
    # Подробное логирование ошибки
    error_details = {
        "error_id": error_id,
        "url": str(request.url),
        "method": request.method,
        "client": request.client.host if request.client else "unknown",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": traceback.format_exc()
    }
    
    # Записываем в лог
    error_logger.error(f"❌ Ошибка {error_id}: {error_details}")
    app_logger.error(f"Ошибка {error_id}: {str(exc)}")
    
    # Для отладки выводим в консоль
    print(f"\n🔴 ОШИБКА {error_id}: {str(exc)}")
    print(traceback.format_exc())
    
    # Возвращаем пользователю понятное сообщение
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Внутренняя ошибка сервера",
            "error_id": error_id,
            "message": "Пожалуйста, сообщите администратору этот ID: " + error_id
        }
    )

# ========== МИДЛВАР ДЛЯ ЛОГИРОВАНИЯ ЗАПРОСОВ ==========
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование всех HTTP запросов"""
    start_time = datetime.now()
    
    # Логируем входящий запрос
    access_logger.info(f"➡️ {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Считаем время выполнения
        process_time = (datetime.now() - start_time).total_seconds()
        
        # Логируем ответ
        access_logger.info(
            f"⬅️ {request.method} {request.url.path} - {response.status_code} "
            f"({process_time:.3f}с)"
        )
        
        # Добавляем заголовок с временем обработки
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # Если произошла ошибка, она будет обработана глобальным обработчиком
        access_logger.error(f"❌ {request.method} {request.url.path} - Ошибка: {str(e)}")
        raise

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Создаем папки, если их нет
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("qr_codes", exist_ok=True)

# Подключаем базу данных
try:
    db = Database()
    app_logger.info("✅ База данных подключена успешно")
except Exception as e:
    error_logger.error(f"❌ Ошибка подключения к БД: {e}")
    raise

# Хранилище для WebSocket соединений админов
admin_connections = []

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def generate_session_id():
    """Генерирует уникальный ID сессии"""
    return str(uuid.uuid4())

def get_client_info(request: Request):
    """Получает информацию о клиенте"""
    return {
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent", "")
    }

async def notify_admins(message: dict):
    """Отправляет уведомление всем подключенным админам через WebSocket"""
    for connection in admin_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            error_logger.error(f"Ошибка отправки уведомления админу: {e}")

# ========== ГОСТЕВЫЕ МАРШРУТЫ ==========

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: Optional[str] = Cookie(None)):
    """Главная страница"""
    try:
        # Проверяем, есть ли активная сессия
        current_session = None
        table_info = None
        
        if session:
            session_data = db.get_session(session)
            if session_data:
                table_info = db.get_table_info(session_data['table_number'])
                if table_info and table_info['is_active']:
                    current_session = {
                        'session_id': session,
                        'table_number': session_data['table_number'],
                        'user_name': session_data['user_name']
                    }
        
        app_logger.info(f"Главная страница загружена, сессия: {session}")
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "current_session": current_session,
                "table_info": table_info
            }
        )
    except Exception as e:
        error_logger.error(f"Ошибка в index: {e}")
        raise

@app.get("/menu", response_class=HTMLResponse)
async def menu_page(request: Request, table: int, name: str, session: Optional[str] = Cookie(None)):
    """Страница меню для конкретного стола"""
    try:
        # Если нет сессии или она не совпадает, создаем новую
        if not session:
            session = generate_session_id()
            db.register_session(session, table, name)
            app_logger.info(f"Новая сессия создана: {session} для стола {table}")
        else:
            session_data = db.get_session(session)
            if not session_data or session_data['table_number'] != table:
                session = generate_session_id()
                db.register_session(session, table, name)
                app_logger.info(f"Сессия обновлена: {session} для стола {table}")
        
        response = templates.TemplateResponse(
            "menu.html",
            {
                "request": request,
                "table_number": table,
                "user_name": name,
                "session_id": session
            }
        )
        response.set_cookie(key="session", value=session)
        return response
        
    except Exception as e:
        error_logger.error(f"Ошибка в menu_page для стола {table}: {e}")
        raise

@app.get("/api/songs")
async def get_songs(table: int, session: str):
    """API для получения списка песен"""
    try:
        # Проверяем блокировку стола
        locked, locked_until = db.is_table_locked(table)
        remaining = 0
        if locked and locked_until:
            now = datetime.now(TIMEZONE)
            remaining = int((locked_until - now).total_seconds())
        
        available_songs = db.get_available_songs()
        paid_songs = db.get_paid_songs()
        
        app_logger.info(f"Загружено песен для стола {table}: новых {len(available_songs)}, повторов {len(paid_songs)}")
        
        return {
            "available": available_songs,
            "paid": paid_songs,
            "table_locked": locked,
            "lock_remaining": max(0, remaining),
            "debt": db.get_table_debt(table)
        }
        
    except Exception as e:
        error_logger.error(f"Ошибка получения песен для стола {table}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки песен")

@app.post("/api/order")
async def create_order(request: Request):
    """API для создания заказа"""
    try:
        data = await request.json()
        
        table = data.get('table')
        session = data.get('session')
        song_id = data.get('song_id')
        order_type = data.get('type')
        
        app_logger.info(f"Заказ: стол {table}, песня {song_id}, тип {order_type}")
        
        # Получаем информацию о сессии
        session_data = db.get_session(session)
        if not session_data or session_data['table_number'] != table:
            error_logger.warning(f"Недействительная сессия для стола {table}")
            raise HTTPException(status_code=401, detail="Сессия недействительна")
        
        # Проверяем блокировку стола
        locked, _ = db.is_table_locked(table)
        if locked:
            error_logger.warning(f"Попытка заказа на заблокированный стол {table}")
            raise HTTPException(status_code=400, detail="Стол заблокирован")
        
        # Создаем заказ
        success, message = db.create_order(
            table, 
            session, 
            session_data['user_name'], 
            song_id, 
            order_type
        )
        
        if not success:
            error_logger.warning(f"Ошибка создания заказа для стола {table}: {message}")
            raise HTTPException(status_code=400, detail=message)
        
        # Блокируем стол
        db.lock_table(table, LOCK_DURATION)
        
        # Получаем информацию о песне
        song = db.get_song_info(song_id)
        
        app_logger.info(f"✅ Заказ успешно создан для стола {table}")
        
        # Уведомляем админов о новом заказе
        await notify_admins({
            "type": "new_order",
            "data": {
                "table": table,
                "user_name": session_data['user_name'],
                "song": dict(song) if song else None,
                "order_type": order_type,
                "price": FREE_PRICE if order_type == 'free' else PAID_PRICE,
                "time": datetime.now(TIMEZONE).strftime("%H:%M")
            }
        })
        
        return {"success": True, "message": message}
        
    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Неожиданная ошибка при создании заказа: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/api/table/{table}/status")
async def table_status(table: int):
    """API для получения статуса стола"""
    try:
        locked, locked_until = db.is_table_locked(table)
        remaining = 0
        if locked and locked_until:
            now = datetime.now(TIMEZONE)
            remaining = int((locked_until - now).total_seconds())
        
        return {
            "locked": locked,
            "remaining": max(0, remaining),
            "debt": db.get_table_debt(table)
        }
        
    except Exception as e:
        error_logger.error(f"Ошибка получения статуса стола {table}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статуса")

# ========== АДМИНСКИЕ МАРШРУТЫ ==========

@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Страница входа в админку"""
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request):
    """Вход в админку"""
    try:
        data = await request.json()
        password = data.get('password')
        
        if password != ADMIN_PASSWORD:
            error_logger.warning(f"Неудачная попытка входа в админку с IP {request.client.host}")
            raise HTTPException(status_code=401, detail="Неверный пароль")
        
        app_logger.info(f"Успешный вход в админку с IP {request.client.host}")
        
        response = JSONResponse({"success": True})
        response.set_cookie(key="admin_auth", value="true", httponly=True)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Ошибка при входе в админку: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin_auth: Optional[str] = Cookie(None)):
    """Админ панель"""
    if admin_auth != "true":
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Требуется авторизация"})
    
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/api/admin/tables")
async def admin_get_tables(admin_auth: Optional[str] = Cookie(None)):
    """API для получения всех столов с группировкой по гостям"""
    if admin_auth != "true":
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        # Получаем все заказы
        all_orders = db.get_pending_orders()
        
        # Группируем по столам
        tables_dict = {}
        
        for order in all_orders:
            table_num = order['table_number']  # или 'table' - зависит от структуры
            
            if table_num not in tables_dict:
                tables_dict[table_num] = {
                    'table': table_num,
                    'total': 0,
                    'guests': set(),  # используем set для уникальных гостей
                    'orders': [],
                    'locked_until': order.get('locked_until'),
                    'is_locked': order.get('is_locked', False)
                }
            
            # Добавляем гостя (если есть поле с именем)
            if 'user_name' in order:
                tables_dict[table_num]['guests'].add(order['user_name'])
            
            # Считаем сумму
            price = FREE_PRICE if order.get('order_type') == 'free' else PAID_PRICE
            tables_dict[table_num]['total'] += price
            
            # Сохраняем заказ для деталей
            tables_dict[table_num]['orders'].append({
                'song_name': order.get('song_name', ''),
                'user_name': order.get('user_name', ''),
                'price': price,
                'time': order.get('created_at', ''),
                'order_type': order.get('order_type', '')
            })
        
        # Преобразуем set в список для JSON
        result_tables = []
        for table_num, data in tables_dict.items():
            data['guests'] = list(data['guests'])
            result_tables.append(data)
        
        # Сортируем по номеру стола
        result_tables.sort(key=lambda x: x['table'])
        
        app_logger.info(f"Админ запросил данные: {len(result_tables)} столов с группировкой гостей")
        
        return {
            "tables": result_tables,
            "pending_orders": all_orders  # оставляем для обратной совместимости
        }
        
    except Exception as e:
        error_logger.error(f"Ошибка получения данных для админа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки данных")
        
@app.post("/api/admin/table/{table}/close")
async def admin_close_table(table: int, admin_auth: Optional[str] = Cookie(None)):
    """Закрыть столик"""
    if admin_auth != "true":
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        db.close_table(table)
        app_logger.info(f"Админ закрыл стол {table}")
        
        # Уведомляем админов
        await notify_admins({
            "type": "table_closed",
            "data": {"table": table}
        })
        
        return {"success": True}
    except Exception as e:
        error_logger.error(f"Ошибка при закрытии стола {table}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при закрытии стола")

@app.post("/api/admin/reset")
async def admin_reset(admin_auth: Optional[str] = Cookie(None)):
    """Сбросить все данные (новый день)"""
    if admin_auth != "true":
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        db.reset_all_data()
        app_logger.info("⚠️ Админ выполнил сброс всех данных (новый день)")
        
        # Уведомляем админов
        await notify_admins({
            "type": "system_reset",
            "data": {"message": "Все данные сброшены"}
        })
        
        return {"success": True}
    except Exception as e:
        error_logger.error(f"Ошибка при сбросе данных: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при сбросе")

# ========== WEBSOCKET ДЛЯ АДМИНОВ ==========

@app.websocket("/admin/ws")
async def admin_websocket(websocket: WebSocket):
    """WebSocket соединение для админов"""
    await websocket.accept()
    
    # Проверяем куку авторизации
    cookies = websocket.cookies
    if cookies.get("admin_auth") != "true":
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    client_host = websocket.client.host if websocket.client else "unknown"
    app_logger.info(f"Админ подключился по WebSocket: {client_host}")
    
    admin_connections.append(websocket)
    try:
        while True:
            # Ждем сообщения от клиента (keep-alive)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        admin_connections.remove(websocket)
        app_logger.info(f"Админ отключился: {client_host}")
    except Exception as e:
        error_logger.error(f"Ошибка WebSocket: {e}")
        if websocket in admin_connections:
            admin_connections.remove(websocket)

# # ========== QR-КОДЫ ==========

# @app.get("/admin/qr-codes")
# async def generate_qr_codes(admin_auth: Optional[str] = Cookie(None)):
#     """Генерирует PDF с QR-кодами для всех столов"""
#     if admin_auth != "true":
#         raise HTTPException(status_code=401, detail="Не авторизован")
    
#     try:
#         # Создаем PDF
#         pdf_path = "qr_codes/tables_qr.pdf"
#         c = canvas.Canvas(pdf_path, pagesize=A4)
#         width, height = A4
        
#         # Размеры QR-кода (40x40 мм)
#         qr_size = 40 * mm
#         margin = 10 * mm
        
#         # Генерируем QR-коды для всех столов
#         x = margin
#         y = height - margin - qr_size
#         col = 0
#         max_cols = 4  # 4 QR-кода в ряд
        
#         for table in range(MIN_TABLE, MAX_TABLE + 1):
#             # URL для стола
#             url = f"{SITE_DOMAIN}/menu?table={table}"
            
#             # Генерируем QR-код
#             qr = qrcode.QRCode(
#                 version=1,
#                 box_size=10,
#                 border=5,
#             )
#             qr.add_data(url)
#             qr.make(fit=True)
#             qr_img = qr.make_image(fill_color="black", back_color="white")
            
#             # Сохраняем временно
#             temp_path = f"qr_codes/table_{table}.png"
#             qr_img.save(temp_path)
            
#             # Вставляем в PDF
#             c.drawImage(temp_path, x, y, width=qr_size, height=qr_size)
#             c.setFont("Helvetica", 12)
#             c.drawString(x + qr_size/2 - 15, y - 10, f"Стол {table}")
            
#             # Переходим к следующей позиции
#             x += qr_size + margin
#             col += 1
            
#             if col >= max_cols:
#                 col = 0
#                 x = margin
#                 y -= (qr_size + margin + 20)  # +20 для подписи
#                 if y < margin:  # Новая страница
#                     c.showPage()
#                     y = height - margin - qr_size
            
#             # Удаляем временный файл
#             os.remove(temp_path)
        
#         c.save()
        
#         app_logger.info(f"Сгенерирован PDF с QR-кодами для столов {MIN_TABLE}-{MAX_TABLE}")
        
#         return FileResponse(
#             pdf_path,
#             media_type='application/pdf',
#             filename=f'qr_codes_stoly_{MIN_TABLE}-{MAX_TABLE}.pdf'
#         )
        
#     except Exception as e:
#         error_logger.error(f"Ошибка генерации QR-кодов: {e}")
#         raise HTTPException(status_code=500, detail="Ошибка генерации QR-кодов")

# ========== ЗАПУСК ==========
application = app

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*50)
    print(f"🚀 ЗАПУСК {APP_NAME} v{APP_VERSION}")
    print("="*50)
    print(f"📍 Часовой пояс: {TIMEZONE}")
    print(f"💰 Цены: новые {FREE_PRICE}₽, повторы {PAID_PRICE}₽")
    print(f"🔒 Админ пароль: {ADMIN_PASSWORD}")
    print(f"⏱️  Блокировка стола: {LOCK_DURATION} сек ({LOCK_DURATION/60} мин)")
    print(f"📝 Логи сохраняются в папке /logs")
    print("="*50)
    print("\n🌐 Откройте в браузере: http://localhost:8000")
    print("🔐 Админка: http://localhost:8000/admin")
    print("="*50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
