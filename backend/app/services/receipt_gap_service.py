"""Detects gaps in EBM SDC receipt-number sequences (e.g. SDC010193518/10,
SDC010193518/11, ... a missing /12 flags an unreported/unrecorded sale).

Pure business logic, no I/O — see app/tests/unit/test_receipt_gap_service.py.
"""
import re
from dataclasses import dataclass

_RECEIPT_PATTERN = re.compile(r"^(?P<prefix>.+)/(?P<seq>\d+)$")


@dataclass(frozen=True)
class ReceiptGapGroup:
    prefix: str
    lowest: int
    highest: int
    present_count: int
    missing: list[int]

    @property
    def missing_receipt_numbers(self) -> list[str]:
        return [f"{self.prefix}/{n}" for n in self.missing]

    @property
    def missing_count(self) -> int:
        return len(self.missing)


class ReceiptGapService:
    """Groups receipt numbers by their SDC device prefix (the part before the
    final "/<sequence>") and reports any sequence numbers missing between the
    lowest and highest number seen for that prefix."""

    def find_missing(self, invoice_numbers: list[str | None]) -> list[ReceiptGapGroup]:
        groups: dict[str, set[int]] = {}
        for raw in invoice_numbers:
            if not raw:
                continue
            match = _RECEIPT_PATTERN.match(raw.strip())
            if not match:
                continue
            prefix = match.group("prefix")
            seq = int(match.group("seq"))
            groups.setdefault(prefix, set()).add(seq)

        results = []
        for prefix, seqs in groups.items():
            lowest, highest = min(seqs), max(seqs)
            missing = sorted(set(range(lowest, highest + 1)) - seqs)
            results.append(
                ReceiptGapGroup(
                    prefix=prefix,
                    lowest=lowest,
                    highest=highest,
                    present_count=len(seqs),
                    missing=missing,
                )
            )
        return sorted(results, key=lambda g: g.prefix)
