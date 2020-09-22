#!/usr/bin/env python
try:
    import polyinterface,logging
    import paho.mqtt.client as mqtt
except ImportError:
    import pgc_interface as polyinterface
import sys
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import time
import json
import requests

LOGGER = polyinterface.LOGGER
LOGGER.setLevel(logging.WARNING)
LOGGER.setLevel(logging.INFO)
LOGGER.setLevel(logging.DEBUG)
_PARM_MQTT_HOST_NAME = "MQTT_HOST"
MILES_PER_KM=0.621371

class Controller(polyinterface.Controller):
    def discover_on_connect(self, client, userdata, flags, rc):
      LOGGER.debug('discover_on_connect: Discover connected with result code '.format(str(rc)))
      client.subscribe("teslamate/cars/+/display_name")
      pass

    def discover_on_message(self, client, userdata, msg):
      LOGGER.debug('discover_on_message')
      LOGGER.debug('MQTT message {}:{}'.format(msg.topic, msg.payload))
      topic = msg.topic.split('/')
      vehicleNumber = topic[2]
      statusItem = topic[3]
      payload = msg.payload.decode('utf-8')
      LOGGER.debug('discover_on_message: vehicleNumber {}, statusItem {}, payload {}'.format(vehicleNumber, statusItem, payload))

      # find the vehicle node
      nodeAddress = str(vehicleNumber)
      LOGGER.debug('discover_on_message: nodeAddress {}'.format(nodeAddress))
      if bool(self.nodes.get(nodeAddress)):
        LOGGER.debug('discover_on_message: Vehicle was found in list - skipping')

      else:
        LOGGER.debug('Vehicle was NOT found in list')
        LOGGER.debug('discover_on_message: nodes = {}'.format(self.nodes))
        # not found, so add the node
        LOGGER.info('Adding node with address {} and name {}'.format(nodeAddress, payload))
        self.addNode(VehicleNode(self, self.address, nodeAddress, payload, self.MQTT_HOST, vehicleNumber))
      fi
      pass

    def controller_on_connect(self, client, userdata, flags, rc):
      LOGGER.debug('Connected with result code '.format(str(rc)))
      client.subscribe("teslamate/cars/#")

    def controller_on_message(self, client, userdata, msg):
      LOGGER.debug('')
      LOGGER.debug('MQTT message {}:{}'.format(msg.topic, msg.payload))
      LOGGER.debug('controller_on_message self = {}'.format(self))
      topic = msg.topic.split('/')
      vehicleNumber = topic[2]
      statusItem = topic[3]
      payload = msg.payload.decode('utf-8')
      LOGGER.debug('Split: vehicleNumber {}, statusItem {}, payload {}'.format(vehicleNumber, statusItem, payload))
      
      # find the vehicle node
      nodeAddress = str(vehicleNumber)
      if bool(self.nodes.get(nodeAddress)): 
        #LOGGER.debug('Vehicle was found in list')

        # pass the message to the node for handling
        targetVehicle = self.nodes.get(nodeAddress)
        targetVehicle.handleMessage(statusItem, payload)

      else:
        LOGGER.debug('Vehicle was NOT found in list - run DISCOVER to add it')
        LOGGER.debug('controller_on_message nodes = {}'.format(self.nodes))
      fi

    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        LOGGER.debug('Controller __init__')
        self.name = 'TeslaMate Controller'
        self.poly.onConfig(self.process_config)
        self.client = mqtt.Client(userdata=self)
        self.client.on_connect = self.controller_on_connect
        self.client.on_message = self.controller_on_message
        LOGGER.debug('Controller done with __init__')

    def start(self):
        # This grabs the server.json data and checks profile_version is up to date
        serverdata = self.poly.get_server_data()
        LOGGER.info('Started TeslaMate NodeServer {}'.format(serverdata['version']))
        LOGGER.info("self.polyConfig[customParams].items() = %s" ,self.polyConfig['customParams'].items())
        self.heartbeat(0)
        self.check_params()
        self.poly.add_custom_config_docs("")
        self.poly.installprofile()
        self.discover()
        self.client = mqtt.Client()
        self.client.on_connect = self.controller_on_connect
        self.client.on_message = self.controller_on_message
        self.client.connect(self.MQTT_HOST, 1883, 60)
        self.client.loop_forever()

    def shortPoll(self):
        LOGGER.debug('shortPoll')

    def longPoll(self):
        LOGGER.debug('longPoll')
        self.heartbeat()

    def query(self,command=None):
        self.check_params()
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        LOGGER.debug('Controller - discover: self.MQTT_HOST = {}'.format(self.MQTT_HOST))

        # start discover MQTT background loop
        self.discover_client = mqtt.Client()
        self.discover_client.on_connect = self.discover_on_connect
        self.discover_client.on_message = self.discover_on_message
        self.discover_client.connect(self.MQTT_HOST, 1883, 60)
        self.discover_client.loop_start()
        # give it 10 seconds to get all the vehicles
        LOGGER.debug("Discover - sleeping for 10 seconds for discovery")
        time.sleep(10)
        LOGGER.debug("Discover - slept for 10 seconds for discovery - stopping discovery")
        self.discover_client.loop_stop()

        return
          
    def delete(self):
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        LOGGER.debug('NodeServer stopped.')

    def process_config(self, config):
        # this seems to get called twice for every change, why?
        # What does config represent?
        LOGGER.info("process_config: Enter config={}".format(config));
        LOGGER.info("process_config: Exit");

    def heartbeat(self,init=False):
        LOGGER.debug('heartbeat: init={}'.format(init))
        if init is not False:
            self.hb = init
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def check_params(self):
        default_api_key = "ABCDEFG"
        self.removeNoticesAll()

        if 'DebugLevel' in self.polyConfig['customParams']:
            LOGGER.debug('DebugLevel found in customParams')
            self.DebugLevel = self.polyConfig['customParams']['DebugLevel']
            LOGGER.debug('check_params: DebugLevel is: {}'.format(self.DebugLevel))
            if self.DebugLevel == '':
                LOGGER.debug('check_params: DebugLevel is empty')
                self.DebugLevel = int(logging.INFO)
                LOGGER.debug('check_params: DebugLevel is defined in customParams, but is blank - please update it.  Using {}'.format(self.DebugLevel))
                self.addNotice('Set \'DebugLevel\' and then restart')
                st = False
        else:
            LOGGER.debug('check_params: DebugLevel does not exist self.polyCconfig: {}'.format(self.polyConfig))
            self.DebugLevel = int(logging.INFO)
            LOGGER.debug('check_params: DebugLevel not defined in customParams, setting to {}'.format(self.DebugLevel))
            st = False

        # convert string to int
        self.DebugLevel = int(self.DebugLevel)

        # Set the debug level based on parameter
        LOGGER.setLevel(self.DebugLevel)
        LOGGER.warning('Setting debug level to {}'.format(self.DebugLevel))
        self.setDriver('GV0', self.DebugLevel)
        LOGGER.warning('Done setting debug level to {}'.format(self.DebugLevel))

        if 'MQTT_HOST' in self.polyConfig['customParams']:
            LOGGER.debug('MQTT_HOST found in customParams')
            self.MQTT_HOST = self.polyConfig['customParams']['MQTT_HOST']
            LOGGER.debug('check_params: MQTT_HOST is: {}'.format(self.MQTT_HOST))
            if self.MQTT_HOST == '' or self.MQTT_HOST == default_api_key:
                LOGGER.debug('check_params: MQTT_HOST is empty')
                self.MQTT_HOST = default_api_key
                LOGGER.debug('check_params: MQTT_HOST is defined in customParams, but is blank - please update it.  Using {}'.format(self.MQTT_HOST))
                self.addNotice('Set \'MQTT_HOST\' and then restart')
                st = False
        else:
            LOGGER.debug('check_params: MQTT_HOST does not exist self.polyCconfig: {}'.format(self.polyConfig))
            self.MQTT_HOST = default_api_key
            LOGGER.debug('check_params: MQTT_HOST not defined in customParams, please update it.  Using {}'.format(self.MQTT_HOST))
            self.addNotice('Set \'MQTT_HOST\' and then restart')
            st = False

        LOGGER.debug('Done checking: self.MQTT_HOST  = {}'.format(self.MQTT_HOST))
        LOGGER.debug('Done checking: self.DebugLevel = {}'.format(self.DebugLevel))

        # Make sure they are in the params
        self.addCustomParam({'DebugLevel': self.DebugLevel, 'MQTT_HOST': self.MQTT_HOST})

    def remove_notice_test(self,command):
        LOGGER.info('remove_notice_test: notices={}'.format(self.poly.config['notices']))
        # Remove all existing notices
        self.removeNotice('test')

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all: notices={}'.format(self.poly.config['notices']))
        # Remove all existing notices
        self.removeNoticesAll()

    def update_profile(self,command):
        LOGGER.info('update_profile:')
        st = self.poly.installprofile()
        return st

    def set_debug_level(self,command):
        self.DebugLevel = int(command['value'])
        LOGGER.warning("New debug level: {}".format(self.DebugLevel))
        self.setDriver('GV0', self.DebugLevel)
        LOGGER.setLevel(self.DebugLevel)

        # Make sure they are in the params
        self.addCustomParam({'DebugLevel': self.DebugLevel, 'MQTT_HOST': self.MQTT_HOST})

    def setOn(self, command):
       self.setDriver('ST', 1)

    def setOff(self, command):
       self.setDriver('ST', 0)

    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all,
        'REMOVE_NOTICE_TEST': remove_notice_test,
        'SET_DEBUG_LEVEL': set_debug_level,
    }
    drivers = [{'driver': 'ST',  'value': 0, 'uom': 2},
               {'driver': 'GV0', 'value': 0, 'uom': 25}
    ]

