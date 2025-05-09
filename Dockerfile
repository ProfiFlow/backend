# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект (все файлы бэкенда из корня)
COPY . .

# Команда для запуска FastAPI приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]