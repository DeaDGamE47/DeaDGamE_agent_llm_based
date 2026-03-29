from abc import ABC, abstractmethod


class BaseTool(ABC):

    name = "base"
    description = ""

    required_args = []
    optional_args = []

    requires_confirmation = False
    risk_level = "low"
    category = "general"

    def validate(self, kwargs):

        for arg in self.required_args:
            if arg not in kwargs or kwargs[arg] is None:
                return {
                    "status": "error",
                    "error": f"Missing required argument: {arg}"
                }

        return None

    @abstractmethod
    def run(self, **kwargs):
        pass