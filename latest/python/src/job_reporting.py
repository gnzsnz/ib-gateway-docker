"""Slack wording shared by the admin (test_jobs.py) and client
(test_plot_clients.py) Market Intelligence jobs."""
import os
import traceback

# Keeps the Slack message readable when IB repeats the same error.
MAX_IB_ERRORS = 5


def failure_detail(exc: BaseException) -> str:
    """'TypeError: msg (ibkr_services.py:249 in fetch_and_upsert)': the error
    plus the innermost frame, so the alert says where it broke without
    needing the pod logs."""
    frames = traceback.extract_tb(exc.__traceback__)
    detail = f"{type(exc).__name__}: {exc}"
    if frames:
        frame = frames[-1]
        detail += f" ({os.path.basename(frame.filename)}:{frame.lineno} in {frame.name})"
    return detail


def skipped_detail(fetch_result: dict) -> str:
    """'' when every asset was fetched; otherwise which assets kept their
    previous prices and the IB errors seen during the fetch."""
    skipped = fetch_result.get("skipped") or []
    if not skipped:
        return ""

    detail = f"no IBKR data for {', '.join(skipped)}: previous prices kept, next run fills the gap"
    ib_errors = fetch_result.get("ib_errors") or []
    if ib_errors:
        lines = ib_errors[:MAX_IB_ERRORS]
        if len(ib_errors) > MAX_IB_ERRORS:
            lines.append(f"… and {len(ib_errors) - MAX_IB_ERRORS} more")
        detail += "\n" + "\n".join(f"• {line}" for line in lines)
    else:
        detail += " (no IB error reported, the history request timed out)"
    return detail
