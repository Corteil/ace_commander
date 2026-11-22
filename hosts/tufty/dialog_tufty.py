"""Text entry on the Tufty (builds 122-124): the game's letter picker (picker.py),
which host_tufty gives the Tufty's buttons and the Pad (controls_tufty.PAD_TYPING)
while it is open (platform_tufty.text_dialog).
"""


def LetterDialog(title, ck):
    from ace_commander.picker import LetterPicker
    return LetterPicker(title, ck)
