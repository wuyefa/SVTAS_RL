'''
Author: Thyssen Wen
Date: 2022-03-18 19:25:14
LastEditors  : Thyssen Wen
LastEditTime : 2023-02-28 18:37:54
Description: main script
FilePath     : /SVTAS/tools/launch.py
'''
import argparse
import os
import sys
path = os.path.join(os.getcwd())
sys.path.append(path)
import random

import numpy as np
import torch

from svtas.tasks.infer import infer
from svtas.tasks.test import test
from svtas.tasks.train import train
from svtas.utils.config import get_config
from svtas.utils.logger import get_logger
from svtas.tasks.profile import profile


def parse_args():
    parser = argparse.ArgumentParser("SVTAS train script")
    parser.add_argument('-c',
                        '--config',
                        type=str,
                        default='configs/example.yaml',
                        help='config file path')
    parser.add_argument('--mode',
                        '--m',
                        choices=["train", "test", "infer", "profile"],
                        help='run mode')
    parser.add_argument('-o',
                        '--override',
                        action='append',
                        default=[],
                        help='config options to be overridden')
    parser.add_argument('-w',
                        '--weights',
                        type=str,
                        help='weights for finetuning or testing')
    parser.add_argument('--local_rank',
        default=-1,
        type=int,
        help='node rank for distributed training')
    parser.add_argument(
        '--validate',
        action='store_true',
        help='whether to evaluate the checkpoint during training')
    parser.add_argument(
        '--use_amp',
        action='store_true',
        help='whether to use amp to accelerate')
    parser.add_argument(
        '--use_tensorboard',
        action='store_true',
        help='whether to use tensorboard to visualize train')
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='fixed all random seeds when the program is running')
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='whether to use amp to accelerate')
    parser.add_argument(
        '--max_iters',
        type=int,
        default=None,
        help='max iterations when training(this argonly used in test_tipc)')
    parser.add_argument(
        '--launcher',
        choices=['none', 'pytorch'],
        default='none',
        help='job launcher')
    args = parser.parse_args()
    if 'LOCAL_RANK' not in os.environ:
        os.environ['LOCAL_RANK'] = str(args.local_rank)
    return args


def main():
    args = parse_args()
    cfg = get_config(args.config, overrides=args.override, tensorboard=args.use_tensorboard)

    # init distributed env first, since logger depends on the dist info.
    if args.launcher == 'none':
        nprocs = 1
    else:
        nprocs = torch.cuda.device_count()
    # set seed if specified
    seed = args.seed
    if seed is not None:
        assert isinstance(
            seed, int), f"seed must be a integer when specified, but got {seed}"
        random.seed(seed)
        os.environ['PYTHONHASHSEED'] = str(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed) # if you are using multi-GPU.
        torch.backends.cudnn.deterministic = True
        # weather accelerate conv op
        torch.backends.cudnn.benchmark = args.benchmark
        logger = get_logger("SVTAS")
        logger.info("Current Seed is: " + str(seed))

    if args.mode in ["test"]:
        test(cfg,
             args=args,
             local_rank=args.local_rank,
             nprocs=nprocs,
             use_amp=args.use_amp,
             weights=args.weights)
    elif args.mode in ["train"]:
        train(cfg,
            args=args,
            local_rank=args.local_rank,
            nprocs=nprocs,
            use_amp=args.use_amp,
            weights=args.weights,
            validate=args.validate)
    elif args.mode in ["infer"]:
        infer(cfg,
            args=args,
            local_rank=args.local_rank,
            nprocs=nprocs,
            weights=args.weights,
            validate=args.validate)
    elif args.mode in ["profile"]:
        profile(cfg,
            args=args,
            local_rank=args.local_rank,
            nprocs=nprocs,
            weights=args.weights)
    else:
        raise NotImplementedError(args.mode + " mode not support!")


if __name__ == '__main__':
    main()
