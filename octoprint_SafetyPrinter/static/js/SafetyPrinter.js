/*
 * Safety Printer Octoprint Plugin
 * Copyright (c) 2021 Rodrigo C. C. Silva [https://github.com/SinisterRj/Octoprint_SafetyPrinter]
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
 */

$(function() {
    function spSensorsType(visible, label, status, color, enabled, active, type, SP, timer) {
        var self = this;
        self.visible = ko.observable(visible);
        self.label = ko.observable(label);
        self.status = ko.observable(status);
        self.color = ko.observable(color);
        self.enabled = ko.observable(enabled);
        self.active = ko.observable(active);
        self.type = ko.observable(type);
        self.SP = ko.observable(SP);
        self.timer = ko.observable(timer);

    }

    function spSensorsSettingsType(visible, checked, label, actualvalue, enabled, active, type, SP, timer, availableSP, expertMode) {
        var self = this;
        self.visible = ko.observable(visible);
        self.checked = ko.observable(checked);
        self.label = ko.observable(label);
        self.actualvalue = ko.observable(actualvalue);        
        self.enabled = ko.observable(enabled);
        self.active = ko.observable(active);
        self.type = ko.observable(type);
        self.SP = ko.observable(SP);
        self.timer = ko.observable(timer);
        self.availableSP = ko.observableArray(availableSP);
        self.expertMode = ko.observable(expertMode)
    }

    function ItemViewModel(val) {
        var self = this;
        self.name = ko.observable(val);
    }

    function TerminalViewModel(line,type) {
        var self = this;
        self.line = ko.observable(line);
        self.type = ko.observable(type);
    }

    function SafetyprinterViewModel(parameters) {
        var self = this;

        self.debug = false;  

        self.settingsViewModel = parameters[0];
        self.printerState = parameters[1];
        
        // Sidebar variables
        self.interlock = ko.observable(false);
        self.activeSensors = "";
        self.confirmVisible = ko.observable(false);

        self.spSensors = ko.observableArray([
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0"),
           new spSensorsType(false,"","offline","gray",false,false,"0","0","0")
        ]);

        // Settings variables        
        self.expertMode = ko.observable(false);
        self.availablePorts = ko.observableArray();
        self.settingsVisible = false;
        self.changedFlag = false;
                
        self.updateSettingsSensors = false;
        self.FWVersion = ko.observable("");
        self.FWReleaseDate = ko.observable("");
        self.FWEEPROM = ko.observable("");
        self.FWCommProtocol = ko.observable("");
        self.FWValidVersion = ko.observable(false);

        self.MCUVolts = ko.observable("");
        self.MCUTemp = ko.observable("");
        self.MCUSRAM = ko.observable("");
        self.MCUMaxTime = ko.observable("");
        self.MCUAvgTime = ko.observable("");

        self.totalMsgs = ko.observable("");
        self.badMsgs = ko.observable("");
        
        self.sensorDataVisible = ko.observable(false);

        self.spSensorsSettings = ko.observableArray([
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false),
           new spSensorsSettingsType(false,false,"","0",false,false,"0","0","0",[],false)
        ]);

        // Navbar variables
        self.navbarcolor = ko.observable("#EB9605");
        self.navbartitle = ko.observable("Safety Printer: Offline");
        self.NBOffline = false;
        self.NBError = false;
        self.NBWarning = false;
        self.NBtrip = false;

        // Tab variables
        self.autoscrollEnabled = ko.observable(true);
        self.showDebug = ko.observable(false);
        self.terminalLines = ko.observableArray();
        self.countTerminalLines = 0;
        self.command = ko.observable();
        self.tabActive = false;
        self.tempMsgFilter = ko.observable(false);
        self.startedFilter = false;
        self.terminalColor = ko.observable("");
        self.terminalBg = ko.observable("");

        // General variables
        self.connection = ko.observable("Offline");
        self.notConnected = ko.observable(true);
        self.connectedPort = ko.observable("None");
        self.connectionCaption = ko.observable("Connect");
        self.automaticShutdownEnabled = ko.observable();
        self.newTrip = ko.observable(false);
        self.numOfSensors = 0;


        // ************* Notifications :

        PNotify.prototype.options.confirm.buttons = [];

        self.tripPopupText = gettext('Printer Emergency Shutdown detected.');
        self.tripPopupOptions = {
            title: gettext('Shutdown'), 
            type: 'error',           
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Ok',
                    addClass: 'btn-block btn-danger',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };

        self.timeoutPopupText = gettext('Shutting down in ');
        self.timeoutPopupOptions = {
            title: gettext('System Shutdown'),
            type: 'notice',
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Abort Shutdown',
                    addClass: 'btn-block btn-danger',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };

        self.errorPopupText = gettext('Error:');
        self.errorPopupOptions = {
            title: gettext('Safety Printer'), 
            type: 'error',           
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Ok',
                    addClass: 'btn-block btn-danger',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        self.updateNavbar('Error',false)
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };

        self.warningPopupText = gettext('Warning:');
        self.warningPopupOptions = {
            title: gettext('Safety Printer'), 
            type: 'warning',           
            icon: true,
            hide: false,
            confirm: {
                confirm: true,
                buttons: [{
                    text: 'Ok',
                    addClass: 'btn-block btn-warning',
                    promptTrigger: true,
                    click: function(notice, value){
                        notice.remove();
                        self.updateNavbar('Warning',false)
                        notice.get().trigger("pnotify.cancel", [notice, value]);
                    }
                }]
            },
            buttons: {
                closer: false,
                sticker: false,
            },
            history: {
                history: false
            }
        };

        self.onStartupComplete = function() {
            if (self.debug) {console.log("onStartupComplete")};
            //Show or hide terminal TAB.
            self.showHideTab();
            OctoPrint.simpleApiCommand("SafetyPrinter", "forceRenew"); 
        };
      
        self.showHideTab = function() {
            if (self.debug) {console.log("showHideTab")};
            // Shows or hides the terminal TAB on UI.
            if ((self.settingsViewModel.settings.plugins.SafetyPrinter.showTerminal() == true) && (!document.getElementById("tab_plugin_SafetyPrinter_link"))) {
                $("<li id='tab_plugin_SafetyPrinter_link' class='' data-bind='allowBindings: true'><a href='#tab_plugin_SafetyPrinter' data-toggle='tab'>Safety Printer</a></li>").appendTo("#tabs");
            } else if (self.settingsViewModel.settings.plugins.SafetyPrinter.showTerminal() == false) {
                $('#tab_plugin_SafetyPrinter_link').remove();
            }
        };

        // ************* Functions of the terminal TAB:

        self.terminalScrollEvent = _.throttle(function () {
            if (self.debug) {console.log("terminalScrollEvent")};
            // If user scrolls the terminal, it stops the autoscrolling
            var container = $("#SafetyPrinterTerminal");
            var pos = container.scrollTop();
            var scrollingUp =
                self.previousScroll !== undefined && pos < self.previousScroll;

            if (self.autoscrollEnabled() && scrollingUp) {
                var maxScroll = container[0].scrollHeight - container[0].offsetHeight;

                if (pos <= maxScroll) {
                    self.autoscrollEnabled(false);
                }
            }
            self.previousScroll = pos;
        }, 250);

        self.gotoTerminalCommand = function () {
            if (self.debug) {console.log("gotoTerminalCommand")};
            // skip if user highlights text.
            var sel = getSelection().toString();
            if (sel) {
                self.autoscrollEnabled(false);
                return;
            }

            $("#SPterminal-command").focus();
        };

        self.onAfterTabChange = function (current, previous) {
            if (self.debug) {console.log("onAfterTabChange")};
            self.tabActive = current === "#term";
            self.updateOutput();
        };


        self.updateOutput = function () {
            if (self.debug) {console.log("updateOutput")};
            if (self.tabActive && OctoPrint.coreui.browserTabVisible && self.autoscrollEnabled() && $("#SafetyPrinterTerminal").is(':visible')) {
                self.scrollToEnd();
            }
        };

        self.displayedLines = ko.pureComputed(function () {
            if (self.debug) {console.log("displayedLines")};
            // Filter and display msgs on terminal

            var col=document.getElementById("terminal-output");
            self.terminalColor(getComputedStyle( col ,null).getPropertyValue('color'));
            self.terminalBg(getComputedStyle( col ,null).getPropertyValue('background-color'));

            var result = [];            
            var lines = self.terminalLines();
            var totalLines = 0;

            _.each(lines, function (entry) {
               
                if (((self.showDebug()) || (entry.type() != "DEBUG")) && ((!self.tempMsgFilter()) || (entry.line().search("R1") == -1))) {
                    self.startedFilter = false;
                    result.push(entry);  
                    totalLines++;

                } else if (!self.startedFilter) {
                    self.startedFilter = true;
                    result.push(new TerminalViewModel("[...]",""));
                    totalLines++;
                }               
            });

            for (i = totalLines; i < 17; i++) { 
                result.unshift(new TerminalViewModel("","")); //Add empity lines to the begining of the array
            }   
            
            return result;
        });
        

        // ************* Update Settings TAB:

        self.onSettingsShown = function () {
            if (self.debug) {console.log("onSettingsShown")};
            
            self.settingsVisible = true;
            self.refreshSettings();
            OctoPrint.simpleApiCommand("SafetyPrinter", "settingsVisible", {status: self.settingsVisible});
        };

        self.onSettingsHidden = function () {
            if (self.debug) {console.log("onSettingsHidden")};
            self.settingsVisible = false;
            OctoPrint.simpleApiCommand("SafetyPrinter", "settingsVisible", {status: self.settingsVisible});
            if (self.changedFlag && !self.printerState.isPrinting()) {
                if (self.debug) {console.log("Writing EEPROM")};
                self.changedFlag = false;
                OctoPrint.simpleApiCommand("SafetyPrinter", "saveEEPROM");  
            }
        }; 

        self.refreshSettings = function() {
            if (self.debug) {console.log("refreshSettings")};
            // Update serial ports info. Also called when user clicks on "default Serial" combo box
            OctoPrint.simpleApiCommand("SafetyPrinter", "forceRenew"); 
            self.availablePorts.removeAll();
            self.availablePorts.push(new ItemViewModel("AUTO"));
            OctoPrint.simpleApiCommand("SafetyPrinter", "getPorts");

            if (self.numOfSensors > 0) {
                self.sensorDataVisible(true);
            }

            self.refreshMCUStats();

            for (i = 0; i < self.numOfSensors; i++) {

                self.spSensorsSettings()[i].visible(self.spSensors()[i].visible());
                self.spSensorsSettings()[i].visible.valueHasMutated();   //Force knockout to refresh View

                self.spSensorsSettings()[i].type(self.spSensors()[i].type());
                self.spSensorsSettings()[i].type.valueHasMutated();

                self.spSensorsSettings()[i].enabled(self.spSensors()[i].enabled());
                self.spSensorsSettings()[i].enabled.valueHasMutated();
                
                self.spSensorsSettings()[i].active(self.spSensors()[i].active());
                self.spSensorsSettings()[i].active.valueHasMutated();

                self.spSensorsSettings()[i].SP(self.spSensors()[i].SP());
                self.spSensorsSettings()[i].SP.valueHasMutated();

                self.spSensorsSettings()[i].timer(self.spSensors()[i].timer());
                self.spSensorsSettings()[i].timer.valueHasMutated();                
            }   
        };

        self.onSettingsBeforeSave = function() {
            if (self.debug) {console.log("onSettingsBeforeSave")};
            //self.changedFlag = false;
            alertFlag = false;
                        
            for (i = 0; i < self.numOfSensors; i++) {                                         

                if (self.spSensorsSettings()[i].SP() != self.spSensors()[i].SP()) {
                    if (!self.printerState.isPrinting()) {  // avoids changins during printing.
                        if (self.debug) {console.log("Changing SP: " + self.spSensorsSettings()[i].label())};
                        OctoPrint.simpleApiCommand("SafetyPrinter", "changeSP", {id: i, newSP: self.spSensorsSettings()[i].SP()});
                        self.changedFlag = true;
                    } else {
                        alertFlag = true;
                    }
                }

                if (self.spSensorsSettings()[i].timer() != self.spSensors()[i].timer()) {
                    if (!self.printerState.isPrinting()) {  // avoids changins during printing.
                        if (self.debug) {console.log("Changing Timer: " + self.spSensorsSettings()[i].label())};
                        OctoPrint.simpleApiCommand("SafetyPrinter", "changeTimer", {id: i, newTimer: self.spSensorsSettings()[i].timer()});
                        self.changedFlag = true;
                    } else {
                        alertFlag = true;
                    }
                }

                //Always keep ENABLE as the last one to avoid spurious trip
                if (self.spSensorsSettings()[i].enabled() != self.spSensors()[i].enabled()) {
                    if (!self.printerState.isPrinting()) {  // avoids changins during printing.
                        if (self.spSensorsSettings()[i].enabled()) {                        
                            if (self.debug) {console.log("Enabling: " + self.spSensorsSettings()[i].label())};
                            OctoPrint.simpleApiCommand("SafetyPrinter", "toggleEnabled", {id: i, onoff: "on"});
                            self.changedFlag = true;
                        } else {
                            if (self.debug) {console.log("Disabling: " + self.spSensorsSettings()[i].label())};
                            OctoPrint.simpleApiCommand("SafetyPrinter", "toggleEnabled", {id: i, onoff: "off"});
                            self.changedFlag = true;
                        }
                    } else {
                        alertFlag = true;
                    }                    
                }
            }
            self.showHideTab();
            if (alertFlag) {
                window.alert("The Safety Printer modifications cannot be applied during printing.");
            }

        };

        // ************* Functions for each button on Settings TAB:

        self.toggleAutoscrollBtn = function() {
            if (self.debug) {console.log("toggleAutoscrollBtn")};
            // Changes the setings terminal autoscroll to ON or OFF
            self.autoscrollEnabled(!self.autoscrollEnabled());

            if (self.autoscrollEnabled()) {
                self.updateOutput();
            }
        };

        self.toggleFilterBtn = function() {
            if (self.debug) {console.log("toggleFilterBtn")};
            // enable or disable <R1> messages on terminal
            self.tempMsgFilter(!self.tempMsgFilter());
        };

        self.resetBtn = function(item) {
            if (self.debug) {console.log("resetBtn")};
            // Send a command to arduino restore sensor settings
            for (i = 0; i < self.numOfSensors; i++) {                                         
                if (self.spSensorsSettings()[i].checked()) {
                    //if (self.debug) {console.log("Restoring " + self.spSensorsSettings()[i].label() + " default settings.")};
                    OctoPrint.simpleApiCommand("SafetyPrinter", "resetSettings", {id: i}); 
                }
            }
            self.updateSettingsSensors = true;            
        };

        self.refreshMCUStats = function(item) {
            if (self.debug) {console.log("refreshMCUStats")};
            // Send a command to arduino refresh MCU status
            OctoPrint.simpleApiCommand("SafetyPrinter", "refreshMCUStats"); 
        };

        // ************* Functions for each button on Terminal TAB:

        self.sendCommandBtn = function() {
            if (self.debug) {console.log("sendCommandBtn")};
            // Send generic user comands from command line on terminal to arduino
            if (self.command().toUpperCase() == "@DISCONNECT") {
                OctoPrint.simpleApiCommand("SafetyPrinter", "disconnect");     
            } else if (self.command().toUpperCase() == "@CONNECT") {
                OctoPrint.simpleApiCommand("SafetyPrinter", "reconnect"); 
            } else if (self.command().toUpperCase() == "@RENEW") {
                OctoPrint.simpleApiCommand("SafetyPrinter", "forceRenew");  
            } else {
                OctoPrint.simpleApiCommand("SafetyPrinter", "sendCommand", {serialCommand: self.command()}); 
            }
        };

        self.scrollToEnd = function () {
            if (self.debug) {console.log("scrollToEnd")};
            var container = $("#SafetyPrinterTerminal");
            if ((container.length) && $("#SafetyPrinterTerminal").is(':visible') && OctoPrint.coreui.browserTabVisible) {
                container.scrollTop(container[0].scrollHeight);
            }
        };

        self.copyAll = function () {
            if (self.debug) {console.log("copyAll")};
            var lines;
            lines = self.terminalLines();
            var clipboard;
            _.each(lines, function (entry) {
                if (entry.type() != "") {
                    clipboard = clipboard + entry.type() + ":" + entry.line() + "\n";
                } else {
                    clipboard = clipboard + entry.line() + "\n";
                }
            });    
            copyToClipboard(clipboard);
        };

        self.clearAllLogs = function () {
            if (self.debug) {console.log("clearAllLogs")};
            self.terminalLines([]);
            self.countTerminalLines = 0;
        };


        // ************* Functions for each button on Sidebar:

        self.tripResetBtn = function() {
            if (self.debug) {console.log("tripResetBtn")};
            // Send a command to arduino to reset all trips
            OctoPrint.simpleApiCommand("SafetyPrinter", "resetTrip");
            
            // Remove notification.
            if (typeof self.tripPopup != "undefined") {
                self.tripPopup.remove();
                self.tripPopup = undefined;
            }
        };

        self.onAutomaticShutdownEvent = function() {
            if (self.debug) {console.log("onAutomaticShutdownEvent")};
            if (self.automaticShutdownEnabled()) {
                OctoPrint.simpleApiCommand("SafetyPrinter", "enableShutdown");
            } else {
                OctoPrint.simpleApiCommand("SafetyPrinter", "disableShutdown");
            }
        };

        self.automaticShutdownEnabled.subscribe(self.onAutomaticShutdownEvent, self);

        self.tripBtn = function() {
            if (self.debug) {console.log("tripBtn")};
            self.confirmVisible(!self.confirmVisible());
        };

        self.tripConfirmBtn = function() {
            if (self.debug) {console.log("tripConfirmBtn")};
            self.confirmVisible(!self.confirmVisible());
            OctoPrint.simpleApiCommand("SafetyPrinter", "sendTrip");
        };

        // ************* Functions for navbar:

        self.updateNavbar = function(flag,status) {
            if (self.debug) {console.log("updateNavbar:"+flag+","+status)};
            switch (flag) {
                case 'Offline':
                    self.NBOffline = status;
                    break;
                case 'Error':
                    self.NBError = status;
                    break;
                case 'Warning':
                    self.NBWarning = status;
                    break;
                case 'Trip':
                    self.NBtrip = status;
                    break;
            }

            if (self.NBtrip) {
                self.navbarcolor("red");
                self.navbartitle("Safety Printer: TRIP!");
            } else if (self.NBError) {
                self.navbarcolor("red");
                self.navbartitle("Safety Printer: Error");
            } else if (self.NBWarning) {
                self.navbarcolor("#EB9605");
                self.navbartitle("Safety Printer: Warning");
            } else if (self.NBOffline) {
                self.navbarcolor("#EB9605");
                self.navbartitle("Safety Printer: Offline");
            } else {
                self.navbarcolor("unset");
                self.navbartitle("Safety Printer: Normal operation");
            }
        };

        // ************* Functions for general buttons:

        self.connectBtn = function() {
            if (self.debug) {console.log("connectBtn")};
            // Connects or disconnects to the Safety Printer Arduino
            if (self.notConnected()) {
                self.connection("Connecting");
                //self.connectionColor("");
                OctoPrint.simpleApiCommand("SafetyPrinter", "reconnect");    
            } else {
                self.connection("Disconecting");
                //self.connectionColor("");                
                OctoPrint.simpleApiCommand("SafetyPrinter", "disconnect");    
            }

        };

        // ************* Function to manage plug-in messages
       
        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (self.debug) {console.log("onDataUpdaterPluginMessage: " + data.type)};
            if (plugin != "SafetyPrinter") {
                return;
            }

            if (data.type == "statusUpdate") {
            // Update all sensors status
                var i = parseInt(data.sensorIndex);
                self.numOfSensors = parseInt(data.totalSensors);

                if (i >=0 || i < 8) {                                        
                    
                    self.spSensors()[i].visible(true);                    
                    self.spSensorsSettings()[i].visible(true);                    
                    self.spSensors()[i].label(data.sensorLabel);
                    self.spSensorsSettings()[i].label(data.sensorLabel);
                    if (data.sensorEnabled == "T") {
                        self.spSensors()[i].enabled(true);    
                        //console.log(Math.floor(Math.random() * 101) + ":Index:" + i + " , Label:" + data.sensorLabel + " , Enabled: True - " + self.spSensors()[i].enabled());
                    } else {
                        self.spSensors()[i].enabled(false); 
                        //console.log(Math.floor(Math.random() * 101) + ":Index:" + i + " , Label:" + data.sensorLabel + " , Enabled: False - " + self.spSensors()[i].enabled());
                    }
                    self.spSensorsSettings()[i].actualvalue(data.sensorActualValue);
                    if (data.sensorActive == "T") {
                        self.spSensors()[i].active(true); 
                        self.spSensorsSettings()[i].active(true);   
                    } else {
                        self.spSensors()[i].active(false);
                        self.spSensorsSettings()[i].active(false);    
                    }
                    if (data.sensorType == "0") {
                        self.spSensors()[i].type("Digital");
                        if (self.spSensorsSettings()[i].availableSP().length == 0) {
                            self.spSensorsSettings()[i].availableSP.push(0,1);    
                        }                        
                    } else if (data.sensorType == "1") {
                        self.spSensors()[i].type("NTC Temperature"); 
                        if (self.spSensorsSettings()[i].availableSP().length == 0) {
                            self.spSensorsSettings()[i].availableSP.push(0,50,100,150,200,210,220,230,240,250,260,270,280,290,300);
                        }
                    }
                    self.spSensors()[i].SP(data.sensorSP);
                    self.spSensors()[i].timer(data.sensorTimer);
                    
                    if (data.sensorType == "1") {
                        //NTC sensor
                        statusStr = data.sensorActualValue + "°C "
                    } else {
                        statusStr = ""
                    }
                    if (data.sensorActive == "T") {
                        if(data.sensorEnabled == "T") {                            
                            statusStr += "Alarm";
                            colorStr = "orange";
                        } else {
                            statusStr += "Alarm (Disabled)";
                            colorStr = "gray";
                        }                        
                    } else {
                        if(data.sensorEnabled == "T") {
                            colorStr = "green";
                        } else {
                            statusStr += "(Disabled)";
                            colorStr = "gray";
                        }                        
                    }
                    self.spSensors()[i].status(statusStr);
                    self.spSensors()[i].color(colorStr);
                }
                if (self.updateSettingsSensors) {
                    self.updateSettingsSensors = false;
                    if (self.settingsVisible) {
                        self.refreshSettings();
                    }
                }
            } 

            else if (data.type == "interlockUpdate") {
            // Update interlock (trip) status
                if (data.interlockStatus == "F") {
                    self.interlock(false);
                    self.updateNavbar('Trip',false)

                    self.activeSensors = "";

                } else {
                    
                    self.tripPopupOptions.text = self.tripPopupText;
                    for (i = 0; i < self.numOfSensors; i++) {                                         
                        if ((self.spSensors()[i].active()) && (self.spSensors()[i].enabled()) && (self.activeSensors.indexOf(String(self.spSensors()[i].label())) == -1)){
                            self.activeSensors = self.activeSensors + "\n" + String(self.spSensors()[i].label());                                                                       
                        }   
                    }
                    if (self.activeSensors != "") {
                        self.tripPopupOptions.text = self.tripPopupText + "\n\n Alarmed sensors:" + self.activeSensors;                      
                    }
                    if (typeof self.tripPopup != "undefined") {
                        self.tripPopup.update(self.tripPopupOptions);
                    } else {
                        self.tripPopup = new PNotify(self.tripPopupOptions);
                        self.tripPopup.get().on('pnotify.cancel');
                    }

                    self.interlock(true);
                    self.updateNavbar('Trip',true)
                }                
            }

            else if (data.type == "connectionUpdate") {
            // Update connection status

                if (data.connectionStatus) {
                    self.totalMsgs(data.totalmsgs);
                    percent = (parseInt(data.badmsgs)/parseInt(data.totalmsgs))*100;
                    self.badMsgs(data.badmsgs + " - " + percent.toFixed(1) + "%"); 
                }
                
                if (data.connectionStatus && self.notConnected()) {
                    self.connection("Online");
                    //self.connectionColor("");
                    self.connectionCaption("Disconnect");
                    self.notConnected(false);
                    self.connectedPort(data.port);
                    self.updateNavbar('Offline',false)
                    
                     //Update Settings tab
                    if (self.settingsVisible) {
                        self.refreshSettings();
                    }  

                } else if ((!data.connectionStatus && !self.notConnected()) || (data.failure)) {
                    self.connection("Offline");
                    self.connectionCaption("Connect");
                    self.notConnected(true); 

                    self.updateNavbar('Offline',true)

                    self.FWVersion("");
                    self.FWReleaseDate("");
                    self.FWEEPROM("");
                    self.FWCommProtocol("");
                    self.FWValidVersion(false);

                    self.MCUVolts("");
                    self.MCUTemp("");
                    self.MCUSRAM("");
                    self.MCUMaxTime("");
                    self.MCUAvgTime("");

                    self.sensorDataVisible(false);

                    var i;
                    for (i = 0; i < self.numOfSensors; i++) {                                         
                        self.spSensors()[i].visible(false);
                        self.spSensorsSettings()[i].visible(false);   
                    }
                }
            }

            else if (data.type == "serialPortsUI") {
            // Update list of serial ports available
                self.availablePorts.push(new ItemViewModel(data.port));
            }

            else if (data.type == "terminalUpdate") {
            // Update messages displayed on settings terminal                
                data.line.replace(/[\n\r]+/g, '');
                self.terminalLines.push(new TerminalViewModel(data.line,data.terminalType));
                self.countTerminalLines++;

                if (self.countTerminalLines > 3600) {
                    self.terminalLines.shift(); //removes the first line
                }
                if (self.autoscrollEnabled() && $("#SafetyPrinterTerminal").is(':visible') && OctoPrint.coreui.browserTabVisible) {
                    self.scrollToEnd();
                }

            }
            else if (data.type == "shutdown") {
                self.automaticShutdownEnabled(data.automaticShutdownEnabled);
                if ((data.timeout_value != null) && (data.timeout_value > 0)) {
                    self.timeoutPopupOptions.text = self.timeoutPopupText + data.timeout_value;
                    if (typeof self.timeoutPopup != "undefined") {
                        self.timeoutPopup.update(self.timeoutPopupOptions);
                    } else {
                        self.timeoutPopup = new PNotify(self.timeoutPopupOptions);
                        self.timeoutPopup.get().on('pnotify.cancel', function() {self.abortShutdown(true);});
                    }
                } else {
                    if (typeof self.timeoutPopup != "undefined") {
                        self.timeoutPopup.remove();
                        self.timeoutPopup = undefined;
                    }
                }
            }
            else if (data.type == "firmwareInfo") {
                self.FWVersion(data.version);
                self.FWReleaseDate(data.releaseDate);
                self.FWEEPROM(data.EEPROM);
                self.FWCommProtocol(data.CommProtocol);
                self.FWValidVersion(data.ValidVersion);
            }
            else if (data.type == "MCUInfo") {
                self.MCUVolts(data.volts);
                self.MCUTemp(data.temp);
                self.MCUSRAM(data.ram);
                self.MCUMaxTime(data.maxTime);
                self.MCUAvgTime(data.avgTime);
            }
            else if (data.type == "error") {
                self.updateNavbar('Error',true)
                self.errorPopupOptions.text = data.errorMsg;
                self.errorPopup = new PNotify(self.errorPopupOptions);
                self.errorPopup.get().on('pnotify.cancel');
            }
            else if (data.type == "warning") {
                self.updateNavbar('Warning',true)
                self.warningPopupOptions.text = data.warningMsg;
                self.warningPopup = new PNotify(self.warningPopupOptions);
                self.warningPopup.get().on('pnotify.cancel');
            }

        };
        
        self.abortShutdown = function(abortShutdownValue) {
            self.timeoutPopup.remove();
            self.timeoutPopup = undefined;
            OctoPrint.simpleApiCommand("SafetyPrinter", "abortShutdown");
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: SafetyprinterViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: ["settingsViewModel","printerStateViewModel"],
        // Elements to bind to, e.g. #settings_plugin_SafetyPrinter, #tab_plugin_SafetyPrinter, ...
        elements: ["#settings_plugin_SafetyPrinter","#navbar_plugin_SafetyPrinter","#sidebar_plugin_SafetyPrinter","#tab_plugin_SafetyPrinter"] //
    });
});
