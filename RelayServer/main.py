from find_airport import AirportFinder
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
# from langchain.schema import Document
from dotenv import load_dotenv
from openai import OpenAI
# from builtins import open
import zmq
import json
# import time
import numpy as np

MODEL_NAME = "gpt-4o"   # for model strings see: https://platform.openai.com/docs/models
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    # Your OpenAI API key needs to be saved as a system variable

MD_RAG_FILE_PATH = "./data/md_rag_files/"   # when adding new pdf files, make sure to run pdf2md.py file to generate markdown files. Does not work for scanned pdf without OCR. In this case, we recommend tools like Nougat, although the success might be limited

APT_FINDER = AirportFinder("./data/all_apts.csv", "./data/metars.csv")
NO_METAR_MSG = "No METAR available"

ECAM_COLORS = ["w", "g", "b", "a", "r"]
ECAM_FULL_COLORS = ["white", "green", "blue", "amber", "red"]
ECAM_LINES = [1, 2, 3, 4, 5, 6, 7]
ECAM_DREFS = [f"AirbusFBW/EWD{l}{c}Text" for l in ECAM_LINES for c in ECAM_COLORS]

FLIGHT_DREFS = ["sim/flightmodel/position/latitude",
                "sim/flightmodel/position/longitude",
                "sim/flightmodel/position/elevation",
                "sim/flightmodel/position/y_agl",
                "sim/flightmodel/position/mag_psi",
                "toliss_airbus/pfdoutputs/captain/pitch_angle",
                "toliss_airbus/pfdoutputs/captain/roll_angle",
                "sim/flightmodel/position/alpha",
                "sim/flightmodel/position/beta",
                "sim/flightmodel/position/indicated_airspeed",
                "sim/flightmodel/position/groundspeed",
                "sim/flightmodel/position/vh_ind_fpm",
                "AirbusFBW/fmod/eng/N1Array",
                "sim/flightmodel2/controls/flap1_deploy_ratio",
                "sim/flightmodel2/controls/flap2_deploy_ratio",
                "AirbusFBW/SlatPositionLWing", 
                "AirbusFBW/SlatPositionRWing",
                "AirbusFBW/RightGearInd",
                "AirbusFBW/LeftGearInd",
                "AirbusFBW/NoseGearInd",
                "sim/flightmodel2/gear/on_ground",  # array where [0] is nose gear, [1] is left gear, [2] is right gear
                "sim/flightmodel/weight/m_fuel_total", 
                "toliss_airbus/fuelTankContent_kgs", # array where [0] is center tank, [1] is left inner tank, [2] right inner tank, [3] is left tip tank, [4] is right tip tank
                "AirbusFBW/AP1Engage",
                "AirbusFBW/AP2Engage",
                "AirbusFBW/ATHRmode",   # >0 indicates that athr is activated    
                "sim/cockpit2/temperature/outside_air_temp_deg",
                "sim/cockpit2/gauges/indicators/wind_heading_deg_mag",
                "sim/cockpit2/gauges/indicators/wind_speed_kts",
                ]

CHAT_HISTORY = []

load_dotenv()

def setup_logging():
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    log_file = os.path.join(log_directory, f"{MODEL_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()

def load_markdown_documents(directory):
    documents = []
    for filename in os.listdir(directory):
        if filename.endswith('.md'):
            file_path = os.path.join(directory, filename)
            loader = TextLoader(file_path)
            documents.extend(loader.load())
            logger.info(f"Loaded {len(documents)} Markdown documents from {directory}")
    return documents

def split_documents(documents):
    text_splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)
    logger.info(f"Split documents into {len(chunks)} chunks")
    return chunks

def create_ensemble_retriever(chunks):
    try:
        # Create FAISS vector store
        embeddings = OpenAIEmbeddings()
        vector_store = FAISS.from_documents(chunks, embeddings)
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": 5})

        # Create BM25 retriever
        bm25_retriever = BM25Retriever.from_documents(chunks)
        bm25_retriever.k = 5

        # Create ensemble retriever
        ensemble_retriever = EnsembleRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            weights=[0.5, 0.5]
        )
        
        logger.info("Created ensemble retriever")
        return ensemble_retriever
    except ImportError as e:
        logger.error(f"Import error: {str(e)}. Make sure all required packages are installed.")
        raise
    except Exception as e:
        logger.error(f"Error creating ensemble retriever: {str(e)}")
        raise

def setup_gpt_client():
    logger.info("Setting up OpenAI client")
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client set up successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to set up OpenAI client: {str(e)}")
        raise

