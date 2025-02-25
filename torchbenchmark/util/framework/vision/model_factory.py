import torch
import torch.optim as optim
import torchvision.models as models
from torchbenchmark.util.model import BenchmarkModel

from torchbenchmark.util.framework.vision.args import parse_args, apply_args

class TorchVisionModel(BenchmarkModel):
    optimized_for_inference = True

    def __init__(self, model_name, test, device, jit=False, train_bs=1, eval_bs=1, extra_args=[]):
        super().__init__()
        assert test == "train" or test == "eval", f"Test must be 'train' or 'eval', but provided {test}."
        self.test = test
        self.device = device
        self.jit = jit
        self.train_bs = train_bs
        self.eval_bs = eval_bs
        self.extra_args = extra_args

        self.model = getattr(models, model_name)().to(self.device)
        self.eval_model = getattr(models, model_name)().to(self.device)
        self.example_inputs = (torch.randn((train_bs, 3, 224, 224)).to(self.device),)
        self.eval_example_inputs = (torch.randn((eval_bs, 3, 224, 224)).to(self.device),)
        self.example_outputs = torch.rand_like(self.model(*self.example_inputs))

        # setup optimizer and loss_fn
        self.optimizer = optim.Adam(self.model.parameters())
        self.loss_fn = torch.nn.CrossEntropyLoss()

        # process extra args
        self.args = parse_args(self, extra_args)
        apply_args(self, self.args)

        if self.jit:
            if hasattr(torch.jit, '_script_pdt'):
                self.model = torch.jit._script_pdt(self.model, example_inputs=[self.example_inputs, ])
                self.eval_model = torch.jit._script_pdt(self.eval_model)
            else:
                self.model = torch.jit.script(self.model, example_inputs=[self.example_inputs, ])
                self.eval_model = torch.jit.script(self.eval_model)
            # model needs to in `eval`
            # in order to be optimized for inference
            self.eval_model.eval()
            self.eval_model = torch.jit.optimize_for_inference(self.eval_model)

    # By default, FlopCountAnalysis count one fused-mult-add (FMA) as one flop.
    # However, in our context, we count 1 FMA as 2 flops instead of 1.
    # https://github.com/facebookresearch/fvcore/blob/7a0ef0c0839fa0f5e24d2ef7f5d48712f36e7cd7/fvcore/nn/flop_count.py
    def get_flops(self, test='eval', flops_fma=2.0):
        if test == 'eval':
            flops = self.eval_flops / self.eval_bs * flops_fma
            return flops, self.eval_bs
        elif test == 'train':
            flops = self.train_flops / self.train_bs * flops_fma
            return flops, self.train_bs
        assert False, "get_flops() only support eval or train mode."

    def get_module(self):
        return self.model, self.example_inputs

    def train(self, niter=3):
        real_input = [ torch.rand_like(self.example_inputs[0]) ]
        real_output = [ torch.rand_like(self.example_outputs) ]
        for _ in range(niter):
            self.optimizer.zero_grad()
            for data, target in zip(real_input, real_output):
                if self.args.cudagraph:
                    self.example_inputs[0].copy_(data)
                    self.example_outputs.copy_(target)
                    self.g.replay()
                else:
                    pred = self.model(data)
                    self.loss_fn(pred, target).backward()
                    self.optimizer.step()

    def eval(self, niter=1):
        if self.args.cudagraph:
            return NotImplementedError("CUDA Graph is not yet implemented for inference.")
        model = self.eval_model
        example_inputs = self.eval_example_inputs
        for _i in range(niter):
            model(*example_inputs)
