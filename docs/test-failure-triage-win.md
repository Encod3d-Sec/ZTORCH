# Test failure triage (merged tree, this Windows seat)

45 failed / 490 passed on the post-merge tree. Root-cause classes:

1. WinError 1314 symlink privilege (~20 tests): pytest tmp_path factories call
   os.symlink; Windows needs admin or Developer Mode. Seat limitation, NOT a
   regression. Files: test_autonomy (11), test_foothold (8), test_board (1),
   test_vector_workflows (partial), test_workflow_cleanup.
2. Path-separator assertions (~8): tests assert forward-slash paths
   ("wiki/tools/broken.md" in err) but the harness prints os.sep backslash form
   on Windows (wiki\tools\broken.md). Files: test_index (3), test_hunt_wiki
   (4: canonical wiki slug join), test_tells (1: path-vs-content regex on \).
   Cosmetic test portability gap; behavior identical on POSIX seats.
3. Subprocess/tool availability (test_with_server x2): FileNotFoundError
   spawning a POSIX-named binary. Seat limitation.
4. test_background_tabs vm-rsh timeout test: empty stdout where the mock
   expected payload; likely a bash-vs-WSL bridge difference on this seat.
5. test_hunt_wiki canonical-wiki: index enumerates CTF dirs instead of
   wiki/techniques/capability-primitives; wiki-index slug join differs on \.

None are logic regressions from the merge: identical failures WITH and WITHOUT
the uncommitted harvest WIP (stash-verified both ways), and the dominant class
is a documented Windows symlink privilege limit. Second seat (WSL/Linux) ran
this suite green per session/log.md 2026-10-05 entries (suite 526).