def generate_gpt_response(client, context, question, history):
    messages = [
        {"role": "system", "content": "You are a pilot assistant to help the pilots of an Airbus A320 in stressful abnormal situations. Therefore, it is important that you provide concise and only immediateley relevant information to the pilots. Your primary source of information should be the provided markdown documents. However, you can also use additional information you have about aviation, if you deem it necessary. If the context doesn't contain relevant information, say so."},
        *history,
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ]
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        response = completion.choices[0].message.content
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "I apologize, but I encountered an error while generating the response. Please try asking a simpler question or rephrasing your query."

def shorten_gpt_response(client, long_response):
    messages = [
        {"role": "system", "content": "You are a pilot assistant to help the pilots of an Airbus A320 in stressful abnormal situations. Therefore, it is important that you provide concise and only immediately relevant information to the pilots. You are provided with the verbose output of another model and your goal is to shorten this output as much as possible while keeping original structure in place. Keep in mind that you are producing output for trained A320 pilots. If the verbose text contains justifications for recommendations, make sure to include those justifications. You can shorten the language to the extent where your output does not include full sentences, but you cannot compromise on important content."},
        {"role": "user", "content": f"Verbos Response: {long_response}"}
    ]
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        response = completion.choices[0].message.content
        # logger.info(f"Generated response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "I apologize, but I encountered an error while generating the response. Please try asking a simpler question or rephrasing your query."
    

def format_ecam_message(ecam_data):
    left_ecam_msgs = []
    right_ecam_msgs = []
    
    for l in ECAM_LINES:
        left_msg = None
        right_msg = None
        padded_colored_messages = []
        for c in ECAM_COLORS:
            padded_colored_messages.append(ecam_data[f"AirbusFBW/EWD{l}{c}Text"].ljust(48))
        
        #split in left and right
        left_padded_colored_messages = [pcm[:24] for pcm in padded_colored_messages]
        right_padded_colored_messages = [pcm[24:] for pcm in padded_colored_messages]
        
        for i,c in enumerate(ECAM_FULL_COLORS):   #invert the priority
            if sum(1 for char in left_padded_colored_messages[i] if char != ' ') > 0:
                left_msg = left_padded_colored_messages[i].rstrip().upper() + f" ({c})"
            if sum(1 for char in right_padded_colored_messages[i] if char != ' ') > 0:    
                right_msg = right_padded_colored_messages[i].rstrip().upper() + f" ({c})"
        
        if left_msg is not None:
            left_ecam_msgs.append(left_msg)
        if right_msg is not None:
            right_ecam_msgs.append(right_msg)
    
    # build final ECAM messges
    final_ecam_msg = '\n'.join(left_ecam_msgs+right_ecam_msgs)
    
    return final_ecam_msg

