import logging

import pytest_asyncio
import yaml
import pytest
from pathlib import Path
from lightkube import Client
import asyncio
from random import choices
from string import ascii_lowercase, digits
import juju.model

log = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--client-model",
        action="store",
        help="Name of client model to use; if not provided, will "
        "create one and clean it up after.",
    )
    parser.addoption(
        "--keep-client-model",
        action="store_true",
        help="Flag to keep the client model, if automatically created.",
    )


@pytest.fixture(scope="session")
def helpers():
    return Helpers()


@pytest.fixture(scope="module")
def lightkube_client():
    return Client()


@pytest_asyncio.fixture
async def client_model(ops_test, request):
    # TODO: fold this into pytest-operator
    model_name = request.config.option.client_model
    if not model_name:
        ops_test.keep_client_model = request.config.option.keep_client_model
        module_name = request.module.__name__.rpartition(".")[-1]
        suffix = "".join(choices(ascii_lowercase + digits, k=4))
        model_name = f"{module_name.replace('_', '-')}-client-{suffix}"
        if not ops_test._controller:
            ops_test._controller = juju.model.Controller()
            await ops_test._controller.connect(ops_test.controller_name)
        model = await ops_test._controller.add_model(model_name, cloud_name=ops_test.cloud_name)
        # NB: This call to `juju models` is needed because libjuju's
        # `add_model` doesn't update the models.yaml cache that the Juju
        # CLI depends on with the model's UUID, which the CLI requires to
        # connect. Calling `juju models` beforehand forces the CLI to
        # update the cache from the controller.
        await ops_test.juju("models")
    else:
        ops_test.keep_client_model = True
        model = juju.model.Model()
        await model.connect(model_name)
    try:
        yield model
    finally:
        if not ops_test.keep_client_model:
            try:
                await asyncio.gather(*(app.remove() for app in model.applications.values()))
                await model.block_until(lambda: not model.applications, timeout=2 * 60)
            except asyncio.TimeoutError:
                log.error("Timed out cleaning up client model")
            except Exception:
                log.exception("Error cleanup in client model")
        await model.disconnect()
        if not ops_test.keep_client_model:
            await ops_test._controller.destroy_model(model_name)


class Helpers:
    @staticmethod
    def oci_image(metadata_file: str, image_name: str) -> str:
        """Find upstream source for a container image.
        Args:
            metadata_file: string path of metadata YAML file relative
                to top level charm directory
            image_name: OCI container image string name as defined in
                metadata.yaml file
        Returns:
            upstream image source
        Raises:
            FileNotFoundError: if metadata_file path is invalid
            ValueError: if upstream source for image name can not be found
        """
        metadata = yaml.safe_load(Path(metadata_file).read_text())

        resources = metadata.get("resources", {})
        if not resources:
            raise ValueError("No resources found")

        image = resources.get(image_name, {})
        if not image:
            raise ValueError(f"{image_name} image not found")

        upstream_source = image.get("upstream-source", "")
        if not upstream_source:
            raise ValueError("Upstream source not found")

        return upstream_source
