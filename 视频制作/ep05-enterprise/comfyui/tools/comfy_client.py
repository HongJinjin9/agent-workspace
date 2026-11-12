#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ComfyUI H3 视频版（优云智算 RTX5090）最小客户端。

用途：绕开浏览器，直接用 HTTP 操作这台被「WyfGate」门禁挡住的 ComfyUI：
  1) 用应用账号密码换取 wyfgate cookie（门禁只认这个 cookie）；
  2) 读取 /system_stats（显卡、显存、ComfyUI 版本）、/object_info（节点清单）、/models；
  3) 提交 API 格式工作流（UI 里「导出 (API)」得到的 JSON）→ 轮询 /history → 下载产物。

用法：
  export H3_USER=... H3_PASS=...
  python3 comfy_client.py stats
  python3 comfy_client.py nodes --grep MiniMax
  python3 comfy_client.py models
  python3 comfy_client.py run workflows/t2v_api.json --set 6.text="prompt 文本" --out out/
  python3 comfy_client.py history <prompt_id>

依赖：requests（本机已有）。
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests

DEFAULT_BASE = os.environ.get("H3_BASE", "https://wp08.unicorn.org.cn:24909")
DEFAULT_USER = os.environ.get("H3_USER", "")
DEFAULT_PASS = os.environ.get("H3_PASS", "")

# 便于 curl/浏览器之外复现：门禁 cookie 名固定为 wyfgate
GATE_COOKIE = "wyfgate"


class AppDownError(RuntimeError):
    """门禁后面的应用进程没起来（网关返回 502）。"""


class ComfyClient:
    def __init__(self, base=DEFAULT_BASE, user=DEFAULT_USER, password=DEFAULT_PASS, timeout=60):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "comfy-client/1.0 (agent-workspace)",
            "Accept": "application/json, text/html;q=0.9",
        })
        self.s.verify = False  # 自签证书；本机只访问该实例
        requests.packages.urllib3.disable_warnings()

    # ---------- 门禁 ----------
    def login(self) -> str:
        if not self.user or not self.password:
            raise SystemExit("缺少凭据：请先 export H3_USER=… H3_PASS=…（凭据不入库）")
        r = self.s.post(
            f"{self.base}/login",
            data={"u": self.user, "p": self.password, "next": "/"},
            allow_redirects=False,
            timeout=self.timeout,
        )
        loc = r.headers.get("location", "")
        if r.status_code != 302 or "err=1" in loc:
            raise SystemExit(f"登录失败：status={r.status_code} location={loc}（账号密码不对？）")
        cookie = self.s.cookies.get(GATE_COOKIE)
        if not cookie:
            raise SystemExit("登录返回 302 但没拿到 wyfgate cookie")
        return cookie

    def _request(self, method, path, **kw):
        kw.setdefault("timeout", self.timeout)
        r = self.s.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 401:
            # 会话过期：重新登录一次再试
            self.login()
            r = self.s.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 502:
            raise AppDownError(
                "502 Bad Gateway：门禁通了，但后面的 ComfyUI 进程没起来"
                "（实例未开机 / 应用启动中 / 应用崩溃）。"
            )
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        return r

    def get_json(self, path, **kw):
        return self._request("GET", path, **kw).json()

    def post_json(self, path, payload, **kw):
        return self._request("POST", path, json=payload, **kw).json()

    # ---------- 只读接口 ----------
    def system_stats(self):
        return self.get_json("/system_stats")

    def object_info(self, node=None):
        return self.get_json(f"/object_info/{node}" if node else "/object_info")

    def models(self):
        try:
            return self.get_json("/models")
        except RuntimeError:
            return {}

    def queue(self):
        return self.get_json("/queue")

    def history(self, prompt_id=None):
        return self.get_json(f"/history/{prompt_id}" if prompt_id else "/history")

    def userdata_workflows(self):
        """列出用户工作流目录（ComfyUI 新版 /userdata 接口）。"""
        out = {}
        for sub in ("workflows",):
            try:
                out[sub] = self.get_json(f"/userdata?dir={sub}&recurse=true&split=false&full_info=false")
            except RuntimeError as e:
                out[sub] = f"不可用: {e}"
        return out

    # ---------- 提交与等待 ----------
    def submit(self, workflow: dict, client_id=None) -> str:
        client_id = client_id or uuid.uuid4().hex
        r = self.post_json("/prompt", {"prompt": workflow, "client_id": client_id})
        if "prompt_id" not in r:
            raise RuntimeError(f"提交失败：{json.dumps(r, ensure_ascii=False)[:800]}")
        return r["prompt_id"]

    def wait(self, prompt_id, timeout=1800, interval=3.0, quiet=False):
        t0 = time.time()
        while time.time() - t0 < timeout:
            h = self.history(prompt_id)
            if prompt_id in h:
                entry = h[prompt_id]
                status = entry.get("status", {})
                if status.get("completed") or status.get("status_str") in ("success", "error"):
                    if not quiet:
                        print(f"[wait] 完成，用时 {time.time() - t0:.1f}s，"
                              f"status={status.get('status_str')}", file=sys.stderr)
                    return entry
            if not quiet:
                print(f"[wait] {time.time() - t0:6.1f}s …", file=sys.stderr, end="\r")
            time.sleep(interval)
        raise TimeoutError(f"等待 {prompt_id} 超时（{timeout}s）")

    def outputs_of(self, entry):
        """把 history entry 展平成 [{filename, subfolder, type, kind}]。"""
        out = []
        for node_id, node_out in (entry.get("outputs") or {}).items():
            for kind in ("images", "gifs", "videos", "audio", "files"):
                for item in node_out.get(kind) or []:
                    # 只收正式产物；LoadVideo 之类的输入预览(type=input)不算
                    if isinstance(item, dict) and item.get("filename") and item.get("type") != "input":
                        out.append({
                            "node": node_id,
                            "kind": kind,
                            **{k: item.get(k, "") for k in ("filename", "subfolder", "type")},
                        })
        return out

    def download(self, filename, subfolder="", type_="output") -> bytes:
        r = self._request("GET", "/view", params={
            "filename": filename, "subfolder": subfolder, "type": type_,
        }, timeout=600)
        return r.content


