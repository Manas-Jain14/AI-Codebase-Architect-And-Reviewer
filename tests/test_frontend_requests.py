from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from streamlit.testing.v1 import AppTest

from frontend import http_client


APP_PATH = Path(__file__).resolve().parents[1] / "frontend" / "streamlit_app.py"
sys.path.insert(0, str(APP_PATH.parent))
PROJECTS = [{"id": 1, "project_name": "sample"}]
ARCHITECTURE = {
    "project_metrics": {
        "total_files": 1,
        "total_folders": 1,
        "python_files": 1,
        "functions": 0,
        "classes": 0,
        "api_routes": 0,
    }
}
REPORT = {
    "summary": "summary",
    "architecture": "architecture",
    "strengths": [],
    "weaknesses": [],
    "roadmap": [],
}


def make_response(
    status_code: int,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
    url: str = "https://backend.example/test",
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    response.encoding = "utf-8"
    response.url = url
    response.reason = "Too Many Requests" if status_code == 429 else "OK"
    response.headers.update(headers or {})
    return response


class GetRetryTests(unittest.TestCase):
    def test_retries_429_using_retry_after(self) -> None:
        with (
            patch.object(
                http_client.requests,
                "get",
                side_effect=[
                    make_response(429, {}, headers={"Retry-After": "1"}),
                    make_response(200, {"ok": True}),
                ],
            ) as get,
            patch.object(http_client.time, "sleep") as sleep,
        ):
            response = http_client.get_with_retries("https://backend.example/projects", timeout=1)

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_retries_429_without_retry_after_using_jitter(self) -> None:
        with (
            patch.object(
                http_client.requests,
                "get",
                side_effect=[make_response(429, {}), make_response(200, {"ok": True})],
            ) as get,
            patch.object(http_client.random, "uniform", return_value=0.25),
            patch.object(http_client.time, "sleep") as sleep,
        ):
            response = http_client.get_with_retries("https://backend.example/projects", timeout=1)

        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(0.25)

    def test_does_not_retry_when_retry_after_exceeds_wait_limit(self) -> None:
        with (
            patch.object(
                http_client.requests,
                "get",
                return_value=make_response(429, {}, headers={"Retry-After": "60"}),
            ) as get,
            patch.object(http_client.time, "sleep") as sleep,
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                http_client.get_with_retries("https://backend.example/projects", timeout=1)

        get.assert_called_once()
        sleep.assert_not_called()

    def test_retries_are_bounded_by_max_attempts(self) -> None:
        with (
            patch.object(
                http_client.requests,
                "get",
                return_value=make_response(429, {}),
            ) as get,
            patch.object(http_client.random, "uniform", return_value=0.1),
            patch.object(http_client.time, "sleep"),
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                http_client.get_with_retries("https://backend.example/projects", timeout=1)

        self.assertEqual(get.call_count, http_client.GET_MAX_RETRIES + 1)

    def test_allowed_404_is_returned_for_optional_data_endpoints(self) -> None:
        with patch.object(
            http_client.requests,
            "get",
            return_value=make_response(404, {}),
        ):
            response = http_client.get_with_retries(
                "https://backend.example/report/1",
                timeout=1,
                allowed_statuses=frozenset({404}),
            )

        self.assertEqual(response.status_code, 404)


class UploadRequestTests(unittest.TestCase):
    def test_upload_makes_one_post_and_does_not_retry_429(self) -> None:
        with patch.object(
            http_client.requests,
            "post",
            return_value=make_response(429, {}, headers={"Retry-After": "1"}),
        ) as post:
            with self.assertRaises(requests.exceptions.HTTPError):
                http_client.upload_zip(
                    "https://backend.example/upload-project",
                    "sample.zip",
                    b"zip",
                )

        post.assert_called_once()


class RequestErrorTests(unittest.TestCase):
    def test_429_message_is_clear_and_includes_retry_after(self) -> None:
        response = make_response(429, {}, headers={"Retry-After": "30"})
        error = requests.exceptions.HTTPError(response=response)

        message = http_client.format_request_error("Upload failed", error)

        self.assertIn("temporarily rate-limiting", message)
        self.assertIn("HTTP 429", message)
        self.assertIn("Retry-After: 30", message)
        self.assertNotIn("backend.example", message)


class StreamlitRequestTests(unittest.TestCase):
    def test_project_list_is_cached_and_hidden_tabs_do_not_fetch(self) -> None:
        def fake_get(url: str, **_kwargs: object) -> requests.Response:
            if url.endswith("/projects"):
                return make_response(200, PROJECTS, url=url)
            if url.endswith("/architecture/1"):
                return make_response(200, ARCHITECTURE, url=url)
            if url.endswith("/report/1"):
                return make_response(200, REPORT, url=url)
            self.fail(f"Unexpected GET request: {url}")

        app = AppTest.from_file(str(APP_PATH), default_timeout=10)
        with patch.object(http_client.requests, "get", side_effect=fake_get) as get:
            app.run()
            self.assertEqual(get.call_count, 1)

            app.sidebar.selectbox[0].select("1: sample").run()
            project_calls = [call for call in get.call_args_list if call.args[0].endswith("/projects")]
            self.assertEqual(len(project_calls), 1)
            self.assertFalse(any("/architecture/" in call.args[0] for call in get.call_args_list))
            self.assertFalse(any("/report/" in call.args[0] for call in get.call_args_list))

            app.session_state["main_tabs"] = "🏗️ Architecture Explorer"
            app.run()
            self.assertEqual(
                sum("/architecture/" in call.args[0] for call in get.call_args_list),
                1,
            )
            self.assertFalse(any("/report/" in call.args[0] for call in get.call_args_list))

            architecture_radio = next(
                radio for radio in app.radio if radio.label == "Diagram type"
            )
            architecture_radio.set_value("Database Usage").run()
            self.assertEqual(
                sum("/architecture/" in call.args[0] for call in get.call_args_list),
                1,
            )

            app.session_state["main_tabs"] = "📋 Stored Report"
            app.run()
            self.assertEqual(
                sum("/report/" in call.args[0] for call in get.call_args_list),
                1,
            )

    def test_manual_refresh_reloads_the_project_list(self) -> None:
        app = AppTest.from_file(str(APP_PATH))
        with patch.object(
            http_client.requests,
            "get",
            return_value=make_response(200, PROJECTS),
        ) as get:
            app.run()
            next(button for button in app.sidebar.button if button.label == "↻ Refresh projects").click().run()

        self.assertEqual(get.call_count, 2)

    def test_failed_project_load_is_not_cached_and_can_be_refreshed(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10)
        with (
            patch.object(
                http_client.requests,
                "get",
                side_effect=[
                    make_response(429, {}, headers={"Retry-After": "0"}),
                    make_response(429, {}, headers={"Retry-After": "0"}),
                    make_response(429, {}, headers={"Retry-After": "0"}),
                    make_response(200, PROJECTS),
                ],
            ) as get,
        ):
            app.run()
            self.assertIsNone(app.session_state["projects"])
            self.assertTrue(any("temporarily rate-limiting" in item.value for item in app.sidebar.error))

            next(button for button in app.sidebar.button if button.label == "↻ Refresh projects").click().run()

        self.assertEqual(get.call_count, 4)
        self.assertEqual(app.session_state["projects"], PROJECTS)

    def test_invalid_project_response_is_not_cached(self) -> None:
        app = AppTest.from_file(str(APP_PATH))
        with patch.object(
            http_client.requests,
            "get",
            side_effect=[
                make_response(200, {"unexpected": "shape"}),
                make_response(200, PROJECTS),
            ],
        ) as get:
            app.run()
            self.assertIsNone(app.session_state["projects"])
            self.assertTrue(any("invalid project list" in item.value for item in app.sidebar.error))

            next(button for button in app.sidebar.button if button.label == "↻ Refresh projects").click().run()

        self.assertEqual(get.call_count, 2)
        self.assertEqual(app.session_state["projects"], PROJECTS)

    def test_successful_deletion_refreshes_the_project_list(self) -> None:
        app = AppTest.from_file(str(APP_PATH))
        with (
            patch.object(
                http_client.requests,
                "get",
                side_effect=[
                    make_response(200, PROJECTS),
                    make_response(200, []),
                ],
            ) as get,
            patch("requests.delete", return_value=make_response(200, {"deleted": True})) as delete,
        ):
            app.run()
            app.sidebar.selectbox[0].select("1: sample").run()
            next(
                button
                for button in app.sidebar.button
                if button.label == "🗑️ Delete selected project"
            ).click().run()
            next(button for button in app.button if button.label == "✅ Confirm").click().run()

        delete.assert_called_once()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(app.session_state["projects"], [])

    def test_successful_upload_posts_once_resets_state_and_refreshes_projects(self) -> None:
        uploaded_file = SimpleNamespace(name="sample.zip", getvalue=lambda: b"zip")
        projects = [
            {"id": 1, "project_name": "sample"},
            {"id": 2, "project_name": "sample"},
        ]
        app = AppTest.from_file(str(APP_PATH))
        with (
            patch("streamlit.file_uploader", return_value=uploaded_file),
            patch.object(
                http_client.requests,
                "get",
                side_effect=[
                    make_response(200, projects[:1]),
                    make_response(200, projects),
                ],
            ) as get,
            patch.object(
                http_client.requests,
                "post",
                return_value=make_response(200, {"project_id": 2}),
            ) as post,
        ):
            app.run()
            next(button for button in app.button if button.label == "📤 Send ZIP to Backend").click().run()

        post.assert_called_once()
        self.assertEqual(get.call_count, 2)
        self.assertFalse(app.session_state["upload_in_progress"])
        self.assertEqual(app.session_state["projects"], projects)
        self.assertTrue(any("Project uploaded with ID 2" in item.value for item in app.success))

    def test_failed_upload_resets_in_progress_and_is_not_retried(self) -> None:
        uploaded_file = SimpleNamespace(name="sample.zip", getvalue=lambda: b"zip")
        app = AppTest.from_file(str(APP_PATH))
        with (
            patch("streamlit.file_uploader", return_value=uploaded_file),
            patch.object(
                http_client.requests,
                "get",
                return_value=make_response(200, PROJECTS),
            ),
            patch.object(
                http_client.requests,
                "post",
                side_effect=requests.exceptions.ConnectionError("connection refused"),
            ) as post,
        ):
            app.run()
            next(button for button in app.button if button.label == "📤 Send ZIP to Backend").click().run()

        post.assert_called_once()
        self.assertFalse(app.session_state["upload_in_progress"])
        self.assertTrue(any("Upload failed" in item.value for item in app.error))


if __name__ == "__main__":
    unittest.main()
