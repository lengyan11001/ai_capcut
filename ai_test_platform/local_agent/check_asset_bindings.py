from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict


def _normalize(value: str) -> str:
    return (value or "").strip()


def _load_rows(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
        return rows


def _is_active(row: dict[str, str]) -> bool:
    return _normalize(row.get("status", "")).lower() == "active"


def validate(path: str) -> tuple[bool, list[str]]:
    rows = _load_rows(path)
    errors: list[str] = []
    warnings: list[str] = []

    required_columns = {
        "reddit_username",
        "device_serial",
        "proxy_name",
        "proxy_exit_ip",
        "status",
    }
    if not rows:
        errors.append("绑定表为空，请至少配置一条记录。")
        return False, errors
    missing = [c for c in required_columns if c not in rows[0]]
    if missing:
        errors.append(f"缺少必填列: {', '.join(missing)}")
        return False, errors

    account_active_rows: dict[str, list[int]] = defaultdict(list)
    account_to_device: dict[str, set[str]] = defaultdict(set)
    account_to_proxy_ip: dict[str, set[str]] = defaultdict(set)
    device_to_accounts: dict[str, set[str]] = defaultdict(set)

    for idx, row in enumerate(rows, start=2):
        account = _normalize(row.get("reddit_username", ""))
        device = _normalize(row.get("device_serial", ""))
        proxy_ip = _normalize(row.get("proxy_exit_ip", ""))
        status = _normalize(row.get("status", "")).lower()

        if not account:
            errors.append(f"第 {idx} 行 reddit_username 为空。")
            continue
        if status not in {"active", "paused", "disabled"}:
            errors.append(f"第 {idx} 行 status 非法: {status}（允许 active|paused|disabled）。")
            continue
        if _is_active(row):
            if not device:
                errors.append(f"第 {idx} 行 active 记录缺少 device_serial。")
            if not proxy_ip:
                errors.append(f"第 {idx} 行 active 记录缺少 proxy_exit_ip。")
            account_active_rows[account].append(idx)
            if device:
                account_to_device[account].add(device)
                device_to_accounts[device].add(account)
            if proxy_ip:
                account_to_proxy_ip[account].add(proxy_ip)

    for account, row_ids in account_active_rows.items():
        if len(row_ids) > 1:
            warnings.append(f"账号 {account} 有多条 active 记录: {row_ids}")
        devices = account_to_device.get(account, set())
        if len(devices) > 1:
            errors.append(f"账号 {account} 绑定了多个设备: {sorted(devices)}")
        proxy_ips = account_to_proxy_ip.get(account, set())
        if len(proxy_ips) > 1:
            errors.append(f"账号 {account} 绑定了多个出口 IP: {sorted(proxy_ips)}")

    for device, accounts in device_to_accounts.items():
        if len(accounts) > 1:
            warnings.append(f"设备 {device} 绑定多个账号: {sorted(accounts)}（建议减少切号）")

    if warnings:
        print("WARN:")
        for item in warnings:
            print(f"  - {item}")

    return len(errors) == 0, errors


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "ASSET_BINDINGS_CSV", "docs/ASSET_BINDING_TEMPLATE.csv"
    )
    if not os.path.exists(path):
        print(f"ERROR: 绑定表不存在: {path}")
        return 2

    ok, errors = validate(path)
    if not ok:
        print("ERROR:")
        for item in errors:
            print(f"  - {item}")
        return 1

    print(f"OK: 绑定校验通过 -> {path}")
    print("建议：执行任务前保持账号-设备-代理固定绑定，避免频繁切换。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
