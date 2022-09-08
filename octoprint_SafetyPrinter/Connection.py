'''
 * Safety Printer Octoprint Plugin
 * Copyright (c) 2021~22 Rodrigo C. C. Silva [https://github.com/SinisterRj/Octoprint_SafetyPrinter]
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 * 
 '''

import os
import re
import sys
import glob
import threading
import serial
import serial.tools.list_ports
import time
import threading

if ((sys.platform == 'linux') or (sys.platform =='linux2')):
    import termios

class Connection():
    def __init__(self, plugin):

        self.compatibleFirmwareCommProtocol = ["5"]
        self.reducedComm = False;

        # Serial connection variables
        self.ports = []
        self._connected = False
        self.lastConnected = False
        self.serialConn = None
        self.connectedPort = ""
        self.waitingResponse = threading.Lock()
        self.totalmsgs = 0
        self.badmsgs = 0
        self.connFail = False
        self.abortSerialConn = False

        # Arrays for sensor status:
        self.interlockStatus = "F"
        self.tripReseted = False
        self.tripMsgcount = 0
        self.sensorLabel = []
        self.sensorEnabled = []
        self.sensorActive = []
        self.sensorActualValue = []
        self.sensorType = []
        self.sensorSP = []
        self.sensorTimer = []
        self.sensorForceDisable = []
        self.sensorTrigger = []
        self.sensorLowSP = []
        self.sensorHighSP = []
        self.sensorAlreadyNotifiedAlarm = []
        
        self.totalSensorsInitial = 0
        self.totalSensors = 0
        self.forceRenew = False
        self.forceRenewConn = False
        self.settingsVisible = False

        # Board warnings
        self.memWarning = "F"
        self.execWarning = "F"
        self.tempWarning = "F"
        self.voltWarning = "F"

        # Plug-in shortcuts
        #self._console_logger = plugin._logger #Change logger to octoprit.log - for debug only
        self._console_logger = plugin._console_logger
        self._logger = plugin._logger
        self._printer = plugin._printer
        self._printer_profile_manager = plugin._printer_profile_manager
        self._plugin_manager = plugin._plugin_manager
        self._identifier = plugin._identifier
        self._settings = plugin._settings

        #Firmware info
        self.FWVersion = ""
        self.FWReleaseDate = ""
        self.FWEEPROM = ""
        self.FWCommProtocol = ""
        self.FWValidVersion = False
        self.FWBoardType = ""

        #Octopod Integration
        helpers = self._plugin_manager.get_helpers("octopod", "apns_notification")
        if helpers and "apns_notification" in helpers:
            self.push_notification_Octopod = helpers["apns_notification"]
        '''
        #Printoid Integration
        helpers = self._plugin_manager.get_helpers("printoid", "fcm_notification")
        if helpers and "fcm_notification" in helpers:
            self.push_notification_Printoid = helpers["fcm_notification"]
        '''
        
        self.connect()        

    # *******************************  Functions to deal with Serial connections

    def connect(self):
        # Connects to Safety Printer Arduino through serial port
        #self._console_logger.info("Connecting...")
        self.connFail = False
        self.abortSerialConn = False
        self.terminal("Connecting...","Info")
        #self.ports = self.getAllPorts()
        #self._console_logger.info("Potential ports: %s" % self.ports)
        #self.terminal("Potential ports: %s" % self.ports,"Info")

        if (self._settings.get(["serialport"]) != "AUTO"): # and (self._settings.get(["serialport"]) not in self.ports)):
            self.ports.append(self._settings.get(["serialport"]))
            self.terminal("User selected port: %s" % self.ports,"Info")
        else:
            if (self._printer.get_current_connection()[1] == None):
                self.forceRenewConn = True
                self.connFail = True
                self.terminal("Can't connect on AUTO serial port if printer is not connected. Aborting Safety Printer MCU connection.","WARNING")
                self.update_ui_connection_status()
                return
            else:
                self.ports = self.getAllPorts()
                #self._console_logger.info("Potential ports: %s" % self.ports)
                self.terminal("Potential ports: %s" % self.ports,"Info")

        reconnect = None
        if self._printer.is_operational():
            # if an arduino nano or uno is used, it will reset upon connection, resseting the printer also.
            _, current_port, current_baudrate, current_profile = self._printer.get_current_connection()
            reconnect = (current_port, current_baudrate, current_profile)
            self.terminal("Printer is operational: port={}, baudrate={}, profile={}".format(current_port, current_baudrate, current_profile),"Info")

        if len(self.ports) > 0:
            for port in self.ports:
                
                if ((not self._connected) and ((self._settings.get(["serialport"]) == "AUTO") or (self._settings.get(["serialport"]) == port))):
                    if self.isPrinterPort(port,True):
                        #self._console_logger.info("Skipping Printer Port:" + port)
                        self.terminal("Skipping Printer Port:" + port,"Info")
                        if (self._settings.get(["serialport"]) == port):
                            self.terminal("Selected port is Printer Port. Please change it in settings:" + port,"WARNING")
                    else:
                        try:
                            self.terminal("Selected BAUD Rate:" + self._settings.get(["BAUDRate"]),"Info")
                            self.serialConn = serial.Serial(port, self._settings.get(["BAUDRate"]), timeout=0.5) #115200, timeout=0.5)
                            self._connected = True
                            self.connectedPort = port
                            self.terminal("Connected to: " + port,"Info")
                        except serial.SerialException as e:
                            self.forceRenewConn = True
                            self.connFail = True
                            self.terminal("Safety Printer MCU connection error: " + str(e),"ERROR")
                            self.update_ui_connection_status()

            if not self._connected:
                self.forceRenewConn = True
                self.connFail = True
                self.terminal("Couldn't connect on any port.","WARNING")
                self.update_ui_connection_status()
            else:
                responseStr = "" #self.serialConn.readline().decode()
                i = 0

                self.serialConn.flush()
                self.serialConn.write("<R6>".encode())

                try:
                    while responseStr.find("R6: Safety Printer MCU") == -1: # Wait for arduino boot and answer
                        i += 1                    
                        time.sleep(0.50)
                        self.terminal("Waiting Safety Printer MCU answer...","Info")
                        responseStr = self.serialConn.readline().decode() 
                        if responseStr:
                            self.terminal(responseStr,"Info")   
                        if i > 40:
                            self.forceRenewConn = True
                            self.connFail = True
                            self.terminal("Safety Printer MCU connection error: No answer.","ERROR")
                            self.closeConnection()
                            return
                except UnicodeDecodeError as e: #serial.SerialTimeoutException as e:
                    self.forceRenewConn = True
                    self.connFail = True
                    self.terminal("Safety Printer MCU connection error: " + str(e),"ERROR")
                    self.closeConnection()

                finally:
                    if (reconnect is not None) and (not self._printer.is_operational()):
                        # if printer was connected and now isn't (due to arduino reboot), reconnect
                        self.terminal("Waiting for printer boot (10s).","Info")
                        time.sleep(10.00)
                        port, baudrate, profile = reconnect
                        self.terminal("Reconnecting to printer: port={}, baudrate={}, profile={}".format(port, baudrate, profile),"Info")
                        self._printer.connect(port=port, baudrate=baudrate, profile=profile)

                self.terminal("Safety Printer MCU connected.","Info")
                self.totalmsgs = 0
                self.badmsgs = 0

                responseStr = self.newSerialCommand("<R4>",10, False)
                if ((responseStr) and (responseStr != "Error")):
                    vpos1 = responseStr.find(':',0)
                    vpos2 = responseStr.find(',',vpos1)
                    self.FWVersion = responseStr[vpos1+1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.FWReleaseDate = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.FWEEPROM = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.FWCommProtocol = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.FWBoardType = responseStr[vpos1:vpos2]


                    self.FWValidVersion = False
                    for version in self.compatibleFirmwareCommProtocol:
                        if version == self.FWCommProtocol:
                            self.FWValidVersion = True

                    if self.FWValidVersion:
                        self.forceRenewConn = True
                        self.reducedComm = False
                        self.update_ui_connection_status()
                    else:
                        self.forceRenewConn = True
                        self.terminal("Invalid firmware comunication protocol version: " + self.FWCommProtocol + ". Communication will be reduced to essentials and no configuration is allowed. It's highly recommended to update this plugin and/or safety printer MCU firmware.","WARNING")
                        self.reducedComm = True
                else:
                    self.forceRenewConn = True
                    self.connFail = True
                    self.terminal("Connected but no valid response.","ERROR")
                    self.closeConnection()

        else:
            self.forceRenewConn = True
            self.connFail = True
            self.terminal("No serial ports found.","WARNING")
            self.update_ui_connection_status()

    def closeConnection(self):
        # Disconnects Safety Printer Arduino
        if self._connected:
            self.serialConn.close()
            self.serialConn.__del__()
            self._connected = False
            self.terminal("Safety Printer MCU connection closed.","Info")
            self.update_ui_connection_status()
        else :
            self.terminal("Safety Printer MCU not connected.","Info")

    # below code "stolen" from https://gitlab.com/mosaic-mfg/palette-2-plugin/blob/master/octoprint_palette2/Omega.py
    #| Chip                | VID  | PID                      | Board                           | Link                                                                     | Note  
    #| Atmel ATMEGA16U2    | 2341 | 003D,003F,0042,0043,0044 | UNO, MEGA2560, ADK, DUE, clones | Included in Arduino software under drivers                               |  
    #| Atmel ATMEGA32U4    | 2341 | 8036 etc.                | Leonardo, micro, clones         | Included in Arduino software under drivers                               |  
    #| FTDI FT232RL        | 0403 | 6001                     | Nano, Duemilanove, MEGA, clones | http://www.ftdichip.com/Drivers/VCP.htm                                  | Included in Arduino software under drivers. Many fakes exist so avoid buying cheap Arduino compatible board with this chip.  
    #| WCH CH34X           | 1A86 | 5523, 7523 etc.          | Many clone boards               | http://www.wch.cn/download/CH341SER_ZIP.html                             | Supports win 10. Seems best choice for Arduino compatible boards.  
    #| Prolific PL2303     | 10CE |                          | Many clone boards               | http://www.prolific.com.tw/US/ShowProduct.aspx?p_id=225&pcid=41          | The company claims that many older PL2303 models on the market are fakes so it has stopped supplying drivers for win 7 and up on these models.  
    #| Silicon Labs CP210X | 11F6 |                          | Many clone boards               | https://www.silabs.com/products/mcu/Pages/USBtoUARTBridgeVCPDrivers.aspx | The driver may not work with win 10 so if you just upgraded to win 10 and your board stops working, … 
    # Source: https://forum.arduino.cc/t/help-me-confirm-some-vid-pid-and-comments-for-an-intall-tutorial/339586

    def getAllPorts(self):
        baselist = []
        
        arduinoVIDPID = ['.*2341:003D.*','.*2341:003F.*','.*2341:0042.*','.*2341:0043.*','.*2341:0044.*','.*0403:6001.*','.*0403:6015.*','.*1A86:5523.*','.*1A86:7523.*','.*2341:8036.*']

        '''
        if 'win32' in sys.platform:
            # use windows com stuff
            self._console_logger.info("Using a Windows machine") 

            for arduino in arduinoVIDPID:
                for port in serial.tools.list_ports.grep(arduino):
                    self._console_logger.info("got port %s" % port.device)
                    baselist.append(port.device)
        else:
            baselist = baselist + glob.glob('/dev/serial/by-id/*FTDI*') + glob.glob('/dev/*usbserial*') + glob.glob(
                '/dev/*usbmodem*') + glob.glob('/dev/serial/by-id/*USB_Serial*') + glob.glob('/dev/serial/by-id/usb-*')
            baselist = self.getRealPaths(baselist)

            for arduino in arduinoVIDPID:
                for port in baselist:
                    if port == serial.tools.list_ports.ListPortInfo
                    baselistfiltered.append(port)'''
        
        #Works for linux and windows:
        for arduino in arduinoVIDPID:
            for port in serial.tools.list_ports.grep(arduino):
                self._console_logger.info("Arduino port: %s" % port.device)
                baselist.append(port.device)

        # get unique values only
        baselist = list(set(baselist))  
        return baselist

    def getRealPaths(self, ports):
        self._console_logger.info("Paths: %s" % ports)
        for index, port in enumerate(ports):
            port = os.path.realpath(port)
            ports[index] = port
        return ports

    def isPrinterPort(self, selected_port, loggin):
        selected_port = os.path.realpath(selected_port)
        #printer_port = self._printer.get_current_connection()[1]
        if self._printer.get_current_connection()[0] == "Closed":
            if loggin:
                self._console_logger.info("No printer connected.")
            return False

        printer_port = os.path.realpath(self._printer.get_current_connection()[1])
                
        if loggin:
            self._console_logger.info("Trying port: %s" % selected_port)
            self._console_logger.info("Printer port: %s" % self._printer.get_current_connection()[1])
            self._console_logger.info("Printer port path: %s" % printer_port)
        # because ports usually have a second available one (.tty or .cu)
        printer_port_alt = ""
        if printer_port is None:
            return False
        else:
            if "tty." in printer_port:
                printer_port_alt = printer_port.replace("tty.", "cu.", 1)
            elif "cu." in printer_port:
                printer_port_alt = printer_port.replace("cu.", "tty.", 1)
            if loggin:
                self._console_logger.info("Printer port alt: %s" % printer_port_alt)
            if selected_port == printer_port or selected_port == printer_port_alt:
                return True
            else:
                return False

    def is_connected(self):
        return self._connected

    def resetTrip(self):
        self.tripReseted = True
        self.tripMsgcount = 0

    # *******************************  Functions to update info on knockout interface

    def update_ui_ports(self):
        # Send one message for each serial port detected
        self.ports = self.getAllPorts()
        for port in self.ports:
            if not self.isPrinterPort(port,True):
                self._plugin_manager.send_plugin_message(self._identifier, {"type": "serialPortsUI", "port": port})

    def update_ui_status(self):
        # Send one message for each sensor with all status
        if self._connected:            
            
            if (len(self.sensorLabel) == 0):
                self.update_ui_sensor_labels()
            
            responseStr = self.send_command("<R1>",10) 

            if ((responseStr == "Error") or (not(isinstance(responseStr, str)))):
                return

            numhash = responseStr.count('#')
            totalSensors = int(numhash)

            if totalSensors != self.totalSensorsInitial:
                self.sensorLabel = []
                return

            buffer = self.interlockStatus
            self.interlockStatus = responseStr[3] 
            if self.tripReseted:
                #wait 5 msgs after trip reset to consider a new trip if there is no change (user reseted with an alarm)
                self.tripMsgcount += 1

            # Prevent tripMsgCount overflow 
            if self.tripMsgcount > 10:
                self.tripMsgcount = 5 

            if ((self.interlockStatus != buffer) or (self.forceRenew) or (self.tripMsgcount > 5)):
                self.tripReseted = False
                self.tripMsgcount = 0
                if (self.interlockStatus == "T"):
                    self.terminal("New INTERLOCK detected.","TRIP")
                self._plugin_manager.send_plugin_message(self._identifier, {"type": "interlockUpdate", "interlockStatus": self.interlockStatus})

            buffer = self.memWarning
            self.memWarning = responseStr[5] 
            if ((self.memWarning != buffer) or (self.forceRenew)) and (self.memWarning == "T"):
                self.terminal("SafetyPrinter MCU low memory.","WARNING")

            buffer = self.execWarning
            self.execWarning = responseStr[7] 
            if ((self.execWarning != buffer) or (self.forceRenew)) and (self.execWarning == "T"):
                self.terminal("SafetyPrinter MCU high update cycle time.","WARNING")

            buffer = self.tempWarning
            self.tempWarning = responseStr[9]            
            if ((self.tempWarning != buffer) or (self.forceRenew)) and (self.tempWarning == "T"):
                if self._settings.get_boolean(["notifyVoltageTemp"]):
                    self.terminal("SafetyPrinter MCU board temperature out of safe limits.","WARNING")

            buffer = self.voltWarning
            self.voltWarning = responseStr[11]           
            if ((self.voltWarning != buffer) or (self.forceRenew)) and (self.voltWarning == "T"):
                if self._settings.get_boolean(["notifyVoltageTemp"]):
                    self.terminal("SafetyPrinter MCU board suply voltage out of safe limits.","WARNING")

            #self._plugin_manager.send_plugin_message(self._identifier, {"type": "warningUpdate", "memWarning": self.memWarning, "execWarning": self.execWarning, "tempWarning": self.tempWarning, "voltWarning": self.voltWarning})

            vpos1 = 12

            for x in range(totalSensors):
                vpos1 = responseStr.find('#',vpos1)
                vpos2 = responseStr.find(',',vpos1)
                
                if responseStr[vpos1+1:vpos2].isdigit():
                    index = int(responseStr[vpos1+1:vpos2])
                else :
                    return
                
                if (index >= 0 and index < totalSensors):

                    originalCRC = self.crc16(self.sensorEnabled[index] + self.sensorActive[index] + self.sensorActualValue[index] + self.sensorSP[index] + self.sensorTimer[index] + self.sensorTrigger[index])

                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorEnabled[index] = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorActive[index] = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorActualValue[index] = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorSP[index] = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorTimer[index] = responseStr[vpos1:vpos2]
                    vpos1 = vpos2 + 1
                    vpos2 = responseStr.find(',',vpos1)
                    self.sensorTrigger[index] = responseStr[vpos1:vpos2]

                    newCRC = self.crc16(self.sensorEnabled[index] + self.sensorActive[index] + self.sensorActualValue[index] + self.sensorSP[index] + self.sensorTimer[index] + self.sensorTrigger[index])

                    if ((originalCRC != newCRC) or (self.forceRenew)):   #avoid sending multiple msgs
                        self._plugin_manager.send_plugin_message(self._identifier, {"type": "statusUpdate", "sensorIndex": index, "totalSensors": totalSensors, "sensorLabel": self.sensorLabel[index], "sensorEnabled": self.sensorEnabled[index], "sensorActive": self.sensorActive[index], "sensorActualValue": self.sensorActualValue[index], "sensorType": self.sensorType[index], "sensorSP": self.sensorSP[index], "sensorTimer": self.sensorTimer[index], "sensorForceDisable": self.sensorForceDisable[index], "sensorTrigger": self.sensorTrigger[index], "sensorLowSP": self.sensorLowSP[index], "sensorHighSP": self.sensorHighSP[index]})
                        if (self.sensorActive[index] == "T" and not self.sensorAlreadyNotifiedAlarm[index]):
                            self.sensorAlreadyNotifiedAlarm[index] = True
                            if (self.sensorEnabled[index] == "T"):
                                self.terminal("New Alarm detected: "+ str(self.sensorLabel[index]) + " (" + str(self.sensorActualValue[index])+ ")","ALARM")
                            else :
                                self.terminal("New Alarm detected (disabled sensor): "+ str(self.sensorLabel[index]) + " (" + str(self.sensorActualValue[index])+ ")","INFO")                        
                        elif (self.sensorActive[index] == "F"):
                            self.sensorAlreadyNotifiedAlarm[index] = False

            if (self.forceRenew): # send all msgs again to update UI
                self.forceRenew = False
        else :
            self.update_ui_connection_status()

    def update_ui_sensor_labels(self):
        # Update local arrays with sensor labels and type. create items for all the other properties. Should run just after connection, only one time or when the number of sensor status sended by arduino changes
        responseStr = self.send_command("<R2>",10)
        
        if ((responseStr == "Error") or (not(isinstance(responseStr, str)))):
                return
        
        numhash = responseStr.count('#')
        vpos1 = 0
        vpos2 = 0
        self.totalSensorsInitial = int(numhash)
        
        for x in range(self.totalSensorsInitial):
            vpos1 = responseStr.find('#',vpos1)
            vpos2 = responseStr.find(',',vpos1)
        
            if responseStr[vpos1+1:vpos2].isdigit():
                index = int(responseStr[vpos1+1:vpos2])
            else :
                return
        
            vpos1 = vpos2 + 1
            vpos2 = responseStr.find(',',vpos1)
        
            if index >= len(self.sensorLabel) :
                self.sensorLabel.append(responseStr[vpos1:vpos2])
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorType.append(responseStr[vpos1:vpos2])
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorForceDisable.append(responseStr[vpos1:vpos2])
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorLowSP.append(responseStr[vpos1:vpos2])
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorHighSP.append(responseStr[vpos1:vpos2])

                
                self.sensorTrigger.append("F")
                self.sensorEnabled.append("")
                self.sensorActive.append("")
                self.sensorActualValue.append("")
                self.sensorSP.append("")
                self.sensorTimer.append("")
                self.sensorAlreadyNotifiedAlarm.append(False)

            else :
                self.sensorLabel[index] = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorType[index] = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorForceDisable[index] = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorLowSP[index] = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                self.sensorHighSP[index] = responseStr[vpos1:vpos2]

                self.sensorTrigger[index] = "F"
                self.sensorEnabled[index] = ""
                self.sensorActive[index] = ""
                self.sensorActualValue[index] = ""
                self.sensorSP[index] = ""
                self.sensorTimer[index] = ""
                self.sensorAlreadyNotifiedAlarm[index] = False

    def update_ui_connection_status(self):
        # Updates knockout connection status

        if ((self.settingsVisible) or (self.forceRenewConn)):
            self._plugin_manager.send_plugin_message(self._identifier, {"type": "connectionUpdate", "connectionStatus": self._connected, "port": self.connectedPort, "totalmsgs": self.totalmsgs, "badmsgs": self.badmsgs, "failure" : self.connFail, "reduced" : self.reducedComm})    
            if (self.forceRenewConn):
                self.forceRenewConn = False
                self._plugin_manager.send_plugin_message(self._identifier, {"type": "firmwareInfo", "version": self.FWVersion, "releaseDate": self.FWReleaseDate, "EEPROM": self.FWEEPROM, "CommProtocol":self.FWCommProtocol, "ValidVersion": self.FWValidVersion, "BoardType": self.FWBoardType})
        else:
            if self.lastConnected != self._connected:
                self.lastConnected = self._connected
                self._plugin_manager.send_plugin_message(self._identifier, {"type": "connectionUpdate", "connectionStatus": self._connected, "port": self.connectedPort, "totalmsgs": self.totalmsgs, "badmsgs": self.badmsgs, "failure" : self.connFail, "reduced" : self.reducedComm})    

    def update_MCU_Stats(self):
        # Update local vars with MCU status. Send data to update Settings Tab
        if not self.reducedComm:
            responseStr = self.newSerialCommand("<R5>",10, False)
            if ((responseStr) and (responseStr != "Error")):
                vpos1 = responseStr.find(':',0)
                vpos2 = responseStr.find(',',vpos1)
                MCUSRAM = responseStr[vpos1+1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                MCUTemp = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                MCUVolts = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                MCUMaxTime = responseStr[vpos1:vpos2]
                vpos1 = vpos2 + 1
                vpos2 = responseStr.find(',',vpos1)
                MCUAvgTime = responseStr[vpos1:vpos2]

                self._plugin_manager.send_plugin_message(self._identifier, {"type": "MCUInfo", "volts": MCUVolts, "temp": MCUTemp, "ram": MCUSRAM, "maxTime": MCUMaxTime, "avgTime": MCUAvgTime})  


    def terminal(self,msg,ttype):
        if self._settings.get_boolean(["showTerminal"]):
            self._plugin_manager.send_plugin_message(self._identifier, {"type": "terminalUpdate", "line": msg, "terminalType": ttype})

        ttype = ttype.lower()

        # Pops up the error msg to user.
        if (ttype == "debug") or (ttype == "send") or (ttype == "recv"):
            self._console_logger.debug(msg)

        elif ttype == "info":
            self._console_logger.info(msg)

        elif ttype == "trip":
            self._console_logger.info(msg)
            popup = "\U0001F6D1 " "SafetyPrinter " + msg
            self.app_notification(popup)

        elif ttype == "alarm":
            self._console_logger.info(msg)
            popup = "\U0001F514 " "SafetyPrinter " + msg
            self.app_notification(popup)            

        elif ttype == "warning":
            self._console_logger.warning(msg)
            
            if self._settings.get_boolean(["notifyWarnings"]):
                popup = "WARNING: " + msg
                self._plugin_manager.send_plugin_message(self._identifier, {"type": "warning", "warningMsg": popup})
                popup = "\U000026A0 " "SafetyPrinter " + popup
                self.app_notification(popup)

        elif  ttype == "error":
            self._console_logger.error(msg)
            popup = "ERROR: " + msg
            self._plugin_manager.send_plugin_message(self._identifier, {"type": "error", "errorMsg": popup})
            popup = "\U000026A0 " + "SafetyPrinter " + popup
            self.app_notification(popup)


        elif ttype == "critical":
            self._console_logger.critical(msg) 
            popup = popup + "CRITICAL ERROR: " + msg
            self._plugin_manager.send_plugin_message(self._identifier, {"type": "error", "errorMsg": popup})
            popup = "\U000026A0 " + popup
            self.app_notification(popup)

    # ****************************************** Functions to interact with Arduino when connected

    def newSerialCommand(self,serialCommand, timeout, force): 
        # Used for 1 time only commands. Keeps tring if no arduino response until timeout (s) expires.
        i = 0
        if self.reducedComm and not force:
            self.terminal("Serial command (" + serialCommand + ") blocked due to a invalid firmware communication protocoll.","WARNING")
            return
        vpos1 = serialCommand.find('<',0)
        vpos2 = serialCommand.find('>',0)
        if ((vpos1 > -1) and  (vpos2 > -1) and (vpos2 - vpos1 > 1)):            
            responseStr = self.send_command(serialCommand,10)
            while ((responseStr == "Error") or (not responseStr)) and (not self.abortSerialConn):
                time.sleep(0.5)
                i += 1            
                if i > 0:
                    self.terminal("newSerialCommand:Serial port is busy or bad answer. Retring command:" + serialCommand + " x" + str(i),"DEBUG")
                if i >= 10:
                    self.closeConnection()
                    break
                responseStr = self.send_command(serialCommand,timeout)
            return responseStr
        else:
            self.terminal("'" + serialCommand + "' is not a valid command.","WARNING")


    def crc16(self, data: str):
        '''
        CRC-16 Algorithm
        Adapted from:
        https://forum.arduino.cc/t/simple-checksum-that-a-noob-can-use/300443

        uint16_t _crc16_update(uint16_t crc, uint8_t a)
        {
          int i;
          crc ^= a;
          for (i = 0; i < 8; ++i)
          {
            if (crc & 1)
            crc = (crc >> 1) ^ 0xA001;
            else
            crc = (crc >> 1);
          }
          return crc;
        }

        '''
        data = data.encode() 
        #data = bytearray(data)
        crc = 0
        for a in data:
            crc ^= a
            for _ in range(0, 8):
                if (crc & 1): 
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = (crc >> 1)
        return crc

    def crcCheck(self, data: str):
        # Checks CRC from received msg

        self.totalmsgs += 1
        vpos1 = data.find('$',0)  
        vpos2 = data.find('$',vpos1+1)      
        arduinoCRC = int(data[vpos1+1:vpos2])
        payload = data[vpos2+1:len(data)]
        calculatedCRC = self.crc16(payload)
        if arduinoCRC == calculatedCRC:  
            return data[0:vpos1] + payload
        else:
            self.terminal("crcCheck:BAD CRC: arduinoCRC:" + str(arduinoCRC) + " calculatedCRC:" + str(calculatedCRC) + " payload:" + payload,"DEBUG")
            self.badmsgs += 1
            return False


    def send_command(self, command, timeout=-1):
        # send serial commands to arduino and receives the answer

        if not self.waitingResponse.acquire(True, timeout):
            return "Error"

        if self.is_connected() and not self.abortSerialConn:
            try:
                self.serialConn.flush()
                self.terminal(command.strip(), "Send")
                self.serialConn.write(command.encode())
                data = ""
                keepReading = True

                while keepReading:
                    time.sleep(0.05)
                    if self.is_connected():
                        newline = self.serialConn.readline()
                    if not newline.strip():
                        keepReading = False
                    else:
                        data += newline.decode()
                
                if data: 
                    data = data.strip()
                    if ((command.lower() == "<r1>") or (command.lower() == "<r2>") or (command.lower() == "<r4>") or (command.lower() == "<r5>")):
                        data = self.crcCheck(data)
                        if not data:
                            self.waitingResponse.release()
                            self.terminal("send_command:["+ command +"] Bad CRC.", "DEBUG")
                            return "Error"

                    self.terminal(data, "Recv")

                    vpos1 = command.find('<',0)
                    vpos2 = command.find('>',0)
                    vpos3 = command.find(' ',0)
                    if vpos3 > -1:
                        sendedCmd = command[vpos1+1:vpos3]
                    else:
                        sendedCmd = command[vpos1+1:vpos2]

                    vpos1 = data.find(':',0)
                    receivedCmd = data[0:vpos1]
                    
                    if receivedCmd == sendedCmd:
                        self.waitingResponse.release()
                        return str(data)
                    else:
                        self.terminal("send_command:Answer ("+ receivedCmd +") doesn't contains command ID:" + sendedCmd, "DEBUG")
                        self.waitingResponse.release()
                        return "Error"
                else:
                    self.terminal("send_command:["+ command +"] Received no data", "DEBUG")
                    return "Error"  
            
            except (serial.SerialException, termios.error): #, termios.error):
                self.waitingResponse.release()
                if (not self.abortSerialConn) :
                    self.terminal("Safety Printer communication error.", "ERROR")
                    self.closeConnection()
                return "Error"

        else:
            self.waitingResponse.release()
            return "Error"

        self.waitingResponse.release()

    # ****************************************** Extra Functions

    def app_notification(self, msg):
        #Octopod notification
        try:
            self.push_notification_Octopod(msg)
        except AttributeError:
            pass  
        '''
        #Printoid notification
        try:
            self.push_notification_Printoid(msg)
        except AttributeError:
            pass  
        '''
