from contextlib import closing
import logging
from pathlib import Path
import time

import listparser
from reader import make_reader, FeedExistsError
import typer
import webserial

from rss_actions.config import RssActionsConfig

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
    try:
        reader.add_feed(url)
    except FeedExistsError:
        pass
    reader.add_feed_tag(url, "list")
    # not a real feed, so no updates
    reader.disable_feed_updates(url)


def update_all(reader, calibredb, fanficfare):
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
    updates = []
    for url, value in reader.update_feeds_iter():
        if value is None:
            print(url, "not modified")
        elif isinstance(value, Exception):
            print(url, "error:", value)
        else:
            feed = reader.get_feed(url)
            if feed.link:
                updates.append(feed.link)

    if updates:
        webserial.perform(calibredb, fanficfare, updates)


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
    calibredb = webserial.CalibreDb(
        config.calibre_username, config.calibre_password, config.calibre_library
    )
    fanficfare = webserial.FanFicFare()
    with closing(make_reader(config.db)) as reader:
        add_list(reader, "https://rss.davidbuckley.ca/subscriptions.xml")

        update_interval = 60 * 10
        last_updated = time.monotonic() - update_interval

        while True:
            # Keep sleeping until we need to update.
            while True:
                now = time.monotonic()
                if now - last_updated > update_interval:
                    break
                to_sleep = update_interval - (now - last_updated)
                message = f"updating in {int(to_sleep // 60) + 1} minutes ..."
                print(message)
                time.sleep(to_sleep)

            print("updating ...")
            last_updated = time.monotonic()
            update_all(reader, calibredb, fanficfare)


if __name__ == "__main__":
    app()
