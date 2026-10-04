"""A skipped test fails the run (spec 5.2; V1_LESSONS 8.6).

In v1 about 457 tests skipped silently when a database or Node was
missing. Here a skip is an accident, and the run says so and fails.
"""


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = len(reporter.stats.get("skipped", [])) if reporter else 0
    if skipped and session.exitstatus == 0:
        reporter.write_line(
            f"{skipped} test(s) were skipped. A skipped test fails the run.", red=True
        )
        session.exitstatus = 1
