from importlib.metadata import version

from affinecap import __version__


def test_runtime_version_matches_installed_distribution_metadata() -> None:
    assert __version__ == version("affinecap")
