'''
Author       : Thyssen Wen
Date         : 2022-10-17 13:15:41
LastEditors  : Thyssen Wen
LastEditTime : 2022-11-28 12:18:13
Description  : file content
FilePath     : /SVTAS/svtas/model/backbones/utils/liteflownet_v3/correlation_package/correlation.py
'''
import torch
from torch.nn.modules.module import Module
from torch.autograd import Function
import warnings
try:
    import correlation_cuda
except:
    warnings.warn("Can't not use LiteFlowNetV3")

class CorrelationFunction(Function):

    @staticmethod
    def forward(ctx, input1, input2, pad_size=3, kernel_size=3, max_displacement=20, stride1=1, stride2=2, corr_multiply=1):
        ctx.save_for_backward(input1, input2)

        ctx.pad_size = pad_size
        ctx.kernel_size = kernel_size
        ctx.max_displacement = max_displacement
        ctx.stride1 = stride1
        ctx.stride2 = stride2
        ctx.corr_multiply = corr_multiply

        with torch.cuda.device_of(input1):
            rbot1 = input1.new()
            rbot2 = input2.new()
            output = input1.new()

            correlation_cuda.forward(input1, input2, rbot1, rbot2, output,
                ctx.pad_size, ctx.kernel_size, ctx.max_displacement, ctx.stride1, ctx.stride2, ctx.corr_multiply)

        return output

    @staticmethod
    def backward(ctx, grad_output):
        input1, input2 = ctx.saved_tensors

        with torch.cuda.device_of(input1):
            rbot1 = input1.new()
            rbot2 = input2.new()

            grad_input1 = input1.new()
            grad_input2 = input2.new()

            correlation_cuda.backward(input1, input2, rbot1, rbot2, grad_output, grad_input1, grad_input2,
                ctx.pad_size, ctx.kernel_size, ctx.max_displacement, ctx.stride1, ctx.stride2, ctx.corr_multiply)

        return grad_input1, grad_input2, None, None, None, None, None, None


class Correlation(Module):
    def __init__(self, pad_size=0, kernel_size=0, max_displacement=0, stride1=1, stride2=2, corr_multiply=1):
        super(Correlation, self).__init__()
        self.pad_size = pad_size
        self.kernel_size = kernel_size
        self.max_displacement = max_displacement
        self.stride1 = stride1
        self.stride2 = stride2
        self.corr_multiply = corr_multiply

    def forward(self, input1, input2):

        result = CorrelationFunction.apply(input1, input2, self.pad_size, self.kernel_size, self.max_displacement, self.stride1, self.stride2, self.corr_multiply)

        return result
