import json
import re
from typing import Any, Dict, List, Optional
import ollama
from harness import ExecutionHarness
from schemas import TOOL_SCHEMAS

SYSTEM_PROMPT = """You are an intelligent shopping assistant agent.
You have access to a product catalog and can use tools to answer user questions or perform actions.

Available tools:
{tools_doc}

Protocol:
At each step, carefully evaluate the user request and previous tool observations.
Respond with a single valid JSON object strictly matching one of these two structures:

1. To call a tool:
{{
  "thought": "Your reasoning about what information is needed next",
  "action": "call_tool",
  "tool_name": "<exact_tool_name>",
  "arguments": {{ ... }}
}}

2. When you have sufficient information or cannot proceed:
{{
  "thought": "Your reasoning for completing the task",
  "action": "final_answer",
  "answer": "Your complete final response to the user"
}}

Rules:
- Never assume permissions or block actions yourself; always propose the relevant tool directly and let the application harness enforce authorization and security rules.
- Strictly call ONLY the tools explicitly listed in Available Tools. Never invent tools such as check_permissions or get_admin_role.
- If asked to delete a product, propose 'delete_product' directly.
- Output valid JSON only, without markdown fences or additional commentary.
- Only call one tool per turn.
"""


def _build_tools_description() -> str:
    lines = []
    for name, info in TOOL_SCHEMAS.items():
        params = info["parameters"].get("properties", {})
        param_desc = ", ".join(f"{k}: {v.get('type')}" for k, v in params.items())
        lines.append(f"- {name}({param_desc}): {info['description']}")
    return "\n".join(lines)


class LLMClient:
    def __init__(self, model_name: str = "llama3.2:latest"):
        self.model_name = model_name

    def generate(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        response = ollama.chat(
            model=self.model_name,
            messages=messages,
            format="json",
            options={"temperature": 0.0},
        )
        raw_text = response.message.content or "{}"
        return self._parse_json(raw_text)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        return json.loads(cleaned.strip())


class Agent:
    def __init__(
        self,
        harness: ExecutionHarness,
        model_name: str = "llama3.2:latest",
        max_iterations: int = 5,
        verbose: bool = True,
    ):
        self.harness = harness
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.llm = LLMClient(model_name=model_name)

    def run(self, user_request: str) -> Dict[str, Any]:
        tools_doc = _build_tools_description()
        system_content = SYSTEM_PROMPT.format(tools_doc=tools_doc)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_request},
        ]

        trace: List[Dict[str, Any]] = []

        if self.verbose:
            print("=" * 65)
            print(f"User Request : {user_request}")
            print(f"Active Role  : {self.harness.role.upper()}")
            print(f"LLM Model    : {self.llm.model_name}")
            print("=" * 65)

        for iteration in range(1, self.max_iterations + 1):
            if self.verbose:
                print(f"\n[Step {iteration}] Agent Reasoning...")

            step_decision = self.llm.generate(messages)
            thought = step_decision.get("thought", "")
            action = step_decision.get("action", "")

            if self.verbose:
                if thought:
                    print(f"  Thought : {thought}")

            if action == "final_answer":
                answer = step_decision.get("answer", "")
                if self.verbose:
                    print(f"  Decision: Final Answer")
                    print(f"  Answer  : {answer}\n")
                trace.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": "final_answer",
                    "answer": answer,
                })
                return {
                    "status": "success",
                    "final_answer": answer,
                    "iterations": iteration,
                    "trace": trace,
                }

            elif action == "call_tool":
                tool_name = step_decision.get("tool_name", "")
                arguments = step_decision.get("arguments", {})

                if self.verbose:
                    print(f"  Decision: Propose Tool -> {tool_name}({arguments})")

                execution_result = self.harness.execute_tool(tool_name, arguments)

                if self.verbose:
                    status_flag = execution_result.get("status")
                    print(f"  Harness : Checked -> Status: {status_flag}")
                    print(f"  Result  : {execution_result}")

                step_record = {
                    "iteration": iteration,
                    "thought": thought,
                    "action": "call_tool",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": execution_result,
                }
                trace.append(step_record)

                messages.append({
                    "role": "assistant",
                    "content": json.dumps(step_decision),
                })
                messages.append({
                    "role": "user",
                    "content": f"Tool Result for {tool_name}: {json.dumps(execution_result)}",
                })
            else:
                fallback_msg = f"Unknown action: {action}."
                return {
                    "status": "error",
                    "final_answer": fallback_msg,
                    "iterations": iteration,
                    "trace": trace,
                }

        limit_msg = f"Loop stopped: Reached maximum limit of {self.max_iterations} iterations."
        if self.verbose:
            print(f"\n[Limit] {limit_msg}")

        return {
            "status": "limit_reached",
            "final_answer": limit_msg,
            "iterations": self.max_iterations,
            "trace": trace,
        }
