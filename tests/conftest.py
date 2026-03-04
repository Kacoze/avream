"""
Shared pytest configuration and helpers for AVream tests.

All existing tests use unittest.IsolatedAsyncioTestCase and define their own
_paths() / stub helpers inline. New tests should follow the same pattern to
stay consistent with the rest of the test suite.
"""
