from PIL import Image

from tools.process_images import process_images
from tools.placeholders import generate_placeholders


def test_converts_and_resizes(tmp_path, content_repo):
    src = tmp_path / "src"
    src.mkdir()
    Image.new("RGB", (1600, 1200), "red").save(src / "hero.png")
    Image.new("RGB", (640, 480), "blue").save(src / "step-1.png")
    written = process_images(src, content_repo, "france", "fr-test-un")
    hero = Image.open(content_repo / "france" / "images" / "fr-test-un" / "hero.webp")
    step = Image.open(content_repo / "france" / "images" / "fr-test-un" / "step-1.webp")
    assert hero.format == "WEBP" and hero.width == 1200
    assert step.format == "WEBP" and step.width == 640  # jamais d'upscale
    assert len(written) == 2


def test_real_images_remove_placeholder_marker(tmp_path, content_repo):
    imgdir = content_repo / "france" / "images" / "fr-test-un"
    (imgdir / ".placeholder").write_text("")
    src = tmp_path / "src2"
    src.mkdir()
    Image.new("RGB", (800, 600), "green").save(src / "hero.png")
    process_images(src, content_repo, "france", "fr-test-un")
    assert not (imgdir / ".placeholder").exists()


def test_placeholders_created_with_marker(content_repo):
    imgdir = content_repo / "france" / "images" / "fr-test-un"
    for f in imgdir.iterdir():
        f.unlink()
    written = generate_placeholders(content_repo, "france", "fr-test-un")
    assert (imgdir / "hero.webp").is_file()
    assert (imgdir / "step-1.webp").is_file()
    assert (imgdir / ".placeholder").is_file()
    assert len(written) == 2
    hero = Image.open(imgdir / "hero.webp")
    assert hero.size == (1200, 800)
