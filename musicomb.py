import itertools
from collections import defaultdict, namedtuple
from typing import Dict, List
import random
import yaml
from ortools.sat.python import cp_model

from commu_file import CommuFile, merge, inner_merge
import mido
import copy

class MusiComb():

    def __init__(self, role_to_midis: Dict[str, List[CommuFile]], timestamp: str, bpm, time_signature, num_measures, genre, music_length) -> None:
        self.music_length = music_length * 60000 # in milliseconds
        self.genre = genre
        self.bar_duration = self.calculate_bar_duration(int(bpm), int(time_signature[0]), int(num_measures))
        self.drum_midies = []

        self.role_to_midis = role_to_midis
        self.correct_tempo()
        self.timestamp = timestamp

        self.role_to_tracks = defaultdict(list)
        self.role_to_tracks_opt = defaultdict(list)
        self.role_to_repeats = defaultdict(list)

        self.model = cp_model.CpModel()

        self._add_constraints()


    def calculate_bar_duration(self, bpm, time_signature, bar_number):
        """
        Calculate the duration in seconds of a given bar number in a musical piece with a 4/4 time signature.

        :param bpm: Beats per minute of the piece.
        :param time_signature: The number of beats in a bar (always 4 for 4/4 time).
        :param bar_number: The bar number to calculate the duration for.
        :return: Duration in seconds up to the given bar.
        """
        # In 4/4 time signature, there are 4 beats per bar
        beats_per_bar = time_signature

        # Calculate the duration of one beat in seconds
        beat_duration_seconds = 60 / bpm

        # Calculate the total duration in seconds for the given number of bars
        total_duration_milliseconds = (bar_number) * beats_per_bar * beat_duration_seconds * 1000
        return int(total_duration_milliseconds)


    def _add_constraints(self) -> None:
        Track = namedtuple('Track', 'start end interval is_present')

        role_to_intervals_intro = defaultdict(list)
        role_to_intervals_vers = defaultdict(list)
        role_to_intervals_chorus = defaultdict(list)
        role_to_intervals_ending = defaultdict(list)
        role_to_durations = {role: [midi.duration for midi in midis] for role, midis in self.role_to_midis.items()}

        # here we define a range for each part of the music, if music is 10 minutes long then:
        # intro takes 1 minute, verse 3 minutes, chorus 4 minutes and ending 2 minutes
        intro_end = int(self.music_length * 0.1)
        verse_end = int(self.music_length * 0.4)
        chorus_end = int(self.music_length * 0.8)

        # solver has to find the capacity for each section in ranges we define
        intro_capacity = self.model.NewIntVar(4, 5, 'intro_capacity')
        vers_capacity = self.model.NewIntVar(5, 6, 'verse_capacity')
        chorus_capacity = self.model.NewIntVar(6, 8, 'chorus_capacity')
        ending_capacity = self.model.NewIntVar(1, 3, 'ending_capacity')

        # manually we set demands of each role for each section, demands will affect
        # how solver will select roles to play
        intro_demands = {'main_melody': 3, 'riff': 3, 'accompaniment': 2, 'sub_melody': 2, 'pad': 2, 'bass': 1, 'drum': 1}
        vers_demands = {'main_melody': 3, 'riff': 3, 'accompaniment': 2, 'sub_melody': 2, 'pad': 2, 'bass': 1, 'drum': 1}
        chorus_demands = {'main_melody': 2, 'riff': 2, 'accompaniment': 2, 'sub_melody': 2, 'pad': 2, 'bass': 1, 'drum': 1}
        ending_demands = {'main_melody': 2, 'riff': 2, 'accompaniment': 2, 'sub_melody': 1, 'pad': 2, 'bass': 1, 'drum': 1}

        for role, durations in role_to_durations.items():
            for k, duration in enumerate(durations):
                        suffix = f'{role}_{k}'  # e.x pad_0

                        # depends on track length, find the maximum number of repeats for each track
                        maximum_possible_repeats = self.music_length // duration
                        for i in range(0, max(1, maximum_possible_repeats)):
                            start_opt = self.model.NewIntVar(self.bar_duration * i, (self.bar_duration * i) + duration, f'start_opt_{suffix}_{i}')
                            end_opt = self.model.NewIntVar(self.bar_duration * i, (self.bar_duration * i) + duration, f'end_opt_{suffix}_{i}')

                            is_present_opt = self.model.NewBoolVar(f'is_present_opt_{suffix}_{i}')
                            interval_opt_ = self.model.NewOptionalIntervalVar(
                                start_opt, duration, end_opt,
                                is_present_opt, f'interval_opt_{suffix}_{i}')
                            self.role_to_tracks[suffix].append(
                                Track(start_opt, end_opt, interval_opt_, is_present_opt))

                            if (duration * i) < intro_end:
                                role_to_intervals_intro[suffix].append(interval_opt_)
                            if intro_end < (duration * i) < verse_end:
                                role_to_intervals_vers[suffix].append(interval_opt_)
                            if verse_end < (duration * i) < chorus_end:
                                role_to_intervals_chorus[suffix].append(interval_opt_)
                            else:
                                role_to_intervals_ending[suffix].append(interval_opt_)

                            if role == 'drum':
                                if random.randint(0, 9) >= 2: # for 80% drum is should be available
                                    is_present_opt = 1

                            self.role_to_repeats[suffix].append(is_present_opt)



        intervals_intro = [interval for intervals in role_to_intervals_intro.values() for interval in intervals]
        intervals_verse = [interval for intervals in role_to_intervals_vers.values() for interval in intervals]
        intervals_chorus = [interval for intervals in role_to_intervals_chorus.values() for interval in intervals]
        intervals_ending = [interval for intervals in role_to_intervals_ending.values() for interval in intervals]
        repeats = [repeat for repeats in self.role_to_repeats.values() for repeat in repeats]

        demands_intro = [intro_demands['_'.join(role.split('_')[:2]) if role.startswith(('main_', 'sub_')) else role.split('_')[0]] for role, _intervals in role_to_intervals_intro.items() for _ in _intervals]
        demands_verse = [vers_demands['_'.join(role.split('_')[:2]) if role.startswith(('main_', 'sub_')) else role.split('_')[0]] for role, _intervals in role_to_intervals_vers.items() for _ in _intervals]
        demands_chorus = [chorus_demands['_'.join(role.split('_')[:2]) if role.startswith(('main_', 'sub_')) else role.split('_')[0]] for role, _intervals in role_to_intervals_chorus.items() for _ in _intervals]
        demands_ending = [ending_demands['_'.join(role.split('_')[:2]) if role.startswith(('main_', 'sub_')) else role.split('_')[0]] for role, _intervals in role_to_intervals_ending.items() for _ in _intervals]

        #objectives
        self.model.AddCumulative(intervals_intro, demands_intro, intro_capacity)
        self.model.AddCumulative(intervals_verse, demands_verse, vers_capacity)
        self.model.AddCumulative(intervals_chorus, demands_chorus, chorus_capacity)
        self.model.AddCumulative(intervals_ending, demands_ending, ending_capacity)


        self.model.Maximize(sum(repeats))


    def correct_tempo(self):
        """
        This function will find the actual tempo of the tracks except Drum
        and will assign most rated one (usually we have just a unique tempo)
        to the track with role: drum
        """
        tempo_count = {}
        for role, midis in self.role_to_midis.items():
            for midi in midis:
                tempo_count[midi.getTempo()] = tempo_count.get(midi.getTempo(), 0) + 1

        most_frequent_tempo = max(tempo_count, key=tempo_count.get)
        for role, midis in self.role_to_midis.items():
            if role == 'drum':
                for midi in midis:
                    midi.setTempo(most_frequent_tempo)

    def solve(self) -> None:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 100
        status = solver.Solve(self.model)
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            shifted_midis = []
            role_to_shifted_midi = defaultdict()
            for role, midis in self.role_to_midis.items():
                    for i, midi in enumerate(midis):
                        suffix = f'{role}_{i}' # e.x : pad_0
                        for j in range(len(self.role_to_repeats[suffix])):
                            if solver.Value(self.role_to_repeats[suffix][j]):
                                shifted_midi = midi.shift(solver.Value(self.role_to_tracks[suffix][j].start))
                                if suffix in role_to_shifted_midi:
                                    role_to_shifted_midi[suffix].append(shifted_midi)
                                else:
                                    role_to_shifted_midi[suffix] = [shifted_midi]
                                shifted_midis.append(shifted_midi)
                                if (role == 'drum') and (j in [0, 1]):
                                    print(shifted_midi.track)


            merged_tracks = []
            for role, tracks_of_same_role in role_to_shifted_midi.items():
                inner_merged = inner_merge(tracks_of_same_role, self.music_length)
                merged_tracks.append(inner_merged)



            merged = merge(merged_tracks)
            old_merged_version = merge(shifted_midis)
            merged.save(f'out/{self.timestamp}/tune.mid')
            old_merged_version.save(f'out/{self.timestamp}/tune_notmerged_sounds.mid')

        elif status == cp_model.INFEASIBLE:
            print(f'No solution found: the problem was proven infeasible')
        elif status == cp_model.MODEL_INVALID:
            print('No solution found: invalid model')
        else:
            print('No solution found: the solver was stopped before reaching an endpoint')


