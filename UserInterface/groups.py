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