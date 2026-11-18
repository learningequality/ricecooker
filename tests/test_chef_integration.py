#!/usr/bin/env python
import copy
import csv
import glob
import importlib.util
import json
import logging
import os
import random
import socket
import socketserver
import string
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock

import pytest
import requests
from le_utils.constants import licenses

from ricecooker import config
from ricecooker.chefs import SushiChef
from ricecooker.classes.files import AudioFile
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.files import VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import AudioNode
from ricecooker.classes.nodes import ChannelNode
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import DocumentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.classes.nodes import VideoNode
from ricecooker.commands import create_initial_tree
from ricecooker.commands import uploadchannel
from ricecooker.commands import uploadchannel_wrapper
from ricecooker.exceptions import InvalidNodeException
from ricecooker.exceptions import InvalidUsageException
from ricecooker.utils.pipeline import FilePipeline
from ricecooker.utils.request_utils import ReconnectingAdapter


class TestChef(SushiChef):
    """
    Used as an integration test by actually using Ricecooker to chef local test content into Studio.

    For anything you need to test, add it to the channel created in the `construct_channel`.

    Copied from examples/tutorial/sushichef.py
    """

    # Be sure we don't conflict with a channel someone else pushed before us when running this test
    # as the channel source domain and ID determine which Channel is updated on Studio and since
    # you'll run this with your own API key we can use this random (enough) string generator (thanks SO)
    # to append a random set of characters to the two values.
    def randomstring():
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )

    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "RicecookerIntegrationTest.{}".format(
            randomstring()
        ),  # who is providing the content (e.g. learningequality.org)
        "CHANNEL_SOURCE_ID": "RicecookerTests.{}".format(
            randomstring()
        ),  # channel's unique id
        "CHANNEL_TITLE": "Ricecooker Testing!",
        "CHANNEL_LANGUAGE": "en",
    }

    # CONSTRUCT CHANNEL
    def construct_channel(self, *args, **kwargs):
        """
        This method is reponsible for creating a `ChannelNode` object and
        populating it with `TopicNode` and `ContentNode` children.
        """
        # Create channel
        ########################################################################
        channel = self.get_channel(*args, **kwargs)  # uses self.channel_info

        # Create topics to add to your channel
        ########################################################################
        # Here we are creating a topic named 'Example Topic'
        exampletopic = TopicNode(source_id="topic-1", title="Example Topic")

        # Now we are adding 'Example Topic' to our channel
        channel.add_child(exampletopic)

        # You can also add subtopics to topics
        # Here we are creating a subtopic named 'Example Subtopic'
        examplesubtopic = TopicNode(source_id="topic-1a", title="Example Subtopic")

        # Now we are adding 'Example Subtopic' to our 'Example Topic'
        exampletopic.add_child(examplesubtopic)

        # Content
        # You can add documents (pdfs and ePubs), videos, audios, and other content
        # let's create a document file called 'Example PDF'
        document_file = DocumentFile(path="http://www.pdf995.com/samples/pdf.pdf")
        examplepdf = DocumentNode(
            title="Example PDF",
            source_id="example-pdf",
            files=[document_file],
            license=get_license(licenses.PUBLIC_DOMAIN),
        )

        # We are also going to add a video file called 'Example Video'
        video_file = VideoFile(
            path="https://archive.org/download/vd_is_for_everybody/vd_is_for_everybody_512kb.mp4"
        )
        fancy_license = get_license(
            licenses.SPECIAL_PERMISSIONS,
            description="Special license for ricecooker fans only.",
            copyright_holder="The chef video makers",
        )
        examplevideo = VideoNode(
            title="Example Video",
            source_id="example-video",
            files=[video_file],
            license=fancy_license,
        )

        # Finally, we are creating an audio file called 'Example Audio'
        audio_file = AudioFile(
            path="https://ia800203.us.archive.org/26/items/Bach_Original_works_and_transcriptions-6556/Felipe_Sarro_-_08_-_Bach_Sinfonia_11_BWV_797.mp3"
        )
        exampleaudio = AudioNode(
            title="Example Audio",
            source_id="example-audio",
            files=[audio_file],
            license=get_license(licenses.PUBLIC_DOMAIN),
        )

        # Now that we have our files, let's add them to our channel
        channel.add_child(examplepdf)  # Adding 'Example PDF' to your channel
        exampletopic.add_child(
            examplevideo
        )  # Adding 'Example Video' to 'Example Topic'
        examplesubtopic.add_child(
            exampleaudio
        )  # Adding 'Example Audio' to 'Example Subtopic'

        # the `construct_channel` method returns a ChannelNode that will be
        # processed by the ricecooker framework
        return channel


