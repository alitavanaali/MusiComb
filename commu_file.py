from __future__ import annotations

import copy
from typing import List

import yaml
from mido import MidiFile, MidiTrack, merge_tracks, tick2second
import mido


class CommuFile(MidiFile):

    channel_count = -1

    def __init__(self, filepath: str, name: str, instrument: str) -> None:
        super().__init__(filepath)
        self._preprocess(name, instrument)

    @property
    def track(self) -> MidiTrack:
        assert len(self.tracks) == 1
        return self.tracks[0]

    def getTempo(self) -> int:
        for message in self.track:
            if message.type == 'set_tempo':
                return message.tempo
        return 500000 # Default MIDI tempo (120 BPM)



    def setTempo(self, tempo):
        for message in self.track:
            if message.type == 'set_tempo':
                message.tempo = tempo
    @property
    def duration(self) -> int:
        current_tempo = 500000  # Default MIDI tempo (120 BPM)
        total_time_in_ticks = 0
        total_time_in_seconds = 0

        for message in self.track:
            if message.type == 'set_tempo':
                # Convert the accumulated ticks to time using the previous tempo
                total_time_in_seconds += tick2second(total_time_in_ticks, self.ticks_per_beat, current_tempo)
                total_time_in_ticks = 0  # Reset the tick count for the new tempo segment
                current_tempo = message.tempo
            total_time_in_ticks += message.time

        # Convert the remaining ticks to time
        total_time_in_seconds += tick2second(total_time_in_ticks, self.ticks_per_beat, current_tempo)
        return int(total_time_in_seconds * 1000)

    def shift(self, time: int) -> CommuFile:
        """
        This method will shift the notes to the right by the value of input (time)
        input will be time in milliseconds, so we need to convert them to ticks before
        any modification
        """
        shifted = copy.deepcopy(self)
        tempo = self.getTempo()
        seconds = time / 1000.0
        beats = seconds / (tempo / 1000000.0)
        time_in_ticks = int(beats * self.ticks_per_beat)

        if shifted.track.name.startswith('drum'):
            first_message = True
            for message in shifted.track:
                if first_message and not message.is_meta:
                    message.time += time_in_ticks
                    first_message = False
        else:
            for message in shifted.track:
                # to shift all the roles except the drum we need to change program_change
                if message.type == 'program_change':
                    message.time += time_in_ticks


        return shifted


    def _preprocess(self, name: str, instrument: str) -> None:
        with open('cfg/programs.yaml') as f:
             inst_to_prog = yaml.safe_load(f)
        self._move_meta()
        self._set_name(name)
        self._set_program(inst_to_prog[instrument])
        self._set_channel()

    def _move_meta(self) -> None:
        # commented assert for checking two tracks
        #assert len(self.tracks) == 2
        assert [message.is_meta for message in self.tracks[0]]
        self.tracks = [merge_tracks(self.tracks)]

    def _set_name(self, name: str) -> None:
        self.track.name = name

    def _set_program(self, program: int) -> None:
        for message in self.track:
            if message.type == 'program_change':
                message.program = program

    def _set_channel(self) -> None:
        CommuFile.channel_count += 1
        if CommuFile.channel_count == 9:
             # channel 10 is reserved to percussions, but there are no percussions in ComMU
             CommuFile.channel_count += 1
        for message in self.track:
            if self.track.name.startswith("drum"):
                if message.type in ['note_on', 'note_off', 'control_change']:
                    # channel 10 is reserved for percussions, 9 in computer science (0-9)
                    message.channel = 9
            elif message.type == 'program_change' or message.type == 'note_on':
                message.channel = CommuFile.channel_count

