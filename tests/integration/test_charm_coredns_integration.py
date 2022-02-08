import logging
import pytest
from pathlib import Path
from juju.tag import untag

log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test, helpers):
    spark_operator_charm = await ops_test.build_charm(".")

    coredns_resources = {"coredns-image": helpers.oci_image("./metadata.yaml", "coredns-image")}
    await ops_test.model.deploy(
        spark_operator_charm, resources=coredns_resources
    )
    await ops_test.model.wait_for_idle(
        status="waiting", raise_on_blocked=True, timeout=300
    )


async def test_relation(ops_test, client_model):
    base_path = Path(__file__).parent
    relation_charm_path = base_path / "data/dns-provider-test"
    relation_charm = await ops_test.build_charm(relation_charm_path)
    relation_charm_resources = {"httpbin-image": "kennethreitz/httpbin"}
    relation_app = await client_model.deploy(relation_charm, resources=relation_charm_resources)

    await client_model.block_until(lambda: len(relation_app.units) == 1, timeout=10 * 60)
    await client_model.wait_for_idle(
        status="active", raise_on_blocked=True, timeout=300
    )

    offer, saas, relation = None, None, None
    try:
        log.info("Creating CMR offer")
        offer = await ops_test.model.create_offer("coredns:dns-provider")
        model_owner = untag("user-", ops_test.model.info.owner_tag)
        log.info("Consuming CMR offer")
        saas = await client_model.consume(f"{model_owner}/{ops_test.model_name}.coredns")
        log.info("Relating to CMR offer")
        relation = await relation_app.add_relation("dns-provider", "coredns:dns-provider")
        await client_model.wait_for_idle(status="active", timeout=60)
    finally:
        if not ops_test.keep_client_model:
            try:
                if relation:
                    log.info("Cleaning up client relation")
                    await relation_app.remove_relation("dns-provider", "coredns:dns-provider")
                    await client_model.wait_for_idle(raise_on_blocked=False, timeout=60)
                    await ops_test.model.wait_for_idle(timeout=60)
                if saas:
                    log.info("Removing CMR consumer")
                    await client_model.remove_saas("coredns")
                if offer:
                    log.info("Removing CMR offer")
                    await ops_test.model.remove_offer("coredns")
            except Exception:
                log.exception("Error performing cleanup")
