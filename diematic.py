
"""
influx -precision rfc3339

CREATE DATABASE "diematic"
GRANT ALL ON "diematic" TO "diematic"
CREATE RETENTION POLICY "one_day" ON "diematic" DURATION 24h REPLICATION 1 DEFAULT
CREATE RETENTION POLICY "five_weeks" ON "diematic" DURATION 5w REPLICATION 1
CREATE RETENTION POLICY "five_years" ON "diematic" DURATION 260w REPLICATION 1

CREATE CONTINUOUS QUERY "cq_month" ON "diematic" BEGIN
  SELECT mean(/temperature/) AS "mean_1h", mean(/pressure/) AS "mean_1h", max(/temperature/) AS "max_1h", max(/pressure/) AS "max_1h"
  INTO "five_weeks".:MEASUREMENT
  FROM "one_day"."diematic"
  GROUP BY time(1h),*
END

CREATE CONTINUOUS QUERY "cq_year" ON "diematic" BEGIN
  SELECT mean(/^mean_.*temperature/) AS "mean_24h", mean(/^mean_.*pressure/) AS "mean_24h", max(/^max_.*temperature/) AS "max_24h", max(/^max_.*pressure/) AS "max_24h"
  INTO "five_years".:MEASUREMENT
  FROM "five_weeks"."diematic"
  GROUP BY time(24h),*
END

DROP CONTINUOUS QUERY cq_month ON diematic
DROP CONTINUOUS QUERY cq_year ON diematic

"""



import logging
import yaml
import time
import os.path
import argparse
from influxdb import InfluxDBClient
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

DEFAULT_LOGGING = 'critical'

DEFAULT_MODBUS_RETRIES = 3
DEFAULT_MODBUS_TIMEOUT = 10
DEFAULT_MODBUS_BAUDRATE = 9600
DEFAULT_MODBUS_UNIT = 10
DEFAULT_MODBUS_DEVICE = None


class Boiler:
    def __init__(self, index):
        self.registers = []
        self.attribute_list = []
        self.index = index
        for register in self.index:
            if 'type' in register and register['type'] == 'bits':
                for varname in register['bits']:
                    setattr(self, varname, None)
                    self.attribute_list.append(varname)
            else:
                setattr(self, register['name'], None)
                self.attribute_list.append(register['name'])

    def _decode_decimal(self, value_int, decimals=0):
        if (value_int == 65535):
            return None
        else:
            output = value_int & 0x7FFF
        if (value_int >> 15 == 1):
            output = -output
        return float(output)/10**decimals

    def browse_registers(self):
        for register in self.index:
            if not isinstance(register['id'], int):
                continue
            register_value = self.registers[register['id']]
            if register_value is None:
                log.debug('Browsing register id {:d} value: None'.format(register['id']))
                continue
            log.debug('Browsing register id {:d} value: {:#04x}'.format(register['id'], register_value))
            if 'type' in register and register['type'] == 'bits':
                for i in range(len(register['bits'])):
                    bit_varname = register['bits'][i]
                    bit_value = register_value >> i & 1
                    setattr(self, bit_varname, bit_value)
            else:
                varname = register.get('name')
                if varname and varname.strip(): #test name exists
                    if 'type' in register and register['type'] == 'DiematicOneDecimal':
                        setattr(self, varname, self._decode_decimal(register_value, 1))
                    else:
                        setattr(self, varname, register_value)
                else:
                    continue

    def dump_registers(self):
        output = ''
        for id in range(len(self.registers)):
            if self.registers[id] is None:
                output += "{:d}: None\n".format(id)
            else:
                output += "{:d}: {:#04x}\n".format(id, self.registers[id])
        return output

    def fetch_data(self):
        output = { }
        for varname in self.attribute_list:
            output[varname] = getattr(self, varname)
        return output

    def dump(self):
        output = ''
        for varname,value in self.fetch_data().items():
            output += varname + ' = ' + str(value) + "\n"
        return output    




# --------------------------------------------------------------------------- #
# configure the client logging
# --------------------------------------------------------------------------- #
FORMAT = ('%(asctime)-15s %(threadName)-15s '
          '%(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s')
logging.basicConfig(format=FORMAT, level=logging.ERROR)
log = logging.getLogger()


# --------------------------------------------------------------------------- #
# retrieve command line arguments
# --------------------------------------------------------------------------- #
parser = argparse.ArgumentParser()
parser.add_argument("-b", "--backend", choices=['none', 'influxdb'], default='influxdb', help="select data backend (default is influxdb)")
parser.add_argument("-d", "--device", help="define modbus device")
parser.add_argument("-l", "--logging", choices=['critical', 'error', 'warning', 'info', 'debug'], help="define logging level (default is critical)")
args = parser.parse_args()

# --------------------------------------------------------------------------- #
# retrieve config from diematic.yaml
# --------------------------------------------------------------------------- #
main_base = os.path.dirname(__file__)
config_file = os.path.join(main_base, "diematic.yaml")
if not os.path.exists(config_file):
    raise FileNotFoundError("Configuration file not found")
