from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

import numpy as np
import pandas as pd
import tensorflow as tf

import utils.utils as utils

class FastGradientSign_AdvGen:

    def __init__(self, cmd_args, input_x_shape, saver, config):
        self.cmd_args = cmd_args
        self.input_x_shape = input_x_shape
        self.saver = saver
        self.config = config

    def run(self, input_dict):
        x = input_dict["x"]
        y_ = input_dict["y_"]
        y_conv = input_dict["y_conv"]
        keep_prob = input_dict["keep_prob"]
        test_data = input_dict["test_data"]
        test_labels = input_dict["test_labels"]

        checkpoint_path = self.config.get('main', 'checkpoint_path')
        eval_frequency = self.config.getint('main', 'eval_frequency')
        num_classes = self.config.getint('main', 'num_classes')
        image_output_path = self.config.get('main', 'image_output_path')
        adversarial_perturbation_min = self.config.getfloat(
            'main', 'adversarial_perturbation_min')
        adversarial_perturbation_max = self.config.getfloat(
            'main', 'adversarial_perturbation_max')
        adversarial_perturbation_steps = self.config.getfloat(
            'main', 'adversarial_perturbation_steps')

        not_fooled = .0
        fooled = .0
        correct_prediction = tf.equal(tf.argmax(y_conv, 1), tf.argmax(y_, 1))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
        cross_entropy = -tf.reduce_sum(tf.cast(y_, "float") * tf.log(y_conv))
        grad = tf.gradients(cross_entropy, x)

        sess = tf.Session()
        tf.initialize_all_variables().run(session=sess)
        self.saver.restore(sess, checkpoint_path)
        df = pd.DataFrame()

        start_time = time.time()

        if self.cmd_args.test:
            iter_range = xrange(1)
            adversarial_perturbation_max = adversarial_perturbation_min
            adversarial_perturbation_steps = 1
        else:
            iter_range = xrange(len(test_data))

        for idx in iter_range:
            if idx % eval_frequency == 0:
                elapsed_time = time.time() - start_time
                print('Adversarial image generation step %d of %d, (%.1fms/step)' %
                    (idx, len(test_data),
                    1000 * elapsed_time / eval_frequency))

            image = test_data[idx]
            label = test_labels[idx]
            y_onehot = np.eye(num_classes)[label]

            pred = sess.run(y_conv, feed_dict={x: (np.reshape(image, self.input_x_shape)), keep_prob: 1.0})
            pred_label = np.argmax(pred)
            grad_val = sess.run(grad, feed_dict={x:np.reshape(image, self.input_x_shape), y_:y_onehot, keep_prob: 1.0})
            grad_sign = np.sign(grad_val[0])
            grad_norm = sum([np.abs(W) for W in grad_val[0]])

            for perturbation in np.linspace(adversarial_perturbation_min, 
                                            adversarial_perturbation_max, 
                                            adversarial_perturbation_steps):
                adv_image = perturbation * grad_sign + image
                adv_pred = sess.run(y_conv, feed_dict={x:adv_image, keep_prob: 1.0})
                adv_label = np.argmax(adv_pred)

                if (adv_label != label): fooled = fooled + 1
                else: not_fooled = not_fooled + 1

                series = pd.Series([idx, label, pred_label, adv_label, grad_norm, pred, adv_pred, image, adv_image, 
                            perturbation, grad_val],
                            index = ["Idx", "True Label", "Predicted Label", "Predicted Label Adversarial", \
                                    "Gradient Norm", "Predicted Prob", "Predicted Prob Adversarial", "Image", \
                                    "Adversarial Image", "Gradient Step", "Gradient"])
                df = df.append(series, ignore_index=True)

        print("Adversarial sample yield: ", fooled/(fooled+not_fooled))
        print("Adversarial samples fooled: ", fooled)
        print("Adversarial samples not fooled: ", not_fooled)
        return df
