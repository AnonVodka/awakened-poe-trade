"""Tries to prepare the necessary data for poe-trade to work properly. 
It requires all files from 
Path of Exile 2/Bundles2/_.index.bin/metadata/statdescriptions
NOT
Path of Exile 2/Bundles2/_.index.bin/metadata/statdescriptions/specific_skill_stat_descriptions
to be in the descriptions folder

NOTE: This may or may not contain all the necessary data, as the parser is not perfect and neither is the data
For example: Unique armor items are missing the "armour" tag, which is required for poe-trade to work properly

Credits and Resources:
SnosMe - https://github.com/SnosMe/poe-dat-viewer
SnosMe - https://github.com/SnosMe/awakened-poe-trade
"""
import os
import json
import re
from parser import Parser, StringUtils
CWD = os.getcwd()
LANGUAGES = {
    "English": "en",
    # "German": "de"
}

TRANSLATION_FILES       = os.listdir(f"{CWD}/descriptions")
TRADE_API_STATS         = json.loads(open(f"{CWD}/api_stats.json").read()) # content of https://www.pathofexile.com/api/trade2/data/stats
TRADE_API_ITEMS         = json.loads(open(f"{CWD}/api_items.json").read()) # content of https://www.pathofexile.com/api/trade2/data/items
TRADE_API_STATIC        = json.loads(open(f"{CWD}/api_static.json").read()) # content of https://www.pathofexile.com/api/trade2/data/static
modifier_trade_ids = {}
item_trade_statics = {}

def parse_api_modifier_trade_ids():
    """Parses the trade ids from the trade api"""
    for res in TRADE_API_STATS["result"]:
        for entry in res.get("entries"):
            id = entry.get("id")
            text = entry.get("text")
            type = entry.get("type")
            text = StringUtils.convert_stat_name(text)
            
            if text not in modifier_trade_ids:
                modifier_trade_ids[text] = {}
                
            if type not in modifier_trade_ids[text]:
                modifier_trade_ids[text][type] = []
            
            modifier_trade_ids[text][type].append(id)

def parse_api_statics():
    """Parses the static data from the trade api, such as images or trade-tags"""
    for static in TRADE_API_STATIC["result"]:
        for entry in static.get("entries"):
            id = entry.get("id")
            name = entry.get("text")
            image = entry.get("image")
            item_trade_statics[name] = {
                "tradeTag": id,
                "icon": f"https://web.poecdn.com/{image}",
            }

if __name__ == "__main__":
    parse_api_modifier_trade_ids()
    parse_api_statics()
    for (lang, code) in LANGUAGES.items():
        print(f"Starting parser for {lang}")
        parser = Parser(CWD, lang, code, TRANSLATION_FILES, modifier_trade_ids, TRADE_API_ITEMS, item_trade_statics)
        parser.parse()