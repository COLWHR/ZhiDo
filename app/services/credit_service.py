"""Credit (积分) ledger: prepaid balance, estimation, deduction and adjustment.

Rules are configurable from the admin panel (system_config). Consumption is
estimated from message length when the SDK does not return a real usage object;
vision calls carry a fixed per-call surcharge.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from app.db.client import db_transaction, fetch_one, fetch_all
from app.services import system_config_service as config_service

logger = logging.getLogger(__name__)

DEFAULT_SIGNUP_BONUS = 1000


class InsufficientCreditsError(RuntimeError):
    """Raised when the account balance cannot cover an estimated cost."""

    def __init__(self, balance: int, required: int, message: str = "积分余额不足"):
        super().__init__(message)
        self.balance = balance
        self.required = required
        self.message = message


def _approx_tokens(text: Optional[str]) -> int:
    """Rough token estimate for CJK-heavy / mixed text without a tokenizer."""
    if not text:
        return 0
    return max(1, len(text) // 2)


def estimate_credits(
    db: Any,
    *,
    tokens_input: int = 0,
    tokens_output: int = 0,
    vision_count: int = 0,
) -> int:
    """Compute the credit cost for a usage record using configured rates."""
    rate_per_1k = config_service.get_config_int(db, "credit.per_1k_text_tokens", 1)
    vision_per_call = config_service.get_config_int(db, "credit.vision_per_call", 5)

    text_tokens = max(0, tokens_input) + max(0, tokens_output)
    text_blocks = (text_tokens + 999) // 1000
    text_cost = text_blocks * max(0, rate_per_1k)
    vision_cost = max(0, vision_count) * max(0, vision_per_call)
    return text_cost + vision_cost


def estimate_from_text(
    db: Any,
    *,
    input_text: str = "",
    output_text: str = "",
    vision_count: int = 0,
) -> dict[str, int]:
    """Estimate tokens and credits from plain text (used when usage is absent)."""
    tokens_input = _approx_tokens(input_text)
    tokens_output = _approx_tokens(output_text)
    cost = estimate_credits(
        db,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        vision_count=vision_count,
    )
    return {
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "vision_count": vision_count,
        "cost": cost,
    }


def get_balance(db: Any, user_id: int) -> int:
    rs = db.execute("SELECT COALESCE(credits_balance, ?) AS balance FROM users WHERE id = ?", [DEFAULT_SIGNUP_BONUS, user_id])
    row = fetch_one(rs)
    if row is None:
        return 0
    return int(getattr(row, "balance", 0) or 0)


def _min_balance(db: Any) -> int:
    return config_service.get_config_int(db, "credit.min_balance", 0)


def check_sufficient(db: Any, user_id: int, estimated_cost: int) -> int:
    """Raise InsufficientCreditsError unless the balance covers the cost + floor."""
    balance = get_balance(db, user_id)
    floor = _min_balance(db)
    if balance - estimated_cost < floor:
        raise InsufficientCreditsError(balance=balance, required=estimated_cost)
    return balance


def _commit(tx: Any, db: Any) -> None:
    """Persist the transaction (libsql needs an explicit commit)."""
    if hasattr(tx, "commit"):
        tx.commit()
    elif hasattr(db, "commit"):
        db.commit()


def _insert_transaction(
    tx: Any,
    *,
    user_id: int,
    change_amount: int,
    balance_after: int,
    reason: str,
    category: str,
    tokens_input: int,
    tokens_output: int,
    vision_count: int,
    reference_type: Optional[str],
    reference_id: Optional[int],
    note: Optional[str],
) -> None:
    tx.execute(
        """
        INSERT INTO credit_transactions (
            user_id, change_amount, balance_after, reason, category,
            tokens_input, tokens_output, vision_count, reference_type, reference_id, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            user_id,
            change_amount,
            balance_after,
            reason,
            category,
            tokens_input,
            tokens_output,
            vision_count,
            reference_type,
            reference_id,
            note,
            datetime.now(),
        ],
    )


def charge(
    db: Any,
    user_id: int,
    *,
    category: str = "text",
    tokens_input: int = 0,
    tokens_output: int = 0,
    vision_count: int = 0,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    note: Optional[str] = None,
    reason: str = "consume",
) -> dict[str, Any]:
    """Atomically deduct estimated credits from the user's balance."""
    cost = estimate_credits(
        db,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        vision_count=vision_count,
    )
    if cost <= 0:
        return {"balance": get_balance(db, user_id), "cost": 0, "transaction": None}

    with db_transaction(db) as tx:
        rs = tx.execute("SELECT COALESCE(credits_balance, ?) AS balance FROM users WHERE id = ?", [DEFAULT_SIGNUP_BONUS, user_id])
        row = fetch_one(rs)
        if row is None:
            raise ValueError("User not found")
        balance = int(getattr(row, "balance", 0) or 0)
        floor = _min_balance(db)
        if balance - cost < floor:
            raise InsufficientCreditsError(balance=balance, required=cost)

        new_balance = balance - cost
        tx.execute("UPDATE users SET credits_balance = ? WHERE id = ?", [new_balance, user_id])
        _insert_transaction(
            tx,
            user_id=user_id,
            change_amount=-cost,
            balance_after=new_balance,
            reason=reason,
            category=category,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            vision_count=vision_count,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
        )
        _commit(tx, db)

    logger.info("Charged %s credits to user %s (balance %s).", cost, user_id, new_balance)
    return {"balance": new_balance, "cost": cost, "transaction": None}


