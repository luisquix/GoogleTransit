import os
import pandas as pd
import zipfile
import time
import datetime
import quixstreams as qx
from quixstreams import Application, State
from quixstreams.models.serializers.quix import QuixDeserializer, QuixTimeseriesSerializer, QuixSerializer, JSONSerializer, SerializationContext
# import the dotenv module to load environment variables from a file
# from dotenv import load_dotenv
# load_dotenv(override=False)

def parse_extended_time(time_str):
    """Parse extended hour time strings into a datetime.timedelta object."""
    hours, minutes, seconds = map(int, time_str.split(':'))
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

def calculate_progress(current_stop, next_stop):
    now = datetime.datetime.now()  # Current datetime
    now_time_as_delta = datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)  # Current time as timedelta for comparison

    departure_time_current = parse_extended_time(current_stop['departure_time'])
    departure_time_next = parse_extended_time(next_stop['arrival_time'])

    # Calculate total duration and elapsed duration
    total_duration = departure_time_next - departure_time_current
    elapsed_since_current = now_time_as_delta - departure_time_current

    # Normalize negative elapsed time in case current time is before the first departure
    if elapsed_since_current.total_seconds() < 0:
        elapsed_since_current = datetime.timedelta(seconds=0)

    # Calculate progress
    durationSeconds = total_duration.total_seconds()
    if durationSeconds == 0:
        return 0
    progress = elapsed_since_current.total_seconds() / durationSeconds 
    return progress

def main():
    # Path to your GTFS zip file
    gtfs_zip_path = 'google_transit.zip'

    # Directory where you want to extract the GTFS files
    extract_to_dir = 'extracted_gtfs'
    os.makedirs(extract_to_dir, exist_ok=True)

    # Extract the GTFS zip file
    with zipfile.ZipFile(gtfs_zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to_dir)

    # Now, you can read any GTFS file into a Pandas DataFrame
    # Example: Reading stops.txt
    print('Parsing data')
    stops_df = pd.read_csv(os.path.join(extract_to_dir, 'stop_times.txt'))
    print('Data parsed')
    print('Sorting data')
    stops_df.sort_values(by=['trip_id', 'stop_sequence'], inplace=True)
    print('Data sorted')

    app = Application.Quix("TrainData", auto_offset_reset="latest")

    input_topic = app.topic(os.environ["LiveTrainData"])

    producer = app.get_producer()
    serializer = JSONSerializer()
    headers = stops_df.columns.tolist()
    last_progress_by_tripId = {}

    with producer:
        while True:
            # Iterate over the data from CSV file
            for index, row in stops_df.iterrows():
                if index + 1 >= len(stops_df):
                    continue

                row_data = { header: row[header] for header in headers }
                row_data["Timestamp"] = time.time_ns()

                # Calculate progress and add to row_data
                
                found_next_row = False
                next_row = stops_df.iloc[index + 1]
                for next_index in range(index + 1, len(stops_df)):
                    potential_next_row = stops_df.iloc[next_index]
                    if potential_next_row["trip_id"] == row["trip_id"]:
                        next_row = potential_next_row
                        found_next_row = True
                        break
                
                if not found_next_row:
                    break
                
                tripId = row_data["trip_id"]

                last_progress = last_progress_by_tripId.get(tripId)
                progress = calculate_progress(row, next_row)
                last_progress_by_tripId[tripId] = max(0, min(1, progress))
                if last_progress is not None and (progress <= 0 or progress >= 1 or last_progress == max(0, min(1, progress))):
                    continue 

                if progress <= 0 or progress >= 1:
                    continue
                
                row_data['arrival_to_destination_time'] = next_row['arrival_time']
                row_data['next_stop_id'] = int(next_row['stop_id'])

                row_data["progress"] = progress
                # Serialize row value to bytes
                serialized_value = serializer(
                    value=row_data, ctx=SerializationContext(topic=input_topic.name)
                )
                
                # publish the data to the topic
                producer.produce(
                    topic=input_topic.name,
                    key=tripId,
                    value=serialized_value,
                )

if __name__ == "__main__":
    main()