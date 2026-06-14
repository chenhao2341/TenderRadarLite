from __future__ import annotations

import io
import os
import unittest
from unittest import mock


class FeishuBotModeConfigTests(unittest.TestCase):
    def test_webhook_mode_is_recognized(self) -> None:
        from app.feishu import FeishuClient

        with mock.patch.dict(
            os.environ,
            {
                "FEISHU_BOT_MODE": "webhook",
                "FEISHU_WEBHOOK_URL": "https://example.com/hook",
                "FEISHU_APP_ID": "",
                "FEISHU_APP_SECRET": "",
                "FEISHU_CHAT_ID": "",
            },
            clear=False,
        ):
            client = FeishuClient(mock.Mock())

        self.assertEqual(client.bot_mode, "webhook")
        self.assertTrue(client.can_send_webhook())
        self.assertFalse(client.can_send_app_bot())

    def test_app_mode_is_recognized(self) -> None:
        from app.feishu import FeishuClient

        with mock.patch.dict(
            os.environ,
            {
                "FEISHU_BOT_MODE": "app",
                "FEISHU_APP_ID": "cli_xxx",
                "FEISHU_APP_SECRET": "secret-value",
                "FEISHU_CHAT_ID": "oc_xxx",
                "FEISHU_WEBHOOK_URL": "",
            },
            clear=False,
        ):
            client = FeishuClient(mock.Mock())

        self.assertEqual(client.bot_mode, "app")
        self.assertTrue(client.can_send_app_bot())
        self.assertFalse(client.can_send_webhook())

    def test_app_mode_requires_chat_id_for_bot_send(self) -> None:
        from app.feishu import FeishuClient, FeishuConfigError

        with mock.patch.dict(
            os.environ,
            {
                "FEISHU_BOT_MODE": "app",
                "FEISHU_APP_ID": "cli_xxx",
                "FEISHU_APP_SECRET": "secret-value",
                "FEISHU_CHAT_ID": "",
                "FEISHU_WEBHOOK_URL": "",
            },
            clear=False,
        ):
            client = FeishuClient(mock.Mock())

        with self.assertRaises(FeishuConfigError) as ctx:
            client.send_bot_message("hello")

        self.assertIn("--list-feishu-chats", str(ctx.exception))
        self.assertNotIn("secret-value", str(ctx.exception))

    def test_app_mode_with_empty_webhook_uses_app_branch(self) -> None:
        from app.feishu import FeishuClient

        with mock.patch.dict(
            os.environ,
            {
                "FEISHU_BOT_MODE": " app ",
                "FEISHU_APP_ID": "cli_xxx",
                "FEISHU_APP_SECRET": "secret-value",
                "FEISHU_CHAT_ID": "oc_xxx",
                "FEISHU_WEBHOOK_URL": "",
            },
            clear=False,
        ):
            client = FeishuClient(mock.Mock())

        with (
            mock.patch.object(client, "send_app_message", return_value=True) as send_app,
            mock.patch.object(client, "send_text_message", return_value=True) as send_text,
        ):
            result = client.send_bot_message("hello")

        self.assertTrue(result)
        send_app.assert_called_once_with("hello")
        send_text.assert_not_called()

    def test_webhook_mode_without_webhook_reports_webhook_missing(self) -> None:
        from app.feishu import FeishuClient, FeishuConfigError

        with mock.patch.dict(
            os.environ,
            {
                "FEISHU_BOT_MODE": "webhook",
                "FEISHU_APP_ID": "cli_xxx",
                "FEISHU_APP_SECRET": "secret-value",
                "FEISHU_CHAT_ID": "oc_xxx",
                "FEISHU_WEBHOOK_URL": "",
            },
            clear=False,
        ):
            client = FeishuClient(mock.Mock())

        with self.assertRaises(FeishuConfigError) as ctx:
            client.send_bot_message("hello")

        self.assertIn("FEISHU_WEBHOOK_URL", str(ctx.exception))
        self.assertNotIn("FEISHU_CHAT_ID", str(ctx.exception))


class FeishuBotCommandTests(unittest.TestCase):
    def test_list_feishu_chats_prints_groups_without_side_effects(self) -> None:
        from app.main import main

        fake_client = mock.Mock()
        fake_client.list_chats.return_value = [
            {"name": "Tender Group", "chat_id": "oc_123"},
            {"name": "Ops Group", "chat_id": "oc_456"},
        ]

        stdout = io.StringIO()
        with (
            mock.patch("app.main.FeishuClient", return_value=fake_client),
            mock.patch("app.main.run_once") as run_once,
            mock.patch("app.main.backfill_feishu") as backfill_feishu,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(["--list-feishu-chats"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Tender Group", stdout.getvalue())
        self.assertIn("oc_123", stdout.getvalue())
        run_once.assert_not_called()
        backfill_feishu.assert_not_called()
        fake_client.write_notice.assert_not_called()
        fake_client.create_test_record.assert_not_called()
        fake_client.send_bot_message.assert_not_called()

    def test_test_feishu_bot_uses_app_mode_without_crawl_or_bitable(self) -> None:
        from app.main import main

        fake_client = mock.Mock()
        fake_client.bot_mode = "app"

        stdout = io.StringIO()
        with (
            mock.patch("app.main.FeishuClient", return_value=fake_client),
            mock.patch("app.main.run_once") as run_once,
            mock.patch("app.main.backfill_feishu") as backfill_feishu,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(["--test-feishu-bot"])

        self.assertEqual(exit_code, 0)
        fake_client.send_bot_message.assert_called_once_with("TenderRadarLite 应用机器人发送测试成功")
        fake_client.write_notice.assert_not_called()
        fake_client.create_test_record.assert_not_called()
        run_once.assert_not_called()
        backfill_feishu.assert_not_called()
        self.assertIn("bot test message sent", stdout.getvalue())

    def test_test_feishu_bot_reports_safe_failure_without_leaking_secret(self) -> None:
        from app.main import main
        from app.feishu import FeishuConfigError

        fake_client = mock.Mock()
        fake_client.send_bot_message.side_effect = FeishuConfigError(
            "FEISHU_CHAT_ID 未配置：app 模式请先执行 python run_mvp.py --list-feishu-chats"
        )

        stdout = io.StringIO()
        with (
            mock.patch("app.main.FeishuClient", return_value=fake_client),
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(["--test-feishu-bot"])

        self.assertEqual(exit_code, 2)
        output = stdout.getvalue()
        self.assertIn("--list-feishu-chats", output)
        self.assertNotIn("tenant_access_token", output)
        self.assertNotIn("secret-value", output)
        self.assertNotIn("https://example.com/hook", output)


if __name__ == "__main__":
    unittest.main()
