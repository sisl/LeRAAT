# This file needs to be copied to /path/to/X-plane/Resources/plugins/PythonPlugins
# It is necessary that XPPython3 is successfully installed before copying the file, in addition make sure that zmq is installed for the Python environment in X-Plane (see README.md)
# It is required by XPPython for plugins to follow the naming convention PI_SOME_NAME.py, otherwise they will not be recognized

import os
from XPPython3 import xp
from XPPython3 import xp_imgui # type: ignore
import imgui  # type: ignore
import imgui.integrations.opengl as gl
import threading
import time
import zmq
import json
import re

# need a dummy function for retrieving arrays
def getvf(dr):
    values = []
    xp.getDatavf(dr,values)
    return values

# need a dummy function for retrieving arrays
def getvi(dr):
    values = []
    xp.getDatavi(dr,values)
    return values

ECAM_COLORS = ["w", "g", "b", "a", "r"]
ECAM_LINES = [1, 2, 3, 4, 5, 6, 7]
ECAM_DREFS = [f"AirbusFBW/EWD{l}{c}Text" for l in ECAM_LINES for c in ECAM_COLORS]

FLIGHT_DREFS = [("sim/flightmodel/position/latitude",xp.getDataf),
                ("sim/flightmodel/position/longitude",xp.getDataf),
                ("sim/flightmodel/position/elevation",xp.getDataf),
                ("sim/flightmodel/position/y_agl",xp.getDataf),
                ("sim/flightmodel/position/mag_psi",xp.getDataf),
                ("toliss_airbus/pfdoutputs/captain/pitch_angle",xp.getDataf),
                ("toliss_airbus/pfdoutputs/captain/roll_angle",xp.getDataf),
                ("sim/flightmodel/position/alpha",xp.getDataf),
                ("sim/flightmodel/position/beta",xp.getDataf),
                ("sim/flightmodel/position/indicated_airspeed",xp.getDataf),
                ("sim/flightmodel/position/groundspeed",xp.getDataf),
                ("sim/flightmodel/position/vh_ind_fpm",xp.getDataf),
                ("AirbusFBW/fmod/eng/N1Array", getvf),  # array of N1
                ("sim/flightmodel2/controls/flap1_deploy_ratio",xp.getDataf),
                ("sim/flightmodel2/controls/flap2_deploy_ratio",xp.getDataf),
                ("AirbusFBW/SlatPositionLWing",xp.getDataf), 
                ("AirbusFBW/SlatPositionRWing",xp.getDataf),
                ("AirbusFBW/RightGearInd",xp.getDatai),
                ("AirbusFBW/LeftGearInd",xp.getDatai),
                ("AirbusFBW/NoseGearInd",xp.getDatai),
                ("sim/flightmodel2/gear/on_ground",getvi),  # array where [0] is nose gear, [1] is left gear, [2] is right gear
                ("sim/flightmodel/weight/m_fuel_total",xp.getDataf), 
                ("toliss_airbus/fuelTankContent_kgs",getvf), # array where [0] is center tank, [1] is left inner tank, [2] right inner tank, [3] is left tip tank, [4] is right tip tank
                ("AirbusFBW/AP1Engage",xp.getDatai),
                ("AirbusFBW/AP2Engage",xp.getDatai),
                ("AirbusFBW/ATHRmode",xp.getDatai),   # >0 indicates that athr is activated    
                ("sim/cockpit2/temperature/outside_air_temp_deg",xp.getDataf),
                ("sim/cockpit2/gauges/indicators/wind_heading_deg_mag",xp.getDataf),
                ("sim/cockpit2/gauges/indicators/wind_speed_kts",xp.getDataf),
                ]

SERVER_URI = "127.0.0.1:5555"

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVBUF, 10 * 1024 * 1024)  # Set receive buffer to 10 MB
socket.setsockopt(zmq.SNDBUF, 10 * 1024 * 1024)  # Set send buffer to 10 MB
socket.connect(f"tcp://{SERVER_URI}")

