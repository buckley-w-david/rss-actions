import enum
from typing import List

from pydantic import BaseModel
import toml  # type: ignore


class TomlModel(BaseModel):
    @classmethod
    def load(cls, file):
        with open(file, "r") as f:
            return cls.parse_obj(toml.load(f))

    def dump(self, file):
        with open(file, "w") as f:
            toml.dump(self.dict(), f)


class FeedType(enum.Enum):
    RSS = "rss"
    ATOM = "atom"
    OPML = "opml"  # These need special handling
    JSON = "json"


class FeedAction(TomlModel):
    feed_url: str  # Feed URL
    cmd: str  # What to call with new entires
    type: FeedType = FeedType.RSS  # What kind of feed is this?

    # This is almost certainly the wrong way to go about this, but...
    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d["type"] = d["type"].value
        return d


class RssActionsConfig(TomlModel):
    db: str = "rss-actions.sqlite"
    feeds: List[FeedAction] = [
        FeedAction(
            feed_url="https://example.com/feed.xml",
            cmd="cat",
            type=FeedType.RSS,
            batch=False,
        )
    ]
