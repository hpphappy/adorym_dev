import tensorflow as tf
from tensorflow.contrib.image import rotate as tf_rotate
import dxchange
import numpy as np
import h5py
from scipy.ndimage.interpolation import rotate
from scipy.misc import imrotate
import matplotlib.pyplot as plt
import tomopy
import time
import os
from util import *


# ============================================
# DO NOT ROTATE PROGRESSIVELY
# (DO NOT CONTINUE TO ROTATE AN INTERPOLATED OBJECT)
# ============================================

PI = 3.1415927

# ============================================
theta_st = 0
theta_end = PI
n_epochs = 200
sino_range = (600, 601, 1)
# alpha_ls = np.arange(1e-5, 1e-4, 1e-5)
alpha_ls = [1e-5]
# learning_rate_ls = [1]
learning_rate_ls = [0.001, 0.01, 0.1]
center = 32
energy_ev = 5000
psize_cm = 1e-7
# output_folder = 'recon_h5_{}_alpha{}'.format(n_epochs, alpha)
# ============================================



def reconstrct(fname, theta_st=0, theta_end=PI, n_epochs=200, alpha=1e-4, learning_rate=1.0, output_folder=None, downsample=None,
               save_intermediate=False):

    def rotate_and_project(i, loss, obj):

        obj_rot = tf_rotate(obj, theta_ls_tensor[i], interpolation='BILINEAR')
        exiting = multislice_propagate(obj_rot[:, :, :, 0], obj_rot[:, :, :, 1], energy_ev, psize_cm)
        exiting = tf.pow(tf.abs(exiting), 2)
        loss += tf.reduce_mean(tf.squared_difference(exiting, prj[i]))
        i = tf.add(i, 1)
        return (i, loss, obj)

    sess = tf.Session()

    if output_folder is None:
        output_folder = 'uni_diff_{}_alpha{}_rate{}_ds_{}_{}_{}'.format(n_epochs, alpha, learning_rate, *downsample)

    t0 = time.time()

    # read data
    print('Reading data...')
    f = h5py.File(fname, 'r')
    prj = f['exchange/data'][...]
    print('Data reading: {} s'.format(time.time() - t0))
    print('Data shape: {}'.format(prj.shape))

    # convert to intensity and drop phase
    prj = np.abs(prj) ** 2

    # correct for center
    # offset = int(prj.shape[-1] / 2) - center
    # if offset != 0:
    #     for i in range(prj.shape[0]):
    #         prj[i, :, :] = realign_image(prj[i, :, :], [0, offset])

    # downsample
    if downsample is not None:
        prj = tomopy.downsample(prj, level=downsample[0], axis=0)
        prj = tomopy.downsample(prj, level=downsample[1], axis=1)
        prj = tomopy.downsample(prj, level=downsample[2], axis=2)
        print('Downsampled shape: {}'.format(prj.shape))


    dim_y, dim_x = prj.shape[-2:]
    n_theta = prj.shape[0]

    # convert data
    prj = tf.convert_to_tensor(prj, dtype=np.complex64)
    theta = -np.linspace(theta_st, theta_end, n_theta)
    theta_ls_tensor = tf.constant(theta, dtype='float32')

    # initialize
    # 2 channels are for real and imaginary parts respectively
    obj = tf.Variable(initial_value=tf.zeros([dim_y, dim_x, dim_x, 2]))
    obj += 0.5

    loss = tf.constant(0.0)

    i = tf.constant(0)
    c = lambda i, loss, obj: tf.less(i, n_theta)


    _, loss, _ = tf.while_loop(c, rotate_and_project, [i, loss, obj])

    loss = loss / n_theta + alpha * tf.reduce_sum(tf.image.total_variation(obj))

    optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(loss)

    loss_ls = []

    sess.run(tf.global_variables_initializer())

    t0 = time.time()

    print('Optimizer started.')

    for epoch in range(n_epochs):

        t00 = time.time()
        _, current_loss = sess.run([optimizer, loss])
        loss_ls.append(current_loss)
        if save_intermediate:
            temp_obj = sess.run(obj)
            dxchange.write_tiff_stack(temp_obj[0, :, :, 0],
                                      fname=os.path.join(output_folder, 'intermediate', 'iter_{:03d}'.format(epoch)),
                                      dtype='float32',
                                      overwrite=True)
        # print(sess.run(tf.reduce_sum(tf.image.total_variation(obj))))
        print('Iteration {}; loss = {}; time = {} s'.format(epoch, current_loss, time.time() - t00))

    print('Total time: {}'.format(time.time() - t0))

    res = sess.run(obj)
    dxchange.write_tiff_stack(res[:, :, :, 0], fname=os.path.join(output_folder, 'recon'), dtype='float32', overwrite=True)

    plt.figure()
    plt.semilogy(range(n_epochs), loss_ls)
    # plt.show()
    plt.savefig(os.path.join(output_folder, 'converge.png'), format='png')


if __name__ == '__main__':

    for alpha in alpha_ls:
        for learning_rate in learning_rate_ls:
            print('Rate: {}; alpha: {}'.format(learning_rate, alpha))
            reconstrct(fname='data_diff.h5',
                       n_epochs=200,
                       alpha=alpha,
                       learning_rate=learning_rate,
                       downsample=(0, 0, 0),
                       save_intermediate=True)