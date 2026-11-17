"""
The Learn screen's lessons (wireframe screen 8), kept as plain data rather than database rows:
they ship with the code, change with a commit, and need no admin.

Each lesson has an `example`: MIDI notes the page can play and the tutor can talk about, and
`fallback`, the answer the tutor gives for this topic when no AI model is available.
"""

LESSONS = [
    {
        "slug": "intervals",
        "title": "Intervals",
        "body": (
            "An interval is the distance between two notes, counted in half steps (semitones). "
            "A major third is 4 half steps (C to E) and sounds bright; a minor third is 3 half "
            "steps (C to E-flat) and sounds darker. Harmony in a cappella is mostly built from "
            "thirds and sixths."
        ),
        "example": [60, 64, 60, 63],
        "example_label": "Major third (C to E), then minor third (C to E-flat)",
        "fallback": (
            "Count half steps from the lower note to the higher one: 3 is a minor third, 4 a "
            "major third, 7 a perfect fifth and 12 an octave. Try singing the lower note, then "
            "sliding up until the second note locks in."
        ),
    },
    {
        "slug": "scales",
        "title": "Scales and modes",
        "body": (
            "A major scale follows the pattern whole, whole, half, whole, whole, whole, half. "
            "In sargam that is Sa Re Ga Ma Pa Dha Ni Sa; in solfege, Do Re Mi Fa Sol La Ti Do. "
            "The natural minor scale lowers the 3rd, 6th and 7th notes."
        ),
        "example": [60, 62, 64, 65, 67, 69, 71, 72],
        "example_label": "C major scale (Sa Re Ga Ma Pa Dha Ni Sa)",
        "fallback": (
            "A scale is a ladder of notes inside one key. Sing it slowly up and down on one "
            "vowel; the half steps (Ga-Ma and Ni-Sa in major) are where most singers drift."
        ),
    },
    {
        "slug": "chords",
        "title": "Chords and harmony",
        "body": (
            "A triad stacks two thirds: root, third and fifth. C major is C-E-G. In a four-part "
            "a cappella arrangement, the bass usually takes the root, and the other voices share "
            "the third, the fifth and a doubled note."
        ),
        "example": [60, 64, 67],
        "example_label": "C major triad (C, E, G)",
        "fallback": (
            "Harmony is two or more notes at once. The easiest harmony to sing is a third "
            "below the melody, following its rhythm; VoxScore's harmony helper starts there."
        ),
    },
    {
        "slug": "rhythm",
        "title": "Rhythm and meter",
        "body": (
            "The time signature tells you how beats are grouped. 4/4 has four quarter-note beats "
            "per bar; 3/4 has three (a waltz); 6/8 has two groups of three eighth notes. Sing "
            "with the metronome and feel where beat 1 lands."
        ),
        "example": [67, 67, 67, 67],
        "example_label": "Four steady beats",
        "fallback": (
            "Count out loud while you clap: 1 2 3 4 in 4/4. Then sing the melody while tapping "
            "the beat. VoxScore's rhythm score measures how close each note starts to the beat."
        ),
    },
    {
        "slug": "reading",
        "title": "Reading sheet music",
        "body": (
            "Notes higher on the staff are higher in pitch. In treble clef the lines from the "
            "bottom are E G B D F, and the spaces spell F A C E. A filled note with a stem is a "
            "quarter note; an open one is a half note."
        ),
        "example": [64, 67, 71, 74, 77],
        "example_label": "The treble clef lines: E G B D F",
        "fallback": (
            "Start by following the shape: notes going up the staff mean your voice goes up. "
            "Sing into the Studio and compare the score VoxScore writes to what you sang."
        ),
    },
    {
        "slug": "sargam",
        "title": "Sargam and ragas",
        "body": (
            "Hindustani music names the notes Sa Re Ga Ma Pa Dha Ni. Sa is the tonic and can be "
            "any pitch you choose, which is why singers practise with a tanpura drone on Sa. A "
            "raga is a set of notes plus rules for how to move between them."
        ),
        "example": [60, 62, 64, 65, 67, 69, 71, 72],
        "example_label": "Bilawal thaat (like the major scale), Sa to Sa",
        "fallback": (
            "Set the Practice drone to your Sa and sing each swar slowly against it. Listen for "
            "the beating sound to disappear: that is the note locking in tune."
        ),
    },
    {
        "slug": "arranging",
        "title": "Arranging basics",
        "body": (
            "A simple a cappella arrangement has a melody, a bass line on the chord roots, and "
            "one or two inner parts on the remaining chord tones. Record the melody first in "
            "the Studio, then add parts on top one at a time."
        ),
        "example": [67, 64, 60, 48],
        "example_label": "Melody, inner parts and bass on one chord",
        "fallback": (
            "Start with melody and bass, then add the part that fills the missing chord tone. "
            "Keep inner parts smooth: move to the nearest note of the next chord."
        ),
    },
]

BY_SLUG = {lesson["slug"]: lesson for lesson in LESSONS}


def get(slug):
    return BY_SLUG.get(slug) or LESSONS[0]
