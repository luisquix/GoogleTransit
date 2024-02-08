import os
from quixstreams import Application, State
from quixstreams.models.serializers.quix import QuixDeserializer, QuixTimeseriesSerializer
# import the dotenv module to load environment variables from a file
#from dotenv import load_dotenv
#load_dotenv(override=False)

app = Application.Quix("TrainData", auto_offset_reset="latest")

input_topic = app.topic(os.environ["LiveTrainData"])
output_topic = app.topic(os.environ["ArrivalTrainData"])

sdf = app.dataframe(input_topic)

# Here put transformation logic.

sdf = sdf[(sdf["progress"] > 0.9)]
sdf = sdf.update(lambda row: print(row))

sdf = sdf.to_topic(output_topic)

if __name__ == "__main__":
    app.run(sdf)