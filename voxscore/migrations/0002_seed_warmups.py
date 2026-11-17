"""
Data migration: the starter warmup library (wireframe screen 4).

Written as a migration, not a fixture, so every database -- a fresh clone, the test database,
CI, PythonAnywhere -- gets the library from `migrate` alone. The exercises are written for
VoxScore from common practice in each tradition; they are not copied from any book.

Patterns are semitones above the starting note. The data is frozen here on purpose: a
migration must keep producing the same rows even if the code changes later.
"""

from django.db import migrations

WARMUPS = [
    # --- Western -------------------------------------------------------------------------
    dict(slug="lip-trill-sirens", name="Lip trill sirens", tradition="western", focus="breath",
         minutes=3, pattern=[0, 4, 7, 12, 7, 4, 0], syllables="brr brr brr brr brr brr brr",
         default_start=55, steps=5, tempo_bpm=84,
         instructions="Relax your lips and blow gently so they flutter (a 'brr' sound), then slide "
                      "through the pattern without stopping the airflow. If the trill stops, "
                      "press lightly on your cheeks with two fingers."),
    dict(slug="five-note-scale-ah", name="Five-note scale on 'ah'", tradition="western",
         focus="range", minutes=3, pattern=[0, 2, 4, 5, 7, 5, 4, 2, 0],
         syllables="ah ah ah ah ah ah ah ah ah", default_start=57, steps=6, tempo_bpm=92,
         instructions="Sing up and down five notes on an open 'ah'. Keep the jaw loose and the "
                      "tone the same on every note. Each repetition moves up a half step."),
    dict(slug="arpeggio-1358", name="Arpeggio 1-3-5-8", tradition="western", focus="range",
         minutes=3, pattern=[0, 4, 7, 12, 7, 4, 0], syllables="do mi sol do sol mi do",
         default_start=55, steps=5, tempo_bpm=88,
         instructions="Sing the notes of the major chord up to the octave and back. Aim for the "
                      "top note from above, not by reaching or pushing."),
    # --- Indian classical ----------------------------------------------------------------
    dict(slug="sargam-alankar", name="Sargam alankar", tradition="indian", focus="agility",
         minutes=5, pattern=[0, 2, 4, 2, 4, 5, 4, 5, 7, 5, 7, 9],
         syllables="Sa Re Ga Re Ga Ma Ga Ma Pa Ma Pa Dha", default_start=60, steps=3,
         tempo_bpm=80,
         instructions="Sing the swaras in groups of three, each group starting one note higher "
                      "(Sa Re Ga, Re Ga Ma, Ga Ma Pa...). Start slowly against the drone on Sa, "
                      "then speed up once every note is clean."),
    dict(slug="sa-pa-sa", name="Sa-Pa-Sa with drone", tradition="indian", focus="blend",
         minutes=4, pattern=[0, 7, 12, 7, 0], syllables="Sa Pa Sa Pa Sa", default_start=60,
         steps=1, tempo_bpm=50,
         instructions="Turn the drone on to your Sa. Hold each note for its full length and "
                      "listen for the beating sound to disappear when you lock in tune."),
    dict(slug="aakar-taan", name="Aakar taan", tradition="indian", focus="agility", minutes=4,
         pattern=[0, 2, 4, 5, 7, 9, 11, 12, 11, 9, 7, 5, 4, 2, 0],
         syllables="aa aa aa aa aa aa aa aa aa aa aa aa aa aa aa", default_start=57, steps=3,
         tempo_bpm=100,
         instructions="Run the full scale up and down on an open 'aa', keeping each note "
                      "distinct without breaking the vowel. Keep the throat relaxed as you speed up."),
    # --- A cappella ----------------------------------------------------------------------
    dict(slug="vowel-blend", name="Vowel blend chords", tradition="acappella", focus="blend",
         minutes=4, pattern=[0, 4, 7, 4, 0], syllables="oo oh ah oh oo", default_start=55,
         steps=3, tempo_bpm=60,
         instructions="Sing each note on a new vowel, matching the vowel shape a group would use. "
                      "In rehearsal, split the notes across voices and hold them as a chord."),
    dict(slug="third-tuning", name="Major and minor third tuning", tradition="acappella",
         focus="blend", minutes=3, pattern=[0, 4, 0, 3, 0], syllables="mm mm mm mm mm",
         default_start=57, steps=3, tempo_bpm=60,
         instructions="Hum the root, then the major third, the root, and the minor third. Notice "
                      "how close the two thirds are: this is where group tuning usually drifts."),
    # --- Other global --------------------------------------------------------------------
    dict(slug="ng-hum-resonance", name="'Ng' hum for resonance", tradition="other",
         focus="resonance", minutes=2, pattern=[0, 2, 4, 2, 0], syllables="ng ng ng ng ng",
         default_start=57, steps=5, tempo_bpm=84,
         instructions="Hum on 'ng' (as at the end of 'sing') and feel the buzz in your face. "
                      "Then open to 'ah' on the last note while keeping the same buzz."),
    dict(slug="breath-ladder", name="Breath ladder", tradition="other", focus="breath",
         minutes=2, pattern=[0, 0, 0, 0], syllables="ss ss ss ss", default_start=60, steps=1,
         tempo_bpm=60,
         instructions="Breathe in for 4 beats, then let the air out on a steady 'ss' for as many "
                      "beats as you can. Add one beat each round. Keep shoulders down."),
    dict(slug="octave-flips", name="Octave flips (yodel-style)", tradition="other",
         focus="range", minutes=3, pattern=[0, 12, 0, 12, 0], syllables="yo dl yo dl yo",
         default_start=52, steps=4, tempo_bpm=76,
         instructions="Flip between chest voice and head voice an octave apart, the way Alpine "
                      "yodelling does. Let the break happen instead of hiding it."),
]


def add_warmups(apps, schema_editor):
    WarmupExercise = apps.get_model("voxscore", "WarmupExercise")
    for row in WARMUPS:
        WarmupExercise.objects.update_or_create(slug=row["slug"], defaults=row)


def remove_warmups(apps, schema_editor):
    WarmupExercise = apps.get_model("voxscore", "WarmupExercise")
    WarmupExercise.objects.filter(slug__in=[w["slug"] for w in WARMUPS]).delete()


class Migration(migrations.Migration):
    dependencies = [("voxscore", "0001_initial")]
    operations = [migrations.RunPython(add_warmups, remove_warmups)]
