##############################
##### MidiModulator v0.1 #####
##############################

# by Joachim Ganseman
# for MusicHackDay London 2013

# This Python script will take a song and modulate the pitch with the melody of a chosen score (basically, another song).

# Used software and APIs:
# - Deezer: download a song
# - EchoNest (python): chop it up in little chunks
# - MuseScore: download a melody
# - SonicAPI: pitch-shift ALL the chunks
# - music21: get the pitches out of the score
# - SoX: glue it back together at the end

# TODO: does not use the 

import requests
import json
import urllib
import urllib2
import echonest.remix.audio as audio
from music21 import *
import re
import zipfile
import os.path
import math
import subprocess

# make sure you've set your EchoNest API key as environment variable, e.g.:
# export ECHO_NEST_API_KEY=XQFFAMVHSL5ZCVZE9

print "##############################"
print "##### MidiModulator v0.1 #####"
print "##############################"

mySonicAPIkey='6142de23-19c3-4e80-84c7-6dead053f82d'


# Step 1: get song from Deezer
title = raw_input('Type a song title: ')
artist = raw_input('And the artist: ')

# get the song from Deezer
string = 'http://api.deezer.com/search?q=' + artist + ' ' + title
r = requests.get(string)

response = r.json()["data"]
#print response[0]

songid = response[0]["id"]
#print songid

#now get this song or get a preview
songlink = requests.get('http://api.deezer.com/track/'+str(songid)).json()["preview"]
print "Downloading this song through Deezer: {0}".format(songlink)

# download to local file
origfilename = 'original.mp3'
mp3file = urllib2.urlopen(songlink)
output = open(origfilename,'wb')
output.write(mp3file.read())
output.close()


# Step 2: pipe this file to echo nest
audio_file = audio.LocalAudioFile(origfilename)
print "Starting EchoNest analysis of song"

# get beats
mybeats = audio_file.analysis.beats
# that's a list of AudioQuantum objects. Save each one to file...
temp = 0
for beat in mybeats:
	beat.encode("temp"+str(temp)+".wav")		# encode as wave
	temp +=1

nrOfSamples = temp


# Step3: now load a midi file. Search MuseScore

midname = raw_input('Search for this modulator melody (query): ')
mspage = urllib2.urlopen('http://musescore.com/sheetmusic?parts=1&text='+midname).read()
#print mspage
		
scores = re.findall('http://musescore.com/user/[0-9]+/scores/[0-9]+', mspage)
myscore = scores[0]
print "Downloading this score from MuseScore: {0}".format(myscore)

# get midi
secrets = re.findall('http://static.musescore.com/[0-9]+/[0-9a-f]+', mspage)
mysecret = secrets[0]

# download and save locally
midilink = mysecret + '/score.mid'
midifile = urllib2.urlopen(midilink)
midifilename = 'modulator.mid'
output = open(midifilename,'wb')
output.write(midifile.read())
output.close()

xmllink = mysecret + '/score.mxl'
xmlfile = urllib2.urlopen(xmllink)
xmlfilename = 'modulator.mxl'
output = open(xmlfilename,'wb')
output.write(xmlfile.read())
output.close()

# unzip xml
zf = zipfile.ZipFile("modulator.mxl")
dest_dir = "./"
for member in zf.infolist():
	# Path traversal defense copied from
	# http://hg.python.org/cpython/file/tip/Lib/http/server.py#l789
	words = member.filename.split('/')
	path = dest_dir
	for word in words[:-1]:
		drive, word = os.path.splitdrive(word)
		head, word = os.path.split(word)
		if word in (os.curdir, os.pardir, ''): continue
		path = os.path.join(path, word)
	# print member.filename
	if "META-INF" in member.filename: continue
	zf.extract(member, path)
	os.rename(member.filename, 'modulator.xml')



# we should have just one file, modulator.xml
# load it in music21
modulator = converter.parse('modulator.xml')
#modulator.show('text') 

notelist = modulator.flat.getElementsByClass('Note')
#notelist.show('text')

pitches = []
for note in notelist:
	pitches.append(note.midi)

print "Music21 extracted the following list of pitches from the score:"
print pitches

lowestpitch = min(pitches)
highestpitch = max(pitches)
middlepitch = math.floor((lowestpitch+highestpitch)/2)

if (highestpitch-lowestpitch) > 45:
	print "Warning: pitch range > 45. Calculated pitchshifts will be modulo 2 octaves."

# set base URL for SonicAPI
sonicupload = 'http://api.sonicapi.com/file/upload'
sonicshift = 'http://api.sonicapi.com/process/elastique?access_id='+mySonicAPIkey+'&input_file='

# iterate over all our sound samples
for i in xrange(nrOfSamples):				#exclusief	nrSamples
	cursamplename = "temp"+str(i)+".wav"
	url = sonicupload
	r = requests.post(url, data = {'access_id' : mySonicAPIkey}, files={'file': open(cursamplename, 'rb')})
	#this comes back in xml format. Cut out the id by regexing: id="4d4d1706-838a-4d6d-b3b7-8507ae9ea621"
	#print r.text	
	fileid = re.findall('id="[0-9a-f-]*"', r.text)[0]
	fileid = fileid[4:-1]
	#print fileid

	#now call the shifter url
	url = sonicshift+fileid+"&pitch_semitones="

	curpitch=pitches[i%len(pitches)];
	if curpitch>=middlepitch:
		midichange = (curpitch-middlepitch)%24
	else:
		midichange = -((middlepitch-curpitch)%24)

	url+=str(midichange)
	url+="&format=wav"

	#do call to SonicAPI
	print "Calling SonicAPI to process chunk {0}, URL: {1}".format(str(i),url)
	shiftedfile = urllib2.urlopen(url)
	output = open("temps"+str(i)+".wav",'wb')
	output.write(shiftedfile.read())
	output.close()
	#append result to newMix
	

# to concatenate, just use sox library.
print("Assembling the result with SoX glue ==> result.wav")
command = "sox "
for i in xrange(nrOfSamples)	:
	cursamplename = "temps"+str(i)+".wav"
	command += cursamplename
	command += " "

command += "result.wav"
# print command

subprocess.call(command, shell=True)

print "##### Done! Thank you for using MidiModulator v0.1 #####"