def _set_param(workflow, spec, value):
    """把 value 写进某个节点的 inputs，spec 形如 '140:131.prompt' 或 '140:133.value:num'。

    注意：ComfyUI API 工作流里节点参数都在 node["inputs"] 下，不在节点顶层。
    """
    node_id, _, path = spec.partition(".")
    if not path:
        raise SystemExit(f"--set 需要 '节点ID.参数名=值' 形式，收到 {spec!r}")
    node = workflow[node_id]
    inputs = node.setdefault("inputs", {})
    key = path
    if key.endswith(":json"):
        inputs[key[: -len(":json")]] = json.loads(value)
    elif key.endswith(":num"):
        key = key[: -len(":num")]
        inputs[key] = float(value) if "." in value else int(value)
    else:
        inputs[key] = value


def main():
    ap = argparse.ArgumentParser(description="ComfyUI H3 客户端")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--passwd", default=DEFAULT_PASS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login")
    sub.add_parser("stats")
    sub.add_parser("models")
    sub.add_parser("queue")
    sub.add_parser("workflows")

    p_nodes = sub.add_parser("nodes")
    p_nodes.add_argument("--grep", default="")
    p_nodes.add_argument("--node", default="")

    p_run = sub.add_parser("run")
    p_run.add_argument("workflow")
    p_run.add_argument("--set", action="append", default=[], metavar="SPEC=VALUE")
    p_run.add_argument("--out", default="out")
    p_run.add_argument("--timeout", type=int, default=1800)
    p_run.add_argument("--dry", action="store_true")

    p_h = sub.add_parser("history")
    p_h.add_argument("prompt_id", nargs="?")

    args = ap.parse_args()
    c = ComfyClient(args.base, args.user, args.passwd)
    c.login()

    if args.cmd == "login":
        print("登录成功，cookie 已保存到会话")

    elif args.cmd == "stats":
        print(json.dumps(c.system_stats(), ensure_ascii=False, indent=2))

    elif args.cmd == "models":
        print(json.dumps(c.models(), ensure_ascii=False, indent=2))

    elif args.cmd == "queue":
        print(json.dumps(c.queue(), ensure_ascii=False, indent=2))

    elif args.cmd == "workflows":
        print(json.dumps(c.userdata_workflows(), ensure_ascii=False, indent=2)[:4000])

    elif args.cmd == "nodes":
        info = c.object_info()
        names = sorted(info)
        if args.grep:
            import re
            names = [n for n in names if re.search(args.grep, n, re.I)]
        if args.node:
            print(json.dumps(info.get(args.node, {}), ensure_ascii=False, indent=2))
        else:
            print(f"共 {len(info)} 个节点，匹配 {len(names)} 个：")
            print("\n".join(names))

    elif args.cmd == "history":
        print(json.dumps(c.history(args.prompt_id), ensure_ascii=False, indent=2)[:6000])

    elif args.cmd == "run":
        wf = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
        for spec in args.set:
            k, _, v = spec.partition("=")
            _set_param(wf, k, v)
        if args.dry:
            print(json.dumps(wf, ensure_ascii=False, indent=2))
            return
        pid = c.submit(wf)
        print(f"[run] prompt_id={pid}")
        t0 = time.time()
        entry = c.wait(pid, timeout=args.timeout)
        print(f"[run] elapsed={time.time() - t0:.1f}s")
        outs = c.outputs_of(entry)
        outdir = Path(args.out)
        for o in outs:
            data = c.download(o["filename"], o["subfolder"], o["type"])
            outdir.mkdir(parents=True, exist_ok=True)
            p = outdir / o["filename"]
            p.write_bytes(data)
            print(f"[run] saved {p} ({len(data)/1048576:.2f} MB)")
        print(json.dumps({"prompt_id": pid, "elapsed": round(time.time() - t0, 1),
                          "outputs": outs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AppDownError as e:
        print(f"[APP DOWN] {e}", file=sys.stderr)
        sys.exit(2)
