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

class GroupStruct:

    def __init__(self):
        self.group = {
                "type": "ALL",
                "appCookie": "0x1234abcd",
                "groupId": "1",
                "buckets": [
                {
                  "treatment": {
                    "instructions": [
                      {
                        "type": "OUTPUT",
                        "port": "1879245060"
                      }
                    ]
                  }
                }
            ]
        }

class Group(GroupStruct):
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"

    def __init__(self):
        super().__init__()

    def configGroup(self, dictConfig, id_group):
        self.group["buckets"][0]["treatment"]["instructions"][0]["port"] = dictConfig["ONUport"]
        self.group["groupId"] = str(id_group)
        self.group["appCookie"] = "0x" + str(id_group)
       
    @staticmethod
    def getGroupsIds(dictServiceParams):
        return [dictServiceParams["groupId"]]