from __future__ import print_function
# Authors: Alexandre Gramfort <alexandre.gramfort@telecom-paristech.fr>
#          Denis Engemann <denis.engemann@gmail.com>
#          Martin Luessi <mluessi@nmr.mgh.harvard.edu>
#          Eric Larson <larson.eric.d@gmail.com>
#
# License: Simplified BSD

import copy
import os.path as op
import warnings

import numpy as np
from numpy.testing import (assert_array_almost_equal, assert_array_equal,
                           assert_allclose)
from nose.tools import assert_true, assert_raises
from mne.channels import (make_eeg_layout, make_grid_layout, read_layout,
                          find_layout)
from mne.channels.layout import _box_size, _auto_topomap_coords
from mne import pick_types, pick_info
from mne.io import Raw
from mne.io import read_raw_kit
from mne.io.constants import FIFF
from mne.preprocessing.maxfilter import fit_sphere_to_headshape
from mne.utils import _TempDir

warnings.simplefilter('always')

fif_fname = op.join(op.dirname(__file__), '..', '..', 'io',
                    'tests', 'data', 'test_raw.fif')

lout_path = op.join(op.dirname(__file__), '..', '..', 'io',
                    'tests', 'data')

bti_dir = op.join(op.dirname(__file__), '..', '..', 'io', 'bti',
                  'tests', 'data')

fname_ctf_raw = op.join(op.dirname(__file__), '..', '..', 'io', 'tests',
                        'data', 'test_ctf_comp_raw.fif')

fname_kit_157 = op.join(op.dirname(__file__), '..', '..',  'io', 'kit',
                        'tests', 'data', 'test.sqd')

test_info = {
    'ch_names': ['ICA 001', 'ICA 002', 'EOG 061'],
    'chs': [{'cal': 1,
             'ch_name': 'ICA 001',
             'coil_trans': None,
             'coil_type': 0,
             'coord_Frame': 0,
             'eeg_loc': None,
             'kind': 502,
             'loc': np.array([0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0., 1.],
                             dtype=np.float32),
             'logno': 1,
             'range': 1.0,
             'scanno': 1,
             'unit': -1,
             'unit_mul': 0},
            {'cal': 1,
             'ch_name': 'ICA 002',
             'coil_trans': None,
             'coil_type': 0,
             'coord_Frame': 0,
             'eeg_loc': None,
             'kind': 502,
             'loc': np.array([0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0., 1.],
                             dtype=np.float32),
             'logno': 2,
             'range': 1.0,
             'scanno': 2,
             'unit': -1,
             'unit_mul': 0},
            {'cal': 0.002142000012099743,
             'ch_name': 'EOG 061',
             'coil_trans': None,
             'coil_type': 1,
             'coord_frame': 0,
             'eeg_loc': None,
             'kind': 202,
             'loc': np.array([0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0., 1.],
                             dtype=np.float32),
             'logno': 61,
             'range': 1.0,
             'scanno': 376,
             'unit': 107,
             'unit_mul': 0}],
    'nchan': 3}


def test_io_layout_lout():
    """Test IO with .lout files"""
    tempdir = _TempDir()
    layout = read_layout('Vectorview-all', scale=False)
    layout.save(op.join(tempdir, 'foobar.lout'))
    layout_read = read_layout(op.join(tempdir, 'foobar.lout'), path='./',
                              scale=False)
    assert_array_almost_equal(layout.pos, layout_read.pos, decimal=2)
    assert_true(layout.names, layout_read.names)

    print(layout)  # test repr


def test_io_layout_lay():
    """Test IO with .lay files"""
    tempdir = _TempDir()
    layout = read_layout('CTF151', scale=False)
    layout.save(op.join(tempdir, 'foobar.lay'))
    layout_read = read_layout(op.join(tempdir, 'foobar.lay'), path='./',
                              scale=False)
    assert_array_almost_equal(layout.pos, layout_read.pos, decimal=2)
    assert_true(layout.names, layout_read.names)


