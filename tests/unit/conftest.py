import pytest
from charm import CharmCoreDNS
from ops.testing import Harness
from ops.pebble import ServiceStatus

@pytest.fixture()
def harness(mocker):
    harness = Harness(CharmCoreDNS)
    harness.set_leader(True)
    harness.begin()
    harness.model.get_binding = mocker.MagicMock()
    return harness


@pytest.fixture()
def container(harness, mocker):
    container = harness.model.unit.get_container("coredns")
    container.push = mocker.MagicMock()
    container.stop = mocker.MagicMock()
    container.start = mocker.MagicMock()
    return container


@pytest.fixture()
def active_container(mocker, container):
    mocked_service = mocker.MagicMock()
    mocked_service.current = ServiceStatus.ACTIVE
    container.get_service = mocker.MagicMock(return_value=mocked_service)
    return container


@pytest.fixture()
def inactive_container(mocker, container):
    mocked_service = mocker.MagicMock()
    mocked_service.current = ServiceStatus.INACTIVE
    container.get_service = mocker.MagicMock(return_value=mocked_service)
    return container
