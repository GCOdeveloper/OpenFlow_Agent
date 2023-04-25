"""
    Copyright 2023, University of Valladolid.
    
    User Interface for GCOdeveloper/OpenFlow_Agent.

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

import json
import signal

from onosController import ONOSController
from menu import Menu

def main():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

    file_json = "SDN_controller.config"

    with open(file_json) as fp:
        config = json.load(fp)
        controller = ONOSController(config["SDN-controller"]["ip_address"], config["SDN-controller"]["port"])

    controller.getDevices()

    menu = Menu(controller)
    menu.menuCreation()

if __name__ == '__main__':
    main()
