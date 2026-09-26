import argparse
import sys
from dotenv import load_dotenv

from agent import Agent
from harness import ExecutionHarness
from tools import reset_catalog

load_dotenv()


def run_demo(provider: str = "auto") -> None:
    print("\n" + "=" * 70)
    print("      Topic 07 - Autonomous Agent & Tool Integration Demo")
    print("=" * 70)

    # Testcase 1: Multi-step tool use (Search -> Check Stock -> Final Answer)
    print("\n>>> Scenario 1: Multi-Step Agent Loop (Customer finds in-stock laptop)")
    reset_catalog()
    harness_1 = ExecutionHarness(role="customer", max_tool_calls=5)
    agent_1 = Agent(harness=harness_1, provider=provider, max_iterations=5, verbose=True)
    agent_1.run("Find a laptop that is currently in stock.")

    # Testcase 2: Permission Enforcement (Customer tries restricted admin action)
    print("\n>>> Scenario 2: Permission Control Check (Customer attempts delete_product)")
    harness_2 = ExecutionHarness(role="customer", max_tool_calls=5)
    agent_2 = Agent(harness=harness_2, provider=provider, max_iterations=5, verbose=True)
    agent_2.run("Delete product 1 from the catalog.")

    # Testcase 3: Authorized Admin Action
    print("\n>>> Scenario 3: Authorized Execution (Admin deletes product 1)")
    harness_3 = ExecutionHarness(role="admin", max_tool_calls=5)
    agent_3 = Agent(harness=harness_3, provider=provider, max_iterations=5, verbose=True)
    agent_3.run("Delete product 1 from the catalog.")

    # Testcase 4: Safety & Validation (Invalid inputs handled by schema/harness)
    print("\n>>> Scenario 4: Safety Validation (Negative ID or invalid quantity)")
    harness_4 = ExecutionHarness(role="customer", max_tool_calls=5)
    print("Executing tool with invalid argument product_id=-99...")
    val_result = harness_4.execute_tool("check_stock", {"product_id": -99})
    print(f"Validation Result: {val_result}")

    # Testcase 5: Loop limit / max tool call boundary
    print("\n>>> Scenario 5: Maximum Tool-Call Limit Boundary")
    limited_harness = ExecutionHarness(role="customer", max_tool_calls=1)
    res_1 = limited_harness.execute_tool("search_products", {"query": "laptop"})
    print(f"Call 1 status: {res_1.get('status')}")
    res_2 = limited_harness.execute_tool("check_stock", {"product_id": 1})
    print(f"Call 2 (exceeding limit) status: {res_2}")

    print("\n" + "=" * 70)
    print("All demonstration scenarios completed successfully.")
    print("=" * 70 + "\n")


def interactive_mode(role: str = "customer", provider: str = "auto") -> None:
    reset_catalog()
    harness = ExecutionHarness(role=role, max_tool_calls=5)
    agent = Agent(harness=harness, provider=provider, max_iterations=5, verbose=True)

    print(f"\n[Interactive Session Started | Role: {role.upper()} | Provider: {agent.llm.provider}]")
    print("Type your request below (or 'exit' / 'quit' to end):\n")

    while True:
        try:
            user_input = input("User > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting session.")
                break
            agent.run(user_input)
            print("-" * 60)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Shopping Agent with Security Harness")
    parser.add_argument("--role", choices=["customer", "admin"], default="customer", help="User role for permission checks")
    parser.add_argument("--prompt", type=str, default=None, help="Direct prompt to process")
    parser.add_argument("--provider", choices=["auto", "gemini", "openai", "simulated"], default="auto", help="LLM backend provider")
    parser.add_argument("--demo", action="store_true", help="Run full demonstration testcases")
    args = parser.parse_args()

    if args.demo:
        run_demo(provider=args.provider)
    elif args.prompt:
        harness = ExecutionHarness(role=args.role, max_tool_calls=5)
        agent = Agent(harness=harness, provider=args.provider, max_iterations=5, verbose=True)
        agent.run(args.prompt)
    else:
        # If no arguments provided, ask or show menu
        print("1. Run Full Demonstration Scenarios")
        print("2. Interactive Customer Mode")
        print("3. Interactive Admin Mode")
        choice = input("Select an option (1/2/3) [Default 1]: ").strip()
        if choice == "2":
            interactive_mode(role="customer", provider=args.provider)
        elif choice == "3":
            interactive_mode(role="admin", provider=args.provider)
        else:
            run_demo(provider=args.provider)


if __name__ == "__main__":
    main()
