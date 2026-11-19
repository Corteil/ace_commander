"""The keyboard as the badge's buttons, joystick and Keyboard Hexpansion
(Raspberry Pi host).

- Arrow keys: the joystick (as a keyboard's arrows already are on the badge:
  the game's Pad counts them as the joystick). Enter: confirm (the joystick
  pressed in); Esc: cancel.
- F1-F6: the badge's buttons A-F (the letter keys are the game's keyboard
  keys, so they can't be the badge buttons too). F7: the joystick pressed in.
- Letters, digits, symbols, Space, Backspace, Tab, Shift, Ctrl: the Keyboard
  Hexpansion's keys, so every keyboard key the game knows works as on the badge
  (Elite's keys, the search and name pages).
- Off the flight (docked, the title, the menus; Brian, 2026-11-19: "when
  docked the letter keys on the keyboard act the same as the badge keys, apart
  when entering text"), the letter keys A-F are the badge's buttons too, as
  well as keyboard keys: C chooses, F goes back, A launches, B the next tab (on
  the Galactic chart's cursor: find), and so on. B stays buy where it buys
  (Market, Equip ship, Ship stats: build 93). Not in flight (C is the docking
  computer, F fires, A and D steer) and not on the typing pages.
"""
import pygame

from pi_firmware import (BADGE, KEYBOARD, STICK, TAB, Button, ButtonDownEvent, ButtonUpEvent)

# a letter that is the keyboard's key and the badge's button at once
AS_BUTTONS = "ABCDEF"
BOTH = {c: Button(c, "PiKey", [KEYBOARD[c], BADGE[c]]) for c in AS_BUTTONS}

SPECIAL = {
    pygame.K_UP: KEYBOARD["UP"], pygame.K_DOWN: KEYBOARD["DOWN"],
    pygame.K_LEFT: KEYBOARD["LEFT"], pygame.K_RIGHT: KEYBOARD["RIGHT"],
    pygame.K_RETURN: KEYBOARD["ENTER"], pygame.K_KP_ENTER: KEYBOARD["ENTER"],
    pygame.K_ESCAPE: KEYBOARD["ESCAPE"], pygame.K_BACKSPACE: KEYBOARD["BACKSPACE"],
    pygame.K_SPACE: KEYBOARD["SPACE"], pygame.K_TAB: TAB,
    pygame.K_LSHIFT: KEYBOARD["SHIFT"], pygame.K_RSHIFT: KEYBOARD["SHIFT"],
    pygame.K_LCTRL: KEYBOARD["CTRL"], pygame.K_RCTRL: KEYBOARD["CTRL"],
    pygame.K_LALT: KEYBOARD["ALT"],
    pygame.K_F1: BADGE["A"], pygame.K_F2: BADGE["B"], pygame.K_F3: BADGE["C"],
    pygame.K_F4: BADGE["D"], pygame.K_F5: BADGE["E"], pygame.K_F6: BADGE["F"],
    pygame.K_F7: STICK["SELECT"],
}


class Keys:
    """pygame key events in, the game's button events out (on the stand-in bus).
    A key's button is remembered at key-down, so its key-up matches even if
    Shift changed the character in between."""

    def __init__(self, bus, as_buttons=None):
        self.bus = bus
        self.as_buttons = as_buttons or (lambda c: False)  # True: letter c is the badge's button too
        self.down = {}          # pygame key -> the Button sent for it

    def button(self, event):
        b = SPECIAL.get(event.key)
        if b is not None:
            return b
        if pygame.K_a <= event.key <= pygame.K_z:
            c = chr(event.key).upper()
            if c in BOTH and self.as_buttons(c):
                return BOTH[c]
            return KEYBOARD[c]
        if pygame.K_0 <= event.key <= pygame.K_9:
            return KEYBOARD[chr(event.key)]
        ch = getattr(event, "unicode", "")
        return KEYBOARD.get(ch) if ch else None

    def handle(self, event):
        """Pass a pygame event on. True if it was a key the game knows."""
        if event.type == pygame.KEYDOWN:
            if event.key in self.down:
                return True     # key repeat: the badge sends one down per press
            b = self.button(event)
            if b is None:
                return False
            self.down[event.key] = b
            self.bus.send(ButtonDownEvent(b))
            return True
        if event.type == pygame.KEYUP:
            b = self.down.pop(event.key, None)
            if b is None:
                return False
            self.bus.send(ButtonUpEvent(b))
            return True
        return False

    def release_all(self):
        """Window lost focus: let go of every key, as the badge would."""
        for b in self.down.values():
            self.bus.send(ButtonUpEvent(b))
        self.down = {}
