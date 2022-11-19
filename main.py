#  SPDX-License-Identifier: Apache-2.0
#
#  Copyright John 'Warthog9' Hawley <warthog9@eaglescrag.net>
#

# main.py

from time import sleep
from umqtt.simple import MQTTClient
#from umqtt.robust import MQTTClient

import network
# needed for home assistant auto discovery channels
import hassnode

mqttclient = MQTTClient(
                hostname,
                config['mqtt']['broker'],
                user=config['mqtt']['user'],
                password=config['mqtt']['password'],
                keepalive=30
                )
mqttclient.DEBUG = True

def mqtt_sub_cb(topic, msg):
    print((topic, msg))
    if topic == hass_status_topic:
        print("HASS Status message %s, resending config" % ( str(msg) ) )
        publish_hass_config()

mqttclient.set_callback(mqtt_sub_cb)

# need to subscribe to the homassistant/status topic so that
# we can figure out if we need to re-publish the config entries
# after a reboot
hass_status_topic = b'homeassistant/status'

topic_base = "micropython/"+ str(hostname) +"/"

windspeed_count = 0
rain_bucket_count = 0

as3935_count = 0
as3935_energy = 0
as3935_distance = -1
as3935_false_count = 0

time_last = 0
time_now = 0

pms_count = 0
pms_data_sum = ( 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 )

#machine.freq(80000000, min_freq=10000000)
machine.freq(80000000)

ha_sensor_bme280_temp = None
ha_sensor_bme280_pressure = None
ha_sensor_bme280_humidity = None
ha_sensor_veml6075_uva = None
ha_sensor_veml6075_uvb = None
ha_sensor_veml6075_uv_index = None
ha_sensor_wind_dir = None
ha_sensor_wind_speed = None
ha_sensor_rain = None
ha_sensor_as3935_events = None
ha_sensor_as3935_energy = None
ha_sensor_as3935_distance = None
ha_sensor_as3935_false_count = None
ha_sensor_soil_moisture = None
ha_sensor_battery_volt = None
ha_sensor_battery = None
ha_sensor_pms_1_0std = None
ha_sensor_pms_2_5std = None
ha_sensor_pms_10_0std = None
ha_sensor_pms_1_0atmo = None
ha_sensor_pms_2_5atmo = None
ha_sensor_pms_10_0atmo = None
ha_sensor_pms_0_3um = None
ha_sensor_pms_0_5um = None
ha_sensor_pms_1_0um = None
ha_sensor_pms_2_5um = None
ha_sensor_pms_5_0um = None
ha_sensor_pms_10_0um = None

sta_if = None
ap_if = None

def rain_bucket_interrupt(pin):
    global rain_bucket_count
    rain_bucket_count += 1
    print("Rain Bucket %d" % rain_bucket_count )

def windspeed_interrupt(pin):
    global windspeed_count
    windspeed_count += 1
    print("Windspeed %d" % windspeed_count )

def as3935_interrupt(pin):
    global as3935_count
    global as3935_energy
    global as3935_distance
    global as3935_false_count

    if as3935 is None:
        as3935_init()

        if as3935 is None:
            print("Got an as3935 interrupt but can't initialize")
            return

    int_status = as3935.interrupt_status
    print('as3935 triggered interrupt: '+ str(int_status))
    as3935_count += 1

    if int_status == as3935.LIGHTNING:  # It's a lightning event
        print(f"Strike Energy = {as3935.energy}")
        print(f"Distance to storm front = {as3935.distance} km")

        as3935_energy = as3935.energy
        as3935_distance = as3935.distance

    elif event_type == sensor.DISTURBER:
        print("False alarm")
        as3935_false_count += 1

