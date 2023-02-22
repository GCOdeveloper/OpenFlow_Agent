import json
import os.path
from urllib.parse import urlparse

import time

import requests
from requests.auth import HTTPBasicAuth
from requests.structures import CaseInsensitiveDict

from flows import Flow, FlowVoIp, FlowMulticast
from meters import Meter
from groups import Group
from exceptions import NoInputError, WrongInputError

class ListOfDevices(list):

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def __str__(self):
        devicesDict = {}
        for i in range(len(self.copy())):
            devicesDict["OLT_" + str(i)] = self.copy()[i]
        return json.dumps(devicesDict, indent=2)

    def getDevicesIds(self):
        listIds = []
        for device in self.copy():
            listIds.append(device["id"])
        return listIds

class ListOfPorts(dict):

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def append(self, item):
        device_id = item.get("element")
        if device_id not in self.keys():
            self.update({device_id : []})
        listPorts = self.get(device_id)
        listPorts.append(item)
        self.update({device_id : listPorts})

    def printPorts(self, device_id):
        portDict = {}
        sortedPorts = sorted(self.copy()[device_id], key = lambda p: (p["port"]), reverse = True)
        for i in range(len(sortedPorts)):
            portDict["port_" + str(i)] = sortedPorts[i]
        return json.dumps(portDict, indent=2)

    def find(self, device_id, port_id):
        for port in self.copy()[device_id]:
            if port["port"] == port_id:
                return True
        return False

    def getPortsIds(self, device_id):
        listPortIds = {}
        for port in self.copy()[device_id]:
            #listPortIds.append(port["port"])
            listPortIds[port["annotations"]["portName"]]=port["port"]
            
        return listPortIds


class ListOfFlows(dict):

    def __init__(self, json_file):
        super().__init__()
        self.json_file = json_file
        self.load()

    def load(self):
        if os.path.exists(self.json_file):
            with open(self.json_file) as fd:
                self.update(json.load(fd))

    def save(self):
        with open(self.json_file, "w") as fd:
            json.dump(self.copy(), fd, indent=4)

    def append(self, device_id, port_id, item):
        if device_id not in self.keys():
            self.update({device_id : {}})
        if port_id not in self.get(device_id).keys():
            self.get(device_id).update({port_id : []})
        listFlows = self.get(device_id).get(port_id)
        listFlows.append(item)
        self.get(device_id).update({port_id : listFlows})
        self.save()

    def delete(self, device_id, port_id):
        if self.get(device_id) is not None:
            if self.get(device_id).get(port_id) is not None:
                self.get(device_id).pop(port_id)
                self.save()

    def getServiceConfiguration(self, device_id, port_id):
        if self.get(device_id) is not None:
            return self.get(device_id).get(port_id)
        return None

class ListOfMeters(dict):

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def append(self, item):
        device_id = item.get("deviceId")
        if device_id not in self.keys():
            self.update({device_id : []})
        listMeters = self.get(device_id)
        listMeters.append(item)
        self.update({device_id : listMeters})

    def getMeterId(self, device_id, cirRate, pirRate):
        for meter in self.copy()[device_id]:
            if ((meter["bands"][0]["rate"] == int(cirRate) and meter["bands"][1]["rate"] == int(cirRate) + int(pirRate)) or
                (meter["bands"][0]["rate"] == int(cirRate) + int(pirRate) and meter["bands"][1]["rate"] == int(cirRate))):
                return meter["id"]
        return None

class ListOfGroups(dict):

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def append(self, item):
        device_id = item.get("deviceId")
        if device_id not in self.keys():
            self.update({device_id : []})
        listGroups = self.get(device_id)
        listGroups.append(item)
        self.update({device_id : listGroups})

    def getGroupId(self, device_id, port):
        for group in self.copy()[device_id]:
            if (group["buckets"][0]["treatment"]["instructions"][0]["port"] == port ):
                return group["id"]
        return None

