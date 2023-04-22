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
