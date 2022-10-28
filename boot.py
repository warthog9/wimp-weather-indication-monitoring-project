#  SPDX-License-Identifier: Apache-2.0
#
#  Copyright John 'Warthog9' Hawley <warthog9@eaglescrag.net>
#

# This file is executed on every boot (including wake-boot from deepsleep)

# Load webrepl
#   Honestly right now this is the most useful / only way into the device
#   remotely.  This should get changed to something more akin to the
#   console present on things like Tasmota but I'm not there at this point
import webrepl
webrepl.start()

from machine import Pin, SPI, I2C, Signal, Timer, SoftI2C, SoftSPI, ADC
import machine
import bme280
import network
import sdcard
import time
import sys
import veml6075
import biffobear_as3935
import pms5003
import uasyncio as asyncio
import ujson
import ubinascii

def load_config():
    with open('config.json') as config_file:
        try:
            return ujson.loads(config_file.read())
        except:
            print('Failed to load config file')
            sys.exit(1)

config = load_config()

hostname = "wimp-" + ubinascii.hexlify(machine.unique_id()).decode('utf-8')
# allow overriding the hostname
if 'hostname' in config:
    hostname = config['hostname']

#
# Pin definitions
#   This tries to define ALL the pins, regardless of their use
#

header_cs = 27
# header_cipo = pin_spi_miso  
# header_copi = pin_spi_mosi
# header_sck = pin_spi_clk
header_pwm1 = 12
header_pwm0 = 13

# header_rx2 = n/c
# header_tx2 = n/c
header_rx1 = 16
# header_tx1 = 17 <-- that's connected to the as3935 interupt
# header_sda = pin_i2c_sda
# header_scl = pin_i2c_scl

# onboard pins
#   on the MM
pin_mm_led_board = 2

#   on the board
pin_i2c_sda = 21
pin_i2c_scl = 22

pin_spi_clk = 18
pin_spi_miso = 19
pin_spi_mosi = 23

pin_as3935_cs = 25
pin_as3935_int = 17

pin_soil_pwr = 15
pin_soil_analog = 34

pin_wind_speed = 14
pin_wind_dir = 35

pin_rain_trigger = 27

pin_sd_cs = 5

bme280_address = 0x77

veml6075_addr = 0x10

pms_uart = machine.UART(1, tx=header_cs, rx=header_rx1, baudrate=9600,  )

pms_lock = asyncio.Lock()
pms = pms5003.PMS5003(
        pms_uart,
        pms_lock,
        active_mode=False,
    )
        #set_pin=Pin(header_pwm1, Pin.OUT),
        #reset_pin=Pin(header_pwm0, Pin.OUT)

bus_i2c = SoftI2C( scl=Pin(pin_i2c_scl), sda=Pin(pin_i2c_sda) )

bus_i2c.scan()

bus_spi = SoftSPI(
        -1,
        sck=Pin(pin_spi_clk),
        mosi=Pin(pin_spi_mosi),
        miso=Pin(pin_spi_miso)
    )

bme = bme280.BME280( i2c=bus_i2c, address=bme280_address )

veml6075 = veml6075.VEML6075( i2c=bus_i2c )

#sd = sdcard.SDCard( bus_spi, cs=Pin(pin_sd_cs) )

as3935 = None

def as3935_init():
    global as3935

    try:
        as3935 = biffobear_as3935.AS3935(
                bus_spi,
                pin_as3935_cs,
                interrupt_pin=pin_as3935_int
            )
    except:
        # NOTE: This seems to fail somewhat regularly on the clock
        #       sync.  Not sure how/why but a power cycle clears it
        #       up.  However there's no way without a FULL power
        #       cycle to cut power to the AS3935.  Ideally this would
        #       be on a transistor so you could easily power on/off
        #       but such is not the case currently.
        print("as3935 init failed - will have to retry")
        as3935 = None

as3935_init()

as3935IntPin = Pin(pin_as3935_int, Pin.IN)

soil_enable = False
if soil_enable:
    soilPwr = Pin(pin_soil_pwr, Pin.OUT)
    soilADC = ADC(Pin(pin_soil_analog, Pin.IN, Pin.PULL_DOWN))

windDirADC = ADC(Pin(pin_wind_dir))
windDirADC.atten(windDirADC.ATTN_11DB)

windSpeedPin = Pin(pin_wind_speed, Pin.IN)

rainBucketPin = Pin(pin_rain_trigger, Pin.IN)

# Ok this is the 5V voltage divider monitor from the carrier board
# I'm honestly not sure this will ever be fully accurate since I think
# the 5V output from the solar panel / battery is already
# regulated so it's kinda pointless?
# Going to add it in anyway

pin_vin_batt_carrier = 39

battery_carrierADC = ADC( Pin(pin_vin_batt_carrier) )
battery_carrierADC.atten(windDirADC.ATTN_6DB)
