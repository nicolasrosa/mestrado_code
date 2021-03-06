#!/usr/bin/python3
# -*- coding: utf-8 -*-

# ===========
#  MonoDeep
# ===========
# This Coarse-to-Fine Network Architecture predicts the log depth (log y).

# TODO: Adaptar o código para tambem funcionar com o tamanho do nyuDepth
# TODO: Adicionar metricas (T is the total number of pixels in all the evaluated images)
# TODO: Adicionar funcao de custo do Eigen, pegar parte do calculo de gradientes da funcao de custo do monodepth
# FIXME: Arrumar dataset_preparation.py, kitti2012.pkl nao possui imagens de teste
<<<<<<< HEAD
=======
# FIXME: Apos uma conversa com o vitor, aparentemente tanto a saida do coarse/fine devem ser lineares, nao eh necessario apresentar o otimizar da Coarse e a rede deve prever log(depth), para isso devo converter os labels para log(y_)
>>>>>>> e7a9bfb3e4a771c6686cb0bd8aaa7408c37db33d

# ===========
#  Libraries
# ===========
import os
import argparse
import tensorflow as tf
import numpy as np
import sys
import matplotlib.pyplot as plt
import time
import pprint

from scipy.misc import imshow
from monodeep_model import *
from monodeep_dataloader import *

# ==================
#  Global Variables
# ==================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['CUDA_VISIBLE_DEVICES'] = '1'

# ===========
#  Functions
# ===========
def argumentHandler():
    # Creating Arguments Parser
    parser = argparse.ArgumentParser(
        "Train the Monodeep Tensorflow implementation taking the dataset.pkl file as input.")

    # Input
    parser.add_argument('-m', '--mode', type=str, help='train or test', default='train')
    parser.add_argument('--model_name', type=str, help='model name', default='monodeep')
    # parser.add_argument(    '--encoder',                   type=str,   help='type of encoder, vgg or resnet50', default='vgg')
    # parser.add_argument(      '--dataset',                   type=str,   help='dataset to train on, kitti, or nyuDepth', default='kitti')
    parser.add_argument('-i', '--data_path', type=str, help="set relative path to the dataset <filename>.pkl file",
                        required=True)
    # parser.add_argument(    '--filenames_file',            type=str,   help='path to the filenames text file', required=True)
    parser.add_argument('--input_height', type=int, help='input height', default=172)
    parser.add_argument('--input_width', type=int, help='input width', default=576)
    parser.add_argument('--batch_size', type=int, help='batch size', default=16)
    parser.add_argument('-e', '--num_epochs', type=int, help='number of epochs', default=50)
    parser.add_argument('--max_steps', type=int, help='number of max Steps', default=1000)

    parser.add_argument('-l', '--learning_rate', type=float, help='initial learning rate', default=1e-4)
    parser.add_argument('-d', '--dropout', type=float, help="enable dropout in the model during training", default=0.5)
    parser.add_argument('--ldecay', type=bool, help="enable learning decay", default=False)
    parser.add_argument('-n', '--l2norm', type=bool, help="Enable L2 Normalization", default=False)

    parser.add_argument('-t', '--show_train_progress', action='store_true', help="Show Training Progress Images",
                        default=False)

    parser.add_argument('-o', '--output_directory', type=str,
                        help='output directory for test disparities, if empty outputs to checkpoint folder',
                        default='output/')
    parser.add_argument('--log_directory', type=str, help='directory to save checkpoints and summaries', default='log/')
    parser.add_argument('--restore_path', type=str, help='path to a specific restore to load', default='')
    parser.add_argument('--retrain', help='if used with restore_path, will restart training from step zero',
                        action='store_true')
    parser.add_argument('--full_summary',
                        help='if set, will keep more data for each summary. Warning: the file can become very large',
                        action='store_true')

    # TODO: Adicionar acima
    # parser.add_argument('-t','--showTrainingErrorProgress', action='store_true', dest='showTrainingErrorProgress', help="Show the first batch label, the correspondent Network predictions and the MSE evaluations.", default=False)
    # parser.add_argument('-v','--showValidationErrorProgress', action='store_true', dest='showValidationErrorProgress', help="Show the first validation example label, the Network predictions, and the MSE evaluations", default=False)
    # parser.add_argument('-u', '--showTestingProgress', action='store_true', dest='showTestingProgress', help="Show the first batch testing Network prediction img", default=False)
    # parser.add_argument('-p', '--showPlots', action='store_true', dest='enablePlots', help="Allow the plots being displayed", default=False) # TODO: Correto seria falar o nome dos plots habilitados
    # parser.add_argument('-s', '--save', action='store_true', dest='enableSave', help="Save the trained model for later restoration.", default=False)

    # parser.add_argument('--saveValidFigs', action='store_true', dest='saveValidFigs', help="Save the figures from Validation Predictions.", default=False) # TODO: Add prefix char '-X'
    # parser.add_argument('--saveTestPlots', action='store_true', dest='saveTestPlots', help="Save the Plots from Testing Predictions.", default=False)   # TODO: Add prefix char '-X'
    # parser.add_argument('--saveTestFigs', action='store_true', dest='saveTestFigs', help="Save the figures from Testing Predictions", default=False)    # TODO: Add prefix char '-X'

    return parser.parse_args()


