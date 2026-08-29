"""CR-003: the dependency tree must stay open source, transitives included."""

from pcbkit.core import licences


def test_the_installed_tree_is_open_source():
    envelope = licences.audit()
    assert envelope.data["count"] > 10, "audit found suspiciously few packages"
    assert envelope.error_count == 0, "\n".join(
        f.one_line() for f in envelope.findings
    )


def test_unstated_licence_is_rejected_not_assumed_permissive():
    """CR-003 ruling: absence of a licence is rejection, not permission."""
    assert licences._OSI.search("") is None
    assert licences._OSI.search("Proprietary") is None


def test_common_open_licences_are_recognised():
    for text in ("MIT", "BSD-3-Clause", "Apache-2.0", "GNU LGPL v2.1",
                 "Mozilla Public License 2.0", "ISC", "Python Software Foundation License"):
        assert licences._OSI.search(text), text


def test_audit_reports_violations_as_findings_not_exceptions():
    envelope = licences.audit()
    assert envelope.ok is True
