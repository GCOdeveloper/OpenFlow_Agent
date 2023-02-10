from requests.structures import CaseInsensitiveDict

class FlowStruct:

    def __init__(self, flowType):
        if flowType == "upstream":
            self.singleTag = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 0,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_ID",
                                "vlanId": 833
                            },
                            {
                                "type": "METER",
                                "meterId": 1
                            },
                            {
                                "type": "OUTPUT",
                                "port": "20"
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "1"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "0"
                            }
                        ]
                    }
                }
            self.doubleTagTable0 = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 0,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_ID",
                                "vlanId": 833
                            },
                            {
                                "type": "METER",
                                "meterId": 1
                            },
                            {
                                "type": "TABLE",
                                "tableId": 1
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "1"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "0"
                            }
                        ]
                    }
                }

            self.doubleTagTable1 = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 1,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_ID",
                                "vlanId": 900
                            },
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_PUSH",
                                "ethernetType": "0x8100"
                            },
                            {
                                "type": "METER",
                                "meterId": 1
                            },
                            {
                                "type": "OUTPUT",
                                "port": "20"
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "1"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "833"
                            }
                        ]
                    }
                }
        if flowType == "downstream":
            self.singleTag = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 0,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_ID",
                                "vlanId": 0
                            },
                            {
                                "type": "METER",
                                "meterId": 1
                            },
                            {
                                "type": "OUTPUT",
                                "port": "1"
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "20"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "833"
                            }
                        ]
                    }
                }
            self.doubleTagTable0 = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 0,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_POP"
                            },
                            {
                                "type": "TABLE",
                                "tableId": 1
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "20"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "900"
                            }
                        ]
                    }
                }

            self.doubleTagTable1 = {
                    "priority": 40000,
                    "timeout": 0,
                    "isPermanent": True,
                    "deviceId": "of:0000000000000001",
                    "tableId" : 1,
                    "treatment": {
                        "instructions": [
                            {
                                "type": "L2MODIFICATION",
                                "subtype": "VLAN_ID",
                                "vlanId": 0
                            },
                            {
                                "type": "METER",
                                "meterId": 1
                            },
                            {
                                "type": "OUTPUT",
                                "port": "1"
                            }
                        ]
                    },
                    "selector": {
                        "criteria": [
                            {
                                "type": "IN_PORT",
                                "port": "20"
                            },
                            {
                                "type": "VLAN_VID",
                                "vlanId": "833"
                            }
                        ]
                    }
                }