class NeverRunChef(SushiChef):
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "example.org",
        "CHANNEL_SOURCE_ID": "example",
        "CHANNEL_TITLE": "Example",
        "CHANNEL_LANGUAGE": "en",
    }

    def get_channel(self, **kwargs):
        return ChannelNode(
            source_domain="example.org", source_id="example", title="Example"
        )

    def download_content(self):
        raise AssertionError("downloaded content")

    def construct_channel(self, **kwargs):
        raise AssertionError("constructed channel")


@pytest.mark.parametrize(
    "channel_info",
    [{**NeverRunChef.channel_info, "CHANNEL_ID": "0" * 32}, {"CHANNEL_ID": "0" * 32}],
    ids=["with_source_keys", "without_source_keys"],
)
def test_channel_id_in_channel_info_is_rejected_before_login(offline, channel_info):
    chef = NeverRunChef()
    chef.channel_info = channel_info

    with pytest.raises(InvalidUsageException, match="CHANNEL_ID is not supported"):
        uploadchannel(chef, token="t")


@pytest.mark.parametrize("removed", [{"resume": True}, {"step": "LAST"}])
def test_uploadchannel_rejects_removed_resume_kwargs_before_login(offline, removed):
    with pytest.raises(InvalidUsageException, match="removed"):
        uploadchannel(NeverRunChef(), token="t", **removed)


class StepChef(SushiChef):
    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument("--step", type=int)

    def construct_channel(self, **kwargs):
        raise AssertionError(f"constructed channel with step={kwargs['step']}")


def test_chef_registered_step_flag_reaches_construct_channel(offline, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["./sushichef.py", "dryrun", "--step", "3"])
    chef = StepChef()
    args, options = chef.parse_args_and_options()

    with pytest.raises(AssertionError, match="step=3"):
        uploadchannel_wrapper(chef, args, options)


@pytest.fixture
def chef_config(monkeypatch):
    for name in (
        "UPDATE",
        "VIDEO_HEIGHT",
        "THUMBNAILS",
        "STAGE",
        "PUBLISH",
        "FILE_PIPELINE",
    ):
        monkeypatch.setattr(config, name, getattr(config, name))
    monkeypatch.setattr(config, "DOWNLOAD_SESSION", requests.Session())


class RunOverrideChef(SushiChef):
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "example.org",
        "CHANNEL_SOURCE_ID": "run-override",
        "CHANNEL_TITLE": "Run override",
        "CHANNEL_LANGUAGE": "en",
    }
    DOMAIN_AUTH_HEADERS = {"example.org": {"X-Api-Key": "EXAMPLE_API_KEY"}}

    def construct_channel(self, **kwargs):
        channel = self.get_channel()
        channel.add_child(
            ContentNode(
                source_id="pdf",
                title="PDF",
                license=get_license(licenses.PUBLIC_DOMAIN),
                uri=os.path.join(
                    os.path.dirname(__file__), "testcontent", "samples", "41568-pdf.pdf"
                ),
            )
        )
        return channel

    def run(self, args, options):
        uploadchannel(self, command="dryrun")


