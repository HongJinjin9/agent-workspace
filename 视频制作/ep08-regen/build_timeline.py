#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期时间轴生成器：67 镜 S01–S67，以 TTS 实测句级时间轴为唯一基准。

输入：
  audio/work/timeline_audio.json         —— 音频组 7 段/73 句实测 start/dur（权威）
  <repo>/视频制作/ep08-scene-design/SCENE-DESIGN.md —— 67 镜分镜表（镜号/时间码/旁白映射）
输出：
  shots.json         —— 分镜 spec（kind/scene/overlay/asset/fallback/anchor/说明）
  work/timeline.json —— 渲染器唯一时间基准（total=音频总长、shots 的 start/dur/end）
  work/srt/all.srt   —— 字幕（从 audio/work/srt/all.srt 拷贝并做覆盖校验）

锚点规则：每镜起点 = 该镜「旁白映射」里第一句的实测句首；镜终点 = 下一镜起点（硬切）；
最后 S67 终点 = 音频 total（片尾 1s 收束）。若某些镜共用同一句，按设计时间码比例插入，
保证单调、最短 0.35s。
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DESIGN_CANDIDATES = [
    "/home/admin/.dsh/state/superagent/work/episode-eight-video-f134d482e964/"
    "视频制作/ep08-scene-design/SCENE-DESIGN.md",
    os.path.join(ROOT, "SCENE-DESIGN.md"),
]
AUDIO_TL = os.path.join(ROOT, "audio", "work", "timeline_audio.json")
SRT_SRC = os.path.join(ROOT, "audio", "work", "srt", "all.srt")