class PythonInterface:
    def __init__(self):
        self.windowNumber = 0  # Number we increment, just to "know" which window I've just created
        self.imgui_windows = {}  # {'xp_imgui.Window' instances}
        self.cmd = None
        self.cmdRef = []
        self.llm_text_pages = ["",]
        self.curr_page = 0
        self.llm_text = self.llm_text_pages[self.curr_page]
        self.text_all_pages = ""
        self.no_pages = len(self.llm_text_pages)
        self.state = "Armed"    # state is either "Armed" or "Active"
        self.master_caut = False    # initialize master warning observation
        self.master_warn = False    # initialize master caution observation
        self.window_height = None
        self.window_width = None
        self.raw_llm_response = None
        self.font_path = './Resources/fonts/tahomabd.ttf'   # this is relative to the X-Plane home directory
        self.font_size = 20
        self.text_box_entry = ""
        
               
        threading.Thread(target=self.listen).start()
        # asyncio.create_task(self.listen_warn_caut())
    
    
        
    def XPluginStart(self):
        # Create command and attach to Menu, to create a new IMGUI window
        self.cmd = xp.createCommand(f"xpppython3/{os.path.basename(__file__)}/createWindow",
                                    "Create IMGUI window")
        xp.registerCommandHandler(self.cmd, self.commandHandler, 1, self.cmdRef)
        xp.appendMenuItemWithCommand(xp.findPluginsMenu(), 'A320 LLM', self.cmd)

        return 'A320 LLM v1.0', 'xppython3.imgui_test', 'An LLM Interface for an Airbus A320'

    def XPluginEnable(self):
        return 1
  
    def XPluginStop(self):
        # unregister command and clean up menu
        xp.unregisterCommandHandler(self.cmd, self.commandHandler, 1, self.cmdRef)
        xp.clearAllMenuItems(xp.findPluginsMenu())
  
    def XPluginDisable(self):
        # delete any imgui_windows, clear the structure
        for x in list(self.imgui_windows):
            self.imgui_windows[x]['instance'].delete()
            del self.imgui_windows[x]
  
    def commandHandler(self, cmdRef, phase, refCon):
        if phase == xp.CommandBegin:
            # For fun, we'll create a NEW window each time the command is invoked.
            self.createWindow(f'A320 LLM ({self.windowNumber})')
            self.windowNumber += 1
        return 1
  
    def createWindow(self, title):
        self.imgui_windows[title] = {'instance': None,
                                     'title': title,}
  
        l, t, r, b = xp.getScreenBoundsGlobal()
        width = 600
        height = 600
        left_offset = 110
        top_offset = 110
  
        # Create the imgui Window, and save it.
        self.imgui_windows[title].update({
            'instance': xp_imgui.Window(left=l + left_offset,
                                        top=t - top_offset,
                                        right=l + left_offset + width,
                                        bottom=t - (top_offset + height),
                                        visible=1,
                                        draw=self.drawWindow,
                                        refCon=self.imgui_windows[title])})
  
        # and (optionally) set the title of the created window using .setTitle()
        self.imgui_windows[title]['instance'].setTitle(title)
        xp.setWindowPositioningMode(self.imgui_windows[title]['instance'].windowID, xp.WindowVR)
        
        # load font
        io = imgui.get_io()
        self.font = io.fonts.add_font_from_file_ttf(
            self.font_path, self.font_size)
        self.imgui_windows[title]['instance'].renderer.refresh_font_texture()

        return
    
    def listen(self,):
        dataRef_WARN = xp.findDataRef('AirbusFBW/MasterWarn')
        dataRef_CAUT = xp.findDataRef('AirbusFBW/MasterCaut')
        
        while True:
            time.sleep(0.5)
            self.master_warn = xp.getDatai(dataRef_WARN)
            self.master_caut = xp.getDatai(dataRef_CAUT)
            
            # if (self.master_warn or self.master_caut) and self.state == "Armed":
                
            
    
    def paginate_text(self,text, wrap_width, page_height):
        words = text.split(' ')
        current_page = []
        pages = []
        current_text = ""
        # with imgui.font(self.font):
            
        for word in words:
            # Try adding the next word
            test_text = current_text + (" " if current_text else "") + word
            
            text_size = imgui.calc_text_size(test_text, wrap_width=wrap_width)

            # Check if adding this word would exceed the page height
            if text_size[1] > page_height:
                # If it would exceed, finalize the current page and start a new one
                pages.append(" ".join(current_page))
                current_text = word
                current_page = [word]

            else:
                # Otherwise, add the word and continue
                current_page.append(word)
                current_text = test_text

        # Add any remaining text as the last page
        if current_page:
            pages.append(" ".join(current_page))

        return pages
    
    def process_llm_response(self,):
        if self.raw_llm_response is not None:    
            self.llm_text_pages = self.paginate_text(self.raw_llm_response, self.window_width, self.window_height*0.7)
            self.no_pages = len(self.llm_text_pages)
            self.curr_page = min(self.curr_page, self.no_pages-1)
            self.llm_text = self.llm_text_pages[self.curr_page]
            self.raw_llm_response = None
        
    def llm_call(self,):
        self.raw_llm_response = "Retrieving Response from LLM..."
        self.state = "Active"
        
        time.sleep(0.5) # ECAM messages show up with a small time delay sometimes
        
        ecam_drefs = [xp.findDataRef(dr) for dr in ECAM_DREFS]
        flight_drefs = [xp.findDataRef(dr[0]) for dr in FLIGHT_DREFS]
        # encode the master warning we got and send it along
        ecam_values = [xp.getDatas(edr) for edr in ecam_drefs]
        flight_values = [f[1](fdr) for fdr,f in zip(flight_drefs,FLIGHT_DREFS)]
        socket.send(json.dumps({
            "trigger_source": "alert" if (self.master_caut or self.master_warn) else "query",
            "master_warning": self.master_warn,
            "master_caution": self.master_caut,
        }|{dr:val for dr,val in zip(ECAM_DREFS, ecam_values)}|
                                {dr[0]:val for dr,val in zip(FLIGHT_DREFS, flight_values)}).encode('utf-8'))
        message = socket.recv().decode()
        message = re.sub(r'[^\x00-\x7F]+', ' ', message).replace("**","")

        self.text_all_pages = message
        self.raw_llm_response = self.text_all_pages

    def llm_call_follow_up(self,):
        msg = self.text_box_entry
        print(msg)
        # if self.raw_llm_response is None:
        self.text_all_pages = self.text_all_pages + f"\n\nQ: {msg}"
        self.raw_llm_response = self.text_all_pages 
        print(self.text_all_pages)
        # else:
        #     self.raw_llm_response += f"\n\nQ: {msg}"
            
        socket.send(json.dumps({
            "trigger_source": "text_entry",
            "message": msg,
        }).encode('utf-8'))
        self.text_box_entry = ""    # clear text box after submission
        message = socket.recv().decode()
        message = re.sub(r'[^\x00-\x7F]+', ' ', message).replace("**","")
        
        
        self.text_all_pages = self.text_all_pages + f"\n\nA: {message}"
        self.raw_llm_response = self.text_all_pages
        print(self.text_all_pages)
        
    def send_arm(self,):
        socket.send(json.dumps({"trigger_source": "arm"}).encode("utf-8"))
        _ = socket.recv().decode()  # need to receive a message or ZMQ is unhappy
    
    def check_master_warn_caut(self,):
        if (self.master_caut or self.master_warn) and self.state == "Armed":
            self.state = "Active"
            threading.Thread(target=self.llm_call).start()
            # asyncio.create_task(self.llm_call())
    
    def query(self,):
        self.state = "Active"
        self.text_all_pages = ""
        self.llm_text_pages = ["",]
        threading.Thread(target=self.llm_call).start()
        # asyncio.create_task(self.llm_call())
        
    def clear(self,):
        self.llm_text = ""
        self.llm_text_pages = ["",]
        self.text_box_entry = ""
        self.text_all_pages = ""
        self.curr_page = 0
        self.no_pages = len(self.llm_text_pages)
        self.state = "Armed"
        
        # send arm command to server
        threading.Thread(target=self.send_arm).start()
        
    
    def next_page(self,):
        if (self.curr_page + 1) < self.no_pages:
            self.curr_page += 1
            self.llm_text = self.llm_text_pages[self.curr_page]
        
    def prev_page(self,):
        if self.curr_page > 0:
            self.curr_page -= 1
            self.llm_text = self.llm_text_pages[self.curr_page] 
    
    def text_box_subm_button(self):
        self.state = "Interactive"
        threading.Thread(target=self.llm_call_follow_up).start()
    
    # this method is called every time the window is refreshed. No compute-heavy steps advised in here
    def drawWindow(self, windowID, refCon):     
        # self.font = self.imgui_windows['A320 LLM (0)']['instance'].renderer.new_font
        self.window_width = imgui.get_window_width()
        self.window_height = imgui.get_window_height()
        gap_width = 0.1 * self.window_width / 5
        button_width = 0.9 * self.window_width / 4
        button_height = button_width/3
        y_position = imgui.get_cursor_pos_y()
        
        # check the master warn/caut for each drawing cycle 
        self.check_master_warn_caut()
        
        with imgui.font(self.font):
            self.process_llm_response()
        
            imgui.set_cursor_pos((gap_width, y_position))
            if imgui.button("Query", button_width, button_height):
                self.query()
            imgui.set_cursor_pos((2 * gap_width + button_width, y_position))
            if imgui.button("Arm", button_width, button_height):
                self.clear()
            
            imgui.set_cursor_pos((3 * gap_width + 2* button_width, y_position))
            
            if self.curr_page == 0: # if at first page, there is no previous page
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.5, 0.5, 0.5, 1.0)  
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.5, 0.5, 0.5, 1.0)  
                imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.5, 0.5, 0.5, 1.0)
                
                if imgui.button("Prev", button_width, button_height):
                    self.prev_page()
                
                imgui.pop_style_color(3)
            
            else:
                if imgui.button("Prev", button_width, button_height):
                    self.prev_page()
                    
                    
            imgui.set_cursor_pos((4 * gap_width + 3* button_width, y_position))
            
            if (self.curr_page+1) >= self.no_pages: # we're at the last page
                imgui.push_style_color(imgui.COLOR_BUTTON, 0.5, 0.5, 0.5, 1.0)  
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.5, 0.5, 0.5, 1.0)  
                imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.5, 0.5, 0.5, 1.0)
                
                if imgui.button("Next", button_width, button_height):
                    self.next_page()
                    
                imgui.pop_style_color(3)
            
            else:
                if imgui.button("Next", button_width, button_height):
                    self.next_page()
                
                
            imgui.spacing()
            
            imgui.text_wrapped(self.llm_text)
            
            # text box entry
            imgui.set_cursor_pos((10,self.window_height-80))
            changed, self.text_box_entry = imgui.core.input_text_multiline("", self.text_box_entry, -1, width=0.8 * self.window_width, height = self.font_size+10)
            
            # text box button
            imgui.set_cursor_pos((0.8 * self.window_width + 20 ,self.window_height-80))
            if imgui.button("Submit", 0.2 * self.window_width - 30, self.font_size + 10):
                print(self.text_box_entry)
                self.text_box_subm_button()
            
            imgui.set_cursor_pos((30,self.window_height-40))
            if self.state == "Armed":
                imgui.text_colored(f"{self.state}",0.4,0.4,0.4)
            elif self.state == "Active":
                imgui.text_colored(f"{self.state}",0.4,1.0,0.4)
            elif self.state == "Interactive":
                imgui.text_colored(f"{self.state}",0.4,0.8,1.0)
                
            imgui.set_cursor_pos((self.window_width-100,self.window_height-40))
            imgui.text(f"Page {self.curr_page + 1}/{self.no_pages}")
        
        return
  
