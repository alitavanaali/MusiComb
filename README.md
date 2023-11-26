# MusiComb

MusiComb is a program born as an extension of Hyun et al., 2022 ([paper](https://arxiv.org/abs/2211.09385) | [code](https://github.com/POZAlabs/ComMU-code)) and aimed at tackling the *combinatorial music generation* task. 

## Setup

1. Clone the repo and `cd` into its directory:
    ```
    $ git clone https://github.com/alitavanaali/musicomb.git
    $ cd midicomb
    ```

1. Create a virtual environment and install the required packages:
    ```
    $ python -m venv .venv
    $ source .venv/bin/activate
    $ pip install -r requirements.txt
    ```

1. Unzip the dataset:
    ```
    $ tar -xvf dataset/commu_midi.tar -C dataset/
    ```
    You should get the following directory structure:
    ```
    dataset
    ├── commu_meta.csv
    ├── commu_midi
    │   ├── train
    │   │   └── raw
    │   │       └── midifiles(.mid)
    │   └── val
    │       └── raw
    │           └── midifiles(.mid)
    ├── commu_midi.tar
    └── README.md
    ```

1. **[OPTIONAL]** If you want the samples to be generated (see the following section), download the model weights from [here](https://drive.google.com/file/d/1y0wl9JO8od3pLOMSxN8NwLy1PCJCyTGL/view?usp=share_link) and move them into the [`ckpt`](ckpt) directory:
    ```
    ckpt
    ├── checkpoint_best.pt
    └── README.md
    ```
    **Note:** the weights are provided by Hyun et al. together with their implementation.

## Run

Run `generate.py` with its required arguments, e.g.
```
$ python generate.py \
--bpm 130 \
--key aminor \
--time_signature 4/4 \
--num_measures 8 \
--genre newage \
--rhythm standard \
--chord_progression Am-F-C-G-Am-F-C-G
```
You can find a list of legal values for each argument [here](cfg/metadata.yaml).

The above command produces a musical composition by combining samples from the dataset. If you want to combine new, generated samples instead, just add the `--generate_samples` flag, e.g.
```
$ python generate.py \
--bpm 130 \
--key aminor \
--time_signature 4/4 \
--num_measures 8 \
--genre newage \
--rhythm standard \
--chord_progression Am-F-C-G-Am-F-C-G \
--generate_samples
```
**Note:** the above command runs either on CPU or on a single GPU. The available device will be detected automatically.

Once the program successfully terminates, you will find an `out` directory with the following structure:
```
out
└── <date>_<time>
    ├── metadata.yaml
    └── tune.mid
```
where `metadata.yaml` contains the arguments of the corresponding run and `tune.mid` is the generated MIDI file.
