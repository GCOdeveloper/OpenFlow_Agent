import os

from consolemenu import *
from consolemenu.items import *

from exceptions import *

class Menu:

    def __init__(self, ONOScontroller):
        self.controller = ONOScontroller
        self.menuTitle = "OpenFlow Agent"
        self.menuSubtitle = "No device selected"
        self.actualDevice = None

    def devicesSubMenu(self):
        #Submenu con los distintos devices registrados
        self.deviceMenu = ConsoleMenu(title="Select a device", subtitle="Ids of all registered devices")

        dictDevices = {}
        listDevices = self.controller.all_devices_ids()
        for i in range(len(listDevices)):
            dictDevices["device_{0}".format(i)] = FunctionItem(text=listDevices[i], function=self.updateDevice, 
                                                               args=[listDevices[i]], menu=self.deviceMenu, should_exit=True)
        for device in dictDevices.values():
            self.deviceMenu.append_item(device)

        self.selectDevice_item = SubmenuItem(text="Select a device", submenu=self.deviceMenu, menu=self.mainMenu)

    def selectedDeviceSubMenu(self):
        #Submenu para la configuracion del device seleccionado
        self.deviceConfigurationMenu = ConsoleMenu(title="Configure the selected device", subtitle=self.menuSubtitle)

        showPorts_item = FunctionItem(text="Show all registered ports", function=self.show_all_ports, menu=self.deviceConfigurationMenu)
        showService_item = FunctionItem(text="Show current configuration of a port", function=self.showService, args=["show"], menu=self.deviceConfigurationMenu)
        configureService_item = FunctionItem(text="Configure a service on a port", function=self.configureService, menu=self.deviceConfigurationMenu)
        deleteService_item = FunctionItem(text="Delete service from a port", function=self.showService, args=["delete"], menu=self.deviceConfigurationMenu)
        statisticsService_item = FunctionItem(text="Show service port statistics", function=self.showStatistics, menu=self.deviceConfigurationMenu)

        self.deviceConfigurationMenu.append_item(showPorts_item)
        self.deviceConfigurationMenu.append_item(showService_item)
        self.deviceConfigurationMenu.append_item(configureService_item)
        self.deviceConfigurationMenu.append_item(deleteService_item)
        self.deviceConfigurationMenu.append_item(statisticsService_item)

        self.deviceConfiguration_item = SubmenuItem(text="Configure the selected device", submenu=self.deviceConfigurationMenu, menu=self.mainMenu)

    def menuCreation(self):
        #Menu principal
        self.mainMenu = ConsoleMenu(title=self.menuTitle, subtitle=self.menuSubtitle)
        self.showDevices_item = FunctionItem(text="Show all registered devices", function=self.show_all_devices, menu=self.mainMenu)
        self.devicesSubMenu()
        self.selectedDeviceSubMenu()

        #Añadimos los distintos items del "mainMenu" y lanzamos el menu
        self.mainMenu.append_item(self.showDevices_item)
        self.mainMenu.append_item(self.selectDevice_item)
        self.mainMenu.append_item(self.deviceConfiguration_item)
        self.mainMenu.show()

    def show_all_devices(self):
        self.controller.showDevices()
        input("\nPress Intro to continue ...")

    def updateDevice(self, selectedDevice):
        self.actualDevice = selectedDevice

        self.menuSubtitle = "Selected device: \"" + self.actualDevice + "\""
        self.mainMenu.subtitle = self.menuSubtitle
        self.deviceConfigurationMenu.subtitle = self.menuSubtitle

        self.controller.getDevicePorts(self.actualDevice)
        self.controller.getDeviceMeters(self.actualDevice)

    def show_all_ports(self):
        if self.actualDevice is None:
            input("\nFirst select a device please ...")
        else:
            self.controller.showDevicePorts(self.actualDevice)
            input("\nPress Intro to continue ...")

    def showService(self, action):
        if self.actualDevice is None:
            input("\nFirst select a device please ...")
            return

        while True:
            print("\nCurrent ONU port configuration:")

            try:
                ONUport = input("\n\tEnter ONU port: ")
                if ONUport == "":
                    raise NoInputError
                if not ONUport.isnumeric():
                    raise InputNotIntegerError
                if not self.controller.checkPort(self.actualDevice, ONUport):
                    raise PortOnuNotExistError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except PortOnuNotExistError:
                print("\n\tThe input value does not match any registered port!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            break

        self.controller.getPortService(self.actualDevice, ONUport, action)

        input("\nPress Intro to return ...")

    def configureService(self):
        if self.actualDevice is None:
            input("\nFirst select a device please ...")
            return

        dictFlow = {}

        while True:
            print("\nEnter the service configuration parameters:")

            try:
                dictFlow["priority"] = input("\n\tEnter priority (1 - 65535): ")
                if dictFlow["priority"] == "":
                    raise NoInputError
                if not dictFlow["priority"].isnumeric():
                    raise InputNotIntegerError
                if not 0 < int(dictFlow["priority"]) <= 65535:
                    raise ValueNotInRangeError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except ValueNotInRangeError:
                print("\n\tThe input value is not in range!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            dictFlow["deviceId"] = self.actualDevice

            try:
                dictFlow["ONUport"] = input("\tEnter ONU port: ")
                if dictFlow["ONUport"] == "":
                    raise NoInputError
                if not dictFlow["ONUport"].isnumeric():
                    raise InputNotIntegerError
                if not self.controller.checkPort(self.actualDevice, dictFlow["ONUport"]):
                    raise PortOnuNotExistError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except PortOnuNotExistError:
                print("\n\tThe input value does not match any registered port!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["Stag"] = input("\tEnter Stag Vlan (1 - 4096): ")
                if dictFlow["Stag"] == "":
                    raise NoInputError
                if not dictFlow["Stag"].isnumeric():
                    raise InputNotIntegerError
                if not 0 < int(dictFlow["Stag"]) <= 4096:
                    raise ValueNotInRangeError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except ValueNotInRangeError:
                print("\n\tThe input value is not in range!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["Ctag"] = input("\tEnter Ctag Vlan (1 - 4095): ")
                if dictFlow["Ctag"] == "":
                    raise NoInputError
                if not dictFlow["Ctag"].isnumeric():
                    raise InputNotIntegerError
                if not 0 < int(dictFlow["Ctag"]) < 4096:
                    raise ValueNotInRangeError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except ValueNotInRangeError:
                print("\n\tThe input value is not in range!!")
                input("\n\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["upstreamCirBandwith"] = input("\tEnter guaranteed upstream bandwith (Kbps): ")
                if dictFlow["upstreamCirBandwith"] == "":
                    raise NoInputError
                if not dictFlow["upstreamCirBandwith"].isnumeric():
                    raise InputNotIntegerError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["upstreamPirBandwith"] = input("\tEnter excess upstream bandwith (Kbps): ")
                if dictFlow["upstreamPirBandwith"] == "":
                    raise NoInputError
                if not dictFlow["upstreamPirBandwith"].isnumeric():
                    raise InputNotIntegerError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["downstreamCirBandwith"] = input("\tEnter guaranteed downstream bandwith (Kbps): ")
                if dictFlow["downstreamCirBandwith"] == "":
                    raise NoInputError
                if not dictFlow["downstreamCirBandwith"].isnumeric():
                    raise InputNotIntegerError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                dictFlow["downstreamPirBandwith"] = input("\tEnter excess downstream bandwith (Kbps): ")
                if dictFlow["downstreamPirBandwith"] == "":
                    raise NoInputError
                if not dictFlow["downstreamPirBandwith"].isnumeric():
                    raise InputNotIntegerError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            break

        input("\n\tPress Intro to create the service ...")

        self.controller.createPortService(dictFlow)

        input("\nPress Intro to return ...")

    def showStatistics(self):
        if self.actualDevice is None:
            input("\nFirst select a device please ...")
            return

        while True:
            print("\nCurrent ONU port statistics:")

            try:
                ONUport = input("\n\tEnter ONU port: ")
                if ONUport == "":
                    raise NoInputError
                if not ONUport.isnumeric():
                    raise InputNotIntegerError
                if not self.controller.checkPort(self.actualDevice, ONUport):
                    raise PortOnuNotExistError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except InputNotIntegerError:
                print("\n\tThe input value is not an integer!!")
                input("\tPlease try again...")
                os.system("clear")
                continue
            except PortOnuNotExistError:
                print("\n\tThe input value does not match any registered port!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            break

        self.controller.getPortStatistics(self.actualDevice, ONUport)

        input("\nPress Intro to return ...")
