from typing import List

from ..schemas.task import Task


# Функция для генерации промта на основе данных
def generate_employee_analysis_prompt(tasks: List[Task]) -> str:
    # Группируем задачи по сотрудникам
    employees = {}

    for task in tasks:
        if not task.assignee:
            continue

        assignee_name = task.assignee.get("display", "Неизвестный сотрудник")
        if assignee_name not in employees:
            employees[assignee_name] = {"completed": 0, "open": 0, "tasks": []}

        task_info = {
            "key": task.key,
            "summary": task.summary,
            "status": task.statusType.get("display", "unknown"),
            "created": task.createdAt,
            "resolved": task.resolvedAt if task.resolvedAt else None,
        }

        employees[assignee_name]["tasks"].append(task_info)

        if task.statusType.get("key") == "done":
            employees[assignee_name]["completed"] += 1
        else:
            employees[assignee_name]["open"] += 1

    # Формируем промт
    prompt = """
    Ты — HR-аналитик. Проанализируй работу сотрудников на основе данных из Яндекс.Трекера.
    Вот статистика по задачам:
    """

    for emp, data in employees.items():
        prompt += f"\n\nСотрудник: {emp}\n"
        prompt += f"- Всего задач: {len(data['tasks'])}\n"
        prompt += f"- Завершено: {data['completed']}\n"
        prompt += f"- В работе: {data['open']}\n"

        # Примеры задач
        prompt += "\nПоследние задачи:\n"
        for task in data["tasks"][:3]:  # Берем первые 3 для примера
            prompt += f"  * {task['key']}: {task['summary']} ({task['status']})\n"

    prompt += """
    \nДайте анализ:
    1. Общая продуктивность по каждому сотруднику.
    2. Проблемные места (например, долгие незавершенные задачи).
    3. Рекомендации по улучшению работы.
    """

    return prompt
