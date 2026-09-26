import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional
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
- Never assume permissions or block actions yourself; always propose the relevant tool and let the application harness enforce authorization and security rules.
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


def _check_local_ollama() -> Optional[str]:
    try:
        req = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5)
        if req.getcode() == 200:
            data = json.loads(req.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            for m in models:
                if "llama" in m or "mistral" in m or "qwen" in m or "gemma" in m:
                    return m
            if models:
                text_models = [m for m in models if "embed" not in m]
                return text_models[0] if text_models else models[0]
    except Exception:
        pass
    return None


class LLMClient:
    def __init__(self, provider: str = "auto", model_name: Optional[str] = None):
        self.provider = provider
        self.model_name = model_name
        self._init_backend()

    def _init_backend(self) -> None:
        if self.provider == "auto":
            local_model = _check_local_ollama()
            if local_model:
                self.provider = "ollama"
                self.model_name = local_model
            elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
                self.provider = "gemini"
            elif os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
            else:
                self.provider = "simulated"

        if self.provider == "ollama":
            try:
                import ollama
                self.ollama_client = ollama
                if not self.model_name:
                    self.model_name = _check_local_ollama() or "llama3.2:latest"
            except Exception:
                self.provider = "simulated"

        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
            except Exception:
                self.provider = "simulated"

        elif self.provider == "openai":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception:
                self.provider = "simulated"

    def generate(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        if self.provider == "simulated":
            return self._simulated_response(messages)

        try:
            if self.provider == "ollama":
                response = self.ollama_client.chat(
                    model=self.model_name,
                    messages=messages,
                    format="json",
                    options={"temperature": 0.0},
                )
                raw_text = response.message.content or "{}"
                parsed = self._parse_json(raw_text)
                if parsed and ("action" in parsed or "thought" in parsed):
                    return parsed

            elif self.provider == "gemini":
                combined_prompt = "\n\n".join(
                    f"{msg['role'].upper()}:\n{msg['content']}" for msg in messages
                )
                response = self.model.generate_content(combined_prompt)
                parsed = self._parse_json(response.text)
                if parsed:
                    return parsed

            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                raw_text = response.choices[0].message.content or "{}"
                parsed = self._parse_json(raw_text)
                if parsed:
                    return parsed
        except Exception:
            return self._simulated_response(messages)

        return self._simulated_response(messages)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        return json.loads(cleaned.strip())

    def _simulated_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        user_query = ""
        last_tool_result: Optional[Dict[str, Any]] = None
        executed_tools: List[str] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user" and not user_query:
                user_query = content
            elif role == "user" and content.startswith("Tool Result for "):
                match = re.match(r"Tool Result for (\w+):\s*(.*)", content)
                if match:
                    t_name = match.group(1)
                    executed_tools.append(t_name)
                    try:
                        last_tool_result = json.loads(match.group(2))
                    except Exception:
                        last_tool_result = {"raw": match.group(2)}

        lower_query = user_query.lower()

        # Branch 1: Deletion requests
        if "delete" in lower_query or "remove" in lower_query:
            id_match = re.search(r"\b(\d+)\b", lower_query)
            target_id = int(id_match.group(1)) if id_match else 1

            if "delete_product" not in executed_tools:
                return {
                    "thought": f"The user wants to delete product ID {target_id}. Proposing 'delete_product' action.",
                    "action": "call_tool",
                    "tool_name": "delete_product",
                    "arguments": {"product_id": target_id},
                }

            if last_tool_result and last_tool_result.get("status") == "error":
                err_msg = last_tool_result.get("message", "Permission denied or product not found.")
                return {
                    "thought": f"Action was rejected by application: {err_msg}",
                    "action": "final_answer",
                    "answer": f"Unable to delete product {target_id}. {err_msg}",
                }

            success_msg = last_tool_result.get("message", f"Product {target_id} successfully deleted.") if last_tool_result else f"Product {target_id} deleted."
            return {
                "thought": "Observed successful deletion from catalog.",
                "action": "final_answer",
                "answer": success_msg,
            }

        # Branch 2: Purchase requests
        if "buy" in lower_query or "purchase" in lower_query or "order" in lower_query:
            qty_match = re.search(r"(\d+)\s*(?:unit|piece|item|x)?", lower_query)
            qty = int(qty_match.group(1)) if (qty_match and int(qty_match.group(1)) < 100) else 1
            id_match = re.search(r"(?:product|id|item)\s*(?:#|no\.?)?\s*(\d+)", lower_query)
            target_id = int(id_match.group(1)) if id_match else 3

            if "buy_product" not in executed_tools:
                return {
                    "thought": f"Proposing to purchase {qty} unit(s) of product ID {target_id}.",
                    "action": "call_tool",
                    "tool_name": "buy_product",
                    "arguments": {"product_id": target_id, "quantity": qty},
                }

            if last_tool_result and last_tool_result.get("status") == "error":
                return {
                    "thought": "Purchase failed due to error or stock limitation.",
                    "action": "final_answer",
                    "answer": f"Purchase could not be completed: {last_tool_result.get('message')}",
                }

            total = last_tool_result.get("total_cost", "N/A") if last_tool_result else "N/A"
            rem = last_tool_result.get("remaining_stock", "N/A") if last_tool_result else "N/A"
            return {
                "thought": "Purchase completed successfully. Formatting receipt for user.",
                "action": "final_answer",
                "answer": f"Order successful! Purchased {qty}x product ID {target_id} for a total of ${total}. Remaining stock: {rem}.",
            }

        # Branch 3: Search and stock queries
        if "search_products" not in executed_tools:
            kw = "laptop"
            if "headphone" in lower_query or "audio" in lower_query:
                kw = "headphones"
            elif "keyboard" in lower_query:
                kw = "keyboard"
            elif "monitor" in lower_query:
                kw = "monitor"
            return {
                "thought": f"The user is searching for items. Searching catalog for '{kw}'.",
                "action": "call_tool",
                "tool_name": "search_products",
                "arguments": {"query": kw},
            }

        if "check_stock" not in executed_tools:
            candidate_id = 1
            if last_tool_result and last_tool_result.get("results"):
                candidate_id = last_tool_result["results"][0]["id"]
            return {
                "thought": f"Catalog search returned results. Now checking inventory stock for candidate ID {candidate_id}.",
                "action": "call_tool",
                "tool_name": "check_stock",
                "arguments": {"product_id": candidate_id},
            }

        stock_info = last_tool_result or {}
        prod_name = stock_info.get("name", "Product")
        units = stock_info.get("stock", 0)
        return {
            "thought": "We have identified the product and verified current stock availability.",
            "action": "final_answer",
            "answer": f"I found the '{prod_name}'. It is currently in stock with {units} units available for purchase.",
        }


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
