#!/usr/bin/env python
"""Sample page-archiving chef: renders a JS/SPA page to an offline HTML5 zip via
the built-in ``singlefile+`` DOWNLOAD handler. See README.md / docs/installation.md
for the single-file-cli + Chromium prerequisites.
"""
from ricecooker.chefs import SushiChef
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ContentNode
from ricecooker.classes.nodes import TopicNode

# A small, stable, public SPA render target (TodoMVC's React example). Confirm
# the exact path during manual offline-render verification (see README.md).
SPA_TARGET = "https://todomvc.com/examples/react/dist/"


class PageArchiveChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "Page archiving demo channel",
        "CHANNEL_SOURCE_DOMAIN": "<yourdomain.org>",  # where content comes from
        "CHANNEL_SOURCE_ID": "<unique id for the channel>",  # CHANGE ME!!!
        "CHANNEL_LANGUAGE": "en",  # le_utils language code
        "CHANNEL_DESCRIPTION": "Headless page archiving via single-file-cli.",
    }

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
