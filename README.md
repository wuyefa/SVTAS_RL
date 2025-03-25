#  End-to-End Streaming Video Temporal Action Segmentation with Reinforcement Learning

Hello! Here is the code of the paper "End-to-End Streaming Video Temporal Action Segmentation with Reinforcement Learning".

## Abstract

The streaming temporal action segmentation (STAS) task, a supplementary task of temporal action segmentation (TAS), has not received adequate attention in the field of video understanding. Existing TAS methods are constrained to offline scenarios due to their heavy reliance on multimodal features and complete contextual information. The STAS task requires the model to classify each frame of the entire untrimmed video sequence clip by clip in time, thereby extending the applicability of TAS methods to online scenarios. However, directly applying existing TAS methods to SATS tasks results in significantly poor segmentation outcomes. In this paper, we thoroughly analyze the fundamental differences between STAS tasks and TAS tasks, attributing the severe performance degradation when transferring models to model bias and optimization dilemmas. We introduce an end-to-end streaming video temporal action segmentation model with reinforcement learning (SVTAS-RL). The end-to-end modeling method mitigates the modeling bias introduced by the change in task nature and enhances the feasibility of online solutions. Reinforcement learning is utilized to alleviate the optimization dilemma. Through extensive experiments, the SVTAS-RL model significantly outperforms existing STAS models and achieves competitive performance to the state-of-the-art TAS model on multiple datasets under the same evaluation criteria, demonstrating notable advantages on the ultra-long video dataset EGTEA.

![SVTAS-RL](model.jpg)

### For more information, you can read [the paper](https://arxiv.org/abs/2309.15683).

## Envirnment Prepare

- Linux Ubuntu 20.04+
- Python 3.8+
- PyTorch 1.13+
- CUDA 11.7+ 
- Cudnn 8.6+ (optional): Only need if you want to use apex accelerate
- Pillow-SIMD (optional): Install it by the following scripts.
- FFmpeg 4.3.1+ (optional): For extract flow and visualize video cam

```bash
conda uninstall -y --force pillow pil jpeg libtiff libjpeg-turbo
pip   uninstall -y         pillow pil jpeg libtiff libjpeg-turbo
conda install -yc conda-forge libjpeg-turbo
CFLAGS="${CFLAGS} -mavx2" pip install --upgrade --no-cache-dir --force-reinstall --no-binary :all: --compile pillow-simd
conda install -y jpeg libtiff
```

- use pip to install environment

```bash
conda create -n torch python=3.8
python -m pip install --upgrade pip
pip install -r requirements.txt

# export
pip freeze > requirements.txt
```

- If report `correlation_cuda package no found`, you should read [Install](svtas/model/backbones/utils/liteflownet_v3/README.md)
- If you want to extract montion vector and residual image to video, you should install ffmpeg, for example, in ubuntu `sudo apt install ffmpeg`

## Document Dictionary

- [Prepare Datset](docs/prepare_dataset.md)
- [Usage](docs/usage.md)
- [Model Zoo](docs/model_zoo.md)
- [Tools Usage](docs/tools_usage.md)
- [Infer Guideline](docs/infer_guideline.md)
- Test Case Guideline

# Citation

```bib
@article{zhang2025end,
  title={End-to-End Streaming Video Temporal Action Segmentation with Reinforcement Learning},
  author={Jinrong Zhang, Wujun Wen, Shenglan Liu, Yunheng Li, Qifeng Li, Lin Feng},
  journal={IEEE transactions on neural networks and learning systems},
  year={2025},
  publisher={IEEE}
}
```