import os
import re
import json
import hashlib

NUMBER_PATTERN = re.compile(r'{\d+}')


class StringUtils:
    @staticmethod
    def convert_translations_in_modifier(modifier: str) -> str:
        """Resolves all brackets(translations) in a translation stat string
        Example: "Adds {0} to {1} [Lightning|Lightning] Damage": "Adds {0} to {1} Lightning Damage"
        Example: "Fügt {0} bis {1} [Lightning|Blitz]schaden hinzu": "Fügt {0} bis {1} Blitzschaden hinzu"
        """
        if len(modifier) == 0:
            return modifier
        
        open_square_bracket = modifier.find("[")
        close_square_bracket = modifier.find("]")
        
        while open_square_bracket >= 0 and close_square_bracket > 0:
            # resolve brackets, this can be either the plain text or a key|value pair
            key = modifier[open_square_bracket + 1:close_square_bracket]

            if "|" in key: # key|value pair
                key = key.split("|")[1] # use value
            modifier = modifier[:open_square_bracket] + key + modifier[close_square_bracket + 1:]
                
            open_square_bracket = modifier.find("[")
            close_square_bracket = modifier.find("]")
            
        return modifier
    
    @staticmethod
    def convert_number_placeholder_in_modifier(modifier: str) -> str:
        """Converts all number placeholders in a stat string to #."""
        if len(modifier) == 0:
            return modifier
        
        # replace all {0-9} with #
        for match in NUMBER_PATTERN.findall(modifier):
            modifier = modifier.replace(match, "#")
            
        # replace {0:+d} with +# (for example: +1)
        modifier = modifier.replace("{0:+d}", "+#")

        return modifier
    
    @staticmethod
    def convert_stat_name(modifier: str) -> str:
        """Converts a stat name to a readable format"""
        modifier = modifier.strip()
        modifier = StringUtils.convert_translations_in_modifier(modifier)
        modifier = StringUtils.convert_number_placeholder_in_modifier(modifier)

        if len(modifier) == 0:
            return None
        
        if modifier[0] == "{" and modifier[1] == "}":
            modifier = "#" + modifier[2:]
            
        return modifier


