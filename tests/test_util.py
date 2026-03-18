from zeal.util import _ZEAL_DIR, _is_internal_frame


class TestIsInternalFrame:
    def test_zeal_source_files_are_internal(self):
        assert _is_internal_frame(f"{_ZEAL_DIR}/listeners.py")
        assert _is_internal_frame(f"{_ZEAL_DIR}/patch.py")
        assert _is_internal_frame(f"{_ZEAL_DIR}/util.py")

    def test_site_packages_are_internal(self):
        assert _is_internal_frame(
            "/usr/lib/python3.9/site-packages/django/db/models/query.py"
        )
        assert _is_internal_frame(
            "/home/user/.venv/lib/python3.12/site-packages/rest_framework/views.py"
        )

    def test_user_code_is_not_internal(self):
        assert not _is_internal_frame("/home/user/myapp/views.py")
        assert not _is_internal_frame("/app/src/myapp/models.py")

    def test_project_named_zeal_is_not_internal(self):
        """A user project with 'zeal' in the path should not be filtered."""
        assert not _is_internal_frame("/home/user/zeal-app/views.py")
        assert not _is_internal_frame("/home/user/zeal/myapp/views.py")
        assert not _is_internal_frame(
            "/home/user/projects/zeal-analytics/src/main.py"
        )
