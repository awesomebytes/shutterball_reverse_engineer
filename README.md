# Use Shutterball from Ubuntu (or anything with BLE)
Find your shutterball with (press the button):
```bash
sudo ./shutter_hack.py find
Found ShutterBall with Bluetooth mac address:
EFB00E62CA1F
From RAW input:
> 04 3E 2B 02 01 03 01 1F CA 62 0E B0 EF 1F 02 01 05 1B FF E2  00 A0 9D 4F E0 10 35 F1 00 00 00 00 00 00 00 00 00 00 00 00 
  00 00 00 00 00 AD
```

Example application playing an audio with it:
```bash
sudo ./shutter_hack.py play_audio
```

# How does ShutterBall work?
The device turns on when you press the button. It then advertises itself using a custom payload (used to identify the devices from the official app). It advertises itself in between 2 and 4 times (haven't looked too deep into it). It also contains 2 bytes in the end of the payload that change on every advertising.

The raw hex values of the device advertising are:
```
04 3E 2B 02 01 03 01 1F CA 62 0E B0 EF 1F 02 01 05 1B FF E2 
00 A0 9D 4F E0 10 35 F1 00 00 00 00 00 00 00 00 00 00 00 00 
00 00 00 00 00 B4
```

Where:
```
XX XX XX XX XX XX XX BB BB BB BB BB BB XX XX XX XX XX XX E2 
00 A0 YY YY YY YY YY YY 00 00 00 00 00 00 00 00 00 00 00 00 
00 00 00 00 00 ZZ
```
`BB BB BB BB BB` is the MAC address reversed, `E200` and nextly `A0` is used to identify the devices as remotes. ZZ is the changing byte in the end. Maybe used to differentiate the same buttonpress?

You must use an app to use the shutter because it is not actually using the BLE protocol to become a typical shutter button. The app takes care of this continuous scanning to trigger a picture. Making an app that runs as a service and triggers a camera buttonpress would make this device more useful (who wants to use their crappy camera app?).


# Research notes
1. Scan for the device.

One can use the Android app [nRF Connect](https://play.google.com/store/apps/details?id=no.nordicsemi.android.mcp&hl=en). But it refuses to connect. We found out the Bluetooth MAC address to be: `EF:B0:0E:62:CA:1F`

2. Try to connect.

Both `nRf Connect` and `gatttool` couldn't connect:
```bash
sudo gatttool -b EF:B0:0E:62:CA:1F -I
[sudo] password for sam: 
[   ][EF:B0:0E:62:CA:1F][LE]> connect
Connecting... connect error: Connection refused (111)
[   ][EF:B0:0E:62:CA:1F][LE]>
```

3. Extra data.
Chip is: N51822

The motherboard says: BM-LDS520 Ver 1.0

And there is a sticker saying: (13100410-01) HW1.1 / FW3.1

Using the app you click on Pair, then press the button, and it's paired. Then you can take pictures ONLY WITH THAT APP when pressing the button. It apparently can be paired with more devices at the same time. This all sounds like typical bluetooth low energy behaviour.



4. Reverse engineer the Android app:
The app can be found [here](https://play.google.com/store/apps/details?id=com.semilink.shutterpanorama_gg). The APK can be stolen from the store with: [https://apps.evozi.com/apk-downloader/?id=com.semilink.shutterpanorama_gg](https://apps.evozi.com/apk-downloader/?id=com.semilink.shutterpanorama_gg).

We can use [apktool](https://ibotpeaches.github.io/Apktool/install/) to reverse engineer the APK file.

And to explore the project we should use [Android studio](https://developer.android.com/studio/install.html).

We extract the APK like:
```bash
./apktool d com.semilink.shutterpanorama_gg.apk 
I: Using Apktool 2.2.2 on com.semilink.shutterpanorama_gg.apk
I: Loading resource table...
I: Decoding AndroidManifest.xml with resources...
I: Loading resource table from file: /home/sam/.local/share/apktool/framework/1.apk
I: Regular manifest package...
I: Decoding file-resources...
I: Decoding values */* XMLs...
I: Baksmaling classes.dex...
I: Copying assets and libs...
I: Copying unknown files...
I: Copying original files...
```

Didn't work. But if we extract the APK, we find `classes.dex` which we can try to convert to java code.

Download dex2jar: https://sourceforge.net/projects/dex2jar/files/latest/download?source=files

Extract.

Give executable permission to .sh files.

Use dex2jar:
```bash
./d2j-dex2jar.sh ../classes.dex 
dex2jar ../classes.dex -> ./classes-dex2jar.jar
```
Download jd-gui: http://jd.benow.ca/
Install
    dpkg -i thing.deb

Execute:
    java -jar /opt/jd-gui/jd-gui.jar

Interesting code:
```java
// DevReg_Dialog.class
  public String a(BluetoothDevice paramBluetoothDevice, byte[] paramArrayOfByte)
  {
    Object localObject = null;
    int k = paramArrayOfByte.length;
    String str1 = a(paramArrayOfByte);
    if (paramBluetoothDevice.getAddress() != null)
    {
      paramArrayOfByte = (byte[])localObject;
      if (paramBluetoothDevice.getName() == null)
      {
        paramArrayOfByte = (byte[])localObject;
        if (k == 62)
        {
          paramBluetoothDevice = str1.substring(10, 14);
          String str2 = str1.substring(14, 16);
          str1.substring(16, 28);
          paramArrayOfByte = (byte[])localObject;
          if (paramBluetoothDevice.equals("e200"))
          {
            paramArrayOfByte = (byte[])localObject;
            if (str2.equals("a0")) {
              paramArrayOfByte = str1.substring(16, 28);
            }
          }
        }
      }
      return paramArrayOfByte;
    }
    Log.e("DevReg_Dialog", "getaddress is null");
    return null;
  }
```
This function if for the [callback](https://developer.android.com/reference/android/bluetooth/BluetoothAdapter.LeScanCallback.html):
```java 
void onLeScan (BluetoothDevice device, 
                int rssi, 
                byte[] scanRecord)
```



Apparently it looks for size `62` in the scanRecord.

Using nrf connect I can see the extended data as:

`0x0201051BFFE200A09D4FE01035F10000000000000000000000000000000000`

In ipython:
```python
In [13]: paramArrayOfByte = '0201051BFFE200A09D4FE01035F100000000000000000000000
    ...: 00000000000'

In [14]: len(paramArrayOfByte)
Out[14]: 62
```

Good.

Next step:
```python
In [15]:  paramBluetoothDevice = paramArrayOfByte[ 10: 14]

In [16]: paramBluetoothDevice
Out[16]: 'E200'
```
Good.
```python
In [18]: str2 = paramArrayOfByte[14:16]

In [19]: str2
Out[19]: 'A0'
```

If we get `E200` and `A0`, which we did, we use:
```
# paramArrayOfByte = str1.substring(16, 28)
In [20]: paramArrayOfByte[16:28]
Out[20]: '9D4FE01035F1'
```

So apparently the app learns that extra info of the device to recognize it. And it just bluetooth scans all the time (and probably triggers when the device appears again). That's why it needs a special app to be used.

To analyse we need
    sudo apt-get install bluez-hcidump

And with that:
```bash
# shell 1
sudo hcitool lescan --discovery=l
LE Scan ...
EF:B0:0E:62:CA:1F (unknown)
```

```bash
sudo hcidump --raw
HCI sniffer - Bluetooth packet analyzer ver 2.5
device: hci0 snap_len: 1500 filter: 0xffffffffffffffff
> 04 3E 2B 02 01 03 01 1F CA 62 0E B0 EF 1F 02 01 05 1B FF E2 
  00 A0 9D 4F E0 10 35 F1 00 00 00 00 00 00 00 00 00 00 00 00 
  00 00 00 00 00 B4
```

Which we can see the info we needed.



