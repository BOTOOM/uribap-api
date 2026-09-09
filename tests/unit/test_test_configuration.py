from pathlib import Path


def test_test_layers_exist() -> None:
    assert Path("tests/unit").is_dir()
    assert Path("tests/integration").is_dir()
    assert Path("tests/api").is_dir()
