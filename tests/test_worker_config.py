from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.worker_config import load_worker_config


class WorkerConfigTests(unittest.TestCase):
    def test_env_fallback_and_relative_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "worker.json"
            config_path.write_text(
                json.dumps(
                    {
                        "timezone": "Asia/Seoul",
                        "monitors": [
                            {
                                "id": "sample",
                                "name": "Sample",
                                "page_url": "https://example.com",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            original_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
            os.environ["DISCORD_WEBHOOK_URL"] = "https://example.com/webhook"
            try:
                config = load_worker_config(config_path)
            finally:
                if original_webhook is None:
                    os.environ.pop("DISCORD_WEBHOOK_URL", None)
                else:
                    os.environ["DISCORD_WEBHOOK_URL"] = original_webhook

        self.assertEqual(config.discord.webhook_url, "https://example.com/webhook")
        self.assertEqual(config.monitors[0].id, "sample")
        self.assertTrue(str(config.state_path).endswith("runtime\\state.json"))


if __name__ == "__main__":
    unittest.main()
