###
 # @Author       : Thyssen Wen
 # @Date         : 2022-06-13 16:04:40
 # @LastEditors  : Thyssen Wen
 # @LastEditTime : 2023-04-25 22:20:51
 # @Description  : Test script
 # @FilePath     : /SVTAS/scripts/test.sh
### 

export CUDA_VISIBLE_DEVICES=1

python tools/launch.py  --mode test -c config/svtas/final/swin_transformer_3d_base_brt_gtea.py --weights=output/swin_transformer_3d_base_brt_gtea_split1/swin_transformer_3d_base_brt_gtea_split1_best.pt
