# diematic

> :warning: This repository is archived because I don't own a Diematic boiler anymore.
> You can visit the [fork](https://github.com/IgnacioHR/diematic_server) from @IgnacioHR with additionnal features.

A Python script to monitor De Dietrich boiler equiped with Diematic system using Modbus RS-845 protocol.
The values fetched from the boiler are sent to an InfluxDB database, for monitoring with Chronograph.

![Screenshot](images/chronograf_screenshot.png?raw=true)


## Hardware requirements

 * A De Dietrich boiler with Diematic regulation and a mini-din socket
 * A mini-din cable 
 * A RS-845 to USB adapter
 * A nano-computer with a USB port and Python3 installed (Raspberry pi or similar)

Check tutorials in the "references" section below on how to do the hardware setup.

## Installation
```
git clone https://github.com/gmasse/diematic.git
cd diematic
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp diematic.yaml.orig diematic.yaml
vi diematic.yaml
```

## Test
Run `python3 diematic.py --help`
```
usage: diematic.py [-h] [-b {none,influxdb}] [-d DEVICE]
                   [-l {critical,error,warning,info,debug}]

optional arguments:
  -h, --help            show this help message and exit
  -b {none,influxdb}, --backend {none,influxdb}
                        select data backend (default is influxdb)
  -d DEVICE, --device DEVICE
                        define modbus device
  -l {critical,error,warning,info,debug}, --logging {critical,error,warning,info,debug}
                        define logging level (default is critical)
```
`python3 diematic.py --backend none --logging debug`

## InfluxDB preparation
### Minimal
```
CREATE DATABASE "diematic"
CREATE USER "diematic" WITH PASSWORD 'mySecurePas$w0rd'
GRANT ALL ON "diematic" TO "diematic"
CREATE RETENTION POLICY "one_week" ON "diematic" DURATION 1w REPLICATION 1 DEFAULT
```

### Additionnal steps for down-sampling
```
CREATE RETENTION POLICY "five_weeks" ON "diematic" DURATION 5w REPLICATION 1
CREATE RETENTION POLICY "five_years" ON "diematic" DURATION 260w REPLICATION 1

CREATE CONTINUOUS QUERY "cq_month" ON "diematic" BEGIN
  SELECT mean(/temperature/) AS "mean_1h", mean(/pressure/) AS "mean_1h", max(/temperature/) AS "max_1h", max(/pressure/) AS "max_1h"
  INTO "five_weeks".:MEASUREMENT
  FROM "one_week"."diematic"
  GROUP BY time(1h),*
END

CREATE CONTINUOUS QUERY "cq_year" ON "diematic" BEGIN
  SELECT mean(/^mean_.*temperature/) AS "mean_24h", mean(/^mean_.*pressure/) AS "mean_24h", max(/^max_.*temperature/) AS "max_24h", max(/^max_.*pressure/) AS "max_24h"
  INTO "five_years".:MEASUREMENT
  FROM "five_weeks"."diematic"
  GROUP BY time(24h),*
END
```


## Crontab
To run the script every minute and feed the database, `crontab -e` and add the following line:
```
*/1 *   * * *       ~/diematic/launcher.sh
```


## References
- https://github.com/riptideio/pymodbus
- (french) http://sarakha63-domotique.fr/chaudiere-de-dietrich-domotise-modbus/amp/
- (french) https://www.dom-ip.com/wiki/Réalisation_d%27une_Interface_Web_pour_une_chaudière_De_Dietrich_équipée_d%27une_régulation_Diematic_3
- (french forum) https://www.domotique-fibaro.fr/topic/5677-de-dietrich-diematic-isystem/
- ~~(french forum) http://www.wit-square.fr/forum/topics/de-dietrich-communication-modbus-bi-ma-tre~~
- (french, modbus registers sheets, copy from previous forum) https://drive.google.com/file/d/156qBsfRGJvOpJBJu5K4WMHUuwv34bZQN/view?usp=sharing
