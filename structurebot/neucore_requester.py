import base64
import json
import requests
import logging
from urllib.parse import urlencode
from structurebot.logger import logger

nc_cache_get = {}
esi_cache_get = {}


def try_nc_cache_get(neucore_prefix: str, params: dict):
    key = tuple(params.items())
    if key in nc_cache_get.keys():
        return nc_cache_get[key]
    return None


def store_nc_cache_get(neucore_prefix: str, params: dict, resp):
    key = tuple(params.items())
    nc_cache_get[key] = resp

    logger.info("Response cached")
    logger.debug("Cached content", extra={"key": key, "response": resp})


def try_esi_cache_get(esiurl: str, params: dict):
    key = (esiurl, tuple(params.items()))
    if key in esi_cache_get.keys():
        return esi_cache_get[key]
    return None


def store_esi_cache_get(esiurl: str, params: dict, resp):
    key = (esiurl, tuple(params.items()))
    esi_cache_get[key] = resp

    logger.info("Response cached")
    logger.debug("Cached content", extra={"key": key, "response": resp})


class NCR:
    def __init__(self, app_id: str, app_secret: str, datasource_id: str, datasource_name: str, neucore_prefix: str,
                 useragent: str = None, esi_prefix: str = "https://esi.evetech.net", esi_version: str = "/latest",
                 cache_nc=True, cache_esi=True) -> None:
        self.app_id = str(app_id)
        self.app_secret = str(app_secret)
        self.neucore_prefix = str(neucore_prefix)
        self.esi_prefix = str(esi_prefix)
        self.useragent = str(useragent)
        self.cache_nc = cache_nc
        self.cache_esi = cache_esi
        self.esi_version = esi_version

        self.nc_session = requests.Session()
        self.esi_session = requests.Session()
        # self.nc_session.auth = (self.app_id,self.app_secret)
        b = base64.b64encode(bytes("{}:{}".format(app_id, app_secret).encode()))
        auth = "Bearer {}".format(b.decode())
        # print(type(auth),auth)
        self.nc_session.headers.update({'Authorization': auth})
        self.nc_session.headers.update({'Neucore-EveCharacter': str(datasource_id)})
        if datasource_name: self.nc_session.headers.update({'Neucore-EveLogin': str(datasource_name)})
        if useragent:
            self.nc_session.headers.update({'User-Agent': useragent})
            self.esi_session.headers.update({'User-Agent': useragent})

        logger.debug("Class init", extra={**self.__dict__})

    def nc_get(self, endpoint: str, page: int = None, query: dict = {}):
        """routes an ESI-GET through Neucore

        used for protected data

        Args:
            endpoint (str): the desired ESI endpoint
            page (int, optional): returns only the specified page. If None concats all pages into the initial request.
                                  Defaults to None.

        Returns:
            requests.Response : the requests response
            data : the json decoded response content
        """

        # TODO add caching here
        # TODO add page-handling
        query_params = query.copy()

        url = self.neucore_prefix
        if page:
            query_params['page'] = page

        if query_params:
            params = {'esi-path-query': self.esi_version + endpoint + "?" + urlencode(query_params)}
        else:
            params = {'esi-path-query': self.esi_version + endpoint}

        logger.info("Request parameters", extra={"query": params})

        resp = None  # try_nc_cache_get(url, params=params)
        if not resp:

            resp = self.nc_session.get(url, params=params)

            if resp.status_code != 200:
                logger.critical("Request not processed", extra={"status_code": resp.status_code})

            logger.info("Response",
                        extra={"method": resp.request.method,
                               "url": resp.url,
                               "status_code": resp.status_code,
                               "duration": resp.elapsed.total_seconds()})
            logger.debug("Response data", extra={"data": resp.json()})

            if resp.status_code == 200 and self.cache_nc:
                logger.info("Caching response", extra={"cacheFlag": self.cache_nc})
                # cache resp
                store_nc_cache_get(url, params=params, resp=resp)

        resp_data = resp.json()

        if page:
            # only requested this page
            return resp, resp_data

        if 'X-Pages' in resp.headers.keys():
            page_max = int(resp.headers['X-Pages'])

            logger.info("Response contains multiple pages", extra={"pageNo": page_max})

            page = 2  # request page 2+ if possible
            while page <= page_max:
                page_resp, page_data = self.nc_get(endpoint=endpoint, page=page, query=query)
                page = page + 1

                if type(resp_data) == dict and type(page_data) == dict:
                    # update dictionaries
                    resp_data.update(page_data)
                elif type(resp_data) == list and type(page_data) == list:
                    # update dictionaries
                    resp_data += page_data
                else:
                    # we should only have lists and dicts
                    logger.error("Wrong response type",
                                 extra={"expected": f"{list} or {dict}", "received": type(resp_data)})

                    pass

        return resp, resp_data

    def esi_get(self, endpoint: str, page=None, query: dict = {}):
        """makes a GET request directly to the ESI

        Used for public data

        Args:
            endpoint (str): the desired ESI endpoint

        Returns:
            requests.Response : the requests response generated
        """
        # TODO add caching here
        # TODO add page-handling

        params = query.copy()
        if page:
            params['page'] = page

        logger.info("Request parameters", extra={"query": params})

        resp = None  # try_esi_cache_get(self.esi_prefix+endpoint,params=params)
        if not resp:
            resp = self.esi_session.get(self.esi_prefix + self.esi_version + endpoint, params=params)
            
            if resp.status_code != 200:
                logger.critical("Request not processed", extra={"status_code": resp.status_code})
                
            if resp.status_code == 200 and self.cache_esi:
                store_esi_cache_get(self.esi_prefix + endpoint, params=params, resp=resp)

        logger.info("Response",
                    extra={"method": resp.request.method,
                           "url": resp.url,
                           "status_code": resp.status_code,
                           "duration": resp.elapsed.total_seconds()})
        logger.debug("Response data", extra={"data": resp.json()})

        data = resp.json()

        if page:
            # only requested this page
            return resp, data

        if 'X-Pages' in resp.headers.keys():
            page_max = int(resp.headers['X-Pages'])
            logger.info("Response contains multiple pages", extra={"page_max": page_max})
            page = 2  # request page 2+ if possible
            while page <= page_max:
                page_resp, page_data = self.esi_get(endpoint=endpoint, page=page, query=query)
                page = page + 1

                if type(data) == dict and type(page_data) == dict:
                    # update dictionaries
                    data.update(page_data)
                elif type(data) == list and type(page_data) == list:
                    # update dictionaries
                    data += page_data
                else:
                    # we should only have lists and dicts
                    logger.error("Wrong response type",
                                 extra={"pageNo": page, "expected": f"{list} or {dict}", "received": type(data)})

                    pass
        return resp, data

    def nc_post(self, endpoint: str, data, page=None, query: dict = {}):
        """routes an ESI-POST through Neucore

        used for protected data

        Args:
            endpoint (str): the desired ESI endpoint

        Returns:
            requests.Response : the requests response generated
        """
        # TODO add caching here
        # TODO add page-handling
        query_params = query.copy()
        if page:
            query_params['page'] = page

        if query_params:
            params = {'esi-path-query': self.esi_version + endpoint + "?" + urlencode(query_params)}
        else:
            params = {'esi-path-query': self.esi_version + endpoint}

        logger.info("Request parameters", extra={"query": params})

        resp = self.nc_session.post(self.neucore_prefix, data=json.dumps(data), params=params)

        if resp.status_code != 200:
            logger.critical("Request not processed", extra={"status_code": resp.status_code})

        logger.info("Response",
                    extra={"method": resp.request.method,
                           "url": resp.url,
                           "status_code": resp.status_code,
                           "duration": resp.elapsed.total_seconds()})
        logger.debug("Response data", extra={"data": resp.json()})
        
        resp_data = resp.json()

        if page:
            # only requested this specific page
            return resp, resp_data

        # there are multiple pages of data. Get them all.
        if 'X-Pages' in resp.headers.keys():
            page_max = int(resp.headers['X-Pages'])
            logger.info("Response contains multiple pages", extra={"page_max": page_max})
            page = 2  # request page 2+ if possible
            while page <= page_max:

                page_resp, page_data = self.nc_post(endpoint=endpoint, data=data, page=page, query=query)
                page = page + 1

                if type(resp_data) == dict and type(page_data) == dict:
                    # update dictionaries
                    resp_data.update(page_data)
                elif type(resp_data) == list and type(page_data) == list:
                    # update lists
                    resp_data += page_data
                else:
                    # we should only have lists and dicts
                    logger.error("Wrong response type",
                                 extra={"expected": f"{list} or {dict}", "received": type(resp_data)})

                    pass
            return resp, resp_data

        # we have no pages.
        return resp, resp_data

    def esi_post(self, endpoint: str, data, page=None, query: dict = {}):
        """makes a POST request directly to the ESI

        used for protected data

        Args:
            endpoint (str): the desired ESI endpoint

        Returns:
            requests.Response : the requests response generated
        """
        # TODO add caching here
        # TODO add page-handling
        params = query.copy()

        if page:
            params['page'] = page
        if len(params) == 0:
            params = None

        logger.info("Request parameters", extra={"query": params})

        resp = self.esi_session.post(self.esi_prefix + self.esi_version + endpoint, data=json.dumps(data),
                                     params=params)

        if resp.status_code != 200:
            logger.critical("Request not processed", extra={"status_code": resp.status_code})

        logger.info("Response",
                    extra={"method": resp.request.method,
                           "url": resp.url,
                           "status_code": resp.status_code,
                           "duration": resp.elapsed.total_seconds()})
        logger.debug("Response data", extra={"data": resp.json()})

        resp_data = resp.json()

        if page:
            # only requested this page
            return resp, resp_data

        if 'X-Pages' in resp.headers.keys():
            page_max = int(resp.headers['X-Pages'])
            logger.info("Response contains multiple pages", extra={"page_max": page_max})
            page = 2  # request page 2+ if possible
            while page <= page_max:

                page_resp, page_data = self.esi_post(endpoint=endpoint, data=data, page=page, query=query)
                page = page + 1

                if type(resp_data) == dict and type(page_data) == dict:
                    # update dictionaries
                    resp_data.update(page_data)
                elif type(data) == list and type(page_data) == list:
                    # update dictionaries
                    resp_data += page_data
                else:
                    # we should only have lists and dicts
                    logger.error("Wrong response type",
                                 extra={"expected": f"{list} or {dict}", "received": type(resp_data)})

                    pass
        return resp, resp_data

    def get_universe_structures_structure_id(self, structure_id):
        endpoint = "/universe/structures/{structure_id}/".format(structure_id=structure_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_corporations_corporation_id_structures(self, corporation_id):
        endpoint = "/corporations/{corporation_id}/structures/".format(corporation_id=corporation_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_corporation_corporation_id_mining_extractions(self, corporation_id):
        endpoint = "/corporation/{corporation_id}/mining/extractions/".format(corporation_id=corporation_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})

        return response, data

    def get_corporations_corporation_id_starbases_starbase_id(self, corporation_id, starbase_id,
                                                              system_id):
        endpoint = "/corporations/{corporation_id}/starbases/{starbase_id}/".format(corporation_id=corporation_id,
                                                                                    starbase_id=starbase_id)
        response, data = self.nc_get(endpoint=endpoint, query={'system_id': system_id})
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_corporations_corporation_id_starbases(self, corporation_id):
        endpoint = "/corporations/{corporation_id}/starbases/".format(corporation_id=corporation_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_universe_systems_system_id(self, system_id):
        endpoint = "/universe/systems/{system_id}/".format(system_id=system_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_universe_moons_moon_id(self, moon_id):
        endpoint = "/universe/moons/{moon_id}/".format(moon_id=moon_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def post_corporations_corporation_id_assets_locations(self, corporation_id, asset_ids: list):
        endpoint = "/corporations/{corporation_id}/assets/locations/".format(corporation_id=corporation_id)
        response, data = self.nc_post(endpoint=endpoint, data=asset_ids)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_sovereignty_map(self):
        endpoint = "/sovereignty/map/"
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_corporations_corporation_id(self, corporation_id):
        endpoint = "/corporations/{corporation_id}/".format(corporation_id=corporation_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def post_universe_ids(self, ids: list):
        endpoint = "/universe/ids/"
        # note: contrary to my understanding of ESI, data should not be 'names':[items] but rather just [items]
        response, data = self.esi_post(endpoint=endpoint, data=ids)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def post_universe_names(self, names: list):
        endpoint = "/universe/names/"
        response, data = self.esi_post(endpoint=endpoint, data=names)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_universe_constellations_constellation_id(self, constellation_id):
        endpoint = "/universe/constellations/{constellation_id}/".format(constellation_id=constellation_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_universe_regions_region_id(self, region_id):
        endpoint = "/universe/regions/{region_id}/".format(region_id=region_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_universe_categories_category_id(self, category_id):
        endpoint = "/universe/categories/{category_id}/".format(category_id=category_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_universe_groups_group_id(self, group_id):
        endpoint = "/universe/groups/{group_id}/".format(group_id=group_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_universe_types_type_id(self, type_id):
        endpoint = "/universe/types/{type_id}/".format(type_id=type_id)
        response, data = self.esi_get(endpoint=endpoint)
        if not type(data) == dict:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": dict, "received": type(data)})
        return response, data

    def get_characters_character_id_assets(self, character_id):
        endpoint = "/characters/{character_id}/assets/".format(character_id=character_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data

    def get_corporations_corporation_id_assets(self, corporation_id):
        endpoint = "/corporations/{corporation_id}/assets/".format(corporation_id=corporation_id)
        response, data = self.nc_get(endpoint=endpoint)
        if not type(data) == list:
            logger.warning("Wrong data type",
                           extra={"endpoint": endpoint, "expected": list, "received": type(data)})
        return response, data


if __name__ == "__main__":
    app_id = ""
    app_secret = ""
    testing_character_id = "00000000"
    testing_datasource = ""
    testing_neucore_prefix = ""
    logging.basicConfig(level=logging.DEBUG)

    connection = NCR(app_id, app_secret, datasource_id=testing_character_id, datasource_name=testing_datasource,
                     neucore_prefix=testing_neucore_prefix)
    testing_corp_id = 00000000
    r, d = connection.get_corporations_corporation_id_assets(corporation_id=testing_corp_id)
    print(r.request.headers)
    print(r.request.url)
    print(d)
    print(r.status_code)
    import datetime

    datetime.datetime.fromisoformat("2023-12-24T12:00:00Z")
