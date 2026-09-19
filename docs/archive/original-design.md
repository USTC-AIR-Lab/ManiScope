> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# RoboTwin 组合泛化评测套件（单内核 · 多策略）

在 RoboTwin 2.0 之上，量一个**冻结的** VLA 在组合泛化上的边界：哪些没见过的组合能做、
哪些不能，以及失败时是**动作能力不够**还是**语言没解析对**（后者才是语言 steerability
的着力点）。

「见过 / 没见过」的定义：policy 在 RoboTwin 2.0 的 50 个任务上微调过，所以这 50 个任务
覆盖的组合 = 见过；本套件的场景 = 把这些元素重组成没见过的。

## 设计：单内核 + 策略插件

所有策略（WLA / DM0.5 / 未来）都走**同一个评测内核** `script/eval_policy.py`。内核拥有
仿真循环、episode 数、step 上限、录像、随机种子、结果格式、stage 日志——这些**只有一份
代码**，策略无从干预，因此不同策略的数字天然可比。

策略之间只差两处：

```
policy/<NAME>/deploy_policy.py   怎么把观测变成动作（三函数 get_model/eval/reset_model）
suite/launch/start_<name>.sh     怎么把推理服务拉起来
```

```
                 suite/run_suite.sh
                        |
                        v
             script/eval_policy.py          <-- 唯一内核（episode/step/录像/种子/结果统一）
              /                  \
   policy/WLA/deploy_policy.py   policy/DM05/deploy_policy.py
        |  socket                     |  HTTP /v1/infer
   WLA policy_server            DM0.5 opendm server
```

对比：早期 WLA 走 RoboTwin 官方 runner、DM0.5 走 dexbotic 的 `run_robotwin2_evaluation.py`，
两套评测循环各写各的（episode 数、录像节奏、结果落点都不同），数字对不齐。现在两者收敛到
同一个内核，这些差异消失。

## 目录

```
robotwin-compo/
  envs/                内嵌 RoboTwin：_base_task.py + 50 基础任务 + 组合场景
  task_config/         含 _eval_step_limit.yml（每个任务/场景的 step 上限）
  description/         指令模板 + generate_episode_instructions
  script/eval_policy.py  唯一评测内核
  assets -> ...        软链（体积大，不入库，见下）
  policy/
    WLA/               socket 瘦客户端插件
    DM05/              HTTP /v1/infer 插件
  suite/
    scenes.yaml        场景清单（单一事实源）
    policies.yaml      策略清单（单一事实源）
    run_suite.sh       统一 runner
    collect.py         汇总对比表
    launch/            各策略推理服务启动脚本
    logs/ diag/ results/   运行产物（gitignore）
```

## 快速开始

```bash
# 跑一个策略的全套场景（自动拉起推理服务）
GPU=0 SIM_GPU=1 bash suite/run_suite.sh wla
GPU=0 SIM_GPU=1 bash suite/run_suite.sh dm05

# 只跑一个场景
bash suite/run_suite.sh wla adjust_bottle_dustbin

# 服务已在别处起好（不自动拉起）
AUTO_LAUNCH=0 bash suite/run_suite.sh dm05

# 场景随机化那一维
SCENE_TASK_CONFIG=_rand_noclutter bash suite/run_suite.sh dm05

# 汇总（可加 --stages 看各场景的 stage 分布）
python3 suite/collect.py --stages
```

统一契约（改 `suite/run_suite.sh` 顶部或用环境变量覆盖，对所有策略生效）：
`EPISODES=50`、`SEED=0`、`MAX_SUCC_VIDEOS=3`、`MAX_FAIL_VIDEOS=3`、`SCENE_TASK_CONFIG=demo_clean`。

## 加一个 policy

1. 写 `policy/<NAME>/deploy_policy.py`，实现三函数（参考 `policy/DM05/deploy_policy.py`）：
   - `get_model(usr_args)` 返回客户端
   - `eval(TASK_ENV, model, observation)` 跑一步推理+执行（按 step_lim/eval_success 中断）
   - `reset_model(model)`
   再写 `deploy_policy.yml` 放协议字段（api_style / action_mode / action_horizon / 连接地址）。
2. 写 `suite/launch/start_<name>.sh` 把推理服务拉起来（端口和 policies.yaml 一致）。
3. 在 `suite/policies.yaml` 里加一段（`policy_name` = 目录名，`ckpt_setting` 必须唯一）。
4. `bash suite/run_suite.sh <name>`。

## 判据（v2）：两层，缺一不可

```
success = SELECT_OK          选对：目标位移 > 所有干扰物（EXCLUSIVE）
        AND GOAL_OK          做对：任务名承诺的终态真的达成了（GOAL）
```

v1 只有第 1 层。`_compo_scene.py` 的 `check_success` 是「位移 > 5cm 且大于干扰物」，
于是 32/59 个场景的名字和它实际测的东西对不上：`place_book_stand` 不检查书有没有上架、
`stack_cups_two` 不检查杯子有没有叠上、`scan_then_basket` 不检查扫没扫码。难度分级
因此是假的 —— L1 和 L3 判的是同一件事。

GOAL 是声明式的，**同时**驱动判据和专家动作（同源，避免专家自己过不了判据导致
`expert_check` 无限拒种子）：

