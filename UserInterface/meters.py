"""
    Copyright 2023, University of Valladolid.
    
    Contributors: Carlos Manuel Sangrador, David de Pintos, Noemí Merayo,
                  Alfredo Gonzalez, Miguel Campano.
    
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