@pytest.fixture
def run_override_chef(chef_config, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EXAMPLE_API_KEY", "secret")
    chef = RunOverrideChef()
    chef.CHEF_RUN_DATA = copy.deepcopy(config.CHEF_DATA_DEFAULT)
    return chef


def test_uploadchannel_builds_pipeline_and_auth_for_run_override(run_override_chef):
    run_override_chef.run({}, {})

    request = requests.Request("GET", "https://example.org/x").prepare()
    assert config.DOWNLOAD_SESSION.auth(request).headers["X-Api-Key"] == "secret"


def test_uploadchannel_keeps_pipeline_set_by_run_override(run_override_chef):
    run_override_chef.file_pipeline = custom = FilePipeline()
    run_override_chef.run({}, {})

    assert config.FILE_PIPELINE is custom


class TwoTopicChef(SushiChef):
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": "example.org",
        "CHANNEL_SOURCE_ID": "two-topics",
        "CHANNEL_TITLE": "Two topics",
        "CHANNEL_LANGUAGE": "en",
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel()
        channel.add_child(TopicNode("t", "T"))
        channel.add_child(TopicNode("sibling", "Sibling"))
        return channel


def _write_content_metadata_csv(tmp_path, row):
    data_dir = tmp_path / "chefdata" / "data"
    data_dir.mkdir(parents=True)
    with open(data_dir / "content_metadata.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_HEADERS)
        writer.writeheader()
        writer.writerow(row)


def _studio_post(posted, finished, rejects):
    """Fake Studio that fails an ``add_nodes`` batch with any child ``rejects`` matches."""

    def studio_post(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        if url == config.authentication_url():
            body = {"username": "chef"}
        elif url == config.check_version_url():
            body = {"status": 0, "message": ""}
        elif url == config.add_nodes_url():
            children = json.loads(kwargs["data"])["content_data"]
            if any(rejects(c) for c in children):
                response.status_code = 500
                response._content = b'"Internal server error"'
                return response
            posted.extend(children)
            body = {"root_ids": {c["node_id"]: "srv_" + c["node_id"] for c in children}}
        else:
            if url == config.finish_channel_url():
                finished.append(url)
            body = {"root": "root", "channel_id": "chan-id", "new_channel": "chan-id"}
        response._content = json.dumps(body).encode("utf-8")
        return response

    return studio_post


def _has_long_tag(child):
    return any(len(tag) > config.MAX_TAG_LENGTH for tag in child["tags"])


def test_uploadchannel_truncates_long_csv_new_title_for_studio(
    chef_config, monkeypatch, tmp_path, caplog
):
    monkeypatch.chdir(tmp_path)
    _write_content_metadata_csv(tmp_path, {"Source ID": "t", "New Title": "x" * 201})
    posted = []
    finished = []
    # Studio's title column is varchar(200); the overflow surfaces as a 500.
    monkeypatch.setattr(
        config.SESSION,
        "post",
        _studio_post(
            posted, finished, lambda c: len(c["title"]) > config.MAX_TITLE_LENGTH
        ),
    )

    with caplog.at_level(logging.WARNING, logger=config.LOGGER.name):
        uploadchannel(TwoTopicChef(), token="t")

    titles = {c["source_id"]: c["title"] for c in posted}
    assert titles == {"t": "x" * config.MAX_TITLE_LENGTH, "sibling": "Sibling"}
    assert finished
    assert any(
        "title" in r.getMessage() and "truncating" in r.getMessage()
        for r in caplog.records
    )


def test_uploadchannel_drops_long_csv_new_tag_for_studio(
    chef_config, monkeypatch, tmp_path, caplog
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "STRICT", False)
    long_tag = "t" * 31
    _write_content_metadata_csv(
        tmp_path, {"Source ID": "t", "New Tags": f"short,{long_tag}"}
    )
    posted = []
    finished = []
    monkeypatch.setattr(
        config.SESSION, "post", _studio_post(posted, finished, _has_long_tag)
    )

    with caplog.at_level(logging.WARNING, logger=config.LOGGER.name):
        uploadchannel(TwoTopicChef(), token="t")

    tags = {c["source_id"]: c["tags"] for c in posted}
    assert tags == {"t": ["short"], "sibling": []}
    assert finished
    assert any(
        "(t):" in r.getMessage() and long_tag in r.getMessage() for r in caplog.records
    )
    with open(tmp_path / "chefdata" / "data" / "content_metadata.csv") as f:
        rows = {row["Source ID"]: row for row in csv.DictReader(f)}
    assert rows["t"]["New Tags"] == f"short,{long_tag}"


def test_uploadchannel_fails_on_long_csv_new_tag_before_add_nodes_in_strict_mode(
    chef_config, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "STRICT", True)
    long_tag = "t" * 31
    _write_content_metadata_csv(tmp_path, {"Source ID": "t", "New Tags": long_tag})
    posted = []
    monkeypatch.setattr(
        config.SESSION, "post", _studio_post(posted, [], lambda c: False)
    )

    with pytest.raises(
        InvalidNodeException, match=f"Invalid New Tags value '{long_tag}'"
    ):
        uploadchannel(TwoTopicChef(), token="t")
    assert posted == []


class SilentDropStudioHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    served_in_epoch = None
    studio_post = staticmethod(_studio_post([], [], lambda c: False))

    def _read_body(self):
        if self.headers.get("Transfer-Encoding") != "chunked":
            return self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = b""
        while True:
            size = int(self.rfile.readline(), 16)
            body += self.rfile.read(size)
            self.rfile.readline()
            if size == 0:
                return body

    def do_POST(self):
        body = self._read_body()
        if self.path == "/drop" or (
            self.served_in_epoch is not None
            and self.served_in_epoch < self.server.idle_epoch
        ):
            self.server.dropped.append(self.path)
            self.close_connection = True
            if self.server.drop_with_reset:
                # Windows' struct linger holds two u_shorts.
                linger = struct.pack("HH" if os.name == "nt" else "ii", 1, 0)
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
                self.connection.close()
            return
        self.server.answered.append((self.path, body))
        self.served_in_epoch = self.server.idle_epoch
        response = self.studio_post(config.DOMAIN + self.path, data=body.decode())
        self.send_response(response.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response._content)))
        self.end_headers()
        self.wfile.write(response._content)

    do_PUT = do_POST

    def log_message(self, *args):
        pass


class SilentDropStudio(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), SilentDropStudioHandler)
        self.answered = []
        self.dropped = []
        self.drop_with_reset = False
        self.idle_epoch = 0
        self.url = f"http://127.0.0.1:{self.server_port}"

    def go_idle(self):
        self.idle_epoch += 1


