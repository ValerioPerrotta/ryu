#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import struct

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, \
    HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology import event

LOG = logging.getLogger('app.openstate.ingressegress')

#numero totale delle porte dello switch
SWITCH_PORTS = 4
#lista delle edge port
EDGE_PORTS = range(1,4)
#numero della porta di trasporto
TRANSPORT_PORT = 4

#numero degli edge switch
EDGE_SWITCHES = 3


class OSIngressEgress(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        LOG.info("OpenState INGRESS-EGRESS SWITCHING sample app initialized")
        LOG.info("Supporting MAX %d ports per switch" % SWITCH_PORTS)
        super(OSIngressEgress, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto

        self.send_features_request(datapath)

        self.send_table_mod(datapath, table_id=0)
	self.send_table_mod(datapath, table_id=3)

        self.send_key_lookup(datapath)
        self.send_key_update(datapath)

        self.add_flow_to_each_table(datapath, False)


    def add_flow_to_each_table(self, datapath, table_miss=False):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
	my_id = datapath.id	#switch id

        LOG.info("Configuring flow tables for switch %d" % my_id)

        if table_miss:
            LOG.debug("Installing table miss...")
            actions = [parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
            match = parser.OFPMatch()
            inst = [parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions)]
            mod = parser.OFPFlowMod(
                datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
                command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
                priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                flags=0, match=match, instructions=inst)

            datapath.send_msg(mod)

        else:

		'''

		Lookup-scope=ETH_DST
		Update-scope=ETH_SRC

		'''
		#TABLE 0
		#The state tab 0 handles the first state of eth_dst
		#	STATE1 == HOST_PORT the port where the host speaks from
		#	METADATA == STATE1 for following tables
		LOG.info("Installing rules for State Table 0, switch: %d" % my_id)

		for in_port in range( 1, SWITCH_PORTS + 1):	#I must install a flow mod for each switch port
			LOG.info("Installing rule for port %d (switch %d)" % (in_port,  my_id))
			in_port_is_edge = self.in_list( list_ = EDGE_PORTS, value = in_port )	#check whether in_port is an edge port or not
			if in_port_is_edge == True:
				#cycle on the state
					#if state == 0 --> set_state(in_port) and goto tab 1 with metadata = 0
					#else if state == TRANSPORT_PORT --> set_state(in_port) and goto tab1 with metadata == TRANSPORT
					#else (state != 0 and state != TRANSPORT_PORT) --> set_state(in_port) and output(state)
				for state in range(0, SWITCH_PORTS + 1):
					if state == 0:
						match = parser.OFPMatch(in_port = in_port, state = state)
						actions = [ parser.OFPActionSetState(state = in_port, stage_id = 0) ]
						inst = [
							 parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							 parser.OFPInstructionWriteMetadata( metadata = 0, metadata_mask = 0xFFFFFFFF ),
							 parser.OFPInstructionGotoTable( table_id = 1 )	]

					elif state == TRANSPORT_PORT:
						match = parser.OFPMatch(in_port = in_port, state = state)
						actions = [ parser.OFPActionSetState(state = in_port, stage_id = 0) ]
						inst = [
							 parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							 parser.OFPInstructionWriteMetadata( metadata = TRANSPORT_PORT, metadata_mask = 0xFFFFFFFF ),
							 parser.OFPInstructionGotoTable( table_id = 1 )	]
					else:
						match = parser.OFPMatch( in_port = in_port, state = state)
						actions = [ 
							    parser.OFPActionSetState( state = in_port, stage_id = 0),
							    parser.OFPActionOutput( state , 0 )]
						inst = [ parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions) ]

					#flow mod code
				        mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)

					datapath.send_msg(mod)
			else:
				#cycle on the state
					#if state == 0 --> set_state(in_port) and goto tab 1 with metadata = 0
					#else --> set_state(in_port) and goto tab 1 with metadata = state
				for state in range( 0 , SWITCH_PORTS + 1 ):
					'''
					if state == 0:
						match = parser.OFPMatch(in_port = in_port, state = state)
						actions = [ parser.OFPActionSetState(state = in_port, stage_id = 0) ]
						inst = [
							 parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							 parser.OFPInstructionWriteMetadata( metadata = 0, metadata_mask = 0xFFFFFFFF ),
							 parser.OFPInstructionGotoTable( table_id = 1 )	]
					else:
						match = parser.OFPMatch(in_port = in_port, state = state)
						actions = [ parser.OFPActionSetState(state = in_port, stage_id = 0) ]
						inst = [
							 parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							 parser.OFPInstructionWriteMetadata( metadata = state, metadata_mask = 0xFFFFFFFF ),
							 parser.OFPInstructionGotoTable( table_id = 1 )	]

					'''
					
					match = parser.OFPMatch(in_port = in_port, state = state)
					actions = [ parser.OFPActionSetState(state = in_port, stage_id = 0) ]
					inst = [
						 parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
						 parser.OFPInstructionWriteMetadata( metadata = state, metadata_mask = 0xFFFFFFFF ),
						 parser.OFPInstructionGotoTable( table_id = 1 )	]

					#flow mod code
				        mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)
					
					datapath.send_msg(mod)

		#TABLE 1
		#The state tab 1 is a utility table. It:	
		#	handles a special flood:
		#		 ordinary output on non transport ports, and output with 2 mpls label on the transport port
		#
		#	processes incoming flows from the transport port
		#		they need the outmost mpls label to be popped.
		#		Incoming packets from the transport_port have 2 mpls_label:
		#			Outmost mpls contains MY_ID or 0 (when the packet has been flooded from other switches)
		#			Innermost mpls label is EDGE_SWITCH_ID (which is always != 0 and can't equal the local value my_id)
		#
		#	METADATA == STATE1 delivered from tab0
		LOG.info("Installing rules for State Table 1, switch: %d" % my_id)
		
		for in_port in range( 1, SWITCH_PORTS + 1):	
			LOG.info("Installing rule for port %d (switch %d)" % (in_port, my_id))
			in_port_is_edge = self.in_list( list_ = EDGE_PORTS, value = in_port )	#check whether in_port is an edge port or not
			if in_port_is_edge:
				#cycle on the stateOne
					#if stateOne == 0 --> special_flood
					#else if stateOne == TRANSPORT_PORT --> add mpls_label(my_id) and goto tab 2 with metadata == TRANSPORT
				for stateOne in range(0, SWITCH_PORTS+1):
					if stateOne == 0:
						match = parser.OFPMatch(in_port = in_port, metadata = stateOne)
						actions = []
						#the following lines are for the special flood
						for out_port in range(1,SWITCH_PORTS+1):
							if in_port != out_port and out_port != TRANSPORT_PORT:
								actions.append(parser.OFPActionOutput(out_port, 0))
						
						actions.append(parser.OFPActionPushMpls(ethertype = 34887))
						#end of special flood lines

						inst = [ parser.OFPInstructionActions(type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							 parser.OFPInstructionWriteMetadata(metadata = 0, metadata_mask = 0xFFFFFFFF),
							 parser.OFPInstructionGotoTable(table_id = 2)]

					elif stateOne == TRANSPORT_PORT:
						match = parser.OFPMatch(in_port = in_port, metadata = stateOne)
						actions = [parser.OFPActionPushMpls( ethertype = 34887)]
						inst = [	
								parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
								parser.OFPInstructionWriteMetadata( metadata = TRANSPORT_PORT, metadata_mask = 0xFFFFFFFF),
								parser.OFPInstructionGotoTable( table_id = 2) ]
					#flow mod code

				        mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=1,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)
					
					datapath.send_msg(mod)

			else:	#in_port == TRANSPORT_PORT
				#cycle on the stateOne
					#if stateOne == 0 --> pop mpls_label and goto tab2 with metadata == 0
					#else --> pop mpls_label and goto tab2 with metadata == stateOne
				'''
				for stateOne in range(0,SWITCH_PORTS+1):
					if stateOne == 0:
						match = parser.OFPMatch( in_port = TRANSPORT_PORT, metadata = stateOne)
						actions = [parser.OFPActionPopMpls( ethertype = ....)]
						inst = [
								parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
								parser.OFPInstructionWriteMetadata(metadata = 0, metadata_mask = 0xFFFFFFFF),
								parser.OFPInstructionGotoTable( table_id = 2)]
				
					else:
						match = parser.OFPMatch( in_port = TRANSPORT_PORT, metadata = stateOne)
						actions = [parser.OFPActionPopMpls()]
						inst = [
								parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
								parser.OFPInstructionWriteMetadata(metadata = stateOne, metadata_mask = 0xFFFFFFFF),
								parser.OFPInstructionGotoTable( table_id = 2)]
				'''
				for stateOne in range(0,SWITCH_PORTS+1):
					
					match = parser.OFPMatch( in_port = TRANSPORT_PORT, metadata = stateOne)
					actions = [parser.OFPActionPopMpls( ethertype = 34887)]	#this mpls_label is useless, because it contains 0 or my_id
					inst = [
							parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							parser.OFPInstructionWriteMetadata( metadata = stateOne, metadata_mask = 0xFFFFFFFF),
							parser.OFPInstructionGotoTable( table_id = 3)]

					#flow mod code
				        mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=1,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)
					
					datapath.send_msg(mod)
		
		#The following n table are utility tables to push and set mpls labels
		
		#TABLE 2
		#	Table 2 allows the first mpls label to be set with my_id (the switch id)
		#	A new mpls label is pushed then
		LOG.info("Installing rules for table 2, switch: %d"  % my_id)
		for in_port in range(1,SWITCH_PORTS + 1):
			#This table can be reached only from the tab1 when in_port is edge and metadata equals 0
			for stateOne in range(0, SWITCH_PORTS+1):
				if stateOne == 0:
					match = parser.OFPMatch(in_port = in_port, metadata = 0, eth_type = 34887, mpls_label = 0)
					actions = [
							parser.OFPActionSetField(mpls_label = my_id),
							parser.OFPActionPushMpls(ethertype = 34887 ),
							parser.OFPActionOutput( TRANSPORT_PORT, 0)
						   ]
					inst = [
							parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions)
						]
	
					#flow mod code
					mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=2,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)
					
					datapath.send_msg(mod)
				
				elif stateOne == TRANSPORT_PORT:
					match = parser.OFPMatch( in_port = in_port, metadata = TRANSPORT_PORT, eth_type = 34887) 
					actions = [
							parser.OFPActionSetField(mpls_label = my_id),
							parser.OFPActionPushMpls(ethertype = 34887 )
						   ]

					inst = [
							parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions),
							parser.OFPInstructionWriteMetadata( metadata = TRANSPORT_PORT,  metadata_mask = 0xFFFFFFFF),
							parser.OFPInstructionGotoTable( table_id = 3)
						]

					#flow mod code			
					mod = parser.OFPFlowMod(
					   datapath=datapath, cookie=0, cookie_mask=0, table_id=2,
					   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
					   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
					   out_port=ofproto.OFPP_ANY,
					   out_group=ofproto.OFPG_ANY,
					   flags=0, match=match, instructions=inst)
					
					datapath.send_msg(mod)
				

		#TABLE 3
		#The state tab 3 handles the second state associated to the host:	
		#	STATE2 == EGRESS_SWITCH_ID this is the id of the egress switch where the host speaks from
		#		Only hosts outside the switch have the second state
		#		State 2 is taken from the innermost mpls_label of flows that comes from outside (in_port == TRANSPORT_PORT)
		#	METADATA == STATE1 delivered from tab1
		LOG.info("Installing rules for State Table 2 for the switch number %d" % my_id)
		
		for in_port in range( 1, SWITCH_PORTS + 1):	
			LOG.info("Installing rule for port %d (switch %d)" % (in_port, my_id))
			in_port_is_edge = self.in_list( list_ = EDGE_PORTS, value = in_port )	#check whether in_port is an edge port or not
			if in_port_is_edge:
				#cycle on the stateOne
					#cycle on yourId
						#if stateOne == TRANSPORT_PORT --> set_mpls(your_id) and out(TRANSPORT_PORT)
				for your_id in range( 1, EDGE_SWITCHES):
					if your_id != my_id:
						match = parser.OFPMatch( in_port = in_port, metadata = TRANSPORT_PORT, eth_type = 34887, mpls_label = my_id, state = your_id) 
						actions = [
								parser.OFPActionSetField( mpls_label = your_id),
								parser.OFPActionOutput( TRANSPORT_PORT, 0)]
						inst = [
								parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions)]
				
						#flow mod
						mod = parser.OFPFlowMod(
						   datapath=datapath, cookie=0, cookie_mask=0, table_id=3,
						   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
						   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
						   out_port=ofproto.OFPP_ANY,
						   out_group=ofproto.OFPG_ANY,
						   flags=0, match=match, instructions=inst)
						
						datapath.send_msg(mod)
					
			else:
				#cycle on the stateOne
					#cycle on yourId
						#if stateOne == 0 --> set_state(your_id) and pop mpls_label and FLOOD
						#else --> set_state(your_id) and pop mpls_label and out(stateOne)
				for stateOne in range( 0, SWITCH_PORTS + 1):
					if stateOne == 0:
						for your_id in range(1, EDGE_SWITCHES + 1):
							if your_id != my_id:
								match = parser.OFPMatch( in_port = in_port, metadata = 0, eth_type = 34887, mpls_label = your_id)
								actions = [
										parser.OFPActionSetState( state = your_id, stage_id = 3),
										parser.OFPActionPopMpls( ethertype = 2048 ),
										parser.OFPActionOutput( ofproto.OFPP_FLOOD, 0)
									  ]
								inst = [ parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions)]

								#flow mod code
								mod = parser.OFPFlowMod(
								   datapath=datapath, cookie=0, cookie_mask=0, table_id=3,
								   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
								   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
								   out_port=ofproto.OFPP_ANY,
								   out_group=ofproto.OFPG_ANY,
								   flags=0, match=match, instructions=inst)
								
								datapath.send_msg(mod)

					else:	#stateOne != 0 and stateOne != TRANSPORT_PORT
						for your_id in range(1, EDGE_SWITCHES + 1):
							if your_id != my_id:
								match = parser.OFPMatch( in_port = in_port, metadata = stateOne, eth_type = 34887, mpls_label = your_id)
								actions = [
										parser.OFPActionSetState( state = your_id, stage_id = 3),
										parser.OFPActionPopMpls( ethertype = 2048 ),
										parser.OFPActionOutput( stateOne, 0)
									  ]
								inst = [ parser.OFPInstructionActions( type_ = ofproto.OFPIT_APPLY_ACTIONS, actions = actions)]

								#flow mod code
								mod = parser.OFPFlowMod(
								   datapath=datapath, cookie=0, cookie_mask=0, table_id=3,
								   command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
								   priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
								   out_port=ofproto.OFPP_ANY,
								   out_group=ofproto.OFPG_ANY,
								   flags=0, match=match, instructions=inst)
								
								datapath.send_msg(mod)
								
    def send_table_mod(self, datapath, table_id):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPTableMod(datapath, table_id, ofp.OFPTC_TABLE_STATEFUL)
        datapath.send_msg(req)

    def add_state_entry(self, datapath, table_id):
        ofproto = datapath.ofproto
        state = datapath.ofproto_parser.OFPStateEntry(
            datapath, ofproto.OFPSC_ADD_FLOW_STATE, 6, 4, [0,0,0,0,0,2],
            cookie=0, cookie_mask=0, table_id= table_id)
        datapath.send_msg(state)

    def send_features_request(self, datapath):
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPFeaturesRequest(datapath)
        datapath.send_msg(req)

    def send_key_lookup(self, datapath):
        ofp = datapath.ofproto

        key_lookup_extractor = datapath.ofproto_parser.OFPKeyExtract(
            datapath, ofp.OFPSC_SET_L_EXTRACTOR, 1, [ofp.OXM_OF_ETH_DST])
        datapath.send_msg(key_lookup_extractor)

    def send_key_update(self, datapath):
        ofp = datapath.ofproto

        key_update_extractor = datapath.ofproto_parser.OFPKeyExtract(
            datapath, ofp.OFPSC_SET_U_EXTRACTOR, 1, [ofp.OXM_OF_ETH_SRC])
        datapath.send_msg(key_update_extractor)

    #Questa funzione ritorna true se il parametro value si trova nella lista list_
    def in_list(self, list_, value):
	for i in range(0,len(list_)):
		if list_[i]==value:
			return True
	return False
