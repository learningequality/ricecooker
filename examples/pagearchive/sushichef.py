#!/usr/bin/env python
"""Sample page-archiving chef.

Renders a JS/SPA page with single-file-cli and seals it into an offline HTML5
zip via the ricecooker pipeline. Enable the render path by overriding
``build_file_pipeline`` to return ``make_page_archiving_pipeline`` and marking
the source URI with the ``singlefile+`` prefix.

Prerequisites (page archiving only — the core install does not need these):
    npm install -g single-file-cli
    plus a Chromium/Chrome browser on PATH (or pass --browser-executable-path
    via the node ``context``).
See docs/installation.md.
"""
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import TopicNode
from ricecooker.utils.pipeline import make_page_archiving_pipeline

# A small, stable, public single-page app used as the render target. TodoMVC's
# React example is a classic minimal SPA (its HTML is a shell that JavaScript
# fills in at runtime), so it exercises the headless-render path. Confirm the
# exact path during the manual offline-render verification (see README.md).
SPA_TARGET = "https://todomvc.com/examples/react/dist/"


class PageArchiveChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Page archiving demo channel",
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # where content comes from
        "CHANNEL_SOURCE_ID": "<unique id for the channel>",  # CHANGE ME!!!
        "CHANNEL_LANGUAGE": "en",  # le_utils language code
        "CHANNEL_DESCRIPTION": "Headless page archiving via single-file-cli.",
    }

    def build_file_pipeline(self, default_context):
        # Opt in to the render handler; forward default_context so --compress
        # settings still apply to the exploded assets.
        return make_page_archiving_pipeline(default_context=default_context)

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        topic = TopicNode(title="Archived pages", source_id="archived_pages")
        channel.add_child(topic)
        page_node = ContentNode(
            title="TodoMVC (React)",
            description="A JS/SPA rendered to an offline HTML5 zip.",
            source_id="todomvc-react",
            license=get_license("Public Domain"),
            language="en",
            uri="singlefile+" + SPA_TARGET,
            # Crawl depth + link scope (parity with the old link_policy).
            context={"crawl_max_depth": 1, "crawl_inner_links_only": True},
        )
        topic.add_child(page_node)
        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py  --token=YOURTOKENHERE9139139f3a23232
    """
    chef = PageArchiveChef()
    chef.main()
