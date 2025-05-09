from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .routers import auth, debug, yandex
from .config import settings
from logging.config import dictConfig

# Конфигурация логирования
dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": True,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        "app": {  # Ваш логгер
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False
        },
    },
})

app = FastAPI()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="ProfiFlow",
        version="1.0.0",
        routes=app.routes,
    )
    
    # Добавляем кнопку авторизации в Swagger
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    # Исключаем определённые пути из требования авторизации
    exclude_paths = [
        "/api/auth/yandex/login",
        "/api/auth/yandex/callback", 
        "/docs",
        "/openapi.json"
    ]
    
    # Применяем security ко всем операциям
    for path in openapi_schema["paths"].values():
        if path not in exclude_paths:
            for method in path.values():
                method.setdefault("security", [{"BearerAuth": []}])
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(yandex.router)
app.include_router(debug.router)

@app.get("/")
async def root():
    return {"message": "Yandex Tracker Integration API"}