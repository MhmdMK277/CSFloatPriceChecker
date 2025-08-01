import json
import os

CONFIG_FILE = "csfloat_config.json"
ITEM_DB_FILE = "cs2_items.json"


def load_config(path: str = CONFIG_FILE):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_config(cfg: dict, path: str = CONFIG_FILE) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)


def load_item_names(path: str = ITEM_DB_FILE):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return list(data.keys())
    return []
