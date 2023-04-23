"""
    Copyright 2023, University of Valladolid.
    
    Contributors: David de Pintos, Carlos Manuel Sangrador, Noemí Merayo

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

import logging
import socket
import time
import math
from pyof.v0x04.symmetric.hello import *
from pyof.v0x04.symmetric.echo_reply import *
from pyof.v0x04.asynchronous.packet_in import *
from pyof.v0x04.asynchronous.error_msg import ErrorMsg
from pyof.v0x04.asynchronous.error_msg import *
from pyof.v0x04.asynchronous.port_status import *
from pyof.v0x04.controller2switch import features_reply
from pyof.foundation.base import *
from pyof.foundation.basic_types import *
from pyof.v0x04.common.header import Header, Type
from pyof.v0x04.common.flow_match import *
from pyof.v0x04.common.flow_instructions import *
from pyof.v0x04.common.action import *
from pyof.v0x04.common.port import *
from pyof.v0x04.controller2switch.get_config_reply import *
from pyof.v0x04.controller2switch.features_reply import *
from pyof.v0x04.controller2switch.barrier_reply import *
from pyof.v0x04.controller2switch.role_request import *
from pyof.v0x04.controller2switch.role_reply import *
from pyof.v0x04.controller2switch.common import *
from pyof.v0x04.controller2switch.multipart_reply import *
from pyof.v0x04.controller2switch.multipart_request import *
from pyof.v0x04.controller2switch.flow_mod import *
from pyof.v0x04.controller2switch.meter_mod import *
from pyof.v0x04.controller2switch.group_mod import *

import src.agentQueue
from src.agentQueue import oltQueue

class ListOfFlows(dict):
    """List of Flow elements"""

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def append(self, item):
        table_id = item.get("tableId")
        if table_id not in self.keys():
            self.update({table_id : []})
        listTable = self.get(table_id)
        listTable.append(item)
        self.update({table_id : listTable})

    def exist(self, itemCookie, itemTableId):
        if itemTableId in self.keys():
            for flow in self.get(itemTableId):
                if flow["flowId"] == itemCookie:
                    return True
        return False

    def delete(self, itemCookie, itemTableId):
        if itemTableId in self.keys():
            for flow in self.get(itemTableId):
                if flow["flowId"] == itemCookie:
                    self.get(itemTableId).remove(flow) # Deleting the Flow
                    return True
        return False

    def getFlow(self, itemFlowId):
        for table_id in self.keys():
            for flow in self.get(table_id):
                if flow["flowId"] == itemFlowId:
                    return flow
        return None

    def getFlowsTable(self, itemTableId):
        return self.get(itemTableId)

    def attachedMeter(self, itemMeterId):
        for table_id in self.keys():
            for flow in self.get(table_id):
                if "meterId" in flow["instructions"] and flow["instructions"]["meterId"] == itemMeterId:
                    return True
        return False

    def attachedGroup(self, itemGroupId):
        for table_id in self.keys():
            for flow in self.get(table_id):
                if "groupId" in flow["instructions"] and flow["instructions"]["groupId"] == itemGroupId:
                    return True
        return False

    def get_port_matched_flows(self, port_no, direction, groupIDs = []):
        flows = []
        start_table_id = max(self.keys()) if direction == "downstream" else 0
        # Ceck groups

        for table_id in range(start_table_id, -1, -1):
            bw_table_flows = self.getFlowsTable(table_id)
            if bw_table_flows is None or len(bw_table_flows) == 0:
                continue

            for flow in sorted(bw_table_flows, key = lambda x: (x['priority']), reverse = True):
                if direction == "upstream" and flow["match"]["inPort"] == port_no:
                    flows.append(flow)
                    continue

                if direction == "downstream" and "groupId" in flow["instructions"]:
                    if flow["instructions"]["groupId"] in groupIDs:
                        flows.append(flow)
                        continue

                if direction == "downstream" and "outPort" in flow["instructions"]:
                    if flow["instructions"]["outPort"] == port_no:
                        flows.append(flow)
                        continue

        return flows

    def get_matched_flow (self, flowParams, table_id):
        logging.info("Matching flow from table %d", table_id)
        logging.info("Received flow table %d", flowParams["tableId"])
        flows = []
        bw_table_flows = self.getFlowsTable(table_id)
        if bw_table_flows is None or len(bw_table_flows) == 0:
            return []

        for flow in sorted(bw_table_flows, key = lambda x: (x['priority']), reverse = True):
            flowMatched = False

            if flow["match"]["inPort"] != flowParams["match"]["inPort"]:
                continue

            if flow["flowType"] != flowParams["flowType"]:
                continue

            # VOIP CHECKS
            if ("serviceType" in flowParams and flowParams["serviceType"] == "voip"
                    and "serviceType" in flow and flow["serviceType"] == "voip"):
                if "udpSrc" in flowParams["match"] and "udpSrc" in flow["match"]:
                    if flowParams["match"]["udpSrc"] != flow["match"]["udpSrc"]:
                        continue
                if "udpDst" in flowParams["match"] and "udpDst" in flow["match"]:
                    if flowParams["match"]["udpDst"] != flow["match"]["udpDst"]:
                        continue
                if "ipv4Src" in flowParams["match"] and "ipv4Src" in flow["match"]:
                    if flowParams["match"]["ipv4Src"] != flow["match"]["ipv4Src"]:
                        continue
                if "ipv4Dst" in flowParams["match"] and "ipv4Dst" in flow["match"]:
                    if flowParams["match"]["ipv4Dst"] != flow["match"]["ipv4Dst"]:
                        continue

            if table_id < flowParams["tableId"]:
                if "gotoTable" not in flow["instructions"]:
                    continue
                if flow["instructions"]["gotoTable"] != flowParams["tableId"]:
                    continue

                for instruction in flow["instructions"].items():
                    if instruction[0] == "setVlan" and instruction[1] == flowParams["match"]["vlanId"]:
                        flowMatched = True
                    elif instruction[0] == "pushVlan" and instruction[1] == flowParams["match"]["vlanId"]:
                        flowMatched = True
                    elif instruction[0] == "popVlan":
                        flowMatched = False if flowMatched else True # Changing the flowMatched value
                    elif instruction[0] == "outPort" or instruction[0] == "groupId":
                        continue

            elif table_id > flowParams["tableId"]:
                if flowParams["instructions"]["gotoTable"] != table_id:
                    return []

                for instruction in flowParams["instructions"].items():
                    if instruction[0] == "setVlan" and instruction[1] == flow["match"]["vlanId"]:
                        flowMatched = True
                    elif instruction[0] == "pushVlan" and instruction[1] == flow["match"]["vlanId"]:
                        flowMatched = True

                if (("popVlan" in flowParams["instructions"].keys())
                        and ("setVlan" not in flowParams["instructions"].keys())
                        and ("pushVlan" not in flowParams["instructions"].keys())
                        and ("outPort" not in flowParams["instructions"].keys())
                        and ("groupId" not in flowParams["instructions"].keys())):
                    flows.append(flow)
                    continue
            else:
                return []

            if flowMatched:
                logging.info("FLOW MATCHED:")
                logging.info("****INITIAL FLOW:")
                print(flowParams)

                logging.info("****MATCHED FLOW:")
                print(flow)
                flows.append(flow)
                break

        return flows

class ListOfFlowMod(dict):
    """List of FlowMod elements"""

    def __init__(self, items=None):
        super().__init__()
        if isinstance(items, list):
            for item in items:
                self.append(item)

    def append(self, item):
        self.update({item.cookie.value : item})

    def get_FlowData(self, flow_id):
        flowMod = self.get(flow_id)
        if flowMod is None:
            return b''

        try:
            FlowData = flowMod.pack()
        except PackException as err:
            logging.error(err)
            return b''
        else:
            return FlowData

class ListOfGroups(FixedTypeList):
    """List of GroupMod elements.

    Represented by instances of GroupMod.
    """

    def __init__(self, items=None):
        """Create a ListOfGroups with the optional parameters below.

        Args:
        items (GroupMod): Instance or a list of instances.
        """
        super().__init__(pyof_class=GroupDescStats, items=items)

    def delete(self, itemGroupId):
        for groupObj in self.copy():
            if groupObj.group_id.value == itemGroupId:
                self.remove(groupObj)

    def get_group (self, groupId):
        for group in self.copy():
            if group.group_id.value == groupId:
                return group
        return None

    def exists (self, groupId):
        if self.get_group(groupId) is None:
            return False
        else:
            return True

    def get_group_ports(self, groupId):
        ports = list()
        group = self.get_group(groupId)

        for bucket in group.buckets:
            for action in bucket.actions:
                if action.action_type == ActionType.OFPAT_OUTPUT:
                    ports.append(action.port.value)
        return ports

    def get_groupsByPort(self, port_id):
        groups = list()

        for group in self.copy():
            for bucket in group.buckets:
                for action in bucket.actions:
                    if (action.action_type == ActionType.OFPAT_OUTPUT
                            and action.port.value == port_id):
                        groups.append(group.group_id.value)

        return groups


class ListOfMeters(FixedTypeList):
    """List of MeterMod elements.

    Represented by instances of MeterMod.
    """

    def __init__(self, items=None):
        """Create a ListOfMeters with the optional parameters below.

        Args:
        items (MeterMod): Instance or a list of instances.
        """
        super().__init__(pyof_class=MeterMod, items=items)

    def delete(self, itemMeterId):
        for meterObj in self.copy():
            if meterObj.meter_id.value == itemMeterId:
                self.remove(meterObj)

    def get_meter (self, meterId):
        for meter in self.copy():
            if meter.meter_id == meterId:
                return meter
        return None

    def get_meterId_bandwidth(self, meterId):
        bandwidth = {}

        meter = self.get_meter(meterId)
        if meter is None:
            return None

        for band in meter.bands:
            if band.band_type != MeterBandType.OFPMBT_DROP:
                continue
            if "cir" in bandwidth.keys():
                if band.rate.value >= bandwidth["cir"]:
                    if "pir" not in bandwidth.keys() or band.rate.value > bandwidth["pir"]:
                        bandwidth["pir"] = band.rate.value
                else:
                    if "pir" not in bandwidth.keys() or bandwidth["cir"] > bandwidth["pir"]:
                        bandwidth["pir"] = bandwidth["cir"]
                    bandwidth["cir"] = band.rate.value
            else:
                bandwidth["cir"] = band.rate.value

            if "pbs" not in bandwidth.keys() or bandwidth["pbs"] < band.burst_size.value:
                bandwidth["pbs"] = band.burst_size.value

        if "pir" not in bandwidth.keys():
            bandwidth["pir"] = bandwidth["cir"]

        return bandwidth


class ListOfFlowStats(FixedTypeList):
    """List of FlowStats.

    Represented by instances of FlowStats.
    """

    def __init__(self, items=None):
        """Create a ListOfFlowStats with the optional parameters below.

        Args:
        items (FlowStats): Instance or a list of instances.
        """
        super().__init__(pyof_class=FlowStats, items=items)
        self.flow_start_time = dict()
        if isinstance(items, list):
            for item in items:
                self.flow_start_time.update({item.cookie.value: int(time.time())})

    def append(self, item):
        super().append(item)

        if isinstance(item, list):
            for it in item:
                self.flow_start_time.update({it.cookie.value: int(time.time())})
        elif issubclass(item.__class__, self._pyof_class):
            self.flow_start_time.update({item.cookie.value: int(time.time())})

    def delete(self, itemCookie):
        for flowObj in self.copy():
            if flowObj.cookie.value == itemCookie:
                self.remove(flowObj) #Eliminamos el flow de la lista de estadisticas de flows
                self.flow_start_time.pop(itemCookie)
                break

    def get_flowStats(self, itemCookie):
        for flowObj in self.copy():
            if flowObj.cookie.value == itemCookie:
                return flowObj
        return None

    def update_statistics(self, itemCookie, packet_count, byte_count, timestamp):
        life = timestamp - self.flow_start_time[itemCookie]

        flowObj = self.get_flowStats(itemCookie)
        if flowObj is None:
            return

        flowObj.packet_count += packet_count
        flowObj.byte_count += byte_count
        flowObj.duration_sec = life

    def get_associated_meter (self, itemCookie):
        flowObj = self.get_flowStats(itemCookie)
        if flowObj is None:
            return None

        for instruction in flowObj.instructions:
            if instruction.instruction_type == InstructionType.OFPIT_METER:
                return instruction.meter_id.value
        return None

class ListOfGroupStats(FixedTypeList):
    """List of GroupStats.

    Represented by instances of GroupStats.
    """

    def __init__(self, items=None):
        """Create a ListOfGroupStats with the optional parameters below.

        Args:
        items (GroupStats): Instance or a list of instances.
        """
        super().__init__(pyof_class=GroupStats, items=items)

        self.group_start_time = dict()
        if isinstance(items, list):
            for item in items:
                self.group_start_time.update({item.group_id.value: int(time.time())})

    def append(self, item):
        super().append(item)

        if isinstance(item, list):
            for it in item:
                self.group_start_time.update({it.group_id.value: int(time.time())})
        elif issubclass(item.__class__, self._pyof_class):
            self.group_start_time.update({item.group_id.value: int(time.time())})


    def delete(self, itemGroupId):
        for groupObj in self.copy():
            if groupObj.group_id.value == itemGroupId:
                self.remove(groupObj) # Deleting the group from the statistics list
                self.group_start_time.pop(itemGroupId)
                break

    def get_groupStats(self, itemGroupId):
        for GroupObj in self.copy():
            if GroupObj.group_id.value == itemGroupId:
                return GroupObj
        return None

    def update_statistics(self, itemGroupId, packet_count, byte_count, timestamp):
        life = timestamp - self.group_start_time[itemGroupId]

        GroupObj = self.get_groupStats(itemGroupId)
        if GroupObj is None:
            return

        GroupObj.packet_count += packet_count
        GroupObj.byte_count += byte_count
        GroupObj.duration_sec = life

        for band in GroupObj.bucket_stats:
            band.packet_count += packet_count
            band.byte_count += byte_count

class ListOfMeterStats(FixedTypeList):
    """List of MeterStats.

    Represented by instances of MeterStats.
    """

    def __init__(self, items=None):
        """Create a ListOfMeterStats with the optional parameters below.

        Args:
        items (MeterStats): Instance or a list of instances.
        """
        super().__init__(pyof_class=MeterStats, items=items)

        self.meter_start_time = dict()
        if isinstance(items, list):
            for item in items:
                self.meter_start_time.update({item.meter_id.value: int(time.time())})

    def append(self, item):
        super().append(item)

        if isinstance(item, list):
            for it in item:
                self.meter_start_time.update({it.meter_id.value: int(time.time())})
        elif issubclass(item.__class__, self._pyof_class):
            self.meter_start_time.update({item.meter_id.value: int(time.time())})


    def delete(self, itemMeterId):
        for meterObj in self.copy():
            if meterObj.meter_id.value == itemMeterId:
                self.remove(meterObj) #Eliminamos el meter de la lista de estadisticas de meters
                self.meter_start_time.pop(itemMeterId)
                break

    def get_meterStats(self, itemMeterId):
        for MeterObj in self.copy():
            if MeterObj.meter_id.value == itemMeterId:
                return MeterObj
        return None

    def update_statistics(self, itemMeterId, packet_count, byte_count, timestamp):
        life = timestamp - self.meter_start_time[itemMeterId]

        MeterObj = self.get_meterStats(itemMeterId)
        if MeterObj is None:
            return

        MeterObj.packet_in_count += packet_count
        MeterObj.byte_in_count += byte_count
        MeterObj.duration_sec = life

        packet_band_count = math.floor(packet_count / len (MeterObj.band_stats))
        byte_band_count = math.floor(byte_count / len (MeterObj.band_stats))

        for band in MeterObj.band_stats:
            band.packet_band_count += packet_band_count
            band.byte_band_count += byte_band_count

class ONOSAdaptor:
    """Establishes and manages the communication with the OpenFlow Controller"""

    def __init__(self, ipONOS = "0.0.0.0", portONOS = 6633):
        self.ipONOS = ipONOS
        self.portONOS = portONOS

        #FlowStats
        self.listF = ListOfFlows()
        self.listFS = ListOfFlowStats()

        self.cookie_to_flowMod = ListOfFlowMod()

        #MeterConfig and MeterStats
        self.listM = ListOfMeters()
        self.listMS = ListOfMeterStats()

        #PortStats
        self.listPorts = ListOfPorts()

        # GroupStats
        self.listGr = ListOfGroups()
        self.listGrS = ListOfGroupStats()

        #Meter features configuration
        self.bandTypes = 0 | 1 << MeterBandType.OFPMBT_DROP.value | 0 << MeterBandType.OFPMBT_DSCP_REMARK.value
        self.meterFlags = MeterFlags.OFPMF_KBPS

    def connect(self):
        self.socket = socket.socket()
        self.socket.connect((self.ipONOS, self.portONOS))

    def OFPT_HELLO_msg(self):
        element = HelloElemHeader(element_type=HelloElemType.OFPHET_VERSIONBITMAP,
                                  length=8, content=bytes.fromhex('00000010'))
        le = ListOfHelloElements(items=[element])
        sendHello = Hello(elements=le)
        message = sendHello.pack()
        self.socket.send(message)  #Enviamos un mensaje OFPT_HELLO al controlador

    def recieve_packets(self, olt_datapath_id, olt_n_buffers, olt_n_tables, olt_auxiliary_id,
                        olt_capabilities, olt_hw_version, olt_fw_version, olt_serial_num):
        self.queue_id = olt_datapath_id
        self.switchTables = olt_n_tables

        #Variable de control para el OFPT_ROLE_REQUEST/REPLY
        storeRole = None

        # Installing NNI Port
        state = PortState.OFPPS_LIVE
        current = advertised = peer = PortFeatures.OFPPF_10GB_FD | PortFeatures.OFPPF_FIBER
        supported = (PortFeatures.OFPPF_10MB_HD | PortFeatures.OFPPF_10MB_FD | PortFeatures.OFPPF_100MB_HD
                    | PortFeatures.OFPPF_100MB_FD | PortFeatures.OFPPF_1GB_HD | PortFeatures.OFPPF_1GB_FD
                    | PortFeatures.OFPPF_10GB_FD | PortFeatures.OFPPF_FIBER)

        self.puertoNNI = Port(port_no=0x14, hw_addr=olt_datapath_id[6:], name="NNI",
                         config=0x00, state=state, curr=current, advertised=advertised, supported=supported, peer=peer,
                         curr_speed=100000, max_speed=100000)

        self.listPorts.append(self.puertoNNI)

        while True:  # Bucle exterior, gestiona los paquetes
            extraByte = 0  # Variable para el acceso relativo a los mensajes
            data = self.socket.recv(10240)  # Recibimos el paquete
            longReal = len(data)  # Longitud del paquete

            #Tamaño mínimo de un mensaje OF
            if longReal < 8: continue

            while True:  #Bucle interior, gestiona los mensajes de un paquete
                #Cabecera de los mensajes OpenFlow recibidos
                header = Header()
                header.unpack(data, extraByte)
                tipo = header.message_type

                if tipo == Type.OFPT_HELLO:
                    self.get_OFPT_HELLO_RESPONSE()

                if tipo == Type.OFPT_ECHO_REQUEST: #OFPT_ECHO_REPLY
                    self.send_OFPT_ECHO_REPLY(header)

                if tipo == Type.OFPT_FEATURES_REQUEST: #OFPT_FEATURES_REQUEST
                    self.send_OFPT_FEATURES_REPLY(header, olt_datapath_id, olt_n_buffers, olt_n_tables,
                                             olt_auxiliary_id, olt_capabilities)

                if tipo == Type.OFPT_GET_CONFIG_REQUEST: #OFPT_GET_CONFIG_REQUEST
                    self.send_OFPT_GET_CONFIG_REPLY(header)

                if tipo == Type.OFPT_FLOW_MOD: #OFPT_FLOW_MOD
                    self.get_OFPT_FLOW_MOD(extraByte, header, data)

                if tipo == Type.OFPT_MULTIPART_REQUEST: #OFPT_MULTIPART_REQUEST
                    self.send_OFPT_MULTIPART_REPLY(extraByte, header, data, olt_hw_version, olt_fw_version,
                                                   olt_serial_num)

                if tipo == Type.OFPT_BARRIER_REQUEST: #OFPT_BARRIER_REQUEST
                    self.send_OFPT_BARRIER_REPLY(header)

                if tipo == Type.OFPT_ROLE_REQUEST: #OFPT_ROLE_REQUEST
                    storeRole = self.send_OFPT_ROLE_REPLY(extraByte, header, data, storeRole)

                if tipo == Type.OFPT_METER_MOD: #OFPT_METER_MOD
                    self.get_OFPT_METER_MOD(extraByte, header, data)

                if tipo == Type.OFPT_GROUP_MOD: #OFPT_GROUP_MOD
                    self.get_OFPT_GROUP_MOD(extraByte, header, data)

                # Comprobamos si hay mas mensajes en el paquete
                if longReal > header.length: #Si hay mas mensajes, procesamos el siguiente mensaje
                    longReal -= header.length.value
                    extraByte += header.length.value
                elif longReal == header.length: #Si no hay mas mensajes, pasamos al siguiente paquete
                    break
                else:
                    logging.error("Error: Not enough bytes from packet to read new OF messages")
                    break

    def get_OFPT_HELLO_RESPONSE(self):
        logging.info("OFPT_HELLO_RESPONSE")

    def send_OFPT_ECHO_REPLY(self, header):
        sendEchoReply = EchoReply(xid=header.xid)
        message = sendEchoReply.pack()
        self.socket.send(message)
        logging.info("OFPT_ECHO_REPLY")

    def send_OFPT_FEATURES_REPLY(self, header, olt_datapath_id, olt_n_buffers, olt_n_tables,
                                 olt_auxiliary_id, olt_capabilities):
        sendFeaturesReply = FeaturesReply(xid=header.xid, datapath_id=olt_datapath_id,
                                          n_buffers=olt_n_buffers, n_tables=olt_n_tables,
                                          auxiliary_id=olt_auxiliary_id, capabilities=olt_capabilities,
                                          reserved=0)
        message = sendFeaturesReply.pack()
        self.socket.send(message)
        logging.info("OFPT_FEATURES_REPLY")

    def send_OFPT_GET_CONFIG_REPLY(self, header):
        sendGetConfigReply = GetConfigReply(xid=header.xid, flags=ConfigFlag.OFPC_FRAG_NORMAL,
                                            miss_send_len=ControllerMaxLen.OFPCML_NO_BUFFER)
        message = sendGetConfigReply.pack()
        self.socket.send(message)
        logging.info("OFPT_GET_CONFIG_REPLY")

    def get_OFPT_FLOW_MOD(self, extraByte, header, data):
        flowMod = FlowMod(xid=header.xid)
        flowMod.unpack(data[extraByte:extraByte+header.length.value], header.get_size())
        flowMod.header.length = header.length

        if flowMod.command == FlowModCommand.OFPFC_ADD: #Si el tipo es OFPFC_ADD
            flowStats = FlowStats(length=flowMod.header.length, table_id=flowMod.table_id,
                                  duration_sec=0, duration_nsec=0, priority=flowMod.priority,
                                  idle_timeout=0, hard_timeout=0, flags=flowMod.flags,
                                  cookie=flowMod.cookie, packet_count=0, byte_count=0,
                                  match=flowMod.match, instructions=flowMod.instructions)
            print("Creando flow ...")
            self.listFS.append(flowStats)
        elif (flowMod.command == FlowModCommand.OFPFC_DELETE or
              flowMod.command == FlowModCommand.OFPFC_DELETE_STRICT): #Si el tipo es OFPFC_DELETE o OFPFC_DELETE_STRICT
            print("Borrando flow ...")
            #self.listFS.delete(flowMod.cookie.value)
            if self.listF.exist(flowMod.cookie.value, flowMod.table_id.value):
                print("Flow borrado asociado a un servicio -> A la cola")
                #Enviamos el identificador del Flow a la cola
                self.flowToQueue(flowMod.cookie.value, flowMod.command)
                #self.listF.delete(flowMod.cookie.value, flowMod.table_id.value)
            else:
                self.listFS.delete(flowMod.cookie.value)

            logging.info("OFPT_FLOW_MOD")
            return

        print("Obteniendo los parametros del Flow")
        #Get Flow parameters
        flowConfig = self.getFlowParameters(flowMod)
        if flowConfig is None:
            return

        check = self.check_flows(flowConfig)
        if not check:
            logging.error("WRONG FLOW received")
            self.listFS.delete(flowConfig["flowId"])
            return

        #Añadimos el Flow a la lista
        self.listF.append(flowConfig)
        self.cookie_to_flowMod.append(flowMod)

        print("Flow creado asociado a un servicio -> A la cola")
        #Enviamos el identificador del Flow a la cola
        self.flowToQueue(flowMod.cookie.value, flowMod.command)

        logging.info("OFPT_FLOW_MOD")

    def send_OFPT_MULTIPART_REPLY(self, extraByte, header, data, olt_hw_version, olt_fw_version, olt_serial_num):
        multipartRequest = MultipartRequest(xid=header.xid)
        multipartRequest.unpack(data, extraByte+header.get_size())
        tipoM = multipartRequest.multipart_type

        if tipoM == MultipartType.OFPMP_DESC: #OFPMP_DESC
            pruebaDesc = Desc(mfr_desc="OpenFlow Agent", hw_desc=olt_hw_version, sw_desc=olt_fw_version,
                              serial_num=olt_serial_num, dp_desc="None")
            sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                flags=multipartRequest.flags, body=pruebaDesc)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_DESC")

        if tipoM == MultipartType.OFPMP_FLOW: #OFPMP_FLOW
            if len(self.listFS) != 0: #Enviamos los flows al controlador si existe alguno
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=self.listFS)
            else:
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=None)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_FLOW")

        if tipoM == MultipartType.OFPMP_TABLE: #OFPMP_TABLE
            sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                flags=multipartRequest.flags, body=None)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_TABLE")

        if tipoM == MultipartType.OFPMP_PORT_STATS: #OFPMP_PORT_STATS
            sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                flags=multipartRequest.flags, body=None)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_PORT_STATS")

        if tipoM == MultipartType.OFPMP_GROUP: #OFPMP_GROUP
            if len(self.listGrS) != 0: # If exists, sends the group Stats
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=self.listGrS)

                descLength = self.listGrS[0].get_size()

            else:
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=None)

            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_GROUP")

        if tipoM == MultipartType.OFPMP_GROUP_DESC: #OFPMP_GROUP_DESC
            if len(self.listGr) != 0: # If exists, sends the group Description
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=self.listGr)
                descLength = self.listGr.get_size()

            else:
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=None)

            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_GROUP_DESC")

        if tipoM == MultipartType.OFPMP_METER: #OFPMP_METER
            if len(self.listMS) != 0: #Enviamos los meters al controlador si existe alguno
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=self.listMS)
            else:
                sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                    flags=multipartRequest.flags, body=None)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_METER")

        if tipoM == MultipartType.OFPMP_METER_FEATURES: #OFPMP_METER_FEATURES
            meterFeatures = MeterFeatures(max_meter=4294967295, band_types=self.bandTypes,
                                          capabilities=self.meterFlags, max_bands=255, max_color=255)
            sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                flags=multipartRequest.flags, body=meterFeatures)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_METER_FEATURES")

        if tipoM == MultipartType.OFPMP_PORT_DESC: #OFPMP_PORT_DESC
            sendMultipartReply = MultipartReply(xid=multipartRequest.header.xid, multipart_type=tipoM,
                                                flags=multipartRequest.flags, body=self.listPorts)
            message = sendMultipartReply.pack()
            self.socket.send(message)
            logging.info("OFPMP_PORT_DESC")

    def send_OFPT_BARRIER_REPLY(self, header):
        sendBarrierReply = BarrierReply(xid=header.xid)
        message = sendBarrierReply.pack()
        self.socket.send(message)
        logging.info("OFPT_BARRIER_REPLY")

    def send_OFPT_ROLE_REPLY(self, extraByte, header, data, storeRole):
        roleRequest = RoleRequest(xid=header.xid)
        roleRequest.unpack(data, extraByte+header.get_size())
        role = roleRequest.role
        generationID = roleRequest.generation_id

        if role == ControllerRole.OFPCR_ROLE_NOCHANGE and storeRole == None:
            storeRole = ControllerRole.OFPCR_ROLE_EQUAL
            sendRoleReply = RoleReply(xid=roleRequest.header.xid, role=storeRole)
            message = sendRoleReply.pack()
            self.socket.send(message)
            logging.info("OFPT_ROLE_REPLY 1")
        elif role == ControllerRole.OFPCR_ROLE_NOCHANGE:
            sendRoleReply = RoleReply(xid=roleRequest.header.xid, role=storeRole, generation_id=generationID)
            message = sendRoleReply.pack()
            self.socket.send(message)
            logging.info("OFPT_ROLE_REPLY 2")
        else:
            storeRole = role
            sendRoleReply = RoleReply(xid=roleRequest.header.xid, role=role, generation_id=generationID)
            message = sendRoleReply.pack()
            self.socket.send(message)
            logging.info("OFPT_ROLE_REPLY 3")

        return storeRole

    def get_OFPT_METER_MOD(self, extraByte, header, data):
        meterMod = MeterMod(xid=header.xid)
        meterMod.unpack(data[extraByte:extraByte+header.length.value], header.get_size())

        if meterMod.command == MeterModCommand.OFPMC_ADD: #Si el tipo es OFPMC_ADD
            lBS = [] #Creamos una lista para guardar los "band stats"
            for i in range(len(meterMod.bands)): #Obtebemos el numero de "band stats"
                bandS = BandStats(packet_band_count=0, byte_band_count=0)
                lBS.append(bandS)
            listBS = ListOfBandStats(items=lBS)
            meterStats = MeterStats(meter_id=meterMod.meter_id, flow_count=0, packet_in_count=0,
                                    byte_in_count=0, duration_sec=0, duration_nsec=0, band_stats=listBS)
            self.listMS.append(meterStats) #Añadimos la estructura de estadisticas del meter a la lista

            #Añadimos el MeterMod a la lista
            self.listM.append(meterMod)
        elif meterMod.command == MeterModCommand.OFPMC_DELETE: #Si el tipo es OFPMC_DELETE
            logging.info("Meter deletion")
            if not self.listF.attachedMeter(meterMod.meter_id.value):
                self.listMS.delete(meterMod.meter_id.value)
                self.listM.delete(meterMod.meter_id.value)
            else:
                logging.info("MeterId %d cannot be delete because is attached at least to one Flow", meterMod.meter_id.value)

        logging.info("OFPT_METER_MOD")

    def get_OFPT_GROUP_MOD(self, extraByte, header, data):
        groupMod = GroupMod(xid=header.xid)
        groupMod.unpack(data[extraByte:extraByte+header.length.value], header.get_size())

        if groupMod.command == GroupModCommand.OFPGC_DELETE:
            logging.info("Group deletion")
            if not self.listF.attachedGroup(groupMod.group_id.value):
                self.listGrS.delete(groupMod.group_id.value)
                self.listGr.delete(groupMod.group_id.value)
            else:
                logging.info("GrouId %d cannot be delete because is attached at least to one Flow", groupMod.group_id.value)
            logging.info("OFPT_GROUP_MOD")
            return
        elif groupMod.command != GroupModCommand.OFPGC_ADD: # TODO adding modify group OFPGC_MODIFY
            return

        # Checking correct groupMod
        check = self.check_mcGroup(groupMod)
        if not check:
            logging.error("WRONG GROUP received")
            return

        lBC = [] # List for BucketCounters
        for i in range(len(groupMod.buckets)):
            buck = BucketCounter(packet_count=0, byte_count=0)
            lBC.append(buck)

        listBS = ListOfBucketCounter(items=lBC)
        groupStats = GroupStats(group_id=groupMod.group_id, ref_count=0,
                                packet_count=0, byte_count=0, duration_sec=0,
                                duration_nsec=0, bucket_stats=listBS)
        groupStats.length = groupStats.get_size()
        groupDesc = GroupDescStats(group_type = groupMod.group_type,
                                   group_id = groupMod.group_id, buckets = ListOfBuckets(items = groupMod.buckets))
        groupDesc.length = groupDesc.get_size() + groupMod.buckets.get_size()

        # Adding the GroupStats to the list
        self.listGrS.append(groupStats)
        # Adding the GroupMod to the list
        self.listGr.append(groupDesc)

        logging.info("OFPT_GROUP_MOD")

    def check_mcGroup(self, groupMod):
        validGroup = False

        if groupMod.group_type != GroupType.OFPGT_ALL:
            return False

        for bucket in groupMod.buckets:
            for action in bucket.actions:
                if action.action_type == ActionType.OFPAT_OUTPUT and self.portNo_exists(action.port.value):
                    validGroup = True

        return validGroup

    def send_OFPT_PORT_STATUS(self, port):
        """Send OFPT_PORT_STATUS OpenFlow message. If the target Port
            already exists, it sends a OFPPR_MODIFY message, else it
            sends a OFPPR_ADD.

        Args:
                port (~pyof.v0x04.common.port.Port): Describe the Port to send
        """

        # Check if Port exists
        if self.portNo_exists(port.port_no):
            reason = PortReason.OFPPR_MODIFY
        else:
            reason = PortReason.OFPPR_ADD

        # Send OFPT_PORT_STATUS message
        port_status = PortStatus(xid=None, reason=reason, desc=port)
        message = port_status.pack()
        self.socket.send(message)

        # Add Port to List of Ports
        self.listPorts.append(port)

        logging.info("Send OFPT_PORT_STATUS")

    def send_OFPT_ERROR_FLOW_MOD_FAILED(self, flow_id, ErrorCode = FlowModFailedCode.OFPFMFC_UNKNOWN):
        """Send OFPT_ERROR OpenFlow message.

        Args:
                flow_id (uint64): cookie or Flow ID
                ErrorCode (~pyof.v0x04.asynchronous.error_msg.FlowModFailedCode): FlowMod code
                        error (default is UNKNOWN).
        """

        flowMod = self.cookie_to_flowMod.get(flow_id)
        if flowMod is None:
            logging.error("Can't find flowMod %d", flow_id)
            return

        flowData = self.cookie_to_flowMod.get_FlowData(flow_id)

        error_msg = ErrorMsg(xid = flowMod.header.xid, error_type = ErrorType.OFPET_FLOW_MOD_FAILED, code = ErrorCode, data = flowData)
        message = error_msg.pack()
        self.socket.send(message)

        logging.info("Send OFPT_ERROR")

    def portNo_exists (self, port_no):
        """Check if the Port exists on the stored 'listPorts'.

        Return:
            True: if the Port exists.
            False: if tha Port doesn't exists.

        Args:
                port_no (uint32): Port number
        """

        for port in self.listPorts:
            if port.port_no == port_no:
                return True

        return False

    def flowToQueue(self, flow_id, flow_action):
        """FLOW indication"""

        logging.info("Flow configuration received:")
        logging.info("****OLT ID: %s", self.queue_id)
        logging.info("****Flow ID: %d", flow_id)
        logging.info("****Action: %s", flow_action)

        data = src.agentQueue.Flow(flow_id, flow_action)
        item = src.agentQueue.QueueItem(self.queue_id, "onos", data)
        oltQueue.put(item)

    def getFlowParameters(self, flow_struct):
        """Get Flow parameters"""

        flowParams = {}

        #General flow parameters
        flowParams["flowId"] = flow_struct.cookie.value
        flowParams["tableId"] = flow_struct.table_id.value
        flowParams["priority"] = flow_struct.priority.value

        #Match
        flowParams["match"] = {}

        for oxm in flow_struct.match.oxm_match_fields:
            if oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_IN_PORT:
                flowParams["match"].update({"inPort" : int.from_bytes(oxm.oxm_value,byteorder='big')})
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_VLAN_VID:
                vlan_present = int.from_bytes(oxm.oxm_value,byteorder='big')
                if (vlan_present & VlanId.OFPVID_PRESENT.value) == VlanId.OFPVID_PRESENT.value:
                    flowParams["match"].update({"vlanId" : (vlan_present ^ VlanId.OFPVID_PRESENT.value)})
                else:
                    return None
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_IP_PROTO:
                flowParams["match"].update({"ipProto" : int.from_bytes(oxm.oxm_value, byteorder='big')})
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_UDP_SRC:
                flowParams["match"].update({"udpSrc" : int.from_bytes(oxm.oxm_value, byteorder='big')})
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_UDP_DST:
                flowParams["match"].update({"udpDst" : int.from_bytes(oxm.oxm_value, byteorder='big')})
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_IPV4_SRC:
                flowParams["match"].update({"ipv4Src" : self.decode_ipAddress(oxm.oxm_value)})
            elif oxm.oxm_field == OxmOfbMatchField.OFPXMT_OFB_IPV4_DST:
                flowParams["match"].update({"ipv4Dst" : self.decode_ipAddress(oxm.oxm_value)})

        if "vlanId" not in flowParams["match"] or "inPort" not in flowParams["match"]:
            return None

        #Instructions
        flowParams["instructions"] = {}

        for j in range(len(flow_struct.instructions)):
            if flow_struct.instructions[j].instruction_type == InstructionType.OFPIT_APPLY_ACTIONS:
                instruction = {}
                vlanOper = "setVlan"
                for k in range(len(flow_struct.instructions[j].actions)):
                    if flow_struct.instructions[j].actions[k].action_type == ActionType.OFPAT_POP_VLAN:
                        vlanOper = "popVlan"
                        instruction.update({vlanOper : flowParams["match"]["vlanId"]})
                    elif flow_struct.instructions[j].actions[k].action_type == ActionType.OFPAT_PUSH_VLAN:
                        vlanOper = "pushVlan"
                    elif flow_struct.instructions[j].actions[k].action_type == ActionType.OFPAT_SET_FIELD:
                        if flow_struct.instructions[j].actions[k].field.oxm_field == OxmOfbMatchField.OFPXMT_OFB_VLAN_VID:
                            vlanTag = int.from_bytes(flow_struct.instructions[j].actions[k].field.oxm_value,byteorder='big') ^ VlanId.OFPVID_PRESENT.value
                            instruction.update({vlanOper : vlanTag})
                            vlanOper = "setVlan" #Para si se hace un unico flow con un pop/push y un set
                    elif flow_struct.instructions[j].actions[k].action_type == ActionType.OFPAT_OUTPUT:
                        out_Port = flow_struct.instructions[j].actions[k].port.value
                        instruction.update({"outPort" : out_Port})
                    elif flow_struct.instructions[j].actions[k].action_type == ActionType.OFPAT_GROUP:
                        instruction.update({"groupId" : flow_struct.instructions[j].actions[k].group_id.value})
                flowParams["instructions"].update(instruction)
            elif flow_struct.instructions[j].instruction_type == InstructionType.OFPIT_GOTO_TABLE:
                table_id = flow_struct.instructions[j].table_id.value
                flowParams["instructions"].update({"gotoTable" : table_id})
            elif flow_struct.instructions[j].instruction_type == InstructionType.OFPIT_METER:
                meter_id = flow_struct.instructions[j].meter_id.value
                flowParams["instructions"].update({"meterId" : meter_id})

        print(flowParams)

        return flowParams

    def check_flows(self, flowConfig):

        #Checking tableId
        print("Checkeando el tableId del Flow")
        if flowConfig["tableId"] >= self.switchTables:
            print("El tableId no es valido")
            return False

        #Checking Flow ports
        print("Checkeando el inPort del Flow")
        if flowConfig["match"]["inPort"] != self.puertoNNI.port_no:
            print("Puerto asociado a la ONT")
            if not self.portNo_exists(flowConfig["match"]["inPort"]):
                logging.error("No existe el puerto")
                return False
            else:
                flowConfig["flowType"] = "upstream"

                if "ipProto" in flowConfig["match"] and flowConfig["match"]["ipProto"] == 17:
                    if "udpDst" in flowConfig["match"] and flowConfig["match"]["udpDst"] == 5060:
                        flowConfig["serviceType"] = "voip"
                        if "ipv4Dst" not in flowConfig["match"]:
                            logging.error("No VoIP server configured.")
                            return False
                print("Existe el puerto")
        else:
            flowConfig["flowType"] = "downstream"
            if "ipProto" in flowConfig["match"] and flowConfig["match"]["ipProto"] == 17:
                if "udpSrc" in flowConfig["match"] and flowConfig["match"]["udpSrc"] == 5060:
                    flowConfig["serviceType"] = "voip"
                    if "ipv4Src" not in flowConfig["match"]:
                        logging.error("No VoIP server configured.")
                        return False
            print("Puerto NNI")

        # Checking Output or Group
        print("Checkeando el outPort y el gotoTable del Flow")
        if "groupId" in flowConfig["instructions"]:
            print("Group ID exists. Multicast Service.")
            if "serviceType" in flowConfig:
                logging.error("VoIP service can't be configured over Multicast service.")
                return False
            flowConfig["serviceType"] = "multicast"
            if not self.listGr.exists(flowConfig["instructions"]["groupId"]):
                logging.error("Group doesn't found")
                return False
        elif "outPort" in flowConfig["instructions"]:
            print("Existe outPort")
            if "serviceType" not in flowConfig:
                flowConfig["serviceType"] = "unicast"
            if self.portNo_exists(flowConfig["instructions"]["outPort"]):
                print("Existe el puerto")
                if flowConfig["match"]["inPort"] == flowConfig["instructions"]["outPort"]:
                    print("Puerto de salida igual a puerto de entrada")
                    return False
            else:
                print("No existe el puerto")
                return False

        elif "gotoTable" in flowConfig["instructions"]:
            print("Existe gotoTable")
            if flowConfig["instructions"]["gotoTable"] <= flowConfig["tableId"] or flowConfig["instructions"]["gotoTable"] >= self.switchTables:
                print("gotoTable erroneo")
                return False

        else:
            return False

        return True

    def matchFlows(self, flow_id):
        """Find all related Flows to create a Service"""
        service = None

        flowParams = self.listF.getFlow(flow_id)
        if flowParams is None:
            logging.error("Error: Flow with id %d doesn't exist", flow_id)
            return None

        if flowParams["tableId"] > 0:
            service = self.backwardTable(flowParams)
            if service is None:
                return []

        services = self.forwardTable(flowParams, service)

        return services

    def matchPorts(self, portsList):
        services = []
        for port in portsList:
            groupIDs = self.listGr.get_groupsByPort(port)

            flows = self.listF.get_port_matched_flows(port["port_no"], port["flowType"], groupIDs)

            for f in flows:
                services.extend(self.matchFlows(flow_id = f["flowId"]))

        return services

    def backwardTable(self, flowParams, service = None):
        backFlows = self.listF.get_matched_flow(flowParams, (flowParams["tableId"] - 1))
        if len(backFlows) != 1:
            logging.error("Can't mach backward Flow. Matched Flows: %d", len(backFlows))
            return None

        backFlow = backFlows[0]

        if service is None:
            service = dict()

        if "flowType" not in service.keys():
            service["flowType"] = backFlow["flowType"]

        if "flowIds" not in service:
            service["flowIds"] = [backFlow["flowId"]]
        else:
            service["flowIds"].insert(0, backFlow["flowId"])

        if "priorities" not in service.keys():
            service["priorities"] = list()

        service["priorities"].append(backFlow["priority"])

        if backFlow["flowType"] == "upstream":
            service["ONUport"] = backFlow["match"]["inPort"]
        elif backFlow["flowType"] == "downstream":
            service["NNIport"] = backFlow["match"]["inPort"]

        # VOIP CONFIGURATION
        if "serviceType" in backFlow and backFlow["serviceType"] == "voip":
            service["serviceType"] = "voip"
            if "voipConfig" not in service:
                service["voipConfig"] = dict()
            if backFlow["flowType"] == "upstream":
                service["voipConfig"]["sipPort"] = backFlow["match"]["udpDst"]
                service["voipConfig"]["sipServer"] = backFlow["match"]["ipv4Dst"]
                if "udpSrc" in backFlow["match"]:
                    service["voipConfig"]["rtpPort"] = backFlow["match"]["udpSrc"]
                if "ipv4Src" in backFlow["match"]:
                    service["voipConfig"]["ipAddress"] = backFlow["match"]["ipv4Src"]
            else:
                service["voipConfig"]["sipPort"] = backFlow["match"]["udpSrc"]
                service["voipConfig"]["sipServer"] = backFlow["match"]["ipv4Src"]
                if "udpDst" in backFlow["match"]:
                    service["voipConfig"]["rtpPort"] = backFlow["match"]["udpDst"]
                if "ipv4Dst" in backFlow["match"]:
                    service["voipConfig"]["ipAddress"] = backFlow["match"]["ipv4Dst"]

        if "meterId" in backFlow["instructions"].keys():
            if "meterIds" not in service.keys():
                service["meterIds"] = [backFlow["instructions"]["meterId"]]
            else:
                service["meterIds"].append(backFlow["instructions"]["meterId"])

        if "vlans" not in service.keys():
            service["vlans"] = list()

        if backFlow["match"]["vlanId"] > 0:
            service["vlans"].insert(0, backFlow["match"]["vlanId"])

        if backFlow["tableId"] > 0:
            service = self.backwardTable(backFlow, service)

        return service

    def forwardTable(self, flowParams, service = None):
        services = []

        if service is None:
            service = dict()

        serviceEnd = False
        nextTable = None

        if "flowType" not in service.keys():
            service["flowType"] = flowParams["flowType"]

        if "flowIds" not in service:
            service["flowIds"] = [flowParams["flowId"]]
        else:
            service["flowIds"].append(flowParams["flowId"])

        if "priorities" not in service.keys():
            service["priorities"] = list()

        service["priorities"].append(flowParams["priority"])

        if flowParams["flowType"] == "upstream":
            if "ONUport" not in service.keys():
                service["ONUport"] = flowParams["match"]["inPort"]
        elif flowParams["flowType"] == "downstream":
            if "NNIport" not in service.keys():
                service["NNIport"] = flowParams["match"]["inPort"]
        else:
            logging.error("Wrong flow type %s", flowParams["flowType"])
            return []

        # VOIP CONFIGURATION
        if "serviceType" in flowParams and flowParams["serviceType"] == "voip":
            service["serviceType"] = "voip"
            if "voipConfig" not in service:
                service["voipConfig"] = dict()
            if flowParams["flowType"] == "upstream":
                service["voipConfig"]["sipPort"] = flowParams["match"]["udpDst"]
                service["voipConfig"]["sipServer"] = flowParams["match"]["ipv4Dst"]
                if "udpSrc" in flowParams["match"]:
                    service["voipConfig"]["rtpPort"] = flowParams["match"]["udpSrc"]
                if "ipv4Src" in flowParams["match"]:
                    service["voipConfig"]["ipAddress"] = flowParams["match"]["ipv4Src"]
            else:
                service["voipConfig"]["sipPort"] = flowParams["match"]["udpSrc"]
                service["voipConfig"]["sipServer"] = flowParams["match"]["ipv4Src"]
                if "udpDst" in flowParams["match"]:
                    service["voipConfig"]["rtpPort"] = flowParams["match"]["udpDst"]
                if "ipv4Dst" in flowParams["match"]:
                    service["voipConfig"]["ipAddress"] = flowParams["match"]["ipv4Dst"]

        if "vlans" not in service.keys():
            service["vlans"] = list()

        if flowParams["match"]["vlanId"] > 0 and (len(service["vlans"]) == 0 or flowParams["match"]["vlanId"] != service["vlans"][-1]):
            service["vlans"].append(flowParams["match"]["vlanId"])

        if "meterIds" not in service.keys():
            service["meterIds"] = list()

        for instruction in flowParams["instructions"].items():
            if instruction[0] == "setVlan" or instruction[0] == "pushVlan":
                service["vlans"].append(instruction[1])
            elif instruction[0] == "meterId":
                service["meterIds"].append(instruction[1])
            elif instruction[0] == "groupId":
                if service["flowType"] == "downstream":
                    if "serviceType" in service and service["serviceType"] == "voip":
                        continue
                    service["groupId"] = instruction[1]
                    service["serviceType"] = "multicast"
                    serviceEnd = True
            elif instruction[0] == "outPort":
                if service["flowType"] == "upstream":
                    service["NNIport"] = instruction[1]
                elif service["flowType"] == "downstream":
                    service["ONUport"] = instruction[1]
                if "serviceType" not in service:
                    service["serviceType"] = "unicast"
                serviceEnd = True
            elif instruction[0] == "gotoTable":
                nextTable = instruction[1]

        if serviceEnd:
            services.append(service)
        elif nextTable is not None:
            fwFlows = self.listF.get_matched_flow(flowParams, nextTable)
            for fwFlow in fwFlows:
                services.extend(self.forwardTable(fwFlow, service))

        return services

    def delete_flow(self, flow_id):
        flowParams = self.listF.getFlow(flow_id)
        if flowParams is None:
            logging.error("Error: Flow with id %d doesn't exist", flow_id)
            return None

        self.listF.delete(flow_id, flowParams["tableId"])
        self.listFS.delete(flow_id)

    def free_flowMod(self, flow_id):
        if flow_id in self.cookie_to_flowMod:
            self.cookie_to_flowMod.pop(flow_id)

    def meterIds_to_bandwidth(self, meterIds):
        totalBandwidth = {}

        for meter in meterIds:
            bandwidth = self.listM.get_meterId_bandwidth(meter)
            if bandwidth is None or len(bandwidth) == 0:
                return {}

            if len(totalBandwidth) == 0:
                totalBandwidth = bandwidth
            else:
                if totalBandwidth["cir"] > bandwidth["cir"]:
                    totalBandwidth["cir"] = bandwidth["cir"]

                if totalBandwidth["pir"] > bandwidth["pir"]:
                    totalBandwidth["pir"] = bandwidth["pir"]

                if totalBandwidth["pbs"] > bandwidth["pbs"]:
                    totalBandwidth["pbs"] = bandwidth["pbs"]

        return totalBandwidth

    def decode_ipAddress(self, field):
        ipAddress = ""
        print(field)

        for i in range(4):
            if i > 0:
                ipAddress += "."
            ipAddress += str(int.from_bytes(field[i:i+1], byteorder='big'))

        print(ipAddress)

        return ipAddress

    def groupId_to_ports(self, group_id):
        return self.listGr.get_group_ports(group_id)

    def update_Flow_statistics(self, flow_id, packet_count, byte_count, timestamp):
        meter_id = self.listFS.get_associated_meter(flow_id)

        self.listFS.update_statistics(flow_id, packet_count, byte_count, timestamp)
        if meter_id is not None:
            self.listMS.update_statistics(meter_id, packet_count, byte_count, timestamp)