def do_connect():
    global hostname
    global config
    global sta_if
    global ap_if

    if sta_if is None:
        sta_if = network.WLAN(network.STA_IF)

    if ap_if is None:
        ap_if  = network.WLAN(network.AP_IF)

    if not sta_if.isconnected():
        print('connecting to network...')
        print("Using hostname: {}".format( hostname ) )
        sta_if.active(True)
        print( "Station Interface - now active" )
        try:
            sta_if.config(dhcp_hostname=hostname)
        except Exception as e:
            print( "Setting hostname did not go well - {} - {}".format( hostname, e ) )
        print( "Station Hostname set" )

        print( "Setting Wifi - {} / {}".format( config['wifi']['ssid'], config['wifi']['password'] ) )

        try:
            sta_if.connect(
                    config['wifi']['ssid'],
                    config['wifi']['password']
                    )
        except OSError as e:
            print("Wifi connection error" )
            print( e )

        if not sta_if.isconnected() and not ap_if.active():
            ap_if.active(True)
            ap_if.config(essid='wimp-ap', password='fallbacks are good 2022' )
            print('AP mode active')

        if sta_if.isconnected():
            print('network config:', sta_if.ifconfig())
    else:
        print('still connected to wifi...')
        if ap_if.active():
            print( "Ohhhhh we are connected, we don't need the AP up anymore" )
            print('Shutting down AP')
            ap_if.active(False)

def pms_callback():
    global pms_data_sum
    global pms_count

    print("called: pms_callback()")
    pmsdata = pms.read()

    pms.print()

    # pms_data_sum = ( 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 )

    tsum = list( pms_data_sum )
    tdata = list( pmsdata )

    try:
        fsum = [sum(value) for value in zip(tsum, tdata)]

        pms_data_sum = tuple( fsum )

        pms_count = pms_count + 1
    except:
        print("something wonky in data")
        print("tsum %s | tdata %s" %( tsum, tdata ) )

def getWindDirection():
    wDir_u16 = windDirADC.read_u16()

    #print("getWindDirection(): "+ str(wDir_u16) +" - "+ str(wDir_uv) +"|")

    # The Arduino version uses analogRead()
    # which has a resolution of 0-1023
    # read_u16() has a resolution of 0-65535
    # and read_uv() has a resolution of microvolts
    # which puts it in the 0-5000000 range?
    # Ok so the table below needs to be adusted some
    # but should, roughly, work.
    #
    # Also noting that the direction is not super
    # fine controled, it's pretty broad
    #
    # ok so this is 65535/1024, or multiply the
    # Arduino values by about 63.999023437
    # I'm going to call it 64
    #
    # Hmmm read() is 4095() and read_u16() is 65535, I'm going to flip this to
    #

    if wDir_u16 < 24320:
        return 113
    if wDir_u16 < 25152:
        return 68
    if wDir_u16 < 26496:
        return 90
    if wDir_u16 < 29184:
        return 158
    if wDir_u16 < 32512:
        return 135
    if wDir_u16 < 35264:
        return 203
    if wDir_u16 < 39360:
        return 180
    if wDir_u16 < 43520:
        return 23
    if wDir_u16 < 47744:
        return 45
    if wDir_u16 < 51264:
        return 248
    if wDir_u16 < 53312:
        return 225
    if wDir_u16 < 56192:
        return 338
    if wDir_u16 < 58432:
        return 0
    if wDir_u16 < 60160:
        return 293
    if wDir_u16 < 61888:
        return 315
    if wDir_u16 < 63360:
        return 270
    return -1

def readSoil():
    if soil_enable:
        soilPwr.value(1)
        soil_moisture = soilADC.read()
        soilPwr.value(0)

        return ( soil_moisture / 4096 ) * 100

    return 0

def publish(topic, value):
    global mqttclient
    global mqtt_failed
    global topic_base
    global sta_if
    global ap_if

    print( 'attempting to publish to: '+ topic )
    #print( 'attempting to publish to'+ topic +' - '+ value)

    if not sta_if.isconnected():
        print( "Not connected as a Wifi client, this won't work - returning early" )
        return

    if mqtt_failed:
        try:
            mqttclient.connect()
            mqtt_failed = False
        except Excetion as e:
            print( "mqtt already marked as failed, and reconnect bailing early" )
            mqtt_failed = True
            return

    try:
        mqttclient.publish(
                topic_base + topic,
                value
                )
        mqtt_failed = False
    except:
        print(topic +': mqtt failed - disconnecting')
        mqtt_failed = True
        mqttclient.disconnect()

