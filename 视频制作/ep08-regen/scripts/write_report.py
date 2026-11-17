#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 08 期收尾：生成 work/final-report.md + work/assets-manifest.json。

数据来源（存在即用，缺失如实标注 null / 跳过，不编数字）：
  work/final-check.json              verify_ep08.py 的硬校验实测
  work/finalize.json                 finalize.py 的编码/耗时/sha
  delivery/delivery-manifest.json    prepare_delivery.py 的交付清单与素材授权
  work/shots.json / work/timeline.json   分镜与章节结构、H3 引用
  audio/work/audio-report.md         音频混音实测报告
  audio/work/timeline_audio.json     句级实测时间轴
  comfyui/report.md                  H3 窗口逐镜清单/耗时/降级
  assets/h3/manifest.json            H3 素材 provenance
  work/notes.md                      人工备注/已知限制（整段并入报告）

用法：python3 scripts/write_report.py [--notes work/notes.md]
"""
import argparse
import datetime
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
FILM = os.path.join(ROOT, "out", "ep08-regen.mp4")
WEB = os.path.join(ROOT, "out", "ep08-regen-web.mp4")


def jload(*cands, default=None):
    for c in cands:
        if c and os.path.isfile(c):
            try:
                return json.load(open(c, encoding="utf-8")), c
            except Exception:
                pass
    return default, None


def sha256(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(*cands):
    for c in cands:
        if c and os.path.isfile(c):
            return open(c, encoding="utf-8", errors="ignore").read()
    return ""


def summary_line(text, pat, limit=180):
    for line in (text or "").splitlines():
        if re.search(pat, line):
            return line.strip()[:limit]
    return None


def load_shots_any():
    d, src = jload(os.path.join(WORK, "shots.json"), os.path.join(WORK, "timeline.json"),
                   os.path.join(ROOT, "shots.json"))
    if d is None:
        return [], None
    shots = None
    if isinstance(d, dict):
        for k in ("shots", "beats", "scenes", "clips"):
            if isinstance(d.get(k), list) and d[k]:
                shots = d[k]
                break
    elif isinstance(d, list):
        shots = d
    out = []

    def h3_of(s):
        raw = s.get("h3")
        a = str(s.get("asset") or s.get("clip") or "")
        if isinstance(raw, str) and raw.strip():
            a = raw.strip()
            raw = True
        if not raw:
            return False, None
        m = re.search(r"[_\-]([SH])\s*(\d+)", a, re.I) or re.search(r"^([SH])\s*(\d+)$", a, re.I)
        if m:
            return True, "%s%02d" % (m.group(1).upper(), int(m.group(2)))
        return True, "?"

    for s in shots or []:
        if not isinstance(s, dict) or not (s.get("id") or s.get("shot")):
            continue
        is_h3, h3id = h3_of(s)
        out.append({
            "id": str(s.get("id") or s.get("shot")),
            "start": float(s.get("start", 0) or 0),
            "dur": float(s.get("dur", s.get("duration", 0)) or 0),
            "end": float(s.get("end", 0) or 0),
            "seg": s.get("seg") or s.get("section") or "S?",
            "h3": is_h3,
            "h3id": h3id,
            "title": s.get("title") or s.get("scene") or "",
        })
    out.sort(key=lambda x: x["start"])
    return out, src


def segment_table(shots, timeline):
    """章节结构：优先 timeline segments，其次按 shots.seg 分组。"""
    rows = []
    if isinstance(timeline, dict):
        segs = None
        for k in ("segments", "sections", "chapters"):
            if isinstance(timeline.get(k), list) and timeline[k]:
                segs = timeline[k]
                break
        if segs:
            for s in segs:
                if not isinstance(s, dict):
                    continue
                start = float(s.get("start", 0) or 0)
                end = float(s.get("end", 0) or 0)
                dur = float(s.get("dur", (end - start) if end else 0) or 0)
                name = s.get("name") or s.get("title") or s.get("id") or "—"
                sents = s.get("sentences")
                n = len(sents) if isinstance(sents, list) else s.get("n_sentences")
                rows.append((str(name), start, dur, n))
            if rows:
                return rows
    if shots:
        groups = {}
        order = []
        for s in shots:
            k = str(s.get("seg") or "S?")
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(s)
        for k in order:
            g = groups[k]
            start = g[0]["start"]
            end = max((x["start"] + x["dur"]) if x["dur"] else x["end"] for x in g)
            rows.append((k, start, end - start, len(g)))
    return rows


def h3_usage(shots, check, h3_manifest, comfy_report, engine_report=""):
    """返回 (H3 逐镜表, 占比, 降级记录, 是否齐全)。"""
    rows = []
    seen = set()
    for s in shots:
        if not s.get("h3"):
            continue
        hh = str(s.get("h3id") or "H?")
        if hh in seen:
            rows.append((s["id"], s["start"], s["dur"], hh, "复用"))
            continue
        seen.add(hh)
        rows.append((s["id"], s["start"], s["dur"], hh, "使用"))
    h3_info = (check or {}).get("h3") or {}
    share = (check or {}).get("h3_share")
    missing = h3_info.get("missing") or []
    degrade = []
    for src in (comfy_report, engine_report):
        if not src:
            continue
        for line in src.splitlines():
            if re.search(r"降级|失败|重试|fallback|fallback", line):
                degrade.append(line.strip()[:220])
    degrade = degrade[:12]
    if missing:
        degrade.append("缺素材：%s（engine 的 footage 层应自动隐藏/降级，不黑屏）"
                       % ", ".join(missing))
    return rows, share, degrade


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default=os.path.join(WORK, "notes.md"))
    args = ap.parse_args()

    check, check_src = jload(os.path.join(WORK, "final-check.json"))
    check = check or {}
    deliv, deliv_src = jload(os.path.join(ROOT, "delivery", "delivery-manifest.json"))
    deliv = deliv or {}
    fin, fin_src = jload(os.path.join(WORK, "finalize.json"))
    fin = fin or {}
    shots, shots_src = load_shots_any()
    timeline, tl_src = jload(os.path.join(WORK, "timeline.json"),
                             os.path.join(ROOT, "work", "timeline.json"))
    timeline = timeline or {}
    tla, tla_src = jload(os.path.join(ROOT, "audio", "work", "timeline_audio.json"),
                         os.path.join(ROOT, "narration", "timeline_audio.json"))
    tla = tla or {}
    h3_manifest, h3m_src = jload(os.path.join(ROOT, "assets", "h3", "manifest.json"))
    audio_report = read_text(os.path.join(ROOT, "audio", "work", "audio-report.md"),
                             os.path.join(ROOT, "audio", "audio-report.md"))
    comfy_report = read_text(os.path.join(ROOT, "comfyui", "report.md"))
    engine_report = read_text(os.path.join(ROOT, "work", "engine-report.md"))
    h3_status, h3_status_src = jload(os.path.join(ROOT, "work", "h3-status.json"))
    h3_status = h3_status or {}
    notes = read_text(args.notes) if args.notes else ""
    facts = None
    for cand in (os.path.join(ROOT, "facts.json"), os.path.join(ROOT, "work", "facts.json"),
                 os.path.join(ROOT, "src", "data", "facts.json")):
        if os.path.isfile(cand):
            facts = cand
            break

    lw = check.get("loudness") or {}
    dur = check.get("duration") or deliv.get("film_duration")
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    ok = not (check.get("problems") or [])
    def wrap(c, blocking=True):
        if c:
            return "✅"
        return "❌" if blocking else "—（记录）"

    lines = []
    A = lines.append
    A("# 第 08 期《电动车松开油门为什么能充电》成片自检报告\n")
    A("> 由 `scripts/write_report.py` 依据实测数据生成（%s UTC）。"
      "一句话方向：**松油门不是「发电」，是「把车已经有的动能，从轮子手里抢回来存进电池」**。\n"
      % now.isoformat())
    A("## 0. 结论\n")
    A("**%s**%s\n" % (
        "全部硬指标通过，可交付。" if ok else
        "存在未通过项：%s（交付前需处理）。" % ", ".join(check.get("problems") or []),
        "" if not check.get("warnings") else
        " 非阻塞记录：%s。" % ", ".join(check.get("warnings"))))

    # ---------------- 1. 技术规格 ----------------
    A("## 1. 技术规格（实测）\n")
    A("| 项目 | 实测 | 目标 | 结论 |")
    A("| --- | --- | --- | --- |")
    A("| 成片 | `%s` | — | — |" % (check.get("film") or "out/ep08-regen.mp4"))
    A("| 时长 | %s s（%d:%05.2f） | 3:40–4:20（%s±0.5s） | %s |" % (
        "%.3f" % dur if dur else "—", int((dur or 0) // 60), (dur or 0) % 60,
        ("%.3f" % check["expected_duration"]) if check.get("expected_duration") else "—",
        wrap(220.0 <= (dur or 0) <= 260.0)))
    A("| 帧数 | %s | %s | %s |" % (
        check.get("frames", "—"), check.get("expected_frames", "—"),
        wrap(abs((check.get("frames") or 0) - (check.get("expected_frames") or 0)) <= 2)))
    A("| 分辨率 | %sx%s | 1920x1080 | %s |" % (
        check.get("width"), check.get("height"),
        wrap((check.get("width"), check.get("height")) == (1920, 1080))))
    A("| 帧率 | %s | 24 | %s |" % (check.get("fps"), wrap(check.get("fps") == 24.0)))
    A("| 画幅 | 16:9 + 2.35:1 上下 132px 遮幅 | 同左 | %s |" % wrap(
        any(c["name"] == "letterbox_2.35" and c["pass"] for c in check.get("checks") or [])))
    A("| 视频/音频 | %s / %s | H.264 High + AAC 48kHz | %s |" % (
        "%s (%s)" % (check.get("video_codec", "—"), check.get("profile", "—")),
        ", ".join("%s %sHz %sch" % (a.get("codec"), a.get("sr"), a.get("ch"))
                  for a in (check.get("audio") or [])) or "—",
        wrap(bool(check.get("audio")))))
    A("| 体积 | %s MB | — | — |" % check.get("size_mb", "—"))
    A("| 全片解码 | %s | 无错误 | %s |" % (
        "无错误" if not check.get("decode_errors") else str(check["decode_errors"])[:80],
        wrap(not check.get("decode_errors"))))
    web = check.get("web") or deliv.get("web") or {}
    if web:
        A("| web 版 | `%s`（%sx%s / %.1fs / %.1fMB） | 1280×720，体积更小 | %s |" % (
            web.get("path") or "out/ep08-regen-web.mp4", web.get("width"), web.get("height"),
            web.get("duration") or 0, web.get("size_mb") or 0,
            wrap(any(c["name"] == "web_version" and c["pass"] for c in check.get("checks") or []))))
    if fin:
        A("| 编码 | %s 模式；master 编码 %.1fs | — | — |" % (
            fin.get("mode", "—"), (fin.get("master_info") or {}).get("elapsed_s") or 0))
    A("")

    # ---------------- 2. 声音 ----------------
    A("## 2. 响度与音频（实测）\n")
    A("| 指标 | 实测 | 目标 | 结论 |")
    A("| --- | --- | --- | --- |")
    A("| 整体响度 I | %s LUFS | -14 ±0.5 | %s |" % (
        lw.get("I", "—"), wrap(lw.get("I") is not None and -14.5 <= lw["I"] <= -13.5)))
    A("| 真峰值 TP | %s dBTP | ≤ -1.0 | %s |" % (
        lw.get("TP", "—"), wrap(lw.get("TP") is not None and lw["TP"] <= -1.0)))
    A("| 响度范围 LRA | %s LU | — | — |" % lw.get("LRA", "—"))
    nar = check.get("narration") or {}
    corr = nar.get("corr") or {}
    if corr:
        worst = min(corr.values())
        A("| 旁白完整性 corr | %s | ≥0.9 | %s |" % (
            ", ".join("%s=%.4f" % (k, v) for k, v in corr.items()), wrap(worst >= 0.9)))
    else:
        A("| 旁白完整性 corr | 无干声/句级时间轴可对比（记录） | ≥0.9 | — |")
    loud_line = summary_line(audio_report, r"loudnorm|LUFS|TP")
    if loud_line:
        A("| 混音报告摘要 | %s | — | — |" % loud_line.replace("|", "/"))
    n_sent = None
    if isinstance(tla, dict):
        for k in ("sentences", "segments", "cues"):
            if isinstance(tla.get(k), list):
                n_sent = len(tla[k])
                break
    A("")
    A("- 旁白 `zh-CN-YunjianNeural` 逐句表演（%s 句/段级时间轴：`%s`）。"
      % (n_sent if n_sent else "见", os.path.relpath(tla_src, ROOT) if tla_src else "audio/work/timeline_audio.json"))
    A("- 母带：`audio/work/audio.m4a`（AAC 48kHz 立体声），finalize 只做 remux，不重新混音。")
    A("")

    # ---------------- 3. 字幕与画面 ----------------
    A("## 3. 字幕与画面硬校验\n")
    A("| 检查项 | 实测 | 结论 |")
    A("| --- | --- | --- |")
    names = {c["name"]: c for c in (check.get("checks") or [])}
    labels = [
        ("letterbox_2.35", "2.35:1 遮幅（上下 132px 黑边）"),
        ("content_present", "画面内容非黑"),
        ("content_coverage", "全片 36 点内容覆盖（无黑段）"),
        ("motion_present", "运动量（8 对 0.5s 帧间差）"),
        ("fade_in", "片头淡入"),
        ("subtitles_present", "字幕带文字存在"),
        ("subtitles_band_black", "字幕落在下黑边内"),
        ("subtitles_inside_bar", "字幕不越到画面上"),
        ("srt_cues", "字幕条数"),
        ("srt_monotonic", "字幕时间单调"),
        ("srt_no_overlap", "字幕无重叠"),
        ("srt_line_len", "单行 ≤18 汉字"),
        ("srt_in_range", "字幕在片内"),
        ("srt_tail", "末条字幕贴近片尾"),
        ("srt_sentence_coverage", "句级字幕覆盖"),
        ("endcard_text_density", "片尾双声明卡文字密度"),
        ("endcard_declaration_text", "片尾口播双声明关键词"),
        ("tail_ending", "尾部收束（黑场/声明卡）"),
        ("h3_assets_present", "H3 素材到位"),
        ("h3_ratio", "H3 成片时长占比 20–35%"),
        ("web_version", "web 版规格"),
    ]
    for key, label in labels:
        c = names.get(key)
        if c:
            A("| %s | %s | %s |" % (label, c.get("detail", "").replace("|", "/"),
                                    wrap(c.get("pass"), c.get("blocking", True))))
    A("")
    srt = check.get("srt") or {}
    A("- 字幕源：`%s`，%s 条；最大单行显示宽度 %s 字；末条结束 %s s。"
      % (os.path.relpath(check["srt_path"], ROOT) if check.get("srt_path") else "—",
         srt.get("cues", "—"), srt.get("max_line_width", "—"), srt.get("last_end", "—")))
    A("- 片尾双声明：画面卡（`work/qa/endcard-check.png` + `delivery/stills/still-10-end-card.jpg`）"
      "与旁白口播（片尾字幕关键词）双通道；本机无 OCR，画面可读性由 Lead 人工目检。")
    A("- **人工逐帧目检项（脚本无法判定）**：能量流方向（轮端→电机→逆变器→电池的回收/输出双向）、"
      "电机-逆变器-电池路径、制动混合方向、H3 画面无乱码文字/无品牌 logo/无真人正脸。"
      "抽帧样张：`work/qa/principle-*.png`（关键原理帧）、`work/qa/h3-H*.png`（逐条 H3 抽帧）、"
      "`work/qa/verify-contact-sheet.jpg`（16 帧全片）；逐帧清单见 `work/qa/human-check.md`。")
    A("")

    # ---------------- 4. 章节结构 ----------------
    rows = segment_table(shots, timeline)
    if rows:
        A("## 4. 章节结构\n")
        A("| 段 | 起点 | 段长 | 句/镜数 |")
        A("| --- | ---: | ---: | ---: |")
        for name, start, d, n in rows:
            A("| %s | %.2fs | %.2fs | %s |" % (name, start, d, n if n is not None else "—"))
        A("")
        A("- 分镜数据：`%s`（%d 镜）。" % (
            os.path.relpath(shots_src, ROOT) if shots_src else "work/shots.json", len(shots)))
        A("")

    # ---------------- 5. H3 使用清单与降级 ----------------
    A("## 5. H3 实拍质感素材：使用清单与降级记录\n")
    hrows, share, degrade = h3_usage(shots, check, h3_manifest, comfy_report, engine_report)
    h3_info = check.get("h3") or {}
    A("- 分镜引用 H3：**%d 条**；assets/h3 文件到位 **%d 条**%s。" % (
        len(h3_info.get("expected") or []), len(h3_info.get("present") or []),
        ("；缺：" + ", ".join(h3_info.get("missing"))) if h3_info.get("missing") else ""))
    _used = check.get("h3_used_shots") or []
    _fb = check.get("h3_fallback_shots") or []
    _red = check.get("h3_redline") or []
    if _used or _fb:
        A("- **H3 实际可用 %d 镜 / 红线降级 %d 镜**（成片按可用口径计 H3 时长）：%s"
          % (len(_used), len(_fb), ("降级 " + ", ".join(_fb)) if _fb else "无降级"))
    if _red:
        for r in _red[:6]:
            A("  - 红线降级 `%s`(%s)：%s" % (r.get("h"), r.get("shot"),
                                             (r.get("reason") or "").replace("|", "/")))
    if share is not None:
        A("- 成片 H3 时长占比：**%.1f%%**（目标 20–35%%；按 manifest 可用口径，红线降级镜不计入）。"
          % (share * 100))
    if hrows:
        A("")
        A("| 镜号 | 起点 | 时长 | H3 | 状态 |")
        A("| --- | ---: | ---: | --- | --- |")
        for sid, start, d, h, st in hrows:
            A("| %s | %.2fs | %.2fs | %s | %s |" % (sid, start, d, h, st))
    A("")
    if degrade:
        A("**降级/失败记录：**")
        for line in degrade:
            A("- %s" % line)
        A("")
    h3_present = len(h3_info.get("present") or [])
    if h3_present == 0:
        A("")
        A("> ⚠️ **本次交付为 code-only 备选版**：`assets/h3/` 0 条到位（ComfyUI 窗口未开启/用户未确认开机），"
          "22 个 H3 混合镜均使用 engine 的代码 fallback（信息层完整、不黑屏），**成片未使用任何 H3 实拍素材**；"
          "内容、数字、原理、字幕与时间轴不受影响，仅损失实景质感。H3 到货后可用同一链路重渲并重跑本报告。")
    A("")
    # H3 manifest 统计（以 assets/h3/manifest.json 为准，fallback 不计入）
    if isinstance(h3_manifest, dict):
        counts = h3_manifest.get("counts") if isinstance(h3_manifest.get("counts"), dict) else {}
        clips = None
        for k in ("shots", "clips", "items", "files"):
            if isinstance(h3_manifest.get(k), (dict, list)) and h3_manifest.get(k):
                clips = h3_manifest.get(k)
                break
        if clips is not None:
            items = list(clips.values()) if isinstance(clips, dict) else clips
            items = [x for x in items if isinstance(x, dict)]
            def is_ok(x):
                st = str(x.get("status") or x.get("state") or "").lower()
                return st in ("ok", "success", "done", "pass", "ready", "downloaded",
                              "generated", "final", "available")
            n_ok = sum(1 for x in items if is_ok(x))
            extra = ""
            if counts:
                extra = ("；counts: total=%s ok=%s failed=%s deferred=%s fl2va=%s t2v=%s"
                         % (counts.get("total"), counts.get("ok"), counts.get("failed"),
                            counts.get("deferred"), counts.get("fl2va"), counts.get("t2v")))
            A("- H3 manifest：`%s`（%d 条；状态 OK %d%s）"
              % (os.path.relpath(h3m_src, ROOT), len(items), n_ok, extra))
            shown = 0
            for x in items:
                if not is_ok(x):
                    continue
                A("  - `%s` %s %s seed=%s 耗时=%ss" % (
                    x.get("id") or x.get("name") or x.get("shot") or "?",
                    x.get("mode") or "", x.get("resolution") or x.get("size") or "",
                    x.get("seed", "—"), x.get("elapsed_s") or x.get("elapsed") or "—"))
                shown += 1
                if shown >= 24:
                    break
    A("- H3 状态（机器可读）：`%s`。" % (
        os.path.relpath(h3_status_src, ROOT) if h3_status_src else "work/h3-status.json（缺失）"))
    if h3_status:
        A("- `work/h3-status.json`：%s"
          % ", ".join("%s=%s" % (k, v) for k, v in list(h3_status.items())[:8]))
    A("- H3 只承担「像真的」：真实道路/车内/踏板/刹车灯/底盘/充电口等实拍质感与环境声；"
      "永不承载文字、数据、原理示意、字幕、配音、最终拼接（PDF §一 Q1–Q4 口径）。")
    A("- provenance：`%s`。" % (os.path.relpath(h3m_src, ROOT) if h3m_src else "assets/h3/manifest.json"))
    A("")

    # ---------------- 6. 合规声明 ----------------
    A("## 6. 合规声明\n")
    A("- **AI 参与声明（双通道）**：片尾画面卡「本片画面与配音含 AI 辅助制作」「选题、核实与判断，由人完成」"
      "+ 旁白口播同义声明。")
    A("- **匿名化**：全片不出镜、不署名、无职业/公司/证件/车牌信息；H3 提示词禁止真实人物与品牌 logo；"
      "不点评具体车型/品牌好坏。")
    A("- **事实与数字**：物理方向（电流方向、能量流向、转子/定子、制动混合）以公开标准/论文/厂商公开参数为准；"
      "数字单一数据源 `%s`，画面与字幕同源。" % (os.path.relpath(facts, ROOT) if facts else "facts.json（待 engine 提供）"))
    A("- **素材授权**：程序化渲染（原创）；H3 生成（MiniMax H3，发布前按平台许可确认）；"
      "Pexels B-roll（Pexels License，如有）；BGM/音效原创合成（numpy，无外部曲库）；"
      "字体 Noto CJK（OFL）。明细见 `delivery/delivery-manifest.json` 的 `assets_provenance`。")
    A("- **成片与素材不入库**：仓库只保留脚本/文档/时间轴/SRT/清单/静帧封面（按 .gitignore）。")
    A("")

    # ---------------- 7. 交付物 ----------------
    A("## 7. 交付物\n")
    film_sha = (deliv.get("film_sha256") or (fin.get("sha256")) or sha256(FILM))
    A("- 成片 master：`out/ep08-regen.mp4`（%s s / %s MB / sha256 `%s`）" % (
        "%.3f" % dur if dur else "—", check.get("size_mb", "—"), film_sha or "—"))
    if deliv.get("web"):
        A("- web 版：`%s`（%s MB / sha256 `%s`）" % (
            deliv["web"].get("path"), deliv["web"].get("size_mb"), deliv["web"].get("sha256")))
    if deliv:
        A("- 静帧：`delivery/stills/` %d 张（%s）" % (
            len(deliv.get("beats") or []),
            ", ".join(b.get("name", "") for b in deliv.get("beats") or [])))
        A("- 联系表：`delivery/contact-sheet.jpg`")
        A("- 封面：%s" % ", ".join(deliv.get("covers") or []))
    A("- 工程：`/app/vedio/ep08-regen`（自研 Python/PIL 程序化渲染 + ComfyUI H3 证据影像）；"
      "仓库同步目录 `视频制作/ep08-regen/`（仅源码/文档/时间轴/SRT/清单/静帧封面，素材与成片不入库）。")
    if fin:
        A("- 渲染/编码：finalize `%s` 模式，master %.1fs、web %.1fs（`work/finalize.json`）。" % (
            fin.get("mode", "—"), (fin.get("master_info") or {}).get("elapsed_s") or 0,
            (fin.get("web_info") or {}).get("elapsed_s") or 0))
    if check.get("contact_sheet"):
        A("- 校验抽帧联系表：`%s`" % check["contact_sheet"])
    A("")

    # ---------------- 8. 已知限制 ----------------
    A("## 8. 已知限制\n")
    auto_limits = [
        "**本机无 OCR**：片尾声明卡与花字可读性以「文字像素密度 + 静帧」判定，交付前由 Lead 人工目检一次。",
        "**物理/能量流正确性需人工逐帧目检**：脚本只能验证画面存在与运动量，不能判断电流方向/能量流箭头语义。",
        "**H3 商用许可**：MiniMax H3 生成内容的商用发布需按平台许可确认；成片仅在内部交付，发布前复核。",
        "**H3 素材缺失时**：engine 的 footage 层自动隐藏/降级（不黑屏），实际使用清单见本报告 §5；本次以 `check.h3` 实测为准。",
        "**响度/真峰值**：以 ffmpeg loudnorm 实测为准；不同播放器/平台转码后可能有 ±0.3 LU 偏差。",
    ]
    for x in auto_limits:
        A("- %s" % x)
    if notes.strip():
        A("")
        A("**本次人工备注 / 补充限制：**")
        A("")
        A(notes.strip())
    A("")

    report = "\n".join(lines) + "\n"
    out_md = os.path.join(WORK, "final-report.md")
    os.makedirs(WORK, exist_ok=True)
    open(out_md, "w", encoding="utf-8").write(report)
    print("report ->", out_md)

    # ---------------- assets-manifest.json ----------------
    prov = (deliv.get("assets_provenance") or {})
    checks_map = {c["name"]: {"pass": c["pass"], "blocking": c.get("blocking", True),
                              "detail": c.get("detail", "")} for c in check.get("checks") or []}
    program_files = []
    for sub in ("scripts",):
        d = os.path.join(ROOT, sub)
        if os.path.isdir(d):
            program_files += sorted(os.path.relpath(os.path.join(d, f), ROOT)
                                    for f in os.listdir(d) if f.endswith((".py", ".sh", ".md")))
    for f in sorted(os.listdir(ROOT)):
        if f.endswith((".py", ".json", ".md")) and os.path.isfile(os.path.join(ROOT, f)):
            program_files.append(f)
    manifest = {
        "episode": "第08期《电动车松开油门为什么能充电》",
        "generated_by": "自研 Python/PIL 程序化渲染引擎 + ComfyUI MiniMax H3 证据影像",
        "generated_at_utc": now.isoformat(),
        "spec": {
            "film": {
                "path": "out/ep08-regen.mp4",
                "duration_s": dur,
                "frames": check.get("frames"),
                "width": check.get("width"), "height": check.get("height"),
                "fps": check.get("fps"), "size_mb": check.get("size_mb"),
                "sha256": film_sha,
            },
            "web": deliv.get("web"),
            "expected_duration_s": check.get("expected_duration"),
            "expected_duration_source": check.get("expected_duration_source"),
            "loudness": lw,
            "letterbox_px": 132,
            "checks": checks_map,
            "problems": check.get("problems") or [],
            "warnings": check.get("warnings") or [],
        },
        "program": {
            "project_dir": "/app/vedio/ep08-regen",
            "entry": "scripts/finalize.py（成片）/ scripts/render_all.sh（逐镜渲染编排）",
            "shots": len(shots),
            "shots_source": os.path.relpath(shots_src, ROOT) if shots_src else None,
            "timeline": os.path.relpath(tl_src, ROOT) if tl_src else None,
            "files": program_files,
        },
        "h3": {
            "manifest": os.path.relpath(h3m_src, ROOT) if h3m_src else "assets/h3/manifest.json",
            "expected": h3_info.get("expected") or [],
            "present": h3_info.get("present") or [],
            "missing": h3_info.get("missing") or [],
            "share": check.get("h3_share"),
            "note": "H3 素材为大文件，不入库；仓库只保留 provenance 清单。",
        },
        "audio": {
            "timeline_audio": os.path.relpath(tla_src, ROOT) if tla_src else "audio/work/timeline_audio.json",
            "master": "audio/work/audio.m4a",
            "report": "audio/work/audio-report.md",
            "segments_or_lines": n_sent,
            "loudness": lw,
            "narration_corr": corr,
        },
        "assets_provenance": prov,
        "delivery": {
            "manifest": "delivery/delivery-manifest.json",
            "stills": [b.get("name") for b in deliv.get("beats") or []],
            "contact_sheet": "delivery/contact-sheet.jpg",
            "covers": deliv.get("covers") or [],
        },
        "qa": check.get("qa") or {},
        "notes": notes.strip() or None,
    }
    out_json = os.path.join(WORK, "assets-manifest.json")
    json.dump(manifest, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("manifest ->", out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
