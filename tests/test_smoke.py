def test_package_imports_and_has_version():
    import civitai_hub

    assert isinstance(civitai_hub.__version__, str)
    assert civitai_hub.__version__
