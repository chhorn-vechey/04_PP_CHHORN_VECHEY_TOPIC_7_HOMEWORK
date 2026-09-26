from typing import Any, Dict, Set
from pydantic import ValidationError
from schemas import TOOL_SCHEMAS
from tools import AVAILABLE_TOOLS

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "customer": {"search_products", "check_stock", "buy_product"},
    "admin": {"search_products", "check_stock", "buy_product", "delete_product"},
}


class ExecutionHarness:
    def __init__(self, role: str = "customer", max_tool_calls: int = 5):
        self.role = role.lower()
        self.max_tool_calls = max_tool_calls
        self.tool_call_count = 0

    def is_permission_granted(self, tool_name: str) -> bool:
        allowed = ROLE_PERMISSIONS.get(self.role, set())
        return tool_name in allowed

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if self.tool_call_count >= self.max_tool_calls:
            return {
                "status": "error",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": f"Execution halted: reached maximum limit of {self.max_tool_calls} tool calls.",
            }

        self.tool_call_count += 1

        if tool_name not in AVAILABLE_TOOLS or tool_name not in TOOL_SCHEMAS:
            return {
                "status": "error",
                "error_code": "TOOL_NOT_FOUND",
                "message": f"Tool '{tool_name}' is not in the approved tool registry.",
            }

        if not self.is_permission_granted(tool_name):
            return {
                "status": "error",
                "error_code": "PERMISSION_DENIED",
                "message": f"Permission denied: role '{self.role}' is not allowed to call '{tool_name}'.",
            }

        schema_entry = TOOL_SCHEMAS[tool_name]
        schema_model = schema_entry["model"]

        try:
            validated_input = schema_model(**arguments)
        except ValidationError as val_err:
            error_details = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in val_err.errors()
            ]
            return {
                "status": "error",
                "error_code": "VALIDATION_ERROR",
                "message": f"Input validation failed for '{tool_name}': {'; '.join(error_details)}",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "INVALID_ARGUMENTS",
                "message": f"Invalid arguments passed to '{tool_name}': {str(exc)}",
            }

        tool_func = AVAILABLE_TOOLS[tool_name]
        try:
            result = tool_func(**validated_input.model_dump())
            return result
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "INTERNAL_TOOL_ERROR",
                "message": f"Execution error in tool '{tool_name}': {str(exc)}",
            }
