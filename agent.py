import json
import os
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
    def __init__(self, provider: str = "auto", model_name: Optional[str] = None):
        self.provider = provider
        self.model_name = model_name or "llama3.2:latest"
        self._init_backend()

    def _init_backend(self) -> None:
        if self.provider == "auto":
            if os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
            elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
                self.provider = "gemini"
            else:
                self.provider = "ollama"

        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "gemini":
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={"response_mime_type": "application/json"}
            )

    def generate(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        if self.provider == "ollama":
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                format="json",
                options={"temperature": 0.0},
            )
            raw_text = response.message.content or "{}"
            return self._parse_json(raw_text)

        elif self.provider == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw_text = response.choices[0].message.content or "{}"
            return self._parse_json(raw_text)

        elif self.provider == "gemini":
            combined_prompt = "\n\n".join(
                f"{msg['role'].upper()}:\n{msg['content']}" for msg in messages
            )
            response = self.gemini_model.generate_content(combined_prompt)
            return self._parse_json(response.text)

        raise ValueError(f"Unsupported LLM provider: {self.provider}")

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
        provider: str = "auto",
        model_name: Optional[str] = None,
        max_iterations: int = 5,
        verbose: bool = True,
    ):
        self.harness = harness
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.llm = LLMClient(provider=provider, model_name=model_name)

    def run(self, user_request: str) -> Dict[str, Any]:
        tools_doc = _build_tools_description()
        system_content = SYSTEM_PROMPT.format(tools_doc=tools_doc)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_request},
        ]

        trace: List[Dict[str, Any]] = []
        provider_display = f"{self.llm.provider.upper()}" + (f" ({self.llm.model_name})" if getattr(self.llm, "model_name", None) else "")

        if self.verbose:
            print("=" * 65)
            print(f"User Request : {user_request}")
            print(f"Active Role  : {self.harness.role.upper()}")
            print(f"LLM Provider : {provider_display}")
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