# ===================== #
#  Training/Validation  #
# ===================== #
def train(params, args):
    print('[App] Selected mode: Train')
    print('[App] Selected Params: ')
    print("\t", args)

    # -----------------------------------------
    #  Network Training Model - Building Graph
    # -----------------------------------------
    graph = tf.Graph()
    with graph.as_default():
        # Optimizer
        dataloader = MonoDeepDataloader(params, args.mode, args.data_path)
        model = MonoDeepModel(params, args.mode, dataloader.inputSize, dataloader.outputSize)

        with tf.name_scope("Optimizer"):
            # TODO: Add Learning Decay
            global_step = tf.Variable(0, trainable=False)  # Count the number of steps taken.
            learningRate = args.learning_rate
            optimizer_f = tf.train.AdamOptimizer(learningRate).minimize(model.tf_lossF, global_step=global_step)

        with tf.name_scope("Summaries"):
            # Summary/Saver Objects
            saver_folder_path = args.log_directory + args.model_name
            summary_writer = tf.summary.FileWriter(
                saver_folder_path)  # FIXME: Tensorboard files not found, not working properly
            # train_saver = tf.train.Saver()                                                  # ~4.3 Gb
            train_saver = tf.train.Saver(tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES))  # ~850 mb

            tf.summary.scalar('learning_rate', args.learning_rate, ['model_0'])
            tf.summary.scalar('tf_lossF', model.tf_lossF, ['model_0'])
            summary_op = tf.summary.merge_all('model_0')


            # Load checkpoint if set
            # TODO: Terminar
            # if args.checkpoint_path != '':
            #     train_saver.restore(sess, args.checkpoint_path.split(".")[0])

            # if args.retrain:
            #     sess.run(global_step.assign(0))

    # ----------------------------------------
    #  Network Training Model - Running Graph
    # ----------------------------------------
    print("\n[Network/Training] Running built graph...")
    with tf.Session(graph=graph) as session:
        # Init
        print("[Network/Training] Training Initialized!\n")
        start = time.time()
        tf.global_variables_initializer().run()
<<<<<<< HEAD
=======
        
        fig, axes = plt.subplots(5, 1) # TODO: Mover
>>>>>>> e7a9bfb3e4a771c6686cb0bd8aaa7408c37db33d

        # TODO: Mover
        fig, axes = plt.subplots(5, 1)
        fig = plt.gcf()
        fig.canvas.set_window_title('Train Predictions')
        axes[0] = plt.subplot(321)
        axes[1] = plt.subplot(323)
        axes[2] = plt.subplot(325)
        axes[3] = plt.subplot(322)
        axes[4] = plt.subplot(324)
        
        """Training Loop"""
        # TODO: Adicionar loop de epocas
        for step in range(args.max_steps):
            start2 = time.time()

            # Training Batch Preparation
            offset = (step * args.batch_size) % (dataloader.train_labels.shape[0] - args.batch_size)  # Pointer
            # print("offset: %d/%d" % (offset,dataloader.train_labels.shape[0]))
            batch_data_colors = dataloader.train_dataset_crop[offset:(offset + args.batch_size), :, :,
                                :]  # (idx, height, width, numChannels) - Raw
            batch_data = dataloader.train_dataset[offset:(offset + args.batch_size), :, :,
                         :]  # (idx, height, width, numChannels) - Normalized
            batch_labels = dataloader.train_labels[offset:(offset + args.batch_size), :, :]  # (idx, height, width)

            feed_dict_train = {model.tf_image: batch_data, model.tf_labels: batch_labels,
                               model.tf_keep_prob: args.dropout}
            feed_dict_valid = {model.tf_image: dataloader.valid_dataset, model.tf_labels: dataloader.valid_labels,
                               model.tf_keep_prob: 1.0}

            # ----- Session Run! ----- #
<<<<<<< HEAD
            _, log_labels, trPredictions_c, trPredictions_f, trLoss_f, summary_str = session.run(
                [optimizer_f, model.tf_log_labels, model.tf_predCoarse, model.tf_predFine, model.tf_lossF, summary_op],
                feed_dict=feed_dict_train)  # Training
            vPredictions_c, vPredictions_f, vLoss_f = session.run(
                [model.tf_predCoarse, model.tf_predFine, model.tf_lossF], feed_dict=feed_dict_valid)  # Validation
            # ------------------------ #
