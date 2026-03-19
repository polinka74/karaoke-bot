#!/bin/bash

echo "🚀 Начинаем деплой караоке-веб приложения..."

# Обновляем пакеты
apt update
apt upgrade -y

# Устанавливаем Python и pip
apt install -y python3-pip python3-venv nginx

# Создаем директорию для приложения
mkdir -p /var/www/karaoke
cd /var/www/karaoke

# Копируем файлы (это нужно будет сделать вручную или через git)
# git clone https://github.com/your-repo/karaoke-web.git .

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаем systemd сервис
cat > /etc/systemd/system/karaoke.service << EOF
[Unit]
Description=Karaoke Web Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/karaoke
Environment="PATH=/var/www/karaoke/venv/bin"
ExecStart=/var/www/karaoke/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Настраиваем nginx
cat > /etc/nginx/sites-available/karaoke << EOF
server {
    listen 80;
    server_name ваш-домен.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Для WebSocket
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static {
        alias /var/www/karaoke/static;
    }
}
EOF

# Активируем сайт
ln -s /etc/nginx/sites-available/karaoke /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# Запускаем сервис
systemctl daemon-reload
systemctl enable karaoke
systemctl start karaoke

echo "✅ Деплой завершен!"
echo "📱 Приложение доступно по адресу: http://ваш-домен.ru"
echo "🔐 Админ пароль: karaoke26"