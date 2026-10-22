// PATS MP-16: everything a sketch needs. `src/core/` is plain C++ (no Arduino) and is unit-tested
// on a PC (firmware/test); MP16Board is the hardware layer for both board revisions.
#pragma once

#include "MP16Board.h"
#include "board_pins.h"
#include "core/chord_engine.h"
#include "core/input.h"
#include "core/midi_parser.h"
#include "core/music_theory.h"
