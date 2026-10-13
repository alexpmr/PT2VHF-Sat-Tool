"""Image metadata must remain conservative and license-attributed."""
from sat_tool.media import find_photo,photo_html


def test_no_imaginary_photo_for_short_name(tmp_path):
    assert find_photo(tmp_path,"ISS","25544") is None
    assert "indisponível" in photo_html(None)


def test_metadata_image_is_escaped():
    result={"url":"https://upload.wikimedia.org/a.jpg","source":"https://commons.wikimedia.org/wiki/File:A.jpg",
            "author":"Contributor<script>x</script>","license":"CC BY-SA 4.0"}
    page=photo_html(result)
    assert "CC BY-SA 4.0" in page
    assert "<script>" not in page
