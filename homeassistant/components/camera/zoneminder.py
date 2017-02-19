"""
Support for ZoneMinder Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.zoneminder/
"""
import asyncio
import logging
import time
from contextlib import closing
from hashlib import md5 # TODO: new requirement?

import aiohttp
import async_timeout
import requests
import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_AUTHENTICATION)
from homeassistant.components.camera.mjpeg import (CONF_MJPEG_URL, MjpegCamera)
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_stream) # TODO: remove unused
from homeassistant.helpers import config_validation as cv
import homeassistant.components.zoneminder as zoneminder
# from homeassistant.components.zoneminder import ZM

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE = 'include' # TODO: use shared const

DEPENDENCIES = ['zoneminder']
DOMAIN = 'zoneminder'

#PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#    vol.Optional(CONF_INCLUDE): cv.string, # TODO
#})

# TODO: don't hard-code cgi-bin path

#@asyncio.coroutine
# pylint: disable=unused-argument
# TODO: async_ issues due to ZM platform not async?
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a ZoneMinder IP Camera."""
    monitors = zoneminder.get_state('api/monitors.json') # TODO: I/O
    for i in monitors['monitors']:
        print(i['Monitor'])
        #yield from
        add_devices([ZoneMinderCamera(hass, config, i['Monitor'])], True)


class ZoneMinderCamera(MjpegCamera):
    """An implementation of a ZoneMinder camera using the still and mjpeg APIs"""

    def __init__(self, hass, device_info, monitor):
        """Initialize a ZoneMinder camera."""
        print(type(device_info))
        device_info[CONF_MJPEG_URL] = None # TODO
        super().__init__(hass, device_info)
        self._name = monitor['Name']
        self._monitor_id = int(monitor['Id'])
        _LOGGER.debug("Initializing camera {:d}".format(self._monitor_id))
        self.zm = hass.data[DOMAIN]
        print(self._calculate_auth_hash())
        print(self._zm_image_url("jpeg"))

    # TODO: move this method to platform comp.
    def _calculate_auth_hash(self):
        """ https://github.com/ZoneMinder/ZoneMinder/blob/67b5444a9841cecc9bfb182ae884b4af4c95f353/web/includes/functions.php#L145 """
        ZM = self.zm
        #print(ZM)
        if not ZM['auth_hash_secret']: #TODO: use const # TODO: support password without hash?
            _LOGGER.info('No "auth_hash_secret" specified so assuming AUTH_RELAY is "none"')
            return None
        localtime = time.localtime()
        remote_address = ''
        password_hash = md5(ZM['password'].encode()).hexdigest() # TODO: handle no auth
        print(password_hash)
        auth_key = '{ZM[auth_hash_secret]}{ZM[username]}{password_hash}{remote_address}{time.tm_hour}{time.tm_mday}{tm_mon}{tm_year}'.format(
            ZM=ZM, password_hash=password_hash, remote_address=remote_address,
            time=localtime, tm_mon=localtime.tm_mon - 1, tm_year=localtime.tm_year - 1900)
        print(auth_key)
        return md5(auth_key.encode()).hexdigest()

    def _zm_image_url(self, mode):
        _LOGGER.debug("_zm_image_url {:d} {:s}".format(self._monitor_id, mode), stack_info=False)
        ZM = self.zm
        return "{ZM[url]}cgi-bin/nph-zms?mode={mode}&scale=100&buffer={buffer}&monitor={monitor}&user={ZM[username]}&pass={ZM[password]}".format(
            mode=mode, ZM=ZM, buffer=1000, monitor=self._monitor_id)

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        # TODO
        return False

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    def update(self):
        self._still_image_url = self._zm_image_url("single")
        self._mjpeg_url = self._zm_image_url("jpeg")
