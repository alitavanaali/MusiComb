from __future__ import annotations

import random
from collections import defaultdict
from itertools import groupby
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml
import itertools
from commu_file import CommuFile


class CommuDataset:

    def __init__(self) -> None:
        #self.df = pd.read_csv('dataset/commu_meta.csv')
        self.df = pd.read_csv('dataset/concatenated_df.csv', sep='\t')
        self._preprocess()

        with open('cfg/chord_progressions.yaml') as f:
            self.fold_to_unfold = yaml.safe_load(f)

    def get_track_roles(self) -> List[str]:
        return self.df.track_role.unique().tolist()

    def get_drum(self, genre, time_signature, num_measures):
        """
        This function will retrieve from database a drum midi track in a dictionary
        to apply the query we need genre, time_signature, num_measures

        because in Groove midi drum database, there is no track of genres: cinematic, newage
        so first we check the input genre, if it's one them we change it to rock which is the
        most populated genre in database
        """
        genre = 'rock' if genre in ['cinematic', 'newage'] else genre

        df_drum = self.df[
            (self.df.track_role == 'drum') &
            (self.df.genre == genre) &
            (self.df.beat_type == 'beat') &
            (self.df.time_signature == time_signature) &
            (self.df.num_measures == num_measures)
            ]

        if df_drum.empty:
                print('No sample satifies the drum with current number of measures. Searching for higher measures...')

                df_drum = self.df[
                    (self.df.track_role == 'drum') &
                    (self.df.genre == genre) &
                    (self.df.beat_type == 'beat') &
                    (self.df.time_signature == time_signature)
                    & (self.df.num_measures > num_measures)
                    ]
                if df_drum.empty:
                    raise ValueError('No Drum Found!')

        # make a sample to dataframe
        df_drum = df_drum.sample()

        role_to_midis = defaultdict(list)

        for i in df_drum.index:
            sample = df_drum[df_drum.index == i]
            role = sample.track_role.item()
            name = f'{role}_{i}'
            midi = CommuFile(
                    f'dataset/groove_drum/{sample.id.item()}',
                    name,
                    sample.instrument.item())
            role_to_midis[role].append(midi)
        return role_to_midis

    def sample_midis(
            self,
            bpm: int,
            key: str,
            time_signature: str,
            num_measures: int,
            genre: str,
            rhythm: str,
            chord_progression: str) -> Dict[str, List[CommuFile]]:
        df_samples = self._get_sample_foreach_role(
            bpm,
            key,
            time_signature,
            num_measures,
            genre,
            rhythm,
            chord_progression)

        
        valid_roles = set(df_samples.track_role.unique())
        midi_count = len(df_samples)
        indexes = df_samples.index.tolist()
        while midi_count < len(self.get_track_roles()):
            try:
                role = random.choice(list(valid_roles))
                sample = self._get_sample(
                    role,
                    bpm,
                    key,
                    time_signature,
                    num_measures,
                    rhythm)
            except IndexError:  # no more valid track roles
                break
            except ValueError:  # no sample satifies the query
                valid_roles = valid_roles - set(role)
                continue
            if sample.index.item() in indexes:  # do not sample same entry twice
                continue
            
            df_samples = pd.concat([df_samples, sample])
            indexes.append(sample.index.item())
            midi_count += 1
        
        role_counts = defaultdict(int)
        role_to_midis = defaultdict(list)

        for i in df_samples.index:
            sample = df_samples[df_samples.index == i]
            role = sample.track_role.item()
            name = f'{role}_{role_counts[role]}'
            if role != 'drum':
                midi = CommuFile(
                    f'dataset/commu_midi/{sample.split.item()}/raw/{sample.id.item()}.mid',
                    name,
                    sample.instrument.item())
            else:
                midi = CommuFile(
                    f'dataset/groove_drum/{sample.id.item()}',
                    name,
                    sample.instrument.item())
            role_counts[role] += 1
            role_to_midis[role].append(midi)

        return role_to_midis
    
    def sample_instrument(self, track_role: str) -> str:
        return self._sample('instrument', track_role).split('-')[0]

    def sample_pitch_range(self, track_role: str) -> str:
        return self._sample('pitch_range', track_role, 'train', weighted=True)

    def sample_min_max_velocity(self, track_role: str) -> Tuple[int, int]: 
        min_v = 0
        max_v = 0
        while min_v >= max_v:
            min_v = self._sample('min_velocity', track_role, 'train', weighted=True)
            max_v = self._sample('max_velocity', track_role, 'train', weighted=True)
        return min_v, max_v

    def unfold(self, chord_progression: str) -> str:
        # BEFORE:
        # 'Am-C-G-Dm-Am-C-G-D'
        # AFTER:
        # 'Am-Am-Am-Am-Am-Am-Am-Am-C-C-C-C-C-C-C-C-G-G-G-G-G-G-G-G-
        #  Dm-Dm-Dm-Dm-Dm-Dm-Dm-Dm-Am-Am-Am-Am-Am-Am-Am-Am-
        #  C-C-C-C-C-C-C-C-G-G-G-G-G-G-G-G-D-D-D-D-D-D-D-D'
        return self.fold_to_unfold[chord_progression]

    def _clean_chord_progression(self) -> None:
        # BEFORE:
        # "[['Am', 'Am', 'Am', 'Am', 'Am', 'Am', 'Am', 'Am', 
        #    'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 
        #    'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 
        #    'Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Dm', 'Dm', 
        #    'Am', 'Am', 'Am', 'Am', 'Am', 'Am', 'Am', 'Am', 
        #    'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 
        #    'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 
        #    'D', 'D', 'D', 'D', 'D', 'D', 'D', 'D']]"
        # AFTER:
        # 'Am-C-G-Dm-Am-C-G-D'
        self.df.chord_progression = self.df.chord_progression.apply(
            lambda cp: str([key for key, _ in groupby(cp[2:-2].replace('\'', '').split(', '))]
                )[1:-1].replace('\'', '').replace(', ', '-'))


    def _get_sample(
            self,
            track_role: str,
            bpm: int,
            key: str,
            time_signature: str,
            num_measures: int,
            rhythm: str) -> pd.DataFrame:
        return self.df[
            (self.df.track_role == track_role) &
            (self.df.bpm == bpm) &
            (self.df.key == key) &
            (self.df.time_signature == time_signature) &
            (self.df.num_measures == num_measures) &
            (self.df.rhythm == rhythm)

        ].sample()


    def _get_sample_foreach_role(
            self,
            bpm: int,
            key: str,
            time_signature: str,
            num_measures: int,
            genre: str,
            rhythm: str,
            chord_progression: str) -> pd.DataFrame:

        df_query = self.df[
            (self.df.track_role != 'drum') &
            (self.df.bpm == bpm) &
            (self.df.key == key) &
            (self.df.time_signature == time_signature) &
            (self.df.num_measures == num_measures) &
            (self.df.rhythm == rhythm)
            ]
        # check optional chord_progression
        if chord_progression != 'none':
            df_query = df_query[df_query.chord_progression == chord_progression]

        genre_for_drum = 'rock' if genre in ['cinematic', 'newage'] else genre
        df_drum = self.df[
            (self.df.track_role == 'drum') &
            (self.df.genre == genre_for_drum) &
            (self.df.beat_type == 'beat') &
            (self.df.time_signature == time_signature) &
            (self.df.num_measures == num_measures)
        ]

        if df_drum.empty:
            print(f'No sample satifies the drum with {num_measures} number of measures. Searching for higher measures...')
            df_drum = self.df[
                (self.df.track_role == 'drum') &
                (self.df.genre == genre_for_drum) &
                (self.df.beat_type == 'beat') &
                (self.df.time_signature == time_signature)
                & (self.df.num_measures > num_measures)
                ]
            if df_drum.empty:
                raise ValueError('No Drum Found!')


        if df_query.empty:
            raise ValueError(
                'No sample satifies the given conjunction of bpm, key, time signature, ' +
                'number of meaures, genre, rhythm, and chord progression values. ' +
                'Please try again with different values.')

        df_query = pd.concat([df_query, df_drum], ignore_index=True)
        
        samples = []
        for role in df_query.track_role.unique():
            df_role = df_query[df_query.track_role == role]
            if role != 'drum':
                samples.append(df_role.sample(2) if len(df_role) > 1 else df_role.sample())
            else:
                samples.append(df_role.sample() if len(df_role) > 1 else df_role.sample())

        return pd.concat(samples)

    def _preprocess(self) -> None:
        self.df.drop(columns=self.df.columns[0], inplace=True)
        self.df.rename(columns={
            'audio_key': 'key',
            'chord_progressions': 'chord_progression',
            'inst': 'instrument',
            'sample_rhythm': 'rhythm',
            'split_data': 'split'
        }, inplace=True)
        self._clean_chord_progression()

    def _sample(self, target: str, track_role: str, split: str | None = None, weighted: bool = False) -> Any:
        if split:
            df = self.df[(self.df.track_role == track_role) & (self.df.split == split)]
        else:
            df = self.df[self.df.track_role == track_role]
        counts = df[target].value_counts()
        return counts.sample(weights=counts.values if weighted else None).index.item()


DSET = CommuDataset()  # singleton


