import pytest

from chaima.models.storage import StorageKind
from chaima.services.storage_locations import validate_kind_hierarchy, InvalidHierarchy


def test_building_has_no_parent():
    validate_kind_hierarchy(child=StorageKind.BUILDING, parent=None)


def test_building_cannot_have_parent():
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.BUILDING, parent=StorageKind.ROOM)


def test_room_requires_building_parent():
    validate_kind_hierarchy(child=StorageKind.ROOM, parent=StorageKind.BUILDING)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.ROOM, parent=None)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.ROOM, parent=StorageKind.CABINET)


def test_cabinet_requires_room_parent():
    validate_kind_hierarchy(child=StorageKind.CABINET, parent=StorageKind.ROOM)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.CABINET, parent=StorageKind.BUILDING)


def test_shelf_requires_cabinet_parent():
    validate_kind_hierarchy(child=StorageKind.SHELF, parent=StorageKind.CABINET)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.SHELF, parent=StorageKind.ROOM)
