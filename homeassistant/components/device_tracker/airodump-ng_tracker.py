"""
Support for scanning for wireless devices using airodump-ng

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.airodump-ng_tracker/
"""
import logging
import os
import re
import subprocess
from collections import namedtuple # TODO: cleanup
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util as util
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import CONF_HOSTS
from homeassistant.helpers.event import track_point_in_utc_time

_LOGGER = logging.getLogger(__name__)

AIRODUMP_CSV_SUFFIX = '-01.csv'

CONF_EXCLUDE = 'exclude'
CONF_INTERFACE = 'interface'
CONF_SCAN_DURATION = 'scan_duration'

DEFAULT_INTERFACE = 'mon0'
DEFAULT_SCAN_DURATION = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
    vol.Optional(CONF_SCAN_DURATION, default=DEFAULT_SCAN_DURATION):
        cv.positive_int,
    vol.Optional(CONF_EXCLUDE, default=[]):
        vol.All(cv.ensure_list, vol.Length(min=1)),
})

# TODO: handle Apple MAC randomization (with local bit checking?)

def setup_scanner(hass, config, see):
    """Setup the airodump-ng scanner."""
    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)
    scan_duration = util.convert(config.get(CONF_SCAN_DURATION), int,
                                 DEFAULT_SCAN_DURATION)
    interface = config.get(CONF_INTERFACE)
    
    def discover_wifi_devices(now):
        import tempfile

        with tempfile.TemporaryDirectory(prefix=__name__) as tempdir:
            file_prefix = os.path.join(tempdir, 'capture')

            _LOGGER.info("Capturing for %d seconds on %s", scan_duration,
                         interface)

            try:
                airodump = subprocess.call(['airodump-ng',
                                            '--band', 'abg',
                                            '--output-format', 'csv',
                                            '--write', file_prefix,
                                            interface],
                                           timeout=scan_duration,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL,
                                           stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                pass

            with open(file_prefix + AIRODUMP_CSV_SUFFIX) as csv_file:
                see_discovered_devices_in_file(csv_file, see)
            
        # TODO: handle interval < duration
        next_update = now + timedelta(seconds=interval)
        _LOGGER.info("Scheduling next update at %s (after %d seconds)",
                      next_update, interval)
        track_point_in_utc_time(hass, discover_wifi_devices, next_update)
    
    discover_wifi_devices(dt_util.utcnow())

    return True


def see_discovered_devices_in_file(csv_file, see):
    lines = csv_file.readlines()
    station_lines = None

    # Find the start of the station section so we can skip everything
    # before it.
    for i, line in enumerate(lines):
        if line.startswith('Station MAC,'):
            station_lines = lines[i:]
            break

    import csv
    station_reader = csv.DictReader(station_lines,
                                    skipinitialspace=True)
    for row in station_reader:
        _LOGGER.debug('Found %s last seen at %s', row['Station MAC'],
                      row['Last time seen'])
        see(mac=row['Station MAC'])