def test_auto_topomap_coords():
    """Test mapping of coordinates in 3D space to 2D"""
    info = Raw(fif_fname).info.copy()
    picks = pick_types(info, meg=False, eeg=True, eog=False, stim=False)

    # Remove extra digitization point, so EEG digitization points match up
    # with the EEG channels
    del info['dig'][85]

    # Remove head origin from channel locations, so mapping with digitization
    # points yields the same result
    dig_kinds = (FIFF.FIFFV_POINT_CARDINAL,
                 FIFF.FIFFV_POINT_EEG,
                 FIFF.FIFFV_POINT_EXTRA)
    _, origin_head, _ = fit_sphere_to_headshape(info, dig_kinds)
    origin_head /= 1000.  # to meters
    for ch in info['chs']:
        ch['loc'][:3] -= origin_head

    # Use channel locations
    l0 = _auto_topomap_coords(info, picks)

    # Remove electrode position information, use digitization points from now
    # on.
    for ch in info['chs']:
        ch['loc'] = np.zeros(12)

    l1 = _auto_topomap_coords(info, picks)
    assert_allclose(l1, l0)

    # Test plotting mag topomap without channel locations: it should fail
    mag_picks = pick_types(info, meg='mag')
    assert_raises(ValueError, _auto_topomap_coords, info, mag_picks)

    # Test function with too many EEG digitization points: it should fail
    info['dig'].append({'r': [1, 2, 3], 'kind': FIFF.FIFFV_POINT_EEG})
    assert_raises(ValueError, _auto_topomap_coords, info, picks)

    # Test function with too little EEG digitization points: it should fail
    info['dig'] = info['dig'][:-2]
    assert_raises(ValueError, _auto_topomap_coords, info, picks)

    # Electrode positions must be unique
    info['dig'].append(info['dig'][-1])
    assert_raises(ValueError, _auto_topomap_coords, info, picks)

    # Test function without EEG digitization points: it should fail
    info['dig'] = [d for d in info['dig'] if d['kind'] != FIFF.FIFFV_POINT_EEG]
    assert_raises(RuntimeError, _auto_topomap_coords, info, picks)

    # Test function without any digitization points, it should fail
    info['dig'] = None
    assert_raises(RuntimeError, _auto_topomap_coords, info, picks)
    info['dig'] = []
    assert_raises(RuntimeError, _auto_topomap_coords, info, picks)


def test_make_eeg_layout():
    """Test creation of EEG layout"""
    tempdir = _TempDir()
    tmp_name = 'foo'
    lout_name = 'test_raw'
    lout_orig = read_layout(kind=lout_name, path=lout_path)
    info = Raw(fif_fname).info
    info['bads'].append(info['ch_names'][0])
    layout = make_eeg_layout(info, exclude=[])
    layout.save(op.join(tempdir, tmp_name + '.lout'))
    lout_new = read_layout(kind=tmp_name, path=tempdir, scale=False)
    assert_array_equal(lout_new.kind, tmp_name)
    assert_allclose(layout.pos, lout_new.pos, atol=0.1)
    assert_array_equal(lout_orig.names, lout_new.names)

    # Test input validation
    assert_raises(ValueError, make_eeg_layout, info, radius=-0.1)
    assert_raises(ValueError, make_eeg_layout, info, radius=0.6)
    assert_raises(ValueError, make_eeg_layout, info, width=-0.1)
    assert_raises(ValueError, make_eeg_layout, info, width=1.1)
    assert_raises(ValueError, make_eeg_layout, info, height=-0.1)
    assert_raises(ValueError, make_eeg_layout, info, height=1.1)


def test_make_grid_layout():
    """Test creation of grid layout"""
    tempdir = _TempDir()
    tmp_name = 'bar'
    lout_name = 'test_ica'
    lout_orig = read_layout(kind=lout_name, path=lout_path)
    layout = make_grid_layout(test_info)
    layout.save(op.join(tempdir, tmp_name + '.lout'))
    lout_new = read_layout(kind=tmp_name, path=tempdir)
    assert_array_equal(lout_new.kind, tmp_name)
    assert_array_equal(lout_orig.pos, lout_new.pos)
    assert_array_equal(lout_orig.names, lout_new.names)

    # Test creating grid layout with specified number of columns
    layout = make_grid_layout(test_info, n_col=2)
    # Vertical positions should be equal
    assert_true(layout.pos[0, 1] == layout.pos[1, 1])
    # Horizontal positions should be unequal
    assert_true(layout.pos[0, 0] != layout.pos[1, 0])
    # Box sizes should be equal
    assert_array_equal(layout.pos[0, 3:], layout.pos[1, 3:])