def publish_hass_config():
    global ha_sensor_bme280_temp
    global ha_sensor_bme280_pressure
    global ha_sensor_bme280_humidity
    global ha_sensor_veml6075_uva
    global ha_sensor_veml6075_uvb
    global ha_sensor_veml6075_uv_index
    global ha_sensor_wind_dir
    global ha_sensor_wind_speed
    global ha_sensor_rain
    global ha_sensor_as3935_events
    global ha_sensor_as3935_energy
    global ha_sensor_as3935_distance
    global ha_sensor_as3935_false_count
    global ha_sensor_soil_moisture
    global ha_sensor_battery_volt
    global ha_sensor_battery
    global ha_sensor_pms_1_0std
    global ha_sensor_pms_2_5std
    global ha_sensor_pms_10_0std
    global ha_sensor_pms_1_0atmo
    global ha_sensor_pms_2_5atmo
    global ha_sensor_pms_10_0atmo
    global ha_sensor_pms_0_3um
    global ha_sensor_pms_0_5um
    global ha_sensor_pms_1_0um
    global ha_sensor_pms_2_5um
    global ha_sensor_pms_5_0um
    global ha_sensor_pms_10_0um

    global mqttclient

    ha_device = {
            "identifiers": hostname +"-16794-sparkfun",
            "name": hostname +"-16794-sparkfun",
            "model": "16794 - MicroMod Weather Carrier",
            "manufacturer": "SparkFun"
            }

    ha_sensor_bme280_temp = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Temperature",
            unit_of_measurement = "°C",
            object_id = hostname +"_bme280_temp_c",
            node_id = hostname,
            device_class = "temperature",
            ha_device = ha_device
            )
    ha_sensor_bme280_pressure = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Barometric Pressure",
            unit_of_measurement = "hPa",
            object_id = hostname +"_bme280_pressure_hpa",
            node_id = hostname,
            device_class = "pressure",
            ha_device = ha_device
            )
    ha_sensor_bme280_humidity = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Humidity",
            unit_of_measurement = "%",
            object_id = hostname +"_bme280_humidity",
            node_id = hostname,
            device_class = "humidity",
            ha_device = ha_device
            )
    ha_sensor_veml6075_uva = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - UVA",
            unit_of_measurement = "counts/μW/cm2",
            object_id = hostname +"_veml6075_uva",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:gauge'
            )

    ha_sensor_veml6075_uvb = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - UVb",
            unit_of_measurement = "counts/μW/cm2",
            object_id = hostname +"_veml6075_uvb",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:gauge'
            )

    ha_sensor_veml6075_uv_index = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - UV Index",
            unit_of_measurement = "uvi",
            object_id = hostname +"_veml6075_uv_index",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:sun-wireless'
            )
    #ha_sensor_veml6075_uv_index.config['icon'] = 'weather-sunny-alert'

    ha_sensor_wind_dir = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Wind Direction",
            unit_of_measurement = "°",
            object_id = hostname +"_wind_dir",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:compass'
            )

    ha_sensor_wind_speed = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Wind Speed",
            unit_of_measurement = "km/h",
            object_id = hostname +"_wind_speed",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:wind-turbine'
            )

    ha_sensor_rain = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Rain Fall",
            unit_of_measurement = "mm",
            object_id = hostname +"_rain",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:water',
            force_update = True
            )

    ha_sensor_as3935_events = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Lightning Events",
            unit_of_measurement = "count",
            object_id = hostname +"_lightning_events",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:lightning-bolt'
            )

    ha_sensor_as3935_energy = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Lightning Energy",
            unit_of_measurement = "lightning energy",
            object_id = hostname +"_lightning_energy",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:lightning-bolt'
            )

    ha_sensor_as3935_distance = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Lightning Distance",
            unit_of_measurement = "km",
            object_id = hostname +"_lightning_distance",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:lightning-bolt'
            )

    ha_sensor_as3935_false_count = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - False Lightning",
            unit_of_measurement = "count",
            object_id = hostname +"_lightning_false_count",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:lightning-bolt'
            )

    ha_sensor_soil_moisture = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Soil Moisture",
            unit_of_measurement = "%",
            object_id = hostname +"_soil",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:lightning-bolt'
            )

    ha_sensor_battery_volt = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Battery V",
            unit_of_measurement = "V",
            object_id = hostname +"_battery_v",
            node_id = hostname,
            device_class = None,
            ha_device = ha_device,
            config_icon = 'mdi:battery'
            )

    ha_sensor_battery = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Battery",
            unit_of_measurement = "%",
            object_id = hostname +"_battery",
            node_id = hostname,
            device_class = "battery",
            ha_device = ha_device
            )

    ha_sensor_pms_1_0std = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 1.0µm Concentration Standard",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_1_0um_std_concentration",
            node_id = hostname,
            device_class = "pm1",
            ha_device = ha_device
            )
    ha_sensor_pms_2_5std = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 2.5µm Concentration Standard",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_2_5um_std_concentration",
            node_id = hostname,
            device_class = "pm25",
            ha_device = ha_device
            )
    ha_sensor_pms_10_0std = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 10.0µm Concentration Standard",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_10_0um_std_concentration",
            node_id = hostname,
            device_class = "pm10",
            ha_device = ha_device
            )
    ha_sensor_pms_1_0atmo = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 1.0µm Concentration Atmospheric",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_1_0um_atmo_concentration",
            node_id = hostname,
            device_class = "pm1",
            ha_device = ha_device
            )
    ha_sensor_pms_2_5atmo = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 2.5µm Concentration Atmospheric",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_2_5um_atmo_concentration",
            node_id = hostname,
            device_class = "pm25",
            ha_device = ha_device
            )
    ha_sensor_pms_10_0atmo = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Matter < 10.0µm Concentration Atmospheric",
            unit_of_measurement = "µg/m³",
            object_id = hostname +"_particulate_matter_10_0um_atmo_concentration",
            node_id = hostname,
            device_class = "pm10",
            ha_device = ha_device
            )
    ha_sensor_pms_0_3um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 0.3/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_0_3um",
            node_id = hostname,
            ha_device = ha_device
            )
    ha_sensor_pms_0_5um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 0.5/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_0_5um",
            node_id = hostname,
            ha_device = ha_device
            )
    ha_sensor_pms_1_0um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 1.0/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_1_0um",
            node_id = hostname,
            ha_device = ha_device
            )
    ha_sensor_pms_2_5um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 2.5/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_2_5um",
            node_id = hostname,
            ha_device = ha_device
            )
    ha_sensor_pms_5_0um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 5.0/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_5_0um",
            node_id = hostname,
            ha_device = ha_device
            )
    ha_sensor_pms_10_0um = hassnode.Sensor(
            mqtt = mqttclient,
            name = hostname +" - Particulate Count > 10.0/dl",
            unit_of_measurement = "/dl",
            object_id = hostname +"_particulate_count_10_0um",
            node_id = hostname,
            ha_device = ha_device
            )


