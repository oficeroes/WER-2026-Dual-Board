# WER 函数库 XML 核对报告

> 本报告由 `WER_函数库/工具/规格/check_library_xml.py` 自动生成（只读核对，不修改任何工程文件）。

## 1. 输入

| 项 | 值 |
|---|---|
| 核对时间 | 2026-11-10 13:34:45 |
| 工程文件 | `D:\UserData\Documents\WER\2026普级赛\WER_函数库\WER函数库.srh` |
| 文件大小 | 50195 字节 |
| SHA256 | `14a204209fa71b53a26ed6b642f9d30641b7e2835f171486639211ce58556069` |
| RobotType | SKCON9 |
| 程序名 | WERFuncLib |
| 积木类型数 | 28 |
| 变量声明 | 27 个 |
| 函数定义 | 20 个 |
| 函数调用 | 22 处 |

## 2. 结论

- 核对结果：**通过**（无 ERROR）
- 计数：ERROR=0，WARN=1，INFO=0
- 使用到的积木类型：`annotation、dual_motor_duration、eeprom_read、get_key、getai_glay、getai_touch、getencoder、getmseconds、getmsecondsreset、if、ifelse、math_compare、math_number、math_op、motor、motor_time、play_sound、printf、procedures_callnoreturn、procedures_defnoreturn、resetencoder、robot_math_unary_operation、start、variables_get、variables_set、wait、while_break、while_cmp`

**核对要点**：
1. 所有 block type 均在 IDE 积木定义（KNOWN_TYPES）中存在；start / procedures_* / variables_* 属动态分类或默认模板，已按允许项处理。
2. 所有 `<field>` 名在该积木的合法字段表中；下拉字段一律按 schema 的【值】比对（不是界面文案）——见第 6 节。
3. 所有 `<value>`/`<statement>` 输入名合法；子块输出 check 与父输入 check 匹配（无 check 的 variables_get 属正常用法，仅 INFO）。
4. `<variables>` 声明与 field VAR 的 id/名字一一对应；函数 mutation 参数 varid 与声明一致。
5. 函数定义/调用签名（名字+参数个数+参数名+顺序）完全一致，无重复定义、无孤调用。
6. 唯一一个 start，deletable=false；整个 XML 中 block id 唯一。

**一句话结论**：本工程 XML 在「结构 / 字段取值 / 输入类型 / 变量引用 / 函数签名」五个层面自洽，可交给 headless 验证与 IDE 实测。（WARN 项见第 4 节，均为需要人工知悉但不必然错误的点）

## 3. ERROR（必须修复）

- 无


## 4. WARN（建议核对/修复）

- `top[16]/statement[STACK]/next/value[bool]/value[A]` **WARN**: block type `get_key` 不在 SKCON9 工具箱里（blocks/ 里有定义）
    - 建议/说明: SKCON9 工具箱未列出（blocks/ 有定义且生成器 robot.check_key 存在，可能是旧版/其他机型遗留）；函数库若使用，请在真机确认 Start 键可用，或改用触碰传感器

## 5. INFO（提示）

- 无

- 另有 12 处语句输入为空（生成器自动补 `pass`，属正常）：`ifelse`×12

## 6. 字段取值核对（下拉重点）

| 积木 | 字段 | 工程中出现的值 | schema 合法值 | 结论 |
|---|---|---|---|---|
| `get_key` | `port` | `1` | `1`、`2`、`3` | ✅ 全部合法 |
| `getai_glay` | `channel` | `10`、`7`、`8`、`9` | `1`、`2`、`3`、`4`、`5`、`6`、`7`、`8`、`9`、`10`… | ✅ 全部合法 |
| `getai_touch` | `channel` | `1` | `1`、`2`、`3`、`4`、`5`、`6`、`7`、`8`、`9`、`10`… | ✅ 全部合法 |
| `getencoder` | `port` | `1`、`2` | `1`、`2`、`3`、`4` | ✅ 全部合法 |
| `getmseconds` | `timer_ID` | `2` | `1`、`2`、`3`、`4`、`5`、`6`、`7`、`8`、`9`、`10`… | ✅ 全部合法 |
| `getmsecondsreset` | `timer_ID` | `2` | `1`、`2`、`3`、`4`、`5`、`6`、`7`、`8`、`9`、`10`… | ✅ 全部合法 |
| `math_compare` | `comparison_operator` | `<`、`==`、`>=` | `==`、`!=`、`<`、`<=`、`>`、`>=` | ✅ 全部合法 |
| `math_op` | `valname` | `*`、`+`、`-` | `+`、`-`、`*`、`/`、`^`、`%` | ✅ 全部合法 |
| `motor` | `channel` | `1`、`2` | `1`、`2`、`3`、`4` | ✅ 全部合法 |
| `motor_time` | `channel` | `3`、`4` | `1`、`2`、`3`、`4` | ✅ 全部合法 |
| `play_sound` | `musicname` | `dazhaohu_c0.mp3` | `dazhaohu_c0.mp3`、`dazhaohu_c1.mp3`、`dazhaohu_c2.mp3`、`dazhaohu_c3.mp3`、`dazhaohu_c4.mp3`、`dongwu_p0.mp3`、`dongwu_p1.mp3`、`dongwu_p2.mp3`、`dongwu_p3.mp3`、`dongwu_p4.mp3`… | ✅ 全部合法 |
| `resetencoder` | `port` | `1`、`2` | `1`、`2`、`3`、`4` | ✅ 全部合法 |
| `robot_math_unary_operation` | `operation` | `fabs`、`negative` | `sqrt`、`fabs`、`negative`、`ln`、`log10`、`e^`、`10^` | ✅ 全部合法 |

