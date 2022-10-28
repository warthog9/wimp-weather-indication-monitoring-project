#  SPDX-License-Identifier: Apache-2.0
#
#  Copyright Rob Connolly <rob@webworxshop.com> 
#  Copyright John 'Warthog9' Hawley <warthog9@eaglescrag.net>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# Original file:
#   https://raw.githubusercontent.com/webworxshop/micropython-room-sensor/master/hassnode.py
# Original Repo:
#   https://github.com/webworxshop/micropython-room-sensor

import ujson as json

class BaseEntity(object):

    # mqtt = mqtt client connection object
    # 

    def __init__(
            self,
            mqtt,
            component,
            object_id,
            node_id,
            discovery_prefix
            ):
        self.mqtt = mqtt

        # https://www.home-assistant.io/docs/mqtt/discovery/
        # [...]
        # The discovery topic need to follow a specific format:
        # <discovery_prefix>/<component>/[<node_id>/]<object_id>/config
        # node_id being "optional"

        if node_id:
            base_topic = "{}/{}/{}/{}/".format(
                    discovery_prefix,
                    component,
                    node_id,
                    object_id
                    )
        else:
            base_topic = "{}/{}/{}/".format(
                    discovery_prefix,
                    component,
                    object_id
                    )

        self.config_topic = base_topic + "config"
        self._state_topic = base_topic + "state"

class BinarySensor(BaseEntity):

    device_class = "binary_sensor"

    def __init__(
            self,
            mqtt,
            name,
            device_class,
            object_id,
            node_id=None,
            discovery_prefix="homeassistant"
            ):

        super(BinarySensor, self).__init__(
                mqtt,
                "binary_sensor",
                object_id,
                node_id,
                discovery_prefix
                )

        self.config = {"name": name, "device_class": device_class}
        try:
            self.mqtt.publish(
                    self.config_topic,
                    bytes(json.dumps(self.config), 'utf-8'),
                    True,
                    1
                    )
        except:
            print('BinarySensor(): mqtt failed')

    def setState(self, state):
        try:
            if state:
                self.mqtt.publish(self._state_topic, bytes("ON", 'utf-8'))
            else:
                self.mqtt.publish(self._state_topic, bytes("OFF", 'utf-8'))
        except:
            print('BinarySensor.setState(): mqtt failed')
            
    def on(self):
        self.setState(True)

    def off(self):
        self.setState(False)

class Sensor(BaseEntity):

    state_class = "measurement"
    state_topic = ""
    device = { 
            "identifiers": "",
            "name": "",
            "model": "",
            "manufacturer": ""
            }
    valid_device_classes = [
            "None",
            "apparent_power",
            "aqi",
            "battery",
            "carbon_dioxide",
            "carbon_monoxide",
            "current",
            "date",
            "energy",
            "frequency",
            "gas",
            "humidity",
            "illuminance",
            "monetary",
            "nitrogen_dioxide",
            "nitrogen_monoxide",
            "nitrous_oxide",
            "ozone",
            "pm1",
            "pm10",
            "pm25",
            "power_factor",
            "power",
            "pressure",
            "reactive_power",
            "signal_strength",
            "sulphur_dioxide",
            "temperature",
            "timestamp",
            "volatile_organic_compounds",
            "voltage"
            ]

    def __init__(
            self,
            mqtt,
            name,
            unit_of_measurement,
            object_id,
            node_id=None,
            discovery_prefix="homeassistant",
            value_template=None,
            device_class=None,
            model="",
            manufacturer="",
            state_topic="",
            unique_id = "",
            device_identifier = "",
            device_name = "",
            device_model = "",
            device_manufacturer = "",
            config_icon=None,
            ha_device=None,
            force_update=None
            ):

        if device_class is not None:
            if device_class not in self.valid_device_classes:
                raise Exception("device_class ({}) not in valid_device_classes".format( str(device_class) ) )

        super(Sensor, self).__init__(
            mqtt,
            "sensor",
            object_id,
            node_id,
            discovery_prefix
            )

        if state_topic:
            self._state_topic = state_topic

        if unique_id is "":
            unique_id = name.replace(" ", "_")

        self.config = {
                "name": name,
                "state_class": self.state_class,
                "state_topic": self._state_topic,
                "unique_id": unique_id,
                "unit_of_measurement": unit_of_measurement
                }

        print("Device class: "+ str(device_class) )
        if device_class is not ( None and "None" ):
                self.config["device_class"] = device_class

        if force_update is not (None and "None" ):
                self.config["force_update"] = force_update

        if config_icon:
            self.config['icon'] = config_icon

        if value_template:
            self.config['value_template'] = value_template

        if ha_device is not None:
            device_dict = {}
            if ha_device["identifiers"] is not None:
                device_dict['identifiers'] = ha_device["identifiers"]
            if ha_device["name"] is not None:
                device_dict['name'] = ha_device["name"]
            if ha_device["model"] is not None:
                device_dict['model'] = ha_device["model"]
            if ha_device["manufacturer"] is not None:
                device_dict['manufacturer'] = ha_device["manufacturer"]
            self.config['device'] = device_dict

        try:
            # Ok first unpublish anything that's there
            #self.mqtt.publish(
            #        self.config_topic,
            #        '',
            #        False
            #        )
            # this should post and update
            self.mqtt.publish(
                    self.config_topic,
                    bytes(json.dumps(self.config), 'utf-8'),
                    True,
                    1
                    )
        except:
            print('Sensor(): mqtt failed')

    def setState(self, state):
        try:
            self.mqtt.publish(
                self._state_topic,
                bytes(json.dumps(state),'utf-8')
                )
        except:
            print('Sensor.setState(): mqtt failed')