# 镜号 → 内容 spec（kind: pil|broll；scene/overlay/fallback；h3 素材逻辑名）
SPEC = {
    "S01": dict(kind="pil", scene="hook_power_flip", title="车内中控/仪表：功率条从放电翻向回收"),
    "S02": dict(kind="broll", asset="h3_S02", overlay="soc_climb", fallback="fb_soc_climb", title="长下坡：电量数字上爬"),
    "S03": dict(kind="pil", scene="word_strike_motor", title="永动机被划掉，能量守恒"),
    "S04": dict(kind="pil", scene="chain_lightup", title="能量通道母题第一次亮起"),
    "S05": dict(kind="broll", asset="h3_S05", overlay="conservation_text", fallback="fb_conservation_text", title="能量守恒压在长下坡底图"),
    "S06": dict(kind="pil", scene="chain_drive", title="驱动链：电池→逆变器→电机→轮端"),
    "S07": dict(kind="broll", asset="h3_S07", overlay="wheel_push_arrow", fallback="fb_wheel_push_arrow", title="车轮反过来推电机"),
    "S08": dict(kind="pil", scene="motor_swap", title="电机剖面：电动/发电两种状态"),
    "S09": dict(kind="pil", scene="word_swap", title="魔法→可逆"),
    "S10": dict(kind="broll", asset="h3_S10", overlay="heat_vs_charge", fallback="fb_heat_vs_charge", title="刹车热 vs 回收电"),
    "S11": dict(kind="pil", scene="word_correct", title="充电 vs 回收"),
    "S12": dict(kind="pil", scene="bucket_limit", title="回收有上限"),
    "S13": dict(kind="pil", scene="word_strike_more", title="越开越多不可能"),
    "S14": dict(kind="pil", scene="three_place", title="三件套总览"),
    "S15": dict(kind="pil", scene="motor_current", title="电 ⇄ 转动"),
    "S16": dict(kind="pil", scene="inverter_door", title="逆变器双向门"),
    "S17": dict(kind="pil", scene="wave_forward", title="直流→交流波形"),
    "S18": dict(kind="pil", scene="wave_reverse", title="交流→直流波形"),
    "S19": dict(kind="pil", scene="switches", title="同一组开关方向反了"),
    "S20": dict(kind="broll", asset="h3_S20", overlay="bms_gate", fallback="fb_bms_gate", title="电池包与 BMS 门禁"),
    "S21": dict(kind="pil", scene="chain_final", title="四站通道图定稿"),
    "S22": dict(kind="pil", scene="chain_bidir", title="同一条路双向箭头"),
    "S23": dict(kind="pil", scene="arrow_flip", title="功率方向翻转"),
    "S24": dict(kind="pil", scene="chain_reverse", title="刹车：反向四站"),
    "S25": dict(kind="broll", asset="h3_S25", overlay="pedal_power", fallback="fb_pedal_power", title="一脚刹车：功率表起跳"),
    "S26": dict(kind="pil", scene="formula_appear", title="公式 ½mv²"),
    "S27": dict(kind="pil", scene="formula_substitute", title="代入 1.5t / 100km/h"),
    "S28": dict(kind="pil", scene="result_016", title="结果约 0.16 度电"),
    "S29": dict(kind="pil", scene="quadratic_curve", title="速度平方项：+44%"),
    "S30": dict(kind="broll", asset="h3_S30", overlay="heat_text", fallback="fb_heat_text", title="刹车盘红热"),
    "S31": dict(kind="pil", scene="chain_loss_bar", title="每站掉一点"),
    "S32": dict(kind="pil", scene="eff_gauge_regen", title="回收效率 70%-87%"),
    "S33": dict(kind="pil", scene="eff_bars_compare", title="驱动效率 87%-89%"),
    "S34": dict(kind="pil", scene="eff_diff", title="回收比驱动更亏"),
    "S35": dict(kind="broll", asset="h3_S35", overlay="real78", fallback="fb_real78", title="实车试验 78%"),
    "S36": dict(kind="pil", scene="sankey_loss", title="能量损失去向 Sankey"),
    "S37": dict(kind="pil", scene="aero_drag", title="风阻随车速放大"),
    "S38": dict(kind="pil", scene="highway_share", title="高速回收占比 <5%"),
    "S39": dict(kind="broll", asset="h3_S39", overlay="city_curve", fallback="fb_city_curve", title="城市走走停停"),
    "S40": dict(kind="broll", asset="h3_S40", overlay="mgh_annotation", fallback="fb_mgh_annotation", title="长下坡势能"),
    "S41": dict(kind="pil", scene="downhill_numbers", title="≈0.14 kWh ≈ 不到 1 km"),
    "S42": dict(kind="pil", scene="limits_quad", title="四条限制总览"),
    "S43": dict(kind="pil", scene="limit_full", title="满电：不收"),
    "S44": dict(kind="broll", asset="h3_S44", overlay="cold_limit", fallback="fb_cold_limit", title="天冷：回收能力被压窄"),
    "S45": dict(kind="pil", scene="lithium_plating", title="析锂伤寿命"),
    "S46": dict(kind="pil", scene="tach_high", title="转速冲上高位"),
    "S47": dict(kind="pil", scene="back_emf_wall", title="反电动势顶住"),
    "S48": dict(kind="broll", asset="h3_S48", overlay="aero_arrows", fallback="fb_aero_arrows", title="高速行驶：车头切风"),
    "S49": dict(kind="broll", asset="h3_S49", overlay="grip_ring", fallback="fb_grip_ring", title="抓地力不够"),
    "S50": dict(kind="broll", asset="h3_S50", overlay="abs_indicator", fallback="fb_abs_indicator", title="ABS 介入，回收让路"),
    "S51": dict(kind="pil", scene="power_limit_sliders", title="充电功率三重上限"),
    "S52": dict(kind="pil", scene="condition_fold", title="条件不对，就不收"),
    "S53": dict(kind="broll", asset="h3_S53", overlay="pedal_logic", fallback="fb_pedal_logic", title="单踏板逻辑"),
    "S54": dict(kind="pil", scene="blend_curves", title="混合制动 Blending"),
    "S55": dict(kind="broll", asset="h3_S55", overlay="decel_cup", fallback="fb_decel_cup", title="平顺 vs 点头"),
    "S56": dict(kind="broll", asset="h3_S56", overlay="ring_city", fallback="fb_ring_city", title="城市续航占比"),
    "S57": dict(kind="broll", asset="h3_S57", overlay="ring_highway", fallback="fb_ring_highway", title="高速几乎为零"),
    "S58": dict(kind="broll", asset="h3_S58", overlay="pad_bars", fallback="fb_pad_bars", title="刹车片更耐磨"),
    "S59": dict(kind="broll", asset="h3_S59", overlay="rust_text", fallback="fb_rust_text", title="刹车盘锈蚀"),
    "S60": dict(kind="broll", asset="h3_S60", overlay="style_traces", fallback="fb_style_traces", title="两种开法分叉"),
    "S61": dict(kind="pil", scene="style_curves", title="提前松 vs 重刹曲线"),
    "S62": dict(kind="pil", scene="bars_compare", title="越急收得越少"),
    "S63": dict(kind="pil", scene="chain_reprise", title="回到母题"),
    "S64": dict(kind="pil", scene="chain_store", title="换方向存回去"),
    "S65": dict(kind="pil", scene="quote_card", title="金句卡"),
    "S66": dict(kind="broll", asset="h3_S66", overlay="end_line", fallback="fb_end_line", title="城市远景：知道边界"),
    "S67": dict(kind="pil", scene="end_card", title="片尾双声明卡"),
}

