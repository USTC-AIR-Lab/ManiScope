# Backend configuration

Install each external backend in its own environment using its upstream instructions and lockfiles.
Set the listed paths in ignored `configs/local.env`. Launch scripts expect `.venv/bin/python` under
many backend roots; create that environment locally. No backends have been reinstalled or all-model
inference validated by this normalization. `eef_bridge` is documented separately.

## dm05

Upstream code: https://github.com/dexmal/opendm
Weights: https://huggingface.co/Dexmal/DM05-robotwin2

Required path variables: `DM05_MODEL`, `OPENDM_DIR`, `OPENDM_ENV`.
Launcher: `suite/launch/start_dm05.sh`.

## pi05

Upstream code: https://github.com/Physical-Intelligence/openpi
Weights: https://huggingface.co/motus-robotics/pi0.5_robotwin2

Required path variables: `OPENPI`, `PI05_CKPT`.
Launcher: `suite/launch/start_pi05.sh`.

## xvla

Upstream code: https://github.com/2toINF/X-VLA
Weights: https://huggingface.co/2toINF/X-VLA-RoboTwin2

Required path variables: `XVLA_CKPT`, `XVLA_DIR`.
Launcher: `suite/launch/start_xvla.sh`.

## pi0

Upstream code: https://github.com/Physical-Intelligence/openpi
Weights: https://huggingface.co/yuffish/robotwin-pi0_aloha-agilex_clean-50

Required path variables: `OPENPI`, `PI0_CKPT`.
Launcher: `suite/launch/start_pi0.sh`.

## wla_formal

Upstream code: https://github.com/SJTU-DENG-Lab/WLA
Weights: https://huggingface.co/SJTU-DENG-Lab/wla_robotwin_all_image_action

Required path variables: `WLA_MODEL_ID`, `WLA_ROOT`.
Launcher: `suite/launch/start_wla_formal.sh`.

## starvla

Upstream code: https://github.com/starVLA/starVLA
Weights: https://huggingface.co/StarVLA/Qwen3-VL-OFT-RoboTwin2-All

Required path variables: `STARVLA_CKPT`, `STARVLA_DIR`.
Launcher: `suite/launch/start_starvla.sh`.

## fastwam

Upstream code: https://github.com/yuantianyuan01/FastWAM
Weights: https://huggingface.co/yuanty/fastwam（RoboTwin ckpt: robotwin_uncond_3cam_384.pt；LeRobot 版 https://huggingface.co/lerobot/fastwam_robotwin_uncond_3cam_384）

Required path variables: `DIFFSYNTH_MODEL_BASE_PATH`, `FASTWAM_CKPT`, `FASTWAM_ROOT`, `FASTWAM_STATS`.
Launcher: `suite/launch/start_fastwam.sh`.

## ahawam

Upstream code: https://github.com/serene-sivy/AHA-WAM
Weights: https://huggingface.co/SereneC/AHA-WAM-RoboTwin2.0（robotwin_ahawam.pt + dataset_stats.json）

Required path variables: `AHAWAM_CKPT`, `AHAWAM_ROOT`, `AHAWAM_STATS`, `DIFFSYNTH_MODEL_BASE_PATH`.
Launcher: `suite/launch/start_ahawam.sh`.

## xwam

Upstream code: https://github.com/sharinka0715/X-WAM
Weights: https://huggingface.co/sharinka0715/X-WAM-checkpoints（robotwin_sft）

Required path variables: `TOKENIZERS_PARALLELISM`, `XWAM_EXP`, `XWAM_ROOT`, `XWAM_WAN_DIR`.
Launcher: `suite/launch/start_xwam.sh`.

## g05

Upstream code: https://github.com/OpenGalaxea/GalaxeaVLA
Weights: https://huggingface.co/OpenGalaxea/G05（g05-robotwin20/ + action_tokenizer.pt + qwen3_5_2b_base_processor/，gated）

Required path variables: `G05_ROOT`.
Launcher: `suite/launch/start_g05.sh`.

## openwam

Upstream code: https://github.com/OpenWAM-Official/OpenWAM
Weights: https://huggingface.co/OpenWAM/OpenWAM-Alpha-Sim-RoboTwin-Full

Required path variables: `OPENWAM_CKPT`, `OPENWAM_DIR`.
Launcher: `suite/launch/start_openwam.sh`.

## motus

Upstream code: https://github.com/thu-ml/Motus
Weights: https://huggingface.co/motus-robotics/Motus_robotwin2

Required path variables: `MOTUS_CKPT`, `MOTUS_ROOT`, `MOTUS_VLM`, `MOTUS_WAN`.
Launcher: `suite/launch/start_motus.sh`.

## lingbot_va

Upstream code: https://github.com/Robbyant/lingbot-va
Weights: https://huggingface.co/robbyant/lingbot-va-posttrain-robotwin

Required path variables: `LB_CKPT`, `LB_DIR`.
Launcher: `suite/launch/start_lingbot_va.sh`.
