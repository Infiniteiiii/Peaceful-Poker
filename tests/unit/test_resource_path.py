"""Tests for source and frozen resource discovery."""

import sys
from pathlib import Path

import pytest

from poker_trainer.resource_path import (
    REQUIRED_RESOURCE_NAMES,
    resource_path,
    validate_required_resources,
)


def test_all_required_source_resources_exist() -> None:
    resources = validate_required_resources()

    assert tuple(resources) == REQUIRED_RESOURCE_NAMES
    assert all(path.is_file() for path in resources.values())


def test_frozen_resource_path_uses_meipass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert resource_path("light.qss") == tmp_path / "poker_trainer" / "resources" / "light.qss"


def test_missing_required_resource_fails_clearly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    with pytest.raises(RuntimeError, match="Required application resources are missing"):
        validate_required_resources()