SEG_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def log(*a):
    print("[timeline] " + " ".join(str(x) for x in a), flush=True)


def find_design():
    for p in DESIGN_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def parse_design(path):
    """解析 §3 逐镜分镜表：返回 [{id, t0, t1, mapping}]，mapping 为旁白 §4.x-y 列表。"""
    raw = open(path, encoding="utf-8").read()
    rows = []
    in_table = False
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("## 3. 逐镜分镜表"):
            in_table = True
            continue
        if in_table and s.startswith("## "):
            break
        if not in_table or not s.startswith("| S"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 8:
            continue
        sid = cells[0]
        m = re.match(r"^S(\d+)$", sid)
        if not m:
            continue
        tm = re.search(r"(\d+):(\d+\.\d+)[–-](\d+):(\d+\.\d+)", cells[1])
        if not tm:
            continue
        t0 = int(tm.group(1)) * 60 + float(tm.group(2))
        t1 = int(tm.group(3)) * 60 + float(tm.group(4))
        mapping = re.findall(r"§4\.(\d)-(\d+)", cells[-1])
        rows.append(dict(id=sid, t0=t0, t1=t1, mapping=mapping,
                         raw_map=cells[-1]))
    return rows


def load_audio():
    tl = json.load(open(AUDIO_TL, encoding="utf-8"))
    segs = tl["segments"]
    sent_index = {}
    seg_sents = {}
    for seg in segs:
        sid = seg["id"]
        seg_sents[sid] = seg["sentences"]
        for sn in seg["sentences"]:
            sent_index[(sid, int(sn["i"]))] = (float(sn["start"]), float(sn["end"]))
    return tl, seg_sents, sent_index


def build():
    design = find_design()
    if not design:
        raise SystemExit("缺少 SCENE-DESIGN.md")
    rows = parse_design(design)
    if len(rows) != 67:
        raise SystemExit("分镜表解析到 %d 镜（应为 67）" % len(rows))
    tl, seg_sents, sent_index = load_audio()
    total = float(tl["total"])
    # 把旁白映射 §4.x-y 映射到音频段/句：§4.1 → 音频 S1；…；§4.7 → 音频 S7
    # 稿件 §4.1..§4.7 与音频 segments 的 S1..S7 一一对应
    def anchor_time(row):
        if not row["mapping"]:
            return None
        sec, sent = row["mapping"][0]
        seg_id = "S%d" % int(sec)
        try:
            st, _en = sent_index[(seg_id, int(sent))]
            return st
        except KeyError:
            return None
    shots = []
    n = len(rows)
    for i, row in enumerate(rows):
        spec = SPEC[row["id"]]
        start = anchor_time(row)
        if start is None:
            start = row["t0"]
        shots.append(dict(id=row["id"], t0=row["t0"], t1=row["t1"],
                          anchor=start, **spec))
    # 单调化 + 终点 = 下一镜起点；最后一镜终点 = total
    for i, sh in enumerate(shots):
        if i > 0 and sh["anchor"] <= shots[i - 1]["anchor"] + 0.12:
            # 同一句内多镜：按设计时长比例插入
            prev = shots[i - 1]
            span = max(0.35, min(sh["t1"] - sh["t0"], 3.0))
            sh["anchor"] = prev["anchor"] + span
        if sh["anchor"] > total - 0.4:
            sh["anchor"] = max(0.0, total - 0.4 - (n - i) * 0.3)
    out = []
    for i, sh in enumerate(shots):
        start = round(sh["anchor"], 3)
        if i == 0:
            start = 0.0        # 片头 0.6s 留白属于第一镜（画面先于旁白起，避免成片视频比音频短 0.6s）
        end = round(shots[i + 1]["anchor"], 3) if i + 1 < n else round(total, 3)
        dur = round(max(0.35, end - start), 3)
        seg = seg_of(start, seg_sents, tl)
        item = {k: sh[k] for k in ("id", "kind", "title")}
        item.update(dict(start=start, dur=dur, end=round(start + dur, 3), seg=seg))
        if sh.get("scene"):
            item["scene"] = sh["scene"]
        if sh.get("asset"):
            item["asset"] = sh["asset"]
            item["h3"] = True
            item["overlay"] = sh["overlay"]
            item["fallback"] = sh["fallback"]
        else:
            item["h3"] = False
        out.append(item)
    # 段统计
    segs = {}
    for it in out:
        segs.setdefault(it["seg"], []).append(it["id"])
    timeline = dict(total=round(total, 3), fps=FPS, shots=out,
                    segments=[{"id": k, "shots": v} for k, v in segs.items()],
                    h3_share=round(sum(it["dur"] for it in out if it["h3"]) / total, 3))
    json.dump(timeline, open(os.path.join(ROOT, "work", "timeline.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump([{k: v for k, v in it.items()} for it in out],
              open(os.path.join(ROOT, "shots.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # SRT 拷贝 + 覆盖校验
    srt_dst = os.path.join(ROOT, "work", "srt", "all.srt")
    if os.path.isfile(SRT_SRC):
        os.makedirs(os.path.dirname(srt_dst), exist_ok=True)
        shutil.copyfile(SRT_SRC, srt_dst)
    # 校验
    tot = sum(it["dur"] for it in out)
    bad = [it["id"] for it in out if it["dur"] < 0.3]
    log("total=%.3fs shots=%d sum=%.3fs h3_share=%.1f%% srt=%s" % (
        total, len(out), tot, timeline["h3_share"] * 100,
        "OK" if os.path.isfile(srt_dst) else "MISSING"))
    if bad:
        log("!! 异常短镜:", bad)
    # 打印分镜表
    for it in out:
        log("%s %-5s %6.2f→%6.2f (%5.2fs) %s %s%s" % (
            it["id"], it["seg"], it["start"], it["end"], it["dur"],
            "H3 " if it["h3"] else "pil",
            it.get("scene") or it.get("asset") or "",
            (" +" + it["overlay"]) if it.get("overlay") else ""))
    return 0


def seg_of(t, seg_sents, tl):
    segsm = tl["segments"]
    for i, seg in enumerate(segsm):
        st = float(seg["start"])
        en = st + float(seg["dur"])
        if i + 1 < len(segsm):
            en = float(segsm[i + 1]["start"])
        if t < en - 1e-6:
            return "S%d" % (i + 1)
    return "S%d" % len(segsm)


if __name__ == "__main__":
    raise SystemExit(build())
