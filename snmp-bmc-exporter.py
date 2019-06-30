#!/usr/bin/env python3
from pysnmp.hlapi import *
from pprint import pprint
from flask import Flask
from flask import request
import time
import re

def get_bulk(device, community_string, objid, masklength):
    obj_list = []
    for (errorIndication, errorStatus, errorIndex, varBinds) in bulkCmd(
        SnmpEngine(), CommunityData(community_string), 
        UdpTransportTarget((device, 161)), ContextData(), 
        0, 25, ObjectType(objid), lexicographicMode=False
        ):
        if errorIndication:
            print(errorIndication)
            return
        elif errorStatus:
            print('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
            return
        else:

            obj_list.append(list(map(lambda varBind: ['.'.join(str(varBind[0].getOid()).split('.')[masklength:]),
                                                      str(varBind[1])], varBinds)))
    return obj_list


def get_one(device, community_string, objid, masklength):
    errorIndication, errorStatus, errorIndex, varBinds = next(getCmd(SnmpEngine(),
                              CommunityData(community_string),
                              UdpTransportTarget((device, 161)),
                              ContextData(),
                              ObjectType(objid),
                              lexicographicMode=False))

    if errorIndication:
        print(errorIndication)
        return
    elif errorStatus:
        print('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        return
    else:
        obj = list(map(lambda varBind: ['.'.join(str(varBind[0].getOid()).split('.')[masklength:]),
                                                      str(varBind[1])], varBinds))
    return obj


class SNMPDevice(object):
    def __init__(self, **kwargs):
        self.host = kwargs['host']
        self.proto = kwargs.get('proto', 'snmpv2')
        self.username = kwargs.get('username', '')
        self.secret = kwargs['secret']
        self.sensors_mibs = [{'index_mib' : '', 'reading_mib': ''}]
        self.sensors = {}

class SNMPQct(SNMPDevice):
    def __init__(self, **kwargs):
        SNMPDevice.__init__(self, **kwargs)
        self.sensors_mibs = [
            {
            'index_mib': '.1.3.6.1.4.1.7244.1.2.1.3.4.1.3.',
            'reading_mib': '.1.3.6.1.4.1.7244.1.2.1.3.4.1.4.'
            },
            {
            'index_mib': '.1.3.6.1.4.1.7244.1.2.1.3.3.1.3.',
            'reading_mib': '.1.3.6.1.4.1.7244.1.2.1.3.3.1.4.'
            }
            ]
        

    def get_sensors(self):
        sensors = []
        for mibs in self.sensors_mibs:
            # getting list of sensors values with and map it to dict with mib last octet as a key 
            sensors_readings = dict(map(lambda x: (x[0][0], x[0][1]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['reading_mib']),14)))
            # getting index of sensors and map to dict sensors name as a key 
            # and sensor values from previous sensors_readings dict   
            sensors += list(map(lambda x: (x[0][1].strip().replace(' ','_'), sensors_readings[x[0][0]]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['index_mib']),14)))
        self.sensors = dict(sensors)

class SNMPSupermicro(SNMPDevice):
    def __init__(self, **kwargs):
        SNMPDevice.__init__(self, **kwargs)
        self.sensors_mibs = [{
            'index_mib': '.1.3.6.1.4.1.21317.1.3.1.13.',
            'reading_mib': '.1.3.6.1.4.1.21317.1.3.1.2.'
            }]

    def get_sensors(self):
        sensors = []
        for mibs in self.sensors_mibs:
            # getting list of sensors values with and map it to dict with mib last octet as a key 
            sensors_readings = dict(map(lambda x: (x[0][0], x[0][1]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['reading_mib']),11)))
            # getting index of sensors and map to dict sensors name as a key 
            # and sensor values from previous sensors_readings dict     
            sensors += list(map(lambda x: (x[0][1].strip().replace(' ','_'), sensors_readings[x[0][0]]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['index_mib']),11)))
            self.sensors = dict(sensors)
app = Flask(__name__)
@app.route('/metrics', methods=['GET', 'POST'])
def metrics_output():
#if __name__ == "__main__":

    startTime = time.time()
    devices = {
        'supermicro': SNMPSupermicro,
        'qct': SNMPQct
    }
    if request.method == 'POST':
        args = request.form
    else:
        args = request.args
    device = devices[args['type']](host=args['host'], secret=args['secret'])
    device.get_sensors()
    metrics = ['#']
    for sensor in device.sensors:
        vars = {
            'metric': re.sub('\x01|\.|-','_',sensor),
            'host': args['host'],
            'type': args['type'],
            'value': device.sensors[sensor]
        }
        metrics.append('snmp_{metric} {{host="{host}", type="{type}" }} {value}'.format(**vars))
    vars['value'] = time.time() - startTime
    metrics.append('snmp_scrape_duration {{host="{host}", type="{type}" }} {value}'.format(**vars))
    metrics.append('#')
    return '\n'.join(metrics)