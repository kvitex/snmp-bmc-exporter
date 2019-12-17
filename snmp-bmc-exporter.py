#!/usr/bin/env python3
from pysnmp.hlapi import *
from copy import deepcopy
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
        self.sensor_snmp_mask = 0
        self.sensors = []
        self.metrics = []
        self.metric_templates = []
        self.metric_prefix = 'snmp_'
        self.metric_sub = '\x01|\.|-| '
        self.metric_repl = '_'
        return
    

    def get_sensors(self, **kwargs):
        self.sensors = []
        for mibs in self.sensors_mibs:
            # getting list of sensors values with and map it to dict with mib last octet as a key 
            sensors_readings = dict(map(lambda x: (x[0][0], x[0][1]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['reading_mib']), kwargs.get('mask', self.sensor_snmp_mask))))
            # getting index of sensors and map to dict sensors name as a key 
            # and sensor values from previous sensors_readings dict     
            self.sensors += list(map(lambda x: (x[0][1].strip(), sensors_readings[x[0][0]]),
                 get_bulk(self.host, self.secret, ObjectIdentity(mibs['index_mib']), kwargs.get('mask', self.sensor_snmp_mask))))
        return
            

    def sensors_to_metrics(self):
        self.metrics = []
        for sensor in self.sensors:
            #metric_string = '{prefix}{metric} {{}} {metric_value}'.format(
            #            prefix=self.metric_prefix,
            #            metric=re.sub(self.metric_sub, self.metric_repl,sensor[0]),
            #            metric_value=sensor[1]
            #            )    
            for template in self.metric_templates:
                if template['check_name'](sensor[0]) is not None:
                    metric_string = '{prefix}{metric} {{ {label}="{label_value}" }} {metric_value}'.format(
                        prefix=self.metric_prefix, 
                        metric=template['name'],
                        label=template['label'],
                        label_value=template['get_index'](sensor[0]),
                        metric_value=sensor[1]
                        )
                    self.metrics.append(metric_string)
        return
            

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
        self.sensor_snmp_mask = 14
        self.metric_templates = [
            {
                'check_name': lambda x: re.search('P(\d{1,3}) Temp', x),
                'get_index': lambda x: re.search('P(\d{1,3}) Temp', x)[1],
                'label': 'cpu_num',
                'name': 'cpu_temp'         
            },
            {
                'check_name': lambda x: re.search('GPU(\d{1,3}).*?TEMP', x),
                'get_index': lambda x: re.search('GPU(\d{1,3}).*?TEMP', x)[1],
                'label': 'gpu_num',
                'name': 'gpu_temp'         
            },
            {
                'check_name': lambda x: re.search('FAN_SYS(\d{1,3}_\d{1,3}).*', x),
                'get_index': lambda x: re.search('FAN_SYS(\d{1,3}_\d{1,3}).*', x)[1],
                'label': 'fan_num',
                'name': 'fan'         
            }
        ]
        return

class SNMPSupermicro(SNMPDevice):
    def __init__(self, **kwargs):
        SNMPDevice.__init__(self, **kwargs)
        self.sensors_mibs = [{
            'index_mib': '.1.3.6.1.4.1.21317.1.3.1.13.',
            'reading_mib': '.1.3.6.1.4.1.21317.1.3.1.2.'
            }]
        self.sensor_snmp_mask = 11
        self.metric_templates = [
            {
                'check_name': lambda x: re.search('CPU(\d{1,3}).*?Temp', x),
                'get_index': lambda x: re.search('CPU(\d{1,3}).*?Temp', x)[1],
                'label': 'cpu_num',
                'name': 'cpu_temp'         
            },
            {
                'check_name': lambda x: re.search('GPU(\d{1,3}).*?Temp', x),
                'get_index': lambda x: re.search('GPU(\d{1,3}).*?Temp', x)[1],
                'label': 'gpu_num',
                'name': 'gpu_temp'         
            },
            {
                'check_name': lambda x: re.search('FAN([\d,A-Z]{1,3}).*', x),
                'get_index': lambda x: re.search('FAN([\d,A-Z]{1,3}).*', x)[1],
                'label': 'fan_num',
                'name': 'fan'         
            }
        ]
        return


app = Flask(__name__)
@app.route('/metrics', methods=['GET', 'POST'])
def metrics_output():
    startTime = time.time()
    device_types = {
        'supermicro': SNMPSupermicro,
        'qct': SNMPQct
    }
    if request.method == 'POST':
        args = request.form
    else:
        args = request.args
    device = device_types[args['type']](host=args['host'], secret=args['secret'])
    device.get_sensors()
    device.sensors_to_metrics()
    metrics_list = list(map(lambda st: str(st), device.metrics))
    return '\n'.join(metrics_list + ['snmp_scrape_duration {{}} {}'.format(time.time() - startTime)])