import numpy as np
import pandas as pd
from copy import deepcopy


class AirportFinder():
    def __init__(self,database_path,metas_path,min_runway_length_ft=8000,N=5):
        self.database_path = database_path
        self.metars_path = metas_path
        self.min_runway_length_ft = min_runway_length_ft
        self.N = N
        self.df = pd.read_csv(self.database_path,index_col=0)   # read the airport database csv
        self.df_metar = pd.read_csv(self.metars_path)
        # merge the airport and METAR df
        self.df = self.df.merge(self.df_metar,how='left',on='ICAO')
        # filter airports by minimum runway length
        self.df_filtered = self.df[self.df["MaxRunwayLength"]>=self.min_runway_length_ft]
        # filter airports by airport types (C=commercial, P=private, M=military)
        self.df_filtered = self.df_filtered[self.df_filtered["AptType"]=="C"]
        
        self.lat_lon = self.df_filtered[["Latitude", "Longitude"]].to_numpy()
        self.glide_ratio = 17   # A320 has a glide ratio of approx. 17:1 in clean config
    
    def get_closest_airports(self,lat1, lon1, altitude=None):
        """
        Calculate the great-circle distances between a single (lat1, lon1) pair and 
        an array of latitude/longitude pairs using the haversine formula.
        
        Parameters:
        - lat1, lon1: Latitude and longitude of the reference point (in degrees).
        - range: Range of the aircraft (in kilometers)
        
        Returns:
        - distances: Array of distances (in kilometers) from the reference point.
        """
        filtered_df = deepcopy(self.df_filtered)
        
        lat_lons = self.lat_lon
        
        # Convert degrees to radians
        lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
        lat2_rad = np.radians(lat_lons[:, 0])
        lon2_rad = np.radians(lat_lons[:, 1])
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = np.sin(dlat / 2.0)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2.0)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        # Radius of Earth in kilometers (use 3958.8 for miles)
        R = 6371.0
        distances = R * c
        
        filtered_df["Distance"] = distances
        filtered_df = filtered_df.sort_values(by='Distance')
        filtered_df["In_Glidepath"] = False
        if altitude is not None:
            max_range = altitude * self.glide_ratio
            filtered_df.loc[filtered_df["Distance"]<=max_range, "In_Glidepath"] = True
            
            if filtered_df[filtered_df["Distance"]<=max_range].shape[0] >= self.N:
                return filtered_df[filtered_df["Distance"]<=max_range].to_dict(orient='records')
            else: 
                return filtered_df.head(self.N).to_dict(orient='records')
        else:
            return filtered_df.head(self.N).to_dict(orient='records')

        

if __name__ == "__main__":
    af = AirportFinder('./all_apts.csv', 'metars.csv')
    pos = np.array([47.229714, -122.172793])
    closest_apts = af.get_closest_airports(*pos)
    print("stp[]")
    