
import toml
from base import *
from gobgp import GoBGPTarget


class freertr(Container):
    CONTAINER_NAME = None
    GUEST_DIR = '/root'

    def __init__(self, host_dir, conf, image='bgperf/freertr'):
        super(freertr, self).__init__(self.CONTAINER_NAME, image, host_dir, self.GUEST_DIR, conf)

    @classmethod
    def build_image(cls, force=False, tag='bgperf/freertr', checkout='', nocache=False):

        cls.dockerfile = '''
FROM debian:latest
WORKDIR /
RUN apt-get update
RUN apt-get -y install iproute2 net-tools default-jdk-headless git zip telnet curl > /dev/null
RUN git clone https://github.com/mc36/freeRtr
WORKDIR freeRtr/src
RUN ./c.sh
'''.format(checkout)
        super(freertr, cls).build_image(force, tag, nocache)


class freertrTarget(freertr, Target):
    CONTAINER_NAME = 'bgperf_freertr_target'
    CONFIG_FILE_NAME = 'rtr-sw.txt'

    def write_config(self):
        neighbors = list(flatten(list(t.get('neighbors', {}).values()) for t in self.scenario_global_conf['testers'])) + [self.scenario_global_conf['monitor']]

        with open('{0}/{1}'.format(self.host_dir, self.CONFIG_FILE_NAME), 'w') as f:

            f.write("""
hostname freertr
logging file debug /root/zzz.log
vrf definition test
 exit
server http web
 host * path /root/
 host * api exec
 vrf test
 exit
server telnet tel
 security protocol telnet
 vrf test
 exit
interface loopback0
 vrf for test
 ipv4 address {1} /0
 exit
router bgp4 1
 vrf test
 router-id {1}
 local-as {0}
 distance 255 255 255
 no safe-ebgp
""".format(self.conf['as'], self.conf['router-id']))

            for n in neighbors:
                f.write("""
 neighbor {0} remote-as {1}
 neighbor {0} connection-mode passive
 neighbor {0} allow-as-out
""".format(n['local-address'], n['as']))

            f.write("""
exit
""")

        with open('{0}/rtr-hw.txt'.format(self.host_dir), 'w') as f:
            f.write("""
tcp2vrf 179 test 179
tcp2vrf 23 test 23
tcp2vrf 80 test 80
""")

    def get_startup_cmd(self):
        return '\n'.join(
            ['#!/bin/bash',
             'cd /root/',
             'java -Xmx4096m -jar /freeRtr/src/rtr.jar routerc /root/rtr-']
        ).format(
            guest_dir=self.guest_dir,
            config_file_name=self.CONFIG_FILE_NAME,
            debug_level='info')

    def get_version_cmd(self):
        return "java -jar /freeRtr/src/rtr.jar show version number"

    def exec_version_cmd(self):
        version = self.get_version_cmd()
        i= dckr.exec_create(container=self.name, cmd=version, stderr=False)
        return dckr.exec_start(i['Id'], stream=False, detach=False).decode('utf-8').strip()

    def get_neighbors_state(self):
        result = {}
        output = self.local("curl 127.0.0.1/.api./exec/show+ipv4+bgp+1+summary").splitlines()
        for i in range(2,len(output)-1):
            line = output[i].decode('ascii').split(";")
            result[line[0]] = int(line[3])
        return result, result
