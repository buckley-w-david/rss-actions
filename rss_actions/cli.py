from contextlib import closing
import logging
from pathlib import Path
import re
import subprocess
import time
from typing import Dict

import listparser  # type: ignore
from reader import make_reader, FeedExistsError  # type: ignore
import typer

from rss_actions.config import RssActionsConfig, FeedType, FeedAction
from rss_actions.runner import exec_cmd

# TODO configurable log level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()


def touch(config_file: Path):
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = RssActionsConfig()  # Creates a config structure with default values
        config.dump(config_file)


def add_list(reader, url):
    reader.add_feed(url)
    reader.add_feed_tag(url, "list")
    # not a real feed, so no updates
    reader.disable_feed_updates(url)


def delete_list(reader, url):
    for feed in reader.get_feeds(tags="from-list:" + url):
        reader.delete_feed(feed)
    reader.delete_feed(url)


def get_list_feeds(url):
    yield from listparser.parse(url).feeds
    # to use the Requests session reader uses
    # (to take advantage of plugins like ua_fallback),
    # use reader._parser.make_session().get()
    # and call parse() with the response


@app.command()
def main(config_file: Path = Path("rss-actions.toml")):
    touch(config_file)
    config = RssActionsConfig.load(config_file)
    with closing(make_reader(config.db)) as reader:
        feeds: Dict[str, FeedAction] = {}
        for feed_action in config.feeds:
            try:
                if feed_action.type == FeedType.OPML:
                    add_list(reader, feed_action.feed_url)
                else:
                    reader.add_feed(feed_action.feed_url)
            except FeedExistsError:
                pass
            feeds[feed_action.feed_url] = feed_action

        # we need to keep track of the feeds that were removed from a list
        for feed in reader.get_feeds(tags=["from-list"]):
            reader.add_feed_tag(feed, "not-in-list-anymore")

        for list_feed in reader.get_feeds(tags=["list"]):
            for feed in get_list_feeds(list_feed.url):
                try:
                    reader.add_feed(feed)
                except FeedExistsError:
                    pass
                reader.add_feed_tag(feed, "from-list")
                reader.add_feed_tag(feed, "from-list:" + list_feed.url)
                reader.remove_feed_tag(feed, "not-in-list-anymore")

        for feed in reader.get_feeds(tags=["from-list", "not-in-list-anymore"]):
            reader.delete_feed(feed)

        # finally, update the actuall feeds (from list or not)
        for url, value in reader.update_feeds_iter():
            if value is None:
                print(url, "not modified")
            elif isinstance(value, Exception):
                print(url, "error:", value)
            else:
                feed = reader.get_feed(url)
                tags = set(reader.get_feed_tags(feed))
                # If it's a list feed
                if "from-list" in tags:
                    for tag in tags:
                        # Find the tag containing the reference to the list
                        if match := re.match(r"from-list:(?P<opml>.+)", tag):
                            # And fetch it's action
                            feed_action = feeds.get(match.group("opml"))
                            break
                    else:
                        # If you can't find the tag, skip
                        continue
                else:
                    feed_action = feeds.get(url)

                if feed_action:
                    exec_cmd(feed_action, feed)

    if __name__ == "__main__":
        app()