| type | 判什么 | 专家做什么 |
|---|---|---|
| `moved` | 位移超阈值 | 抓起 + 抬高 |
| `lift` | 相对自身起始高度抬升 dz | 抓起 + 抬 0.15 |
| `on` | 落在 ref 正上方、xy 在容差内、双爪张开 | 抓起 + `place_actor` 到 ref 位置 |
| `stack` | 叠在 ref 上方 dz≈0.05 | 用 ref 的 `functional_point(1)` 当落点 |
| `in` | xy 落在容器内、z 不低于容器口、已离开原位 | 取容器最近功能点，按手别给接近姿态，先不松手 |
| `rel` | 在 ref 的左/右/前/后侧，横向不跑偏 | 抓起 + 放到 ref 的对应侧 |
| `between` | 在两个 ref 连线中点附近 | 抓起 + 放到中点 |
| `press` | 夹爪接触点落在物体 contact_point 上，且物体没被搬走 | 不抓取，对准压下再抬起 |
| `qpos` | 铰接关节归一化状态过阈值 | 铰接物体专用 |
| `seq` | 阶段序：必须依次达成，只升不降 | 逐段执行，每段结束显式锁 stage |

坐标约定：`x<0` 左、`x>0` 右；`y` 增大 = 远离机器人（behind）。

## 加场景：改 `suite/table.py`，不要改 `envs/*.py`

场景表是唯一事实来源，`python3 suite/gen_scenes.py` 编译出 `envs/*.py` 和指令模板。
生成前有硬校验，下面这些坑会在生成阶段就被拦住（都是实测踩出来的）：

1. **被操作的物体必须有 `contact_points`**。没有的话 `grasp_actor` 里
   `choose_grasp_pose` 直接 `TypeError: 'NoneType' object is not subscriptable`，
   整条场景 0/8。`088_wineglass` / `066_vinegar` / `067_steamer` 都栽在这。
   静态参照物（垫子/秤/展示架/挂架）不会被抓，不受这条限制。
   可用清单见 `suite/caps.json`（从 `assets/objects/*/model_data*.json` 扫出来）。

2. **放置类场景的被操作物不能是 `create_box` 的裸方块**。同一套放置流程，
   目标换成真实模型（048_stapler）是 **3/3**，用裸方块是 **0–1/10**。
   裸方块只能用在 `lift` / `moved` 这类纯抓起场景，以及当静态垫子/参照物。

3. **落点必须和目标同侧**。手臂按**落点**选而不是按物体选：左臂抓左边的物体没问题，
   但把它放到 `x=+0.2` 规划不出来（实测 `plan=False`，物体一直举在手里，stack 0/8）。
   表里的 `L` / `CL` 分区就是为这个。

4. **`constrain="align"` 只适合有固定抓取朝向的物体**。照抄 move_stapler_pad 的
   `align` + `[0.707,0,0,0.707]` 给随机绕 z 转过的物体用，规划全灭（2/3 → 0/8）。
   默认用 `free` + `[1,0,0,0]`。

5. **放置高度和判据高度是两个量**。`place_actor` 的 `target_pose` 给参照物的位置，
   物体停放高度由它自己算；GOAL 里的 `dz` 是「落好之后中心该比参照物高多少」。
   混用会让物体悬空。

6. **`lift` 阈值别设太高**。`001_bottle` 躺着时中心离桌 0.034，光「扶正」就升到 0.124；
   真抓起来实测才 0.148。阈值顶到 0.10 以上，专家自己都过不了，`expert_check`
   会无限拒种子（v1 在 attr_bind_bottle 上空转过 28 分钟）。

新场景先过专家烟测，**产出率 ≥ 2/8 才进正式清单**：

```bash
TAG=mydim bash suite/smoke_par.sh <scene> <scene> ...     # 8 卡并行
python3 suite/diag/goal_debug.py <scene> --n 5            # 判据分量插桩
```

## 难度分级自检

```bash
python3 suite/collect.py --gradient      # 难度梯度自检
```

同一策略在 L1→L4 上成功率必须单调下降。不单调说明**分级是错的**（某档判据松紧不对，
或干扰物强度没拉开），要回去改场景，不是改策略。

## 环境依赖

评测分两个进程，两套环境（装不到一起，走本地端口）：

- **仿真端**（本仓库这套）：sapien + curobo，跑 `script/eval_policy.py`。用 `ROBOTWIN_PYTHON`
  指定其 python（默认指向一套已装好 sapien/curobo 的 conda 环境）。
- **推理端**（外部后端）：各策略自带，见 `suite/launch/start_<name>.sh`。WLA 在
  harobotsDL_beta 的 robotsdl 环境；DM0.5 在 dexbotic/opendm 环境。

站点相关的绝对路径都写成 `suite/launch/*.sh` 和 `run_suite.sh` 里的**环境变量默认值**
（`${VAR:-/abs/default}`），换机器只需覆盖对应变量，不用改代码。见
`requirements/` 里各环境的依赖清单。

## assets（不入库）

`assets/` 是 RoboTwin 的物体/纹理/embodiment 资源（数 GB），本仓库用软链引用，不进 git。
换机器时按 RoboTwin 官方方式获取 assets，然后
`ln -sfn <robotwin_assets> assets`。
