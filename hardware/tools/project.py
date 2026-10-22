"""Write <board>.kicad_pro: net classes (Power = wide tracks) and JLCPCB-safe design rules."""
import json


def netclass(name, track, clearance, via_d, via_drill):
    return {'name': name, 'clearance': clearance, 'track_width': track, 'via_diameter': via_d,
            'via_drill': via_drill, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2,
            'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'wire_width': 6, 'bus_width': 12, 'line_style': 0,
            'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'}


def write(path, power_nets, name, clearance=0.2, classes=None, min_track=0.15):
    """classes: extra net classes {name: (track width mm, [nets])}; they take precedence over Power."""
    classes = classes or {}
    extra = {n for _, nets in classes.values() for n in nets}
    pro = {
        'board': {'design_settings': {
            'defaults': {'board_outline_line_width': 0.1, 'copper_line_width': 0.2},
            'rules': {  # JLCPCB standard 2-layer process allows less; these keep margin
                'min_clearance': min(0.15, clearance), 'min_track_width': min_track, 'min_via_diameter': 0.6,
                'min_through_hole_diameter': 0.3, 'min_via_annular_width': 0.13,
                'min_copper_edge_clearance': 0.3, 'min_hole_to_hole': 0.25, 'min_hole_clearance': 0.25,
                'min_silk_clearance': 0.0, 'min_text_height': 0.8, 'min_text_thickness': 0.12,
                'solder_mask_clearance': 0.05, 'solder_mask_min_width': 0.1},
            'track_widths': [0.0, 0.25, 0.4, 0.6, 1.0],
            'via_dimensions': [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.8, 'drill': 0.4}],
        }},
        'meta': {'filename': name + '.kicad_pro', 'version': 1},
        'net_settings': {
            'classes': [netclass('Default', 0.25, clearance, 0.6, 0.3), netclass('Power', 0.6, clearance, 0.8, 0.4)] +
                       [netclass(c, w, clearance, 0.6, 0.3) for c, (w, _) in sorted(classes.items())],
            'meta': {'version': 3},
            'net_colors': None,
            'netclass_assignments': None,
            'netclass_patterns': [{'netclass': 'Power', 'pattern': n} for n in sorted(set(power_nets) - extra)] +
                                 [{'netclass': c, 'pattern': n} for c, (_, nets) in sorted(classes.items())
                                  for n in sorted(nets)],
        },
        'pcbnew': {'last_paths': {}, 'page_layout_descr_file': ''},
        'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []},
        'sheets': [],
        'text_variables': {},
    }
    with open(path, 'w') as f:
        json.dump(pro, f, indent=2)
        f.write('\n')
