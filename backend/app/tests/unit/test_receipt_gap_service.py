from app.services.receipt_gap_service import ReceiptGapService


def test_finds_missing_receipts_in_sequence() -> None:
    numbers = [
        "SDC010193518/10",
        "SDC010193518/11",
        "SDC010193518/13",
        "SDC010193518/14",
        "SDC010193518/16",
    ]
    groups = ReceiptGapService().find_missing(numbers)

    assert len(groups) == 1
    group = groups[0]
    assert group.prefix == "SDC010193518"
    assert group.lowest == 10
    assert group.highest == 16
    assert group.present_count == 5
    assert group.missing == [12, 15]
    assert group.missing_count == 2
    assert group.missing_receipt_numbers == ["SDC010193518/12", "SDC010193518/15"]


def test_no_gaps_returns_empty_missing_list() -> None:
    numbers = ["SDC010193518/1", "SDC010193518/2", "SDC010193518/3"]
    groups = ReceiptGapService().find_missing(numbers)

    assert groups[0].missing == []
    assert groups[0].missing_count == 0


def test_unordered_input_is_handled_correctly() -> None:
    # mirrors real EBM exports, which are ordered by date, not receipt number
    numbers = ["SDC010193518/29", "SDC010193518/3", "SDC010193518/10", "SDC010193518/11"]
    groups = ReceiptGapService().find_missing(numbers)

    group = groups[0]
    assert group.lowest == 3
    assert group.highest == 29
    # everything between 3 and 29 except 3, 10, 11, 29 is missing
    assert 3 not in group.missing
    assert 29 not in group.missing
    assert 12 in group.missing
    assert len(group.missing) == 29 - 3 + 1 - 4


def test_multiple_device_prefixes_are_grouped_separately() -> None:
    numbers = ["SDC010193518/1", "SDC010193518/3", "SDC099999999/5", "SDC099999999/6"]
    groups = ReceiptGapService().find_missing(numbers)

    assert len(groups) == 2
    by_prefix = {g.prefix: g for g in groups}
    assert by_prefix["SDC010193518"].missing == [2]
    assert by_prefix["SDC099999999"].missing == []


def test_ignores_unparseable_and_none_invoice_numbers() -> None:
    numbers = ["SDC010193518/1", None, "not-a-receipt", "SDC010193518/2"]
    groups = ReceiptGapService().find_missing(numbers)

    assert len(groups) == 1
    assert groups[0].missing == []


def test_duplicate_receipt_numbers_counted_once() -> None:
    numbers = ["SDC010193518/1", "SDC010193518/1", "SDC010193518/2"]
    groups = ReceiptGapService().find_missing(numbers)

    assert groups[0].present_count == 2
