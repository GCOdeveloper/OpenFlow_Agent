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

import os

import time

from consolemenu import *
from consolemenu.items import *

from exceptions import *

class Menu:


    def __init__(self, ONOScontroller):
        self.controller = ONOScontroller
        self.menuTitle = "OpenFlow Agent"
        self.menuSubtitle = "No OLT selected"
        self.actualDevice = None

    def devicesSubMenu(self):
        #Submenu con los distintos devices registrados
        self.deviceMenu = ConsoleMenu(title="Select a OLT", subtitle="Ids of all registered OLTs")

        dictDevices = {}
        listDevices = self.controller.all_devices_ids()
        for i in range(len(listDevices)):
            dictDevices["device_{0}".format(i)] = FunctionItem(text=listDevices[i], function=self.updateDevice, 
                                                               args=[listDevices[i]], menu=self.deviceMenu, should_exit=True)
        for device in dictDevices.values():
            self.deviceMenu.append_item(device)

        self.selectDevice_item = SubmenuItem(text="Select a OLT", submenu=self.deviceMenu, menu=self.mainMenu)

    def serviceSubMenu(self):
        #Submenu para la seleccionar el tipo de servicio
        self.serviceMenu = ConsoleMenu(title="Configure the selected OLT. Select type service", subtitle=self.menuSubtitle)
 
        ethernet_item = FunctionItem(text="Ethernet service", function=self.ethernetSubMenu, menu=self.serviceMenu)
        multicast_item = FunctionItem(text="Multicast service", function=self.multicastSubMenu, menu=self.serviceMenu)
        voip_item = FunctionItem(text="VoIP service", function=self.voIpSubMenu, menu=self.serviceMenu)
        

        self.serviceMenu.append_item(ethernet_item)
        self.serviceMenu.append_item(multicast_item)
        self.serviceMenu.append_item(voip_item)
        
        self.serviceMenu.show()


    def ethernetSubMenu(self):
        #Submenu para la seleccionar el puerto
        self.ethernetMenu = ConsoleMenu(title="Configure the ethernet service. Select ONU port", subtitle=self.menuSubtitle)
        
        dictPorts = {}
        listPorts = self.controller.all_ports_ids(self.actualDevice)

        for dato, valor in listPorts.items():

            POTS = True if (int(valor) >> 27) & 0x01 == 1 else False
  
            if POTS == False and valor !="20":
                dictPorts["port_{0}".format(dato)] = FunctionItem(text=dato, function=self.configureServiceEthernet, 
                                                               args=[valor], menu=self.ethernetMenu)
        for port in dictPorts.values():
            self.ethernetMenu.append_item(port)
        #showPorts_item = FunctionItem(text=listPorts[3], function=self.configureService, menu=self.ethernetMenu)

        self.ethernetMenu.show()
        #self.ethernet_item = SubmenuItem(text="Ethernet service", submenu=self.portMenu, menu=self.serviceMenu)

    def voIpSubMenu(self):
        #Submenu para la seleccionar el puerto
        self.voIpMenu = ConsoleMenu(title="Configure the VoIP service. Select ONU port", subtitle=self.menuSubtitle)
        
        dictPorts = {}
        listPorts = self.controller.all_ports_ids(self.actualDevice)

        for dato, valor in listPorts.items():

            POTS = True if (int(valor) >> 27) & 0x01 == 1 else False
  
            if POTS == True and valor !="20":
                dictPorts["port_{0}".format(dato)] = FunctionItem(text=dato, function=self.configureServiceVoIp, 
                                                               args=[valor], menu=self.voIpMenu)
        for port in dictPorts.values():
            self.voIpMenu.append_item(port)
        #showPorts_item = FunctionItem(text=listPorts[3], function=self.configureService, menu=self.ethernetMenu)

        self.voIpMenu.show()
        #self.ethernet_item = SubmenuItem(text="Ethernet service", submenu=self.portMenu, menu=self.serviceMenu)

    def multicastSubMenu(self):
        #Submenu para la seleccionar el puerto
        self.multicastMenu = ConsoleMenu(title="Configure the multicast service. Select ONU port", subtitle=self.menuSubtitle)
        
        dictPorts = {}
        listPorts = self.controller.all_ports_ids(self.actualDevice)

        for dato, valor in listPorts.items():

            POTS = True if (int(valor) >> 27) & 0x01 == 1 else False
  
            if POTS == False and valor !="20":
                dictPorts["port_{0}".format(dato)] = FunctionItem(text=dato, function=self.configureServiceMulticast, 
                                                               args=[valor], menu=self.multicastMenu)
        for port in dictPorts.values():
            self.multicastMenu.append_item(port)

        self.multicastMenu.show()

    def deleteSubMenu(self):
        #Submenu para la seleccionar el puerto
        self.deleteMenu = ConsoleMenu(title="Delete service from a ONU port. Select ONU port", subtitle=self.menuSubtitle)
        
        dictPorts = {}
        listPorts = self.controller.all_ports_ids(self.actualDevice)

        for dato, valor in listPorts.items():
  
            if valor !="20":
                dictPorts["port_{0}".format(dato)] = FunctionItem(text=dato, function=self.showService, 
                                                               args=["delete", valor], menu=self.deleteMenu)
        for port in dictPorts.values():
            self.deleteMenu.append_item(port)

        self.deleteMenu.show()

    def showConfigSubMenu(self):
        #Submenu para la seleccionar el puerto
        self.showConfigMenu = ConsoleMenu(title="Show current configuration of a ONU port. Select ONU port", subtitle=self.menuSubtitle)
        
        dictPorts = {}
        listPorts = self.controller.all_ports_ids(self.actualDevice)

        for dato, valor in listPorts.items():
  
            if valor !="20":
                dictPorts["port_{0}".format(dato)] = FunctionItem(text=dato, function=self.showService, 
                                                               args=["show", valor], menu=self.showConfigMenu)
        for port in dictPorts.values():
            self.showConfigMenu.append_item(port)

        self.showConfigMenu.show()

    def selectedDeviceSubMenu(self):
        #Submenu para la configuracion del device seleccionado
        self.deviceConfigurationMenu = ConsoleMenu(title="Configure the selected OLT", subtitle=self.menuSubtitle)
        #self.serviceSubMenu()

        showPorts_item = FunctionItem(text="Show all registered ONU ports", function=self.show_all_ports, menu=self.deviceConfigurationMenu)
        showService_item = FunctionItem(text="Show current configuration of a ONU port", function=self.showConfigSubMenu, menu=self.deviceConfigurationMenu)
        configureService_item = FunctionItem(text="Configure a service on a ONU port", function=self.serviceSubMenu, menu=self.deviceConfigurationMenu)
        deleteService_item = FunctionItem(text="Delete service from a ONU port", function=self.deleteSubMenu, menu=self.deviceConfigurationMenu)
        statisticsService_item = FunctionItem(text="Show service ONU port statistics", function=self.showStatistics, menu=self.deviceConfigurationMenu)

        self.deviceConfigurationMenu.append_item(showPorts_item)
        self.deviceConfigurationMenu.append_item(showService_item)
        self.deviceConfigurationMenu.append_item(configureService_item)
        self.deviceConfigurationMenu.append_item(deleteService_item)
        self.deviceConfigurationMenu.append_item(statisticsService_item)

        self.deviceConfiguration_item = SubmenuItem(text="Configure the selected OLT", submenu=self.deviceConfigurationMenu, menu=self.mainMenu)

    def menuCreation(self):
        #Menu principal
        self.mainMenu = ConsoleMenu(title=self.menuTitle, subtitle=self.menuSubtitle)
        self.showDevices_item = FunctionItem(text="Show all registered OLTs", function=self.show_all_devices, menu=self.mainMenu)
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

        self.menuSubtitle = "Selected OLT: \"" + self.actualDevice + "\""
        self.mainMenu.subtitle = self.menuSubtitle
        self.deviceConfigurationMenu.subtitle = self.menuSubtitle

        self.controller.getDevicePorts(self.actualDevice)
        self.controller.getDeviceMeters(self.actualDevice)
        self.controller.getDeviceGroups(self.actualDevice)


    def show_all_ports(self):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
        else:
            self.controller.showDevicePorts(self.actualDevice)
            input("\nPress Intro to continue ...")

    def showService(self, action, port):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
            return

        while True:
            print("\nCurrent ONU port configuration:")

            try:
                ONUport = str(port)
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

    def configureServiceEthernet(self, selectedPort):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
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
                dictFlow["ONUport"] = selectedPort
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

        self.controller.createPortService(dictFlow, "ethernet")

        input("\nPress Intro to return ...")

    def configureServiceVoIp(self, selectedPort):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
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
                dictFlow["ONUport"] = selectedPort
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
                dictFlow["IpServer"] = input("\tEnter server IP: ")
                if dictFlow["IpServer"] == "":
                    raise NoInputError
                
                #Comprobar ip válida

            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                netmaskServerAux = input("\tEnter server netmask: ")
                if netmaskServerAux == "":
                    raise NoInputError
                
                #Comprobar ip válida

                netmaskServerVec = netmaskServerAux.split(sep =".")

                bytesTotal =""

                for i in range(len(netmaskServerVec)):
                    byte = int(netmaskServerVec[i])
                    byte = bin(byte)
                    bytesTotal = bytesTotal + str(byte)

                netmaskServer=str(bytesTotal.count("1"))
                dictFlow["netmaskServer"] = netmaskServer

            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue


            
            try:
                dictFlow["IpUser"] = input("\tEnter user IP: ")
                if dictFlow["IpUser"] == "":
                    raise NoInputError
                
                #Comprobar ip válida

            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                os.system("clear")
                continue

            try:
                netmaskUserAux = input("\tEnter user netmask: ")
                if netmaskUserAux == "":
                    raise NoInputError
                
                #Comprobar ip válida

                netmaskUserVec = netmaskUserAux.split(sep =".")

                bytesTotal =""

                for i in range(len(netmaskUserVec)):
                    byte = int(netmaskUserVec[i])
                    byte = bin(byte)
                    bytesTotal = bytesTotal + str(byte)

                netmaskUser=str(bytesTotal.count("1"))
                dictFlow["netmaskUser"] = netmaskUser
                
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
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

        self.controller.createPortService(dictFlow, "voip")

        input("\nPress Intro to return ...")

    def configureServiceMulticast(self, selectedPort):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
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
                dictFlow["ONUport"] = selectedPort
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

            """try:
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
                continue"""

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

        self.controller.createPortService(dictFlow, "multicast")

        input("\nPress Intro to return ...")

    def showStatistics(self):
        if self.actualDevice is None:
            input("\nFirst select a OLT please ...")
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