try:
    windSpeedPin.irq(trigger=Pin.IRQ_RISING, handler=windspeed_interrupt)
except Exception as e:
    print( "windSpeedPin couldn't be setup - {}".format( e ) )

try:
    rainBucketPin.irq(trigger=Pin.IRQ_RISING, handler=rain_bucket_interrupt)
except Exception as e:
    print( "rainBucketPin couldn't be setup - {}".format( e ) )

try:
    as3935IntPin.irq(trigger=Pin.IRQ_RISING, handler=as3935_interrupt)
except Exception as e:
    print( "as3935IntPin couldn't be setup - {}".format( e ) )

print( "Initial connection attempt" )
print( "sta_if: {}".format( sta_if ) )
if not sta_if is None:
    print( "connected: {}".format( sta_if.isconnected() ) )

while True:
    if not sta_if is None and sta_if.isconnected():
        break

    if not sta_if is None:
        print( "Retrying conncting.." )

    print( "Connecting..." )
    do_connect()
    sleep( 10 )

print( "Clearly made it out of connecting..." )
print('network config:', sta_if.ifconfig())

# Ok this is where we start running the loop
# but we need to start with an initial sleep

time_sleep = 10

time_last = time.time_ns()
#sleep( time_sleep )

# bme_values[0]: 2688 - 26.88C
# windDir: 113
# Wind Speed: 0.000000km/h
# Rain dropped: 0.000000mm
# Battery: 4.477411


# Home Assistant reporting pieces
#   Note: HA, mostly, doesn't support wind direction which seems shockingly dumb
#         It also doesn't seem to support rain gauges?  There's some broken there
#         It's possible that doing this as "auto discovery" is not a great plan


