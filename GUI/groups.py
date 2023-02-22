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