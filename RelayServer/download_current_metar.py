# This helper scripts downloads all current real-world METARs for commericial airports with at least one runway with a length >=8000ft.
# The resulting file is saved in ./metars.csv. Airports that do not have a METAR available will have an empty entry in the ./metars.csv

import pandas as pd
import requests
from tqdm import tqdm

def download_metar(ICAO):
    base_url = 'https://tgftp.nws.noaa.gov/data/observations/metar/stations/'
    url = base_url + ICAO + '.TXT'
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.text.split('\n')[1]
    except requests.RequestException as e:
        # raise ValueError
        print(f"Error fetching the file: {e}")
        
        return ""   # just return an empty string if no METAR could be found

database_path = './data/all_apts.csv'
min_runway_length_ft = 8000
min_runway_length_ft = min_runway_length_ft
df = pd.read_csv(database_path,index_col=0)
# filter airports by minimum runway length
df_filtered = df[df["MaxRunwayLength"]>=min_runway_length_ft]
# filter airports by airport types (C=commercial, P=private, M=military)
df_filtered = df_filtered[df_filtered["AptType"]=="C"]

# list of all global (approx. 2000) airports that are candidates due to to airport type and min max runway length
icao_list = df_filtered["ICAO"].to_list()
metars = []
for icao in tqdm(icao_list):
    metars.append(download_metar(icao))

df = pd.DataFrame({"ICAO":icao_list, "METAR":metars}).to_csv('./data/metars.csv',index=False)

print("Completed.")