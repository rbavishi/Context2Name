#!/usr/bin/env python3
import argparse
import json
import pickle
import numpy as np
import bottleneck
from http.server import BaseHTTPRequestHandler, HTTPServer

from keras import Input
from keras.engine import Model
from keras.preprocessing import sequence
from keras.utils import np_utils
from keras.layers.core import Activation, Dense, RepeatVector
from keras.layers.recurrent import LSTM
from keras.models import Sequential
from keras.models import load_model
from keras.layers.wrappers import TimeDistributed
from timeit import default_timer as timer

class Config:
    def __init__(self):
        self.UNKNOWN_TOKEN = "**UNK**"
        self.PAD_TOKEN = "**PAD**"
        self.INPUT_VOCAB_SIZE = 4096
        self.OUTPUT_VOCAB_SIZE = 60000
        self.N_NEIGHBORS = 10
        self.KTH_COMMON = 1

        self.SEQ_LEN = 5
        self.HIDDEN_LAYER_SIZE = 80
        self.HIDDEN_LAYER_SIZE2 = 3500
        self.BATCH_SIZE = 32
        self.NUM_EPOCHS = 50
        self.ACCURACY = 0.996
        self.ACCURACY2 = 0.9
        self.PLATEAU_LEN = 1
        self.CHUNK_SIZE1 = 25000
        self.CHUNK_SIZE2 = 20000

        self.PROCESSED_FILE="vocab.pkl"
        self.TRAINING_FILE = "training.csv"  # space separated
        self.EVAL_FILE = "eval.csv"  # space separated
        self.MODEL_FILE = "model.h5"
        self.CONFIG_FILE = "config.json"

def get_models():
    return imap, omap, encoder, lstm

class DPLServer(BaseHTTPRequestHandler):

    def __init__(self, imap, omap, encoder, lstm, *args):
        self.imap = imap
        self.omap = omap
        self.encoder = encoder
        self.lstm = lstm
        BaseHTTPRequestHandler.__init__(self, *args)

    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def log_message(self, format, *args):
        return

    def parse_input(self, inp):
        contexts = []
        targets = []
        for line in inp:
            tokens = line.split()
            target = tokens[1]
            context = tokens[2:]
            def translator(x):
                if x.startswith("1ID:-1") : return x.split(':')[2]
                if x.startswith("1ID:0") : return x.split(':')[2]
                if x.startswith("1ID") : return "1ID"
                return x

            context = list(map(translator, context))
            req = config.SEQ_LEN * config.N_NEIGHBORS
            if len(context) < req:
                context += [config.PAD_TOKEN] * req

            context = context[:req]
            context.reverse()
            contexts.append(context)
            targets.append(target)

        return contexts, targets

    def prepare_input(self, inp):
        d = self.imap[1][config.UNKNOWN_TOKEN]
        ctxs = []
        for ctx in inp[0]:
            ctxs.append(list(map(lambda x : self.imap[1].get(x, d), ctx)))
        return np.array(ctxs), inp[1]

    def prepare_output(self, out):
        return list(map(lambda y : list(map(lambda x : (-x[0], self.omap[2].get(x[1], config.UNKNOWN_TOKEN), x[2]), y)), out))

    def predict(self, inp):
        start = timer()
        ctx, o = self.prepare_input(self.parse_input(inp))
        encoder_inp = np_utils.to_categorical(ctx.reshape([-1]), num_classes=self.imap[0]).reshape([-1,config.N_NEIGHBORS,self.imap[0]])
        encoder_out = self.encoder.predict(encoder_inp)
        lstm_inp = encoder_out.reshape([-1,config.SEQ_LEN,config.HIDDEN_LAYER_SIZE])
        prediction = self.lstm.predict(lstm_inp)
        toptens = bottleneck.argpartition(-prediction, 10, axis=1)[:,:10]
        toptens = [sorted([(-float(prediction[i][int(j)]), int(j), i) for j in x]) for i, x in enumerate(toptens)]
        
        res = self.prepare_output(toptens)
        end = timer() 
        return res, o, (end - start) * 1000.0

    def initDPL(self):
        imap, omap, encoder, lstm = get_models()
        self.imap = imap
        self.omap = omap
        self.encoder = encoder
        self.lstm = lstm

    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        self._set_response()
        self.wfile.write(json.dumps(self.predict(data['tests'])).encode("utf-8"))

if __name__ == "__main__":
    config = Config()
    parser = argparse.ArgumentParser()
    parser.add_argument('--differentiate-toplevel', action='store_true', default=False,
                        help='Treat vars with scope-id = 0 different from scope-id = -1')

    i_map_default = "i_" + str(config.INPUT_VOCAB_SIZE) + "_" + config.PROCESSED_FILE
    parser.add_argument('-i', type=str, default=i_map_default,
                        dest='iload',
                        help='Input vocabulary file')

    o_map_default = "o_" + str(config.OUTPUT_VOCAB_SIZE) + "_" + config.PROCESSED_FILE
    parser.add_argument('-o', type=str, default=o_map_default,
                        dest='oload',
                        help='Output vocabulary file')

    encoder_default = "encoder." + str(config.INPUT_VOCAB_SIZE) + "_" + str(config.HIDDEN_LAYER_SIZE) + "." + config.MODEL_FILE
    parser.add_argument('-e', type=str, default=encoder_default,
                        dest='encoder',
                        help='Encoder file')

    lstm_default = "lstm_" + str(config.HIDDEN_LAYER_SIZE2) + "_" + str(config.OUTPUT_VOCAB_SIZE) + "." + config.MODEL_FILE
    parser.add_argument('-m', type=str, default=lstm_default,
                        dest='lstm',
                        help='LSTM Model file')

    args = parser.parse_args()

    imap = pickle.load(open(args.iload, 'rb'))
    omap = pickle.load(open(args.oload, 'rb'))
    encoder = load_model(args.encoder)
    lstm = load_model(args.lstm)

    print("Models loaded!")

    def handler(*args):
        return DPLServer(imap, omap, encoder, lstm, *args)

    server = HTTPServer(('0.0.0.0', 8080), handler)
    try:
        server.serve_forever()
    except:
        pass
