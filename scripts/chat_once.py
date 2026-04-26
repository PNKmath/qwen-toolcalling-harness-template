#!/usr/bin/env python3
import argparse

from harness.runner import pretty_json, run_agent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("prompt", help="사용자 프롬프트")
    args = p.parse_args()

    out = run_agent(args.prompt)
    print(pretty_json(out))


if __name__ == "__main__":
    main()
