from __future__ import annotations

from ves.modules.base import EngineeringModule


class UnknownModuleError(KeyError):
    pass


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, EngineeringModule] = {}

    def register(self, module: EngineeringModule) -> None:
        descriptor = module.describe()
        if descriptor.id in self._modules:
            raise ValueError(f"Duplicate module id: {descriptor.id}")
        self._modules[descriptor.id] = module

    def get(self, module_id: str) -> EngineeringModule:
        try:
            return self._modules[module_id]
        except KeyError as exc:
            raise UnknownModuleError(module_id) from exc

    def descriptors(self):
        return [module.describe() for module in self._modules.values()]

