#!/etc/ConsolePi/venv/bin/python3

""" 
    -- dev testing file currently --
    This file currently only logs
    Eventually this file may be used for ztp trigger or oobm switch discovery for the menu

"""

from consolepi.common import check_reachable
import sys
import os
import json
import requests
from consolepi.common import ConsolePi_Log
# from consolepi.common import get_local

# -- Some Testing Stuff --
# with open('/home/pi/dhcp-test.out', 'a') as new_file:
#     new_file.write(str(sys.argv[1:]) + '\n' + str(os.environ) + '\n')

# -- Some Testing Stuff - eventually move to ztp.conf or oobm.conf file --
match = ['2530', '3810']

cpi_log = ConsolePi_Log()
log = cpi_log.log

add_del = sys.argv[1]
mac = sys.argv[2]
ip = sys.argv[3]

try:
    iface = os.environ['DNSMASQ_INTERFACE']
except KeyError:
    iface = None
try:
    vendor = os.environ['DNSMASQ_VENDOR_CLASS']
except KeyError:
    vendor = None

log.info('DHCP Client Connected ({}): iface: {}, mac: {}, ip: {}, vendor: {}'.format(add_del, iface, mac, ip, vendor))

if vendor is not None and 'ConsolePi' in vendor:
    log.info('ConsolePi Discovered via DHCP')
    url = 'http://{}:5000/api/v1.0/details'.format(ip)

    headers = {
        'User-Agent': 'ConsolePi/version',
        'Accept': '*/*',
        'Cache-Control': 'no-cache',
        'Host': '{}:5000'.format(ip),
        'accept-encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'cache-control': 'no-cache'
    }

    response = requests.request("GET", url, headers=headers)
    log.info('Response from {}[{}]: \n{}'.format(ip, response.status_code, response.text))

    # TODO get/post info from/to ConsolePi that just connected via API
    # Update local cloud cache
# oobm Discovery & ZTP trigger
elif vendor is not None and iface is not None and iface == 'eth0':
    for _ in match:
        if _ in vendor:
            if check_reachable(ip, 22):
                log.info('{} is reachable via ssh @ {}'.format(_, ip))
            elif check_reachable(ip, 23):
                log.info('{} is reachable via telnet @ {}'.format(_, ip))
    # TODO add connection to reachable ssh/telnet on eth if oobm is enabled in config
    # TODO add option to ztp via jinja2 templates (longer term goal)