class Flow(FlowStruct):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    appId = "org.onosproject.fwd"

    def __init__(self, flowType):
        self.flowType = flowType
        super().__init__(flowType)

    def configFlow(self, dictConfig):
        if self.flowType == "upstream":
            return self.upstreamFlow(dictConfig)
        elif self.flowType == "downstream":
            return self.downstreamFlow(dictConfig)

    def upstreamFlow(self, dictConfig):
        if int(dictConfig["Stag"]) == 4096:
            self.singleTag["priority"] = int(dictConfig["priority"])
            self.singleTag["deviceId"] = dictConfig["deviceId"]
            self.singleTag["treatment"]["instructions"][0]["vlanId"] = int(dictConfig["Ctag"])
            self.singleTag["treatment"]["instructions"][1]["meterId"] = int(dictConfig[self.flowType + "MeterId"])
            self.singleTag["selector"]["criteria"][0]["port"] = dictConfig["ONUport"]
            return "singleTag"
        else:
            self.doubleTagTable0["priority"] = int(dictConfig["priority"])
            self.doubleTagTable0["deviceId"] = dictConfig["deviceId"]
            self.doubleTagTable0["treatment"]["instructions"][0]["vlanId"] = int(dictConfig["Ctag"])
            self.doubleTagTable0["treatment"]["instructions"][1]["meterId"] = int(dictConfig[self.flowType + "MeterId"])
            self.doubleTagTable0["selector"]["criteria"][0]["port"] = dictConfig["ONUport"]

            self.doubleTagTable1["priority"] = int(dictConfig["priority"])
            self.doubleTagTable1["deviceId"] = dictConfig["deviceId"]
            self.doubleTagTable1["treatment"]["instructions"][0]["vlanId"] = int(dictConfig["Stag"])
            self.doubleTagTable1["treatment"]["instructions"][2]["meterId"] = int(dictConfig[self.flowType + "MeterId"])
            self.doubleTagTable1["selector"]["criteria"][0]["port"] = dictConfig["ONUport"]
            self.doubleTagTable1["selector"]["criteria"][1]["vlanId"] = dictConfig["Ctag"]
            return "doubleTag"

    def downstreamFlow(self, dictConfig):
        if int(dictConfig["Stag"]) == 4096:
            self.singleTag["priority"] = int(dictConfig["priority"])
            self.singleTag["deviceId"] = dictConfig["deviceId"]
            self.singleTag["treatment"]["instructions"][1]["meterId"] = int(dictConfig[self.flowType + "MeterId"])
            self.singleTag["treatment"]["instructions"][2]["port"] = dictConfig["ONUport"]
            self.singleTag["selector"]["criteria"][1]["vlanId"] = dictConfig["Ctag"]
            return "singleTag"
        else:
            self.doubleTagTable0["priority"] = int(dictConfig["priority"])
            self.doubleTagTable0["deviceId"] = dictConfig["deviceId"]
            self.doubleTagTable0["selector"]["criteria"][1]["vlanId"] = dictConfig["Stag"]

            self.doubleTagTable1["priority"] = int(dictConfig["priority"])
            self.doubleTagTable1["deviceId"] = dictConfig["deviceId"]
            self.doubleTagTable1["treatment"]["instructions"][1]["meterId"] = int(dictConfig[self.flowType + "MeterId"])
            self.doubleTagTable1["treatment"]["instructions"][2]["port"] = dictConfig["ONUport"]
            self.doubleTagTable1["selector"]["criteria"][1]["vlanId"] = dictConfig["Ctag"]
            return "doubleTag"

    @staticmethod
    def getFlowsParams(listOfServiceFlows, port_id):
        dictServiceParams = {}
        upstreamFlow = False

        if len(listOfServiceFlows) == 2: #Servicio single tag
            for flow in listOfServiceFlows:
                upstreamFlow = False
                for criteria in flow["selector"]["criteria"]:
                    if criteria["type"] == "IN_PORT":
                        if criteria["port"] == int(port_id):
                            upstreamFlow = True
                if upstreamFlow: #Flow de upstream
                    dictServiceParams["priority"] = flow["priority"]
                    for instruction in flow["treatment"]["instructions"]:
                        if instruction["type"] == "L2MODIFICATION" and instruction["subtype"] == "VLAN_ID":
                            dictServiceParams["Ctag"] = instruction["vlanId"]
                        if instruction["type"] == "METER":
                            dictServiceParams["upstreamMeterId"] = instruction["meterId"]
                elif not upstreamFlow: #Flow de downstream
                    for instruction in flow["treatment"]["instructions"]:
                        if instruction["type"] == "METER":
                            dictServiceParams["downstreamMeterId"] = instruction["meterId"]
        elif len(listOfServiceFlows) == 4: #Servicio double tag
            for flow in listOfServiceFlows:
                upstreamFlow = False
                if flow["tableId"] != 1:
                    continue
                else: #Flow de la tabla 1
                    for criteria in flow["selector"]["criteria"]:
                        if criteria["type"] == "IN_PORT":
                            if criteria["port"] == int(port_id):
                                upstreamFlow = True
                    if upstreamFlow: #Flow de upstream
                        dictServiceParams["priority"] = flow["priority"]
                        for instruction in flow["treatment"]["instructions"]:
                            if instruction["type"] == "L2MODIFICATION" and instruction["subtype"] == "VLAN_ID":
                                dictServiceParams["Stag"] = instruction["vlanId"]
                            if instruction["type"] == "METER":
                                dictServiceParams["upstreamMeterId"] = instruction["meterId"]
                        for criteria in flow["selector"]["criteria"]:
                            if criteria["type"] == "VLAN_VID":
                                dictServiceParams["Ctag"] = criteria["vlanId"]
                    elif not upstreamFlow: #Flow de downstream
                        for instruction in flow["treatment"]["instructions"]:
                            if instruction["type"] == "METER":
                                dictServiceParams["downstreamMeterId"] = instruction["meterId"]

        return dictServiceParams

    @staticmethod
    def getFlowsStatistics(listOfServiceFlows, port_id):
        dictServiceStatistics = {}
        upstreamFlow = False

        dictAuxiliar = {}

        if len(listOfServiceFlows) == 2: #Servicio single tag
            for flow in listOfServiceFlows:
                upstreamFlow = False
                for criteria in flow["selector"]["criteria"]:
                    if criteria["type"] == "IN_PORT":
                        if criteria["port"] == int(port_id):
                            upstreamFlow = True
                if upstreamFlow: #Flow de upstream
                    dictServiceStatistics["upstreamPackets"] = flow["packets"]
                    dictServiceStatistics["upstreamBytes"] = flow["bytes"]
                elif not upstreamFlow: #Flow de downstream
                    dictServiceStatistics["downstreamPackets"] = flow["packets"]
                    dictServiceStatistics["downstreamBytes"] = flow["bytes"]
        elif len(listOfServiceFlows) == 4: #Servicio double tag
            for flow in listOfServiceFlows:
                upstreamFlow = False
                for criteria in flow["selector"]["criteria"]:
                    if criteria["type"] == "IN_PORT":
                        if criteria["port"] == int(port_id):
                            upstreamFlow = True
                if upstreamFlow: #Flow de upstream
                    if flow["tableId"] == 0:
                        dictAuxiliar["upstreamPacketsTable0"] = flow["packets"]
                        dictAuxiliar["upstreamBytesTable0"] = flow["bytes"]
                    elif flow["tableId"] == 1:
                        dictAuxiliar["upstreamPacketsTable1"] = flow["packets"]
                        dictAuxiliar["upstreamBytesTable1"] = flow["bytes"]
                elif not upstreamFlow: #Flow de downstream
                    if flow["tableId"] == 0:
                        dictAuxiliar["downstreamPacketsTable0"] = flow["packets"]
                        dictAuxiliar["downstreamBytesTable0"] = flow["bytes"]
                    elif flow["tableId"] == 1:
                        dictAuxiliar["downstreamPacketsTable1"] = flow["packets"]
                        dictAuxiliar["downstreamBytesTable1"] = flow["bytes"]

            dictServiceStatistics["upstreamPackets"] = (dictAuxiliar["upstreamPacketsTable0"]
                                  if dictAuxiliar["upstreamPacketsTable0"] < dictAuxiliar["upstreamPacketsTable1"]
                                  else dictAuxiliar["upstreamPacketsTable1"])
            dictServiceStatistics["upstreamBytes"] = (dictAuxiliar["upstreamBytesTable0"]
                                  if dictAuxiliar["upstreamBytesTable0"] < dictAuxiliar["upstreamBytesTable1"]
                                  else dictAuxiliar["upstreamBytesTable1"])
            dictServiceStatistics["downstreamPackets"] = (dictAuxiliar["downstreamPacketsTable0"]
                                  if dictAuxiliar["downstreamPacketsTable0"] < dictAuxiliar["downstreamPacketsTable1"]
                                  else dictAuxiliar["downstreamPacketsTable1"])
            dictServiceStatistics["downstreamBytes"] = (dictAuxiliar["downstreamBytesTable0"]
                                  if dictAuxiliar["downstreamBytesTable0"] < dictAuxiliar["downstreamBytesTable1"]
                                  else dictAuxiliar["downstreamBytesTable1"])

        return dictServiceStatistics
