#!/usr/bin/env python3
import argparse
import json
import os
import time
from urllib import request, error


def post_json(url: str, payload: dict, timeout: int = 120):
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), time.time() - t0
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), time.time() - t0
    except Exception as e:
        return -1, str(e), time.time() - t0


def probe(base_url: str, model: str, ntoks: int, timeout: int):
    prompt = "x " * ntoks
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": f"{prompt}\n\nReply exactly: OK"}],
        "temperature": 0,
        "max_tokens": 2,
        "chat_template_kwargs": {"enable_thinking": False, "reasoning_effort": "low"},
    }
    st, body, elapsed = post_json(base_url.rstrip("/") + "/chat/completions", payload, timeout=timeout)
    rec = {"requested_tokens": ntoks, "status": st, "elapsed_sec": round(elapsed, 3)}
    if st == 200:
        try:
            parsed = json.loads(body)
            rec["usage_prompt_tokens"] = parsed.get("usage", {}).get("prompt_tokens")
            rec["content"] = (parsed.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        except Exception:
            rec["parse_error"] = "invalid_json"
            rec["body_head"] = body[:200]
    else:
        rec["error_head"] = body[:300]
    return rec


def smoke(base_url: str, model: str):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply exactly: OK"}],
        "temperature": 0,
        "max_tokens": 2,
        "chat_template_kwargs": {"enable_thinking": False, "reasoning_effort": "low"},
    }
    st, body, elapsed = post_json(base_url.rstrip("/") + "/chat/completions", payload, timeout=30)
    rec = {"status": st, "elapsed_sec": round(elapsed, 3)}
    if st == 200:
        try:
            parsed = json.loads(body)
            rec["content"] = (parsed.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
        except Exception:
            rec["content"] = ""
    else:
        rec["error_head"] = body[:200]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--sizes", nargs="+", type=int, default=[96000, 128000])
    ap.add_argument("--timeout", type=int, default=310)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = {
        "endpoint": args.base_url,
        "model": args.model,
        "sizes": args.sizes,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pre_smoke": smoke(args.base_url, args.model),
        "results": [],
    }

    for s in args.sizes:
        report["results"].append(probe(args.base_url, args.model, s, args.timeout))

    report["post_smoke"] = smoke(args.base_url, args.model)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
