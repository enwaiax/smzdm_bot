"""Generic task execution primitives."""

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class TaskPriority(Enum):
    """Execution priority for account tasks."""

    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """A named operation and its execution policy."""

    task_name: str
    operation: Callable[[], Any] = field(repr=False)
    priority: TaskPriority = TaskPriority.NORMAL
    continue_on_failure: bool = True
    delay_seconds_range: tuple[float, float] = (1, 5)


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    """The technical outcome of one task operation."""

    task_name: str
    completed_without_error: bool
    return_value: Any = None
    error_message: str | None = None


def execute_task_definitions(
    task_definitions: Sequence[TaskDefinition],
) -> list[TaskExecutionResult]:
    """Execute tasks by priority while applying their failure policies."""
    ordered_definitions = sorted(
        task_definitions,
        key=lambda task_definition: task_definition.priority.value,
    )
    execution_results: list[TaskExecutionResult] = []

    for task_definition in ordered_definitions:
        logger.info(f"执行: {task_definition.task_name}")
        wait_for_random_delay(task_definition.delay_seconds_range)

        try:
            return_value = task_definition.operation()
        except Exception as error:
            error_message = str(error)
            execution_results.append(
                TaskExecutionResult(
                    task_name=task_definition.task_name,
                    completed_without_error=False,
                    error_message=error_message,
                )
            )

            if task_definition.continue_on_failure:
                logger.warning(f"{task_definition.task_name} 失败: {error_message}")
                continue

            logger.error(f"{task_definition.task_name} 失败: {error_message}")
            break

        execution_results.append(
            TaskExecutionResult(
                task_name=task_definition.task_name,
                completed_without_error=True,
                return_value=return_value,
            )
        )
        logger.success(f"{task_definition.task_name} 完成")

    return execution_results


def wait_for_random_delay(
    delay_seconds_range: tuple[float, float],
) -> float:
    """Wait for a uniformly random delay and return the chosen duration."""
    minimum_seconds, maximum_seconds = delay_seconds_range
    if minimum_seconds < 0 or maximum_seconds < minimum_seconds:
        raise ValueError("Invalid delay range")
    if maximum_seconds == 0:
        return 0

    delay_seconds = random.uniform(minimum_seconds, maximum_seconds)
    logger.debug(f"随机等待 {delay_seconds:.1f} 秒")
    time.sleep(delay_seconds)
    return delay_seconds


__all__ = [
    "TaskDefinition",
    "TaskExecutionResult",
    "TaskPriority",
    "execute_task_definitions",
    "wait_for_random_delay",
]