def grant(
    db: Any,
    user_id: int,
    amount: int,
    *,
    reason: str = "recharge",
    category: str = "admin",
    note: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
) -> dict[str, Any]:
    """Add credits to an account (recharge / signup bonus / admin grant)."""
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Grant amount must be positive")

    with db_transaction(db) as tx:
        rs = tx.execute("SELECT COALESCE(credits_balance, ?) AS balance FROM users WHERE id = ?", [DEFAULT_SIGNUP_BONUS, user_id])
        row = fetch_one(rs)
        if row is None:
            raise ValueError("User not found")
        balance = int(getattr(row, "balance", 0) or 0)
        new_balance = balance + amount
        tx.execute("UPDATE users SET credits_balance = ? WHERE id = ?", [new_balance, user_id])
        _insert_transaction(
            tx,
            user_id=user_id,
            change_amount=amount,
            balance_after=new_balance,
            reason=reason,
            category=category,
            tokens_input=0,
            tokens_output=0,
            vision_count=0,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
        )
        _commit(tx, db)
    return {"balance": new_balance, "granted": amount}


def adjust(
    db: Any,
    user_id: int,
    amount: int,
    *,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Admin manual adjustment: positive grants, negative deducts; never below 0."""
    amount = int(amount)
    with db_transaction(db) as tx:
        rs = tx.execute("SELECT COALESCE(credits_balance, ?) AS balance FROM users WHERE id = ?", [DEFAULT_SIGNUP_BONUS, user_id])
        row = fetch_one(rs)
        if row is None:
            raise ValueError("User not found")
        balance = int(getattr(row, "balance", 0) or 0)
        new_balance = max(0, balance + amount)
        tx.execute("UPDATE users SET credits_balance = ? WHERE id = ?", [new_balance, user_id])
        _insert_transaction(
            tx,
            user_id=user_id,
            change_amount=new_balance - balance,
            balance_after=new_balance,
            reason="admin_adjust",
            category="admin",
            tokens_input=0,
            tokens_output=0,
            vision_count=0,
            reference_type="admin",
            reference_id=None,
            note=note,
        )
        _commit(tx, db)
    return {"balance": new_balance, "adjusted": new_balance - balance}


def ensure_signup_bonus(db: Any, user_id: int) -> None:
    """Set the one-time signup bonus when the account has no prior transactions.

    The users column ships with a default balance, so this reconciles the
    balance to the bonus amount instead of adding the bonus on top of the
    default to avoid double counting.
    """
    bonus = config_service.get_config_int(db, "credit.signup_bonus", DEFAULT_SIGNUP_BONUS)
    if bonus <= 0:
        return
    rs = db.execute("SELECT COUNT(*) AS cnt FROM credit_transactions WHERE user_id = ?", [user_id])
    row = fetch_one(rs)
    existing = int(getattr(row, "cnt", 0) or 0)
    if existing > 0:
        return

    balance = get_balance(db, user_id)
    new_balance = max(bonus, balance)
    delta = new_balance - balance
    with db_transaction(db) as tx:
        tx.execute("UPDATE users SET credits_balance = ? WHERE id = ?", [new_balance, user_id])
        _insert_transaction(
            tx,
            user_id=user_id,
            change_amount=delta,
            balance_after=new_balance,
            reason="signup",
            category="signup",
            tokens_input=0,
            tokens_output=0,
            vision_count=0,
            reference_type="signup",
            reference_id=None,
            note="注册赠送积分",
        )
        _commit(tx, db)


def list_transactions(db: Any, user_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    if user_id is not None:
        rs = db.execute(
            "SELECT * FROM credit_transactions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [user_id, limit, offset],
        )
    else:
        rs = db.execute(
            "SELECT * FROM credit_transactions ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            [limit, offset],
        )
    rows = fetch_all(rs)
    return [
        {
            "id": getattr(row, "id", None),
            "user_id": getattr(row, "user_id", None),
            "change_amount": getattr(row, "change_amount", 0),
            "balance_after": getattr(row, "balance_after", 0),
            "reason": getattr(row, "reason", None),
            "category": getattr(row, "category", None),
            "tokens_input": getattr(row, "tokens_input", 0),
            "tokens_output": getattr(row, "tokens_output", 0),
            "vision_count": getattr(row, "vision_count", 0),
            "reference_type": getattr(row, "reference_type", None),
            "reference_id": getattr(row, "reference_id", None),
            "note": getattr(row, "note", None),
            "created_at": getattr(row, "created_at", None),
        }
        for row in rows
    ]


def get_summary(db: Any) -> dict[str, Any]:
    rs = db.execute(
        """
        SELECT
            COUNT(*) AS user_count,
            COALESCE(SUM(credits_balance), 0) AS total_balance,
            COALESCE((SELECT SUM(change_amount) FROM credit_transactions WHERE change_amount > 0), 0) AS total_issued,
            COALESCE((SELECT SUM(-change_amount) FROM credit_transactions WHERE change_amount < 0), 0) AS total_consumed
        FROM users
        """
    )
    row = fetch_one(rs)
    return {
        "user_count": int(getattr(row, "user_count", 0) or 0),
        "total_balance": int(getattr(row, "total_balance", 0) or 0),
        "total_issued": int(getattr(row, "total_issued", 0) or 0),
        "total_consumed": int(getattr(row, "total_consumed", 0) or 0),
    }
