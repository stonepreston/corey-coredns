# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
from unittest.mock import call
import pytest
import logging

from charm import CharmCoreDNS
from ops.model import ActiveStatus, WaitingStatus, MaintenanceStatus
from ops.testing import Harness

from tests.unit import COREFILE_BASE, COREFILE_EXTRA, EXTRA_SERVER


def test_not_leader():
    harness = Harness(CharmCoreDNS)
    harness.begin()
    assert harness.charm.model.unit.status == WaitingStatus('Waiting for leadership')


def test_coredns_pebble_ready(harness, container):
    initial_plan = harness.get_container_pebble_plan("coredns")
    assert initial_plan.to_yaml() == "{}\n"
    expected_plan = {
        "services": {
            "coredns": {
                "override": "replace",
                "summary": "CoreDNS",
                "command": "/coredns -conf /etc/coredns/Corefile",
                "startup": "enabled",
            }
        },
    }
    harness.charm.on.coredns_pebble_ready.emit(container)
    updated_plan = harness.get_container_pebble_plan(
        "coredns").to_dict()
    assert expected_plan == updated_plan
    service = harness.model.unit.get_container(
        "coredns").get_service("coredns")
    assert service.is_running()
    assert harness.model.unit.status == WaitingStatus('Awaiting dns-provider relation')


def test_coredns_pebble_ready_already_started(harness, active_container, caplog, mocker):
    with caplog.at_level(logging.INFO):
        harness.charm.on.coredns_pebble_ready.emit(active_container)
    assert "CoreDNS already started" in caplog.text


def test_config_changed(harness, active_container, caplog, mocker):
    harness.update_config({"forward": "1.1.1.1"})
    harness.update_config({"extra_servers": EXTRA_SERVER})
    active_container.push.assert_has_calls([
        call("/etc/coredns/Corefile", COREFILE_BASE, make_dirs=True),
        call("/etc/coredns/Corefile", COREFILE_EXTRA, make_dirs=True),
    ])


def test_config_changed_not_running(harness, inactive_container, caplog, mocker):
    with caplog.at_level(logging.INFO):
        harness.update_config({"forward": "1.1.1.1"})
    assert "CoreDNS is not running" in caplog.text


def test_dns_provider_relation_changed(harness, active_container, mocker):
    harness.model.get_binding.return_value.network.ingress_address = "127.0.0.1"
    relation_id = harness.add_relation("dns-provider",
                                            "kubernetes-master")
    harness.add_relation_unit(relation_id, "kubernetes-master/0")
    harness.update_relation_data(relation_id, "kubernetes-master", {})
    assert harness.get_relation_data(relation_id, "corey-coredns/0") == {
        "domain": "cluster.local",
        "sdn-ip": "127.0.0.1",
        "port": "53",
    }
    assert harness.model.unit.status == ActiveStatus('CoreDNS started')


def test_dns_provider_relation_changed_no_ingress_address(harness, active_container, mocker):
    harness.model.get_binding.return_value.network.ingress_address = None
    relation_id = harness.add_relation("dns-provider",
                                            "kubernetes-master")
    harness.add_relation_unit(relation_id, "kubernetes-master/0")
    harness.update_relation_data(relation_id, "kubernetes-master", {})
    assert harness.model.unit.status == MaintenanceStatus('')


def test_dns_provider_relation_changed_not_running(harness, inactive_container, mocker):
    relation_id = harness.add_relation("dns-provider",
                                       "kubernetes-master")
    harness.add_relation_unit(relation_id, "kubernetes-master/0")
    harness.update_relation_data(relation_id, "kubernetes-master", {})
    assert harness.model.unit.status == WaitingStatus('CoreDNS is not running')

