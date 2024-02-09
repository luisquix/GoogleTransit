import os
import pandas as pd
from quixstreams import Application, State
from quixstreams.models.serializers.quix import QuixDeserializer, QuixTimeseriesSerializer
# import the dotenv module to load environment variables from a file
from dotenv import load_dotenv
load_dotenv(override=False)

app = Application.Quix("TrainData", auto_offset_reset="latest")

stops_df = pd.read_csv('stops.txt')
stops_df.columns = stops_df.columns.str.strip()
stops_df = stops_df.map(lambda x: x.strip() if isinstance(x, str) else x)

trips_df = pd.read_csv('trips.txt')
trips_df.columns = trips_df.columns.str.strip()
trips_df = trips_df.map(lambda x: x.strip() if isinstance(x, str) else x)

routes_df = pd.read_csv('routes.txt')
routes_df.columns = routes_df.columns.str.strip()
routes_df = routes_df.map(lambda x: x.strip() if isinstance(x, str) else x)

input_topic = app.topic(os.environ["LiveTrainData"])
output_topic = app.topic(os.environ["ArrivalTrainData"])

sdf = app.dataframe(input_topic)

# Here put transformation logic.

sdf = sdf[(sdf["progress"] > 0.9 )]
sdf = sdf[(sdf["progress"] < 1.1 )]
def safe_get_stop_name(stop_id):
    try:
        return stops_df.loc[stops_df['stop_id'] == stop_id, 'stop_name'].iloc[0]
    except IndexError:
        return None  # or a default value like 'Unknown'
def safe_get_next_stop_name(next_stop_id):
    try:
        return stops_df.loc[stops_df['stop_id'] == next_stop_id, 'stop_name'].iloc[0]
    except IndexError:
        return None  # or a default value like 'Unknown'
def safe_get_route_id(trip_id):
    try:
        return trips_df.loc[trips_df['trip_id'] == trip_id, 'route_id'].iloc[0]
    except IndexError:
        return None  # or a default value
def safe_get_route_name(route_id):
    try:
        return routes_df.loc[routes_df['route_id'] == route_id, 'route_long_name'].iloc[0]
    except IndexError:
        return None  # or a default value like 'Unknown Route'

sdf['stop_name'] = sdf.apply(lambda value: safe_get_stop_name(value['stop_id']))
sdf['next_stop_name'] = sdf.apply(lambda value: safe_get_next_stop_name(value['next_stop_id']))
sdf['route_id'] = sdf.apply(lambda value: safe_get_route_id(value['trip_id']))
sdf['route_name'] = sdf.apply(lambda value: safe_get_route_name(value['route_id']))

# sdf = sdf.update(lambda row: print(row["progress"]))
sdf = sdf.to_topic(output_topic)

if __name__ == "__main__":
    app.run(sdf)