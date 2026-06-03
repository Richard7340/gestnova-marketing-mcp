"""Connector registry."""
from __future__ import annotations
from ._base import Connector, HttpClient

_REGISTRY: dict[str, type[Connector]] = {}


def register(source: str):
    def deco(cls: type[Connector]) -> type[Connector]:
        cls.source = source
        _REGISTRY[source] = cls
        return cls
    return deco


def get_connector(source: str, http: HttpClient, *, now_iso: str) -> Connector:
    if source not in _REGISTRY:
        raise ValueError(f"Unknown source: {source}")
    return _REGISTRY[source](http, now_iso=now_iso)


def supported_sources() -> list[str]:
    return sorted(_REGISTRY)
