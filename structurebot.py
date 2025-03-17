#!/usr/bin/env python

from __future__ import absolute_import
import logging
import argparse

from structurebot.config import CONFIG
from structurebot.util import notify_slack, name_to_id
from structurebot.citadels import Structure
from structurebot.assets import Asset
from structurebot.pos import check_pos
from structurebot.logger import setup_logger

parser = argparse.ArgumentParser()
parser.add_argument('--suppress-upcoming-detonations', dest='upcoming_detonations', action='store_false')
parser.add_argument('--suppress-unscheduled-detonations', dest='unscheduled_detonations', action='store_false')
parser.add_argument('--suppress-ansiblex-ozone', dest='ansiblex_ozone', action='store_false')
parser.add_argument('--suppress-fuel-warning', dest='fuel_warning', action='store_false')
parser.add_argument('--suppress-service-state', dest='service_state', action='store_false')
parser.add_argument('--suppress-structure-state', dest='structure_state', action='store_false')
parser.add_argument('--suppress-core-state', dest='core_state', action='store_false')
parser.add_argument('-d', '--debug', action='store_true')

args = parser.parse_args()
debug = CONFIG['DEBUG'] or args.debug

level = logging.WARNING
if debug:
    level = logging.INFO
setup_logger(level=level)


messages = []
errors = []
corp_name = CONFIG['CORPORATION_NAME']
try:
    CONFIG['CORP_ID'] = name_to_id(corp_name, 'corporation')

    assetsError = False
    assets = None
    try:
        assets = Asset.from_entity_name(corp_name)
    except Exception as e:
        assetsError = True
        errors.append(str(e))
        errors.append(":frogsiren:   *********************************************************   :frogsiren:")
        errors.append("    Failed to read assets, Ozone and Core checks will be skipped.    ")
        errors.append(":frogsiren:   *********************************************************   :frogsiren:")

    structures = Structure.from_corporation(corp_name, assets)
    for structure in structures:
        message = []
        if not structure.accessible:
            msg = 'Found an inaccessible citadel ({}) in {}'.format(structure.structure_id, structure.system_id)
            messages.append(msg)
            continue
        if args.unscheduled_detonations and structure.needs_detonation:
            message.append('Needs to have an extraction scheduled')
        if args.upcoming_detonations and structure.detonates_soon:
            message.append('Ready to detonate {}'.format(structure.detonation))
        if args.ansiblex_ozone and structure.needs_ozone and not assetsError:
            message.append('Low on Liquid Ozone: {}'.format(structure.jump_fuel))
        if args.fuel_warning and structure.needs_fuel:
            message.append('Runs out of fuel on {}'.format(structure.fuel_expires))
            if args.service_state:
                if structure.online_services:
                    message.append('Online Services: {}'.format(', '.join(structure.online_services)))
                if structure.offline_services:
                    message.append('Offline Services: {}'.format(', '.join(structure.offline_services)))
        if args.service_state and structure.offline_services:
            message.append('Offline services: {}'.format(', '.join(structure.offline_services)))
        if args.structure_state and (structure.vulnerable or structure.reinforced):
            state = structure.state.replace('_', ' ').title()
            message.append('{} until {}'.format(state, structure.state_timer_end))
        if args.core_state and structure.needs_core and not assetsError:
            message.append('No core installed')
        if message:
            messages.append(u'\n'.join([u'{}'.format(structure.name)] + message))
    messages += check_pos(corp_name, assets)
except Exception as e:
    if debug:
        raise
    else:
        messages = [str(e)]

if messages:
    messages = sorted(messages)
    messages.insert(0, 'Upcoming {} Structure Maintenance Tasks'.format(corp_name))
    messages = errors + messages
    notify_slack(messages)
