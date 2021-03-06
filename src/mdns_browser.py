#!/etc/ConsolePi/venv/bin/python3

""" Browse for other ConsolePis on the network """

import socket
import time
from typing import cast
import json
from threading import Thread
import sys
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from consolepi.common import check_reachable
from consolepi.common import ConsolePi_data
try:
    import better_exceptions # pylint: disable=import-error
except Exception:
    pass

HOSTNAME = socket.gethostname()

class MDNS_Browser:

    def __init__(self, log=None, show=False):
        self.config = ConsolePi_data(do_print=False)
        self.show = show
        self.log = log if log is not None else self.config.log
        self.stop = False
        self.zc = self.run()
        self.update = self.config.update_local_cloud_file
        self.if_ips = self.config.interfaces
        self.ip_list = []
        for _iface in self.if_ips:
            self.ip_list.append(self.if_ips[_iface]['ip'])
        self.discovered = []

    def on_service_state_change(self,
        zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        mdns_data = None
        config = self.config
        ip_list = config.get_ip_list()
        log = self.log
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                if info.server.split('.')[0] != config.hostname:
                    log.info('[MDNS DSCVRY] {} Discovered via mdns'.format(info.server.split('.')[0]))
                    if info.properties:
                        properties = info.properties
                        # -- DEBUG --
                        properties_decode = {}
                        for key in properties:
                            key_dec = key.decode("utf-8")                          
                            properties_decode[key_dec] = properties[key].decode("utf-8")
                        log_out = json.dumps(properties_decode, indent=4, sort_keys=True)
                        log.debug('[MDNS DSCVRY] {} Properties Discovered via mdns:\n{}'.format(
                            info.server.split('.')[0], log_out))
                        # -- /DEBUG --
                        hostname = properties[b'hostname'].decode("utf-8")
                        user = properties[b'user'].decode("utf-8")
                        interfaces = json.loads(properties[b'interfaces'].decode("utf-8"))
                        rem_ip = None
                        for _iface in interfaces:
                            _ip = interfaces[_iface]['ip']
                            if _ip not in ip_list:
                                if check_reachable(_ip, 22):
                                    rem_ip = _ip
                                    break
                        try:
                            if isinstance(properties[b'adapters'], bytes):
                                adapters = json.loads(properties[b'adapters'].decode("utf-8"))
                            else:
                                adapters = config.get_adapters_via_api(rem_ip) if rem_ip is not None else 'API'
                        except KeyError:
                            log.info('[MDNS DSCVRY] {} provided no adapter data Collecting via API'.format(info.server.split('.')[0]))
                            adapters = config.get_adapters_via_api(rem_ip) if rem_ip is not None else 'API'
                            
                        mdns_data = {hostname: {'interfaces': interfaces, 'adapters': adapters, 'user': user, 'rem_ip': rem_ip, 'source': 'mdns', 'upd_time': int(time.time())}}
                        if self.show:
                            self.discovered.append(hostname)
                            print(hostname + ' Discovered via mdns:')
                            print(json.dumps(mdns_data, indent=4, sort_keys=True))
                            print('Discovered ConsolePis: {}'.format(self.discovered))
                            print("\npress Ctrl-C to exit...\n")

                        log.debug('[MDNS DSCVRY] {} Final data set:\n{}'.format(info.server.split('.')[0], json.dumps(mdns_data, indent=4, sort_keys=True)))
                        self.update(remote_consoles=mdns_data)
                        log.info('[MDNS DSCVRY] {} Local Cache Updated after mdns discovery'.format(info.server.split('.')[0]))
                    else:
                        log.warning('[MDNS DSCVRY] {}: No properties found'.format(info.server.split('.')[0]))
            else:
                log.warning('[MDNS DSCVRY] {}: No info found'.format(info))


    def run(self):
        log = self.log
        zeroconf = Zeroconf()
        log.info("[MDNS DSCRY] Discovering ConsolePis via mdns")
        browser = ServiceBrowser(zeroconf, "_consolepi._tcp.local.", handlers=[self.on_service_state_change])  # pylint: disable=unused-variable
        return zeroconf

if __name__ == '__main__':
    if len(sys.argv) > 1:
        mdns = MDNS_Browser(show=True)
        print("\nBrowsing services, press Ctrl-C to exit...\n")
    else:
        mdns = MDNS_Browser()
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        mdns.zc.close()

