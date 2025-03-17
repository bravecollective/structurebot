from __future__ import absolute_import

from structurebot.logger import logger
from collections import Counter

from methodtools import lru_cache

from .util import ncr, name_to_id, names_to_ids, HTTPError  # esi_client, esi_pub, esi_auth, esi_datasource


def is_system_id(location_id):
    """Determines if an ID is in the CCP defined system ID range
    https://github.com/esi/eve-glue/blob/master/eve_glue/location_type.py

    Args:
        location_id (integer): ESI provided ID

    Returns:
        boolean: is or is not a system id

    >>> is_system_id(30000000)
    True
    >>> is_system_id(60000000)
    False
    """
    if 30000000 <= location_id <= 39999999:
        return True
    return False


def is_station_id(location_id):
    """Determines if an ID is in the CCP defined station ID range
    https://github.com/esi/eve-glue/blob/master/eve_glue/location_type.py

    Args:
        location_id (integer): ESI provided ID

    Returns:
        boolean: is or is not a station id

    >>> is_station_id(60000000)
    True
    >>> is_station_id(30000000)
    False
    """
    if 60000000 <= location_id <= 64000000:
        return True
    return False


class Category(object):
    """EVE SDE item category
    https://esi.evetech.net/ui/#/Universe/get_universe_categories_category_id

    Args:
        category_id (integer): ESI provided category ID
        name (string): ESI provided category name
        published (boolean): published item
        groups (list): ESI provided list of member group IDs
    """

    def __init__(self, category_id, name, published, groups):
        """Create new Category"""
        super(Category, self).__init__()
        self.category_id = category_id
        self.name = name
        self.published = published
        self.category_id = category_id
        self.groups = groups

        logger.debug("Class init", extra={**self.__dict__})

    @lru_cache(maxsize=1000)
    @classmethod
    def from_id(cls, id):
        """Creates a new Category from a ESI provided category ID

        Args:
            id (integer): ESI provided category ID

        Raises:
            ValueError: id not an integer
            HTTPError: ESI error

        Returns:
            Category: new category from id
        """
        if not isinstance(id, int):
            raise ValueError('Type ID must be an integer')
        type_response, type_response_data = ncr.get_universe_categories_category_id(
            category_id=id)  # esi_client.request(type_request)
        if type_response.status_code == 200:
            return cls(**type_response_data)
        else:
            raise HTTPError(request=type_response.request, response=type_response)

    @classmethod
    def from_ids(cls, ids):
        """Returns a list of Category's given a list of ESI category IDs

        Args:
            ids (list of ints): ESI provided category ID

        Returns:
            list: list of Category's
        """
        types = []
        for eve_id in ids:
            types.append(cls.from_id(eve_id))
        return types


class Group(object):
    """EVE SDE item group
    https://esi.evetech.net/ui/#/Universe/get_universe_groups_group_id

    Args:
        group_id (integer): ESI provided group ID
        name (string): ESI provided group name
        published (boolean): published item
        category (integer): ESI provided parent category
    """

    def __init__(self, group_id, name, published, category_id, types,
                 category=None):
        """Create new Group"""
        super(Group, self).__init__()
        self.group_id = group_id
        self.name = name
        self.published = published
        self.category_id = category_id
        self.types = types
        self.category = category or Category.from_id(category_id)

        logger.debug("Class init", extra={**self.__dict__})

    @lru_cache(maxsize=1000)
    @classmethod
    def from_id(cls, id):
        """Creates a new Group from a ESI provided group ID

        Args:
            id (integer): ESI provided group ID

        Raises:
            ValueError: id not an integer
            HTTPError: ESI error

        Returns:
            Group: new Group from id
        """
        if not isinstance(id, int):
            raise ValueError('Type ID must be an integer')
        type_response, type_response_data = ncr.get_universe_groups_group_id(group_id=id)
        if type_response.status_code == 200:
            return cls(**type_response_data)
        else:
            raise HTTPError(request=type_response.request, response=type_response)

    @classmethod
    def from_ids(cls, ids):
        """Returns a list of Group's given a list of ESI group IDs

        Args:
            ids (list of ints): ESI provided group ID

        Returns:
            list: list of Group's
        """
        types = []
        for eve_id in ids:
            types.append(cls.from_id(eve_id))
        return types


