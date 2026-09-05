import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))


def test_owned_receipt_claims_only_that_pid():
    import terminal_census as tc

    rows = [
        {
            "Name": "powershell.exe",
            "ProcessId": 100,
            "ParentProcessId": 1,
            "CommandLine": "powershell -NoLogo -NoExit -ExecutionPolicy Bypass -Command -",
        },
        {
            "Name": "conhost.exe",
            "ProcessId": 101,
            "ParentProcessId": 100,
            "CommandLine": r"\??\C:\WINDOWS\system32\conhost.exe 0x4",
        },
        {
            "Name": "powershell.exe",
            "ProcessId": 200,
            "ParentProcessId": 1,
            "CommandLine": "powershell.exe",
        },
    ]

    snap = tc.build_snapshot(rows, owned_pids={100})

    assert snap["counts"]["oracle_related"] == 2
    assert snap["counts"]["unclassified"] == 1
    owners = {r["pid"]: r["owner"] for r in snap["records"]}
    assert owners[100] == "oracle_owned"
    assert owners[101] == "oracle_child"
    assert owners[200] == "unclassified"


def test_codex_and_external_helpers_are_not_oracle_owned():
    import terminal_census as tc

    rows = [
        {
            "Name": "cmd.exe",
            "ProcessId": 10,
            "ParentProcessId": 1,
            "CommandLine": r'C:\WINDOWS\system32\cmd.exe /d /s /c "C:\Users\noahh\.codex\plugins\cache\openai-bundled\chrome\extension-host.exe"',
        },
        {
            "Name": "cmd.exe",
            "ProcessId": 20,
            "ParentProcessId": 1,
            "CommandLine": r'C:\WINDOWS\system32\cmd.exe /d /s /c "C:\Program Files\WindowsApps\AppleInc.iCloud\iCloudChrome.exe"',
        },
    ]

    snap = tc.build_snapshot(rows, owned_pids=set())

    assert snap["counts"]["codex_related"] == 1
    assert snap["counts"]["external_helpers"] == 1
    assert snap["counts"]["oracle_related"] == 0


def test_terminal_limit_flags_excess_shell_processes():
    import terminal_census as tc

    rows = [
        {"Name": "powershell.exe", "ProcessId": pid, "ParentProcessId": 1, "CommandLine": "powershell.exe"}
        for pid in range(10, 16)
    ]

    snap = tc.build_snapshot(rows, owned_pids=set(), max_shells=4)

    assert snap["counts"]["shell_processes"] == 6
    assert snap["counts"]["excess_shells_over_limit"] == 2
