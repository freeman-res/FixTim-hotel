from .providers.base import BaseProvider
from .csv import CSVProvider
from ..demo import DemoProvider
from ..http import HTTPProvider
from ..json import JSONProvider
from ..sql import SQLProvider
def make_provider(kind: str, **kwargs) -> BaseProvider:
    """ Создает провайдер строковому идентификатору."""
    mapping = {
        "demo": DemoProvider,
        "json": JSONProvider,
        "csv": CSVProvider,
        "sql": SQLProvider,
        "http": HTTPProvider, }
    if kind not in mapping:
        raise ValueError(
            f"Unknown provider: {kind!r}. Available: {list(mapping)}"  )
    return mapping[kind](**kwargs)