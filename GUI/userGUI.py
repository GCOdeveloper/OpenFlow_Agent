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
