# From https://towardsdatascience.com/using-the-strava-api-and-pandas-to-explore-your-activity-data-d94901d9bfde
# From https://github.com/franchyze923/Code_From_Tutorials/blob/master/Strava_Api/strava_api.py
# API usage example: https://www.strava.com/api/v3/athlete/activities?access_token=<token>&per_page=200&page=1

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import pandas as pd
import json
import pickle
import plotly.express as px
from datetime import timedelta
import numpy as np

auth_url = "https://www.strava.com/oauth/token"
activites_url = "https://www.strava.com/api/v3/athlete/activities"

# Read the JSON file with token information
with open('payload.json', 'r') as file:
    payload = json.load(file)

# Authenticate Strava token to access the API
def strava_authenticate(payload=payload):

    print("Requesting Token...\n")
    res = requests.post(auth_url, data=payload, verify=False)
    access_token = res.json()['access_token']
    print("Access Token = {}\n".format(access_token))

    return access_token

# Authenticate Strava token to access the API
def get_activities(access_token):

    header = {'Authorization': 'Bearer ' + access_token}
    page = 1
    my_dataset = []

    while True:
        param = {'per_page': 200, 'page': page}
        requestedacts = requests.get(activites_url, headers=header, params=param).json()
        if len(requestedacts)>0:
            my_dataset.extend( requestedacts )
            page += 1
        else:
            break

    activities = pd.json_normalize(my_dataset)

    activities = process_activities(activities)

    return activities

# Process activities, filtering and changing units
def process_activities(activities):

    # cols = ['name', 'id', 'type', 'distance', 'moving_time',   
    #         'average_speed', 'max_speed','total_elevation_gain',
    #         'start_date_local', 'average_watts', 'kilojoules'
    #     ]
    # activities = activities[cols]

    activities['start_date_local'] = pd.to_datetime(activities['start_date_local'])
    activities['start_time'] = activities['start_date_local'].dt.time
    activities['start_date_local'] = activities['start_date_local'].dt.date
    activities['kcal'] = activities['kilojoules']*1.115

    activities["distance"] = activities["distance"]/1.e3
    activities["moving_time"] = activities["moving_time"].astype(float)/60.
    activities["average_speed"] = activities["average_speed"]*3.6
    activities["max_speed"] = activities["max_speed"]*3.6

    activities = activities[activities["distance"]>0.]
    activities = activities.reset_index()

    activities['date'] = activities['start_date_local']
    activities['elevation'] = activities['total_elevation_gain']

    return activities

# Import object from pickle file
def import_data(name):
    with open("data/"+name+'.pickle', 'rb') as handle:
        activities = pickle.load(handle)
    return activities

# Export object to pickle file
def export_data(name, activities):
    with open("data/"+name+'.pickle', 'wb') as handle:
        pickle.dump(activities, handle, protocol=pickle.HIGHEST_PROTOCOL)


# Estimate of Training Load, or Training Stress Score, from https://ssp3nc3r.github.io/post/2020-05-08-calculating-training-load-in-cycling/
# See also https://science4performance.com/2019/11/04/modelling-strava-fitness-and-freshness/
# It should be normalized power rather than average power
# Evolution looks similar, but probably is a bit different
def TrainingLoad(duration, power, FTP=180):
    return 100*(power/FTP)*(duration/60.)

# Plot fitness, fatigue and form
# Form positive for races, negative for workouts, be between -10 and -30 (Allen 2019), https://ssp3nc3r.github.io/post/2020-05-08-calculating-training-load-in-cycling/
def plot_fitness_freshness(runs, rangedata=None, export=False):
    
    runs["training_load"] = TrainingLoad(runs["moving_time"], runs["average_watts"])

    prev_range = pd.to_timedelta(7, unit='d')  # previous 7 days
    start_day = runs["date"].min()-prev_range
    end_day = pd.Timestamp.today() # runs["start_date_local"].max()
    daterange = pd.date_range(start=start_day, end=end_day)
    runs["date"] = pd.to_datetime(runs["date"])
    runsgrouped = runs.groupby([pd.Grouper(key="date")])['training_load'].sum().reset_index().sort_values('date')
    f_df = pd.DataFrame({"date":daterange})
    merged = pd.merge(runsgrouped, f_df, on="date", how="right")
    merged.loc[merged['training_load'].isnull(), 'training_load'] = 0
    #merged["training_load"][merged["training_load"].isnull()]=0.

    # Fitness, or Chronic Training Load (CTL)
    merged["fitness"] = merged["training_load"].ewm(alpha=1.-np.exp(-1/42)).mean()
    #merged["fitness"] = merged["training_load"].ewm(alpha=2./(42.+1.)).mean()  # Allen 2019, maybe wrong, the above formula mas more sense, comes from ODEs
    
    # Fatigue, or Acute Training Load (ATL)
    merged["fatigue"] = merged["training_load"].ewm(alpha=1.-np.exp(-1/7)).mean()
    #merged["fatigue"] = merged["training_load"].ewm(alpha=2./(7.+1.)).mean()   # Allen 2019
    
    # Form, fitness minus fatigue
    merged["form"] = merged["fitness"] - merged["fatigue"]
    
    fig = px.line(merged, x="date", y=["fitness","fatigue","form"], title=None)
    
    if rangedata is None:
        rangedata = [runs["date"].min()-timedelta(days=1), runs["date"].max()+timedelta(days=1)]
    fig.update_xaxes(range=rangedata)
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    
    if export:
        fig.write_html("htmls/fitness.html")
    
    return fig

