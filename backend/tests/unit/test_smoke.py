"""Smoke test to verify pytest infrastructure works."""
import asyncio


def test_sync_smoke():
    assert 1 + 1 == 2


async def test_async_smoke():
    await asyncio.sleep(0.01)
    assert True
