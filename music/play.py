import asyncio

from machine import Pin, PWM
from utime import sleep

from music.melodies import *  # import melodies.py
from music.notes import *  # import notes.py
from pins import BUZZER_PIN

buzzer = PWM(Pin(BUZZER_PIN), freq=30000)  # pin where buzzer is connected

volume = 0  # set volume to a value between 0 and 1000


# functions to play the melodies

def playtone(frequency):
    """Play one tone at the configured volume."""
    buzzer.duty_u16(volume) # maximal volume at duty cycle equal to 32768
    buzzer.freq(frequency)


def be_quiet():
    """Mute the buzzer output."""
    buzzer.duty_u16(0)  # turns sound off


def duration(tempo, t):
    """Compute note duration in milliseconds."""
    # calculate the duration of a whole note in milliseconds (60s/tempo)*4 beats
    wholenote = (60000 / tempo) * 4

    # calculate the duration of the current note
    # (we need an integer without decimals, hence the // instead of /)
    if t > 0:
        noteDuration = wholenote // t
    elif (t < 0):
        # dotted notes are represented with negative durations
        noteDuration = wholenote // abs(t)
        noteDuration *= 1.5  # increase their duration by a half

    return noteDuration

is_playing = False
stop_requested = False
async def playsong_async(mysong):
    """Play one melody asynchronously."""
    global is_playing
    global stop_requested
    if is_playing:
        return
    stop_requested = False
    is_playing = True
    try:

        print(mysong[0])  # print title of the song to the shell
        tempo = mysong[1]  # get the tempo for this song from the melodies list

        # iterate over the notes of the melody.
        # The array is twice the number of notes (notes + durations)
        for thisNote in range(2, len(mysong), 2):
            if stop_requested:
                print("STOP demandé")
                break
            noteduration = duration(tempo, int(mysong[thisNote + 1]))

            if (mysong[thisNote] == "REST"):
                be_quiet()
            else:
                playtone(notes[mysong[thisNote]])

            await asyncio.sleep_ms(int(noteduration * 0.9))  # we only play the note for 90% of the duration...
            be_quiet()
            await asyncio.sleep_ms(int(noteduration * 0.1))  # ... and leave 10% as a pause between notes

    except:  # make sure the buzzer stops making noise when something goes wrong or when the script is stopped
        be_quiet()
    be_quiet()
    is_playing = False

def playsong(mysong):
    """Play one melody synchronously."""
    try:

        print(mysong[0])  # print title of the song to the shell
        tempo = mysong[1]  # get the tempo for this song from the melodies list

        # iterate over the notes of the melody.
        # The array is twice the number of notes (notes + durations)
        for thisNote in range(2, len(mysong), 2):

            noteduration = duration(tempo, int(mysong[thisNote + 1]))

            if (mysong[thisNote] == "REST"):
                be_quiet()
            else:
                playtone(notes[mysong[thisNote]])

            sleep(noteduration * 0.9 / 1000)  # we only play the note for 90% of the duration...
            be_quiet()
            sleep(noteduration * 0.1 / 1000)  # ... and leave 10% as a pause between notes

    except:  # make sure the buzzer stops making noise when something goes wrong or when the script is stopped
        be_quiet()

def set_volume(new_volume):
    """Set the volume of the music."""
    global volume
    volume = new_volume
