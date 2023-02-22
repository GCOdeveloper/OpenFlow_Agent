# System imports
import logging
import grpc
import random
from voltha_protos import openolt_pb2_grpc
from voltha_protos import openolt_pb2
from voltha_protos import tech_profile_pb2_grpc
from voltha_protos import tech_profile_pb2

# Local imports
import src.agentQueue
from src.agentQueue import oltQueue
import external.omci.omci as omci
from external.omci.omci_defs import OmciNullPointer

class OLTadaptor:
    """Class OLTadaptor:
            Defines the connection with the OLT
            Configures the network
    """

    def __init__(self, ip_address = "0.0.0.0", port = 9191):
        """Initialize variables:
                ip_address (string): OLT IP
                port: connection port
        """

        self.ip_address = ip_address
        self.port = port

        # Create the RPC channel
        self.channel = grpc.insecure_channel(f"{self.ip_address}:{self.port}")
        # Connect with the OLT
        self.stub = openolt_pb2_grpc.OpenoltStub(self.channel)

        # Initilice dicts
        self.omci_queues = {} # Used for ONUs OMCI responds: key(TCI) value(array(intf_id, onu_id, OMCImsg))
        self._omci_mibs = {} # ONU MIB map: key(intf_id, onu_id) value(class OnuMIB)

    def olt_connect(self):
        try:
            device_info = self.stub.GetDeviceInfo(openolt_pb2.Empty())
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        self.vendor = device_info.vendor
        self.model = device_info.model
        self.hw_version = device_info.hardware_version
        self.fw_version = device_info.firmware_version
        self.pon_ports = device_info.pon_ports
        self.serial_num = device_info.device_serial_number
        self.device_id = device_info.device_id
        self.onu_id_start = device_info.onu_id_start
        self.onu_id_end = device_info.onu_id_end
        self.alloc_id_start = device_info.alloc_id_start
        self.alloc_id_end = device_info.alloc_id_end
        self.gemport_id_start = device_info.gemport_id_start
        self.gemport_id_end = device_info.gemport_id_end
        self.gemport_id_mc_start = 4094
        self.flow_id_start = device_info.flow_id_start
        self.flow_id_end = device_info.flow_id_end

        return True

    def activate_onu(self, onu_id, intf_id, vendor_id, vendor_specific):
        serial_number = openolt_pb2.SerialNumber(vendor_id = vendor_id, vendor_specific = vendor_specific)
        onu = openolt_pb2.Onu(intf_id = intf_id, onu_id = onu_id, serial_number = serial_number)

        try:
            self.stub.ActivateOnu(onu)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())

    def flow_add(self, flow):
        try:
            self.stub.FlowAdd(flow)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def flow_remove(self, flow):
        try:
            self.stub.FlowRemove(flow)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def group_perform(self, group):
        try:
            self.stub.PerformGroupOperation(group)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def group_remove(self, group):
        try:
            self.stub.DeleteGroup(group)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def create_traffic_schedulers(self, trafficScheds):
        try:
            self.stub.CreateTrafficSchedulers(trafficScheds)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def remove_traffic_schedulers(self, trafficScheds):
        try:
            self.stub.RemoveTrafficSchedulers(trafficScheds)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def create_traffic_queues(self, trafficQueues):
        try:
            self.stub.CreateTrafficQueues(trafficQueues)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def remove_traffic_queues(self, trafficQueues):
        try:
            self.stub.RemoveTrafficQueues(trafficQueues)
        except grpc.RpcError as e:
            status_code = e.code()
            logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                          self.ip_address, self.port, status_code.name, e.details())
            return False

        return True

    def omci_onu_initialize(self, intf_id, onu_id):
        """Initilize ONU:
                OMCI MIB initialize (MIB RESET and MIB UPLOAD)
                OMCI default entities generation (MAC_BRIDGE_SERVICE_PROFILE,
                                                  MAC_BRIDGE_PORT_CONFIGURATION_DATA
                                                  EXTENDED_VLAN_TAGGING_OPERATION_CONFIGURATION_DATA)

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
        """

        logging.debug("Starting OMCI MIB initialization: ONU ID %d, interface %d.", onu_id, intf_id)

        # Execute OMCI MIB Reset
        mib_key = (intf_id, onu_id)
        logging.info("****Starting MIB RESET...")
        check = self.omci_mib_reset(intf_id, onu_id)
        if not check:
            logging.error("MIB RESET failed: ONU ID %d, interface %d", onu_id, intf_id)
            return False

        logging.debug("****MIB RESET success on ONU ID %d, interface %d", onu_id, intf_id)

        # Execute OMCI MIB Upload
        logging.debug("****Starting MIB UPLOAD...")
        check = self.omci_mib_upload(intf_id, onu_id)
        if not check:
            logging.error("MIB UPLOAD failed: ONU ID %d, interface %d", onu_id, intf_id)
            return False
        logging.debug("****MIB UPLOAD success on ONU ID %d, interface %d", onu_id, intf_id)

        # GET UNIs POTS
        PyPath_TP_UNI = self._omci_mibs[mib_key].get_entity_ids(omci.PptpEthernetUni.class_id)
        # Get MAC_BRIDGE ID
        Ani_G = self._omci_mibs[mib_key].get_entity_ids(omci.AniG.class_id)
        if len(Ani_G) == 0:
            logging.error("ONU ID %d, interface %d ANI_G entity not found.", onu_id, intf_id)
            self.omci_rebootOnt(intf_id, onu_id)

        slot_id = (Ani_G[0] >> 8) & 0xff
        mac_bridge_id = ((slot_id << 8) & 0xff00) | 0x01 if self._omci_mibs[mib_key].entity_exists(omci.Cardholder.class_id, slot_id) else 1

        ## OMCI CREATE - MAC BRIDGE SERVICE PROFILE
        check, result_str = self.create_macBridgeServiceProfile (intf_id, onu_id, mac_bridge_id)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, result_str)
            return False

        logging.debug(result_str)

        check, result_str = self.create_galEthernetProfile(intf_id, onu_id)
        if not check:
            logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, result_str)
            return False

        logging.debug(result_str)

        # UNIs BUCLE
        for uni in PyPath_TP_UNI:
            ## OMCI CREATE - MAC BRIDGE PORT CONFIGURATION DATA
            check, result_str = self.create_macBridgePortConfigurationData (intf_id, onu_id, uni, "PPTP")
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, result_str)
                return False

            logging.debug(result_str)

            ## OMCI CREATE - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
            check, result_str = self.create_extendedVlanTaggingOperationConfigurationData (intf_id, onu_id, uni)
            if not check:
                logging.error("ONU ID %d, interface %d %s", onu_id, intf_id, result_str)
                return False

            logging.debug(result_str)

        return True

    def enable_indications(self, datapath_id):
        """This function subscribes the program to the OLT indications,
            once the connection is stablished, there is a bucle to keep
            listening the indications.
            
            This function must be call throught a thread.

        Args:
                datapath_id (string): The identifier of the OLT, to put the
                indications data on the queue.
        """

        self.queue_id = datapath_id
        indications = self.stub.EnableIndication(openolt_pb2.Empty())

        # Bucle
        while True:
            try:
                ind = next(indications)
            except Exception as e:
                logging.error("gRPC connection lost")
                break
            else:
                if ind.HasField('onu_disc_ind'):
                    self.onu_discovery(ind.onu_disc_ind)
                elif ind.HasField('onu_ind'):
                    self.onu_indication(ind.onu_ind)
                elif ind.HasField('omci_ind'):
                    self.omci_indication(ind.omci_ind)
                elif ind.HasField('flow_stats'):
                    self.flowStats_indication(ind.flow_stats)

    # INDICATIONS FUNCTIONS
    def onu_discovery(self, onuDisc):
        """ONU Discovery Indication"""

        logging.info("ONU Discovery Indication received:")
        logging.info("****OLT ID: %s", self.queue_id)
        logging.info("****ONU interface: %d", onuDisc.intf_id)
        logging.info("****Vendor ID: %s", onuDisc.serial_number.vendor_id.decode("utf-8"))
        logging.info("****Vendor specific: %s", onuDisc.serial_number.vendor_specific.hex()[:8])

        data = src.agentQueue.OnuDisc(onuDisc.intf_id, onuDisc.serial_number.vendor_id, onuDisc.serial_number.vendor_specific)
        item = src.agentQueue.QueueItem(self.queue_id, "olt", data)
        oltQueue.put(item)

    def onu_indication(self, onuInd):
        """Onu Indication"""

        logging.info("ONU Indication received:")
        logging.info("****OLT ID: %s", self.queue_id)
        logging.info("****ONU interface: %d", onuInd.intf_id)
        logging.info("****ONU ID: %d", onuInd.onu_id)
        logging.info("****Oper state: %s", onuInd.oper_state)
        logging.info("****Admin state: %s", onuInd.admin_state)
        logging.info("****Fail reason: %d", onuInd.fail_reason)

        data = src.agentQueue.OnuInd(onuInd.intf_id, onuInd.onu_id, onuInd.oper_state, onuInd.admin_state, onuInd.fail_reason)
        item = src.agentQueue.QueueItem(self.queue_id, "olt", data)
        oltQueue.put(item)

    def flowStats_indication(self, flowStats):
        """FLOW stats indication"""

        logging.info("FLOW stats received:")
        logging.info("****OLT ID: %s", self.queue_id)
        logging.info("****Flow ID: %d", flowStats.flow_id)
        logging.info("****RX bytes: %d", flowStats.rx_bytes)
        logging.info("****RX packets: %d", flowStats.rx_packets)
        logging.info("****TX bytes: %d", flowStats.tx_bytes)
        logging.info("****TX packets: %d", flowStats.tx_packets)
        logging.info("****Timestamp: %d", flowStats.timestamp)

        data = src.agentQueue.FlowStatsInd(flowStats.flow_id,
                                           flowStats.rx_bytes,
                                           flowStats.rx_packets,
                                           flowStats.tx_bytes,
                                           flowStats.tx_packets,
                                           flowStats.timestamp)
        item = src.agentQueue.QueueItem(self.queue_id, "olt", data)
        oltQueue.put(item)

    def omci_indication(self, omciInd):
        """OMCI Indication"""

        msg = omci.OmciFrame(omciInd.pkt[:44])

        tci = msg.getfieldval("transaction_id")
        if tci in self.omci_queues:
            item = (omciInd.intf_id, omciInd.onu_id, msg)
            self.omci_queues[tci].put(item)
        else:
            pass
            #msg.show()

    def omci_msg_transmission(self, intf_id, onu_id, msg_type, ent_class, tci, msg):
        """This function is in charge of send the OMCI messages and wait
            for the response.

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                msg_type (OmciMessage.message_id): OMCI message type (MIB_RESET, CREATE, DELETE, etc)
                ent_class (EntityClass.class_id): target OMCI entity (ONU_DATA, ONU_G, etc)
                tci (uint16): Transmission Correlation Identifier
                msg (omciFrame): message to send, formated with the scapy library
        """

        # Create the queue for OMCI respond
        result_queue = src.agentQueue.queue.Queue()
        # Include the queue on the OMCI queues map
        self.omci_queues[tci] = result_queue

        # Generate the message for RPC communication
        packet = msg.build().hex()
        pkt = openolt_pb2.OmciMsg(intf_id = intf_id, onu_id = onu_id, pkt = bytes(packet, 'utf-8'))

        # Send and wait for the response, 6 tries
        retries = 0
        while retries < 6:
            try:
                # Send the message
                self.stub.OmciMsgOut(pkt)
            except grpc.RpcError as e:
                status_code = e.code()
                logging.error("RPC ERROR recived on OLT %s:%d | %s | Details: %s",
                              self.ip_address, self.port, status_code.name, e.details())
                self.omci_queues.pop(tci)
                return None

            # Retrieve the response from the Queue
            try:
                result_msg = result_queue.get(block = True, timeout = 3)
            except src.agentQueue.queue.Empty:
                retries += 1
                continue
            else:
                self.omci_queues.pop(tci)

                # Check if the message is correct and return the message
                if (result_msg[0] != intf_id or result_msg[1] != onu_id):
                    logging.error("Received wrong OMCI message: interface %d or ONU ID %d malformed.", result_msg[0], result_msg[1])
                    return None

                message_type = result_msg[2].getfieldval("message_type")
                omci_msg = result_msg[2].getfieldval("omci_message")
                entity_class = omci_msg.getfieldval("entity_class")
                if ((message_type & 0x1f) != (msg_type & 0x1f) or entity_class != ent_class):
                    logging.error("Received wrong OMCI message: message type %d or entity_class %d malformed", message_type, entity_class)
                    return None

                return omci_msg

        self.omci_queues.pop(tci)
        return None

    def omci_mib_reset(self, intf_id, onu_id):
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciMibReset.message_id,
            omci_message = omci.OmciMibReset(
                entity_class = omci.OntData.class_id,
                entity_id = 0
            )
        )

        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciMibReset.message_id, omci.OntData.class_id, tci, msg)
        if result_msg is None:
            return False

        if result_msg.getfieldval("success_code") == 0:
            mib_key = (intf_id, onu_id)
            if mib_key in self._omci_mibs:
                self._omci_mibs.pop(mib_key)
            return True
        else: # Reboot the ONT
            check = self.omci_rebootOnt(intf_id, onu_id)
            if check:
                return True

        return False

    def omci_mib_upload(self, intf_id, onu_id):
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciMibUpload.message_id,
            omci_message = omci.OmciMibUpload(
                entity_class = omci.OntData.class_id,
                entity_id = 0
            )
        )

        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciMibUpload.message_id, omci.OntData.class_id, tci, msg)
        if result_msg is None:
            return False

        number_of_frames = result_msg.getfieldval("number_of_commands")
        mib_key = (intf_id, onu_id)
        self._omci_mibs[mib_key] = OnuMIB()

        for i in range(number_of_frames):
            tci = random.randint(0, 32767)
            msg = omci.OmciFrame(
                transaction_id = tci,
                message_type = omci.OmciMibUploadNext.message_id,
                omci_message = omci.OmciMibUploadNext(
                    entity_class = omci.OntData.class_id,
                    entity_id = 0,
                    command_sequence_number = i
                )
            )
            result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciMibUploadNext.message_id, omci.OntData.class_id, tci, msg)
            if result_msg is None:
                return False
            if result_msg.getfieldval("object_entity_class") in OnuMIB.managed_entities:
                self._omci_mibs[mib_key].add_modify_entity(result_msg)

        return True

    def omci_rebootOnt(self, intf_id, onu_id):
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciMibReset.message_id,
            omci_message = omci.OmciReboot(
                entity_class = omci.OntG.class_id,
                entity_id = 0
            )
        )

        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciReboot.message_id, omci.OntG.class_id, tci, msg)
        if result_msg is None:
            return False

        if result_msg.getfieldval("success_code") != 0:
            logging.error("OMCI REBOOT ERROR: %s", omci.omciError_to_str(result_msg.getfieldval("success_code")))
            return False

        return True

    def omci_get_entity_ids (self, intf_id, onu_id, entity_class_id):
        """Return the entity IDs stored on the MIB for the entity
            requested.

        Args:
                intf_id (uint8): ONU interface ID
                onu_id (uint16): ONU ID
                entity_class_id (EntityClass.class_id): Class ID
        """

        mib_key = (intf_id, onu_id)
        result_arr = sorted(self._omci_mibs[mib_key].get_entity_ids(entity_class_id))

        return result_arr

    def omci_get_entity_values (self, intf_id, onu_id, entity_class_id, entity_id, fields):
        """Get the requested values from OMCI MIB, getting the data from the local stored MIB.

        Return:
            The requested fields are returned in dictionary format.

        Args:
                intf_id (uint8): ONU interface ID
                onu_id (uint16): ONU ID
                entity_class_id (EntityClass.class_id): Class ID
                entity_id (EntityClass.managed_entity_id): entity ID
                fields (tuple(string)): Tuple with the requested EntityClass fields names
        """
        mib_key = (intf_id, onu_id)
        result_dict = dict()

        for field in fields:
            result_dict.update({field: self._omci_mibs[mib_key].get_entity_value(entity_class_id, entity_id, field)})

        return result_dict

    def omci_update_entity_values (self, intf_id, onu_id, entity_class, entity_id, fields):
        """Get the requested values from OMCI, sending OmciGet messages to the ONTs,
            and store the data on the local MIB.

        Return:
            The requested fields are returned in dictionary format.

        Args:
                intf_id (uint8): ONU interface ID
                onu_id (uint16): ONU ID
                entity_class_id (EntityClass.class_id): Class ID
                entity_id (EntityClass.managed_entity_id): entity ID
                fields (tuple(string)): Tuple with the requested EntityClass fields names
        """

        mib_key = (intf_id, onu_id)

        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciGet.message_id,
            omci_message = omci.OmciGet(
                entity_class = entity_class.class_id,
                entity_id = entity_id,
                attributes_mask = entity_class.mask_for(*fields)
            )
        )

        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciGet.message_id, entity_class.class_id, tci, msg)
        if result_msg is None or result_msg.getfieldval("success_code") != 0:
            return None

        self._omci_mibs[mib_key].add_modify_entity(result_msg)

        return result_msg.getfieldval("data")


    def create_macBridgeServiceProfile (self, intf_id, onu_id, mac_bridge_id):
        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MAC BRIDGE SERVICE PROFILE
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.MacBridgeServiceProfile.class_id,
                entity_id = mac_bridge_id,
                data = dict(
                    spanning_tree_ind=True,
                    learning_ind=True,
                    port_bridging_ind=True,
                    priority=32000,
                    max_age=6 * 256,
                    hello_time=2 * 256,
                    forward_delay=4 * 256,
                    unknown_mac_address_discard=False
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.MacBridgeServiceProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: MAC BRIDGE SERVICE PROFILE Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****MAC BRIDGE SERVICE PROFILE ID {mac_bridge_id}:\n" +
                      "\t\t\t\t********Spanning_tree_ind = True\n" +
                      "\t\t\t\t********Learning_ind = True\n" +
                      "\t\t\t\t********Port_bridging_ind = True\n" +
                      "\t\t\t\t********Priority = 32000\n" +
                      "\t\t\t\t********Max_age = 1536\n" +
                      "\t\t\t\t********Hello_time = 512\n" +
                      "\t\t\t\t********Forward_delay = 1024\n" +
                      "\t\t\t\t********Unknown_mac_address_discard = False\n"
                      )

        return True, result_str

    def create_macBridgePortConfigurationData (self, intf_id, onu_id, uni_gem_id, tp_type):
        result_str = ""
        mib_key = (intf_id, onu_id)

        MacBridge_ids = self._omci_mibs[mib_key].get_entity_ids(omci.MacBridgeServiceProfile.class_id)
        mac_bridge_id = MacBridge_ids[0]

        if tp_type == "PPTP":
            TPtype = 1
        elif tp_type == "GEM_IW_TP":
            TPtype = 5
        elif tp_type == "MC_GEM_IW_TP":
            TPtype = 6
        else:
            TPtype = 1

        ## OMCI CREATE - MAC BRIDGE PORT CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.MacBridgePortConfigurationData.class_id,
                entity_id = uni_gem_id,
                data = dict(
                    bridge_id_pointer=mac_bridge_id,
                    port_num=uni_gem_id & 0xff,
                    tp_type=TPtype,
                    tp_pointer=uni_gem_id
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.MacBridgePortConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: MAC BRIDGE PORT CONFIGURATION Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****MAC BRIDGE PORT COMFIGURATION DATA ID {uni_gem_id}:\n" +
                      f"\t\t\t\t********Bridge_id_pointer = {mac_bridge_id}\n" +
                      f"\t\t\t\t********Port_num = {uni_gem_id & 0xff}\n" +
                      f"\t\t\t\t********Tp_type = {TPtype}\n" +
                      f"\t\t\t\t********tp_pointer = {uni_gem_id}\n"
                      )

        return True, result_str

    def delete_macBridgePortConfigurationData (self, intf_id, onu_id, uni_gem_id):
        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MAC BRIDGE PORT CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.MacBridgePortConfigurationData.class_id,
                entity_id = uni_gem_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.MacBridgePortConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: MAC BRIDGE PORT CONFIGURATION Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_extendedVlanTaggingOperationConfigurationData (self, intf_id, onu_id, uni_id, association_type = 0):
        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.ExtendedVlanTaggingOperationConfigurationData.class_id,
                entity_id = uni_id,
                data = dict(
                    association_type=association_type,
                    associated_me_pointer=uni_id
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.ExtendedVlanTaggingOperationConfigurationData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: UNI ID " + str(uni_id) + " EXTENDED VLAN TAGGING OPERATION CONFIG DATA Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        ## OMCI SET - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = self.set_extendedVlanTaggingOperationConfigurationData_message(tci, uni_id, "untagged", tags_to_remove = 3, treatmentTPID = 0)

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.ExtendedVlanTaggingOperationConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: UNI ID " + str(uni_id) + " Untagged EXTENDED VLAN TAGGING OPERATION CONFIG DATA Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        ## OMCI SET - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = self.set_extendedVlanTaggingOperationConfigurationData_message(tci, uni_id, "single_tag", tags_to_remove = 3, treatmentTPID = 0)

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.ExtendedVlanTaggingOperationConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: UNI ID " + str(uni_id) + " Single-Tagged EXTENDED VLAN TAGGING OPERATION CONFIG DATA Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        ## OMCI SET - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = self.set_extendedVlanTaggingOperationConfigurationData_message(tci, uni_id, "double_tag", tags_to_remove = 3, treatmentTPID = 0)
        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.ExtendedVlanTaggingOperationConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: UNI ID " + str(uni_id) + " Double-Tagged EXTENDED VLAN TAGGING OPERATION CONFIG DATA Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****EXTENDED VLAN TAGGING OPER CONFIG DATA ID {uni_id}:\n" +
                      f"\t\t\t\t********Association_type = {association_type}\n" +
                      f"\t\t\t\t********Associated_me_pointer = {uni_id}\n"
                      )

        return True, result_str

    def update_extendedVlanTaggingOperationConfigurationData(self, intf_id, onu_id, uni_id, tagType,
                                                                  filter_outer_priority = None,
                                                                  filter_outer_vid = 4096,
                                                                  filter_inner_priority = None,
                                                                  filter_inner_vid = 4096,
                                                                  tags_to_remove = 3,
                                                                  inner_priority = 15,
                                                                  inner_vid = 0,
                                                                  treatmentTPID = 4, delete = False):
        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI SET - EXTENDED VLAN TAGGING OPERATION CONFIGURATION DATA
        tci = random.randint(0, 32767)
        msg = self.set_extendedVlanTaggingOperationConfigurationData_message(tci, uni_id, tagType = tagType,
                                                                             filter_outer_priority = filter_outer_priority,
                                                                             filter_outer_vid = filter_outer_vid,
                                                                             filter_inner_priority = filter_inner_priority,
                                                                             filter_inner_vid = filter_inner_vid,
                                                                             tags_to_remove = tags_to_remove,
                                                                             inner_priority = inner_priority,
                                                                             inner_vid = inner_vid,
                                                                             treatmentTPID = treatmentTPID, delete = delete)

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.ExtendedVlanTaggingOperationConfigurationData.class_id, tci, msg)

        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: UNI ID " + str(uni_id) + " configure EXTENDED VLAN TAGGING OPERATION CONFIG DATA Failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        oper = "Updated" if not delete else "Deleted"
        result_str = (f"\t****{oper} EXTENDED VLAN TAGGING OPER CONFIG DATA ID {uni_id}:\n" +
                      f"\t\t\t\t********Tag_type = {tagType}\n" +
                      f"\t\t\t\t********Filter_outer_priority = {filter_outer_priority}\n" +
                      f"\t\t\t\t********Filter_outer_vid = {filter_outer_vid}\n" +
                      f"\t\t\t\t********Filter_inner_priority = {filter_inner_priority}\n" +
                      f"\t\t\t\t********Filter_inner_vid = {filter_inner_vid}\n" +
                      f"\t\t\t\t********Tags_to_remove = {tags_to_remove}\n" +
                      "\t\t\t\t********Outer_priority = 15\n" +
                      "\t\t\t\t********Outer_vid = 0\n" +
                      f"\t\t\t\t********Inner_priority = {inner_priority}\n" +
                      f"\t\t\t\t********Inner_vid = {inner_vid}\n" +
                      f"\t\t\t\t********TreatmentTPID = {treatmentTPID}\n"
                      )

        return True, result_str

    def set_extendedVlanTaggingOperationConfigurationData_message(self, tci, entity_id, tagType,
                                                                  filter_outer_priority = None,
                                                                  filter_outer_vid = 4096,
                                                                  filter_inner_priority = None,
                                                                  filter_inner_vid = 4096,
                                                                  tags_to_remove = 0,
                                                                  inner_priority = 15,
                                                                  inner_vid = 0,
                                                                  treatmentTPID = 4, delete = False):
        """Create the OMCI message ExtendedVlanTaggingOperationConfigurationData.

        Return:
            Return the OMCI message.

        Args:
                tci (uint16): Transaction Correlation Identifier
                entity_id (uint16): Entity instance ID
                tagType (string): Treatment of the tags (double_tag, single_tag, untagged)
                filter_outer_priority (4 bits): Defines de outer VLAN VID priority filtering
                                                operation.
                filter_outer_vid (13 bits): defines the outer VLAN VID filtering operation.
                filter_inner_priority (4 bits): Defines de inner VLAN VID priority filtering
                                                operation.
                filter_inner_vid (13 bits): defines the inner VLAN VID filtering operation.
                tags_to_remove (2 bits): Remove 0, 1 or 2 tags (3 discard the frame)
                inner_priority (4 bits): Defines the inner VLAN priority treatment.
                inner_vid (13 bits): Defines the inner VLAN VID treatment.
                treatmentTPID (3 bits): Defines both inner and outer VLAN TPID/DEI treatment.
                delete (bool): If True, the message will be created for delete the entry.
        """

        if tagType == "double_tag":
            filter_outer_prio = (filter_outer_priority if filter_outer_priority is not None else 0xe)
        else:
            filter_outer_prio = 0xf

        if tagType != "untagged":
            filter_inner_prio = (filter_inner_priority if filter_inner_priority is not None else 0xe)
        else:
            filter_inner_prio = 0xf

        data = dict(
            input_tpid = 0x8100,
            output_tpid = 0x8100,
            downstream_mode = 0,
            received_frame_vlan_tagging_operation_table = omci.VlanTaggingOperation(
                filter_outer_priority= filter_outer_prio,
                filter_outer_vid= (filter_outer_vid if tagType == "double_tag" else 4096),
                filter_outer_tpid_de=0,

                filter_inner_priority= filter_inner_prio,
                filter_inner_vid= (filter_inner_vid if tagType != "untaged" else 4096),
                filter_inner_tpid_de=0,
                filter_ether_type=0,

                treatment_tags_to_remove=tags_to_remove,
                treatment_outer_priority=15,
                treatment_outer_vid=0,
                treatment_outer_tpid_de=treatmentTPID,

                treatment_inner_priority=inner_priority,
                treatment_inner_vid=inner_vid,
                treatment_inner_tpid_de=treatmentTPID
            )
        )

        if delete:
            data["received_frame_vlan_tagging_operation_table"].delete()

        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.ExtendedVlanTaggingOperationConfigurationData.class_id,
                entity_id = entity_id,
                attributes_mask = omci.ExtendedVlanTaggingOperationConfigurationData.mask_for(*data.keys()),
                data = data
            )
        )

        return msg

    def configure_onu_allocID (self, intf_id, onu_id, alloc_id):
        result_str = ""
        mib_key = (intf_id, onu_id)

        Tcont_id = self._omci_mibs[mib_key].entityID_get_configured_field(omci.Tcont.class_id, "alloc_id", 65535)

        data = dict(
            alloc_id = alloc_id
        )

        ## OMCI CREATE - MAC BRIDGE SERVICE PROFILE
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.Tcont.class_id,
                entity_id = Tcont_id,
                attributes_mask = omci.Tcont.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.Tcont.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: T-CONT configuration failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return None, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****T-CONT ID {Tcont_id}:\n" +
                      f"\t\t\t\t********alloc_id = {alloc_id}\n"
                      )

        return Tcont_id, result_str

    def deconfigure_onu_allocID (self, intf_id, onu_id, alloc_id):
        result_str = ""
        mib_key = (intf_id, onu_id)

        Tcont_id = self._omci_mibs[mib_key].entityID_get_configured_field(omci.Tcont.class_id, "alloc_id", alloc_id)

        data = dict(
            alloc_id = 65535
        )

        ## OMCI CREATE - MAC BRIDGE SERVICE PROFILE
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.Tcont.class_id,
                entity_id = Tcont_id,
                attributes_mask = omci.Tcont.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.Tcont.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: T-CONT configuration failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_gemPortNetworkCTP (self, intf_id, onu_id, gemport_id, tcont_id, queue_id, direction = 3, encryption_key = 0):
        """Create OMCI GEM_PORT_NETWORK_CTP

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                gemport_id (uint16): GEM Port ID
                tcont_id (uint16): T-CONT ID
                queue_id (uint16): Queue ID
                encryption_key (uint8): Specifies the encryption associated to this GEM Port.
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        traffic_mgmt_oper = self._omci_mibs[mib_key].get_entity_value(omci.OntG.class_id, 0, "traffic_management_options")

        if traffic_mgmt_oper == 1:
            traffic_mgmt_up = tcont_id
        else:
            traffic_mgmt_up = queue_id

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.GemPortNetworkCtp.class_id,
                entity_id = gemport_id,
                data = dict(
                    port_id = gemport_id,
                    tcont_pointer = tcont_id,
                    direction = direction,
                    traffic_management_pointer_upstream = traffic_mgmt_up,
                    priority_queue_pointer_downstream = queue_id,
                    encryption_key_ring = encryption_key
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.GemPortNetworkCtp.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: GEM_PORT_NETWORK_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****GEM PORT NETWORK CTP ID {gemport_id}:\n" +
                      f"\t\t\t\t********Port_id = {gemport_id}\n" +
                      f"\t\t\t\t********Tcont_pointer = {tcont_id}\n" +
                      "\t\t\t\t********direction = 3\n" +
                      f"\t\t\t\t********Traffic_management_pointer_upstream = {traffic_mgmt_up}\n" +
                      f"\t\t\t\t********Priority_queue_pointer_downstream = {queue_id}\n" +
                      f"\t\t\t\t********encryption_key_ring = {encryption_key}\n"
                      )

        return True, result_str

    def delete_gemPortNetworkCTP (self, intf_id, onu_id, gemport_id):
        """Create OMCI GEM_PORT_NETWORK_CTP

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                gemport_id (uint16): GEM Port ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.GemPortNetworkCtp.class_id,
                entity_id = gemport_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.GemPortNetworkCtp.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete GEM_PORT_NETWORK_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_galEthernetProfile (self, intf_id, onu_id):
        """Create OMCI GAL_ETHERNET_PROFILE

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        if self._omci_mibs[mib_key].entity_exists(omci.GalEthernetProfile.class_id, 1):
            return True, "success"

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.GalEthernetProfile.class_id,
                entity_id = 1,
                data = dict(
                    max_gem_payload_size = 4095
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.GalEthernetProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: GAL_ETHERNET_PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = ("\t****GAL ETHERNET PROFILE ID 1:\n" +
                      "\t\t\t\t********Max_gem_payload_size = 4095\n"
                      )

        return True, result_str

    def delete_galEthernetProfile (self, intf_id, onu_id):
        """Delete OMCI GAL_ETHERNET_PROFILE

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        if not self._omci_mibs[mib_key].entity_exists(omci.GalEthernetProfile.class_id, 1):
            return True, "success"

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.GalEthernetProfile.class_id,
                entity_id = 1
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.GalEthernetProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete GAL_ETHERNET_PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_gemInterworkingTP (self, intf_id, onu_id, gemport_id, multicast = False):
        """Create OMCI GEM_PORT_NETWORK_CTP

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                gemport_id (uint16): GEM Port ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        MacBridge_ids = self._omci_mibs[mib_key].get_entity_ids(omci.MacBridgeServiceProfile.class_id)
        mac_bridge_id = MacBridge_ids[0]

        ent_class = omci.MulticastGemInterworkingTp.class_id if multicast else omci.GemInterworkingTp.class_id

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = ent_class,
                entity_id = gemport_id,
                data = dict(
                    gem_port_network_ctp_pointer = gemport_id,
                    interworking_option = 1,
                    service_profile_pointer = mac_bridge_id,
                    interworking_tp_pointer = 0,
                    gal_profile_pointer = 1
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                ent_class, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: GEM_PORT_NETWORK_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        mc_str = "MULTICAST" if multicast else ""
        result_str = (f"\t****{mc_str}GEM INTERWORKING TP ID {gemport_id}:\n" +
                      f"\t\t\t\t********Gem_port_network_ctp_pointer = {gemport_id}\n" +
                      "\t\t\t\t********Interworking_option = 1\n" +
                      f"\t\t\t\t********Service_profile_pointer = {mac_bridge_id}\n" +
                      "\t\t\t\t********Interworking_tp_pointer = 0\n" +
                      "\t\t\t\t********gal_profile_pointer = 1\n"
                      )

        if multicast:
            ## OMCI SET - IPv4 Multicast Address
            tci = random.randint(0, 32767)
            msg = self.set_multicastGemInterworkingTP(tci, gemport_id, gemport_id, "224.0.0.0", "239.255.255.255")

            # Send OMCI msg
            result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                    omci.MulticastGemInterworkingTp.class_id, tci, msg)

            if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
                result_str += "OMCI ERROR: ONU ID " + str(onu_id) + " Multicast GEM Interworking TP Failed: "
                if result_msg is not None:
                    result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
                return False, result_str

            self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, result_str

    def delete_gemInterworkingTP (self, intf_id, onu_id, gemport_id, multicast = False):
        """Delete OMCI GEM_PORT_NETWORK_CTP

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                gemport_id (uint16): GEM Port ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)
        ent_class = omci.MulticastGemInterworkingTp.class_id if multicast else omci.GemInterworkingTp.class_id

        ## OMCI CREATE - GEM PORT NETWORK CTP
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = ent_class,
                entity_id = gemport_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                ent_class, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete GEM_INTERWORKING_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def set_multicastGemInterworkingTP (self, tci, entity_id, gemPort, ip_start, ip_end, delete = False):
        """Create the OMCI message ExtendedVlanTaggingOperationConfigurationData.

        Return:
            Return the OMCI message.

        Args:
                tci (uint16): Transaction Correlation Identifier
                entity_id (uint16): Entity instance ID
                gemPort (uint16): GEM Port
                ip_start (uint32): IP multicast DA range start
                ip_end (uint32): IP multicast DA range end
                delete (bool): If True, the message will be created for delete the entry.
        """


        data = dict(
            ipv4_multicast_address_table = omci.IPv4MulticastAddress(
                gem_port_id = gemPort,
                ip_multicast_da_range_start = ip_start,
                ip_multicast_da_range_stop = ip_end
            )
        )

        if delete:
            data["ipv4_multicast_address_table"].delete()

        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.MulticastGemInterworkingTp.class_id,
                entity_id = entity_id,
                attributes_mask = omci.MulticastGemInterworkingTp.mask_for(*data.keys()),
                data = data
            )
        )

        return msg

    def create_vlanTaggingFilterData (self, intf_id, onu_id, entity_id, arr_vlans):
        """Create OMCI VLAN_TAGGING_FILTER_DATA

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
                arr_vlans (list(tuple(vlan_p, vlan_t))): Array with all the VLANs
                    to be filtered.
        """

        result_str = ""
        mib_key = (intf_id, onu_id)
        CFI = 0
        vlanFilterList = []

        if len(arr_vlans) > 12:
            return False, "VLANs limit exceded"

        for vlan in arr_vlans:
            shortNum = ((vlan[0] << 13) & 0xe000) | ((CFI << 12) & 0x1000) | (vlan[1] & 0x0fff)
            vlanFilterList.append(shortNum)


        ## OMCI CREATE - VLAN TAGGING FILTER DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.VlanTaggingFilterData.class_id,
                entity_id = entity_id,
                data = dict(
                    vlan_filter_list = vlanFilterList,
                    forward_operation = 0x10,
                    number_of_entries = len(arr_vlans)
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.VlanTaggingFilterData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: GEM_PORT_NETWORK_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****VLAN TAGGING FILTER DATA ID {entity_id}:\n" +
                      f"\t\t\t\t********Vlan_filter_list = {arr_vlans}\n" +
                      "\t\t\t\t********Forward_operation = 0x10\n" +
                      f"\t\t\t\t********Number_of_entires = {len(arr_vlans)}\n"
                      )

        return True, result_str

    def delete_vlanTaggingFilterData (self, intf_id, onu_id, entity_id):
        """Create OMCI VLAN_TAGGING_FILTER_DATA

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - VLAN TAGGING FILTER DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.VlanTaggingFilterData.class_id,
                entity_id = entity_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.VlanTaggingFilterData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete GEM_PORT_NETWORK_CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_multicastOperationsProfile (self, intf_id, onu_id, entity_id, upVlan):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
                vlan (tuple(vlan_p, vlan_t)): Upstream traffic VLAN.
        """

        result_str = ""
        mib_key = (intf_id, onu_id)
        CFI = 0

        upTCI = ((upVlan[0] << 13) & 0xe000) | ((CFI << 12) & 0x1000) | (upVlan[1] & 0x0fff)


        ## OMCI CREATE - VLAN TAGGING FILTER DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.MulticastOperationsProfile.class_id,
                entity_id = entity_id,
                data = dict(
                    igmp_version = 3,
                    igmp_function = 0,
                    immediate_leave = 1,
                    us_igmp_tci = upTCI,
                    us_igmp_tag_ctrl = 2,
                    us_igmp_rate = 0,
                    robustness = 0,
                    querier_ip = "0.0.0.0",
                    query_interval = 0,
                    querier_max_response_time = 0
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.MulticastOperationsProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: MULTICAST OPERATIONS PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****MULTICAST OPERATIONS PROFILE ID {entity_id}:\n" +
                      f"\t\t\t\t********Upstream Vlan = {upVlan}\n")

        return True, result_str

    def delete_multicastOperationsProfile (self, intf_id, onu_id, entity_id):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - VLAN TAGGING FILTER DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.MulticastOperationsProfile.class_id,
                entity_id = entity_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.MulticastOperationsProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete MULTICAST OPERATION PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def create_multicastSubscriberConfigInfo (self, intf_id, onu_id, entity_id, operProfile_id):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
                operProfile_id (uint16): Multicast Operations Profile entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.MulticastSubscriberConfigInfo.class_id,
                entity_id = entity_id,
                data = dict(
                    me_type = 0,
                    mcast_operations_profile_pointer = operProfile_id,
                    max_simultaneous_groups = 0,
                    max_multicast_bandwidth = 0,
                    bandwidth_enforcement = 0
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.MulticastSubscriberConfigInfo.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: MULTICAST SUBSCRIBER CONFIG INFO failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****MULTICAST SUBSCRIBER CONFIG INFO ID {entity_id}:\n" +
                      f"\t\t\t\t********OperationsProfileID = {operProfile_id}\n")

        return True, result_str

    def delete_multicastSubscriberConfigInfo (self, intf_id, onu_id, entity_id):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = omci.MulticastSubscriberConfigInfo.class_id,
                entity_id = entity_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                omci.MulticastSubscriberConfigInfo.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete MULTICAST SUBSCRIBER CONFIG INFO failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

    def set_VoipConfigData (self, intf_id, onu_id):
        """Set VoIP Config Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        data = dict(
            signalling_protocol_used = 0x01,
            voip_configuration_method_used = 0x01
        )

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.VoipConfigData.class_id,
                entity_id = 0,
                attributes_mask = omci.VoipConfigData.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.VoipConfigData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: VOIP CONFIG DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****IP VOIP CONFIG DATA ID 0:\n" + 
                      "\t\t\t\t********Signalling protocol = SIP\n" +
                      "\t\t\t\t********VoIP config method = OMCI\n")

        return True, result_str

    def set_ipHostConfigData (self, intf_id, onu_id, entity_id, ipAddress = None, mask = None,
                              gateway = None, primaryDNS = None, secondaryDNS = None, delete = False):
        """Set IP Host Config Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        if delete:
            ip_options = 0x00
        elif ipAddress is None or mask is None or gateway is None:
            ip_options = 0x0f
        else:
            ip_options = 0x0e

        data = dict(
            ip_options = ip_options,
            ip_address = ipAddress,
            mask = mask,
            gateway = gateway,
            primary_dns = primaryDNS,
            secondary_dns = secondaryDNS
        )

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.IpHostConfigData.class_id,
                entity_id = entity_id,
                attributes_mask = omci.IpHostConfigData.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.IpHostConfigData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: IP HOST CONFIG DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****IP HOST CONFIG DATA ID {entity_id}:\n")
        if delete:
            result_str += "\t\t\t\t********IP host config data DISABLE\n"
        elif ipAddress is None or mask is None or gateway is None:
            result_str += "\t\t\t\t********DHCP enable = True\n"
        else:
            result_str += f"\t\t\t\t********IpAddress = {ipAddress}\n"
            result_str += f"\t\t\t\t********Mask = {mask}\n"
            result_str += f"\t\t\t\t********Gateway = {gateway}\n"

        return True, result_str

    def create_tcpUdpConfigData (self, intf_id, onu_id, entity_id, port, ip_host_pointer):
        """Create TCP/UDP config data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.TcpUdpConfigData.class_id,
                entity_id = entity_id,
                data = dict(
                    port_id = port,
                    protocol = 0x11, # UDP
                    tos_diffserv_field = 0,
                    ip_host_pointer = ip_host_pointer
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.TcpUdpConfigData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: TCP/UDP CONFIG DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****TCP/UDP CONFIG DATA ID {entity_id}:\n" +
                      f"\t\t\t\t********Port = {port}\n" +
                      f"\t\t\t\t********IpHost pointer = {ip_host_pointer}\n")

        return True, result_str

    def create_VoiceServiceProfile (self, intf_id, onu_id, entity_id):
        """Create Voice Service Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.VoiceServiceProfile.class_id,
                entity_id = entity_id,
                data = dict(
                    annuncement_type = 0xff,
                    jitter_target = 0,
                    jitter_buffer_max = 0,
                    echo_cancel_ind = 1,
                    pstn_protocol_variant = 0,
                    dtmf_digit_levels = 0x8000,
                    dtmf_digit_duration = 0,
                    hook_flash_minimum_time = 0,
                    hook_flash_maximum_time = 0,
                    network_specific_extensions_pointer = OmciNullPointer
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.VoiceServiceProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: VOICE SERVICE PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****VOICE SERVICE PROFILE ID {entity_id}:\n")

        return True, result_str

    def create_RtpProfileData (self, intf_id, onu_id, entity_id):
        """Create RTP Profile Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.RtpProfileData.class_id,
                entity_id = entity_id,
                data = dict()
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.RtpProfileData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: RTP PROFILE DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****RTP PROFILE DATA ID {entity_id}:\n")

        return True, result_str

    def create_VoipMediaProfile (self, intf_id, onu_id, entity_id, service_pointer, rtp_pointer):
        """Create VoIP Media Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
                service_pointer (uint16): VoIP Service Profile pointer
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.VoipMediaProfile.class_id,
                entity_id = entity_id,
                data = dict(
                    voip_service_profile_pointer = service_pointer,
                    rtp_profile_pointer = rtp_pointer
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.VoipMediaProfile.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: VOIP MEDIA PROFILE failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****VOIP MEDIA PROFILE ID {entity_id}:\n" +
                      f"\t\t\t\t********VoIP service profile pointer = {service_pointer}\n" +
                      f"\t\t\t\t********RTP profile pointer = {rtp_pointer}\n")

        return True, result_str

    def create_VoipVoiceCtp (self, intf_id, onu_id, entity_id, sip_user_pointer, pptp_pointer, voip_profile_pointer):
        """Create VoIP Media Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
                sip_user_pointer (uint16): SIP User Data pointer
                pptp_pointer (uint16): POTS TP pointer
                voip_profile_pointer (uint16): VoIP Media Profile pointer
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.VoipVoiceCtp.class_id,
                entity_id = entity_id,
                data = dict(
                    user_protocol_pointer = sip_user_pointer,
                    pptp_pointer = pptp_pointer,
                    voip_media_profile_pointer = voip_profile_pointer
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.VoipVoiceCtp.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: VOIP VOICE CTP failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****VOIP VOICE CTP ID {entity_id}:\n" +
                      f"\t\t\t\t********User Protocol pointer = {sip_user_pointer}\n" +
                      f"\t\t\t\t********PPTP pointer = {pptp_pointer}\n" +
                      f"\t\t\t\t********VoIP Media Profile pointer = {voip_profile_pointer}\n")

        return True, result_str

    def create_SipConfiguration(self, intf_id, onu_id, uni_id, ipAddress, username, password,
                                primaryDNS, secondaryDNS, tcp_udp_pointer, validation_scheme = 0):
        """Create SIP configuration:
            - SIP Agent Config Data
            - SIP User Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        check, netMsg = self.create_NetworkAddress(intf_id, onu_id, uni_id, ipAddress, username, password, validation_scheme)
        if not check:
            return False, netMsg

        ckeck, agMsg = self.create_SipAgentConfigData(intf_id, onu_id, uni_id, ipAddress, username, password,
                                                    primaryDNS, secondaryDNS, tcp_udp_pointer, validation_scheme)
        if not check:
            return False, agMsg

        check, usMsg = self.create_SipUserData(intf_id, onu_id, uni_id, uni_id, username, password)
        if not check:
            return False, usMsg

        msg = netMsg + "\n\t\t\t" + agMsg + "\n\t\t\t" + usMsg

        return True, msg

    def delete_SipConfiguration(self, intf_id, onu_id, uni_id, username):
        """Delete SIP configuration:
            - SIP Agent Config Data
            - SIP User Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                uni_id (uint16): Entity ID
        """

        check, msg = self.delete_SipUserData(intf_id, onu_id, uni_id, username)
        if not check:
            return False, msg

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.SipAgentConfigData.class_id, uni_id)
        if not check:
            return False, msg

        check, msg = self.delete_NetworkAddress(intf_id, onu_id, uni_id)
        if not check:
            return False, msg

        return True, "success"

    def create_SipAgentConfigData(self, intf_id, onu_id, entity_id, ipAddress, username, password,
                                  primaryDNS, secondaryDNS, tcp_udp_pointer, validation_scheme = 0):
        """Create VoIP Media Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.SipAgentConfigData.class_id,
                entity_id = entity_id,
                data = dict(
                    proxy_server_address_pointer = entity_id,
                    outbound_proxy_address_pointer = entity_id,
                    primary_sip_dns = primaryDNS,
                    secondary_sip_dns = secondaryDNS,
                    sip_registrar = entity_id
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.SipAgentConfigData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: SIP AGENT CONFIG DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        data = dict(
            tcp_udp_pointer = tcp_udp_pointer
        )

        # CONFIGURE SIP AGENT CONFIG DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.SipAgentConfigData.class_id,
                entity_id = entity_id,
                attributes_mask = omci.SipAgentConfigData.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.SipAgentConfigData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: SIP AGENT CONFIG DATA failed: "
            if result_msg is not None:
                err = omci.omciError_to_str(result_msg.getfieldval("success_code"))
                if err != "AttributeFailure":
                    result_str += err
                    return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****SIP AGENT CONFIG DATA ID {entity_id}:\n" +
                      f"\t\t\t\t********Proxy server = {ipAddress}\n" +
                      f"\t\t\t\t********Outbound Proxy server = {ipAddress}\n" +
                      f"\t\t\t\t********Primary DNS = {primaryDNS}\n" +
                      f"\t\t\t\t********Secondary DNS = {secondaryDNS}\n" +
                      f"\t\t\t\t********SIP username = {username}\n" +
                      f"\t\t\t\t********SIP password = {password}\n" +
                      f"\t\t\t\t********SIP registrar server = {ipAddress}\n" +
                      f"\t\t\t\t********TCP/UDP pointer = {tcp_udp_pointer}\n")

        return True, result_str

    def create_SipUserData(self, intf_id, onu_id, entity_id, uni_id, username, password):
        """Create SIP User Data

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - LARGE STRING
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.LargeString.class_id,
                entity_id = username,
                data = dict()
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.LargeString.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: LARGE STRING failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        data = omci.LargeString.update_string(str(username))

        # CONFIGURE LARGE STRING
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.LargeString.class_id,
                entity_id = username,
                attributes_mask = omci.LargeString.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.LargeString.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: LARGE STRING failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        ## OMCI CREATE - SIP USER DATA
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.SipUserData.class_id,
                entity_id = entity_id,
                data = dict(
                    sip_agent_pointer = entity_id,
                    user_part_aor = username,
                    username_and_password = entity_id,
                    pptp_pointer = uni_id
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.SipUserData.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: SIP USER DATA failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****SIP USER DATA ID {entity_id}:\n" +
                      f"\t\t\t\t********SIP Agent pointer = {entity_id}\n" +
                      f"\t\t\t\t********User part AOR = {username}\n" +
                      f"\t\t\t\t********Username and Pass pointer = {entity_id}\n" +
                      f"\t\t\t\t********PPTP pointer = {uni_id}\n")

        return True, result_str

    def delete_SipUserData (self, intf_id, onu_id, entity_id, username):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_class (omci.omci_entities.entity.class_id): Entity class ID
                entity_id (uint16): Entity ID
        """

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.SipUserData.class_id, entity_id)
        if not check:
            return False, msg

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.LargeString.class_id, username)
        if not check:
            return False, msg

        return True, "success"

    def create_AuthentincationSecurityMethod(self, intf_id, onu_id, entity_id, username, password, validation_scheme = 0):
        """Create VoIP Media Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - AUTHENTICATION SECURITY METHOD
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.AuthenticationSecurityMethod.class_id,
                entity_id = entity_id,
                data = dict()
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.AuthenticationSecurityMethod.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Creation AUTHENTICATION SECURITY METHOD failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        data = dict(
            validation_scheme = validation_scheme,
            username_1 = str(username)
        )

        # CONFIGURE AUTHENTICATION SECURITY METHOD
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.AuthenticationSecurityMethod.class_id,
                entity_id = entity_id,
                attributes_mask = omci.AuthenticationSecurityMethod.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.AuthenticationSecurityMethod.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Configuration AUTHENTICATION SECURITY METHOD failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        data = dict(
            password = password
        )

        # CONFIGURE AUTHENTICATION SECURITY METHOD
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.AuthenticationSecurityMethod.class_id,
                entity_id = entity_id,
                attributes_mask = omci.AuthenticationSecurityMethod.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.AuthenticationSecurityMethod.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Configuration AUTHENTICATION SECURITY METHOD failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, result_str

    def create_NetworkAddress(self, intf_id, onu_id, entity_id, ipAddress, username, password, validation_scheme = 0):
        """Create VoIP Media Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        check, msg = self.create_AuthentincationSecurityMethod(intf_id, onu_id, entity_id, username, password, validation_scheme)
        if not check:
            return False, msg

        ## OMCI CREATE - LARGE STRING
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.LargeString.class_id,
                entity_id = entity_id,
                data = dict()
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.LargeString.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: LARGE STRING failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        data = omci.LargeString.update_string(ipAddress)

        # CONFIGURE LARGE STRING
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.LargeString.class_id,
                entity_id = entity_id,
                attributes_mask = omci.LargeString.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.LargeString.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: LARGE STRING failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        ## OMCI CREATE - NETWORK ADDRESS
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciCreate.message_id,
            omci_message = omci.OmciCreate(
                entity_class = omci.NetworkAddress.class_id,
                entity_id = entity_id,
                data = dict(
                    security_pointer = entity_id,
                    address_pointer = entity_id
                )
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciCreate.message_id,
                                                omci.NetworkAddress.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: NETWORK ADDRESS failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****NETWORK ADDRESS ID {entity_id}:\n" +
                      f"\t\t\t\t********Username = {username}\n" +
                      f"\t\t\t\t********Password = {password}\n" +
                      f"\t\t\t\t********Address = {ipAddress}\n")

        return True, result_str

    def delete_NetworkAddress (self, intf_id, onu_id, entity_id):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_id (uint16): Entity ID
        """

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.NetworkAddress.class_id, entity_id)
        if not check:
            return False, msg

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.LargeString.class_id, entity_id)
        if not check:
            return False, msg

        check, msg = self.delete_omciEntity(intf_id, onu_id, omci.AuthenticationSecurityMethod.class_id, entity_id)
        if not check:
            return False, msg

        return True, "success"

    def configure_PotsUni(self, intf_id, onu_id, uni_id):
        """Configure POTS UNI

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                uni_id (uint16): PPTP POTS UNI ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        data = dict(
            administrative_state = 0,
            transmission_path = 0
        )

        # CONFIGURE PPTP POTS UNI
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciSet.message_id,
            omci_message = omci.OmciSet(
                entity_class = omci.PptpPotsUni.class_id,
                entity_id = uni_id,
                attributes_mask = omci.PptpPotsUni.mask_for(*data.keys()),
                data = data
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciSet.message_id,
                                                omci.PptpPotsUni.class_id, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Configure PPTP POTS UNI failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        result_str = (f"\t****PPTP POTS UNI ID {uni_id}:\n" +
                      "\t\t\t\t********Admin state = 0\n" +
                      "\t\t\t\t********Transmission path = 0\n")

        return True, result_str

    def delete_omciEntity (self, intf_id, onu_id, entity_class, entity_id):
        """Create Multicast Operations Profile

        Args:
                intf_id (uint8): ONU interface
                onu_id (uint16): ONU ID
                entity_class (omci.omci_entities.entity.class_id): Entity class ID
                entity_id (uint16): Entity ID
        """

        result_str = ""
        mib_key = (intf_id, onu_id)

        ## OMCI CREATE - MULTICAST SUBSCRIBER CONFIG INFO
        tci = random.randint(0, 32767)
        msg = omci.OmciFrame(
            transaction_id = tci,
            message_type = omci.OmciDelete.message_id,
            omci_message = omci.OmciDelete(
                entity_class = entity_class,
                entity_id = entity_id
            )
        )

        # Send OMCI msg
        result_msg = self.omci_msg_transmission(intf_id, onu_id, omci.OmciDelete.message_id,
                                                entity_class, tci, msg)
        if (result_msg is None) or (result_msg.getfieldval("success_code") != 0):
            result_str += "OMCI ERROR: Delete failed: "
            if result_msg is not None:
                result_str += omci.omciError_to_str(result_msg.getfieldval("success_code"))
            return False, result_str

        self._omci_mibs[mib_key].add_modify_entity(msg.getfieldval("omci_message"))

        return True, "success"

# CLASS ONU MIB
class OnuMIB:
    """Contains and manage the ONU MIB information"""

    # Managed entities
    managed_entities = [
        omci.OntData.class_id,
        omci.OntG.class_id,
        omci.AniG.class_id,
        omci.Cardholder.class_id,
        omci.Tcont.class_id,
        omci.PptpEthernetUni.class_id,
        omci.PptpPotsUni.class_id,
        omci.Ont2G.class_id,
        omci.MacBridgeServiceProfile.class_id,
        omci.MacBridgePortConfigurationData.class_id,
        omci.ExtendedVlanTaggingOperationConfigurationData.class_id,
        omci.GemPortNetworkCtp.class_id,
        omci.GalEthernetProfile.class_id,
        omci.GemInterworkingTp.class_id,
        omci.MulticastGemInterworkingTp.class_id,
        omci.PriorityQueueG.class_id,
        omci.MulticastOperationsProfile.class_id,
        omci.MulticastSubscriberConfigInfo.class_id,
        omci.VoipConfigData.class_id,
        omci.IpHostConfigData.class_id
    ]

    managed_tables = {
        omci.ExtendedVlanTaggingOperationConfigurationData.class_id : "received_frame_vlan_tagging_operation_table",
        omci.MulticastGemInterworkingTp.class_id : "ipv4_multicast_address_table"
        #omci.MulticastOperationsProfile.class_id : "dynamic_access_control_list_table"
    }

    def __init__(self):
        self._mib = {}

    # Class methods
    def add_modify_entity(self, msg):
        """Add or modify a entity from OMCI message data.
            The supported messages types are:
                OmciMibUploadNextResponse
                OmciSet
                OmciCreate
                OmciResponse
                OmciDelete

        Args:
                msg (OmciMessage): message to upload MIB data
        """

        # Retrieve the data from the message
        if msg.__class__.__name__ == "OmciMibUploadNextResponse":
            entity_class = msg.getfieldval("object_entity_class")
            entity_id = msg.getfieldval("object_entity_id")
            data = msg.getfieldval("object_data")
        elif msg.__class__.__name__ in ("OmciSet", "OmciCreate", "OmciGetResponse"):
            entity_class = msg.getfieldval("entity_class")
            entity_id = msg.getfieldval("entity_id")
            data = msg.getfieldval("data")
        elif msg.__class__.__name__ == "OmciDelete":
            entity_class = msg.getfieldval("entity_class")
            entity_id = msg.getfieldval("entity_id")
        else:
            return

        # Update MIB
        key = (entity_class, entity_id)

        if msg.__class__.__name__ == "OmciSet" and entity_class in self.managed_tables:
            table_field = self.managed_tables[entity_class]
            if table_field in data:
                self._tableEntry_treatment(key, table_field, data[table_field])
                data.pop(table_field)

        if key in self._mib:
            if msg.__class__.__name__ == "OmciDelete":
                self._mib.pop(key)
            else:
                self._mib[key].update(data)
        elif msg.__class__.__name__ != "OmciDelete":
            self._mib[key] = data

    def _tableEntry_treatment(self, mib_key, table_field, tableOperation):
        if mib_key not in self._mib:
            self._mib[mib_key] = dict()

        if table_field not in self._mib[mib_key]:
            self._mib[mib_key].update({table_field : []})

        for entry in self._mib[mib_key].get(table_field):
            if entry.index() == tableOperation.index():
                self._mib[mib_key][table_field].remove(entry)
        
        if not tableOperation.is_delete():
            self._mib[mib_key][table_field].append(tableOperation)

    def get_entity_ids(self, entity_class_id):
        """Return the entity IDs stored on the MIB for the entity
            requested.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
        """

        entityIDs = []
        for key in self._mib.keys():
            if key[0] == entity_class_id:
                entityIDs.append(key[1])
        return entityIDs
    
    def entity_exists(self, entity_class_id, entity_id):
        """Check if the requested entity exists.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
                entity_id (EntityClass.managed_entity_id): entity ID
        """

        key = (entity_class_id, entity_id)
        return key in self._mib

    def entity_field_configured(self, entity_class_id, field, value):
        """Check if the requested entity field is configured with
            the given value.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
                field (string): EntityClass field name
                value(any): value of the field
        """
        entity_ids = self.get_entity_ids(entity_class_id)

        for i in entity_ids:
            if self._mib[(entity_class_id, i)].get(field) == value:
                return True

        return False

    def entityID_get_configured_field(self, entity_class_id, field, defaultValue):
        """Given a field of an entity class and his default value,
            check if there is a entry with this default value and
            return the entity ID.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
                field (string): EntityClass field name
                defaultValue(any): default value of the field
        """
        entity_ids = self.get_entity_ids(entity_class_id)

        for i in entity_ids:
            if self._mib[(entity_class_id, i)].get(field) == defaultValue:
                return i

        return None

    def get_entity_value(self, entity_class_id, entity_id, field):
        """Return the value of a entity field.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
                entity_id (EntityClass.managed_entity_id): entity ID
                field (string): EntityClass field name
        """

        key = (entity_class_id, entity_id)
        return self._mib[key].get(field)

    def get_entity_data(self, entity_class_id, entity_id):
        """Return the value of all the entity fields.
            The values are returned in dictionary format.

        Args:
                entity_class_id (EntityClass.class_id): Class ID
                entity_id (EntityClass.managed_entity_id): entity ID
        """

        key = (entity_class_id, entity_id)
        return self._mib[key]