class Parser:
    lang: str # Language name
    langCode: str # Language code
    
    base_dir: str # Base directory for the dumped data
    output_dir: str # Output directory for the parsed data
    
    mod_translations: dict      = {} # Translations for mods
    base_items: dict            = {} # Base items
    item_classes: dict          = {} # Item classes
    item_class_categories: dict = {} # Item class categories
    armour_types: dict          = {} # Armour types
    weapon_types: dict          = {} # Weapon types
    skill_gems: dict            = {} # Skill gems
    skill_gem_info: dict        = {} # Skill gem info
    stats_file: dict            = {} # Stats file - modifiers
    mods_file: dict             = {} # Mods file - modifiers
    modifiers: dict             = {} # Stats
    mods: dict                  = {} # Mods
    parsed_item_class_categories: dict = {} # Parsed item class categories
    parsed_item_classes: dict   = {} # Parsed item classes
    unique_items: list          = [] # Parsed unique items from the poe trade2 api
    items: dict                 = {} # Parsed items
    
    def __init__(self, cwd: str, lang: str, langCode: str, translation_files: list, trade_api_modifiers: dict, trade_api_items: dict, item_trade_statics: dict):
        self.lang       = lang
        self.langCode   = langCode
        self.cwd        = cwd
        
        self.base_dir               = self.cwd + f"/tables/{self.lang}/"
        self.out_dir                = self.cwd + f"/../renderer/public/data/{self.langCode}/"
            
        self.TRANSLATION_FILES      = translation_files
        self.TRADE_API_MODIFIERS    = trade_api_modifiers
        self.TRADE_API_ITEMS        = trade_api_items
        self.TRADE_API_ITEM_STATICS = item_trade_statics
        
        self.base_items             = self.load_file("BaseItemTypes")
        self.item_classes           = self.load_file("ItemClasses")
        self.item_class_categories  = self.load_file("ItemClassCategories")
        self.armour_types           = self.load_file("ArmourTypes")
        self.weapon_types           = self.load_file("WeaponTypes")
        self.skill_gems             = self.load_file("SkillGems")
        self.skill_gem_info         = self.load_file("SkillGemInfo")
        self.stats_file             = self.load_file("Stats")
        self.mods_file              = self.load_file("Mods")
        
    def load_file(self, file: str) -> dict:
        """Loads a file from the base directory"""
        return json.loads(open(f"{self.base_dir}/{file}.json").read())
    
    def parse_modifier(self, id: str, strings: list):
        """Parses the given modifier"""
        matchers = []
        seen = set()
        
        def add_matcher(matcher: str, negate: bool, type: str) -> None:
            if matcher not in seen:
                seen.add(matcher)
                matchers.append({
                    "string": matcher,
                    "negate": negate,
                    "type": type
                })
        
        if len(strings) == 0:
            return
        
        ref = None
        for raw in strings:
            lang = StringUtils.convert_stat_name(raw)
            
            if lang == None:
                continue
                    
            matcher = lang
            # remove prefixs
            if "+#" in matcher:
                matcher = matcher.replace("+#", "#")

            has_negate = matcher.find("negate") > 0
            
            if has_negate:
                matcher = matcher[:matcher.find('"')].strip()

            # the following part is super disgusting
            # the issue is, i dont know typescript
            # so i have to do all possible modifier combinations in python

            add_matcher(matcher, has_negate, "matcher")
            add_matcher(lang, has_negate, "lang")
                        
            # fix up raw if its the negated version
            if has_negate:
                raw = raw[:raw.find('"')].strip()
                
            add_matcher(raw, has_negate, "raw")

            # raw - placeholders replaced
            # not so raw anymore, i guess?
            not_so_raw = StringUtils.convert_number_placeholder_in_modifier(raw)
            if raw != not_so_raw:
                add_matcher(not_so_raw, has_negate, "not_so_raw")
                if "+#" in not_so_raw:
                    add_matcher(not_so_raw.replace("+#", "#"), has_negate, "not_so_raw_2")
                
            if ref == None:
                ref = lang
            
        id = id.split(" ")
        
        for a in id:
            self.mod_translations[a] = {
                "ref": ref,
                "matchers": matchers,
            }
    
    def parse_translation_file(self, file: str) -> None:
        """Parses the given translation file"""
        dir = f"{self.cwd}/descriptions/{file}"
        
        print("Parsing", dir)
        
        modifier_translations = open(dir, encoding="utf-16").read().split("\n")
        
        for i in range(0, len(modifier_translations)):
            line = modifier_translations[i]

            if line == "description":
                # start of the translation block
                id = modifier_translations[i + 1].strip()[2:].replace('"', "") # skip first 2 characters
                amt_stat_translations = modifier_translations[i + 2].strip()
                
                strings = []
                for j in range(0, int(amt_stat_translations)):
                    translation_string = modifier_translations[i + 3 + j].strip() # skip first 2 characters
                    start = translation_string.find('"')
                    end = translation_string.rfind('"')
                    translation_string = translation_string[start + 1: end] # remove quotes
                    
                    if "negate" in translation_string:
                        # mod has a negated version
                        end = translation_string.find('negate')
                        translation_string = translation_string[translation_string.find('"') + 1:end + len('negate')] # remove quotes and negate
                        
                    strings.append(translation_string)
                        
                self.parse_modifier(id, strings)

    def parse_mods(self) -> None:
        """Parses the mods file"""
        
        for stat in self.stats_file:
            id = stat.get("_index")
            name = stat.get("Id")
            self.modifiers[id] = name   
        
        # translations
        for file in self.TRANSLATION_FILES:
            if os.path.isdir(f"{self.cwd}/descriptions/{file}"):
                # traverse directories if it doesnt start with _
                if not file.startswith("_"):
                    for _file in os.listdir(f"{self.cwd}/descriptions/{file}"):
                        self.parse_translation_file(f"{file}/{_file}")
            elif ".csd" in file:
                self.parse_translation_file(file)
                
        for mod in self.mods_file:
            id = mod.get("Id")
            stats_key = mod.get("StatsKey1")
            if stats_key != None:
                stats_id = self.modifiers.get(stats_key)
                translation = self.mod_translations.get(stats_id)
                if translation:
                    ref = translation.get("ref")
                    matchers = translation.get("matchers")
                    
                    trade_ids = {}
                    for matcher in matchers:
                        search = matcher.get("string")
                        ids = self.TRADE_API_MODIFIERS.get(search)
                        if ids != None:
                            trade_ids = ids
                            
                    # if len(trade_ids) == 0:
                        # print("No trade ids found for", matchers[0].get("string"))
                        
                    self.mods[stats_id] = {
                        "ref": ref,
                        "better": 1,
                        "id": stats_id,
                        "matchers": translation.get("matchers"),
                        "trade": {"ids": trade_ids}
                    }

    def parse_categories(self) -> None:
        """Parses the item categories"""
        
        for cat in self.item_class_categories:
            id = cat.get("_index")
            if id == None:
                continue
            
            text = cat.get("Id")
            self.parsed_item_class_categories[id] = text    

        for cat in self.item_classes:
            id = cat.get("_index")
            if id == None:
                continue
            
            text = cat.get("Id")
            self.parsed_item_classes[id] = {
                "name": text,
                "short": self.parsed_item_class_categories.get(cat.get("ItemClassCategory"))
            }    

    def parse_items(self) -> None:
        """Parses all base items including uniques"""
        
        # NOTE: Unique items aren't translated into the correct language
        for entry in self.TRADE_API_ITEMS["result"]:
            for item in entry.get("entries"):
                name = item.get("name")
                if name == None:
                    continue
                type = item.get("type")
                
                self.unique_items.append({
                    "name": name,
                    "refName": name,
                    "namespace": "UNIQUE",
                    "unique": {
                        "base": type
                    }
                })

        # parse base items
        for item in self.base_items:
            id = item.get("_index")
            if id == None:
                continue
            
            name = item.get("Name")
            
            if len(name) == 0:
                continue
            
            class_key = item.get("ItemClassesKey")
            
            self.items[id] = {
                "name": name,
                "refName": name,
                "namespace": "ITEM",
                "class": class_key,
                "dropLevel": item.get("DropLevel"),
                "icon": "%NOT_FOUND%"
            }
            
            class_info = self.parsed_item_classes.get(class_key)
            
            if class_info != None:
                class_info = class_info.get("short")
                
                if "flask" in name.lower():
                    class_info = "Flask"
                
                # if class_info in ["Belt", "Ring", "Amulet"]:
                if class_info != None:
                    self.items[id].update({
                        "craftable": {
                            "category": class_info
                        }
                    })
            else:
                print("No class info found for", name)
        # convert base items into gems
        for gem in self.skill_gems:
            id = gem.get("BaseItemTypesKey")
            if id in self.items:
                self.items[id].update({
                    "namespace": "GEM",
                    "gem": {
                        "awakened": False,
                        "transfigured": False
                    }
                })
            
        # weapons and armor need the craftable tag ("craftable": "type (helmet, boots etc)")
        # convert base items into weapons
        for wpn in self.weapon_types:
            id = wpn.get("BaseItemTypesKey")
            
            if id in self.items:
                class_key = self.items[id].get("class")
                self.items[id].update({
                    "craftable": {
                        "category": self.parsed_item_classes.get(class_key).get("short"),
                    }
                })

        # convert base items into armor types
        # armour needs the armour tag ("armour": "ar": [min, max], "ev": [min, max], "es": [min, max])
        for armour in self.armour_types:
            id = armour.get("BaseItemTypesKey")
            
            ar = [armour.get("ArmourMin"), armour.get("ArmourMax")]
            ev = [armour.get("EvasionMin"), armour.get("EvasionMax")]
            es = [armour.get("EnergyShieldMin"), armour.get("EnergyShieldMax")]
            
            armour = {}
            
            if ar[1] > 1:
                armour["ar"] = ar
            
            if ev[1] > 1:
                armour["ev"] = ev
            
            if es[1] > 1:
                armour["es"] = es
            
            if id in self.items:
                self.items[id].update({ 
                    "armour": armour
                })

    def resolve_item_classes(self) -> None:
        """Resolves the item classes and their categories"""
        
        for item_class in self.item_classes:
            id = item_class.get("_index")
            if id == None:
                continue
            
            name = item_class.get("Name")
            item_class_category = item_class.get("ItemClassCategory")
            
            if id in self.items:
                self.items[id].update({
                    "class": name,
                    "category": self.parsed_item_classes.get(item_class_category)
                })

    def write_items_to_file(self) -> None: 
        """Writes all items to the items.ndjson file"""
        f = open(f"{self.out_dir}/items.ndjson", "w", encoding="utf-8")
        for item in self.items.values():
            name = item.get("name")
            namespace = item.get("namespace", "ITEM")
            craftable = item.get("craftable", None)
            gem = item.get("gem", None)
            armour = item.get("armour", None)
            icon = item.get("icon", None)
            
            trade_tag = self.TRADE_API_ITEM_STATICS.get(name)
            
            out = {
                "name": name,
                "refName": name,
                "namespace": namespace, 
                "icon": icon
            }
            
            if trade_tag != None:
                # print("Trade tag found for", name)
                out.update({
                    "tradeTag": trade_tag.get("tradeTag"),
                    "icon": trade_tag.get("icon")
                })
            
            if craftable:
                out.update({
                    "craftable": craftable
                })
                
            if armour:
                out.update({
                    "armour": armour
                })
                
            if gem:
                out.update({
                    "gem": gem
                })
            
            f.write(json.dumps(out) + "\n")
            
        for item in self.unique_items:
            f.write(json.dumps(item) + "\n")
            
        f.close()

    def write_modifiers_to_file(self) -> None:
        """Writes all modifiers to the stats.ndjson file"""
        seen = set()
        m = open(f"{self.out_dir}/stats.ndjson", "w", encoding="utf-8")
        for mod in self.mods.values():
            # compute hash of the mod
            hash = hashlib.md5(json.dumps(mod).encode()).hexdigest()
            if hash in seen:
                continue
            
            m.write(json.dumps(mod) + "\n")
            seen.add(hash)
            
        m.close()
        
    def write_to_file(self) -> None:
        self.write_items_to_file()
        self.write_modifiers_to_file()
        
        # data dumping
        with open("items_dump.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.items, indent=4))
        
        with open("mods_dump.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.mods, indent=4))

    def parse(self) -> None:
        """Parses all data"""
        self.parse_mods()
        self.parse_categories()
        self.parse_items()
        self.resolve_item_classes()
        self.write_to_file()