class BaseType(object):
    """Base EVE SDE Type"""

    def __init__(self, type_id, name, description, published, group_id,
                 group=None, market_group_id=None, radius=None, volume=None,
                 packaged_volume=None, icon_id=None, capacity=None,
                 portion_size=None, mass=None, graphic_id=None,
                 dogma_attributes=[], dogma_effects=[], **kwargs):
        super(BaseType, self).__init__()
        self.type_id = type_id
        self.name = name
        self.description = description
        self.published = published
        self.group_id = group_id
        self.group = group or Group.from_id(group_id)
        self.market_group_id = market_group_id
        self.radius = radius
        self.volume = volume
        self.packaged_volume = packaged_volume
        self.icon_id = icon_id
        self.capacity = capacity
        self.portion_size = portion_size
        self.mass = mass
        self.graphic_id = graphic_id
        self.dogma_attributes = dogma_attributes
        self.attributes = {a['attribute_id']: a['value'] for a in dogma_attributes}
        self.dogma_effects = dogma_effects
        self.effects = {e['effect_id']: e['is_default'] for e in dogma_effects}

        logger.debug("Class init", extra={**self.__dict__})

    @classmethod
    def from_id(cls, ident):
        """Return Type from ident

        Args:
            ident (int): EVE SDE Type id

        Returns:
            Type: Type matching id

        Raises:
            HTTPError: Unexpected ESI error
            ValueError: Not an int
        """
        if not isinstance(ident, int):
            raise ValueError('Type ID must be an integer')
        type_response, type_response_data = ncr.get_universe_types_type_id(type_id=ident)
        if type_response.status_code == 200:
            return cls(**type_response_data)
        else:
            raise HTTPError(request=type_response.request, response=type_response)

    @classmethod
    def from_ids(cls, ids):
        """Returns Types from a list of type IDs

        Args:
            ids (list of ints): list of EVE SDE Type IDs (invalid are ignored)

        Returns:
            list: EVE SDE Types
        """
        types = []
        for eve_id in ids:
            types.append(cls.from_id(eve_id))
        return types

    @classmethod
    def from_name(cls, name):
        """Return a Type from a type name

        Args:
            name (str): Name of an EVE SDE Type

        Returns:
            Type: Type matching name
        """
        eve_id = name_to_id(name, 'inventory_type')
        return cls.from_id(eve_id)

    @classmethod
    def from_names(cls, names):
        """Returns Types from a list of Type names

        Args:
            names (list of str): list of EVE SDE Type names

        Returns:
            TYPE: Description

        >>> [str(i) for i in Type.from_names(['125mm Gatling AutoCannon II'])]
        ['125mm Gatling AutoCannon II - (2873)']
        """
        ids = list(names_to_ids(names)['inventory_types'].values())
        return cls.from_ids(ids)

    def __str__(self):
        return '{} - ({})'.format(self.name, self.type_id)


class Type(BaseType):
    """EVE SDE Type with bulk constructors"""

    @lru_cache(maxsize=5000)
    @classmethod
    def from_id(cls, ident):
        return super(Type, cls).from_id(ident)

    @lru_cache(maxsize=1000)
    @classmethod
    def from_name(cls, name):
        return super(Type, cls).from_name(name)


class Asset(BaseType):
    """EVE Asset Item"""

    def __init__(self, location_id=0, location_type='', quantity=1, item_id=0,
                 is_singleton=True, location_flag='', is_blueprint_copy=None,
                 xyz=None, *args, **kwargs):
        super(Asset, self).__init__(*args, **kwargs)
        self.location_id = location_id
        self.location_type = location_type
        self.quantity = quantity
        self.item_id = item_id
        self.is_singleton = is_singleton
        self.location_flag = location_flag
        self.xyz = xyz

        logger.debug("Class init", extra={**self.__dict__})

    @classmethod
    def from_id(cls, ident, **kwargs):
        asset = super(Asset, cls).from_id(ident)
        for key, value in kwargs.items():
            setattr(asset, key, value)
        return asset

    @classmethod
    def from_name(cls, name, **kwargs):
        asset = super(Asset, cls).from_name(name)
        for key, value in kwargs.items():
            setattr(asset, key, value)
        return asset

    @classmethod
    def from_entity_id(cls, id, id_type):
        """Returns Assets owned by id of id_type

        Args:
            id (int): Asset owner id
            id_type (TYPE): Type of Asset owner (characters or corporations)

        Returns:
            list: Assets owned by id
        """
        #####
        assets = []
        if id_type == 'characters':
            assets_response, assets_response_data = ncr.get_characters_character_id_assets(id)
        elif id_type == 'corporations':
            assets_response, assets_response_data = ncr.get_corporations_corporation_id_assets(id)
        else:
            return assets
        if assets_response.status_code != 200:
            raise HTTPError(request=assets_response.request, response=assets_response)
        for asset in assets_response_data:
            asset_type = Type.from_id(asset['type_id'])
            type_dict = asset_type.__dict__
            asset.update(type_dict)
            assets.append(cls(**asset))
        return assets

    @classmethod
    def from_entity_name(cls, name):
        """Return Assets owned by owner name

        Args:
            name (string): Character or Corporation name

        Returns:
            list: List of Assets
        """
        id_results = names_to_ids([name])
        eve_id = None
        id_type = None
        if 'characters' in id_results:
            id_type = 'characters'
        elif 'corporations' in id_results:
            id_type = 'corporations'
        else:
            return None
        eve_id = id_results[id_type][name]
        return cls.from_entity_id(eve_id, id_type)


