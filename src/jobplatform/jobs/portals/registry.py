from jobplatform.jobs.portals.base import BasePortalAdapter


class PortalRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BasePortalAdapter] = {}

    def register(self, adapter: BasePortalAdapter) -> None:
        self._adapters[adapter.portal_id] = adapter

    def get(self, portal_id: str) -> BasePortalAdapter:
        if portal_id not in self._adapters:
            raise KeyError(f"Portal '{portal_id}' not registered")
        return self._adapters[portal_id]

    def all(self) -> list[BasePortalAdapter]:
        return list(self._adapters.values())


portal_registry = PortalRegistry()