def test_find_layout():
    """Test finding layout"""
    assert_raises(ValueError, find_layout, test_info, ch_type='meep')

    sample_info = Raw(fif_fname).info
    grads = pick_types(sample_info, meg='grad')
    sample_info2 = pick_info(sample_info, grads)

    mags = pick_types(sample_info, meg='mag')
    sample_info3 = pick_info(sample_info, mags)

    # mock new convention
    sample_info4 = copy.deepcopy(sample_info)
    for ii, name in enumerate(sample_info4['ch_names']):
        new = name.replace(' ', '')
        sample_info4['ch_names'][ii] = new
        sample_info4['chs'][ii]['ch_name'] = new

    eegs = pick_types(sample_info, meg=False, eeg=True)
    sample_info5 = pick_info(sample_info, eegs)

    lout = find_layout(sample_info, ch_type=None)
    assert_true(lout.kind == 'Vectorview-all')
    assert_true(all(' ' in k for k in lout.names))

    lout = find_layout(sample_info2, ch_type='meg')
    assert_true(lout.kind == 'Vectorview-all')

    # test new vector-view
    lout = find_layout(sample_info4, ch_type=None)
    assert_true(lout.kind == 'Vectorview-all')
    assert_true(all(' ' not in k for k in lout.names))

    lout = find_layout(sample_info, ch_type='grad')
    assert_true(lout.kind == 'Vectorview-grad')
    lout = find_layout(sample_info2)
    assert_true(lout.kind == 'Vectorview-grad')
    lout = find_layout(sample_info2, ch_type='grad')
    assert_true(lout.kind == 'Vectorview-grad')
    lout = find_layout(sample_info2, ch_type='meg')
    assert_true(lout.kind == 'Vectorview-all')

    lout = find_layout(sample_info, ch_type='mag')
    assert_true(lout.kind == 'Vectorview-mag')
    lout = find_layout(sample_info3)
    assert_true(lout.kind == 'Vectorview-mag')
    lout = find_layout(sample_info3, ch_type='mag')
    assert_true(lout.kind == 'Vectorview-mag')
    lout = find_layout(sample_info3, ch_type='meg')
    assert_true(lout.kind == 'Vectorview-all')

    lout = find_layout(sample_info, ch_type='eeg')
    assert_true(lout.kind == 'EEG')
    lout = find_layout(sample_info5)
    assert_true(lout.kind == 'EEG')
    lout = find_layout(sample_info5, ch_type='eeg')
    assert_true(lout.kind == 'EEG')
    # no common layout, 'meg' option not supported

    fname_bti_raw = op.join(bti_dir, 'exported4D_linux_raw.fif')
    lout = find_layout(Raw(fname_bti_raw).info)
    assert_true(lout.kind == 'magnesWH3600')

    lout = find_layout(Raw(fname_ctf_raw).info)
    assert_true(lout.kind == 'CTF-275')

    lout = find_layout(read_raw_kit(fname_kit_157).info)
    assert_true(lout.kind == 'KIT-157')


def test_box_size():
    """Test calculation of box sizes."""
    # No points. Box size should be 1,1.
    assert_allclose(_box_size([]), (1.0, 1.0))

    # Create one point. Box size should be 1,1.
    point = [(0, 0)]
    assert_allclose(_box_size(point), (1.0, 1.0))

    # Create two points. Box size should be 0.5,1.
    points = [(0.25, 0.5), (0.75, 0.5)]
    assert_allclose(_box_size(points), (0.5, 1.0))

    # Create three points. Box size should be (0.5, 0.5).
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_allclose(_box_size(points), (0.5, 0.5))

    # Create a grid of points. Box size should be (0.1, 0.1).
    x, y = np.meshgrid(np.linspace(-0.5, 0.5, 11), np.linspace(-0.5, 0.5, 11))
    x, y = x.ravel(), y.ravel()
    assert_allclose(_box_size(np.c_[x, y]), (0.1, 0.1))

    # Create a random set of points. This should never break the function.
    rng = np.random.RandomState(42)
    points = rng.rand(100, 2)
    width, height = _box_size(points)
    assert_true(width is not None)
    assert_true(height is not None)

    # Test specifying an existing width.
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_allclose(_box_size(points, width=0.4), (0.4, 0.5))

    # Test specifying an existing width that has influence on the calculated
    # height.
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_allclose(_box_size(points, width=0.2), (0.2, 1.0))

    # Test specifying an existing height.
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_allclose(_box_size(points, height=0.4), (0.5, 0.4))

    # Test specifying an existing height that has influence on the calculated
    # width.
    points = [(0.25, 0.25), (0.75, 0.45), (0.5, 0.75)]
    assert_allclose(_box_size(points, height=0.1), (1.0, 0.1))

    # Test specifying both width and height. The function should simply return
    # these.
    points = [(0.25, 0.25), (0.75, 0.45), (0.5, 0.75)]
    assert_array_equal(_box_size(points, width=0.1, height=0.1), (0.1, 0.1))

    # Test specifying a width that will cause unfixable horizontal overlap and
    # essentially breaks the function (height will be 0).
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_array_equal(_box_size(points, width=1), (1, 0))

    # Test adding some padding.
    # Create three points. Box size should be a little less than (0.5, 0.5).
    points = [(0.25, 0.25), (0.75, 0.25), (0.5, 0.75)]
    assert_allclose(_box_size(points, padding=0.1), (0.9 * 0.5, 0.9 * 0.5))
