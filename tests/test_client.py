"""Unit tests for the Grocy API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from grocy_mcp import client


@pytest.fixture(autouse=True)
def configure_client() -> None:
    client.configure("https://grocy.example", api_key="secret", timeout=5)


@respx.mock
def test_system_info_sends_grocy_api_key() -> None:
    route = respx.get("https://grocy.example/api/system/info").mock(
        return_value=httpx.Response(200, json={"grocy_version": {"Version": "4.6.0"}})
    )

    data = client.system_info()

    assert data["grocy_version"]["Version"] == "4.6.0"
    assert route.calls[0].request.headers["GROCY-API-KEY"] == "secret"


@respx.mock
def test_list_objects_normalises_list() -> None:
    respx.get("https://grocy.example/api/objects/products").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Flour"}])
    )

    assert client.list_objects("products") == [{"id": 1, "name": "Flour"}]


@respx.mock
def test_list_objects_normalises_dict_keyed_by_id() -> None:
    respx.get("https://grocy.example/api/objects/products").mock(
        return_value=httpx.Response(200, json={"1": {"id": 1, "name": "Flour"}})
    )

    assert client.list_objects("products") == [{"id": 1, "name": "Flour"}]


@respx.mock
def test_update_object_refetches_when_empty_response() -> None:
    respx.put("https://grocy.example/api/objects/products/1").mock(return_value=httpx.Response(204))
    respx.get("https://grocy.example/api/objects/products/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Updated"})
    )

    assert client.update_object("products", 1, {"name": "Updated"}) == {"id": 1, "name": "Updated"}


@respx.mock
def test_stock_actions_post_expected_payloads() -> None:
    add_route = respx.post("https://grocy.example/api/stock/products/7/add").mock(
        return_value=httpx.Response(200, json={"id": "tx-add"})
    )
    consume_route = respx.post("https://grocy.example/api/stock/products/7/consume").mock(
        return_value=httpx.Response(200, json={"id": "tx-consume"})
    )
    inventory_route = respx.post("https://grocy.example/api/stock/products/7/inventory").mock(
        return_value=httpx.Response(200, json={"id": "tx-inventory"})
    )

    assert client.add_stock(7, {"amount": 2})["id"] == "tx-add"
    assert client.consume_stock(7, {"amount": 1, "spoiled": False})["id"] == "tx-consume"
    assert client.inventory_product(7, {"new_amount": 3})["id"] == "tx-inventory"

    assert add_route.calls[0].request.content == b'{"amount":2}'
    assert consume_route.calls[0].request.content == b'{"amount":1,"spoiled":false}'
    assert inventory_route.calls[0].request.content == b'{"new_amount":3}'


@respx.mock
def test_http_errors_are_readable() -> None:
    respx.get("https://grocy.example/api/system/info").mock(return_value=httpx.Response(401, text="Unauthorized"))

    with pytest.raises(client.GrocyError, match="HTTP 401"):
        client.system_info()


@respx.mock
def test_set_userfields_returns_response_body_when_present() -> None:
    route = respx.put("https://grocy.example/api/userfields/recipes/3").mock(
        return_value=httpx.Response(200, json={"Tag": "Diet,Papa Spuds"})
    )

    assert client.set_userfields("recipes", 3, {"Tag": "Diet,Papa Spuds"}) == {"Tag": "Diet,Papa Spuds"}
    assert route.calls[0].request.content == b'{"Tag":"Diet,Papa Spuds"}'


@respx.mock
def test_set_userfields_refetches_userfields_when_empty_response() -> None:
    respx.put("https://grocy.example/api/userfields/recipes/3").mock(return_value=httpx.Response(204))
    respx.get("https://grocy.example/api/objects/recipes/3").mock(
        return_value=httpx.Response(200, json={"id": 3, "userfields": {"Tag": "Diet"}})
    )

    assert client.set_userfields("recipes", 3, {"Tag": "Diet"}) == {"Tag": "Diet"}


@respx.mock
def test_list_chores_returns_list() -> None:
    respx.get("https://grocy.example/api/chores").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Take out Trash", "next_estimated_execution_time": "2026-08-02 23:59:59"}])
    )

    chores = client.list_chores()

    assert chores[0]["name"] == "Take out Trash"
    assert chores[0]["next_estimated_execution_time"] == "2026-08-02 23:59:59"


@respx.mock
def test_execute_chore_posts_tracked_time_for_backdating() -> None:
    route = respx.post("https://grocy.example/api/chores/1/execute").mock(
        return_value=httpx.Response(200, json={"id": "tx-chore"})
    )

    result = client.execute_chore(1, {"tracked_time": "2026-07-29 00:00:00", "skipped": False})

    assert result["id"] == "tx-chore"
    assert route.calls[0].request.content == b'{"tracked_time":"2026-07-29 00:00:00","skipped":false}'


@respx.mock
def test_list_tasks_returns_list() -> None:
    respx.get("https://grocy.example/api/tasks").mock(return_value=httpx.Response(200, json=[{"id": 1, "name": "Fix fence"}]))

    assert client.list_tasks() == [{"id": 1, "name": "Fix fence"}]