def _serve(server):
    threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    ).start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def silent_drop_studio():
    yield from _serve(SilentDropStudio())


class SlowBuildChef(TwoTopicChef):
    def __init__(self, studio):
        super().__init__()
        self.studio = studio

    def construct_channel(self, **kwargs):
        self.studio.go_idle()
        return super().construct_channel(**kwargs)


def test_uploadchannel_survives_studio_dropping_idle_connection(
    chef_config, monkeypatch, tmp_path, silent_drop_studio
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "DOMAIN", silent_drop_studio.url)
    monkeypatch.setattr(config.SESSION, "headers", config.SESSION.headers.copy())

    uploadchannel(SlowBuildChef(silent_drop_studio), token="t")

    answered = silent_drop_studio.answered
    assert [path.rsplit("/", 1)[-1] for path, _ in answered] == [
        "authenticate_user_internal",
        "check_version",
        "create_channel",
        "create_channel",
        "add_nodes",
        "finish_channel",
    ]
    assert [path.rsplit("/", 1)[-1] for path in silent_drop_studio.dropped] == [
        "create_channel"
    ]


@pytest.fixture
def reconnecting_session():
    session = requests.Session()
    session.mount("http://", ReconnectingAdapter())
    return session


@pytest.fixture
def idle_reconnecting_session(reconnecting_session, silent_drop_studio):
    url = f"{silent_drop_studio.url}/upload"
    reconnecting_session.post(url).raise_for_status()
    silent_drop_studio.go_idle()
    return reconnecting_session, url


def test_reconnecting_adapter_resends_after_connection_reset(
    idle_reconnecting_session, silent_drop_studio
):
    session, url = idle_reconnecting_session
    silent_drop_studio.drop_with_reset = True

    session.post(url).raise_for_status()

    assert silent_drop_studio.dropped == ["/upload"]
    assert len(silent_drop_studio.answered) == 2


def test_reconnecting_adapter_resends_whole_file_body_after_drop(
    idle_reconnecting_session, silent_drop_studio, tmp_path
):
    session, url = idle_reconnecting_session
    path = tmp_path / "upload.bin"
    path.write_bytes(b"header-content")

    with open(path, "rb") as f:
        f.read(len(b"header-"))
        session.put(url, data=f).raise_for_status()

    assert silent_drop_studio.dropped == ["/upload"]
    assert silent_drop_studio.answered[-1][1] == b"content"


def test_reconnecting_adapter_does_not_resend_unrewindable_body(
    idle_reconnecting_session, silent_drop_studio
):
    session, url = idle_reconnecting_session

    with pytest.raises(requests.ConnectionError):
        session.put(url, data=iter([b"content"]))

    assert silent_drop_studio.dropped == ["/upload"]
    assert len(silent_drop_studio.answered) == 1


def test_reconnecting_adapter_does_not_resend_after_fresh_connection_drop(
    reconnecting_session, silent_drop_studio
):
    with pytest.raises(requests.ConnectionError):
        reconnecting_session.post(f"{silent_drop_studio.url}/drop")

    assert silent_drop_studio.dropped == ["/drop"]


class Socks5Relay(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, target):
        super().__init__(("127.0.0.1", 0), Socks5RelayHandler)
        self.target = target
        self.url = f"socks5h://127.0.0.1:{self.server_address[1]}"


class Socks5RelayHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client = self.request
        client.recv(client.recv(2)[1])
        client.sendall(b"\x05\x00")
        request = client.recv(4)
        address_length = {1: 4, 4: 16}.get(request[3]) or client.recv(1)[0]
        client.recv(address_length + 2)
        with socket.create_connection(self.server.target) as upstream:
            client.sendall(b"\x05\x00\x00\x01" + bytes(6))
            threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()
            _pipe(client, upstream)


def _pipe(source, sink):
    try:
        while data := source.recv(65536):
            sink.sendall(data)
        sink.shutdown(socket.SHUT_WR)
    except OSError:
        pass


