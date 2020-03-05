# diematic
De Dietrich Diematic Modbus data to InfluxDB

![Screenshot](images/chronograf_screenshot.png?raw=true)

## Installation
```
git clone https://github.com/gmasse/diematic.git
cd diematic
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
vi diematic.yaml.orig
mv diematic.yaml.orig diematic.yaml
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
  FROM "one_day"."diematic"
  GROUP BY time(1h),*
END

CREATE CONTINUOUS QUERY "cq_year" ON "diematic" BEGIN
  SELECT mean(/^mean_.*temperature/) AS "mean_24h", mean(/^mean_.*pressure/) AS "mean_24h", max(/^max_.*temperature/) AS "max_24h", max(/^max_.*pressure/) AS "max_24h"
  INTO "five_years".:MEASUREMENT
  FROM "five_weeks"."diematic"
  GROUP BY time(24h),*
END
```


## Cron
To run the script every minute, `crontab -e`
```
*/1 *   * * *       ~/diematic/venv/bin/python3 ~/diematic/diematic.py
```


## References
- https://github.com/riptideio/pymodbus
- (french) http://sarakha63-domotique.fr/chaudiere-de-dietrich-domotise-modbus/amp/
- (french) https://www.dom-ip.com/wiki/Réalisation_d%27une_Interface_Web_pour_une_chaudière_De_Dietrich_équipée_d%27une_régulation_Diematic_3
- (french forum) https://www.domotique-fibaro.fr/topic/5677-de-dietrich-diematic-isystem/
- (french forum) http://www.wit-square.fr/forum/topics/de-dietrich-communication-modbus-bi-ma-tre
- (french, modbus registers sheets, copy from previous forum) https://drive.google.com/file/d/156qBsfRGJvOpJBJu5K4WMHUuwv34bZQN/view?usp=sharing
