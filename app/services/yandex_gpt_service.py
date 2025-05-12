import json
from typing import List, Dict, Any, Optional, Type
# Use the Async client for async operations
from yandex_cloud_ml_sdk import AsyncYCloudML
# Import the result types explicitly for type checking
from yandex_cloud_ml_sdk._models.completions.result import GPTModelResult, Alternative
# Import Pydantic for structured output
from pydantic import BaseModel, Field, ValidationError 

from app.schemas.sprint_report import Recommendation
from app.config import settings
# Import prompt templates
from app.schemas.yandex_tracker import Task
from app.services import prompts
from app.services.report_service import SprintStats 
import logging

log = logging.getLogger(__name__)

# --- Pydantic models for LLM Responses ---
class TextResponse(BaseModel):
    """Pydantic model for simple text responses, expecting {"text": "..."}."""
    text: str = Field(description="The generated text content.")

class RecommendationsResponse(BaseModel):
    """Pydantic model for list of recommendations, expecting {"recommendations": [...]} ."""
    recommendations: List[Recommendation] = Field(description="List of recommendations.")

class RatingResponse(BaseModel):
    """Pydantic model for employee rating and explanation, expecting {"rating": N, "explanation": "..."}."""
    rating: int = Field(ge=1, le=5, description="The numerical rating (1-5).")
    explanation: str = Field(description="The explanation for the rating.")

class TeamRatingItem(BaseModel):
    employee_id: str
    rating: int = Field(ge=1, le=5)
    rating_explanation: str

class TeamRatingList(BaseModel):
    ratings: List[TeamRatingItem]

# --- End Pydantic models ---