print('Going to try and do initial mqtt connection')
while 1:
    try:
        mqttclient.connect()
        mqtt_failed = False
        break
    except OSError as e:
        print( "mqtt: error connecting - waiting" )
        mqtt_failed = True
        sleep( 10 )
        #mqttclient.reconnect()

publish_hass_config()
mqttclient.subscribe(hass_status_topic)

# go ahead and stay connected, no need to disconnect
#mqttclient.disconnect()

# also need to plumb the veml6075 and the as3935 in here...

async def main():
    global windspeed_count
    global rain_bucket_count
    global time_last
    global as3935_count
    global as3935_energy
    global as3935_distance
    global as3935_false_count
    global pms_data_sum
    global pms_count
    global mqttclient
    global mqtt_failed

    global ha_sensor_bme280_temp
    global ha_sensor_bme280_pressure
    global ha_sensor_bme280_humidity
    global ha_sensor_veml6075_uva
    global ha_sensor_veml6075_uvb
    global ha_sensor_veml6075_uv_index
    global ha_sensor_wind_dir
    global ha_sensor_wind_speed
    global ha_sensor_rain
    global ha_sensor_as3935_events
    global ha_sensor_as3935_energy
    global ha_sensor_as3935_distance
    global ha_sensor_as3935_false_count
    global ha_sensor_soil_moisture
    global ha_sensor_battery_volt
    global ha_sensor_battery
    global ha_sensor_pms_1_0std
    global ha_sensor_pms_2_5std
    global ha_sensor_pms_10_0std
    global ha_sensor_pms_1_0atmo
    global ha_sensor_pms_2_5atmo
    global ha_sensor_pms_10_0atmo
    global ha_sensor_pms_0_3um
    global ha_sensor_pms_0_5um
    global ha_sensor_pms_1_0um
    global ha_sensor_pms_2_5um
    global ha_sensor_pms_5_0um
    global ha_sensor_pms_10_0um

    while True:

        do_connect()

        if as3935 is None:
            as3935_init()

            if as3935 is None:
                print("Tried to init as3935, failed again")

        if mqtt_failed:
            try:
                mqttclient.connect()
            except:
                print("mqtt connection failure, going to sleep and try again")
                sleep( time_sleep )
                continue
            publish_hass_config()
            mqttclient.subscribe(hass_status_topic)

        print("*** Checking for mqtt messages...")
        try:
            mqttclient.check_msg()
        except Exception as e:
            print("Something went wrong with the mqtt check_msg - {}".format( e ) )

        try:
            bme_values = bme.values_no_units()

            print("bme_values[0]: %s - %s - %s" % ( bme_values[0], bme_values[1], bme_values[2] ) )
            #if( bme_values[0] < 20 ):
            #    print("***ERROR***")
            #    error_state = True

            publish( "sensors/temperature_C", bytes( bme_values[0], 'utf-8' ) )
            ha_sensor_bme280_temp.setState(float(bme_values[0]))

            publish( "sensors/pressure", bytes( bme_values[1], 'utf-8' ) )
            ha_sensor_bme280_pressure.setState(float(bme_values[1]))

            publish( "sensors/humidity", bytes( bme_values[2], 'utf-8' ) )
            ha_sensor_bme280_humidity.setState(float(bme_values[2]))
        except Exception as e:
            print( "Something Wrong with publishing BMEx80 values - {}".format( e ) )

        try:
            # ok lets do the veml6075 uva / uvb / uv_index sensor

            publish( "sensors/uva", bytes( str(veml6075.uva), 'utf-8' ) )
            ha_sensor_veml6075_uva.setState(float(veml6075.uva))

            publish( "sensors/uvb", bytes( str(veml6075.uvb), 'utf-8' ) )
            ha_sensor_veml6075_uvb.setState(float(veml6075.uvb))

            publish( "sensors/uv_index", bytes( str(veml6075.uv_index), 'utf-8' ) )
            ha_sensor_veml6075_uv_index.setState(float(veml6075.uv_index))
        except Exception as e:
            print( "Something Wrong with publishing veml6075 values - {}".format( e ) )

        try:
            windDir = getWindDirection()
            print("windDir: %d" % ( windDir ) )
            publish( "sensors/wind_direction", str(windDir) )
            ha_sensor_wind_dir.setState(float(windDir))
        except Exception as e:
            print( "Something Wrong with publishing windDir values - {}".format( e ) )

        # Ok lets deal with the wind speed and rain gauge
        # According to the datasheet
        # https://cdn.sparkfun.com/assets/d/1/e/0/6/DS-15901-Weather_Meter.pdf
        # the rain gauge triggers every 0.2794mm of water.
        # So we can just do trigger = value + 0.2794mm
        # per cycle, and then clear it.  Good enough
        #
        # As for the anemometer this is going to be obnoxious
        # math.  From the datasheet:
        #   A wind speed of 2.4km/h causes the switch to
        #   close once per second.
        # So I can either do this as closures per second, and
        # run the loop on about a 1 second timer, or have to
        # do closures per time frame and figure it out from
        # there
        # So it's ( <closures>/<seconds> ) * 2.47km/h?
        # 1 closure in 1 second is 2.47km/h, ok
        # 2 closures in 1 second is ~5km/h, ok
        # 1 closure in 2 seconds is 1.23km/h
        # ok I think that math works out ok

        # ok lets sort out wind speed and rain count
        # for this time period
        # Step one, record the time

        time_now = time.time_ns()

        count_wind = windspeed_count
        windspeed_count = 0

        count_rain = rain_bucket_count
        rain_bucket_count = 0

        # ok nowthat's we've dealt with the data we need, CALCULATE!

        seconds_elapsed = ( time_now - time_last ) / 1000000000

        wind_speed_kmh = ( count_wind / seconds_elapsed ) * 2.47
        print( "( %d / %d ) * 2.47 ) = %g" %( count_wind, seconds_elapsed, wind_speed_kmh ) )

        rain_mm = count_rain * 0.2794

        time_last = time_now
        time_now = 0

        print("Wind Speed: %fkm/h" % ( wind_speed_kmh ) )
        publish( "sensors/wind_speed_kmh", str(wind_speed_kmh) )
        ha_sensor_wind_speed.setState(float(wind_speed_kmh))

        print("Rain dropped: %fmm" % ( rain_mm ) )
        publish( "sensors/rain_fall_mm", str(rain_mm) )
        ha_sensor_rain.setState(float(rain_mm))

        try:
            # calibrating the 5V based on actual readings
            battery_max = 4.38
            battery_min = 2.58
            battery_carrier_voltage = ( battery_carrierADC.read() / 4095 ) * 5.637982196
            battery_percent = (
                    (
                        battery_carrier_voltage - battery_min
                    ) / (
                        battery_max - battery_min
                    )
                ) * 100
            print("Battery: "+ str( battery_carrier_voltage ) +" - "+ str(battery_percent) +"%")
            publish( "sensors/battery_carrier_v", str(battery_carrier_voltage) )
            ha_sensor_battery_volt.setState(battery_carrier_voltage)
            publish( "sensors/battery_carrier_percent", str(battery_carrier_voltage) )
            ha_sensor_battery.setState(battery_percent)
        except Exception as e:
            print( "Something Wrong with publishing battery values - {}".format( e ) )

        try:
            print("Lightning Count: %d" % ( as3935_count ) )
            publish( "sensors/lightning_count", str(as3935_count) )
            ha_sensor_as3935_events.setState(int(as3935_count))

            print("Lightning Energy: %d" % ( as3935_energy ) )
            publish( "sensors/lightning_energy", str(as3935_energy) )
            ha_sensor_as3935_energy.setState(int(as3935_energy))

            print("Lightning Distance: %f" % ( as3935_distance ) )
            publish( "sensors/lightning_distance", str(as3935_distance) )
            ha_sensor_as3935_distance.setState(float(as3935_distance))

            print("Lightning False Count: %d" % ( as3935_false_count ) )
            publish( "sensors/lightning_false_count", str(as3935_false_count) )
            ha_sensor_as3935_false_count.setState(int(as3935_false_count))

            as3935_count = 0
            as3935_false_count = 0
            as3935_distance = -1
            as3935_energy = 0
        except Exception as e:
            print( "Something Wrong with publishing as3935 values - {}".format( e ) )

        try:
            soil_moisture = readSoil()
            print("Soil Moisture: %f" % ( float(soil_moisture) ) )
            publish( "sensors/soil_moisture", str(soil_moisture) )
            ha_sensor_soil_moisture.setState(float(soil_moisture))
        except Exception as e:
            print( "Something Wrong with publishing soil moisture values - {}".format( e ) )

        try:
            #
            # PMS sensors here
            #

            if pms_count > 0:
                # only need to send this if we've actually gotten
                # pms data

                pms_data = pms_data_sum
                pms_lcount = pms_count
                pms_data_sum = ( 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 )
                pms_count = 0

                if pms_lcount is 0:
                    pms_data = ( 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 )
                else:
                    pms_data = tuple([ x / pms_lcount for x in pms_data ])

                print( "pms_data: %s " %( pms_data, ) )

                print( "pms_data[0] ")
                #publish( "sensors/pms_5003_1_0std", bytes( pms_data[0], 'utf-8' ) )
                ha_sensor_pms_1_0std.setState(float(pms_data[0]))

                print( "pms_data[1] ")
                #publish( "sensors/pms_5003_2_5std", bytes( pms_data[1], 'utf-8' ) )
                ha_sensor_pms_2_5std.setState(float(pms_data[1]))

                print( "pms_data[2] ")
                #publish( "sensors/pms_5003_10_0std", bytes( pms_data[2], 'utf-8' ) )
                ha_sensor_pms_10_0std.setState(float(pms_data[2]))

                print( "pms_data[3] ")
                #publish( "sensors/pms_5003_1_0atmo", bytes( pms_data[3], 'utf-8' ) )
                ha_sensor_pms_1_0atmo.setState(float(pms_data[3]))

                print( "pms_data[4] ")
                #publish( "sensors/pms_5003_2_5atmo", bytes( pms_data[4], 'utf-8' ) )
                ha_sensor_pms_2_5atmo.setState(float(pms_data[4]))

                print( "pms_data[5] ")
                #publish( "sensors/pms_5003_10_0atmo", bytes( pms_data[5], 'utf-8' ) )
                ha_sensor_pms_10_0atmo.setState(float(pms_data[5]))

                print( "pms_data[6] ")
                #publish( "sensors/pms_5003_0_3um", bytes( pms_data[6], 'utf-8' ) )
                ha_sensor_pms_0_3um.setState(float(pms_data[6]))

                print( "pms_data[7] ")
                #publish( "sensors/pms_5003_0_5um", bytes( pms_data[7], 'utf-8' ) )
                ha_sensor_pms_0_5um.setState(float(pms_data[7]))

                print( "pms_data[8] ")
                #publish( "sensors/pms_5003_1_0um", bytes( pms_data[8], 'utf-8' ) )
                ha_sensor_pms_1_0um.setState(float(pms_data[8]))

                print( "pms_data[9] ")
                #publish( "sensors/pms_5003_2_5um", bytes( pms_data[9], 'utf-8' ) )
                ha_sensor_pms_2_5um.setState(float(pms_data[9]))

                print( "pms_data[10] ")
                #publish( "sensors/pms_5003_5_0um", bytes( pms_data[10], 'utf-8' ) )
                ha_sensor_pms_5_0um.setState(float(pms_data[10]))

                print( "pms_data[11] ")
                #publish(
                #    "sensors/pms_5003_10_0um",
                #    bytes( pms_data[11], 'utf-8' )
                #    )
                ha_sensor_pms_10_0um.setState(float(pms_data[11]))
            # end pms_count > 0
        except Exception as e:
            print( "Something Wrong with publishing soil moisture values - {}".format( e ) )

        #
        # Clean up mqtt
        #

        #try:
        #    mqttclient.disconnect()
        #except:
        #    print("mqttclient couldn't disconnect")
        #sleep( time_sleep )
        await asyncio.sleep( time_sleep )

    # end while true
# end async main()

try:
    pms5003.set_debug(True)
except Exception as e:
    print( "pms5003 error trying to set_debug() - {}".format( e ) )

try:
    pms.registerCallback(pms_callback)
except Exception as e:
    print( "Counld not create pms callback - {}".format( e ) )

try:
    asyncio.create_task(main())
except Exception as e:
    print( "could not setup main task... that seems like an issue" )

loop=asyncio.get_event_loop()
try:
    loop.run_forever()
except Exception as err:
    print( "main loop exception"+ err )
