import h5py
import numpy as np
import matplotlib.pyplot as plt
import os
import dxchange
from tqdm import trange
import time

np.random.seed(int(time.time()))

src_fname = 'cone_256_foam_ptycho/data_cone_256_foam_1nm.h5'
# src_fname = 'cell/ptychography/data_cell_phase.h5'
# src_fname = 'cone_256_filled_ptycho/data_cone_256_1nm_marc.h5'
# dest_fname = 'cone_256_filled_ptycho/data_cone_256_1nm_marc_n2e3_2.h5'
n_ph_tx = '1e7'
n_sample_pixel = 28529
n_ph = float(n_ph_tx) / n_sample_pixel
dest_fname = 'cone_256_foam_ptycho/data_cone_256_foam_1nm_n{}_temp.h5'.format(n_ph_tx)
# dest_fname = 'cell/ptychography/data_cell_phase_n{}_ref.h5'.format(n_ph_tx)
# dest_fname = 'cell/ptychography/data_cell_phase_n4e8.h5'


is_ptycho = False
if 'ptycho' in src_fname:
    is_ptycho = True

o = h5py.File(src_fname, 'r')['exchange/data']
file_new = h5py.File(dest_fname, 'w')
grp = file_new.create_group('exchange')
n = grp.create_dataset('data', dtype='complex64', shape=o.shape)
snr_ls = []

if is_ptycho:
    sigma = 6
    n_ph *= (n_sample_pixel / (o.shape[1] * 3.14 * sigma ** 2)) # photon per diffraction spot

if is_ptycho:
    for i in trange(o.shape[0]):
        for j in range(o.shape[1]):
            prj_o = o[i, j]
            prj_o_inten = np.abs(prj_o) ** 2
            # dc_intensity = prj_o_inten[int(o.shape[-2] / 2), int(o.shape[-1] / 2)]
            # prj_o_inten_norm = prj_o_inten / dc_intensity
            print(n_ph)
            prj_o_inten_noisy = np.random.poisson(prj_o_inten * n_ph)
            prj_o_inten_noisy = prj_o_inten_noisy / n_ph
            noise = prj_o_inten_noisy - prj_o_inten
            snr = np.var(prj_o_inten) / np.var(noise)
            snr_ls.append(snr)
            data = np.sqrt(prj_o_inten_noisy)
            n[i, j] = data.astype('complex64')

else:
    for i in trange(o.shape[0]):
        prj_o = o[i]
        prj_o_inten = np.abs(prj_o) ** 2
        prj_o_inten_noisy = np.random.poisson(prj_o_inten * n_ph)
        # noise = prj_o_inten_noisy - prj_o_inten
        # print(np.var(noise))
        prj_o_inten_noisy = prj_o_inten_noisy / n_ph
        noise = prj_o_inten_noisy - prj_o_inten
        snr = np.var(prj_o_inten) / np.var(noise)
        snr_ls.append(snr)
        data = np.sqrt(prj_o_inten_noisy)
        n[i] = data.astype('complex64')

print('Average SNR is {}.'.format(np.mean(snr_ls)))

dxchange.write_tiff(abs(n[0]), os.path.join(os.path.dirname(dest_fname), 'n{}'.format(n_ph_tx)), dtype='float32', overwrite=True)


# ------- based on SNR -------
# snr = 10

# for i in tqdm(range(o.shape[0])):
# for i in tqdm(range(1)):
#     prj_o = o[i]
#     prj_o_inten = np.abs(prj_o) ** 2
#     var_signal = np.var(prj_o_inten)
#     var_noise = var_signal / snr

    # noise = np.random.poisson(prj_o_inten * (var_noise / np.mean(prj_o_inten)) * 1e10) / 1e5
    # noise = noise * np.sqrt(var_noise / np.var(noise))
    # noise -= np.mean(noise)
    # prj_n_inten = prj_o_inten + noise
    # prj_n = prj_o * np.sqrt(prj_n_inten / prj_o_inten)
    #
    # n[i] = prj_n
