from pydantic import BaseModel
import toml

from webserial import config


class TomlModel(BaseModel):
    @classmethod
    def load(cls, file):
        with open(file, "r") as f:
            return cls.parse_obj(toml.load(f))

    def dump(self, file):
        with open(file, "w") as f:
            toml.dump(self.dict(), f)


class RssActionsConfig(config.WebserialConfig, TomlModel):
    db: str = "rss-actions.sqlute"
