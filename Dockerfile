# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

RUN apt-get update && apt install -y netcat-traditional && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект (все файлы бэкенда из корня)
COPY . .

EXPOSE 8000

# Команда для запуска FastAPI приложения
CMD ["./entrypoint.sh"]
