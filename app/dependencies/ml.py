from typing import Annotated

from fastapi import Depends

# Attempt to import the real service
try:
    from app.services.yandex_gpt_service import YandexGPTMLService
    YANDEX_GPT_AVAILABLE = True
except ImportError:
    YANDEX_GPT_AVAILABLE = False
    YandexGPTMLService = None
except ValueError as e:
    print(f"Configuration error loading YandexGPTMLService: {e}")
    YANDEX_GPT_AVAILABLE = False
    YandexGPTMLService = None

# --- Service Instances (Singletons for simplicity in this example) ---
# In a real app, you might manage lifespan differently (e.g., request-scoped)

mock_tracker_service = MockYandexTrackerService()

mock_ml_service = MockMLService()
yandex_gpt_service = None
if YANDEX_GPT_AVAILABLE and settings.YC_FOLDER_ID and (settings.YC_API_KEY or settings.YC_IAM_TOKEN):
    try:
        print("Initializing YandexGPTMLService instance for dependency injection")
        yandex_gpt_service = YandexGPTMLService()
    except Exception as e:
        print(f"Failed to initialize YandexGPTMLService instance: {e}")
        yandex_gpt_service = None # Ensure it's None if init fails

def get_ml_service() -> BaseMLService:
    """Provides an ML service instance, preferring YandexGPT if configured."""
    if yandex_gpt_service:
        print("Providing YandexGPTMLService via dependency")
        return yandex_gpt_service
    else:
        print("Providing MockMLService via dependency")
        return mock_ml_service

# --- Type Hinting for Dependencies --- 
# Using Annotated for clearer dependency definitions in route functions
TrackerServiceDep = Annotated[BaseTrackerService, Depends(get_tracker_service)]
MLServiceDep = Annotated[BaseMLService, Depends(get_ml_service)]
SettingsDep = Annotated[settings.__class__, Depends(lambda: settings)] # Simple settings dependency 
