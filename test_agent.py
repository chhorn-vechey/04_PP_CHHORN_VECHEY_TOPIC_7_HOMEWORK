import pytest
from agent import Agent
from harness import ExecutionHarness
from schemas import CheckStockInput, BuyProductInput, SearchProductsInput
from tools import reset_catalog, search_products, check_stock, buy_product, delete_product


@pytest.fixture(autouse=True)
def setup_catalog():
    reset_catalog()


def test_schema_validations():
    valid_search = SearchProductsInput(query="laptop")
    assert valid_search.query == "laptop"

    with pytest.raises(Exception):
        SearchProductsInput(query="   ")

    valid_stock = CheckStockInput(product_id=2)
    assert valid_stock.product_id == 2

    with pytest.raises(Exception):
        CheckStockInput(product_id=-1)

    valid_buy = BuyProductInput(product_id=3, quantity=2)
    assert valid_buy.quantity == 2

    with pytest.raises(Exception):
        BuyProductInput(product_id=3, quantity=0)

    with pytest.raises(Exception):
        BuyProductInput(product_id=3, quantity=1000)


def test_tools_execution():
    res = search_products("laptop")
    assert res["status"] == "success"
    assert res["count"] >= 1

    stock_res = check_stock(1)
    assert stock_res["status"] == "success"
    assert stock_res["stock"] > 0

    buy_res = buy_product(product_id=1, quantity=1)
    assert buy_res["status"] == "success"
    assert buy_res["remaining_stock"] == 4

    del_res = delete_product(product_id=1)
    assert del_res["status"] == "success"


def test_harness_permission_enforcement():
    customer_harness = ExecutionHarness(role="customer")
    admin_harness = ExecutionHarness(role="admin")

    # Customer allowed tools
    assert customer_harness.execute_tool("search_products", {"query": "laptop"})["status"] == "success"
    assert customer_harness.execute_tool("check_stock", {"product_id": 1})["status"] == "success"

    # Customer disallowed tool
    denied = customer_harness.execute_tool("delete_product", {"product_id": 1})
    assert denied["status"] == "error"
    assert denied["error_code"] == "PERMISSION_DENIED"

    # Admin allowed tool
    allowed = admin_harness.execute_tool("delete_product", {"product_id": 1})
    assert allowed["status"] == "success"


def test_harness_validation_and_safety():
    harness = ExecutionHarness(role="customer")

    # Validation error
    val_err = harness.execute_tool("check_stock", {"product_id": -5})
    assert val_err["status"] == "error"
    assert val_err["error_code"] == "VALIDATION_ERROR"

    # Tool not found
    not_found = harness.execute_tool("unknown_tool", {})
    assert not_found["status"] == "error"
    assert not_found["error_code"] == "TOOL_NOT_FOUND"


def test_harness_tool_call_limit():
    strict_harness = ExecutionHarness(role="customer", max_tool_calls=2)
    res1 = strict_harness.execute_tool("search_products", {"query": "laptop"})
    assert res1["status"] == "success"

    res2 = strict_harness.execute_tool("check_stock", {"product_id": 1})
    assert res2["status"] == "success"

    res3 = strict_harness.execute_tool("check_stock", {"product_id": 1})
    assert res3["status"] == "error"
    assert res3["error_code"] == "RATE_LIMIT_EXCEEDED"


def test_agent_multistep_loop():
    harness = ExecutionHarness(role="customer", max_tool_calls=5)
    agent = Agent(harness=harness, provider="simulated", max_iterations=5, verbose=False)
    result = agent.run("Find a laptop that is currently in stock.")

    assert result["status"] == "success"
    assert "ThinkPad Carbon Ultrabook" in result["final_answer"]
    assert len(result["trace"]) >= 2
