from requests.structures import CaseInsensitiveDict

class MeterStruct:

    def __init__(self):
        self.meter = {
                "deviceId": "of:0000000000000001",
                "unit": "KB_PER_SEC",
                "burst": True,
                "bands": [
                    {
                        "type": "DROP",
                        "rate": "0",
                        "burstSize": "2004",
                        "prec": "0"
                    },
                    {
                        "type": "DROP",
                        "rate": "0",
                        "burstSize": "2004",
                        "prec": "0"
                    }
                ]
            }

class Meter(MeterStruct):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"

    def __init__(self, flowType):
        self.flowType = flowType
        super().__init__()

    def configMeter(self, dictConfig):
        self.meter["deviceId"] = dictConfig["deviceId"]
        self.meter["bands"][0]["rate"] = dictConfig[self.flowType + "CirBandwith"]
        self.meter["bands"][1]["rate"] = str(int(dictConfig[self.flowType + "CirBandwith"]) + int(dictConfig[self.flowType + "PirBandwith"]))

    @staticmethod
    def getMetersIds(dictServiceParams):
        if dictServiceParams["serviceType"] == "multicast":
            return [dictServiceParams["downstreamMeterId"]]
        else:
            return [dictServiceParams["upstreamMeterId"], dictServiceParams["downstreamMeterId"]]