def format_flight_data(flight_data):
    fligh_data_msgs = []
    
    def ldg_pos_str(ldg_ind):
        if ldg_ind == 0:
            pos = "Up"
        elif ldg_ind == 1:
            pos = "Changing"
        elif ldg_ind == 2:
            pos = "Down"
        elif ldg_ind == 3:
            pos = "Changing"
        else:
            pos = "Unknown"
            
        return pos
        
    fligh_data_msgs.append(f"Latitude: {flight_data['sim/flightmodel/position/latitude']:.6f} deg")
    fligh_data_msgs.append(f"Longitude: {flight_data['sim/flightmodel/position/longitude']:.6f} deg")
    fligh_data_msgs.append(f"Altitde MSL: {int(flight_data['sim/flightmodel/position/elevation'] * 3.28084)} ft")
    fligh_data_msgs.append(f"Altitde AGL: {int(flight_data['sim/flightmodel/position/y_agl'] * 3.28084)} ft")
    fligh_data_msgs.append(f"Magnetic Heading: {flight_data['sim/flightmodel/position/mag_psi']:.1f} deg")
    fligh_data_msgs.append(f"Pitch Angle: {flight_data['toliss_airbus/pfdoutputs/captain/pitch_angle']:.1f} deg")
    fligh_data_msgs.append(f"Roll Angle: {flight_data['toliss_airbus/pfdoutputs/captain/roll_angle']:.1f} deg")
    fligh_data_msgs.append(f"Angle of Attack: {flight_data['sim/flightmodel/position/alpha']:.1f} deg")
    fligh_data_msgs.append(f"Sideslip Angle: {flight_data['sim/flightmodel/position/beta']:.1f} deg")
    fligh_data_msgs.append(f"Inidcated Airspeed: {flight_data['sim/flightmodel/position/indicated_airspeed']:.1f} kt")
    fligh_data_msgs.append(f"Groundspeed: {flight_data['sim/flightmodel/position/groundspeed'] * 1.94384:.1f} kt")
    fligh_data_msgs.append(f"Vertical Speed: {int(flight_data['sim/flightmodel/position/vh_ind_fpm'])} ft/min")
    fligh_data_msgs.append(f"Left N1: {flight_data['AirbusFBW/fmod/eng/N1Array'][0]:.1f}%")
    fligh_data_msgs.append(f"Right N1: {flight_data['AirbusFBW/fmod/eng/N1Array'][1]:.1f}%")
    fligh_data_msgs.append(f"Left Flaps Deployment: {flight_data['sim/flightmodel2/controls/flap1_deploy_ratio']*100:.1f}%")
    fligh_data_msgs.append(f"Right Flaps Deployment: {flight_data['sim/flightmodel2/controls/flap2_deploy_ratio']*100:.1f}%")
    fligh_data_msgs.append(f"Left Slats Deployment: {flight_data['AirbusFBW/SlatPositionLWing']*100/27:.1f}%")  # originally in deg
    fligh_data_msgs.append(f"Right Slats Deployment: {flight_data['AirbusFBW/SlatPositionRWing']*100/27:.1f}%") 
    fligh_data_msgs.append(f"Left Landing Gear Position: {ldg_pos_str(flight_data['AirbusFBW/LeftGearInd'])}")
    fligh_data_msgs.append(f"Right Landing Gear Position: {ldg_pos_str(flight_data['AirbusFBW/RightGearInd'])}")
    fligh_data_msgs.append(f"Nose Landing Gear Position: {ldg_pos_str(flight_data['AirbusFBW/NoseGearInd'])}")
    fligh_data_msgs.append(f"Wheels Ground Contact: {bool(np.any(flight_data['sim/flightmodel2/gear/on_ground']))}")
    fligh_data_msgs.append(f"Estimated Fuel on Board: {int(flight_data['sim/flightmodel/weight/m_fuel_total'])} kg")
    fligh_data_msgs.append(f"Fuel Mass Center Tank: {int(flight_data['toliss_airbus/fuelTankContent_kgs'][0])} kg (max capcity: 6500kg)")
    fligh_data_msgs.append(f"Fuel Mass Main Wing Tanks: Left: {int(flight_data['toliss_airbus/fuelTankContent_kgs'][1])} kg, Right: {int(flight_data['toliss_airbus/fuelTankContent_kgs'][2])} kg (max capacity per side: 5400 kg)")
    fligh_data_msgs.append(f"Fuel Mass Tip Tank: Left: {int(flight_data['toliss_airbus/fuelTankContent_kgs'][3])} kg,  Right: {int(flight_data['toliss_airbus/fuelTankContent_kgs'][4])} kg (max capacity per side: 680 kg)")
    fligh_data_msgs.append(f"Auto Pilot 1 Active: {bool(flight_data['AirbusFBW/AP1Engage'])}")
    fligh_data_msgs.append(f"Auto Pilot 2 Active: {bool(flight_data['AirbusFBW/AP2Engage'])}")
    fligh_data_msgs.append(f"Auto Throttle Active: {flight_data['AirbusFBW/ATHRmode'] > 0}") 
    fligh_data_msgs.append(f"Outside Air Temperature: {int(flight_data['sim/cockpit2/temperature/outside_air_temp_deg'])} C")
    fligh_data_msgs.append(f"Wind Direction and Speed: {int(flight_data['sim/cockpit2/gauges/indicators/wind_heading_deg_mag'])}/{int(flight_data['sim/cockpit2/gauges/indicators/wind_speed_kts'])} ")
    
    final_flight_data_msg = '\n'.join(fligh_data_msgs)
    
    return final_flight_data_msg

def format_alternate_airports(flight_data):
    latitude = flight_data['sim/flightmodel/position/latitude']
    longitude = flight_data['sim/flightmodel/position/longitude']
    
    closest_airports = APT_FINDER.get_closest_airports(latitude, longitude)
    
    altn_apts_message = []
    
    for apt in closest_airports:
        metar_msg = apt['METAR'] if isinstance(apt['METAR'],str) else NO_METAR_MSG
        altn_apts_message.append(f"Airport: {apt['ICAO']}, Distance: {apt['Distance']*0.539957:.1f} NM, Maximum Runway Length: {int(apt['MaxRunwayLength'])} ft, METAR: {metar_msg}")
    
    altn_apts_message = "\n".join(altn_apts_message)
    
    return altn_apts_message
            
        