=======
            _, log_labels,trPredictions_c, trPredictions_f, trLoss_f,summary_str = session.run([optimizer_f, model.tf_log_labels, model.tf_predCoarse, model.tf_predFine, model.tf_lossF, summary_op], feed_dict=feed_dict_train) # Training
            vPredictions_c, vPredictions_f, vLoss_f = session.run([model.tf_predCoarse, model.tf_predFine, model.tf_lossF], feed_dict=feed_dict_valid) # Validation
            # -----
>>>>>>> e7a9bfb3e4a771c6686cb0bd8aaa7408c37db33d

            # summary_writer.add_summary(summary_str, global_step=step)

            # Prints Training Progress
<<<<<<< HEAD
            if step % 10 == 0:
                def plot1(raw, label, log_label, coarse, fine):
                    

=======
            if step % 10 == 0:                
                def plot1(raw, label, log_label, coarse, fine):
>>>>>>> e7a9bfb3e4a771c6686cb0bd8aaa7408c37db33d
                    axes[0].imshow(raw)
                    axes[0].set_title("Raw")
                    axes[1].imshow(label)
<<<<<<< HEAD
                    axes[1].set_title("Label")
                    axes[2].imshow(log_label)
                    axes[2].set_title("log(Label)")
                    axes[3].imshow(coarse)
                    axes[3].set_title("Coarse")
                    axes[4].imshow(fine)
                    axes[4].set_title("Fine")
                    plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0)

                    plt.pause(0.001)

                if args.show_train_progress:
                    plot1(raw=batch_data_colors[0, :, :], label=batch_labels[0, :, :], log_label=log_labels[0, :, :],
                          coarse=trPredictions_c[0, :, :], fine=trPredictions_f[0, :, :])

                end2 = time.time()

                print('step: %d/%d | t: %f | Batch trLoss_f: %0.4E | vLoss_f: %0.4E' % (
                step, args.max_steps, end2 - start2, trLoss_f, vLoss_f))
=======
                    axes[2].imshow(log_label)
                    axes[3].imshow(coarse)
                    axes[4].imshow(fine)
                    plt.pause(0.001)

                if args.show_train_progress:
                    plot1(raw=batch_data_colors[0,:,:], label=batch_labels[0,:,:], log_label=log_labels[0,:,:],coarse=trPredictions_c[0,:,:], fine=trPredictions_f[0,:,:])

                end2 = time.time()

                print('step: %d/%d | t: %f | Batch trLoss_f: %0.4E | vLoss_f: %0.4E' % (step, args.max_steps, end2-start2, trLoss_f, vLoss_f))
>>>>>>> e7a9bfb3e4a771c6686cb0bd8aaa7408c37db33d

        end = time.time()
        print("\n[Network/Training] Training FINISHED! Time elapsed: %f s" % (end - start))

        # Saves trained model
        print("[Network/Training] Saving Trained model...")
        train_saver.save(session, args.log_directory + '/' + args.model_name + '/model')  # global_step=last


