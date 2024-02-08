import os
import pandas as pd
import zipfile
import time
import datetime
import quixstreams as qx
from quixstreams import Application, State
from quixstreams.models.serializers.quix import QuixDeserializer, QuixTimeseriesSerializer, QuixSerializer, JSONSerializer, SerializationContext
# import the dotenv module to load environment variables from a file
from dotenv import load_dotenv
load_dotenv(override=False)

def parse_gtfs_time(gtfs_time_str):
    """Parse a GTFS time string, which might exceed 24 hours, into a datetime.timedelta."""
    hours, minutes, seconds = map(int, gtfs_time_str.split(':'))
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

def calculate_progress(arrival_time, departure_time, current_time):
    """Calculate progress as a ratio. Returns a value between 0 and 1."""
    # Convert GTFS times to timedeltas
    arrival_delta = parse_gtfs_time(arrival_time)
    departure_delta = parse_gtfs_time(departure_time)
    
    # Assuming current_time is a datetime.datetime object
    # Convert current time to the same day for comparison (ignore date part for simplicity)
    midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    current_delta = current_time - midnight
    
    # Calculate progress
    duration = departure_delta - arrival_delta
    elapsed = current_delta - arrival_delta
    
    if elapsed.total_seconds() < 0:
        # Before arrival
        return -1
    elif elapsed > duration:
        # After departure
        return -2
    else:
        # Between arrival and departure
        return elapsed / duration

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
    stops_df = pd.read_csv(os.path.join(extract_to_dir, 'stop_times.txt'))

    app = Application.Quix("transformation-v1", auto_offset_reset="latest")

    input_topic = app.topic(os.environ["input"])

    producer = app.get_producer()
    serializer = JSONSerializer()
    headers = stops_df.columns.tolist()

    with producer:
        while True:
            # Iterate over the data from CSV file
            for index, row in stops_df.iterrows():
                row_data = { header: row[header] for header in headers }
                row_data["Timestamp"] = time.time_ns()

                # Calculate progress and add to row_data
                current_time = datetime.datetime.now()
                progress = calculate_progress(row['arrival_time'], row['departure_time'], current_time)
                if progress < 0:
                    continue
                row_data["progress"] = progress
                tripId = row_data["trip_id"]
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