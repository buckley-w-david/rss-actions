import dataclasses
import json
import subprocess

from reader import Feed  # type: ignore

from rss_actions.config import FeedAction


def exec_cmd(feed_config: FeedAction, feed: Feed):
    subprocess.run(
        [
            feed_config.cmd,
        ],
        input=json.dumps(dataclasses.asdict(feed), default=str),
        text=True,
        shell=True,
    )
