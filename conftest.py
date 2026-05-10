import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "test_drill" in item.module.__name__:
            item.add_marker(pytest.mark.xdist_group(name="drill"))
