import base64
import os

# A valid 1x1 PNG — single-file inlines binary assets as base64 ``data:`` URIs,
# and the CONVERT stage needs a decodable image to explode.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def fake_render_page(**expected_kwargs):
    """Return a render_page stand-in that emits an index.html with a data: img.

    The emitted body has real content (the <img>), which the CONVERT stage's
    index.html body validation requires.
    """
    data_uri = "data:image/png;base64," + base64.b64encode(_PNG_1x1).decode()

    def render_page(url, output_dir, **kwargs):
        for key, value in expected_kwargs.items():
            assert kwargs.get(key) == value
        index_path = os.path.join(output_dir, "index.html")
        with open(index_path, "w") as fh:
            fh.write('<html><body><img src="{}"></body></html>'.format(data_uri))
        return index_path

    return render_page
