from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from typing import List
from ..services.yandex import YandexService
from ..dependencies import get_yandex_service, get_current_user
from ..schemas.user import UserModel
from ..schemas.task import TrackerData
from ..utils.promt import generate_employee_analysis_prompt
from ..services.token_manager import verify_token
import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/yandex", tags=["Yandex Tracker Integration"])
    
@router.get(
    "/profile",
    summary="Получить профиль пользователя в Яндекс.Трекере",
    response_description="Профиль пользователя",
    responses={
        200: {"description": "Успешное получение профиля"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_yandex_profile(user_id: int = Depends(get_current_user), service: YandexService = Depends(get_yandex_service)):
    """
        Получает профиль текущего пользователя из Яндекс.Трекера.
        
        Требуется:
        - Действительный JWT токен в заголовке Authorization
        
        Возвращает:
        - Объект с данными профиля пользователя
    """
    user = await service.get_user_profile(int(user_id))
    return user

@router.get(    
    "/set_org_id",
    summary="Установить organization_id для пользователя",
    response_description="Обновленный профиль пользователя",
    responses={
        200: {"description": "Organization ID успешно установлен"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    })
async def get_yandex_profile(
        organization_id: str,
        user_id: int = Depends(get_current_user), 
        service: YandexService = Depends(get_yandex_service)
    ):
    """
    Устанавливает organization_id для текущего пользователя.
    
    Параметры:
    - organization_id: Идентификатор организации в Яндекс.Трекере
    
    Возвращает:
    - Обновленный профиль пользователя с установленным organization_id
    """
    user = await service.set_org_id(int(user_id), organization_id)
    return user

@router.get("/users",
    response_model=List[UserModel],
    summary="Получить список пользователей",
    description="Возвращает список пользователей Яндекс.Трекера, исключая роботов",
    response_description="Список пользователей",
    responses={
        200: {"description": "Успешное получение списка пользователей"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    })
async def get_users(
    user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)
) -> List[UserModel]:
    """
    Получает список пользователей из Яндекс.Трекера, исключая системных роботов.
    
    Фильтрация:
    - Исключает пользователей с именами, начинающимися на "Робот сервиса"
    - Исключает пользователей с фамилией "Робот"
    - Исключает пользователей с логинами, заканчивающимися на "-robot"
    
    Возвращает:
    - Список объектов UserModel с данными пользователей
    """
    users_data = await service.get_users(int(user_id))
    filtered_users = [
        UserModel(**user) 
        for user in users_data
        if not (
            user.get("firstName", "").startswith("Робот сервиса") 
            or user.get("lastName") == "Робот"
            or user.get("login", "").endswith("-robot")
        )
    ]
    return filtered_users


@router.get(
    "/queues",
    summary="Получить список очередей",
    response_description="Список очередей",
    responses={
        200: {"description": "Успешное получение списка очередей"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_queues(user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)):
    """
    Получает список очередей задач из Яндекс.Трекера.
    
    Возвращает:
    - Список объектов очередей с их основными параметрами
    """
    queues = await service.get_queues(int(user_id))
    return queues

@router.get(
    "/queue",
    summary="Получить информацию об очереди",
    response_description="Данные очереди",
    responses={
        200: {"description": "Успешное получение данных очереди"},
        401: {"description": "Не авторизован"},
        404: {"description": "Очередь не найдена"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_queue(queue_id: int, user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)
    ):
    """
    Получает детальную информацию об указанной очереди.
    
    Параметры:
    - queue_id: Идентификатор очереди
    
    Возвращает:
    - Объект с полной информацией об очереди
    """
    queue = await service.get_queue(int(user_id), queue_id)
    return queue


@router.get(
    "/boards",
    summary="Получить список досок",
    response_description="Список досок",
    responses={
        200: {"description": "Успешное получение списка досок"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_boards(user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)):
    """
    Получает список досок из Яндекс.Трекера.
    
    Возвращает:
    - Список объектов досок с их основными параметрами
    """
    boards = await service.get_boards(int(user_id))
    return boards


@router.get(
    "/issues",
    summary="Получить список задач",
    response_description="Список задач",
    responses={
        200: {"description": "Успешное получение списка задач"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_issues(user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)):
    """
    Получает список задач пользователя из Яндекс.Трекера.
    
    Возвращает:
    - Список объектов задач с их основными параметрами
    """
    issues = await service.get_issues(int(user_id))
    return issues

@router.get(
    "/issue",
    summary="Получить информацию о задаче",
    response_description="Данные задачи",
    responses={
        200: {"description": "Успешное получение данных задачи"},
        401: {"description": "Не авторизован"},
        404: {"description": "Задача не найдена"},
        500: {"description": "Ошибка сервера"}
    }
)
async def get_issue(issue_key: str, user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)):
    """
    Получает детальную информацию об указанной задаче.
    
    Параметры:
    - issue_key: Ключ задачи (например, "KNOW-123")
    
    Возвращает:
    - Объект с полной информацией о задаче
    """
    issue = await service.get_issue(int(user_id), issue_key)
    return issue


@router.get(
    "/generate_prompt",
    summary="Сгенерировать промт для анализа задач",
    response_description="Сгенерированный промт",
    responses={
        200: {"description": "Промт успешно сгенерирован"},
        401: {"description": "Не авторизован"},
        500: {"description": "Ошибка генерации промта"}
    }
)
async def generate_prompt(user_id: int = Depends(get_current_user),
    service: YandexService = Depends(get_yandex_service)):
    """
    Генерирует аналитический промт на основе задач пользователя из Яндекс.Трекера.
    
    Процесс:
    1. Получает все задачи пользователя
    2. Анализирует статусы и другие параметры задач
    3. Формирует текстовый промт для дальнейшего анализа
    
    Возвращает:
    - Объект с полем "prompt", содержащим сгенерированный текст
    """
    try:
        tasks = await service.get_issues(int(user_id))
        if not tasks:
            return {}
        issues = TrackerData(tasks=tasks)
        prompt = generate_employee_analysis_prompt(issues.tasks)
        return {"prompt": prompt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