class ONOSController:

    def __init__(self, ipONOS="0.0.0.0", portONOS=8181):
        self.ipONOS = ipONOS
        self.portONOS = portONOS
        self.listFlows = ListOfFlows("flows_configuration.json")

    def getDevices(self):
        """Get all connected devices"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/devices"

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.RequestException as err:
            raise SystemExit(err)

        self.listDevices = ListOfDevices(resp.json()["devices"])

    def showDevices(self):
        """Show all registered devices"""

        print(self.listDevices)

    def all_devices_ids(self):
        """List of Ids attached to all registered devices"""

        return self.listDevices.getDevicesIds()

    def getDevicePorts(self, device_id):
        """Get all registerd ports"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/devices/" + device_id.replace(":", "%3A") + "/ports"

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return

        self.listPorts = ListOfPorts(resp.json()["ports"])


    def all_ports_ids(self, device_id):
        """List of Ids attached to all ports"""
        self.getDevicePorts(device_id)
        return self.listPorts.getPortsIds(device_id)

    def showDevicePorts(self, device_id):
        """Show all registered ports"""

        self.getDevicePorts(device_id)
        print(self.listPorts.printPorts(device_id))

    def checkPort(self, device_id, port_id):
        """Check if the selected port exists"""

        self.getDevicePorts(device_id)
        return self.listPorts.find(device_id, port_id)

    def getDeviceFlows(self, device_id):
        """Get all registered flows"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + device_id.replace(":", "%3A")

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return

        if len(resp.json()["flows"]) != 0:
            return resp.json()["flows"]
        else:
            return None

    def getDeviceMeters(self, device_id):
        """Get all registered meters"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/meters/" + device_id.replace(":", "%3A")

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return

        if len(resp.json()["meters"]) != 0:
            self.listMeters = ListOfMeters(resp.json()["meters"])
        else:
            self.listMeters = None

    def getDeviceGroups(self, device_id):
        """Get all registered meters"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/groups/" + device_id.replace(":", "%3A")

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return

        if len(resp.json()["groups"]) != 0:
            self.listGroups = ListOfGroups(resp.json()["groups"])
        else:
            self.listGroups = None

    def createPortService(self, dictConfig, serviceType):
        """Create the required flows and meters for a service"""

        #Check if port already has a service
        if self.listFlows.getServiceConfiguration(dictConfig["deviceId"], dictConfig["ONUport"]) is not None:
            print("\nThe selected ONU port already has a service attached!!")
            return

        #Upstream
        ##Creacion del meter de upstream
        if serviceType != "multicast":
            if not self.createMeter(dictConfig, "upstream"):
                return
            ##Creacion del flow de upstream
            if not self.createFlow(dictConfig, "upstream", serviceType):
                return


        #Downstream
        ##Creacion del meter de downstream
        if not self.createMeter(dictConfig, "downstream"):
            return

        #Creacion del group para servicio multicast
        if serviceType == "multicast":
            if not self.createGroup(dictConfig):
                return

        #Creacion del flow de downstream
        if not self.createFlow(dictConfig, "downstream", serviceType):
            return


    def createMeter(self, dictConfig, flowType):
        """Create the required meter for a service"""

        if self.listMeters is None:
            meterConfiguration = Meter(flowType)
            meterConfiguration.configMeter(dictConfig)

            url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/meters/" + meterConfiguration.meter["deviceId"].replace(":", "%3A")

            try:
                resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=meterConfiguration.headers, json=meterConfiguration.meter)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print ("\nHttp Error:", err)
                return False

            input("Meter Succesfully created")
            self.getDeviceMeters(dictConfig["deviceId"])
            dictConfig[flowType + "MeterId"] = self.listMeters.getMeterId(dictConfig["deviceId"], dictConfig[flowType + "CirBandwith"], dictConfig[flowType + "PirBandwith"])
        else:
            if self.listMeters.getMeterId(dictConfig["deviceId"], dictConfig[flowType + "CirBandwith"], dictConfig[flowType + "PirBandwith"]) is None:
                meterConfiguration = Meter(flowType)
                meterConfiguration.configMeter(dictConfig)

                url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/meters/" + meterConfiguration.meter["deviceId"].replace(":", "%3A")

                try:
                    resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=meterConfiguration.headers, json=meterConfiguration.meter)
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as err:
                    print ("\nHttp Error:", err)
                    return False

                input("Meter Succesfully created")
                self.getDeviceMeters(dictConfig["deviceId"])
                dictConfig[flowType + "MeterId"] = self.listMeters.getMeterId(dictConfig["deviceId"], dictConfig[flowType + "CirBandwith"], dictConfig[flowType + "PirBandwith"])
            else:
                input("Meter already exist")
                dictConfig[flowType + "MeterId"] = self.listMeters.getMeterId(dictConfig["deviceId"], dictConfig[flowType + "CirBandwith"], dictConfig[flowType + "PirBandwith"])

        return True

    def createFlow(self, dictConfig, flowType, service):
        """Create the required flow for a service"""

        if service == "ethernet":
            flowConfiguration = Flow(flowType)
            serviceType = flowConfiguration.configFlow(dictConfig)

        if service == "voip":
            flowConfiguration = FlowVoIp(flowType)
            serviceType = flowConfiguration.configFlowVoIp(dictConfig)

        if service == "multicast":
            flowConfiguration = FlowMulticast(flowType)
            serviceType = flowConfiguration.configFlowMulticast(dictConfig)

        if serviceType == "singleTag":
            url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + flowConfiguration.singleTag["deviceId"].replace(":", "%3A") + "?appId=" + flowConfiguration.appId

            try:
                resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=flowConfiguration.headers, json=flowConfiguration.singleTag)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print ("\nHttp Error:", err)
                return False

            input(flowType.upper() + " Flow Succesfully created")
            self.listFlows.append(dictConfig["deviceId"], dictConfig["ONUport"], self.getFlowIdFromResponse(resp))
        elif serviceType == "doubleTag":
            url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + flowConfiguration.doubleTagTable0["deviceId"].replace(":", "%3A") + "?appId=" + flowConfiguration.appId

            try:
                resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=flowConfiguration.headers, json=flowConfiguration.doubleTagTable0)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print ("\nHttp Error:", err)
                return False

            input(flowType.upper() + " Flow table 0 succesfully created")
            self.listFlows.append(dictConfig["deviceId"], dictConfig["ONUport"], self.getFlowIdFromResponse(resp))

            url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + flowConfiguration.doubleTagTable1["deviceId"].replace(":", "%3A") + "?appId=" + flowConfiguration.appId

            try:
                resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=flowConfiguration.headers, json=flowConfiguration.doubleTagTable1)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print ("\nHttp Error:", err)
                return False

            input(flowType.upper() + " Flow table 1 succesfully created")
            self.listFlows.append(dictConfig["deviceId"], dictConfig["ONUport"], self.getFlowIdFromResponse(resp))

        return True

    def createGroup(self, dictConfig):
        """Create the required group for a multicast service"""

        if self.listGroups is None:
            groupConfiguration = Group()
            groupConfiguration.configGroup(dictConfig, "1")

            url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/groups/" + dictConfig["deviceId"].replace(":", "%3A")

            try:
                resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=groupConfiguration.headers, json=groupConfiguration.group)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                print ("\nHttp Error:", err)
                return False

            input("Group Succesfully created")
            self.getDeviceGroups(dictConfig["deviceId"])
            dictConfig["GroupId"] = self.listGroups.getGroupId(dictConfig["deviceId"], dictConfig["ONUport"])
        else:
            if self.listGroups.getGroupId(dictConfig["deviceId"], dictConfig["ONUport"]) is None:
                groupConfiguration = Group()
                id_group = len(self.listGroups) + 1
                groupConfiguration.configGroup(dictConfig, id_group)

                url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/groups/" + dictConfig["deviceId"].replace(":", "%3A")

                try:
                    resp = requests.post(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=groupConfiguration.headers, json=groupConfiguration.group)
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as err:
                    print ("\nHttp Error:", err)
                    return False

                input("Group Succesfully created")
                self.getDeviceGroups(dictConfig["deviceId"])
                dictConfig["GroupId"] = self.listGroups.getGroupId(dictConfig["deviceId"], dictConfig["ONUport"])
            else:
                input("Group already exist")
                dictConfig["GroupId"] = self.listGroups.getGroupId(dictConfig["deviceId"], dictConfig["ONUport"])

        return True

    def getFlowIdFromResponse(self, response):
        """Get flow id from http response headers"""

        location = response.headers.get("location")
        parseLocation = urlparse(location)
        listElements = parseLocation.path.split("/")

        return listElements[-1]

    def getPortService(self, device_id, port_id, action):
        """Get the service configure on the selected port"""

        listOfServiceFlows = []
        listOfServiceMeters = []

        #Get Flows ids
        serviceFlows = self.listFlows.getServiceConfiguration(device_id, port_id)
        if serviceFlows is None:
            print("\nThe selected ONU port does not have any service attached!!")
            return

        #Get Flows structs
        for flow_id in serviceFlows:
            if self.getFlowFromId(device_id, flow_id) is None:
                return
            listOfServiceFlows.append(self.getFlowFromId(device_id, flow_id))


        #Get Service params from flows
        dictServiceParams = Flow.getFlowsParams(listOfServiceFlows, port_id)

        #Get Meters ids from flows
        serviceMeters = Meter.getMetersIds(dictServiceParams)

        #Get Meters structs
        for meter_id in serviceMeters:
            if self.getMeterFromId(device_id, meter_id) is None:
                return
            listOfServiceMeters.append(self.getMeterFromId(device_id, meter_id))

        if dictServiceParams["serviceType"] == "multicast":
            downstreamGuaranteed = (listOfServiceMeters[0]["bands"][0]["rate"]
                              if listOfServiceMeters[0]["bands"][0]["rate"] < listOfServiceMeters[0]["bands"][1]["rate"]
                              else listOfServiceMeters[0]["bands"][1]["rate"])
            downstreamExcess = ((listOfServiceMeters[0]["bands"][1]["rate"] - listOfServiceMeters[0]["bands"][0]["rate"])
                              if listOfServiceMeters[0]["bands"][1]["rate"] > listOfServiceMeters[0]["bands"][0]["rate"]
                              else (listOfServiceMeters[0]["bands"][0]["rate"] - listOfServiceMeters[0]["bands"][1]["rate"]))
    

            #Print service configuration
            print("\n\tService priority:", dictServiceParams["priority"])
            if dictServiceParams.get("Stag") is not None:
                print("\tStag Vlan:", dictServiceParams["Stag"])
            print("\tCtag Vlan:", dictServiceParams["Ctag"])
            print("\tDownstream guaranteed bandwith (Kbps):", downstreamGuaranteed)
            print("\tDownstream excess bandwith (Kbps):", downstreamExcess)

        else:

            upstreamGuaranteed = (listOfServiceMeters[0]["bands"][0]["rate"]
                                      if listOfServiceMeters[0]["bands"][0]["rate"] < listOfServiceMeters[0]["bands"][1]["rate"]
                                      else listOfServiceMeters[0]["bands"][1]["rate"])
            upstreamExcess = ((listOfServiceMeters[0]["bands"][1]["rate"] - listOfServiceMeters[0]["bands"][0]["rate"])
                                  if listOfServiceMeters[0]["bands"][1]["rate"] > listOfServiceMeters[0]["bands"][0]["rate"]
                                  else (listOfServiceMeters[0]["bands"][0]["rate"] - listOfServiceMeters[0]["bands"][1]["rate"]))
            downstreamGuaranteed = (listOfServiceMeters[1]["bands"][0]["rate"]
                                        if listOfServiceMeters[1]["bands"][0]["rate"] < listOfServiceMeters[1]["bands"][1]["rate"]
                                        else listOfServiceMeters[1]["bands"][1]["rate"])
            downstreamExcess = ((listOfServiceMeters[1]["bands"][1]["rate"] - listOfServiceMeters[1]["bands"][0]["rate"])
                                    if listOfServiceMeters[1]["bands"][1]["rate"] > listOfServiceMeters[1]["bands"][0]["rate"]
                                    else (listOfServiceMeters[1]["bands"][0]["rate"] - listOfServiceMeters[1]["bands"][1]["rate"]))

            #Print service configuration
            print("\n\tService priority:", dictServiceParams["priority"])
            if dictServiceParams.get("Stag") is not None:
                print("\tStag Vlan:", dictServiceParams["Stag"])
            print("\tCtag Vlan:", dictServiceParams["Ctag"])
            print("\tUpstream guaranteed bandwith (Kbps):", upstreamGuaranteed)
            print("\tUpstream excess bandwith (Kbps):", upstreamExcess)
            print("\tDownstream guaranteed bandwith (Kbps):", downstreamGuaranteed)
            print("\tDownstream excess bandwith (Kbps):", downstreamExcess)

        #Delete Flows
        if action == "delete":
            self.deletePortService(device_id, port_id, serviceFlows, serviceMeters)

    def getFlowFromId(self, device_id, flow_id):
        """Get flow struct from flow id"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + device_id.replace(":", "%3A") + "/" + flow_id

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return None

        return resp.json()["flows"][0] if len(resp.json()["flows"]) != 0 else None

    def getMeterFromId(self, device_id, meter_id):
        """Get meter struct from meter id"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/meters/" + device_id.replace(":", "%3A") + "/" + meter_id

        try:
            resp = requests.get(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return None

        return resp.json()["meters"][0] if len(resp.json()["meters"]) != 0 else None

    def deletePortService(self, device_id, port_id, serviceFlows, serviceMeters):
        """Delete the service configure on the selected port"""

        while True:
            try:
                selection = input("\n\tAre you sure you want to delete the service? (yes/no): ")
                if selection == "":
                    raise NoInputError
                if selection != "yes" and selection != "no":
                    raise WrongInputError
            except NoInputError:
                print("\n\tA value is required!!")
                input("\tPlease try again...")
                continue
            except WrongInputError:
                print("\n\tThe input value must be 'yes' or 'no'!!")
                input("\tPlease try again...")
                continue

            break

        if selection == "no":
            return

        if selection == "yes":
            for flow_id in serviceFlows:
                if not self.deleteFlow(device_id, port_id, flow_id):
                    return
            for meter_id in serviceMeters:
                if not self.deleteMeter(device_id, meter_id):
                    return
            print("\nThe service has been removed!!")

    def deleteFlow(self, device_id, port_id, flow_id):
        """Delete flow associated with a service"""

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/flows/" + device_id.replace(":", "%3A") + "/" + flow_id

        try:
            resp = requests.delete(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return False

        self.listFlows.delete(device_id, port_id)

        return True

    def deleteMeter(self, device_id, meter_id):
        """Delete meter associated with a service"""

        #Check if the meter is attached to other flows
        if self.getDeviceFlows(device_id) is None:
            return True
        deviceFlows = self.getDeviceFlows(device_id)

        for flow in deviceFlows:
            if flow["state"] == "PENDING_REMOVE":
                continue
            for instruction in flow["treatment"]["instructions"]:
                if instruction["type"] == "METER":
                    if instruction["meterId"] == meter_id:
                        return True

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        url = "http://" + self.ipONOS + ":" + str(self.portONOS) + "/onos/v1/meters/" + device_id.replace(":", "%3A") + "/" + meter_id

        try:
            resp = requests.delete(url, auth=HTTPBasicAuth('onos', 'rocks'), headers=headers)
        except requests.exceptions.HTTPError as err:
            print ("\nHttp Error:", err)
            return False

        self.getDeviceMeters(device_id)

        return True

    def getPortStatistics(self, device_id, port_id):
        """Get the service statistics of the selected port"""

        listOfServiceFlows = []

        #Get Flows ids
        serviceFlows = self.listFlows.getServiceConfiguration(device_id, port_id)
        if serviceFlows is None:
            print("\nThe selected ONU port does not have any service attached!!")
            return

        #Get Flows structs
        for flow_id in serviceFlows:
            if self.getFlowFromId(device_id, flow_id) is None:
                return
            listOfServiceFlows.append(self.getFlowFromId(device_id, flow_id))

        #Get Service statistics from flows
        dictServiceStatistics = Flow.getFlowsStatistics(listOfServiceFlows, port_id)

        #Print service statistics
        print("\n\tUpstream transmitted packets:", dictServiceStatistics["upstreamPackets"])
        print("\tUpstream transmitted bytes:", dictServiceStatistics["upstreamBytes"])
        print("\tDownstream transmitted packets:", dictServiceStatistics["downstreamPackets"])
        print("\tDownstream transmitted bytes:", dictServiceStatistics["downstreamBytes"])