def inner_merge(tracks_of_same_role: List[CommuFile], music_length_in_milliseconds) -> CommuFile:
    """
    This Function will merge all the tracks in a same group like all the pad midi files (pad_0_0, pad_0_1 and...)
    into one single track (type -> CommiFile

        1- an example of Drum midi track:
        MidiTrack([
            MetaMessage('track_name', name='drum_0_0', time=0),
            MetaMessage('instrument_name', name='Brooklyn', time=0),
            MetaMessage('time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0),
            MetaMessage('key_signature', key='C', time=0),
            MetaMessage('smpte_offset', frame_rate=24, hours=33, minutes=0, seconds=0, frames=0, sub_frames=0, time=0),
            MetaMessage('set_tempo', tempo=600000, time=0),
            Message('note_on', channel=9, note=36, velocity=71, time=122880),
            Message('note_on', channel=9, note=22, velocity=113, time=0),
            Message('note_off', channel=9, note=36, velocity=64, time=50),
            Message('note_off', channel=9, note=22, velocity=64, time=8),
            ...

        2- an example of Bass midi track:
        MidiTrack([
            MetaMessage('track_name', name='bass_0_0', time=0),
            MetaMessage('set_tempo', tempo=600000, time=0),
            MetaMessage('time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0),
            MetaMessage('key_signature', key='C', time=0),
            MetaMessage('marker', text='c', time=0),
            Message('program_change', channel=12, program=0, time=122880),
            Message('note_on', channel=12, note=36, velocity=42, time=0),
            MetaMessage('marker', text='c', time=1920),
            Message('note_on', channel=12, note=36, velocity=0, time=0),
            Message('note_on', channel=12, note=36, velocity=42, time=0),
            MetaMessage('marker', text='f', time=1920),
            Message('note_on', channel=12, note=36, velocity=0, time=0),
            Message('note_on', channel=12, note=41, velocity=41, time=0),
            ...
    """
    # calculate music length of the music in ticks
    tempo = tracks_of_same_role[0].getTempo()
    seconds = music_length_in_milliseconds / 1000.0
    beats = seconds / (tempo / 1000000.0)
    music_length_in_ticks = int(beats * tracks_of_same_role[0].ticks_per_beat)

    # get a copy of first track (all the tracks are same, so second one is fine too) to set te midi name, path and etc.
    file = copy.deepcopy(tracks_of_same_role[0])
    merged_track = mido.MidiTrack()
    # define a flag to find if all the headers of midi file has been collected
    flag_meta_message_finished = False

    sum_time = 0
    for track in tracks_of_same_role:
        copied = copy.deepcopy(track)

        # if the track is drum or other roles
        is_drum = track.track.name.startswith('drum')

        # because the structure of Drum midi files are different with other instruments we need a unique flag for it's header
        is_first_drum_change = True
        for msg in copied.track:
                # fill the header of the final track
                if msg.type in ['track_name', 'set_tempo', 'time_signature', 'key_signature', 'smpte_offset', 'instrument_name']:
                    if not flag_meta_message_finished:
                        merged_track.append(msg)
                else:
                    flag_meta_message_finished = True
                    if msg.type == 'end_of_track':
                        continue
                    elif msg.type == 'program_change':
                        updated_message = copy.deepcopy(msg)
                        updated_message.time = max(0, msg.time - sum_time)
                        sum_time += updated_message.time
                        merged_track.append(updated_message)
                    elif is_first_drum_change and is_drum:
                            updated_message = copy.deepcopy(msg)
                            # for those tracks that for a few milliseconds they will pass the number of measures defined before
                            # example: bar 8 ends in 13 seconds, but this track ends in 13.02 seconds
                            while (msg.time - sum_time) < 0:
                                    last_message = merged_track[-1]
                                    sum_time -= last_message.time
                                    del merged_track[-1]
                            updated_message.time = msg.time - sum_time
                            sum_time += updated_message.time
                            merged_track.append(updated_message)
                            is_first_drum_change = False
                    else:
                            sum_time += msg.time
                            # don't need the notes after the end of the music
                            if sum_time < music_length_in_ticks:
                                merged_track.append(msg)


    file.tracks = [merged_track]
    return file

def merge(midis: List[CommuFile]) -> MidiFile:
    merged = MidiFile()
    merged.tracks = [midi.track for midi in midis]
    return merged
