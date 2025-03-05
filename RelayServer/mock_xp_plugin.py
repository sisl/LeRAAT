import zmq
import json

DATA = {'trigger_source': 'alert', 
        'master_warning': 1, 
        'master_caution': 0, 
        'AirbusFBW/EWD1wText': '', 
        'AirbusFBW/EWD1gText': '', 
        'AirbusFBW/EWD1bText': '', 
        'AirbusFBW/EWD1aText': '', 
        'AirbusFBW/EWD1rText': 'eng 2 FIRE              LAND ASAP', 
        'AirbusFBW/EWD2wText': '', 
        'AirbusFBW/EWD2gText': '', 
        'AirbusFBW/EWD2bText': ' -THR LEVER 2.......IDLE', 
        'AirbusFBW/EWD2aText': '', 
        'AirbusFBW/EWD2rText': '', 
        'AirbusFBW/EWD3wText': '', 
        'AirbusFBW/EWD3gText': '', 
        'AirbusFBW/EWD3bText': ' -ENG MASTER 2.......OFF', 
        'AirbusFBW/EWD3aText': '', 
        'AirbusFBW/EWD3rText': '', 
        'AirbusFBW/EWD4wText': '', 
        'AirbusFBW/EWD4gText': '', 
        'AirbusFBW/EWD4bText': ' -ENG FIRE P/B 2....PUSH', 
        'AirbusFBW/EWD4aText': '', 
        'AirbusFBW/EWD4rText': '', 
        'AirbusFBW/EWD5wText': '', 
        'AirbusFBW/EWD5gText': '', 
        'AirbusFBW/EWD5bText': ' -AGENT1 AFTER 10S.DISCH', 
        'AirbusFBW/EWD5aText': '', 
        'AirbusFBW/EWD5rText': '', 
        'AirbusFBW/EWD6wText': '', 
        'AirbusFBW/EWD6gText': '', 
        'AirbusFBW/EWD6bText': ' -ATC.............NOTIFY', 
        'AirbusFBW/EWD6aText': '', 
        'AirbusFBW/EWD6rText': '', 
        'AirbusFBW/EWD7wText': '', 
        'AirbusFBW/EWD7gText': '', 
        'AirbusFBW/EWD7bText': ' -AGENT 2..........DISCH', 
        'AirbusFBW/EWD7aText': '', 
        'AirbusFBW/EWD7rText': '', 
        'sim/flightmodel/position/latitude': 25.76130485534668, 
        'sim/flightmodel/position/longitude': -80.81539154052734, 
        'sim/flightmodel/position/elevation': 3536.704833984375, 
        'sim/flightmodel/position/y_agl': 3532.852294921875, 
        'sim/flightmodel/position/mag_psi': 260.4881286621094, 
        'toliss_airbus/pfdoutputs/captain/pitch_angle': 7.700178623199463, 
        'toliss_airbus/pfdoutputs/captain/roll_angle': 0.32229772210121155, 
        'sim/flightmodel/position/alpha': 2.012021541595459, 
        'sim/flightmodel/position/beta': -0.026648346334695816, 
        'sim/flightmodel/position/indicated_airspeed': 287.0511474609375, 
        'sim/flightmodel/position/groundspeed': 165.65615844726562, 
        'sim/flightmodel/position/vh_ind_fpm': 3176.704345703125, 
        'AirbusFBW/fmod/eng/N1Array': [85.15528869628906, 85.26714324951172, 0.0, 0.0], 
        'sim/flightmodel2/controls/flap1_deploy_ratio': 0.0, 
        'sim/flightmodel2/controls/flap2_deploy_ratio': 0.0, 
        'AirbusFBW/SlatPositionLWing': 0.0, 
        'AirbusFBW/SlatPositionRWing': 0.0, 
        'AirbusFBW/RightGearInd': 0, 
        'AirbusFBW/LeftGearInd': 0, 
        'AirbusFBW/NoseGearInd': 0, 
        'sim/flightmodel2/gear/on_ground': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 
        'sim/flightmodel/weight/m_fuel_total': 6299.2197265625, 
        'toliss_airbus/fuelTankContent_kgs': [0.0, 2471.313232421875, 2471.90625, 678.0, 678.0, 0.0, 0.0, 0.0, 0.0], 
        'AirbusFBW/AP1Engage': 1, 
        'AirbusFBW/AP2Engage': 0, 
        'AirbusFBW/ATHRmode': 2, 
        'sim/cockpit2/temperature/outside_air_temp_deg': -1.1136822700500488, 
        'sim/cockpit2/gauges/indicators/wind_heading_deg_mag': 269.8157653808594, 
        'sim/cockpit2/gauges/indicators/wind_speed_kts': 19.817636489868164}

# Example for an a textbox message
# DATA = {'trigger_source': 'text_entry', 'message': 'What should I do if there does not seem to be an engine fire?'}

# Example how to arm the system again
# DATA = {'trigger_source': 'arm'}


SERVER_URI = "127.0.0.1:5555"

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVBUF, 10 * 1024 * 1024)  # Set receive buffer to 10 MB
socket.setsockopt(zmq.SNDBUF, 10 * 1024 * 1024)  # Set send buffer to 10 MB
socket.connect(f"tcp://{SERVER_URI}")


socket.send(json.dumps(DATA).encode('utf-8'))
message = socket.recv().decode()

print(message)