with open(config_file) as f:
    # use safe_load instead load
    cfg = yaml.safe_load(f)

# --------------------------------------------------------------------------- #
# set logging level
# --------------------------------------------------------------------------- #
new_logging_level = DEFAULT_LOGGING
if args.logging:
    new_logging_level = args.logging
elif 'logging' in cfg:
    new_logging_level = cfg['logging']
numeric_level = getattr(logging, new_logging_level.upper())
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)
log.setLevel(numeric_level)


# --------------------------------------------------------------------------- #
# set configuration variables (command line prevails on configuration file)
# --------------------------------------------------------------------------- #
MODBUS_RETRIES = None
MODBUS_TIMEOUT = None
MODBUS_BAUDRATE = None
MODBUS_UNIT = None
MODBUS_DEVICE = None

if 'modbus' in cfg:
    if isinstance(cfg['modbus']['retries'], int):
        MODBUS_RETRIES = cfg['modbus']['retries']
    if isinstance(cfg['modbus']['timeout'], int):
        MODBUS_TIMEOUT = cfg['modbus']['timeout']
    if isinstance(cfg['modbus']['baudrate'], int):
        MODBUS_BAUDRATE = cfg['modbus']['baudrate']
    if isinstance(cfg['modbus']['unit'], int):
        MODBUS_UNIT = cfg['modbus']['unit']
    if isinstance(cfg['modbus']['device'], str):
        MODBUS_DEVICE = cfg['modbus']['device']

if args.device:
    MODBUS_DEVICE = args.device


# --------------------------------------------------------------------------- #
# check mandatory configuration variables
# --------------------------------------------------------------------------- #
if MODBUS_DEVICE is None:
    raise ValueError('Modbus device not set')

# --------------------------------------------------------------------------- #
# check optional configuration variables
# --------------------------------------------------------------------------- #
if MODBUS_RETRIES is None:
    MODBUS_RETRIES = DEFAULT_MODBUS_RETRIES
if MODBUS_TIMEOUT is None:
    MODBUS_TIMEOUT = DEFAULT_MODBUS_TIMEOUT
if MODBUS_BAUDRATE is None:
    MODBUS_BAUDRATE = DEFAULT_MODBUS_BAUDRATE
if MODBUS_UNIT is None:
    MODBUS_UNIT = DEFAULT_MODBUS_UNIT



# --------------------------------------------------------------------------- #
# let's go!
# --------------------------------------------------------------------------- #
MyBoiler = Boiler(index=cfg['registers'])

def run_sync_client():
    #enabling modbus communication
    client = ModbusClient(method='rtu', port=MODBUS_DEVICE, timeout=MODBUS_TIMEOUT, baudrate=MODBUS_BAUDRATE)
    client.connect()

    #loading modbus data (registers: 600-620, 700-705)
    id_start=600
    id_stop=620
    MyBoiler.registers = [None] * id_start;

    for i in range(MODBUS_RETRIES):
        log.debug("Attempt "+str(i+1))
        rr = client.read_holding_registers(count=(id_stop-id_start+1), address=id_start, unit=MODBUS_UNIT)
        if rr.isError():
            log.error(rr.message)
            MyBoiler.registers.extend([None] * (id_stop-id_start+1))
        else:
            MyBoiler.registers.extend(rr.registers)
            break
    id_start=700
    MyBoiler.registers.extend([None] * (id_start-id_stop-1))
    id_stop=706
    for i in range(MODBUS_RETRIES):
        log.debug("Attempt "+str(i+1))
        rr = client.read_holding_registers(count=(id_stop-id_start+1), address=id_start, unit=MODBUS_UNIT)
        if rr.isError():
            log.error(rr.message)
            MyBoiler.registers.extend([None] * (id_stop-id_start+1))
        else:
            MyBoiler.registers.extend(rr.registers)
            break
    client.close()

    #parsing registers to push data in Object attributes
    MyBoiler.browse_registers()
    log.info(MyBoiler.dump())


    #pushing data to influxdb
    if args.backend and args.backend == 'influxdb':
        timestamp = int(time.time() * 1000) #milliseconds
        influx_json_body = [
        {
            "measurement": "diematic",
            "tags": {
                "host": "raspberrypi",
            },
            "timestamp": timestamp,
            "fields": MyBoiler.fetch_data() 
        }
        ]

        influx_client = InfluxDBClient(cfg['influxdb']['host'], cfg['influxdb']['port'], cfg['influxdb']['user'], cfg['influxdb']['password'], cfg['influxdb']['database'])

        log.debug("Write points: {0}".format(influx_json_body))
        try:
            influx_client.write_points(influx_json_body, time_precision='ms')
        except InfluxDBClient.client.InfluxDBClientError as err:
            log.critical("InfluxDB JSON request: {0}".format(influx_json_body))
            log.critical("InfluxDB Client write_points error: {0}".format(err))
        except Exception as e:
            log.critical("InfluxDB JSON request: {0}".format(influx_json_body))
            log.critical("InfluxDB write_points unknown error ({0}): {0}".format(type(e), e))


if __name__ == "__main__":
    run_sync_client()







