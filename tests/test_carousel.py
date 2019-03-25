import shutil
from ricecooker.utils.carousel import create_carousel_node

def test_carousel():
    node = create_carousel_node(
            ["http://placekitten.com/200/300",
             "http://placekitten.com/200/301",
             "http://placekitten.com/200/302",
             "http://placekitten.com/200/303",
             "http://placekitten.com/200/304"],
            license = "Public Domain",
            copyright_holder = "X")
    filename = str(node.files[0])
    with open(filename, "rb") as f:
        assert b"PK" == f.read(2)[:2]
    shutil.rmtree("__carousel_downloads")

