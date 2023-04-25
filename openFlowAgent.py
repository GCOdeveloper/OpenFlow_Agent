"""
    Copyright 2023, University of Valladolid.
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
        http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import sys
import json
import logging
import src.agentQueue
from src.agentQueue import oltQueue
from src.oltDevice import OLTDevice
from src.onosAdaptor import ONOSAdaptor

deviceList = {}

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s: %(message)s',
                    datefmt='%m-%d-%Y %H:%M:%S',
                    handlers=[
                        logging.FileHandler('agent.log'),
                        logging.StreamHandler(sys.stdout)
                    ])

def main():
    logging.info("Starting OpenFlow Agent...")

    file_json = "openFlow_agent.config"

    with open(file_json) as fp:
        config = json.load(fp)

        for olt in config["olts"]:
            voip_start = olt["voip_extension_start"] if "voip_extension_start" in olt else 1111
            voip_end = olt["voip_extension_end"] if "voip_extension_end" in olt else 9999
            device = OLTDevice(ip_address = olt["ip_address"], port = olt["port"],
                               voip_extensions_start = voip_start, voip_extensions_end = voip_end)

            datapath_id = device.generate()

            if (datapath_id != ""):
                logging.info("Registered OLT:")
                logging.info("****IP address: %s", olt["ip_address"])
                logging.info("****Port: %d", olt["port"])
                logging.info("****Datapath ID: %s", datapath_id)

                deviceList[datapath_id] = device

                device.enable_olt()
                device.enable_controller(ipONOS = config["SDN-controller"]["ip_address"], portONOS = config["SDN-controller"]["port"])
            else:
                logging.error("OLT %s:%d does not respond", olt["ip_address"], olt["port"])

    if len(deviceList) == 0:
        logging.error("OLTs not found")
        return

    #Queue for OLT an ONOS actions
    while True:
        try:
            item = oltQueue.get(block = True, timeout = 3)
        except src.agentQueue.queue.Empty:
            continue

        if (item.datapath_id not in deviceList):
            continue

        if item.source == "olt":
            if item.isClass("OnuDisc"):
                deviceList[item.datapath_id].initialize_onu(item.data.intf_id, item.data.vendor_id, item.data.vendor_specific)

            elif item.isClass("OnuInd"):
                if (item.data.fail_reason == 0): # FAIL_REASON_NONE
                    deviceList[item.datapath_id].create_ports(item.data.intf_id, item.data.onu_id, item.data.oper_state, item.data.admin_state)
                else:
                    logging.error("ONU Indication error:")
                    if item.data.fail_reason == 1: # RANGING_FAILURE
                        logging.error("****Activarion Fail Reason: RANGING")
                    elif item.data.fail_reason == 2: # PASSWORD_AUTHENTICATION_FAILURE
                        logging.error("****Activarion Fail Reason: PASSWORD AUTHENTICATION")
                    elif item.data.fail_reason == 3: # LOS_FAILURE
                        logging.error("****Activarion Fail Reason: LOS")
                    elif item.data.fail_reason == 4: # ONU_ALARM_FAILURE
                        logging.error("****Activarion Fail Reason: ONU ALARM")
                    elif item.data.fail_reason == 5: # SWITCH_OVER_FAILURE
                        logging.error("****Activarion Fail Reason: SWITCH OVER")

            elif item.isClass("FlowStatsInd"):
                deviceList[item.datapath_id].update_Flow_statistics(item.data.flow_id,
                                                                    item.data.rx_bytes,
                                                                    item.data.rx_packets,
                                                                    item.data.tx_bytes,
                                                                    item.data.tx_packets,
                                                                    item.data.timestamp)
                logging.info("Received OLT Flow Stats indication")
            else:
                logging.error("Queue OLT Indication not found")
        elif item.source == "onos":
            if item.isClass("Flow"):
                deviceList[item.datapath_id].configureFlows(item.data.flow_id, item.data.flow_action)

        oltQueue.task_done()

if __name__ == '__main__':
    main()
