from __future__ import absolute_import

import datetime

from .assets import Fitting, Asset, Type
from .config import CONFIG
from .universe import System
from .util import ncr, name_to_id, ids_to_names, HTTPError
from structurebot.logger import logger


class Structure(object):
    def __init__(self, structure_id, corporation_id=None, type_id=None, type_name=None,
                 system_id=None, services=None, fuel_expires=None,
                 accessible=None, name=None, state=None, state_timer_end=None,
                 detonation=None, unanchors_at=None, profile_id=None,
                 fuel=[], fitting=Fitting()):
        super(Structure, self).__init__()
        self.structure_id = structure_id
        self.corporation_id = corporation_id
        self.type_id = type_id
        self.type = Type.from_id(type_id)
        self.type_name = type_name or self.type.name
        self.system_id = system_id
        if self.system_id:
            self.system = System.from_id(self.system_id)
            self.system_name = self.system.name
            self.constellation_name = self.system.constellation.name
            self.region_name = self.system.constellation.region.name
        self.fuel = fuel
        self.fuel_expires = None
        if fuel_expires:
            # convert to datetime if not already
            if type(fuel_expires) == str:
                self.fuel_expires = datetime.datetime.fromisoformat(fuel_expires)
        self.accessible = accessible
        self.name = name
        self.state = state
        self.state_timer_end = None
        if state_timer_end:
            # convert to datetime if not already
            if type(state_timer_end) == str:
                self.state_timer_end = datetime.datetime.fromisoformat(state_timer_end)
        self.detonation = None
        if detonation:
            # convert to datetime if not already
            if type(detonation) == str:
                self.detonation = datetime.datetime.fromisoformat(detonation)
        self.unanchors_at = None
        if unanchors_at:
            # convert to datetime if not already
            if type(unanchors_at) == str:
                self.unanchors_at = datetime.datetime.fromisoformat(unanchors_at)
        self.profile_id = profile_id
        self.fitting = fitting
        self._fuel_rate = 0
        structure_response, structure_info = ncr.get_universe_structures_structure_id(structure_id=structure_id)

        if structure_response.status_code == 200:
            self.name = structure_info['name']
            self.system_id = structure_info['solar_system_id']
            self.type_id = structure_info['type_id']
            self.accessible = True
        elif structure_response.status_code == 403:
            self.name = "Inaccessible Structure"
            self.accessible = False
        self.online_services = []
        self.offline_services = []
        if services:
            for service in services:
                if service['state'] == 'online':
                    self.online_services.append(service['name'])
                if service['state'] == 'offline':
                    self.offline_services.append(service['name'])

        logger.debug("Class init", extra={**self.__dict__})

    @property
    def packaged_volume(self):
        return self.type.packaged_volume + self.fitting.packaged_volume

    @property
    def fuel_rate(self):
        if self._fuel_rate:
            return self._fuel_rate
        if not self.fitting:
            return self._fuel_rate
        fuel_bonus = {
            # Engineering Complex
            1404: {
                # Structure Engineering Service Module
                1415: 0.75
            },
            # Refinery
            1406: {
                # Structure Resource Processing Service Module
                1322: 0.80
            },
            # Citadel
            1657: {
                # Structure Citadel Service Module
                1321: 0.75
            },
        }
        for service in self.fitting.ServiceSlot:
            hourly_fuel = [a['value'] for a in service.dogma_attributes
                           if a['attribute_id'] == 2109][0]
            try:
                if service.group_id in fuel_bonus[self.type.group_id]:
                    modifier = fuel_bonus[self.type.group_id][service.group_id]
                else:
                    modifier = 1.0
            except KeyError:
                modifier = 1.0
            self._fuel_rate += hourly_fuel * modifier
        return self._fuel_rate

    @property
    def needs_detonation(self):
        for service in self.online_services:
            if service == 'Moon Drilling' and not self.detonation:
                return True
        return False

    @property
    def detonates_soon(self):
        now = datetime.datetime.now(datetime.UTC)
        if self.detonation and (self.detonation - now < CONFIG['DETONATION_WARNING']):
            return True
        return False

    @property
    def needs_ozone(self):
        if self.type_name == 'Ansiblex Jump Gate' and self.jump_fuel < CONFIG['JUMPGATE_FUEL_WARN']:
            return True
        return False

    @property
    def needs_fuel(self):
        now = datetime.datetime.now(datetime.UTC)
        if self.fuel_expires and (self.fuel_expires - now < CONFIG['TOO_SOON']):
            if self.unanchoring and self.unanchors_at < self.fuel_expires:
                return False
            return True
        return False

    @property
    def jump_fuel(self):
        return sum([lo.quantity for lo in self.fuel if lo.name == 'Liquid Ozone'])

    @property
    def reinforced(self):
        if self.state in ['armor_reinforce', 'hull_reinforce']:
            return True
        return False

    @property
    def vulnerable(self):
        if self.state in ['deploy_vulnerable', 'armor_vulnerable', 'hull_vulnerable']:
            return True
        return False

    @property
    def has_core(self):
        if self.fitting.QuantumCoreRoom:
            return True
        return False

    @property
    def needs_core(self):
        if self.type.group.name.startswith('Upwell') or self.has_core:
            return False
        return True

    @property
    def unanchoring(self):
        if self.unanchors_at:
            return True
        return False

    @classmethod
    def from_corporation(cls, corporation_name, assets=None):
        structure_list = []
        corporation_id = name_to_id(corporation_name, 'corporation')

        try:
            assets = assets or Asset.from_entity_id(corporation_id, 'corporations')
        except Exception as e:
            logger.critical("Error reading assets: {}".format(e))

        """ Old code:
        endpoint = 'get_corporation_corporation_id_mining_extractions'
        detonations_request = esi_auth.op[endpoint](corporation_id=corporation_id, datasource=esi_datasource)
        detonations_response = esi_client.request(detonations_request)
        if detonations_response.status != 200:
            raise HTTPError(detonations_response.raw)
        detonations = detonations_response.data
        """
        structures_response, structures = ncr.get_corporations_corporation_id_structures(corporation_id=corporation_id)
        detonations_response, detonations = ncr.get_corporation_corporation_id_mining_extractions(
            corporation_id=corporation_id)

        if detonations_response.status_code != 200:
            raise HTTPError(detonations_response.raw)

        # New Code End
        detonations = {d['structure_id']: d['chunk_arrival_time']
                       for d in detonations}
        structure_keys = ['structure_id', 'corporation_id', 'system_id', 'type_id',
                          'services', 'fuel_expires', 'state', 'state_timer_end',
                          'unanchors_at', 'profile_id']
        for s in structures:
            sid = s['structure_id']
            kwargs = {k: v for k, v in s.items() if k in structure_keys}
            # Old Code: kwargs['type_name'] = ids_to_names([s['type_id']])[s['type_id']]
            kwargs['type_name'] = ids_to_names([s['type_id']])[s['type_id']]
            kwargs['detonation'] = detonations.get(sid)

            structure_contents = None
            if assets:
                structure_contents = [a for a in assets if a.location_id == sid]
            if structure_contents:
                kwargs['fitting'] = Fitting.from_assets(structure_contents)
                kwargs['fuel'] = [a for a in structure_contents if a.location_flag == 'StructureFuel']

            structure_list.append(cls(**kwargs))
        return structure_list

    def __str__(self):
        return '{} ({}) - {}'.format(self.name, self.structure_id, self.type_name)