class VehicleNode(polyinterface.Node):
  def __init__(self, controller, primary, address, name, vehicleNumber):
    super(VehicleNode, self).__init__(controller, primary, address, name)
    self.vehicleNumber = vehicleNumber

  def handleMessage(self, statusItem, payload):
      LOGGER.debug('Vehicle MQTT message {}:{}'.format(statusItem, payload))

      d = {"state"                  : self.vehicle_state,
           "odometer"               : self.vehicle_odometer,
           "charge_limit_soc"       : self.vehicle_charge_limit_soc,
           "locked"                 : self.vehicle_locked,
           "est_battery_range_km"   : self.vehicle_est_battery_range_km,
           "rated_battery_range_km" : self.vehicle_rated_battery_range_km,
           "inside_temp"            : self.vehicle_inside_temp,
           "usable_battery_level"   : self.vehicle_usable_battery_level}
      try:
        LOGGER.debug('statusItem = "{}"'.format(statusItem))
        #LOGGER.debug('d = "{}"'.format(d))
        #LOGGER.info('Calling dict enttry')
        d[statusItem](payload)
        #LOGGER.info('Called  dict enttry')
      except KeyError:
        LOGGER.debug("Status item '{}' unimplemented".format(statusItem))

  def start(self):
    pass

  def shortPoll(self):
    LOGGER.debug('VehicleNode - shortPoll')

  def longPoll(self):
    LOGGER.debug('VehicleNode - longPoll')

  def setOn(self, command):
    LOGGER.debug("Vehicle setOn")
    self.setDriver('ST', 1)

  def setOff(self, command):
    LOGGER.debug("Vehicle setOff")
    self.setDriver('ST', 0)

  def query(self,command=None):
    self.reportDrivers()

  def vehicle_locked(self, payload):
    LOGGER.debug('lock status received: {}'.format(payload))
    if payload == "true":
      self.setDriver('GV7', 1)
    else:
      self.setDriver('GV7', 0)
    LOGGER.debug('lock status updated: {}'.format(payload))

  def vehicle_inside_temp(self, payload):
    LOGGER.debug('vehicle_inside_temp = {}'.format(payload))
    fahrenheit = (float(payload) * (9 / 5)) + 32;
    LOGGER.debug('fahrenheit = {}'.format(fahrenheit))
    self.setDriver('GV8', round(fahrenheit, 17))

  def vehicle_odometer(self, payload):
    miles = float(payload) * MILES_PER_KM;
    self.setDriver('GV6', round(miles, 2))

  def vehicle_est_battery_range_km(self, payload):
    miles = float(payload) * MILES_PER_KM;
    self.setDriver('GV3', round(miles, 2))

  def vehicle_rated_battery_range_km(self, payload):
    miles = float(payload) * MILES_PER_KM;
    self.setDriver('GV5', round(miles, 2))

  def vehicle_usable_battery_level(self, payload):
    self.setDriver('GV2', payload)

  def vehicle_charge_limit_soc(self, payload):
    self.setDriver('GV4', payload)

  def vehicle_state(self, payload):
    LOGGER.debug('vehicleNumber {} - state: {}'.format(self.vehicleNumber, payload))
    sleepState = {'asleep': 0,
                  'idle'  : 1,
                  'driving': 2,
                  'charging' : 3,
                  'suspended': 4}
    LOGGER.debug("Setting vehicle_state to {}".format(sleepState[payload]))
    self.setDriver('GV1', sleepState[payload])
    LOGGER.debug("Set     vehicle_state to {}".format(sleepState[payload]))
                
  # hint = [1,2,3,4]
  drivers = [{'driver': 'ST',  'value': 0, 'uom': 2},
             {'driver': 'GV0', 'value': 0, 'uom': 25},
             {'driver': 'GV1', 'value': 0, 'uom': 25},
             {'driver': 'GV2', 'value': 0, 'uom': 51},
             {'driver': 'GV3', 'value': 0, 'uom': 116},
             {'driver': 'GV4', 'value': 0, 'uom': 51},
             {'driver': 'GV5', 'value': 0, 'uom': 116},
             {'driver': 'GV6', 'value': 0, 'uom': 116},
             {'driver': 'GV7', 'value': 0, 'uom': 25},
             {'driver': 'GV8', 'value': 0, 'uom': 17},
  ]
  id = 'vehicle'
  commands = {
      'DON': setOn, 'DOF': setOff
  }

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('TeslaMateNS')
        """
        Instantiates the Interface to Polyglot.
        The name doesn't really matter unless you are starting it from the
        command line then you need a line Template=N
        where N is the slot number.
        """
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        control = Controller(polyglot)
        """
        Creates the Controller Node and passes in the Interface
        """
        control.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