def format_prompt(data):
    ecam_data = {dr:data[dr] for dr in ECAM_DREFS}
    flight_data = {dr:data[dr] for dr in FLIGHT_DREFS}
    
    formatted_ecam_message = format_ecam_message(ecam_data)
    formatted_flight_data_message = format_flight_data(flight_data)
    formatted_altn_apts_message = format_alternate_airports(flight_data)


    prompt = f"""Given the following flight data and ECAM messages for an A320, what are the immediate next steps a pilot should take given the situation. If the airplane is in a dangerous state, the primary goal is to recover the aircraft as quickly. If the aircraft is not in a dangerous state, you should acknowledge this to avoid false positive alarms and stressing pilots unnecessarily. This also means you should not display flight data that is already displayed in the cockpit unless it is relevant for a failure. Use the provided flight data and ECAM messages to determine if the airplane is in a dangerous state. You should reason if there are any anomalies in the flight data. Be as concise as possible, but give justifications for your suggestions. If you discover an unsafe state, use the alternate airports list and take the METAR weather reports at those airports into consideration for giving a recommendation to which airport to deviate to. If there are multiple airports that are suitable, rank them and provide justifications. If no diversion is necessary, do not list alternate airports. Under no circumstances should you hallucinate. If you are uncertain, you should state this. The relevant sections of the Quick Reference Handbook and Flight Crew Training Manual are given to you in the context.

Flight data:
{formatted_flight_data_message}

ECAM messages:
{formatted_ecam_message}

Alternate Airports:
{formatted_altn_apts_message}
"""
    print("-"*80)
    print("Prompt:")
    print(prompt)
    return prompt


def format_retrieval_prompt(data):
    if data["trigger_source"] == "text_entry":
        prompt = f"""Given the following (follow up) question from the pilot, what are important considerations?
        
{data["message"]}"""
    
    else:
        ecam_data = {dr:data[dr] for dr in ECAM_DREFS}
        
        formatted_ecam_message = format_ecam_message(ecam_data)


        prompt = f"""Given the following ECAM messages, what are important considerations?

{formatted_ecam_message}"""

    return prompt

def format_flight_health_prompt(data):
    flight_data = {dr:data[dr] for dr in FLIGHT_DREFS}
    
    formatted_flight_data_message = format_flight_data(flight_data)
    
    prompt = f"""Given the following flight data for an A320, do you detect any anomalies that would warrent an intervention. Justify your answers and be as concise as possible. Under no circumstances hallucinate. If you are not sure, state so.

Flight data:
{formatted_flight_data_message}
"""
    print("-"*80)
    print("Flight Data Prompt:")
    print(prompt)
    return prompt

def format_prompt_text_entry(data):
    return data["message"]
    

def main():
    logger.info("Starting main function")
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.RCVBUF, 10 * 1024 * 1024)  # Set receive buffer to 10 MB
    socket.setsockopt(zmq.SNDBUF, 10 * 1024 * 1024)  # Set send buffer to 10 MB
    socket.bind("tcp://*:5555")
    
    global CHAT_HISTORY
    
    documents = load_markdown_documents(MD_RAG_FILE_PATH)
    if not documents:
        logger.warning(f"No Markdown documents found in the '{MD_RAG_FILE_PATH}' directory.")
        print(f"No Markdown documents found. Please add .md files to the '{MD_RAG_FILE_PATH}' directory and try again.")
        return

    chunks = split_documents(documents)
    retriever = create_ensemble_retriever(chunks)
    
    client = setup_gpt_client()
    

    while True:
        #  Wait for next request from client
        message = socket.recv()
        payload = json.loads(message.decode())
        print("----------------------MESSAGE RECEIVED----------------------")
        print("-"*80)
        print(payload)
        print("-"*80)
        
        if payload["trigger_source"] == "arm":
            CHAT_HISTORY = []
            socket.send("ok".encode('utf-8'))

        else:
            retrieval_prompt = format_retrieval_prompt(payload)            
            relevant_docs = retriever.get_relevant_documents(retrieval_prompt)
            context = "\n".join([doc.page_content for doc in relevant_docs])
            
            # Print the context used
            print("\nContext used:")
            print(context)
            print("\n" + "-"*50 + "\n")
            

            if payload["trigger_source"] == "text_entry":
                prompt = format_prompt_text_entry(payload)
                response = generate_gpt_response(client, context, prompt, CHAT_HISTORY)
                CHAT_HISTORY.append({"role":"user", "content":payload["message"]})  # add to history after to avoid double use
                shortened_response = shorten_gpt_response(client, response)
                CHAT_HISTORY.append({"role":"assistant", "content": shortened_response})
            
            else:
                prompt = format_prompt(payload)
                CHAT_HISTORY = []   # this is triggerd through Query button or Master Warn/Caution, so we want to erase everything
                response = generate_gpt_response(client, context, prompt, CHAT_HISTORY)
                CHAT_HISTORY = [{"role":"user", "content":prompt},]     
                shortened_response = shorten_gpt_response(client, response)
                CHAT_HISTORY.append({"role":"assistant", "content": shortened_response})
            
            print(f"\nQuestion: {prompt}")
            print(f"\nLong Answer: {response}")
            print("-"*80)
            print(f"\nShort Answer: {shortened_response}")


            #  Send reply back to client
            socket.send(shortened_response.encode('utf-8'))

    
if __name__ == "__main__":
    main()
