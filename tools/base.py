from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from pydantic import BaseModel


# =========================================================
# TOOL RESPONSE
# =========================================================

class ToolResponse(BaseModel):
    status: str  # success | error | need_clarification | need_confirmation
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    undo_data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# =========================================================
# BASE TOOL
# =========================================================

class BaseTool(ABC):

    name = "base"
    description = ""

    required_args = []
    optional_args = []

    requires_confirmation = False
    risk_level = "low"
    category = "general"

    # =========================================================
    # VALIDATION
    # =========================================================

    def validate(self, kwargs):

        for arg in self.required_args:
            if arg not in kwargs or kwargs[arg] is None:
                return self.error(f"Missing required argument: {arg}")

        return None

    # =========================================================
    # RESPONSE HELPERS 🔥
    # =========================================================

    def success(self, data=None, message=None, undo_data=None, meta=None):
        return ToolResponse(
            status="success",
            data=data,
            message=message,
            undo_data=undo_data,
            meta=meta
        ).model_dump()

    def error(self, message):
        return ToolResponse(
            status="error",
            error=message
        ).model_dump()

    def need_confirmation(self, data=None, message=None, meta=None):
        return ToolResponse(
            status="need_confirmation",
            data=data,
            message=message,
            meta=meta
        ).model_dump()

    def need_clarification(self, options, message=None):
        return ToolResponse(
            status="need_clarification",
            data={"options": options},
            message=message
        ).model_dump()

    # =========================================================
    # ABSTRACT
    # =========================================================

    @abstractmethod
    def run(self, **kwargs):
        pass