@pytest.fixture
def socks_relay(silent_drop_studio):
    yield from _serve(Socks5Relay(silent_drop_studio.server_address))


@pytest.mark.parametrize(
    "proxy_fixture,dropped_path",
    [
        ("silent_drop_studio", "http://studio.invalid/upload"),
        ("socks_relay", "/upload"),
    ],
)
def test_reconnecting_adapter_resends_through_proxy_after_drop(
    reconnecting_session, silent_drop_studio, request, proxy_fixture, dropped_path
):
    proxies = {"http": request.getfixturevalue(proxy_fixture).url}
    url = "http://studio.invalid/upload"
    reconnecting_session.post(url, proxies=proxies).raise_for_status()
    silent_drop_studio.go_idle()

    reconnecting_session.post(url, proxies=proxies).raise_for_status()

    assert silent_drop_studio.dropped == [dropped_path]
    assert len(silent_drop_studio.answered) == 2


def test_reconnecting_adapter_sends_untellable_pipe_body(
    reconnecting_session, silent_drop_studio
):
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"content")
    os.close(write_fd)

    with os.fdopen(read_fd, "rb") as pipe:
        reconnecting_session.post(
            f"{silent_drop_studio.url}/upload", data=pipe
        ).raise_for_status()

    assert silent_drop_studio.answered[-1][1] == b"content"


@pytest.fixture
def offline(chef_config, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(config, "FILE_PIPELINE", FilePipeline())
    monkeypatch.setattr(config, "STRICT", True)


WIKIPEDIA_PAGES = {
    "https://en.wikipedia.org/wiki/List_of_citrus_fruits": """<table>
        <tr><th>Name</th><th>Image</th></tr>
        <tr><td><a href="/wiki/Lemon">Lemon</a></td><td><img src="//upload.wikimedia.org/120px-Lemon.jpg"></td></tr>
        <tr><td><a href="/wiki/Citron">Citron</a></td><td><img src="//upload.wikimedia.org/120px-Citron.svg"></td></tr>
        <tr><td>Unlinked hybrid</td><td></td></tr>
        </table>""",
    "https://en.wikipedia.org/wiki/List_of_potato_cultivars": """<table>
        <tr><th>Name</th><th>Image</th></tr>
        <tr><td><a href="/wiki/Yukon_Gold_potato">Yukon Gold</a></td><td></td></tr>
        </table>""",
}


class CannedPagesAdapter(requests.adapters.BaseAdapter):
    def send(self, request, **kwargs):
        if request.url not in WIKIPEDIA_PAGES:
            raise requests.ConnectionError(f"network disabled in test: {request.url}")
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response._content = WIKIPEDIA_PAGES[request.url].encode()
        return response

    def close(self):
        pass


def load_example_chefs(script):
    name = os.path.basename(os.path.dirname(script))
    spec = importlib.util.spec_from_file_location(f"example_{name}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chefs = []
    for obj in vars(module).values():
        if not (
            isinstance(obj, type)
            and issubclass(obj, SushiChef)
            and obj.__module__ == module.__name__
        ):
            continue
        chef = obj()
        if hasattr(chef, "channel_info"):
            chef.channel_info = {
                **chef.channel_info,
                "CHANNEL_SOURCE_DOMAIN": "example.org",
                "CHANNEL_SOURCE_ID": "example",
            }
        chefs.append(chef)
    return chefs


def construct_offline(chef, monkeypatch):
    session = requests.Session()
    session.mount("https://", CannedPagesAdapter())
    session.mount("http://", CannedPagesAdapter())
    with monkeypatch.context() as m:
        m.setattr(config, "DOWNLOAD_SESSION", session)
        return chef.construct_channel()


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")
EXAMPLE_SCRIPTS = sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*", "sushichef.py")))


@pytest.mark.parametrize(
    "script",
    EXAMPLE_SCRIPTS,
    ids=[os.path.basename(os.path.dirname(s)) for s in EXAMPLE_SCRIPTS],
)
def test_example_chef_builds_valid_tree_offline(script, offline, monkeypatch):
    chefs = load_example_chefs(script)
    assert chefs

    for chef in chefs:
        channel = construct_offline(chef, monkeypatch)
        create_initial_tree(channel)
        assert channel.get_non_topic_descendants()


if __name__ == "__main__":
    """
    This code will run when the sushi chef is called from the command line.
    """
    chef = TestChef()
    print(
        "Note that you will need your Studio API key for this. It will upload to your account."
    )
    chef.main()
