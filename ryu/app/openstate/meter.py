
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
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER,HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology import event



class SimpleSwitch12(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch12, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
	print "here is my initialization\n"


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

	msg=ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto

 	self.send_features_request(datapath)
 	#self.send_table_mod(datapath)
        
        #self.send_meter_mod_drop(datapath) 
	self.send_meter_mod_dscp(datapath) 
        
        self.send_key_lookup(datapath)
	self.send_key_update(datapath)

# install table-miss flow entry (if no rule matched, send it to controller)
        self.add_flow(datapath,True)
#install the xfsm machine rules:
	self.add_flow(datapath)


#port considere in_port and state=metadata: matching headers are in_port + metadata
    def add_flow(self, datapath,table_miss=False):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        fw_servers=['10.0.0.1','10.0.0.2']

        print "here is my add flow\n"
        if table_miss:
            print "here is table miss\n"
	    actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,ofproto.OFPCML_NO_BUFFER)]
	    match = datapath.ofproto_parser.OFPMatch()
	    inst = [datapath.ofproto_parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS, actions)]
	    mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=0, buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0, match=match, instructions=inst)
        
	    datapath.send_msg(mod)

        else:
	    
            print "here is flow mod install rules for meter" 
            match = datapath.ofproto_parser.OFPMatch(eth_type=0x0806)
            actions = [datapath.ofproto_parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            inst=[datapath.ofproto_parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS,actions)]

	    mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=32760, buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0, match=match, instructions=inst)
        
	    datapath.send_msg(mod)
            
            match = datapath.ofproto_parser.OFPMatch(eth_type=0x0800,ipv4_dst='10.0.0.1')
            actions = [datapath.ofproto_parser.OFPActionOutput(1)]
            inst=[datapath.ofproto_parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS, actions)]

	    mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=32760, buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0, match=match, instructions=inst)
        
	    datapath.send_msg(mod)

            match = datapath.ofproto_parser.OFPMatch(eth_type=0x0800,ipv4_dst='10.0.0.2')
            actions = [datapath.ofproto_parser.OFPActionOutput(2)]
            inst=[datapath.ofproto_parser.OFPInstructionMeter(meter_id=1),datapath.ofproto_parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS,actions),parser.OFPInstructionGotoTable(1)]

	    mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, cookie=0, cookie_mask=0, table_id=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=32760, buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0, match=match, instructions=inst)
        
	    datapath.send_msg(mod)
           
            #I made sure that if there is not match in the table 0, flow checking rule in table 1 will not match never, needs a rule in table 0 to send the packet to the table 1.matching against dscp is funciotning. 
            match = datapath.ofproto_parser.OFPMatch(eth_type=0x0800,ip_dscp=48)
            #actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,ofproto.OFPCML_NO_BUFFER)]
            actions = [datapath.ofproto_parser.OFPActionOutput(3)]
            inst=[datapath.ofproto_parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS,actions)]

	    mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, cookie=0, cookie_mask=0, table_id=1,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=32760, buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0, match=match, instructions=inst)
        
	    datapath.send_msg(mod)
            
    def send_meter_mod_dscp(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
	#for meter_id in range (1,3):
        band = parser.OFPMeterBandDscpRemark(rate=10, burst_size=1, prec_level=2)
        req = parser.OFPMeterMod(datapath=datapath, command=ofproto.OFPMC_ADD,
                                 flags=ofproto.OFPMF_PKTPS,meter_id= 1,bands= [band])
        datapath.send_msg(req)


    def send_meter_mod_drop(self,datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        bands = ofp_parser.OFPMeterBandDrop(rate=1000, burst_size=1)
        req = ofp_parser.OFPMeterMod(datapath,ofp.OFPMC_ADD,ofp.OFPMF_KBPS,1,
                                  [bands])
        datapath.send_msg(req)       
    
    def send_table_mod(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
	print ofp.OFPTC_TABLE_STATEFULL
        req = ofp_parser.OFPTableMod(datapath,0, ofp.OFPTC_TABLE_STATEFULL)
        datapath.send_msg(req)

#in the normal condition every flow starts from default state, so no need to implement this fun at the moment
    def add_state_entry(self,datapath):
        ofproto = datapath.ofproto
	state=datapath.ofproto_parser.OFPStateEntry(datapath,ofproto.OFPSC_ADD_FLOW_STATE,3,1,[1,2,3],
			cookie=0, cookie_mask=0, table_id=0)
    
    def send_features_request(self, datapath):
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPFeaturesRequest(datapath)
        datapath.send_msg(req)

    def send_key_lookup(self,datapath):
        ofp=datapath.ofproto
	key_lookup_extractor=datapath.ofproto_parser.OFPKeyExtract(datapath,ofp.OFPSC_SET_L_EXTRACTOR,2,[ofp.OXM_OF_IPV4_SRC,ofp.OXM_OF_IPV4_DST],table_id=0)
	datapath.send_msg(key_lookup_extractor)
    
    def send_key_update(self,datapath):
        ofp=datapath.ofproto
	
	key_update_extractor=datapath.ofproto_parser.OFPKeyExtract(datapath,ofp.OFPSC_SET_U_EXTRACTOR,2,[ofp.OXM_OF_IPV4_SRC,ofp.OXM_OF_IPV4_DST],table_id=0)
	datapath.send_msg(key_update_extractor)
