"""
    Copyright 2023, University of Valladolid.
    
    Contributors: Carlos Manuel Sangrador, David de Pintos, Noemí Merayo,
                  Alfredo Gonzalez, Miguel Campano.
    
    User Interface for GCOdeveloper/OpenFlow_Agent.

    This file is part of GCOdeveloper/OpenFlow_Agent.

    GCOdeveloper/OpenFlow_Agent is free software: you can redistribute it and/or 
    modify it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or (at your
    option) any later version.

    GCOdeveloper/OpenFlow_Agent is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
    more details.

    You should have received a copy of the GNU General Public License along with
    GCOdeveloper/OpenFlow_Agent. If not, see <https://www.gnu.org/licenses/>.
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
