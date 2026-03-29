"""
Week 59 - Builder 2 Tests: Quality Assurance Module
Unit tests for QA Manager, Code Reviewer, and Defect Tracker
"""

import pytest
from parwa_testing_qa.quality_assurance import (
    QAManager, QACheck, QACheckStatus,
    CodeReviewer, CodeReview,
    DefectTracker, Defect, DefectSeverity, DefectStatus
)


class TestQAManager:
    """Tests for QAManager class"""

    @pytest.fixture
    def qa_manager(self):
        """Create QA manager"""
        return QAManager()

    def test_create_check(self, qa_manager):
        """Test check creation"""
        check = qa_manager.create_check("Security Review", "security")
        assert check.name == "Security Review"
        assert check.category == "security"

    def test_get_check(self, qa_manager):
        """Test get check"""
        check = qa_manager.create_check("Test", "category")
        retrieved = qa_manager.get_check(check.id)
        assert retrieved.name == "Test"

    def test_update_check_status(self, qa_manager):
        """Test update check status"""
        check = qa_manager.create_check("Test", "category")
        result = qa_manager.update_check_status(
            check.id, QACheckStatus.APPROVED, "reviewer1"
        )

        assert result is True
        assert qa_manager.get_check(check.id).status == QACheckStatus.APPROVED

    def test_create_checklist(self, qa_manager):
        """Test checklist creation"""
        c1 = qa_manager.create_check("Check 1", "cat")
        c2 = qa_manager.create_check("Check 2", "cat")
        qa_manager.create_checklist("release", [c1.id, c2.id])

        checklist = qa_manager.get_checklist("release")
        assert len(checklist) == 2

    def test_run_checklist(self, qa_manager):
        """Test run checklist"""
        c1 = qa_manager.create_check("Check 1", "cat")
        qa_manager.create_checklist("smoke", [c1.id])

        results = qa_manager.run_checklist("smoke")
        assert c1.id in results

    def test_request_approval(self, qa_manager):
        """Test approval request"""
        qa_manager.request_approval("release-1", ["alice", "bob"])
        assert "release-1" in qa_manager.approvals

    def test_approve(self, qa_manager):
        """Test approval"""
        qa_manager.request_approval("release-1", ["alice", "bob"])
        result = qa_manager.approve("release-1", "alice")

        assert result is True
        assert "alice" not in qa_manager.approvals["release-1"]

    def test_is_approved(self, qa_manager):
        """Test approval check"""
        qa_manager.request_approval("release-1", ["alice"])
        assert qa_manager.is_approved("release-1") is False

        qa_manager.approve("release-1", "alice")
        assert qa_manager.is_approved("release-1") is True

    def test_get_stats(self, qa_manager):
        """Test statistics"""
        check = qa_manager.create_check("Test", "cat")
        qa_manager.update_check_status(check.id, QACheckStatus.APPROVED)

        stats = qa_manager.get_stats()
        assert "total_checks" in stats


class TestCodeReviewer:
    """Tests for CodeReviewer class"""

    @pytest.fixture
    def reviewer(self):
        """Create code reviewer"""
        return CodeReviewer()

    def test_register_standard(self, reviewer):
        """Test standard registration"""
        reviewer.register_standard("pep8", ["E501", "W293"])
        assert "pep8" in reviewer.standards

    def test_create_review(self, reviewer):
        """Test review creation"""
        review = reviewer.create_review("/path/to/file.py", "alice")
        assert review.file_path == "/path/to/file.py"
        assert review.reviewer == "alice"

    def test_add_issue(self, reviewer):
        """Test adding issue"""
        review = reviewer.create_review("/path/file.py", "alice")
        result = reviewer.add_issue(review.id, 10, "Line too long")

        assert result is True
        assert len(reviewer.get_review(review.id).issues) == 1

    def test_add_suggestion(self, reviewer):
        """Test adding suggestion"""
        review = reviewer.create_review("/path/file.py", "alice")
        result = reviewer.add_suggestion(review.id, "Use list comprehension")

        assert result is True
        assert len(reviewer.get_review(review.id).suggestions) == 1

    def test_analyze_code(self, reviewer):
        """Test code analysis"""
        code = """
def test():
    print("debug")
    pass
"""
        issues = reviewer.analyze_code(code, "python")
        assert len(issues) >= 1  # Should find print statement

    def test_calculate_score(self, reviewer):
        """Test score calculation"""
        review = reviewer.create_review("/path/file.py", "alice")
        reviewer.add_issue(review.id, 10, "Issue", "warning")
        reviewer.add_issue(review.id, 20, "Error", "error")

        score = reviewer.calculate_score(review.id)
        assert score < 100  # Should have deductions

    def test_get_review(self, reviewer):
        """Test get review"""
        review = reviewer.create_review("/path/file.py", "alice")
        retrieved = reviewer.get_review(review.id)
        assert retrieved.file_path == "/path/file.py"


class TestDefectTracker:
    """Tests for DefectTracker class"""

    @pytest.fixture
    def tracker(self):
        """Create defect tracker"""
        return DefectTracker()

    def test_create_defect(self, tracker):
        """Test defect creation"""
        defect = tracker.create_defect(
            title="Bug in login",
            description="Login fails",
            severity=DefectSeverity.HIGH
        )

        assert defect.title == "Bug in login"
        assert defect.id.startswith("DEF-")

    def test_get_defect(self, tracker):
        """Test get defect"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        retrieved = tracker.get_defect(defect.id)
        assert retrieved.title == "Bug"

    def test_update_status(self, tracker):
        """Test status update"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        result = tracker.update_status(defect.id, DefectStatus.IN_PROGRESS)

        assert result is True
        assert tracker.get_defect(defect.id).status == DefectStatus.IN_PROGRESS

    def test_add_comment(self, tracker):
        """Test adding comment"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        result = tracker.add_comment(defect.id, "alice", "Fixed in PR #123")

        assert result is True
        assert len(tracker.get_defect(defect.id).comments) == 1

    def test_search_defects(self, tracker):
        """Test defect search"""
        tracker.create_defect("Bug1", "Desc", DefectSeverity.HIGH)
        tracker.create_defect("Bug2", "Desc", DefectSeverity.LOW)

        results = tracker.search_defects(severity=DefectSeverity.HIGH)
        assert len(results) == 1

    def test_get_stats(self, tracker):
        """Test statistics"""
        tracker.create_defect("Bug1", "Desc", DefectSeverity.HIGH)
        tracker.create_defect("Bug2", "Desc", DefectSeverity.LOW)

        stats = tracker.get_stats()
        assert stats["total"] == 2
        assert "HIGH" in stats["by_severity"]

    def test_resolve_defect(self, tracker):
        """Test resolve defect"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        result = tracker.resolve_defect(defect.id)

        assert result is True
        assert tracker.get_defect(defect.id).status == DefectStatus.RESOLVED

    def test_close_defect(self, tracker):
        """Test close defect"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        tracker.close_defect(defect.id)

        assert tracker.get_defect(defect.id).status == DefectStatus.CLOSED

    def test_reopen_defect(self, tracker):
        """Test reopen defect"""
        defect = tracker.create_defect("Bug", "Desc", DefectSeverity.MEDIUM)
        tracker.close_defect(defect.id)
        tracker.reopen_defect(defect.id)

        assert tracker.get_defect(defect.id).status == DefectStatus.REOPENED
