from __future__ import annotations

from sktr_git import parse_diff_stats


def test_parse_diff_stats_for_added_modified_deleted_files() -> None:
    changes = parse_diff_stats(
        name_status_output="\n".join(
            [
                "M\tsrc/orders/service.py",
                "A\tsrc/payments/client.py",
                "D\tsrc/legacy/payment.py",
            ]
        ),
        numstat_output="\n".join(
            [
                "10\t2\tsrc/orders/service.py",
                "25\t0\tsrc/payments/client.py",
                "0\t18\tsrc/legacy/payment.py",
            ]
        ),
    )

    assert [change.status for change in changes] == ["modified", "added", "deleted"]
    assert [change.path for change in changes] == [
        "src/orders/service.py",
        "src/payments/client.py",
        "src/legacy/payment.py",
    ]
    assert changes[0].added_lines == 10
    assert changes[0].removed_lines == 2
    assert changes[2].removed_lines == 18


def test_parse_diff_stats_for_renamed_file() -> None:
    changes = parse_diff_stats(
        name_status_output="R100\tsrc/old/payment.py\tsrc/new/payment.py",
        numstat_output="3\t1\tsrc/{old => new}/payment.py",
    )

    assert len(changes) == 1
    assert changes[0].status == "renamed"
    assert changes[0].old_path == "src/old/payment.py"
    assert changes[0].path == "src/new/payment.py"
    assert changes[0].added_lines == 3
    assert changes[0].removed_lines == 1


def test_parse_diff_stats_treats_binary_counts_as_zero() -> None:
    changes = parse_diff_stats(
        name_status_output="M\tassets/logo.png",
        numstat_output="-\t-\tassets/logo.png",
    )

    assert changes[0].added_lines == 0
    assert changes[0].removed_lines == 0
