import re
import os
import sarge
import serial
import time

try:
    import serial.tools.list_ports
    from serial.tools import list_ports
except ImportError:
    exit("This requires serial module\nInstall with: sudo pip install pyserial")

AVRDUDE_WRITING = "writing flash"
AVRDUDE_VERIFYING = "reading on-chip flash data"
AVRDUDE_TIMEOUT = "timeout communicating with programmer"
AVRDUDE_ERROR = "ERROR:"
AVRDUDE_ERROR_SYNC = "not in sync"
AVRDUDE_ERROR_VERIFICATION = "verification error"
AVRDUDE_ERROR_DEVICE = "can't open device"

WINDOWS_PATTERN = "^[A-z]\:\\\\.+.exe$"
POSIX_PATTERN = "^(\/[^\0/]+)+$"

USB_VID_PID_MK2 = "2c99:0001"
USB_VID_PID_MK3 = "2c99:0002"
USB_VID_PID_MMU_BOOT = "2c99:0003"
USB_VID_PID_MMU_APP  = "2c99:0004"
USB_VID_PID_CW1_BOOT = "2c99:0007"
USB_VID_PID_CW1_APP  = "2c99:0008"

TARGET_NO_PRUSA = 0
TARGET_MMU = 1
TARGET_CW1 = 2

ser = serial

def _check_avrdude(self):
    avrdude_path = self._settings.get(["avrdude_path"])
    avrdude_avrmcu = "ATmega328p"
    avrdude_programmer = "arduino"

    if os.name == 'nt':
       pattern = re.compile(WINDOWS_PATTERN)
    else:
       pattern = re.compile(POSIX_PATTERN)

    if not pattern.match(avrdude_path):
        #self._logger.error(u"Path to avrdude is not valid: {path}".format(path=avrdude_path))
        self.conn.terminal(u"Path to avrdude is not valid: {path}".format(path=avrdude_path),"ERROR")
        return False
    elif not os.path.exists(avrdude_path):
        #self._logger.error(u"Path to avrdude does not exist: {path}".format(path=avrdude_path))
        self.conn.terminal(u"Path to avrdude does not exist: {path}".format(path=avrdude_path),"ERROR")
        return False
    elif not os.path.isfile(avrdude_path):
        #self._logger.error(u"Path to avrdude is not a file: {path}".format(path=avrdude_path))
        self.conn.terminal(u"Path to avrdude is not a file: {path}".format(path=avrdude_path),"ERROR")
        return False
    elif not os.access(avrdude_path, os.X_OK):
        #self._logger.error(u"Path to avrdude is not executable: {path}".format(path=avrdude_path))
        self.conn.terminal(u"Path to avrdude is not executable: {path}".format(path=avrdude_path),"ERROR")
        return False
    else:
        return True

def _flash_avrdude(self, firmware=None, printer_port=None, **kwargs):
    assert(firmware is not None)
    assert(printer_port is not None)

    avrdude_path = self._settings.get(["avrdude_path"])
    avrdude_conf = None
    avrdude_avrmcu = "ATmega328p" #self.get_profile_setting("avrdude_avrmcu")
    avrdude_programmer = "arduino" #self.get_profile_setting("avrdude_programmer")
    avrdude_baudrate = "115200" #self.get_profile_setting("avrdude_baudrate")
    avrdude_disableverify = False #self.get_profile_setting_boolean("avrdude_disableverify")

    working_dir = os.path.dirname(avrdude_path)

    avrdude_command = "{avrdude} -v -q -p {mcu} -c {programmer} -P {port} -D -C {conffile} -b {baudrate} {disableverify} -U flash:w:{firmware}:i" #self.get_profile_setting("avrdude_commandline")
    avrdude_command = avrdude_command.replace("{avrdude}", avrdude_path)
    avrdude_command = avrdude_command.replace("{mcu}", avrdude_avrmcu)
    avrdude_command = avrdude_command.replace("{programmer}", avrdude_programmer)

    if avrdude_conf is not None and avrdude_conf != "":
        avrdude_command = avrdude_command.replace("{conffile}", avrdude_conf)
    else:
        avrdude_command = avrdude_command.replace(" -C {conffile} ", " ")

    if avrdude_baudrate is not None and avrdude_baudrate != "":
        avrdude_command = avrdude_command.replace("{baudrate}", str(avrdude_baudrate))
    else:
        avrdude_command = avrdude_command.replace(" -b {baudrate} ", " ")

    if avrdude_disableverify:
        avrdude_command = avrdude_command.replace("{disableverify}", "-V")
    else:
        avrdude_command = avrdude_command.replace(" {disableverify} ", " ")

    
    avrdude_command = avrdude_command.replace("{port}", printer_port)
    avrdude_command = avrdude_command.replace("{firmware}", firmware)

    self._logger.info(u"Running '{}' in {}".format(avrdude_command, working_dir))
    self._console_logger.info(u"")
    self._console_logger.info(avrdude_command)

    try:
        p = sarge.run(avrdude_command, cwd=working_dir, async_=True, stdout=sarge.Capture(), stderr=sarge.Capture())
        p.wait_events()

        while p.returncode is None:
            output = p.stderr.read(timeout=0.5).decode('utf-8')
            if not output:
                p.commands[0].poll()
                continue

            for line in output.split("\n"):
                if line.endswith("\r"):
                    line = line[:-1]
                self._console_logger.info(u"> {}".format(line))

            if AVRDUDE_WRITING in output:
                #self._logger.info(u"Writing memory...")
                self.conn.terminal("AVRDude: Writing memory...","INFO")
                self._send_status("progress", subtype="writing")
            elif AVRDUDE_VERIFYING in output:
                #self._logger.info(u"Verifying memory...")
                self.conn.terminal("AVRDude: Verifying memory...","INFO")
                self._send_status("progress", subtype="verifying")
            elif AVRDUDE_TIMEOUT in output:
                p.commands[0].kill()
                p.close()
                raise FlashException("Timeout communicating with programmer")
            elif AVRDUDE_ERROR_DEVICE in output:
                p.commands[0].kill()
                p.close()
                raise FlashException("Error opening serial device")
            elif AVRDUDE_ERROR_VERIFICATION in output:
                p.commands[0].kill()
                p.close()
                raise FlashException("Error verifying flash")
            elif AVRDUDE_ERROR_SYNC in output:
                p.commands[0].kill()
                p.close()
                raise FlashException("Avrdude says: 'not in sync" + output[output.find(AVRDUDE_ERROR_SYNC) + len(AVRDUDE_ERROR_SYNC):].strip() + "'")
            elif AVRDUDE_ERROR in output:
                raise FlashException("Avrdude error: " + output[output.find(AVRDUDE_ERROR) + len(AVRDUDE_ERROR):].strip())

        if p.returncode == 0:
            return True
        else:
            raise FlashException("Avrdude returned code {returncode}".format(returncode=p.returncode))

    except FlashException as ex:
        #self._logger.error(u"Flashing failed. {error}.".format(error=ex.reason))
        error_message = u"Flashing failed. {error}.".format(error=ex.reason)
        self.conn.terminal(error_message,"ERROR")
        self._send_status("flasherror", message=ex.reason)
        return False
    except:
        self._logger.exception(u"Flashing failed. Unexpected error.")
        self._send_status("flasherror")
        return False

class FlashException(Exception):
	def __init__(self, reason, *args, **kwargs):
		Exception.__init__(self, *args, **kwargs)
		self.reason = reason