class Fitting(object):
    """docstring for Fitting"""

    slots = ['Cargo', 'DroneBay', 'FighterBay', 'FighterTube', 'HiSlot',
             'LoSlot', 'MedSlot', 'RigSlot', 'ServiceSlot', 'SubSystemSlot',
             'StructureFuel', 'QuantumCoreRoom']

    def __init__(self, Cargo=[], DroneBay=[], FighterBay=[], FighterTube=[],
                 HiSlot=[], LoSlot=[], MedSlot=[], RigSlot=[], ServiceSlot=[],
                 SubSystemSlot=[], StructureFuel=[], QuantumCoreRoom=[]):
        super(Fitting, self).__init__()
        self.Cargo = Cargo
        self.DroneBay = DroneBay
        self.FighterBay = FighterBay
        self.FighterTube = FighterTube
        self.HiSlot = HiSlot
        self.LoSlot = LoSlot
        self.MedSlot = MedSlot
        self.RigSlot = RigSlot
        self.ServiceSlot = ServiceSlot
        self.SubSystemSlot = SubSystemSlot
        self.StructureFuel = StructureFuel
        self.QuantumCoreRoom = QuantumCoreRoom

        logger.debug("Class init", extra={**self.__dict__})

    @classmethod
    def from_assets(cls, assets):
        fittings = {slot: [] for slot in Fitting.slots}
        for asset in assets:
            flag = asset.location_flag
            if not flag:
                continue
            for slot in Fitting.slots:
                if flag.startswith(slot):
                    if flag.startswith('FighterTube'):
                        # Fighter tubes report squadrons, which consist of variable quantities
                        asset.quantity = int(asset.attributes.get(2215, 1))
                    fittings[slot].append(asset)
                    fit = True
        return cls(**fittings)

    @staticmethod
    def _name_count(asset):
        name = asset.name
        if asset.quantity > 1:
            name += ' ({})'.format(asset.quantity)
        return name

    @property
    def packaged_volume(self):
        volume = 0
        for slot in self.slots:
            for item in getattr(self, slot):
                volume += item.packaged_volume * item.quantity
        return volume

    def _compare(self, other):
        """Generates a Counter of items in self minus items in other

        Args:
            other (Fitting): Fitting to compare

        Raises:
            NotImplementedError: If other is not a Fitting

        Returns:
            integer: 0 if they're the same, -1 if self is less than other, positive if self is greater than other
        """
        if not isinstance(other, Fitting):
            raise NotImplementedError
        equality = 0
        for slot in Fitting.slots:
            item_counts = {i.type_id: i.quantity - 1 for i in getattr(self, slot)}
            items = Counter([i.type_id for i in getattr(self, slot)])
            items.update(item_counts)
            other_item_counts = {i.type_id: i.quantity - 1 for i in getattr(other, slot)}
            other_items = Counter([i.type_id for i in getattr(other, slot)])
            other_items.update(other_item_counts)
            items.subtract(other_items)
            for item in items.keys():
                if items[item] < 0:
                    return -1
                if items[item] > 0:
                    equality += items[item]
        return equality

    def __eq__(self, other):
        if self._compare(other) == 0:
            return True
        return False

    def __lt__(self, other):
        if self._compare(other) < 0:
            return True
        return False

    def __gt__(self, other):
        if self._compare(other) > 0:
            return True
        return False

    def __le__(self, other):
        if self._compare(other) <= 0:
            return True
        return False

    def __ge__(self, other):
        if self._compare(other) >= 0:
            return True
        return False

    def __bool__(self):
        for slot in self.slots:
            if getattr(self, slot):
                return True
        return False

    __nonzero__ = __bool__

    def __str__(self):
        slot_strings = []
        for slot in Fitting.slots:
            slot_strs = [Fitting._name_count(i) for i in getattr(self, slot, {}) if i]
            if slot_strs:
                slot_str = ', '.join(sorted(slot_strs))
                slot_strings.append('{}: {}'.format(slot, slot_str))
        return '\n'.join(sorted(slot_strings))
