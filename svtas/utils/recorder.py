'''
Author: Thyssen Wen
Date: 2022-04-27 16:24:59
LastEditors  : Thyssen Wen
LastEditTime : 2023-03-09 10:56:32
Description: recorder construct function
FilePath     : /SVTAS/svtas/utils/recorder.py
'''
from .logger import AverageMeter

def build_recod(architecture_type, mode):
    assert mode in ["train", "validation", "test"]
    if architecture_type in ["StreamSegmentation2DWithNeck"]:
        if mode == "train":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                    'reader_time': AverageMeter('reader_time', '.5f'),
                    'loss': AverageMeter('loss', '7.5f'),
                    'lr': AverageMeter('lr', 'f', need_avg=False),
                    'Acc': AverageMeter("Acc", '.5f'),
                    'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                    'backbone_loss': AverageMeter("backbone_loss", '.5f'),
                    'neck_loss': AverageMeter("neck_loss", '.5f'),
                    'head_loss': AverageMeter("head_loss", '.5f')
                    }
        elif mode == "validation":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'Acc': AverageMeter("Acc", '.5f'),
                   'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                   'backbone_loss': AverageMeter("backbone_loss", '.5f'),
                   'neck_loss': AverageMeter("neck_loss", '.5f'),
                   'head_loss': AverageMeter("head_loss", '.5f')
                  }
    elif architecture_type in ["StreamSegmentation2DWithBackbone",
                "StreamSegmentation3DWithBackbone"]:
        if mode == "train":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                    'reader_time': AverageMeter('reader_time', '.5f'),
                    'loss': AverageMeter('loss', '7.5f'),
                    'lr': AverageMeter('lr', 'f', need_avg=False),
                    'Acc': AverageMeter("Acc", '.5f'),
                    'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                    'backbone_loss': AverageMeter("backbone_loss", '.5f'),
                    'head_loss': AverageMeter("head_loss", '.5f')
                    }
        elif mode == "validation":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'Acc': AverageMeter("Acc", '.5f'),
                   'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                   'backbone_loss': AverageMeter("backbone_loss", '.5f'),
                   'head_loss': AverageMeter("head_loss", '.5f')
                  }
    elif architecture_type in ["FeatureSegmentation", "Recognition2D", "Recognition3D", "Transeger",
                                "Segmentation2D", "Segmentation3D", "ActionCLIP", "ActionCLIPSegmentation",
                                "FeatureSegmentation3D", "MultiModalityStreamSegmentation", "RLFeatureSegmentation"]:
        if mode == "train":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                    'reader_time': AverageMeter('reader_time', '.5f'),
                    'loss': AverageMeter('loss', '7.5f'),
                    'lr': AverageMeter('lr', 'f', need_avg=False),
                    'Acc': AverageMeter("Acc", '.5f'),
                    'Seg_Acc': AverageMeter("Seg_Acc", '.5f')
                    }
        elif mode == "validation":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'Acc': AverageMeter("Acc", '.5f'),
                   'Seg_Acc': AverageMeter("Seg_Acc", '.5f')
                  }
    elif architecture_type in ["SegmentationCLIP"]:
        if mode == "train":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                    'reader_time': AverageMeter('reader_time', '.5f'),
                    'loss': AverageMeter('loss', '7.5f'),
                    'lr': AverageMeter('lr', 'f', need_avg=False),
                    'Acc': AverageMeter("Acc", '.5f'),
                    'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                    'img_seg_loss': AverageMeter("img_seg_loss", '.5f'),
                    'clip_loss': AverageMeter("clip_loss", '.5f'),
                    }
        elif mode == "validation":
            return {'batch_time': AverageMeter('batch_cost', '.5f'),
                   'reader_time': AverageMeter('reader_time', '.5f'),
                   'loss': AverageMeter('loss', '7.5f'),
                   'Acc': AverageMeter("Acc", '.5f'),
                   'Seg_Acc': AverageMeter("Seg_Acc", '.5f'),
                   'img_seg_loss': AverageMeter("img_seg_loss", '.5f'),
                   'clip_loss': AverageMeter("clip_loss", '.5f'),
                  }
    else:
        raise NotImplementedError