#!/usr/bin/python3
# -*- coding: utf-8 -*-

# =======
#  To-Do
# =======
# TODO: Adicionar metricas (T is the total number of pixels in all the evaluated images)
# TODO: Adicionar funcao de custo do Eigen, pegar parte do calculo de gradientes da funcao de custo do monodepth
# FIXME: Após uma conversa com o vitor, aparentemente tanto a saida do coarse/fine devem ser lineares, nao eh necessario apresentar o otimizar da Coarse e a rede deve prever log(depth), para isso devo converter os labels para log(y_)
# TODO: Evitar ficar utilizando import *

# ===========
#  Libraries
# ===========
import argparse
import time
# import numpy as np
# import pprint

from collections import deque

from utils.importNetwork import *
from utils.monodeep_dataloader import *
from utils.plot import Plot
from utils.loss import Loss

# ==================
#  Global Variables
# ==================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['CUDA_VISIBLE_DEVICES'] = '1'

appName = 'monodeep'
datetime = time.strftime("%Y-%m-%d") + '_' + time.strftime("%H-%M-%S")

ENABLE_EARLY_STOP = True
ENABLE_RESTORE = True
ENABLE_TENSORBOARD = True
ENABLE_SAVE_CHECKPOINT = False
SAVE_TEST_DISPARITIES = True
SHOW_TEST_DISPARITIES = True

# Early Stop Configuration
AVG_SIZE = 20
MIN_EVALUATIONS = 1000
MAX_STEPS_AFTER_STABILIZATION = 10000


# ===========
#  Functions
# ===========
def argumentHandler():
    # Creating Arguments Parser
    parser = argparse.ArgumentParser("Train the Bitnet Tensorflow implementation taking the dataset.pkl file as input.")

    # Input
    parser.add_argument('-m', '--mode', type=str, help="Select 'train' or 'test' mode", default='train')
    parser.add_argument('--model_name', type=str, help="Select Network topology: 'monodeep', etc",
                        default='monodeep')  # TODO: Adicionar mais topologias
    # parser.add_argument(    '--encoder',                   type=str,   help='type of encoder, vgg or resnet50', default='vgg')
    parser.add_argument('-i', '--data_path', type=str,
                        help="Set relative path to the input dataset <filename>.pkl file",
                        default='/media/olorin/Documentos/datasets/')

    parser.add_argument('-s', '--dataset', action='store', dest='dataset',
                        help="Selects the dataset ['kitti2012','kitti2015','nyudepth',kittiraw]", required=True)

    parser.add_argument('--batch_size', type=int, help="Define the Training batch size", default=16)
    parser.add_argument('--max_steps', type=int, help="Define the number of max Steps", default=1000)
    parser.add_argument('-l', '--learning_rate', type=float, help="Define the initial learning rate", default=1e-4)
    parser.add_argument('-d', '--dropout', type=float, help="Enable dropout in the model during training", default=0.5)
    parser.add_argument('--ldecay', action='store_true', help="Enable learning decay", default=False)
    parser.add_argument('-n', '--l2norm', action='store_true', help="Enable L2 Normalization", default=False)

    parser.add_argument('--full_summary', action='store_true',
                        help="If set, will keep more data for each summary. Warning: the file can become very large")

    parser.add_argument('--log_directory', type=str, help="Set directory to save checkpoints and summaries",
                        default='log_tb/')
    parser.add_argument('-r', '--restore_path', type=str, help="Set path to a specific restore to load", default='')

    parser.add_argument('-t', '--show_train_progress', action='store_true', help="Show Training Progress Images",
                        default=False)

    parser.add_argument('-te','--show_train_error_progress', action='store_true', help="Show the first batch label, the correspondent Network predictions and the MSE evaluations.", default=False)

    parser.add_argument('-o', '--output_directory', type=str,
                        help='output directory for test disparities, if empty outputs to checkpoint folder',
                        default='output/')

    # TODO: Adicionar acima
    # parser.add_argument('-u', '--showTestingProgress', action='store_true', dest='showTestingProgress', help="Show the first batch testing Network prediction img", default=False)
    # parser.add_argument('-s', '--save', action='store_true', dest='enableSave', help="Save the trained model for later restoration.", default=False)

    # parser.add_argument('--saveValidFigs', action='store_true', dest='saveValidFigs', help="Save the figures from Validation Predictions.", default=False) # TODO: Add prefix char '-X'
    # parser.add_argument('--saveTestPlots', action='store_true', dest='saveTestPlots', help="Save the Plots from Testing Predictions.", default=False)   # TODO: Add prefix char '-X'
    # parser.add_argument('--saveTestFigs', action='store_true', dest='saveTestFigs', help="Save the figures from Testing Predictions", default=False)    # TODO: Add prefix char '-X'

    # parser.add_argument('--retrain', help='if used with restore_path, will restart training from step zero', action='store_true')

    return parser.parse_args()


