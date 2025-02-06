import pytest


@pytest.fixture
def _image_browser_scenario(image_factory, collection_factory):
    image_factory(public=True)
    image_factory(public=False)
    collection_factory(public=True)
    collection_factory(public=False)
