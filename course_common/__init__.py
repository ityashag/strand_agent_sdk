"""Shared helpers for the Strands course: settings, model factory, offline model, logging."""

from course_common.config import CourseSettings, get_settings
from course_common.fake_model import ModelCall, ScriptedModel, ToolCall
from course_common.logging_setup import setup_logging
from course_common.models import build_model
from course_common.show import show_result

__all__ = [
    "CourseSettings",
    "ModelCall",
    "ScriptedModel",
    "ToolCall",
    "build_model",
    "get_settings",
    "setup_logging",
    "show_result",
]
