# snmp-bmc-exporter 
Export metrics from servers BMC/IPMI by snmp. <br />
Application can be started using start_app.sh script. <br />
Example: <br />
./start_app.sh snmp-bmc-exporter.py 127.0.0.1 9003 <br />

Metric path is /metrics <br />
GET or POST method can be used <br />
Parameters are: <br />
host - target hostname or ip <br />
type - device type, only 'supermicro' and 'qct' are supported for now. <br />
secret - snmp community <br />
