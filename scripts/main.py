#!/usr/bin/env python3

#konashi
try:
    from asyncio.exceptions import CancelledError
except ModuleNotFoundError:
    from asyncio import CancelledError
from konashi import *
import konashi
from konashi.Settings import System as KonashiSystem
from konashi.Settings import Bluetooth as KonashiBluetooth
from konashi.Io import SoftPWM as KonashiSPWM
from konashi.Io import HardPWM as KonashiHPWM
from konashi.Io import Gpio as KonashiGpio
from konashi.Io import Analog as KonashiAnalog
from konashi.Io import I2C as KonashiI2C
from konashi.Builtin import Presence as KonashiPresence
from konashi.Builtin import AccelGyro as KonashiAccelGyro
from konashi.Builtin import Temperature as KonashiTemperature
from konashi.Builtin import Humidity as KonashiHumidity
from konashi.Builtin import Presence as KonashiPresence
from konashi.Builtin import RGBLed as KonashiRGB
import logging
import asyncio
import argparse
#emo
from emo import emo_send
#other
from Timer import *

global Temp
global Hum
global Press
Temp=Hum=Press=0.0

global END
END=False
global Presence
Presence=False
global RGB
RGB=[
        [0,0,0],
        [255,255,0],
        [0,255,0],
        [0,255,128],
        [255,255,255],
    ]
global msg
msg=[
        "",
        "土が乾燥してるよ、水をあげよう",
        "土はいい感じ",
        "水あげすぎだよ",
    ]
global alpha
alpha=255

async def main(device):
    global END
    try:
        if device is None:
            logging.info("Scan for konashi devices for 5 seconds")
            ks = await Konashi.search(5)
            if len(ks) > 0:
                device = ks[0]
                logging.info("Use konashi device: {}".format(device.name))
            else:
                logging.error("Could no find a konashi device")
                return
        try:
            await device.connect(5)
        except Exception as e:
            logging.error("Could not connect to konashi device '{}': {}".format(device.name, e))
            return
        logging.info("Connected to device")

        global button
        button=False
        #function
        def LED_to_soil(soil):
            if 0.0 <= soil and soil < 29.33:
                d=1
            elif 29.33 <= soil and soil < 68.43:
                d=2
            elif 68.43 <= soil:
                d=3
            return d
        def input_cb(pin, level):
            global button
            if level:
                button=True
            logging.info("Pin {}: {}".format(pin, level))
        # Input callback function set
        device.io.gpio.set_input_cb(input_cb)
        # GPIO0: enable, input, notify on change, pull-down off, pull-up off, wired function off
        # GPIO1~4: enable, output, pull-down off, pull-up off, wired function off
        await device.io.gpio.config_pins([
            (0x01, KonashiGpio.PinConfig(KonashiGpio.PinDirection.INPUT, KonashiGpio.PinPull.NONE, True)),
        ])

        # set analog input callback
        def Ainput_cb(pin, val):
            global Temp
            global Hum
            global Press
            global soil
            if pin==0:
                soil=(val/3.3)*100
                logging.info("Ain{}: {:.2f}V/soil={:.2f}%/{}[℃],{}[%],{}[hPa]".format(pin, val,soil,Temp,Hum,Press))
        device.io.analog.set_input_cb(Ainput_cb)

        # setup ADC read period to 0.5s, ref to VDD (3.3V) and enable all pins as input
        await device.io.analog.config_adc_period(0.5)
        await device.io.analog.config_adc_ref(KonashiAnalog.AdcRef.REF_VDD)
        await device.io.analog.config_pins([(0x07, KonashiAnalog.PinConfig(True, KonashiAnalog.PinDirection.INPUT, True))])
        #気温、湿度、気圧
        def temperature_cb(temp):
            global Temp
            Temp=temp

        def humidity_cb(hum):
            global Hum
            Hum=hum

        def pressure_cb(press):
            global Press
            Press=press

        def presence_cb(pres):#人感センサー
            global Presence
            Presence=pres
            print("Presence1:", pres)

        #気温,湿度,気圧
        global Temp
        global Hum
        global Press
        await device.builtin.temperature.set_callback(temperature_cb)
        await device.builtin.humidity.set_callback(humidity_cb)
        await device.builtin.pressure.set_callback(pressure_cb)
        #人感センサ設定
        await device.builtin.presence.set_callback(presence_cb)
        global soil
        soil=0.00
        d=0
        sendflag=False
        t1=Timer()
        while True:
            if Presence:
                if not sendflag:
                    d=LED_to_soil(soil)
                    emomsg="気温"+str(Temp)+"度,湿度"+str(Hum)+"％,"+str(Press)+"ヘクトパスカルだよ。"+msg[d]
                    #emo_send(emomsg,[RGB[d][0],RGB[d][1],RGB[d][2]])
                    sendflag=True
                t1.reset()
            else:
                d=0
                if t1.stand_by(10):
                    sendflag=False
            await device.builtin.rgbled.set(RGB[d][0],RGB[d][1],RGB[d][2],alpha,100)
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Stop loop")
        END=True
        await device.builtin.rgbled.set(RGB[d][0],RGB[d][1],RGB[d][2],0,1)
    finally:
        try:
            if device is not None:
                await device.disconnect()
                logging.info("Disconnected")
        except konashi.Errors.KonashiConnectionError:
            pass
    logging.info("Exit")


parser = argparse.ArgumentParser(description="Connect to a konashi device, setup the PWMs and control them.")
parser.add_argument("--device", "-d", type=Konashi, help="The konashi device name to use. Ommit to scan and use first discovered device.")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
main_task = None
try:
    main_task = loop.create_task(main(args.device))
    loop.run_until_complete(main_task)
except KeyboardInterrupt:
    if main_task is not None:
        main_task.cancel()
        loop.run_until_complete(main_task)
        main_task.exception()
finally:
    loop.close()