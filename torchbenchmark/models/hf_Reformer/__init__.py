import torch
import torch.optim as optim
import torchvision.models as models
from ...util.model import BenchmarkModel
from torchbenchmark.tasks import NLP
from transformers import *
from datasets import load_dataset

class Model(BenchmarkModel):
    task = NLP.LANGUAGE_MODELING

    def __init__(self, test, device, jit=False, extra_args=[]):
        super().__init__()
        self.device = device
        self.jit = jit
        self.test = test
        self.extra_args = extra_args

        torch.manual_seed(42)
        config = ReformerConfig()
        if not config.num_buckets:
            # silence "config.num_buckets is not set. Setting config.num_buckets to 128"
            config.num_buckets = 128
        self.model = AutoModelForMaskedLM.from_config(config).to(device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)

        input_ids = torch.randint(0, config.vocab_size, (8, 4096)).to(device)
        decoder_ids = torch.randint(0, config.vocab_size, (8, 4096)).to(device)

        eval_context = torch.randint(0, config.vocab_size, (1, 4096)).to(device)

        self.train_inputs = {'input_ids': input_ids, 'labels': decoder_ids}
        self.eval_inputs = {'input_ids': eval_context, }

    def get_module(self):
        if self.jit:
            raise NotImplementedError()
        return self.model, (self.eval_inputs["input_ids"], )

    def train(self, niter=3):
        if self.jit:
            raise NotImplementedError()
        self.model.train()
        for _ in range(niter):
            outputs = self.model(**self.train_inputs)
            loss = outputs.loss
            loss.backward()
            self.optimizer.step()

    def eval(self, niter=1):
        if self.jit:
            raise NotImplementedError()
        self.model.eval()
        with torch.no_grad():
            for _ in range(niter):
                out = self.model(**self.eval_inputs)
