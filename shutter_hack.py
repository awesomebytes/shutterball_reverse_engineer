#!/usr/bin/python

import subprocess
import tempfile
import os
import sys
import signal
import time


class ShellCmd:
    """Helpful class to spawn commands and keep track of them"""

    def __init__(self, cmd):
        self.retcode = None
        self.outf = tempfile.NamedTemporaryFile(mode="w")
        self.errf = tempfile.NamedTemporaryFile(mode="w")
        self.inf = tempfile.NamedTemporaryFile(mode="r")
        self.process = subprocess.Popen(cmd, shell=True, stdin=self.inf,
                                        stdout=self.outf, stderr=self.errf,
                                        preexec_fn=os.setsid, close_fds=True)

    def __del__(self):
        if not self.is_done():
            self.kill()
        self.outf.close()
        self.errf.close()
        self.inf.close()

    def get_stdout(self):
        with open(self.outf.name, "r") as f:
            return f.read()

    def get_stderr(self):
        with open(self.errf.name, "r") as f:
            return f.read()

    def get_retcode(self):
        """Get retcode or None if still running"""
        if self.retcode is None:
            self.retcode = self.process.poll()
        return self.retcode

    def is_done(self):
        return self.get_retcode() is not None

    def is_succeeded(self):
        """Check if the process ended with success state (retcode 0)
        If the process hasn't finished yet this will be False."""
        return self.get_retcode() == 0

    def kill(self):
        self.retcode = -1
        os.killpg(self.process.pid, signal.SIGTERM)
        self.process.wait()


class ShutterBall(object):
    def __init__(self):
        self.sleep_time = 0.02
        self.lescan = None
        self.hcidump = None
        self.filter_by_time = True
        self.filter_time = 0.35
        self.baddr_time_dict = {}
        # This callback will be called every time
        # a ShutterBall is found
        # the call parameters are (baddress, full_raw_bluetooth_dump)
        self.on_shooter_appeared_callback = None

    def start_reading(self, baddr):
        self.baddr = baddr.replace(':', '')
        self.baddr = self.baddr.upper()
        if len(self.baddr) != 12:
            print("Incorrect bluetooth address (" + self.baddr + ")")
            exit(0)
        print("Starting ShutterBall for bluetooth address: " + str(baddr))
        self.start_lescan()
        self.start_hcidump()
        self.parse_scan()

    def find_shutters(self):
        def print_baddress(baddr, full_raw):
            print("Found ShutterBall with Bluetooth mac address:")
            print(baddr)
            print("From RAW input:")
            print(full_raw)

        self.on_shooter_appeared_callback = print_baddress
        self.on_shutter_work()

    def execute_command_on_button_press(self, command, baddr=''):
        # Execute a shell command on every button press
        if baddr == '':
            print("Alert: command will be executed with any Shutter!")
        commanding_baddr = baddr

        def execute_command(baddr, full_raw):
            print("Last raw bytes: " + full_raw[-2])
            if baddr == commanding_baddr or commanding_baddr == '':
                print("Executing: " + command)
                os.system(command)

        self.on_shooter_appeared_callback = execute_command
        self.on_shutter_work()

    def on_shutter_work(self):
        self.start_lescan()
        self.start_hcidump()
        with open(self.hcidump.outf.name, "r") as f:
            while True:
                line = f.readline()
                line = line.rstrip()
                # Look for this line first:
                # > 04 3E 2B 02 01 03 01 1F CA 62 0E B0 EF 1F 02 01 05 1B FF E2
                if line.startswith('>') and line.endswith('E2'):
                    # Then for one like:
                    # 00 A0 9D 4F E0 10 35 F1 00 00 00 00 00 00 00 00 00 00 00
                    # 00
                    line2 = f.readline()
                    if line2.startswith('  00 A0'):
                        line3 = f.readline()
                        full_raw = line + line2 + line3
                        baddr = self.get_baddr_shutter(line + line2 + line3)
                        if self.filter_by_time:
                            print("Filtering by time...")
                            last_time = self.baddr_time_dict.get(baddr, None)
                            if last_time is None:
                                print("First time we see this baddr....")
                                self.baddr_time_dict[baddr] = time.time()
                                if self.on_shooter_appeared_callback:
                                        self.on_shooter_appeared_callback(baddr, full_raw)
                            else:
                                if time.time() - last_time > self.filter_time:
                                    self.baddr_time_dict[baddr] = time.time()
                                    print("Passed time filter!")
                                    if self.on_shooter_appeared_callback:
                                        self.on_shooter_appeared_callback(baddr, full_raw)
                                else:
                                    # it's the same buttonpress... ignoring
                                    print("Its the same buttonpress...")
                                    pass
                        else:
                            if self.on_shooter_appeared_callback:
                                self.on_shooter_appeared_callback(baddr, full_raw)
                time.sleep(self.sleep_time)

    def get_baddr_shutter(self, raw_str):
        # We look for a scan like:
        # > 04 3E 2B 02 01 03 01 1F CA 62 0E B0 EF 1F 02 01 05 1B FF E2
        #   00 A0 9D 4F E0 10 35 F1 00 00 00 00 00 00 00 00 00 00 00 00
        #   00 00 00 00 00 A6
        # which contains the Bluetooth Address inverted and the words
        # That the app looks for, E200 and A0
        # > XX XX XX XX XX XX XX BB BB BB BB BB BB YY YY YY YY YY YY E2
        #   00 A0 YY YY YY YY YY YY 00 00 00 00 00 00 00 00 00 00 00 00
        #   00 00 00 00 00 ZZ
        # Clean raw_str
        raw_str = raw_str.replace('>', '')
        raw_str = raw_str.replace(' ', '')
        raw_str = raw_str.replace('\n', '')
        # print("Raw string no spaces:")
        # print(raw_str)
        # Cleaned looks like:
        # 043E2B020103011FCA620EB0EF1F0201051BFFE200A09D4FE01035F1000000000000000000000000
        # mac address at
        mac_reversed = raw_str[14:26]
        # split 2 by 2 characters in a list
        split_mac_reversed = [mac_reversed[i:i + 2]
                              for i in range(0, len(mac_reversed), 2)]
        # reverse the list
        split_mac_reversed.reverse()
        baddr = ''.join(split_mac_reversed)

        return baddr

    def start_lescan(self):
        # The ShutterBall is advertised as a LimitedDiscoverable device
        # We also allow duplicates (--duplicates) otherwise we would
        # get notified only once every long time
        self.lescan = ShellCmd('hcitool lescan --discovery=l --duplicates')

    def start_hcidump(self):
        self.hcidump = ShellCmd('hcidump --raw')

    def stop(self):
        print("Stopping...")
        if self.lescan:
            self.lescan.kill()
        if self.hcidump:
            self.hcidump.kill()

    def __del__(self):
        self.stop()


if __name__ == '__main__':
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\n" +
             "Please try again, this time using 'sudo'. Exiting.")

    if len(sys.argv) > 1:
        what_to_do = sys.argv[1]
    else:
        what_to_do = 'find'

    if what_to_do == 'find':
        try:
            sb = ShutterBall()
            sb.find_shutters()
        except KeyboardInterrupt:
            print("Control+C pressed, stopping...")
    elif what_to_do == 'play_audio':
        try:
            sb = ShutterBall()
            sb.execute_command_on_button_press('nohup aplay /home/sam/tmp/bluetoothle/shutter_click_16pcm.wav &')
        except KeyboardInterrupt:
            print("Control+C pressed, stopping...")
    else:
        print("Not implemented.")