class YandexGPTMLService:
    """
    ML Service implementation using Yandex GPT via yandex-cloud-ml-sdk.
    Uses the SDK's asynchronous interface (AsyncYCloudML), configures response_format
    with the target Pydantic model, extracts JSON from the result object, and parses it.
    """

    def __init__(self):
        if not settings.yc_folder_id:
            raise ValueError("Yandex Cloud Folder ID (YC_FOLDER_ID) is not configured.")
        
        auth_param = None
        if settings.yc_api_key:
            auth_param = settings.yc_api_key
        elif settings.yc_iam_token:
            auth_param = settings.yc_iam_token
            
        if not auth_param:
             print("Warning: No YC_API_KEY or YC_IAM_TOKEN found. Attempting SDK default auth.")

        try:
            # Initialize AsyncYCloudML for asynchronous operations
            self.sdk = AsyncYCloudML(folder_id=settings.yc_folder_id, auth=auth_param)
            # Get the base model object. Specific configuration (like response_format) 
            # will be applied per-request in the helper method.
            self.base_model = self.sdk.models.completions(settings.yc_gpt_model, model_version=settings.yc_gpt_version).configure(
                temperature=settings.yc_gpt_temperature,
                max_tokens=settings.yc_gpt_max_tokens,
                # No response_format here, set per call
            )
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Yandex Cloud ML SDK: {e}. Ensure credentials are set.") from e

    async def _call_llm_structured(
        self, 
        system_prompt: Optional[str], 
        user_prompt: str,
        response_model: Type[BaseModel] # Use Type for type hints
    ) -> BaseModel:
        """Calls Yandex GPT API async, requests structured output, extracts JSON from result, parses and returns Pydantic instance."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})
        messages.append({"role": "user", "text": user_prompt})

        result = None # For error reporting
        json_string = None # For error reporting
        try:
            # Configure the model specifically for this request with the target Pydantic model
            configured_model = self.base_model.configure(response_format=response_model)

            # Use await with 'run'. Expect SDK to return a GPTModelResult object.
            log.debug(f"Run configured model: {configured_model}")
            result = await configured_model.run(messages)
            
            # Validate the result structure and extract the text containing JSON
            if not isinstance(result, GPTModelResult):
                 raise ConnectionError(f"Received unexpected response type from SDK. Expected GPTModelResult, got: {type(result)}. Value: {result}")
            if not result.alternatives:
                 raise ConnectionError(f"Received no alternatives in GPTModelResult. Value: {result}")
            
            # Assuming the first alternative contains the desired JSON string
            alternative = result.alternatives[0]
            if not isinstance(alternative, Alternative) or not alternative.text:
                 raise ConnectionError(f"Invalid or empty alternative in GPTModelResult. Alternative: {alternative}")
                 
            json_string = alternative.text
            log.debug(f"JSON string: {json_string}")

            # Parse the extracted JSON string using the expected Pydantic model.
            parsed_response = response_model.parse_raw(json_string)
            log.debug(f"Parsed response: {parsed_response}")
            return parsed_response
            
        except json.JSONDecodeError as jde:
            # Handle errors if the extracted text is not valid JSON
            print(f"Yandex GPT JSON Decode Error: {jde}. Extracted text: '{json_string}'")
            raise ConnectionError(f"LLM response text was not valid JSON: {jde}. Text: '{json_string}'") from jde
        except ValidationError as ve:
            # Handle Pydantic validation errors if the JSON structure doesn't match the model
             print(f"Yandex GPT Pydantic Validation Error: {ve}. Extracted text: '{json_string}'")
             raise ConnectionError(f"LLM response failed validation for {response_model.__name__}: {ve}. Text: '{json_string}'") from ve
        except ConnectionError as ce:
            # Re-raise specific ConnectionErrors from validation/extraction logic
            raise ce
        except Exception as e:
            # Catch other potential errors (network, SDK internal, credentials, etc.)
            print(f"Yandex GPT ML SDK Async Error: {e}. Raw result: {result}")
            # Check if the error message indicates an issue with structured response format itself
            error_str = str(e).lower()
            if "unprocessable entity" in error_str or "structured output" in error_str or "response_format" in error_str:
                 # Include json_string if extraction was successful but something else failed
                 context = f"Text: '{json_string}'" if json_string else f"Raw result: {result}"
                 raise ConnectionError(f"LLM or SDK failed to process structured output request ({response_model.__name__}): {e}. {context}") from e
            # Include raw result in generic error if available
            error_suffix = f". Raw result: {result}" if result else ""
            raise ConnectionError(f"Failed async call via Yandex GPT ML SDK: {e}{error_suffix}") from e

    # --- Methods implementing BaseMLService interface using _call_llm_structured ---
    
    async def analyze_employee_activity(self, tasks: list[Task], sprint_stats: SprintStats) -> str:
        system_prompt = prompts.EMPLOYEE_ACTIVITY_SYSTEM
        task_descriptions = [f"Summary: {task.summary}. Status: {task.status.key}" for task in tasks]
        task_descriptions_str = "\n".join(task_descriptions) or "Нет задач для анализа."
        user_prompt = prompts.EMPLOYEE_ACTIVITY_USER.format(
            task_descriptions=task_descriptions_str,
            story_points_closed=sprint_stats.total_story_points,
            tasks_completed=sprint_stats.total_tasks,
            deadlines_missed=sprint_stats.deadlines_missed,
            average_task_completion_time=sprint_stats.average_completion_time
        )
        response_obj = await self._call_llm_structured(system_prompt, user_prompt, response_model=TextResponse)
        return response_obj.text

    async def generate_employee_recommendations(self, tasks: List[Task], sprint_stats: SprintStats) -> List[Recommendation]:
        system_prompt = prompts.EMPLOYEE_RECOMMENDATIONS_SYSTEM
                
        user_prompt = prompts.EMPLOYEE_RECOMMENDATIONS_USER.format(
            story_points_closed=sprint_stats.total_story_points,
            tasks_completed=sprint_stats.total_tasks,
            deadlines_missed=sprint_stats.deadlines_missed,
            average_task_completion_time=sprint_stats.average_completion_time,
        )

        response_obj = await self._call_llm_structured(system_prompt, user_prompt, response_model=RecommendationsResponse)
        return response_obj.recommendations[:3] 


    async def analyze_team_activity(self, tasks_by_employee: Dict[str, List[Dict[str, Any]]]) -> str:
        system_prompt = prompts.TEAM_ACTIVITY_SYSTEM
        
        total_tasks = sum(len(t) for t in tasks_by_employee.values())
        total_completed = sum(sum(1 for task in tasks if task.get('is_completed')) for tasks in tasks_by_employee.values())
        avg_completion_rate = (total_completed / total_tasks * 100) if total_tasks > 0 else 0
        
        user_prompt = prompts.TEAM_ACTIVITY_USER.format(
            total_tasks=total_tasks,
            total_completed=total_completed,
            avg_completion_rate=avg_completion_rate
        )

        # Expect a Pydantic object matching TextResponse
        response_obj = await self._call_llm_structured(system_prompt, user_prompt, response_model=TextResponse)
        return response_obj.text


    async def generate_team_recommendations(self, team_sprint_stats: Dict[str, Any]) -> List[Recommendation]:
        system_prompt = prompts.TEAM_RECOMMENDATIONS_SYSTEM
        
        user_prompt = prompts.TEAM_RECOMMENDATIONS_USER.format(
            total_story_points_closed=team_sprint_stats.get('total_story_points_closed', 0),
            total_tasks_completed=team_sprint_stats.get('total_tasks_completed', 0),
            total_deadlines_missed=team_sprint_stats.get('total_deadlines_missed', 0),
            avg_task_completion_time=team_sprint_stats.get('avg_task_completion_time', 0)
        )

        response_obj = await self._call_llm_structured(system_prompt, user_prompt, response_model=RecommendationsResponse)
        return response_obj.recommendations[:3]

    async def rate_employee_performance(self, employee_id: str, sprint_stats: Dict[str, Any], tasks: List[Dict[str, Any]],
                                 previous_sprint_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        system_prompt = prompts.EMPLOYEE_RATING_SYSTEM
        
        current_stats_str = f"Текущий спринт: SP={sprint_stats.get('story_points_closed', 0)}, Задачи={sprint_stats.get('tasks_completed', 0)}, Пропуски={sprint_stats.get('deadlines_missed', 0)}, Ср.Время={sprint_stats.get('average_task_completion_time', 0):.1f}ч"
        previous_stats_str = ""
        if previous_sprint_stats:
            previous_stats_str = f" Предыдущий спринт: SP={previous_sprint_stats.get('story_points_closed', 0)}, Задачи={previous_sprint_stats.get('tasks_completed', 0)}, Пропуски={previous_sprint_stats.get('deadlines_missed', 0)}, Ср.Время={previous_sprint_stats.get('average_task_completion_time', 0):.1f}ч"
            
        completed_task_titles = [t.get('title', 'Без названия') for t in tasks if t.get('is_completed')]
        task_titles_str = "\n".join([f"- {title}" for title in completed_task_titles]) or "Завершенных задач нет."
            
        user_prompt = prompts.EMPLOYEE_RATING_USER.format(
            employee_id=employee_id,
            current_stats_str=current_stats_str,
            previous_stats_str=previous_stats_str,
            task_titles_str=task_titles_str
        )
        
        response_obj = await self._call_llm_structured(system_prompt, user_prompt, response_model=RatingResponse)
        # Return dict matching expected format
        return {
            "rating": response_obj.rating,
            "explanation": response_obj.explanation
        }

    async def rate_team_performance(
        self,
        current_user_id: int,
        employee_stats: list[dict],
        prev_employee_stats: list[dict] | None = None,
    ) -> list[dict]:
        """
        Анализирует командные метрики и возвращает список рейтингов и объяснений для каждого сотрудника.
        """
        # Формируем блоки для промпта
        def stats_block(stats_list):
            lines = []
            for emp in stats_list:
                log.debug(f"Emp: {emp}")
                lines.append(
                    f"- {emp['employee_name']} (ID: {emp['employee_id']}): SP={emp['story_points_closed']['current']}, "
                    f"Задачи={emp['tasks_completed']['current']}, Пропуски={emp['deadlines_missed']['current']}, "
                    f"Ср.Время={emp['average_task_completion_time']['current']}"
                )
            return '\n'.join(lines)
        employee_stats_block = stats_block(employee_stats)
        prev_employee_stats_block = stats_block(prev_employee_stats) if prev_employee_stats else "нет данных"
        log.debug(f"Employee stats block: {employee_stats_block}")
        log.debug(f"Prev employee stats block: {prev_employee_stats_block}")
        system_prompt = prompts.TEAM_RATING_SYSTEM
        log.debug(f"System prompt: {system_prompt}")
        user_prompt = prompts.TEAM_RATING_USER.format(
            employee_stats_block=employee_stats_block,
            prev_employee_stats_block=prev_employee_stats_block
        )
        log.debug("!!!!!!")
        log.debug(f"User prompt: {user_prompt}")
        llm_response: TeamRatingList = await self._call_llm_structured(system_prompt, user_prompt, response_model=TeamRatingList)
        log.debug(f"LLM response: {llm_response}")
        return [item.model_dump() for item in llm_response.ratings]
