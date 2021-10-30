#!/usr/bin/env python3

import os
import sys
import time
import json

import pyaudio
import wave
import requests
from dotenv import load_dotenv

import kbd



load_dotenv()  # take environment variables from .env.

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
# RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "output.wav"

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
