from __future__ import absolute_import
from __future__ import print_function

import requests
from requests.exceptions import HTTPError

from .config import *
from .neucore_requester import NCR
from structurebot.logger import logger

datasource = CONFIG['NEUCORE_DATASOURCE'].split(':', 1)
datasource_id = datasource[0]
if len(datasource) > 1:
    datasource_name = datasource[1]
else:
    datasource_name = None

ncr = NCR(app_id=CONFIG['NEUCORE_APP_ID'],
          app_secret=CONFIG['NEUCORE_APP_SECRET'],
          neucore_prefix=CONFIG['NEUCORE_HOST'],
          datasource_id=datasource_id,
          datasource_name=datasource_name,
          useragent=CONFIG['USER_AGENT'],
          esi_prefix=CONFIG['ESI_HOST'],
          cache_esi=False,
          cache_nc=False)

############

cat_name_id = {}  # stores name:id pairs by category to save on requests
id_name_cat = {}  # stores (name,category) by ID to save on requests


def name_to_id(name, name_type):
    """Looks up a name of name_type in ESI

    Args:
        name (string): Name to search for
        name_type (string): types to search (see ESI for valid types)

    Returns:
        integer: eve ID or None if no match

    >>> name_to_id('Aunsou', 'solar_system')
    30003801
    >>> name_to_id('n0rman', 'character')
    1073945516
    >>> name_to_id('Nonexistent', 'solar_system')
    """

    logger.info("Lookup for name", extra={"name": name, "name_type": name_type})

    if name_type == 'corporation':
        category = 'corporations'
    elif name_type == 'inventory_type':
        category = 'inventory_types'
    elif name_type == 'solar_system':
        category = 'systems'
    elif name_type == 'character':
        category = 'characters'
    else:
        logger.info("No proper type provided, returning None")

        return None
    try:
        logger.info("Looking up data in cache", extra={"category": category, "name": name})

        return cat_name_id[category][name]
    except KeyError:
        # data not found in cache
        logger.info("Data not found in cache", extra={"category": category, "name": name})
        logger.debug("Category cache data", extra={"cache": cat_name_id})

        pass
    # try fetch ID
    try:
        names_to_ids([name])
    except HTTPError:
        return None
    try:
        return cat_name_id[category][name]
    except KeyError:
        # data not found after fetching
        logger.info("Data not found in cache on second run", extra={"category": category, "name": name})
        logger.debug("Category cache data", extra={"cache": cat_name_id})

        return None


def names_to_ids(lookup_names: list):
    """
    Resolve a set of names to IDs in the following categories:
        agents, alliances, characters, constellations, corporations,
        factions, inventory_types, regions, stations, and systems.
    Only exact matches will be returned. All names searched for are cached for 12 hours
    
    Args:
        lookup_names (list): a list of the names to look up

    Returns:
        dict: {'category':{'name':id}}
    """
    logger.info("Resolving names", extra={"names": lookup_names})

    names = []
    r_val_cat_name_id = {}  # {'category':{'name':id}}

    for n in lookup_names:
        found = False
        for c in cat_name_id.keys():
            if n in cat_name_id[c].keys():
                found = True
                if c in r_val_cat_name_id.keys():
                    r_val_cat_name_id[c][n] = cat_name_id[c][n]
                else:
                    r_val_cat_name_id[c] = {n: cat_name_id[c][n]}
        if not found:
            names.append(n)

    if len(names) > 0:
        chunk_size = 400  # Max Items is 500
        for chunk in [names[i:i + chunk_size] for i in range(0, len(names), chunk_size)]:
            resp, chunk_data = ncr.post_universe_ids(ids=chunk)
            if resp.status_code == 200:
                for c in chunk_data.keys():
                    if c not in cat_name_id.keys():
                        cat_name_id[c] = {}
                    for entry in chunk_data[c]:
                        n = entry['name']
                        entry_id = entry['id']
                        cat_name_id[c][n] = entry_id
                        id_name_cat[entry_id] = (n, c)
                        if c in r_val_cat_name_id.keys():
                            r_val_cat_name_id[c][n] = cat_name_id[c][n]
                        else:
                            r_val_cat_name_id[c] = {n: cat_name_id[c][n]}
                        r_val_cat_name_id[entry['name']] = entry['id']

    logger.info("Resolving completed", extra={"data": r_val_cat_name_id})

    return r_val_cat_name_id


def ids_to_names(lookup_ids):
    """Looks up names from a list of ids

    Args:
        lookup_ids (list of integers): list of ids to resolve to names

    Returns:
        dict: dict of id to name mappings

    >>> ids_to_names([1073945516, 30003801])
    {30003801: 'Aunsou', 1073945516: 'n0rman'}
    >>> ids_to_names([1])
    Traceback (most recent call last):
    ...
    requests.exceptions.HTTPError: Ensure all IDs are valid before resolving.
    """
    logger.info("Looking up ids", extra={"lookup": lookup_ids})

    ids = []
    id_name = {}
    for i in lookup_ids:
        try:
            id_name[i] = id_name_cat[i][0]
        except KeyError:
            ids.append(i)
    if len(ids) > 0:
        chunk_size = 400  # max is 500
        for chunk in [ids[i:i + chunk_size] for i in range(0, len(ids), chunk_size)]:
            resp, chunk_data = ncr.post_universe_names(names=chunk)
            if resp.status_code == 200:
                for d in chunk_data:
                    d_id = d["id"]
                    d_cat = d["category"]
                    d_name = d["name"]
                    id_name_cat[d_id] = (d_name, d_cat)
                    if d_cat not in cat_name_id.keys():
                        cat_name_id[d_cat] = {}
                    cat_name_id[d_cat][d_name] = d_id
                    id_name[d_id] = d_name

    logger.info("Lookup finished", extra={"returned": dict(sorted(id_name.items()))})

    return dict(sorted(id_name.items()))


############


def notify_slack(messages):
    params = {
        'text': '\n\n'.join(messages)
    }
    results = requests.post(CONFIG['OUTBOUND_WEBHOOK'], json=params)
    results.raise_for_status()
    # print(params)