## 7. 函数定义与调用签名

| 函数 | 定义参数 | 调用处数 | 参数一致性 |
|---|---|---|---|
| `func_ArmDown` | [] | 0 | ✅ 一致 |
| `func_ArmUp` | [] | 0 | ✅ 一致 |
| `func_BackwardCM` | ['cm'] | 0 | ✅ 一致 |
| `func_Beep` | [] | 0 | ✅ 一致 |
| `func_DriveSpeed` | ['speedL', 'speedR'] | 0 | ✅ 一致 |
| `func_DriveTime` | ['speedL', 'speedR', 'sec'] | 0 | ✅ 一致 |
| `func_ForwardCM` | ['cm'] | 1 | ✅ 一致 |
| `func_Grab` | [] | 0 | ✅ 一致 |
| `func_Init` | [] | 13 | ✅ 一致 |
| `func_LineStep` | [] | 2 | ✅ 一致 |
| `func_LineTime` | ['sec'] | 0 | ✅ 一致 |
| `func_LineUntilCross` | [] | 0 | ✅ 一致 |
| `func_Release` | [] | 0 | ✅ 一致 |
| `func_ResetEncoder` | [] | 4 | ✅ 一致 |
| `func_Show` | ['text'] | 0 | ✅ 一致 |
| `func_Stop` | [] | 1 | ✅ 一致 |
| `func_TurnLeft` | ['deg'] | 0 | ✅ 一致 |
| `func_TurnRight` | ['deg'] | 1 | ✅ 一致 |
| `func_WaitStartKey` | [] | 0 | ✅ 一致 |
| `func_WaitTouch` | [] | 0 | ✅ 一致 |

## 8. 变量 id 对应核对

- `<variables>` 声明 27 个；被积木字段引用的变量 id 必须∈声明集合（逐条已在 ERROR/WARN 中列出）。
- 声明清单（id = 名字）：
  - `v_1_var_1cm` = `var_1cm`
  - `v_2_var_1angle` = `var_1angle`
  - `v_3_var_speed` = `var_speed`
  - `v_4_var_straight_Kp` = `var_straight_Kp`
  - `v_5_var_turn_speed` = `var_turn_speed`
  - `v_6_var_arm_speed` = `var_arm_speed`
  - `v_7_var_arm_time` = `var_arm_time`
  - `v_8_var_ray_white` = `var_ray_white`
  - `v_9_var_ray_speed` = `var_ray_speed`
  - `v_10_var_ray_Kp` = `var_ray_Kp`
  - `v_11_var_ray_Kd` = `var_ray_Kd`
  - `v_12_var_ee_white_9` = `var_ee_white_9`
  - `v_13_var_ee_white_10` = `var_ee_white_10`
  - `v_14_var_err_last_9` = `var_err_last_9`
  - `v_15_var_err_last_10` = `var_err_last_10`
  - `v_16_var_ready` = `var_ready`
  - `v_17_cm` = `cm`
  - `v_18_var_enc_diff` = `var_enc_diff`
  - `v_19_deg` = `deg`
  - `v_20_speedL` = `speedL`
  - `v_21_speedR` = `speedR`
  - `v_22_sec` = `sec`
  - `v_23_var_err_9` = `var_err_9`
  - `v_24_var_err_10` = `var_err_10`
  - `v_25_var_pid_9` = `var_pid_9`
  - `v_26_var_pid_10` = `var_pid_10`
  - `v_27_text` = `text`

## 9. 未覆盖项（本脚本不做）

- 运行期行为：真实 IDE 渲染、函数分类 flyout 实例化、Python 生成/下载/机器人执行（由 `工具/验证/run_validate.py` 的 headless 验证覆盖）。
- `.srhs` 打包（zip 注释=机器人类型枚举）与 IDE 项目列表安装。
- 硬件相关风险：如 `get_key` 不在 SKCON9 工具箱，真机是否有 Start/Left/Right 键需实机确认。
- 生成器语义级检查（同一份 XML 生成 Python 是否正确）不在本脚本范围；本脚本只看 XML 结构/字段/类型/引用是否自洽。

---

（报告由脚本生成；核对基准为 `block_schemas.json`，其证据来源见该文件 `meta.sources`。）