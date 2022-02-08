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


@pytest.fixture()
def corefile_base():
    return """.:53 {
    errors
    health {
      lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      fallthrough in-addr.arpa ip6.arpa
      pods insecure
    }
    prometheus :9153
    forward . 1.1.1.1
    cache 30
    loop
    reload
    loadbalance
}

"""


@pytest.fixture()
def extra_server():
    return """. {{
    log
}}
"""


@pytest.fixture()
def corefile_extra(corefile_base, extra_server):
    return f"""{corefile_base[0:-2]}
{extra_server}
"""