# ========= #
#  Testing  #
# ========= #
def test(params, args):
    print('[App] Selected mode: Test')
    print('[App] Selected Params: ', args)

    # Load Dataset and Model
    restore_graph = tf.Graph()
    with restore_graph.as_default():
        dataloader = MonoDeepDataloader(params, args.mode, args.data_path)
        model = MonoDeepModel(params, args.mode, dataloader.inputSize, dataloader.outputSize)

    # Session
    with tf.Session(graph=restore_graph) as sess_restore:

        # Saver
        train_saver = tf.train.Saver(tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES))

        # Restore
        if args.restore_path == '':
            restore_path = tf.train.latest_checkpoint(args.log_directory + '/' + args.model_name)
        else:
            restore_path = args.restore_path.split(".")[0]
        train_saver.restore(sess_restore, restore_path)
        print('\n[Network/Restore] Restoring model from: %s' % restore_path)
        train_saver.restore(sess_restore, restore_path)
        print("[Network/Restore] Model restored!")
        print("[Network/Restore] Restored variables:\n", tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES), '\n')

        """Testing Loop"""
        num_test_samples = dataloader.test_dataset.shape[0]
        test_predFine = np.zeros((num_test_samples, dataloader.outputSize[1], dataloader.outputSize[2]),
                                 dtype=np.float32)
        for step in range(num_test_samples):
            # Testing Batch Preparation
            feed_dict_test = {model.tf_image: np.expand_dims(dataloader.test_dataset[step], 0),
                              model.tf_keep_prob: 1.0}  # model.tf_image: (1, height, width, numChannels)

            # ----- Session Run! ----- #
            test_predFine[step] = sess_restore.run(model.tf_predFine, feed_dict=feed_dict_test)
            # -----

            # Prints Testing Progress
            # print('k: %d | t: %f' % (k, app.timer2.elapsedTime)) # TODO: ativar
            print('step: %d/%d | t: %f' % (step + 1, num_test_samples, -1))

        # Testing Finished.
        print("\n[Network/Testing] Testing FINISHED!")

        print("[Network/Testing] Saving testing predictions...")
        if args.output_directory == '':
            output_directory = os.path.dirname(args.restore_path)
        else:
            output_directory = args.output_directory

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        np.save(output_directory + 'test_disparities.npy', test_predFine)

        # Show Results
        show_test_disparies = True  # TODO: Criar argumento
        if show_test_disparies:
            # TODO: Mover
            fig, axes = plt.subplots(3, 1)  
            fig = plt.gcf()
            fig.canvas.set_window_title('Test Predictions')
            
            for i, image in enumerate(test_predFine):
                # TODO: Codigo mais rapido
                # if i == 0:
                #     plt.figure(1)

                # plt.imshow(image)
                # plt.imshow(dataloader.test_dataset_crop[i])
                # # plt.draw()
                # plt.pause(0.01)
                # # plt.show()

                # TODO: Codigo temporario
                def plot2(raw, label, fine):
                    axes[0].imshow(raw)
                    plt.title("Raw[%d]" % i)
                    axes[1].imshow(label)
                    plt.title("Label")
                    axes[2].imshow(fine)
                    plt.title("Fine")

                    plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0)
                    plt.pause(0.001)

                plot2(dataloader.test_dataset_crop[i], dataloader.test_labels_crop[i], image)



                # TODO: print save done

                # TODO: Adaptar e remover
                # for k in range(dataloader.test_dataset.shape[0]):
                #     # Testing Batch Preparation
                #     offset = (k * net.test.getBatchSize()) % (dataloader.test_labels.shape[0] - net.test.getBatchSize())
                #     batch_data = dataloader.test_dataset[offset:(offset + net.test.getBatchSize()), :, :, :]   # (idx, height, width, numChannels)

                #     # TODO: Nem todos os datasets possuem testing labels
                #     # batch_labels = dataloader.test_labels[offset:(offset + net.test.getBatchSize()), :, :]     # (idx, height, width)
                #     # feed_dict = {tf_dataset: batch_data, tf_labels: batch_labels, keep_prob: 1.0}
                #     feed_dict_test = {tf_dataset: batch_data, keep_prob: 1.0}

                #     # Session Run!
                #     app.timer2.start()
                #     tPredictions_f = session.run(tf_prediction_f, feed_dict=feed_dict_test)
                #     app.timer2.end()

                #     # Prints Testing Progress
                #     print('k: %d | t: %f' % (k, app.timer2.elapsedTime))

                #     if app.args.showTestingProgress or app.args.saveTestPlots:
                #         # Plot.displayImage(dataloader.test_dataset[k,:,:],"dataloader.test_dataset[k,:,:]",6)
                #         # Plot.displayImage(tPredictions_f[0,:,:],"tPredictions_f[0,:,:]",7)

                #         # TODO: A variavel dataloader.test_dataset_crop[k] passou a ser um array, talvez a seguinte funcao de problema
                #         Plot.displayTestingProgress(k, dataloader.test_dataset_crop[k], dataloader.test_dataset[k],tPredictions_f[0,:,:],3)

                #         if app.args.saveTestPlots:
                #             app.saveTestPlot(dataset.list_test_colors_files_filename[k])

                #     if app.args.saveTestFigs:
                #         app.saveTestFig(dataset.list_test_colors_files_filename[k], tPredictions_f[0,:,:])

                #     if app.args.showTestingProgress:
                #         plt.draw()
                #         plt.pause(0.1)

                # # Testing Finished.
                # # if app.args.showTestingProgress:
                # #     plt.close('all')
                # print("[Network/Testing] Testing FINISHED!")


# ======
#  Main
# ======
def main(args):
    print("[App] Running...")

    params = monodeep_parameters(
        height=args.input_height,
        width=args.input_width,
        batch_size=args.batch_size,
        num_epochs=args.num_epochs,
        max_steps=args.max_steps,
        dropout=args.dropout,
        full_summary=args.full_summary)

    if args.mode == 'train':
        train(params, args)
    elif args.mode == 'test':
        test(params, args)

    print("\n[App] DONE!")
    sys.exit()


# ======
#  Main
# ======
if __name__ == '__main__':
    args = argumentHandler()
    tf.app.run(main=main(args))