# Plot wrapper in plotly
def px_plot(acts, y, color, x="date", rangedata=None, export=False, title=None):

    fig = px.scatter(acts, y=y, x=x,hover_name="name", hover_data=["date"],color=color,title=title)

    if rangedata is None:
        rangedata = [acts["date"].min()-timedelta(days=1), acts["date"].max()+timedelta(days=1)]
    fig.update_xaxes(range=rangedata)
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))

    if export:
        fig.write_html("htmls/"+x+"_vs_"+y+".html")

    return fig

# Compute the Eddington number
def Eddington_number(activities_move):
    
    distances = np.floor(activities_move.distance.values)
    
    edd = 1
    num_dist = 0

    max_dist = int(distances.max())
    
    list_dists = []

    for i in range(max_dist):

        for dist in distances:

            if dist>=i:
                num_dist+=1
                
        list_dists.append([i, num_dist])

        if num_dist>edd:
            edd+=1
            
        num_dist = 0
    
    distance_freq = pd.DataFrame(list_dists, columns=["distance [km]","number"])
            
    return edd, distance_freq

# Plot the Eddington number
def Eddington_plot(edd, distance_freq, export=False):

    fig = px.bar(distance_freq,x="distance [km]",y="number")
    fig.add_vline(x=edd, line_width=3, line_color="red")

    if export:
        fig.write_html("htmls/eddington.html")

    return fig

# Get GPS info for each activity
def get_gps_activities(activities, access_token, acts_gps=None, acts_info=None):

    columns = ["id","name","distance","moving_time","elevation","start_time"]

    if acts_gps is None:
        acts_gps = []

    if acts_info is None:
        acts_info = pd.DataFrame([], columns=columns)

    numerrors = 0

    for i in range(len(activities)):
       
        if activities.iloc[i]["type"]=="WeightTraining" or activities.iloc[i]["type"]=="Workout":
            continue

        if activities.iloc[i]["distance"]<=0.:
            continue
            
        #print(i, activities.iloc[i]["name"])

        id = activities.iloc[i]["id"]
        start_time = activities.iloc[i]["date"]

        # Check if the activity is already in the DataFrame, continue in that case
        if id in acts_info['id'].values:
            continue

        # Make API call
        url = f"https://www.strava.com/api/v3/activities/{id}/streams"
        header = {'Authorization': 'Bearer ' + access_token}
        #print(requests.get(url, headers=header, params={'keys':['latlng']}).json())
        try:
            requested = requests.get(url, headers=header, params={'keys':['latlng']}).json()
            #print(requested)
            latlong = requested[0]['data']
            
            #time_list = requests.get(url, headers=header, params={'keys':['time']}).json()[1]['data']
            #altitude = requests.get(url, headers=header, params={'keys':['altitude']}).json()[1]['data']

            # Create dataframe to store data 'neatly'
            data = pd.DataFrame([*latlong], columns=['lat','long'])
            #data['altitude'] = altitude
            #start = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
            #data['time'] = [(start+timedelta(seconds=t)) for t in time_list]
            new_act =  pd.DataFrame([[id, activities.iloc[i]["name"], activities.iloc[i]["distance"], activities.iloc[i]["moving_time"], activities.iloc[i]["total_elevation_gain"],start_time]], columns=columns)
            #acts_gps = pd.concat([acts_gps, data], ignore_index=True)
            acts_gps.append(data)
            acts_info = pd.concat([acts_info, new_act], ignore_index=True)
        except:
            if requested['message']!='Resource Not Found':
                print("Error in",i, activities.iloc[i]["name"])
                print(requested['message'])
                numerrors += 1
                if numerrors>2:
                    print("Stopping due to request errors. Try again later...")
                    break
                continue

    export_data("acts_gps",acts_gps)
    export_data("acts_info",acts_info)
        
    return acts_gps, acts_info