def createSaveFolder():
    save_path = None
    save_restore_path = None

    if ENABLE_RESTORE or ENABLE_TENSORBOARD:
        # Saves the model variables to disk.
        relative_save_path = 'output/' + appName + '/' + datetime + '/'
        save_path = os.path.join(os.getcwd(), relative_save_path)
        save_restore_path = os.path.join(save_path, 'restore/')

        if not os.path.exists(save_restore_path):
            os.makedirs(save_restore_path)

    return save_path, save_restore_path


# ===================== #
#  Training/Validation  #
# ===================== #
def train(args, params):
    # Local Variables
    movMeanLast = 0
    movMean = deque()

    print('[%s] Selected mode: Train' % appName)
    print('[%s] Selected Params: ' % appName)
    print("\t", args)

    save_path, save_restore_path = createSaveFolder()

    # -----------------------------------------
    #  Network Training Model - Building Graph
    # -----------------------------------------
    graph = tf.Graph()
    with graph.as_default():
        # MonoDepth
        dataloader = MonodepthDataloader(args.data_path, params, args.dataset, args.mode)
        params['inputSize'] = dataloader.inputSize
        params['outputSize'] = dataloader.outputSize

        model = MonoDeepModel(args.mode, params)

        def test_dataAug():
            for i in range(10):
                image, _, _, _ = dataloader.readImage(dataloader.train_dataset[i], dataloader.train_labels[i],
                                                      mode='train')
            input("Continue")

        # test_dataAug() # TODO: Remover, após terminar de implementar dataAugmentation Transforms

        with tf.name_scope("Summaries"):
            # Summary Objects
            summary_writer = tf.summary.FileWriter(save_path + args.log_directory, graph)
            summary_op = tf.summary.merge_all('model_0')

        # Creates Saver Obj
        train_saver = tf.train.Saver(tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES))

    # ----------------------------------------
    #  Network Training Model - Running Graph
    # ----------------------------------------
    print("\n[Network/Training] Running built graph...")
    with tf.Session(graph=graph) as session:
        # Local Variables
        step, stabCounter = 0, 0
        train_lossF, valid_lossF = None, None

        tf.global_variables_initializer().run()

        print("[Network/Training] Training Initialized!\n")

        # Proclaim the epochs
        epochs = np.floor(
            args.batch_size * args.max_steps / dataloader.numTrainSamples)
        print('Train with approximately %d epochs' % epochs)

        # Memory Allocation
        batch_data = np.zeros((args.batch_size,
                               dataloader.inputSize[1],
                               dataloader.inputSize[2],
                               dataloader.inputSize[3]),
                               dtype=np.float64) # (?, 172, 576, 3)

        # batch_labels = np.zeros((args.batch_size,
        #                          dataloader.outputSize[1],
        #                          dataloader.outputSize[2]),
        #                          dtype=np.int32) # (?, 43, 144)

        batch_labels = np.zeros((args.batch_size,
                                 dataloader.inputSize[1],
                                 dataloader.inputSize[2]),
                                 dtype=np.int32) # (?, 172, 576)

        batch_data_crop = np.zeros((args.batch_size,
                                      dataloader.inputSize[1],
                                      dataloader.inputSize[2],
                                      dataloader.inputSize[3]),
                                      dtype=np.uint8) # (?, 172, 576, 3)

        valid_dataset_o = np.zeros((len(dataloader.valid_dataset),
                                    dataloader.inputSize[1],
                                    dataloader.inputSize[2],
                                    dataloader.inputSize[3]),
                                    dtype=np.uint8) # (?, 172, 576, 3)

        # valid_labels_o = np.zeros((len(dataloader.valid_labels),
        #                            dataloader.outputSize[1],
        #                            dataloader.outputSize[2]),
        #                            dtype=np.int32) # (?, 43, 144)

        valid_labels_o = np.zeros((len(dataloader.valid_labels),
                                   dataloader.inputSize[1],
                                   dataloader.inputSize[2]),
                                   dtype=np.int32) # (?, 172, 576)

        # =================
        #  Training Loop
        # =================
        start = time.time()
        train_plotObj = Plot(args.mode, title='Train Predictions')  # TODO: Qual o melhor lugar para essa linhas?

        for i in range((len(dataloader.valid_dataset))):
            valid_dataset_o[i], valid_labels_o[i], _, _ = dataloader.readImage(dataloader.valid_dataset[i],
                                                                               dataloader.valid_labels[i],
                                                                               mode='valid',
                                                                               showImages=False)

        for step in range(args.max_steps):
            start2 = time.time()

            # Training and Validation Batches and Feed Dictionary Preparation
            offset = (step * args.batch_size) % (dataloader.numTrainSamples - args.batch_size)  # Pointer
            batch_data_path = dataloader.train_dataset[offset:(offset + args.batch_size)]
            batch_labels_path = dataloader.train_labels[offset:(offset + args.batch_size)]

            # print("offset: %d/%d" % (offset,dataloader.numTrainSamples))
            # print(batch_data_path)
            # print(len(batch_data_path))

            for i in range(len(batch_data_path)):
                # FIXME: os tipos retornados das variaveis estao errados, quando originalmente eram uint8 e int32, lembrar que o placeholder no tensorflow é float32
                image, depth, image_crop, depth_crop = dataloader.readImage(batch_data_path[i],
                                                                            batch_labels_path[i],
                                                                            mode='train',
                                                                            showImages=False)

                # print(image.dtype,depth.dtype, image_crop.dtype, depth_crop.dtype)

                batch_data[i] = image
                batch_labels[i] = depth
                batch_data_crop[i] = image_crop

            feed_dict_train = {model.tf_image: batch_data, model.tf_labels: batch_labels,
                               model.tf_keep_prob: args.dropout}

            feed_dict_valid = {model.tf_image: valid_dataset_o, model.tf_labels: valid_labels_o,
                               model.tf_keep_prob: 1.0}

            # ----- Session Run! ----- #
            _, log_labels, train_PredCoarse, train_PredFine, train_lossF, summary_str = session.run(
                [model.train, model.tf_log_labels, model.tf_predCoarse, model.tf_predFine, model.tf_lossF,
                 summary_op], feed_dict=feed_dict_train)  # Training
            valid_PredCoarse, valid_PredFine, valid_lossF = session.run(
                [model.tf_predCoarse, model.tf_predFine, model.tf_lossF], feed_dict=feed_dict_valid)  # Validation
            # -----

            if ENABLE_TENSORBOARD:
                # Write information to TensorBoard
                summary_writer.add_summary(summary_str, step)
                summary_writer.flush()  # Don't forget this command! It makes sure Python writes the summaries to the log-file

            # TODO: Não faz sentido eu ter validAccRate, uma vez que eu não meço Accuracy, eu apenas monitoro o erro.
            # TODO: Validar, original era movMeanAvg <= movMeanAvgLast
            if ENABLE_EARLY_STOP:
                movMean.append(valid_lossF)

                if step > AVG_SIZE:
                    movMean.popleft()

                movMeanAvg = np.sum(movMean) / AVG_SIZE
                movMeanAvgLast = np.sum(movMeanLast) / AVG_SIZE

                if (movMeanAvg >= movMeanAvgLast) and step > MIN_EVALUATIONS:
                    # print(step,stabCounter)

                    stabCounter += 1
                    if stabCounter > MAX_STEPS_AFTER_STABILIZATION:
                        print("\nSTOP TRAINING! New samples may cause overfitting!!!")
                        break
                else:
                    stabCounter = 0

                movMeanLast = deque(movMean)

            # Prints Training Progress
            if step % 10 == 0:
                if args.show_train_progress:
                    train_plotObj.plot_train(raw=batch_data_crop[0, :, :], label=batch_labels[0, :, :],
                                             log_label=log_labels[0, :, :],
                                             coarse=train_PredCoarse[0, :, :], fine=train_PredFine[0, :, :])

                    # Plot.plotTrainingProgress(raw=batch_data_crop[0, :, :], label=batch_labels[0, :, :],log_label=log_labels[0, :, :], coarse=train_PredCoarse[0, :, :],fine=train_PredFine[0, :, :], fig_id=3)


                if args.show_train_error_progress:
                    # Lembre que a Training Loss utilizaRMSE_log_scaleInv, porém o resultado é avaliado utilizando MSE
                    train_MSE_c_img = Loss.np_MSE(y=train_PredCoarse[0, :, :], y_=batch_labels[0, :, :], )
                    train_MSE_f_img = Loss.np_MSE(y=train_PredFine[0, :, :], y_=batch_labels[0, :, :])

                    Plot.plotTrainingErrorProgress(raw=batch_data_crop[0, :, :], label=batch_labels[0, :, :],
                                                      coarse=train_PredCoarse[0, :, :], fine=train_PredFine[0, :, :],
                                                      coarseMSE=train_MSE_c_img, fineMSE=train_MSE_f_img, figId=8)

                end2 = time.time()
                print('step: {0:d}/{1:d} | t: {2:f} | Batch trLoss: {3:>16.4f} | vLoss: {4:>16.4f} '.format(step,
                                                                                                            args.max_steps,
                                                                                                            end2 - start2,
                                                                                                            train_lossF,
                                                                                                            valid_lossF))

        end = time.time()
        print("\n[Network/Training] Training FINISHED! Time elapsed: %f s" % (end - start))

        # ==============
        #  Save Results
        # ==============
        if ENABLE_RESTORE:
            model.saveTrainedModel(save_restore_path, session, train_saver, args.model_name)

        # Logs the obtained test result
        f = open('results.txt', 'a')
        f.write("%s\t\t%s\t\t%s\t\tsteps: %d\ttrain_lossF: %f\tvalid_lossF: %f\n" % (
            datetime, appName, args.dataset, step, train_lossF,
            valid_lossF))  # TODO: Nao salvar o appName, e sim o nome do model utilizado.
        f.close()


