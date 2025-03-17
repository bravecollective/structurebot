#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
import logging
import argparse
import csv
import sys

from structurebot.citadels import Structure
from structurebot.config import CONFIG
from structurebot.logger import setup_logger


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--csv', help='Print CSV output',
                        action='store_true')
    parser.add_argument('-d', '--debug', help='Print debug output',
                        action='store_true')
    args = parser.parse_args()

    level = logging.WARNING
    if CONFIG['DEBUG'] or args.debug:
        level = logging.INFO

    setup_logger(level=level)

    pyswagger_logger = logging.getLogger('pyswagger')
    pyswagger_logger.setLevel(logging.ERROR)
    structures = Structure.from_corporation(CONFIG['CORPORATION_NAME'])
    total_fuel = 0
    writer = csv.writer(sys.stdout)
    columns = []
    if args.csv:
        columns = [
            'structure_id',
            'type_name',
            'name',
            'state',
            'state_timer_end',
            'unanchoring',
            'fuel_expires',
            'fuel_rate',
            'needs_fuel',
            'jump_fuel',
            'needs_core',
            'profile_id',
            'packaged_volume',
            'system_name',
            'constellation_name',
            'region_name'
        ]
        writer.writerow(columns)
    for structure in sorted(structures, key=lambda x: x.name):
        if args.csv:
            writer.writerow([getattr(structure, c) for c in columns])
        else:
            print(structure)
            print('Fuel/Cycle: {}'.format(structure.fuel_rate))
            print(structure.fitting)
            print('-----')
            total_fuel += structure.fuel_rate
    if not args.csv:
        print('Total fuel/cycle: {}'.format(total_fuel))
