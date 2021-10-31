#!/usr/bin/env python3

import os
import sys
import time
import json
import pickle

import pyaudio
import wave
import requests
from dotenv import load_dotenv
from twilio.rest import Client

import kbd



load_dotenv()  # take environment variables from .env.

import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument('--model', dest='model_path', type=str, default=os.path.join('pretrained', 'model-29'),
                    help='(optional) DL model to use')
parser.add_argument('--style', dest='style', type=int, default=0, help='Style of handwriting (1 to 7)')
parser.add_argument('--bias', dest='bias', type=float, default=0.9,
                    help='Bias in handwriting. More bias is more unclear handwriting (0.00 to 1.00)')
parser.add_argument('--force', dest='force', action='store_true', default=False)
parser.add_argument('--color', dest='color_text', type=str, default='0,0,150',
                    help='Color of handwriting in RGB format')
parser.add_argument('--output', dest='output', type=str, default='./handwritten.pdf',
                    help='Output PDF file path and name')
args = parser.parse_args()

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
# RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"


import matplotlib
# import tensorflow as tf
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()

import generate

matplotlib.use('agg')

p = pyaudio.PyAudio()

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("* recording")

frames = []

# for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
#     data = stream.read(CHUNK)
#     frames.append(data)

kb = kbd.KBHit()

print('Hit ESC to exit')

while True:
    data = stream.read(CHUNK)
    frames.append(data)

    if kb.kbhit():
        c = kb.getch()

        if ord(c) == 27:
            print("Stopping recording...")
            break
        else:
            print(c)

kb.set_normal_term()

print("* done recording")

stream.stop_stream()
stream.close()
p.terminate()

wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()

def read_file(filename, chunk_size=5242880):
    with open(filename, 'rb') as _file:
        while True:
            data = _file.read(chunk_size)
            if not data:
                break
            yield data

headers = {
    "authorization": os.environ["ASSEMBLYAI_TOKEN"],
}
response = requests.post('https://api.assemblyai.com/v2/upload',
                         headers=headers,
                         data=read_file(WAVE_OUTPUT_FILENAME))

print(f"Audio Upload Response:")
print(response.json())


endpoint = "https://api.assemblyai.com/v2/transcript"

json_payload = {
  "audio_url": response.json()['upload_url']
}

headers = {
    "authorization": os.environ["ASSEMBLYAI_TOKEN"],
    "content-type": "application/json",
}

response = requests.post(endpoint, json=json_payload, headers=headers)

print(f"Job start response:")
print(response.json())

transcript_id = response.json()['id']

endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"

headers = {
    "authorization": os.environ["ASSEMBLYAI_TOKEN"],
}

while True:
    print("Waiting for transcription to complete...")
    response = requests.get(endpoint, headers=headers)
    # print(response.json())
    time.sleep(2)
    if response.json()['status'] in ['completed', 'error']:
        break

final_transcript_response = response.json()
print(f"Final response: {response.json()}")

endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}/paragraphs"

response = requests.get(endpoint, headers=headers)

print(response.json())
print(json.dumps((response.json()), indent=2))

fulltext_string = "\n\n".join(x['text'] for x in response.json()["paragraphs"])

print(f"Full text:\n\n{fulltext_string}")

def writetext(text):
    with open(os.path.join('data', 'translation.pkl'), 'rb') as file:
        translation = pickle.load(file)
    rev_translation = {v: k for k, v in translation.items()}
    charset = [rev_translation[i] for i in range(len(rev_translation))]
    charset[0] = ''

    config = tf.ConfigProto(
        device_count={'GPU': 0}
    )

    with tf.Session(config=config) as sess:
        saver = tf.train.import_meta_graph(args.model_path + '.meta')
        saver.restore(sess, args.model_path)

        print("\n\nInitialization Complete!\n\n\n\n")

        color = [int(i) for i in args.color_text.replace(' ', '').split(',')]
        pdf = generate.generate(text.replace('1', 'I'), args, sess, translation, color[:3])

writetext(fulltext_string)

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.environ['TWILIO_ACCOUNT_SID']
auth_token = os.environ['TWILIO_AUTH_TOKEN']
client = Client(account_sid, auth_token)

message = client.messages \
                .create(
                     body="Your latest AutoNote is ready to view!",
                     from_='+15076985168',
                     to=os.environ['TARGET_NUMBER']
                 )

print(message.sid)
