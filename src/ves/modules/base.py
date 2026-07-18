from __future__ import annotations

from abc import ABC, abstractmethod

from ves.core.models import (
    CaseDescriptor,
    EvidenceBundle,
    ModuleDescriptor,
    ValidationCheck,
)


class EngineeringModule(ABC):
    """Small, read-only contract implemented by every engineering module."""

    @abstractmethod
    def describe(self) -> ModuleDescriptor:
        raise NotImplementedError

    @abstractmethod
    def list_cases(self) -> list[CaseDescriptor]:
        raise NotImplementedError

    @abstractmethod
    def build_evidence(self, case_id: str) -> EvidenceBundle:
        raise NotImplementedError

    @abstractmethod
    def validate(self, evidence: EvidenceBundle) -> list[ValidationCheck]:
        raise NotImplementedError