# ========= #
#  Testing  #
# ========= #
def test(args, params):
    # Local Variables
    test_plotObj = Plot(args.mode, title='Test Predictions') # TODO: Qual o melhor lugar para essa linhas?

    print('[%s] Selected mode: Test' % appName)
    print('[%s] Selected Params: %s' % (appName, args))

    # TODO: fazer rotina para pegar imagens externas, nao somente do dataset
    # Loads the dataset and restores a specified trained model.
    dataloader = MonodepthDataloader(args.data_path, params, args.dataset, args.mode)
    model = ImportGraph(args.restore_path)

    # Memory Allocation
    # predCoarse = np.zeros((dataloader.numTestSamples, dataloader.outputSize[1], dataloader.outputSize[2]),
    #                       dtype=np.float32) # (?, 43, 144)

    predCoarse = np.zeros((dataloader.numTestSamples, dataloader.inputSize[1], dataloader.inputSize[2]),
                          dtype=np.float32) # (?, 172, 576)

    # predFine = np.zeros((dataloader.numTestSamples, dataloader.outputSize[1], dataloader.outputSize[2]),
    #                     dtype=np.float32) # (?, 43, 144)

    predFine = np.zeros((dataloader.numTestSamples, dataloader.inputSize[1], dataloader.inputSize[2]),
                        dtype=np.float32) # (?, 172, 576)


    test_dataset_o = np.zeros(
        (len(dataloader.test_dataset), dataloader.inputSize[1], dataloader.inputSize[2], dataloader.inputSize[3]),
        dtype=np.uint8) # (?, 172, 576, 3)

    # Length of test_dataset used, so when there is not test_labels, the variable will still be declared.
    # test_labels_o = np.zeros((len(dataloader.test_dataset), dataloader.outputSize[1], dataloader.outputSize[2]),
    #                          dtype=np.int32) # (?, 43, 144)

    test_labels_o = np.zeros((len(dataloader.test_dataset), dataloader.inputSize[1], dataloader.inputSize[2]),
                             dtype=np.int32)  # (?, 172, 576)

    test_dataset_crop_o = np.zeros(
        (len(dataloader.test_dataset), dataloader.inputSize[1], dataloader.inputSize[2], dataloader.inputSize[3]),
        dtype=np.uint8) # (?, 172, 576, 3)

    # ==============
    #  Testing Loop
    # ==============
    start = time.time()

    for i, image_path in enumerate(dataloader.test_dataset):
        start2 = time.time()

        if dataloader.test_labels:  # It's not empty
            image, depth, image_crop = dataloader.readImage(dataloader.test_dataset[i], dataloader.test_labels[i],
                                                            mode='test')

            # print(image.shape, depth.shape, image_crop.shape)
            test_labels_o[i] = depth
        else:
            image, _, image_crop = dataloader.readImage(dataloader.test_dataset[i], None, mode='test')

        test_dataset_o[i] = image
        test_dataset_crop_o[i] = image_crop

        predCoarse[i], predFine[i] = model.networkPredict(image)

        # Prints Testing Progress
        end2 = time.time()
        print('step: %d/%d | t: %f' % (i + 1, dataloader.numTestSamples, end2 - start2))
        # break # Test

        def devel():
            # TODO: Terminar implementacao Bilinear
            # bilinearOutput(img=predFine[i], size=dataloader.datasetObj.depthInputSize)
            img = predFine[i]

            res_np_resized = np_resizeImage_bilinear(img=predFine[i], size=dataloader.datasetObj.imageInputSize)

            graph = tf.Graph()
            with graph.as_default():
                tf_image = tf.placeholder(tf.float32, shape=(43, 144, 1), name='image')
                tf_resized = tf.image.resize_images(tf_image, [376, 1241])

            with tf.Session(graph=graph) as sess:
                res_tf_resized = tf_resized.eval(feed_dict={tf_image: np.expand_dims(predFine[i],axis=2)})

                print(res_tf_resized.shape)

            plt.figure(2)
            plt.imshow(img)
            plt.title('img')

            plt.figure(3)
            plt.imshow(res_np_resized)
            plt.title('res_np_resized')

            plt.figure(4)
            plt.imshow(res_tf_resized[:,:,0])
            plt.title('res_tf_resized')

            plt.show()
            input("Continue")

        # devel() # TODO: Remover


    # Testing Finished.
    end = time.time()
    print("\n[Network/Testing] Testing FINISHED! Time elapsed: %f s" % (end - start))

    # ==============
    #  Save Results
    # ==============
    # Saves the Test Predictions
    print("[Network/Testing] Saving testing predictions...")
    if args.output_directory == '':
        output_directory = os.path.dirname(args.restore_path)
    else:
        output_directory = args.output_directory

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if SAVE_TEST_DISPARITIES:
        np.save(output_directory + 'test_coarse_disparities.npy', predCoarse)
        np.save(output_directory + 'test_fine_disparities.npy', predFine)

    # Show Results
    if SHOW_TEST_DISPARITIES:
        for i in range(dataloader.numTestSamples):
            test_plotObj.showTestResults(test_dataset_crop_o[i], test_labels_o[i], predCoarse[i], predFine[i], i)


# ======
#  Main
# ======
def main(args):
    """ This Coarse-to-Fine Network Architecture predicts the log depth (log y)."""
    print("[%s] Running..." % appName)

    modelParams = {'inputSize': -1, 'outputSize': -1, 'model_name': args.model_name,
                   'learning_rate': args.learning_rate, 'batch_size': args.batch_size,
                   'max_steps': args.max_steps, 'dropout': args.dropout, 'ldecay': args.ldecay, 'l2norm': args.l2norm,
                   'full_summary': args.full_summary}

    if args.mode == 'train':
        train(args, modelParams)
    elif args.mode == 'test':
        test(args, modelParams)

    print("\n[%s] Done." % appName)
    sys.exit()


# ======
#  Main
# ======
if __name__ == '__main__':
    args = argumentHandler()
    tf.app.run(main=main(args))
