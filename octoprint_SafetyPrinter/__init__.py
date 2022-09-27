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
 * 
 *  Change log:
 *  
 * Version 1.2.0
 * 27/09/22 
 * 1) Include <r4> command in connection to receive answer from Arduino Leonardo;
 * 2) Arduino Leonardo VID & PID included on auto detect ports;
 * 3) Limits terminal lines to 300, as Octoprint's terminal;
 * 4) Include timeout as argument on newSerialCommand function;
 * 5) Make MCU voltage and temperature warnings optional;
 * 6) Include force as argument on newSerialCommand function;
 * 7) Include firmware flash ability;
 * 8) Include "save" button on serial port change on settings;
 * 9) Include persistence to terminal filter;
 * 10) Add threading lock to send_command.
 *
 *
 * Version 1.1.0
 * 17/06/2021
 * 1) Include CRC check from <r1>, <r2>, <r4> and <r5> command responses (communication protocol rev. 2),
 * 2) Improve logging and notifications,
 * 3) Add MCU info to settings tab,
 * 4) Add BAUD rate to settings tab,
 * 5) More Themeify and UI Customizer friendly,
 * 6) Remake terminal filters;
 * 7) Include terminal local commands (@connect, @disconnect);
 * 8) Include Alarms and Trips on terminal;
 * 9) Python-JS messages sanitization;
 * 10) Fix bug that writes eeprom after first change, with settings multiple changes;
 * 11) Fix bug that keeps "Connecting" status if connection fails;
 * 12) Remove unnecessary Knockout bindings;
 * 13) Include a better navibar icon management.
 * 14) Adds emoji to terminal;
 * 15) Warns user if selected port is printer port;
 * 16) Allow user defined serial port;
 * 17) Dynamicaly changes terminal lenght based on window lenght;
 * 18) Terminal checks for commands endmarks on user sended strings;
 * 19) Fix some bugs on shutdonw warning banner;
 * 20) Adds terminal command history;
 * 21) Fix a bug that saves wrong sensor data when connect thru setting tab and hit save;
 * 22) Fix a bug that warns disconnection as communication fault.
 * 23) Reconnects printer after Safetyprinter connection.
 * 24) Increase to 20s the printer connection timeout.
 * 

 '''

# coding=utf-8
from __future__ import absolute_import
import logging
import logging.handlers
import octoprint.plugin
import serial
import time
import flask
from . import Connection
from octoprint.util import RepeatedTimer
from octoprint.events import eventManager, Events
from octoprint.server import user_permission
import tempfile
import threading
import shutil
from octoprint.server import admin_permission, NO_CONTENT
from octoprint_SafetyPrinter.methods import avrdude
import os

totalSensors = 0

class SafetyPrinterPlugin(
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.ShutdownPlugin):

    def __init__(self):
        self.abortTimeout = 0
        self.rememberCheckBox = False
        self.lastCheckBoxValue = False
        self.turnOffPrinter = True
        self._automatic_shutdown_enabled = False        
        self._timeout_value = None
        self._abort_timer = None
        self._wait_for_timelapse_timer = None
        self.loggingLevel = 0
        self._flash_thread = None

    def initialize(self):
        self._console_logger = logging.getLogger("octoprint.plugins.safetyprinter")
        
    def new_connection(self):
        self._console_logger.info("Attempting to connect to Safety Printer MCU ...")
        self.conn = Connection.Connection(self)
        self.startTimer(1.0)

    def startTimer(self, interval):
        # timer that updates UI with Arduino information
        self._commTimer = RepeatedTimer(interval, self.updateStatus, None, None, True)
        self._commTimer.start()

    def updateStatus(self):
        # Update UI status (connection, trip and sensors)
        if self.conn:            
            self.conn.update_ui_connection_status()
            if self.conn.is_connected():
                self.conn.update_ui_status()
            else:
                self._commTimer.cancel()

    # ~~ StartupPlugin mixin
    def on_startup(self, host, port):
        console_logging_handler = logging.handlers.RotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="console"), maxBytes=2 * 1024 * 1024)
        console_logging_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        #console_logging_handler.setLevel(logging.DEBUG)

        self._console_logger.addHandler(console_logging_handler)
        self.loggingLevel = self._settings.get_int(["loggingLevel"])
        self._console_logger.setLevel(self.loggingLevel)
        #self.console_setlevel(self.loggingLevel)
        self._console_logger.propagate = False

    def on_after_startup(self):
        self._logger.info("Safety Printer Plugin started.") #Octoprint logger 
        self._console_logger.info("******************* Starting Safety Printer Plug-in ***************************")
        self._console_logger.info("Default Serial Port:" + str(self._settings.get(["serialport"])))
        self._console_logger.info("Default BAUD rate:" + str(self._settings.get(["BAUDRate"])))
        self.new_connection()

        self.abortTimeout = self._settings.get_int(["abortTimeout"])
        self._console_logger.debug("abortTimeout: %s" % self.abortTimeout)

        self.rememberCheckBox = self._settings.get_boolean(["rememberCheckBox"])
        self._console_logger.debug("rememberCheckBox: %s" % self.rememberCheckBox)

        self.lastCheckBoxValue = self._settings.get_boolean(["lastCheckBoxValue"])
        self._console_logger.debug("lastCheckBoxValue: %s" % self.lastCheckBoxValue)
        if self.rememberCheckBox:
            self._automatic_shutdown_enabled = self.lastCheckBoxValue

        self.showTerminal = self._settings.get_boolean(["showTerminal"])
        self._console_logger.debug("showTerminal: %s" % self.showTerminal)

        self.loggingLevel = self._settings.get(["loggingLevel"])
        self._console_logger.debug("loggingLevel: %s" % self.loggingLevel)

        self.notifyVoltageTemp = self._settings.get_boolean(["notifyVoltageTemp"])
        self._console_logger.debug("notifyVoltageTemp: %s" % self.notifyVoltageTemp)

        self._console_logger.debug("avrdude_path: %s" % self._settings.get(["avrdude_path"]))

    # ~~ ShutdonwPlugin mixin
    def on_shutdown(self):
        self._console_logger.info("#############################  on_shutdown")
        self._console_logger.info("Disconnecting from Safety Printer MCU...")
        self._commTimer.cancel()
        self.conn.abortSerialConn = True
        self.conn.closeConnection()        
                            
    ##~~ SettingsPlugin mixin    
    def get_settings_defaults(self):
        return dict(
            serialport="AUTO",
            BAUDRate="38400",
            abortTimeout = 30,
            rememberCheckBox = False,
            lastCheckBoxValue = False,
            turnOffPrinter = True,
            showTerminal = False,
            loggingLevel = "INFO",
            notifyWarnings = True,
            useEmoji = True,
            additionalPort = "",
            notifyVoltageTemp = True,
            avrdude_path = "/usr/bin/avrdude",
            terminalMsgFilter = False
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        self.abortTimeout = self._settings.get_int(["abortTimeout"])
        self.rememberCheckBox = self._settings.get_boolean(["rememberCheckBox"])
        self.lastCheckBoxValue = self._settings.get_boolean(["lastCheckBoxValue"])
        self.turnOffPrinter = self._settings.get_boolean(["turnOffPrinter"])
        self.showTerminal = self._settings.get_boolean(["showTerminal"])
        self.loggingLevel = self._settings.get_int(["loggingLevel"]) 
        #self.notifyVoltageTemp = self._settings.get_boolean(["notifyVoltageTemp"])
        #self._console_logger.setLevel(self.loggingLevel)
        
        self._console_logger.info("User changed settings.")
        self._console_logger.debug("serialport: %s" % self._settings.get(["serialport"]))
        self._console_logger.debug("BAUDRate: %s" % self._settings.get(["BAUDRate"]))
        self._console_logger.debug("abortTimeout: %s" % self.abortTimeout)
        self._console_logger.debug("rememberCheckBox: %s" % self.rememberCheckBox)
        self._console_logger.debug("lastCheckBoxValue: %s" % self.lastCheckBoxValue)
        self._console_logger.debug("showTerminal: %s" % self.showTerminal)
        self._console_logger.debug("loggingLevel: %s" % self.loggingLevel)
        self._console_logger.debug("notifyWarnings: %s" % self._settings.get(["notifyWarnings"]))
        self._console_logger.debug("useEmoji: %s" % self._settings.get(["useEmoji"]))
        self._console_logger.debug("additionalPort: %s" % self._settings.get(["additionalPort"]))
        self._console_logger.debug("notifyVoltageTemp: %s" % self._settings.get(["notifyVoltageTemp"]))
        self._console_logger.debug("avrdude_path : %s" % self._settings.get(["avrdude_path"]))


    def get_template_vars(self):
        return dict(
            serialport=self._settings.get(["serialport"]),
            loggingLevel=self._settings.get(["loggingLevel"]),
        )

    ##~~ AssetPlugin mixin
    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True),
            #dict(type="navbar", custom_bindings=False),
            dict(type="sidebar", name="Safety Printer", custom_bindings=False, icon="fire"),
            dict(type="tab", name="Safety Printer", custom_bindings=False, icon="fire"),
        ]

    def get_assets(self):
        return dict(
            js=["js/SafetyPrinter.js"],
            css=["css/SafetyPrinter.css"] #,
            #less=["less/SafetyPrinter.less"]
          )

    ##~~ Softwareupdate hook
    def get_update_information(self):
        return dict(
            SafetyPrinter=dict(
                displayName="Safety Printer",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="SinisterRj",
                repo="Octoprint_SafetyPrinter",
                current=self._plugin_version,

                stable_branch=dict(
                    name="Stable", branch="main", comittish=["main"]
                ),
                prerelease_branches=[
                    dict(
                        name="Release Candidate",
                        branch="devel",
                        comittish=["devel", "main"],
                    )
                ],

                # update method: pip
                pip="https://github.com/SinisterRj/Octoprint_SafetyPrinter/archive/refs/tags/{target_version}.zip"
             )
          )
    
    # Simple API commands. Deal with UI commands

    def get_api_commands(self):
        return dict(
            reconnect=[],
            disconnect=[],
            resetTrip=[],
            sendTrip=[],
            getPorts=[],
            toggleEnabled=["id", "onoff"],
            changeSP=["id", "newSP"],
            changeTimer=["id", "newTimer"],
            sendCommand=["serialCommand"],
            resetSettings=["id"],
            saveEEPROM=[],
            enableShutdown=[],
            disableShutdown=[],
            abortShutdown=[],
            refreshMCUStats=[],
            forceRenew=[],
            settingsVisible=["status"],
            flashFile=["fileName"]
        )

    def on_api_command(self, command, data):
        try:
            if command == "reconnect":
                self.new_connection()
            elif command == "disconnect":
                self.on_shutdown()
            elif command == "resetTrip":
                self.resetTrip()
            elif command == "sendTrip":
                self.sendTrip()
            elif command == "getPorts":
                self.conn.update_ui_ports()
            elif command == "toggleEnabled":
                self.toggleEnabled(int(data["id"]), str(data["onoff"]))
            elif command == "changeSP":
                self.changeSP(int(data["id"]), str(data["newSP"]))
            elif command == "changeTimer":
                self.changeTimer(int(data["id"]), str(data["newTimer"]))
            elif command == "sendCommand":
                self.sendCommand(str(data["serialCommand"]))
            elif command == "resetSettings":
                self.resetSettings(int(data["id"]))    
            elif command == "saveEEPROM":
                self.saveEEPROM()
            elif command == "enableShutdown":
                self.enableShutdown()
            elif command == "disableShutdown":
                self.disableShutdown()
            elif command == "abortShutdown":
                self.abortShutdown()
            elif command == "refreshMCUStats":
                self.refreshMCUStats()
            elif command == "forceRenew":
                self.forceRenew()
            elif command == "settingsVisible":
                self.settingsVisible(bool(data["status"]))
            elif command == "flashFile":
                self.flashFile(str(data["fileName"]))
            response = "POST request (%s) successful" % command
            return flask.jsonify(response=response, data=data, status=200), 200
        except Exception as e:
            error = str(e)
            self._console_logger.info("Exception message: %s" % str(e))
            return flask.jsonify(error=error, status=500), 500

    def resetTrip(self):
        if self.conn:
            if self.conn.is_connected():
                self.conn.resetTrip()
                self._console_logger.info("Resseting ALL trips.")
                self.conn.newSerialCommand("<C1>",10, False)
            
    def sendTrip(self):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Virtual Emergency Button pressed.")            
                self.conn.newSerialCommand("<C2>",10, True)

    def toggleEnabled(self, index, status):
        if self.conn:
            if self.conn.is_connected():
                if status == "on":
                    self._console_logger.info("Enabling sensor #" + str(index))
                else:
                    self._console_logger.info("Disabling sensor #" + str(index))
                self.conn.newSerialCommand("<C3 " + str(index) + " " + status + ">",10, False)

    def changeSP(self, index, newSP):
        if self.conn:            
            if self.conn.is_connected():
                self._console_logger.info("Changing sensor #" + str(index) + " setpoint to:" + newSP)
                self.conn.newSerialCommand("<C4 " + str(index) + " " + newSP + ">",10, False)

    def changeTimer(self, index, newTimer):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Changing sensor #" + str(index) + " timer to:" + newTimer)
                self.conn.newSerialCommand("<C7 " + str(index) + " " + newTimer + ">",10, False)

    def sendCommand(self,newCommand):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Sending terminal command: " + newCommand)
                self.conn.newSerialCommand(newCommand,10, False)
    
    def resetSettings(self, index):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Loading sensor #" + str(index) + " default configurations.")
                self.conn.newSerialCommand("<C8 " + str(index) + ">",10, False)

    def saveEEPROM(self):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Saving configuration to EEPROM.")
                self.conn.newSerialCommand("<C5>",10, False)

    def toggleShutdown(self):
        self.lastCheckBoxValue = self._automatic_shutdown_enabled
        if self.rememberCheckBox:
            self._settings.set_boolean(["lastCheckBoxValue"], self.lastCheckBoxValue)
            self._settings.save()
            eventManager().fire(Events.SETTINGS_UPDATED)
        self._plugin_manager.send_plugin_message(self._identifier, {"type":"shutdown","automaticShutdownEnabled": self._automatic_shutdown_enabled, "timeout_value":self._timeout_value})
    
    def enableShutdown(self):
        self._automatic_shutdown_enabled = True
        self.toggleShutdown()

    def disableShutdown(self):
        self._automatic_shutdown_enabled = False
        self.toggleShutdown()        

    def abortShutdown(self):
        if self._wait_for_timelapse_timer is not None:
                self._wait_for_timelapse_timer.cancel()
                self._wait_for_timelapse_timer = None
        if self._abort_timer is not None:
                self._abort_timer.cancel()
                self._abort_timer = None
        self._timeout_value = None
        self._plugin_manager.send_plugin_message(self._identifier, {"type":"shutdown","automaticShutdownEnabled": self._automatic_shutdown_enabled, "timeout_value":self._timeout_value})
        self._console_logger.info("Shutdown aborted.")
    
    def refreshMCUStats(self):
        if self.conn:
            if self.conn.is_connected():
                self._console_logger.info("Refreshing MCU status.")
                self.conn.update_MCU_Stats()

    def forceRenew(self):
        if self.conn:
            self.conn.forceRenew = True
            self.conn.forceRenewConn = True
            self.conn.terminal("Renew UI status.","INFO")

    def settingsVisible(self,status):
        if self.conn:
            self.conn.settingsVisible = status

    '''def flashFile(self, fileName):
        if self.conn:
            self._console_logger.info("Flashing new firmware to MCU (" + fileName + ").")
            self.conn.flashFirmware(fileName)
    '''

    def on_event(self, event, payload):

        if event == Events.CLIENT_OPENED:
            self._plugin_manager.send_plugin_message(self._identifier, {"type":"shutdown","automaticShutdownEnabled": self._automatic_shutdown_enabled, "timeout_value":self._timeout_value})
            return
       
        if not self._automatic_shutdown_enabled:
            return
        
        if not self._settings.global_get(["server", "commands", "systemShutdownCommand"]):
            self._console_logger.warning("systemShutdownCommand is not defined. Aborting shutdown...")
            return

        if event not in [Events.PRINT_DONE, Events.PRINT_FAILED]:
            return

        if event == Events.PRINT_FAILED and not self._printer.is_closed_or_error():
            #Cancelled job
            return
        
        if event in [Events.PRINT_DONE, Events.PRINT_FAILED]:
            webcam_config = self._settings.global_get(["webcam", "timelapse"], merged=True)
            timelapse_type = webcam_config["type"]
            if (timelapse_type is not None and timelapse_type != "off"):
                    self._wait_for_timelapse_start()
            else:
                    self._timer_start()
            return

    def _wait_for_timelapse_start(self):
        if self._wait_for_timelapse_timer is not None:
                return

        self._wait_for_timelapse_timer = RepeatedTimer(5, self._wait_for_timelapse)
        self._wait_for_timelapse_timer.start()

    def _wait_for_timelapse(self):
        c = len(octoprint.timelapse.get_unrendered_timelapses())

        if c > 0:
                self._console_logger.info("Waiting for %s timelapse(s) to finish rendering before starting shutdown timer..." % c)
        else:
                self._timer_start()

    def _timer_start(self):
        if self._abort_timer is not None:
                return

        if self._wait_for_timelapse_timer is not None:
                self._wait_for_timelapse_timer.cancel()

        self._console_logger.info("Starting abort shutdown timer.")
        
        self._timeout_value = self.abortTimeout
        self._abort_timer = RepeatedTimer(1, self._timer_task)
        self._abort_timer.start()

    def _timer_task(self):
        if self._timeout_value is None:
                return

        self._timeout_value -= 1
        self._plugin_manager.send_plugin_message(self._identifier, {"type":"shutdown", "automaticShutdownEnabled": self._automatic_shutdown_enabled, "timeout_value":self._timeout_value})
        if self._timeout_value <= 0:
                if self._wait_for_timelapse_timer is not None:
                        self._wait_for_timelapse_timer.cancel()
                        self._wait_for_timelapse_timer = None
                if self._abort_timer is not None:
                        self._abort_timer.cancel()
                        self._abort_timer = None
                self._shutdown_system()

    def _shutdown_system(self):
        if self.turnOffPrinter:
            if self.conn.is_connected():
                self._console_logger.info("Turning off the printer.")
                self.conn.newSerialCommand("<C6 off>",10, False)           

        shutdown_command = self._settings.global_get(["server", "commands", "systemShutdownCommand"])
        self._console_logger.info("Shutting down system with command: {command}".format(command=shutdown_command))
        try:
            import sarge            
            self._console_logger.info("**************** SHUT DOWN ******************")
            p = sarge.run(shutdown_command, async_=True)
        except Exception as e:
            self._console_logger.exception("Error when shutting down: {error}".format(error=e))
            return

    #~~ BluePrint API

    def is_blueprint_csrf_protected(self):
        return True

    @octoprint.plugin.BlueprintPlugin.route("/status", methods=["GET"])
    @octoprint.server.util.flask.restricted_access
    def status(self):
        return flask.jsonify(flashing=self._flash_thread is not None)

    @octoprint.plugin.BlueprintPlugin.route("/flash", methods=["POST"])
    @octoprint.server.util.flask.restricted_access
    @octoprint.server.admin_permission.require(403)
    def flash_firmware(self):

        if not self.conn or not self.conn.is_connected():
            error_message = "Safety Printer MCU must be connected to flash."
            self._send_status("flasherror", subtype="notconnected", message=error_message)
            self.conn.terminal(error_message,"ERROR")            
            return flask.make_response(NO_CONTENT)

        if self._printer.is_printing():
            error_message = "Cannot flash firmware, printer is busy"
            self._send_status("flasherror", subtype="busy", message=error_message)
            self.conn.terminal(error_message,"ERROR")
            return flask.make_response(NO_CONTENT)

        value_source = flask.request.json if flask.request.json else flask.request.values

        if not "port" in value_source:
            error_message = "Cannot flash firmware, Safety Printer MCU port was not specified."
            self._send_status("flasherror", subtype="port", message=error_message)
            self.conn.terminal(error_message,"ERROR")
            return flask.make_response(NO_CONTENT)

        mcu_port = value_source["port"]

        self._settings.save()

        if not avrdude._check_avrdude(self):
            error_message = "Cannot flash firmware, AVRDude path is invalid"
            self._send_status("flasherror", subtype="path", message=error_message)
            self.conn.terminal(error_message,"ERROR")
            return flask.make_response(NO_CONTENT)

        file_to_flash = None

        input_name = "file"
        input_upload_path = input_name + "." + self._settings.global_get(["server", "uploads", "pathSuffix"])

        if input_upload_path in flask.request.values:
            # flash from uploaded file
            uploaded_hex_path = flask.request.values[input_upload_path]

            try:
                file_to_flash = tempfile.NamedTemporaryFile(mode='r+b', delete=False)
                file_to_flash.close()
                shutil.move(os.path.abspath(uploaded_hex_path), file_to_flash.name)
            except:
                if file_to_flash:
                    try:
                        os.remove(file_to_flash.name)
                    except:
                        self.conn.terminal("Error while trying to delete the temporary hex file.","DEBUG")
                error_message = "Error while copying the uploaded hex file."
                self.conn.terminal(error_message,"ERROR")
                self._send_status("flasherror", subtype="hexfile", message=error_message)

        if self._start_flash_process(file_to_flash.name, mcu_port):
            return flask.make_response(NO_CONTENT)
        else:
            error_message = "Cannot flash firmware, already flashing"
            self._send_status("flasherror", subtype="already_flashing")
            self.conn.terminal(error_message,"WARNING")
            return flask.make_response(NO_CONTENT)

    def _start_flash_process(self, hex_file, mcu_port):
        
        if self.conn:
            if self.conn.is_connected():
                self.conn.terminal("Starting Safety Printer MCU flashing on port: " + mcu_port + ".","INFO")
                self._send_status("progress", subtype="boardreset")
                self.conn.newSerialCommand("<C9 0>",10 , True)
                
                if self._flash_thread is not None:
                    return False

                self._flash_thread = threading.Thread(target=self._flash_worker, args=(hex_file, mcu_port))
                self._flash_thread.daemon = True
                self.on_shutdown() #Disconect from the MCU
                self._flash_thread.start()

                return True
        return False

    def _flash_worker(self, firmware, mcu_port):

        try:
            self._logger.info("Firmware update started")

            if self.conn:
                if self.conn.is_connected():
                    self.on_shutdown()
                    self._send_status("progress", subtype="disconnecting")

            self._send_status("progress", subtype="startingflash")

            try:
                if avrdude._flash_avrdude(self, firmware=firmware, printer_port=mcu_port):
                    time.sleep(1)
                    self._send_status("progress", subtype="reconnecting")                
                    self.new_connection() # Reconnect to the Safety Printer MCU.
                    time.sleep(0.5)
                    message = u"Flashing successful."
                    self.conn.terminal(message,"INFO") 
                    self._send_status("success")  
   
            except:
                self.conn.terminal("Error while attempting to flash","ERROR")
                self.on_shutdown() #Disconect from the MCU

            finally:
                try:
                    os.remove(firmware)
                except:
                    self.conn.terminal(u"Could not delete temporary hex file at {}".format(firmware),"WARNING") 

        finally:
            self._flash_thread = None

    def _send_status(self, status, subtype=None, message=None):
        self._plugin_manager.send_plugin_message(self._identifier, dict(type="status", status=status, subtype=subtype, message=message))


__plugin_name__ = "Safety Printer"
__plugin_version__ = "1.1.1rc2" #just used for Betas and release candidates. Change in Setup.py for main releases.
__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SafetyPrinterPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {"octoprint.plugin.softwareupdate.check_config":__plugin_implementation__.get_update_information}


