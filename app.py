from flask import Flask, request, render_template_string
import subprocess
import pandas as pd
from itertools import groupby
import yaml

# Initialize the Flask application
app = Flask(__name__)

INPUT_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Music Generation</title>
  <style>
    body { 
      color: white; 
      background-color: black; 
      font-family: Arial, sans-serif; 
    }
    .container {
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding-top: 50px;
    }
    form {
      display: grid;
      grid-template-columns: auto auto;
      gap: 10px;
      justify-content: center;
      align-items: center;
    }
    .label {
      text-align: right;
      font-size: 20px;
    }
    select {
      padding: 10px;
      background-color: black;
      color: white;
      font-size: 18px;
      border: 1px solid #fff;
    }
    button {
      grid-column: span 2;
      padding: 10px 20px;
      margin-top: 10px;
    }
    h1 {
        width: 100%;
        text-align: center;
        padding-top: 20px;
    }
  </style>
</head>
<body>
  <h1>Music Generation</h1>
  <div class="container">
    <form method="post">
      <div class="label">Music Length:</div>
      <select name="music_length">
        {% for length, value in music_length_options.items() %}
          <option value="{{ value }}">{{ length }}</option>
        {% endfor %}
      </select>
      <div class="label">BPM:</div>
      <select name="bpm">
        {% for bpm in bpm_options %}
          <option value="{{ bpm }}">{{ bpm }}</option>
        {% endfor %}
      </select>

      <div class="label">Key:</div>
      <select name="key">
        {% for key in key_options %}
          <option value="{{ key }}">{{ key }}</option>
        {% endfor %}
      </select>

      <div class="label">Time Signature:</div>
      <select name="time_signature">
        {% for ts in time_signature_options %}
          <option value="{{ ts }}">{{ ts }}</option>
        {% endfor %}
      </select>

      <div class="label">Number of Measures:</div>
      <select name="num_measures">
        {% for num in num_measures_options %}
          <option value="{{ num }}">{{ num }}</option>
        {% endfor %}
      </select>

      <div class="label">Genre:</div>
      <select name="genre">
        {% for genre in genre_options %}
          <option value="{{ genre }}">{{ genre }}</option>
        {% endfor %}
      </select>

      <div class="label">Rhythm:</div>
      <select name="rhythm">
        {% for rhythm in rhythm_options %}
          <option value="{{ rhythm }}">{{ rhythm }}</option>
        {% endfor %}
      </select>

      <div class="label">Chord Progression:</div>
      <select name="chord_progression" style="width: 500px">
        {% for chord in chord_progression_options %}
          <option value="{{ chord }}">{{ chord }}</option>
        {% endfor %}
      </select>
      
      <div class="label">Generate Notes (or sample):</div>
      <input type="checkbox" name="isgenerate" id="isgenerate">


      <button type="submit" style="font-size:18px">Generate</button>
    </form>
  </div>
</body>
</html>
"""

# Route for handling the input form
@app.route('/', methods=['GET', 'POST'])
def home():
    with open('cfg/metadata.yaml') as f:
        cfg = yaml.safe_load(f)

    main_df = pd.read_csv('dataset/concatenated_df.csv', sep='\t')
    df = clean_chord_progression(main_df)
    df = df[df['track_role'] != 'drum']
    music_length_options = {'1:00': 1, '2:00': 2, '3:00': 3, '4:00': 4, '5:00':5, '10:00': 10}
    bpm_options = sorted(df['bpm'].unique())
    key_options = sorted(df['audio_key'].unique())
    time_signature_options = ['4/4']
    num_measures_options = [8]
    genre_options = sorted(main_df['genre'].unique())
    rhythm_options = ['standard']
    chord_progression_options = sorted(cfg['chord_progression'])

    if request.method == 'POST':
        # Extract the form values
        bpm = request.form['bpm']
        key = request.form['key']
        time_signature = request.form['time_signature']
        num_measures = request.form['num_measures']
        genre = request.form['genre']
        rhythm = request.form['rhythm']
        chord_progression = request.form['chord_progression']
        music_length = request.form['music_length']

        # Check if the checkbox is checked
        isgenerate = 'isgenerate' in request.form
        # Execute the generate.py script with the parameters
        if not isgenerate:
            # No need to generate midi files, we need to select them from database
            command = f'python generate.py --bpm {bpm} --key {key} --time_signature {time_signature} --num_measures {num_measures} --genre {genre} ' \
                      f'--rhythm {rhythm} --chord_progression {chord_progression} --music_length {music_length}'
        else:
            # Generate sample by using model checkpoints
            command = f'python generate.py --bpm {bpm} --key {key} --time_signature {time_signature} --num_measures {num_measures} --genre {genre} ' \
                      f'--rhythm {rhythm} --chord_progression {chord_progression} --music_length {music_length} --generate_samples'
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()
        # Return the result (for now just a confirmation message)
        return f'Music generation initiated with parameters: BPM={bpm}, Key={key}, Time Signature={time_signature}, Number of Measures={num_measures}, Genre={genre}, Rhythm={rhythm}, Chord Progression={chord_progression}'
    return render_template_string(INPUT_FORM,
                                  music_length_options = music_length_options,
                                  bpm_options=bpm_options,
                                  key_options=key_options,
                                  time_signature_options=time_signature_options,
                                  num_measures_options=num_measures_options,
                                  genre_options=genre_options,
                                  rhythm_options=rhythm_options,
                                  chord_progression_options=chord_progression_options)

def clean_chord_progression(df):
        df.chord_progressions = df.chord_progressions.apply(
            lambda cp: str([key for key, _ in groupby(cp[2:-2].replace('\'', '').split(', '))]
                )[1:-1].replace('\'', '').replace(', ', '-'))
        return df

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
